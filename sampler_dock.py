# -*- coding: utf-8 -*-

import os
import sip
from datetime import datetime

from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QTextEdit, QFrame, QFileDialog,
    QMessageBox, QSizePolicy, QScrollArea, QDialog,
    QInputDialog, QLineEdit, QRadioButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressDialog
)
from qgis.PyQt.QtCore import Qt, QTimer, QSize
from qgis.PyQt.QtGui import QPixmap, QIcon

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature,
    QgsProject, QgsWkbTypes, QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
    QgsAttributeTableConfig, QgsEditorWidgetSetup,
    QgsProcessingMultiStepFeedback, QgsProcessingFeedback,
    QgsGeometry, QgsFeatureRequest, QgsMapLayer, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsFields, QgsDistanceArea,
    QgsExpression, QgsFeatureRequest as QgsFeatReq
)
from qgis.PyQt.QtCore import QVariant

import processing

from .db_manager import DBManager, sanitize_text
from .db_config  import BIOMAS, CLASSES_POR_BIOMA
from .login_dialog         import LoginDialog
from .class_manager_dialog import ClassManagerDialog

PIXEL_SIZE_M = 10.0

# ── Paleta pastel ────────────────────────────────────────────────
C_BG      = '#FAFBFC'
C_SURFACE = '#FFFFFF'
C_BORDER  = '#E8ECF0'
C_TEXT    = '#2D3142'
C_MUTED   = '#8A93A2'

C_SAGE    = '#9BBFA8'
C_STEEL   = '#7EB8D4'
C_SAND    = '#C9B99A'
C_SLATE   = '#A0AEC0'
C_ROSE    = '#D4908A'
C_LINK    = '#5B9BBF'

_TXT_SAGE  = '#FFFFFF'
_TXT_STEEL = '#FFFFFF'
_TXT_SAND  = '#5A4200'
_TXT_SLATE = '#FFFFFF'
_TXT_ROSE  = '#FFFFFF'

def _pill(bg, txt='#FFFFFF'):
    return f"""
        QPushButton {{
            background: {bg}; color: {txt};
            border: none; border-radius: 7px;
            font-size: 8.5pt; font-weight: 600;
            padding: 0 12px; min-height: 30px;
        }}
        QPushButton:hover   {{ background: {bg}CC; }}
        QPushButton:pressed {{ background: {bg}99; }}
        QPushButton:disabled {{ background: #E2E8F0; color: #A0AEC0; }}
    """

_BTN_ACT = f"""
    QPushButton {{
        background: {C_SURFACE}; color: {C_TEXT};
        border: 1.5px solid {C_BORDER};
        border-radius: 7px;
        font-size: 8.5pt; font-weight: 600;
        padding: 0 12px; min-height: 30px;
    }}
    QPushButton:hover {{
        background: #2D3142; color: #FFFFFF;
        border-color: #2D3142;
    }}
    QPushButton:pressed {{
        background: #1A1E2E; color: #FFFFFF;
        border-color: #1A1E2E;
    }}
    QPushButton:disabled {{
        background: #E2E8F0; color: #A0AEC0;
    }}
"""

class PieChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._slices = []

    def set_data(self, slices):
        self._slices = [s for s in slices if s[1] > 0]
        self.update()

    def paintEvent(self, event):
        from qgis.PyQt.QtGui import QPainter, QColor, QFont, QPen, QBrush
        from qgis.PyQt.QtCore import QRectF, Qt
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W = self.width()
        H = self.height()
        margin = 12
        pie_size = min(W, H) - (margin * 2)
        pie_size = max(pie_size, 10)
        pie_x = (W - pie_size) / 2
        pie_y = (H - pie_size) / 2
        rect = QRectF(pie_x, pie_y, pie_size, pie_size)
        if not self._slices:
            p.setPen(QPen(QColor("#FFFFFF"), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(rect)
            p.setPen(QColor('#8A93A2'))
            p.setFont(QFont('Segoe UI', 8))
            p.drawText(rect, Qt.AlignCenter, 'sem dados')
            p.end()
            return
        total = sum(v for _, v, _ in self._slices)
        if total <= 0:
            p.end()
            return
        start_angle = 90 * 16
        for label, value, color in self._slices:
            if value <= 0:
                continue
            span_angle = int((value / total) * 360 * 16)
            p.setBrush(QBrush(QColor(color)))
            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.drawPie(rect, start_angle, -span_angle)
            start_angle -= span_angle
        p.end()

class SamplerDock(QDockWidget):

    def __init__(self, iface, plugin):
        super().__init__('Sample Design')
        self.iface  = iface
        self.plugin = plugin
        self.canvas = iface.mapCanvas()

        self.user_info    = None
        self.biome        = None
        self.project_type = None
        self.is_auditor   = False
        self.classes      = []
        self.layer        = None
        self.layer_id     = None
        self.total        = 0
        self.counts       = {}
        self._undo_stack  = []
        self._redo_stack  = []
        self._next_fid    = 1
        self.pixel_size   = 10
        self.is_admin     = False
        self.max_scale    = 10000
        self._enforcing_scale = False
        self._is_local_geopackage = False

        self.tile_layer   = None
        self.subregion_layer = None

        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        self.db = DBManager()
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))

        self._build_ui()
        self.canvas.scaleChanged.connect(self._on_scale_changed)

    @staticmethod
    def _safe_set_enabled(widget, enabled):
        if widget and not sip.isdeleted(widget):
            widget.setEnabled(enabled)

    @staticmethod
    def _layer_ok(layer):
        return layer and not sip.isdeleted(layer)

    # ═══════════════════════════════════════════════════════════════
    # LOGIN / SESSÃO
    # ═══════════════════════════════════════════════════════════════
    def _request_login(self):
        ok, err = self.db.test_connection()
        if not ok:
            self._log(f'Sem conexão: {err}')
            self._start_local_mode()
            return
        try:
            self.db.bootstrap()
        except Exception as e:
            self._log(f'Aviso: {e}')

        dlg = LoginDialog(self.db, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            self._start_local_mode()
            return

        self.user_info    = dlg.user_info
        self.biome        = dlg.biome
        self.project_type = dlg.project_type
        self.is_admin     = self.user_info.get('is_admin', False)
        self.is_auditor   = self.user_info.get('is_auditor', False)
        config = self.db.get_biome_config(self.biome)
        self.max_scale = config['max_scale']
        self._is_local_geopackage = False
        self._on_session_started()
        self._refresh_filtros()

    def _on_session_started(self):
        username = self.user_info['username']
        nome     = self.user_info.get('nome_completo', username)

        self.lbl_user.setText(nome)
        self.lbl_biome_val.setText(f"{self.biome} - {self.project_type}" if self.project_type else self.biome)
        self.btn_session.setText('Sair')
        self.btn_session.setStyleSheet(_pill(C_ROSE))

        if not self._is_local_geopackage and username != 'local':
            self.db.ensure_user_biome(username, self.biome)

        if self._is_local_geopackage:
            self.classes = list(CLASSES_POR_BIOMA.get((self.biome, 'Prodes'), []))
        else:
            self.classes = self.db.get_custom_classes(self.biome, self.project_type, username)

        self.counts = {c[0]: 0 for c in self.classes}
        self._populate_combo()
        is_admin = self.user_info.get('is_admin', False) and not self._is_local_geopackage
        self.btn_mgr.setVisible(is_admin)
        self.btn_manage_users.setVisible(is_admin)      # movido para junto do gerenciador de classes

        self._safe_set_enabled(self.spin, is_admin)
        self._safe_set_enabled(self.spin_max_scale, is_admin)
        self.spin_max_scale.setValue(self.max_scale)

        # Mostrar/ocultar controles de auditoria
        self.audit_mode_cb.setVisible(self.is_auditor)
        self.grp_upload.setVisible(is_admin and not self._is_local_geopackage)
        if self.is_auditor:
            self.audit_mode_cb.setChecked(False)

        self._rebuild_counters_grid()

        if not self._is_local_geopackage:
            filter_by_user = not self.is_auditor
            layer, err = self.db.get_postgis_layer(self.biome, self.project_type, username,
                                                   filter_by_user=filter_by_user)
            if err:
                self._log(err)
                self._start_local_mode()
                return
            self.layer    = layer
            self.layer_id = layer.id()

        self._apply_style()
        self._configure_layer_visibility(is_admin)
        if self._layer_ok(self.layer):
            QgsProject.instance().addMapLayer(self.layer, False)
            QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        self._sync_counts(username)
        self._refresh_timer.start()
        self._log(f'Sessão iniciada — {nome} · {self.biome} · {self.project_type}')
        self.btn_wfs.setEnabled(self._is_local_geopackage)

    def _start_local_mode(self):
        self.user_info    = {'username': 'local', 'nome_completo': 'Modo local'}
        self.biome        = list(BIOMAS.keys())[0]
        self.project_type = 'Prodes'
        self.is_auditor   = False
        self.classes      = list(CLASSES_POR_BIOMA.get((self.biome, 'Prodes'), []))
        self.counts       = {c[0]: 0 for c in self.classes}
        self.is_admin     = False
        self.max_scale    = 10000
        self._is_local_geopackage = False
        self._safe_set_enabled(self.spin, False)
        self._safe_set_enabled(self.spin_max_scale, False)
        self.spin_max_scale.setValue(self.max_scale)
        self.lbl_user.setText('Sem conexão')
        self.lbl_user.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        self.lbl_biome_val.setText(self.biome)
        self._populate_combo()
        self._rebuild_counters_grid()
        self._new_memory_layer()
        self._configure_layer_visibility(False)
        self._log('Modo local ativo.')
        self.btn_mgr.setVisible(False)
        self.btn_manage_users.setVisible(False)
        self.btn_wfs.setEnabled(False)
        self.audit_mode_cb.setVisible(False)
        self.grp_upload.setVisible(False)

    def _logout(self):
        self._refresh_timer.stop()
        if self._is_local_geopackage and self._layer_ok(self.layer):
            QgsProject.instance().removeMapLayer(self.layer)
        self.tile_layer = None
        self.subregion_layer = None
        self.user_info    = None
        self.biome        = None
        self.project_type = None
        self.is_auditor   = False
        self.classes      = []
        self.layer        = None
        self.layer_id     = None
        self.is_admin     = False
        self.max_scale    = 10000
        self._is_local_geopackage = False
        self._safe_set_enabled(self.spin, False)
        self._safe_set_enabled(self.spin_max_scale, False)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.total  = 0
        self.counts = {}
        self._update_counters()
        self.lbl_user.setText('—')
        self.lbl_biome_val.setText('—')
        self.btn_session.setText('Entrar')
        self.btn_session.setStyleSheet(_pill(C_STEEL))
        self.btn_wfs.setEnabled(False)
        self.audit_mode_cb.setVisible(False)
        self.btn_manage_users.setVisible(False)
        self.grp_upload.setVisible(False)

    def _sync_counts(self, username):
        if not self._layer_ok(self.layer):
            return
        self.total  = 0
        self.counts = {c[0]: 0 for c in self.classes}
        analyst_idx = self.layer.fields().indexOf('analyst')
        if analyst_idx == -1:
            analyst_idx = self.layer.fields().indexOf('interpreter')
        if analyst_idx == -1:
            self._log("Campo 'analyst' não encontrado.")
            return
        label_idx = self.layer.fields().indexOf('label')
        for feat in self.layer.getFeatures():
            if self.is_auditor or feat[analyst_idx] == username:
                self.total += 1
                code = feat[label_idx] if label_idx >= 0 else ''
                if code in self.counts:
                    self.counts[code] += 1
        self._update_counters()

    def _reset_session_counts(self):
        if not self.user_info:
            return
        self.total = 0
        self.counts = {c[0]: 0 for c in self.classes}
        self._update_counters()
        self._log('Contadores de sessão reiniciados.')
        self._update_filtered_count()

    def _on_session_btn(self):
        if self._is_local_geopackage or (self.user_info and self.user_info.get('username') != 'local'):
            if QMessageBox.question(
                self, 'Sample Design', 'Encerrar sessão?',
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self._logout()
        else:
            self._request_login()

    # ═══════════════════════════════════════════════════════════════
    # BUILD UI
    # ═══════════════════════════════════════════════════════════════
    def _build_ui(self):
        root = QWidget()
        root.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        root.setStyleSheet(f"""
            QWidget {{
                background: {C_BG}; color: {C_TEXT};
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 9pt;
            }}
            QGroupBox {{
                background: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px 10px 8px 10px;
                font-weight: 600; font-size: 8pt;
                color: {C_MUTED};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; top: -1px;
                padding: 0 4px; background: {C_BG};
                letter-spacing: 0.6px; text-transform: uppercase;
            }}
            QComboBox {{
                background: {C_SURFACE};
                border: 1.5px solid {C_BORDER};
                border-radius: 7px;
                padding: 5px 10px; font-size: 9.5pt;
            }}
            QComboBox:hover {{ border-color: #C5CDD8; }}
            QComboBox:focus {{ border-color: {C_STEEL}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QSpinBox {{
                background: {C_SURFACE};
                border: 1.5px solid {C_BORDER};
                border-radius: 7px; padding: 4px 8px;
            }}
            QSpinBox:focus {{ border-color: {C_STEEL}; }}
            QTextEdit {{
                background: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-radius: 7px; padding: 4px;
                font-family: 'Consolas','Courier New',monospace;
                font-size: 7.5pt; color: {C_MUTED};
            }}
        """)

        lay = QVBoxLayout(root)
        lay.setSpacing(10)
        lay.setContentsMargins(14, 16, 14, 16)

        # Header
        hdr = QHBoxLayout(); hdr.setSpacing(10)
        icon_path = os.path.join(self._plugin_dir, 'icons', 'sample_design_icon.png')
        if os.path.exists(icon_path):
            ico = QLabel()
            px  = QPixmap(icon_path).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ico.setPixmap(px); ico.setFixedSize(30, 30); hdr.addWidget(ico)
        t1 = QLabel('Sample Design')
        t1.setStyleSheet(f'font-size: 13pt; font-weight: 700; color: {C_TEXT}; letter-spacing: -0.3px;')
        hdr.addWidget(t1); hdr.addStretch(); lay.addLayout(hdr)
        self._sep(lay, top=6, bottom=2)

        # Sessão
        grp_s = QGroupBox('Sessão'); gs = QVBoxLayout(grp_s); gs.setSpacing(5)
        row_u = QHBoxLayout(); row_u.setSpacing(4)
        lbl_u_full = QLabel('Usuário:'); lbl_u_full.setFixedWidth(55); lbl_u_full.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:700; background:transparent;')
        self.lbl_user = QLabel('—'); self.lbl_user.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        row_u.addWidget(lbl_u_full); row_u.addWidget(self.lbl_user); row_u.addStretch(); gs.addLayout(row_u)
        row_b = QHBoxLayout(); row_b.setSpacing(4)
        lbl_b_full = QLabel('Bioma:'); lbl_b_full.setFixedWidth(55); lbl_b_full.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:700; background:transparent;')
        self.lbl_biome_val = QLabel('—'); self.lbl_biome_val.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        row_b.addWidget(lbl_b_full); row_b.addWidget(self.lbl_biome_val); row_b.addStretch(); gs.addLayout(row_b)
        self.btn_session = QPushButton('Entrar'); self.btn_session.setMinimumHeight(30); self.btn_session.setStyleSheet(_pill(C_STEEL)); self.btn_session.clicked.connect(self._on_session_btn)
        gs.addWidget(self.btn_session)

        self.btn_geopackage = QPushButton('Abrir GeoPackage')
        self.btn_geopackage.setMinimumHeight(30)
        self.btn_geopackage.setStyleSheet(_BTN_ACT)
        self.btn_geopackage.clicked.connect(self._open_geopackage)
        gs.addWidget(self.btn_geopackage)

        lay.addWidget(grp_s)

        # ── Admin upload GeoPackage ─────────────────────────
        self.grp_upload = QGroupBox('Arquivo local')
        self.grp_upload.setVisible(False)
        gu = QVBoxLayout(self.grp_upload)
        self.btn_upload_gpkg = QPushButton('Selecionar GeoPackage e Submeter')
        self.btn_upload_gpkg.setStyleSheet(_BTN_ACT)
        self.btn_upload_gpkg.clicked.connect(self._submit_geopackage)
        gu.addWidget(self.btn_upload_gpkg)
        self.lbl_upload_status = QLabel('')
        self.lbl_upload_status.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        gu.addWidget(self.lbl_upload_status)
        lay.addWidget(self.grp_upload)

        # Classe
        grp_cls = QGroupBox('Classe'); lc = QVBoxLayout(grp_cls); lc.setSpacing(6)
        self.cls_color_bar = QFrame(); self.cls_color_bar.setFixedHeight(3); self.cls_color_bar.setStyleSheet('background: #C5CDD8; border-radius: 2px;')
        self.combo = QComboBox(); self.combo.setMinimumHeight(34); self.combo.currentIndexChanged.connect(self._on_class_changed)
        lc.addWidget(self.combo); lc.addWidget(self.cls_color_bar)
        self.btn_mgr = QPushButton('Gerenciar classes'); self.btn_mgr.setMinimumHeight(26); self.btn_mgr.clicked.connect(self._open_class_manager)
        self.btn_mgr.setStyleSheet(f'QPushButton {{ background:transparent; color:{C_LINK}; border:1.5px solid {C_BORDER}; border-radius:7px; font-size:8pt; font-weight:600; padding:0 10px; min-height:26px; }} QPushButton:hover {{ background:#EEF6FB; border-color:{C_STEEL}; }}')
        lc.addWidget(self.btn_mgr)
        # ── Gerenciar usuários (admin) ──
        self.btn_manage_users = QPushButton('Gerenciar usuários')
        self.btn_manage_users.setMinimumHeight(26)
        self.btn_manage_users.setStyleSheet(f'QPushButton {{ background:transparent; color:{C_LINK}; border:1.5px solid {C_BORDER}; border-radius:7px; font-size:8pt; font-weight:600; padding:0 10px; min-height:26px; }} QPushButton:hover {{ background:#EEF6FB; border-color:{C_STEEL}; }}')
        self.btn_manage_users.clicked.connect(self._manage_users)
        self.btn_manage_users.setVisible(False)
        lc.addWidget(self.btn_manage_users)
        lay.addWidget(grp_cls)

        # Janela de Amostragem
        grp_w = QGroupBox('Janela de Amostragem'); lw = QVBoxLayout(grp_w); lw.setSpacing(4)
        row_size = QHBoxLayout(); row_size.setSpacing(8)
        lbl_size = self._small('Tamanho:')
        lbl_size.setFixedWidth(75)
        row_size.addWidget(lbl_size)
        self.spin = QSpinBox(); self.spin.setRange(1, 50); self.spin.setValue(10); self.spin.setSuffix(' px'); self.spin.setFixedWidth(78)
        self.spin.valueChanged.connect(self._on_spin)
        row_size.addWidget(self.spin)
        self.lbl_m = QLabel('= 100 × 100 m'); self.lbl_m.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        row_size.addWidget(self.lbl_m); row_size.addStretch(); lw.addLayout(row_size)
        row_max_scale = QHBoxLayout(); row_max_scale.setSpacing(8)
        lbl_scale = self._small('Escala máx.:')
        lbl_scale.setFixedWidth(75)
        row_max_scale.addWidget(lbl_scale)
        self.spin_max_scale = QSpinBox()
        self.spin_max_scale.setRange(100, 1000000)
        self.spin_max_scale.setValue(10000)
        self.spin_max_scale.setFixedWidth(78)
        self.spin_max_scale.valueChanged.connect(self._on_max_scale_changed)
        row_max_scale.addWidget(self.spin_max_scale)
        lbl_suffix = QLabel('(1:x)'); lbl_suffix.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        row_max_scale.addWidget(lbl_suffix); row_max_scale.addStretch(); lw.addLayout(row_max_scale)
        lay.addWidget(grp_w)

        # ── Modo de desenho (square / polygon) ─────────────────────
        grp_mode = QGroupBox('Modo de desenho')
        mode_layout = QHBoxLayout(grp_mode)
        self.radio_square = QRadioButton('Quadrado pré-definido')
        self.radio_polygon = QRadioButton('Polígono livre')
        self.radio_square.setChecked(True)
        mode_layout.addWidget(self.radio_square)
        mode_layout.addWidget(self.radio_polygon)
        lay.addWidget(grp_mode)
        self._sep(lay)

        self._draw_mode = 'square'
        self.radio_square.toggled.connect(self._on_mode_changed)
        self.radio_polygon.toggled.connect(self._on_mode_changed)

        # Dashboard de Amostras
        grp_cnt = QGroupBox('Amostras'); lcnt = QVBoxLayout(grp_cnt); lcnt.setSpacing(6)
        self.lbl_total = QLabel('0'); self.lbl_total.setAlignment(Qt.AlignCenter)
        self.lbl_total.setStyleSheet(f'font-size:26pt; font-weight:700; color:{C_TEXT}; padding:4px; letter-spacing:-1px;')
        lcnt.addWidget(self.lbl_total)
        sub = QLabel('coletadas nesta sessão'); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt; margin-bottom:2px;')
        lcnt.addWidget(sub)
        
        # Reset session button
        btn_reset = QPushButton('Resetar contagem')
        btn_reset.setStyleSheet(_BTN_ACT)
        btn_reset.clicked.connect(self._reset_session_counts)
        lcnt.addWidget(btn_reset)
        
        # ── Auditoria ─────────────────────
        self.audit_mode_cb = QCheckBox('Modo Auditoria')
        self.audit_mode_cb.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        self.audit_mode_cb.setVisible(False)
        self.audit_mode_cb.toggled.connect(self._toggle_audit_mode)
        lcnt.addWidget(self.audit_mode_cb)
        
        self._sep(lcnt, top=2, bottom=4)
        self.pie_widget = PieChartWidget(); self.pie_widget.setFixedHeight(160); lcnt.addWidget(self.pie_widget)
        self._sep(lcnt, top=4, bottom=4)
        row_filtros = QHBoxLayout(); row_filtros.setSpacing(6)
        col_t = QVBoxLayout(); col_t.setSpacing(2); col_t.addWidget(self._small('Tile'))
        self.combo_tile = QComboBox(); self.combo_tile.setMinimumHeight(26); self.combo_tile.addItem('Todos'); self.combo_tile.currentIndexChanged.connect(self._update_filtered_count); col_t.addWidget(self.combo_tile)
        col_e = QVBoxLayout(); col_e.setSpacing(2); col_e.addWidget(self._small('Ecorregião'))
        self.combo_eco = QComboBox(); self.combo_eco.setMinimumHeight(26); self.combo_eco.addItem('Todas'); self.combo_eco.currentIndexChanged.connect(self._update_filtered_count); col_e.addWidget(self.combo_eco)
        row_filtros.addLayout(col_t); row_filtros.addLayout(col_e); lcnt.addLayout(row_filtros)
        self.lbl_filtro_total = QLabel('Filtrado: 0')
        self.lbl_filtro_total.setStyleSheet(f'font-size:8pt; font-weight:700; color:{C_TEXT};')
        lcnt.addWidget(self.lbl_filtro_total)
        self._sep(lcnt, top=2, bottom=4)
        self.cnt_grid_widget = QWidget(); self.cnt_grid_layout = QGridLayout(self.cnt_grid_widget); self.cnt_grid_layout.setSpacing(3); self.cnt_grid_layout.setColumnStretch(1, 1); self.count_labels = {}; lcnt.addWidget(self.cnt_grid_widget)
        btn_relatorio = QPushButton('Gerar relatório')
        btn_relatorio.setStyleSheet(_BTN_ACT)
        btn_relatorio.clicked.connect(self._gerar_relatorio)
        lcnt.addWidget(btn_relatorio)
        lay.addWidget(grp_cnt)

        self._sep(lay)

        # Ações
        btn_undo = QPushButton('↩  Desfazer'); btn_undo.setStyleSheet(_BTN_ACT); btn_undo.clicked.connect(self._undo); lay.addWidget(btn_undo)
        btn_redo = QPushButton('↪  Refazer'); btn_redo.setStyleSheet(_BTN_ACT); btn_redo.clicked.connect(self._redo); lay.addWidget(btn_redo)
        btn_ref  = QPushButton('↺  Atualizar mapa'); btn_ref.setStyleSheet(_BTN_ACT); btn_ref.clicked.connect(self._manual_refresh); lay.addWidget(btn_ref)
        btn_exp  = QPushButton('↑  Exportar'); btn_exp.setStyleSheet(_BTN_ACT); btn_exp.clicked.connect(self._export); lay.addWidget(btn_exp)

        self.btn_wfs = QPushButton('Exportar para WFS')
        self.btn_wfs.setStyleSheet(_BTN_ACT)
        self.btn_wfs.clicked.connect(self._export_to_wfs)
        self.btn_wfs.setEnabled(False)
        lay.addWidget(self.btn_wfs)

        self._sep(lay)

        # Log
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(80); lay.addWidget(self.log)

        # Scroll
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setWidget(root)
        scroll.setStyleSheet(f"""QScrollArea {{ border:none; background:{C_BG}; }} QScrollBar:vertical {{ background:transparent; width:8px; }} QScrollBar::handle:vertical {{ background:#D1D9E0; border-radius:4px; min-height:20px; }} QScrollBar::handle:vertical:hover {{ background:#A0AEC0; }} QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }} QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}""")
        self.setWidget(scroll)
        self.setMinimumWidth(220)

    def _on_mode_changed(self):
        if self.radio_square.isChecked():
            self._draw_mode = 'square'
        else:
            self._draw_mode = 'polygon'
        if hasattr(self, 'tool') and self.tool:
            self.tool.set_mode(self._draw_mode)

    def get_draw_mode(self):
        return self._draw_mode

    # ── Abrir GeoPackage OFFLINE ──────────────────────────────
    def _find_layer_by_keyword(self, gpkg_path, keyword):
        root = QgsVectorLayer(gpkg_path, '', 'ogr')
        for sl in root.dataProvider().subLayers():
            name = sl.split('!!::!!')[1]
            if keyword.lower() in name.lower():
                return QgsVectorLayer(f"{gpkg_path}|layername={name}", name, 'ogr')
        return None

    def _open_geopackage(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir GeoPackage', '', 'GeoPackage (*.gpkg)')
        if not path:
            return
        analyst, ok = QInputDialog.getText(self, 'Analista', 'Nome do analista:')
        if not ok or not analyst.strip():
            return
        analyst = analyst.strip()
        biome, ok = QInputDialog.getItem(self, 'Bioma', 'Selecione o bioma:', list(BIOMAS.keys()), 0, False)
        if not ok:
            return

        sample_layer = self._find_layer_by_keyword(path, 'amostras')
        if not sample_layer or not sample_layer.isValid():
            QMessageBox.critical(self, 'Erro', 'Não foi possível encontrar a camada de amostras no GeoPackage.')
            return

        self.tile_layer = self._find_layer_by_keyword(path, 'tile')
        self.subregion_layer = self._find_layer_by_keyword(path, 'subregio')

        if not self.tile_layer:
            self._log('Aviso: camada de tiles não encontrada.')
        if not self.subregion_layer:
            self._log('Aviso: camada de subregiões não encontrada.')

        pr = sample_layer.dataProvider()
        fields = sample_layer.fields()
        if fields.indexOf('analyst') == -1:
            pr.addAttributes([QgsField('analyst', QVariant.String, 'string', 100)])
            sample_layer.updateFields()
        if fields.indexOf('biome') == -1:
            pr.addAttributes([QgsField('biome', QVariant.String, 'string', 50)])
            sample_layer.updateFields()

        if self._layer_ok(self.layer):
            QgsProject.instance().removeMapLayer(self.layer)
        self.layer = sample_layer
        self.layer_id = sample_layer.id()
        self._is_local_geopackage = True
        self.user_info = {'username': analyst, 'nome_completo': analyst}
        self.biome = biome
        self.project_type = 'Prodes'
        self.is_auditor = False
        self.classes = list(CLASSES_POR_BIOMA.get((biome, 'Prodes'), []))
        self.counts = {c[0]: 0 for c in self.classes}
        self.is_admin = False
        self.max_scale = 10000
        self._safe_set_enabled(self.spin, False)
        self._safe_set_enabled(self.spin_max_scale, False)
        self.spin_max_scale.setValue(self.max_scale)
        self.lbl_user.setText(analyst)
        self.lbl_biome_val.setText(biome)
        self.btn_session.setText('Fechar GeoPackage')
        self.btn_session.setStyleSheet(_pill(C_ROSE))
        self.btn_mgr.setVisible(False)
        self.btn_manage_users.setVisible(False)
        self.btn_wfs.setEnabled(True)
        self._populate_combo()
        self._rebuild_counters_grid()
        self._apply_style()
        self._configure_layer_visibility(False)
        QgsProject.instance().addMapLayer(self.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        
        self._refresh_filtros()
        self._sync_counts(analyst)
        self._log(f'GeoPackage aberto: {path} — {analyst} · {biome}')

    # ── Visibilidade das colunas ───────────────────────────────
    def _configure_layer_visibility(self, is_admin):
        if not self._layer_ok(self.layer): return
        always_hidden = {'área', 'ações'}
        hidden_for_non_admin = {'area_m2', 'px_size', 'window_px', 'analyst'}
        if not is_admin and not self.is_auditor:
            hidden_for_non_admin.update({'audit', 'label_audit'})
        cfg = self.layer.attributeTableConfig()
        columns = cfg.columns()
        for col in columns:
            if col.name in always_hidden or col.name in hidden_for_non_admin:
                col.hidden = True
            else:
                col.hidden = False
        cfg.setColumns(columns)
        self.layer.setAttributeTableConfig(cfg)
        idx_audit = self.layer.fields().indexOf('label_audit')
        if idx_audit >= 0:
            options = [(label, code) for code, label, _ in self.classes]
            setup = QgsEditorWidgetSetup('ValueMap', {'map': dict(options)})
            self.layer.setEditorWidgetSetup(idx_audit, setup)

    # ── Restrição de escala ─────────────────────────────────────
    def _on_scale_changed(self, scale):
        if not self.is_admin and not self._enforcing_scale:
            if scale < self.max_scale:
                self._enforcing_scale = True
                self.canvas.zoomScale(self.max_scale)
                self._enforcing_scale = False

    def _on_max_scale_changed(self, value):
        self.max_scale = value
        if not self._is_local_geopackage and self.user_info and self.user_info.get('username') != 'local':
            self.db.set_biome_config(self.biome, value)

    # ═══════════════════════════════════════════════════════════════
    # AUDITORIA
    # ═══════════════════════════════════════════════════════════════
    def _toggle_audit_mode(self, checked):
        if not self._layer_ok(self.layer):
            return
        if checked:
            self.layer.selectionChanged.connect(self._on_audit_selection)
            self._log('Modo Auditoria ativado.')
        else:
            try:
                self.layer.selectionChanged.disconnect(self._on_audit_selection)
            except TypeError:
                pass
            self._log('Modo Auditoria desativado.')

    def _on_audit_selection(self):
        if not self._layer_ok(self.layer) or not self.user_info:
            return
        if not self.is_auditor:
            return
        
        selected_ids = self.layer.selectedFeatureIds()
        if not selected_ids:
            return
        
        code = self.combo.currentData()
        if not code:
            self._log('Nenhuma classe selecionada para auditoria.')
            return
        
        auditor = self.user_info['username']
        layer = self.layer
        fields = layer.fields()
        idx_label_audit = fields.indexOf('label_audit')
        idx_audit = fields.indexOf('audit')
        
        if idx_label_audit == -1 or idx_audit == -1:
            self._log('Campos de auditoria não encontrados na camada.')
            return
        
        changes = {}
        for fid in selected_ids:
            changes[fid] = {idx_label_audit: code, idx_audit: auditor}
        
        if self._is_local_geopackage:
            layer.dataProvider().changeAttributeValues(changes)
            layer.updateExtents()
            self.canvas.refresh()
        else:
            layer.dataProvider().changeAttributeValues(changes)
            layer.triggerRepaint()
        
        self._log(f'Auditoria aplicada: {len(selected_ids)} polígono(s) com classe "{self.combo.currentText()}" pelo usuário {auditor}.')
        self._sync_counts(self.user_info['username'])
        self._refresh_filtros()

    # ═══════════════════════════════════════════════════════════════
    # GERENCIAR USUÁRIOS (admin)
    # ═══════════════════════════════════════════════════════════════
    def _manage_users(self):
        if not self.is_admin or self._is_local_geopackage:
            return

        users = self.db.get_active_users()          # agora retorna todos os ativos com is_auditor
        dlg = QDialog(self)
        dlg.setWindowTitle('Gerenciar Usuários')
        dlg.setMinimumWidth(600)
        layout = QVBoxLayout(dlg)

        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(['Usuário', 'Nome completo', 'Bioma padrão', 'Admin', 'Auditor'])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)

        def refresh_table():
            nonlocal users
            users = self.db.get_active_users()
            tbl.setRowCount(0)
            for i, u in enumerate(users):
                tbl.insertRow(i)
                tbl.setItem(i, 0, QTableWidgetItem(u['username']))
                tbl.setItem(i, 1, QTableWidgetItem(u.get('nome_completo', '')))
                tbl.setItem(i, 2, QTableWidgetItem(u.get('bioma_padrao', '')))
                tbl.setItem(i, 3, QTableWidgetItem('Sim' if u.get('is_admin') else 'Não'))
                tbl.setItem(i, 4, QTableWidgetItem('Sim' if u.get('is_auditor') else 'Não'))
        refresh_table()

        layout.addWidget(tbl)

        btn_row = QHBoxLayout()
        btn_add = QPushButton('Adicionar usuário')
        btn_add.setStyleSheet(_BTN_ACT)
        btn_del = QPushButton('Excluir permanentemente')
        btn_del.setStyleSheet(_BTN_ACT)
        btn_fechar = QPushButton('Fechar')
        btn_fechar.setStyleSheet(_BTN_ACT)

        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)

        def add_user():
            dlg_add = QDialog(dlg)
            dlg_add.setWindowTitle('Novo usuário')
            dlg_add.setMinimumWidth(350)
            lay_add = QGridLayout(dlg_add)
            lay_add.addWidget(QLabel('Usuário:'), 0, 0)
            edit_user = QLineEdit()
            lay_add.addWidget(edit_user, 0, 1)
            lay_add.addWidget(QLabel('Nome completo:'), 1, 0)
            edit_nome = QLineEdit()
            lay_add.addWidget(edit_nome, 1, 1)
            lay_add.addWidget(QLabel('Senha:'), 2, 0)
            edit_pass = QLineEdit(); edit_pass.setEchoMode(QLineEdit.Password)
            lay_add.addWidget(edit_pass, 2, 1)
            lay_add.addWidget(QLabel('Bioma padrão:'), 3, 0)
            combo_bioma = QComboBox()
            combo_bioma.addItems(list(BIOMAS.keys()))
            lay_add.addWidget(combo_bioma, 3, 1)
            chk_admin = QCheckBox('Administrador')
            lay_add.addWidget(chk_admin, 4, 0, 1, 2)
            chk_auditor = QCheckBox('Auditor')
            lay_add.addWidget(chk_auditor, 5, 0, 1, 2)
            btn_save = QPushButton('Salvar')
            btn_cancel = QPushButton('Cancelar')
            lay_add.addWidget(btn_save, 6, 0)
            lay_add.addWidget(btn_cancel, 6, 1)

            def save():
                username = edit_user.text().strip()
                nome_completo = edit_nome.text().strip()
                senha = edit_pass.text().strip()
                bioma = combo_bioma.currentText()
                is_admin = chk_admin.isChecked()
                is_auditor = chk_auditor.isChecked()
                if not username or not senha:
                    QMessageBox.warning(dlg_add, 'Atenção', 'Usuário e senha são obrigatórios.')
                    return
                ok, msg = self.db.register_user(username, nome_completo, senha, bioma, is_auditor)
                if ok:
                    if is_admin:
                        self.db.set_user_admin(username, True)
                    dlg_add.accept()
                else:
                    QMessageBox.critical(dlg_add, 'Erro', msg)

            btn_save.clicked.connect(save)
            btn_cancel.clicked.connect(dlg_add.reject)
            if dlg_add.exec_() == QDialog.Accepted:
                refresh_table()

        def delete_user():
            row = tbl.currentRow()
            if row < 0:
                QMessageBox.warning(dlg, 'Atenção', 'Selecione um usuário.')
                return
            username = users[row]['username']
            if QMessageBox.question(dlg, 'Confirmar exclusão',
                f'Deseja excluir permanentemente o usuário "{username}"?\nEsta ação não pode ser desfeita.',
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                ok, msg = self.db.delete_user(username)
                if not ok:
                    QMessageBox.critical(dlg, 'Erro', msg)
                else:
                    refresh_table()

        btn_add.clicked.connect(add_user)
        btn_del.clicked.connect(delete_user)
        btn_fechar.clicked.connect(dlg.accept)
        dlg.exec_()

    # ═══════════════════════════════════════════════════════════════
    # COMBO / GRID DINÂMICOS (mantidos sem alteração)
    # ═══════════════════════════════════════════════════════════════
    def _populate_combo(self):
        self.combo.blockSignals(True)
        prev = self.combo.currentData()
        self.combo.clear()
        for code, label, color in self.classes:
            self.combo.addItem(label, userData=code)
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == prev:
                self.combo.setCurrentIndex(i)
                break
        self.combo.blockSignals(False)
        idx = self.combo.currentIndex()
        if 0 <= idx < len(self.classes):
            self.cls_color_bar.setStyleSheet(f'background:{self.classes[idx][2]}; border-radius:2px;')

    def _rebuild_counters_grid(self):
        while self.cnt_grid_layout.count():
            item = self.cnt_grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.count_labels = {}
        for row_i, (code, label, color) in enumerate(self.classes):
            dot = QLabel('●'); dot.setFixedWidth(14); dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
            name = QLabel(label); name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
            num = QLabel(str(self.counts.get(code, 0))); num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
            self.cnt_grid_layout.addWidget(dot,  row_i, 0)
            self.cnt_grid_layout.addWidget(name, row_i, 1)
            self.cnt_grid_layout.addWidget(num,  row_i, 2)
            self.count_labels[code] = num
        total_label = QLabel('Total')
        total_label.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT};')
        total_num = QLabel(str(self.total))
        total_num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
        self.cnt_grid_layout.addWidget(total_label, len(self.classes), 1)
        self.cnt_grid_layout.addWidget(total_num,  len(self.classes), 2)
        self.total_label_widget = total_num

    def _update_counters(self):
        self.lbl_total.setText(str(self.total))
        for code, lbl in self.count_labels.items():
            n = self.counts.get(code, 0)
            lbl.setText(str(n))
            lbl.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT if n > 0 else C_MUTED}; min-width:22px;')
        if hasattr(self, 'total_label_widget') and not sip.isdeleted(self.total_label_widget):
            self.total_label_widget.setText(str(self.total))
        slices = [(label, self.counts.get(code, 0), color) for code, label, color in self.classes if self.counts.get(code, 0) > 0]
        self.pie_widget.set_data(slices)

    def _refresh_filtros(self):
        """Populate tile and ecoregion combos from the sample layer (GeoPackage) or DB."""
        if self._is_local_geopackage:
            self.combo_tile.blockSignals(True)
            self.combo_eco.blockSignals(True)
            self.combo_tile.clear()
            self.combo_eco.clear()
            self.combo_tile.addItem('Todos')
            self.combo_eco.addItem('Todas', None)
            if self._layer_ok(self.layer):
                tiles = set()
                ecos = set()
                for feat in self.layer.getFeatures():
                    tile = feat['tile']
                    if tile is not None:
                        tiles.add(str(tile))
                    eco = feat['ecoregion']
                    if eco is not None:
                        ecos.add(str(eco))
                for t in sorted(tiles):
                    self.combo_tile.addItem(t)
                for e in sorted(ecos):
                    self.combo_eco.addItem(e, userData=e)
            self.combo_tile.blockSignals(False)
            self.combo_eco.blockSignals(False)
            self._update_filtered_count()
            return
        
        if not self.user_info or self.user_info['username'] == 'local': 
            return
        tiles, ecos_sanitized = self.db.get_tiles_ecorregioes(self.biome, self.project_type, self.user_info['username'])
        self.combo_tile.blockSignals(True)
        self.combo_tile.clear()
        self.combo_tile.addItem('Todos')
        self.combo_tile.addItems(tiles)
        self.combo_eco.clear()
        self.combo_eco.addItem('Todas', None)
        eco_map = self.db.get_ecoregion_display_map(self.biome, self.project_type)
        for eco_s in ecos_sanitized:
            display = eco_map.get(eco_s, eco_s)
            self.combo_eco.addItem(display, userData=eco_s)
        self.combo_tile.blockSignals(False)
        self.combo_eco.blockSignals(False)
        self._update_filtered_count()

    def _update_filtered_count(self):
        if not self._layer_ok(self.layer):
            return
        
        tile = self.combo_tile.currentText() if self.combo_tile.count() > 0 else 'Todos'
        eco = self.combo_eco.currentData() if self.combo_eco.count() > 0 else None
        
        if self._is_local_geopackage:
            layer = self.layer
            label_idx = layer.fields().indexOf('label')
            if label_idx == -1:
                self._log("Campo 'label' não encontrado.")
                return
            
            filters = []
            if tile != 'Todos':
                filters.append(f"tile = '{tile}'")
            if eco is not None:
                filters.append(f"ecoregion = '{eco}'")
            
            if filters:
                expr = QgsExpression(' AND '.join(filters))
                request = QgsFeatReq(expr)
            else:
                request = QgsFeatReq()
            
            counts = {code: 0 for code, _, _ in self.classes}
            total_f = 0
            for feat in layer.getFeatures(request):
                code = feat['label'] if label_idx >= 0 else ''
                if code in counts:
                    counts[code] += 1
                    total_f += 1
            
            while self.cnt_grid_layout.count():
                item = self.cnt_grid_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            self.count_labels = {}
            color_map = {code: color for code, _, color in self.classes}
            row_i = 0
            for code, n in counts.items():
                if n == 0:
                    continue
                display_name = code
                for c, label, _ in self.classes:
                    if c == code:
                        display_name = label
                        break
                color = color_map.get(code, '#888888')
                dot = QLabel('●'); dot.setFixedWidth(14); dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
                name = QLabel(display_name); name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
                num = QLabel(str(n)); num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
                self.cnt_grid_layout.addWidget(dot,  row_i, 0)
                self.cnt_grid_layout.addWidget(name, row_i, 1)
                self.cnt_grid_layout.addWidget(num,  row_i, 2)
                row_i += 1
            total_label = QLabel('Total')
            total_label.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT};')
            total_num = QLabel(str(total_f))
            total_num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
            self.cnt_grid_layout.addWidget(total_label, row_i, 1)
            self.cnt_grid_layout.addWidget(total_num,  row_i, 2)
            self.lbl_filtro_total.setText(f'Filtrado: {total_f}')
            
            if (tile != 'Todos' or eco is not None) and total_f > 0:
                slices = [(display_name, n, color_map.get(code, '#888888')) for code, n in counts.items() if n > 0]
                self.pie_widget.set_data(slices)
            else:
                slices = [(label, self.counts.get(code, 0), color) for code, label, color in self.classes if self.counts.get(code, 0) > 0]
                self.pie_widget.set_data(slices)
        else:
            if not self.user_info or self.user_info['username'] == 'local': 
                return
            rows = self.db.get_contagem(self.biome, self.project_type, self.user_info['username'],
                                        tile=tile if tile != 'Todos' else None,
                                        ecoregion=eco)
            while self.cnt_grid_layout.count():
                item = self.cnt_grid_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            self.count_labels = {}
            color_map = {code: color for code, _, color in self.classes}
            total_f   = 0
            for i, (cls_code, n) in enumerate(rows):
                display_name = cls_code
                for code, label, _ in self.classes:
                    if code == cls_code:
                        display_name = label
                        break
                color = color_map.get(cls_code, '#888888')
                dot = QLabel('●'); dot.setFixedWidth(14); dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
                name = QLabel(display_name); name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
                num = QLabel(str(n)); num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
                self.cnt_grid_layout.addWidget(dot,  i, 0)
                self.cnt_grid_layout.addWidget(name, i, 1)
                self.cnt_grid_layout.addWidget(num,  i, 2)
                total_f += n
            total_label = QLabel('Total')
            total_label.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT};')
            total_num = QLabel(str(total_f))
            total_num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
            self.cnt_grid_layout.addWidget(total_label, len(rows), 1)
            self.cnt_grid_layout.addWidget(total_num,  len(rows), 2)
            self.lbl_filtro_total.setText(f'Filtrado: {total_f}')
            is_filtered = (tile != 'Todos' or eco is not None)
            if is_filtered and rows:
                self.pie_widget.set_data([(display_name, n, color_map.get(cls_code, '#888888')) for cls_code, n in rows if n > 0])
            else:
                slices = [(label, self.counts.get(code, 0), color) for code, label, color in self.classes if self.counts.get(code, 0) > 0]
                self.pie_widget.set_data(slices)

    def _open_class_manager(self):
        if not self.user_info or self._is_local_geopackage: return
        username = self.user_info['username']
        dlg = ClassManagerDialog(self.classes, db=self.db, bioma=self.biome, username=username, parent=self)
        if dlg.exec_() != QDialog.Accepted: return
        new = dlg.get_classes()
        if not new: return
        self.classes = list(new)
        existing = {c[0] for c in self.classes}
        for code in list(self.counts.keys()):
            if code not in existing: del self.counts[code]
        for code, _, _ in self.classes:
            if code not in self.counts: self.counts[code] = 0
        self._populate_combo()
        self._rebuild_counters_grid()
        self._update_counters()
        if self._layer_ok(self.layer):
            self._apply_style()
            self.canvas.refresh()
        self._log(f'Classes atualizadas ({len(self.classes)}).')

    def _new_memory_layer(self):
        crs = self.canvas.mapSettings().destinationCrs()
        self.layer = QgsVectorLayer(f'Polygon?crs={crs.authid()}', 'Amostras (local)', 'memory')
        pr = self.layer.dataProvider()
        pr.addAttributes([
            QgsField('fid',         QVariant.Int,    'int',    10),
            QgsField('label',       QVariant.String, 'string', 150),
            QgsField('analyst',     QVariant.String, 'string', 100),
            QgsField('biome',       QVariant.String, 'string', 50),
            QgsField('date',        QVariant.Date,   'date',   0),
            QgsField('prodes',      QVariant.String, 'string', 10),
            QgsField('area_m2',     QVariant.Double, 'double', 14, 2),
            QgsField('px_size',     QVariant.Int,    'int',    5),
            QgsField('window_px',   QVariant.Int,    'int',    5),
        ])
        self.layer.updateFields()
        idx = self.layer.fields().indexOf('date')
        if idx >= 0:
            setup = QgsEditorWidgetSetup('DateTime', {'display_format':'yyyy:MM:dd','calendar_popup':False,'field_format':'yyyy:MM:dd'})
            self.layer.setEditorWidgetSetup(idx, setup)
        self._apply_style()
        QgsProject.instance().addMapLayer(self.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        self.layer_id  = self.layer.id()
        self.total     = 0
        self.counts    = {c[0]: 0 for c in self.classes}
        self._next_fid = 1
        self._update_counters()

    def _apply_style(self):
        if not self._layer_ok(self.layer) or not self.classes: return
        cats = []
        for code, label, color in self.classes:
            r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            sym = QgsFillSymbol.createSimple({'color':f'{r},{g},{b},255','outline_color':'50,50,50,200','outline_width':'0.4','style':'solid'})
            cats.append(QgsRendererCategory(code, sym, label))
        self.layer.setRenderer(QgsCategorizedSymbolRenderer('label', cats))
        self.layer.triggerRepaint()

    def window_size_m(self): return self.pixel_size * PIXEL_SIZE_M
    def _on_spin(self, val):
        self.pixel_size = val
        self.lbl_m.setText(f'= {val * PIXEL_SIZE_M:.0f} × {val * PIXEL_SIZE_M:.0f} m')
    def _on_class_changed(self, idx):
        if 0 <= idx < len(self.classes):
            self.cls_color_bar.setStyleSheet(f'background:{self.classes[idx][2]}; border-radius:2px;')
    def _log(self, msg):
        try:
            if not sip.isdeleted(self.log):
                self.log.append(msg)
                self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        except RuntimeError:
            pass
    def _get_layer(self):
        if not self.layer_id: return None
        layer = QgsProject.instance().mapLayer(self.layer_id)
        if not layer or sip.isdeleted(layer):
            self.layer = None; self.layer_id = None; return None
        self.layer = layer; return layer
    def _auto_refresh(self):
        if not self._is_local_geopackage:
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
    def _manual_refresh(self):
        self._auto_refresh()
        self._refresh_filtros()
        self._log('Mapa atualizado.')

    # ═══════════════════════════════════════════════════════════════
    # INTERSECÇÃO LOCAL
    # ═══════════════════════════════════════════════════════════════
    def _local_intersect(self, geom):
        tile = None
        ecoregion = None
        if self._layer_ok(self.tile_layer):
            for feat in self.tile_layer.getFeatures():
                if feat.geometry().intersects(geom):
                    tile = feat['tile']
                    break
        if self._layer_ok(self.subregion_layer):
            for feat in self.subregion_layer.getFeatures():
                if feat.geometry().intersects(geom):
                    raw = feat['eco']
                    if raw:
                        ecoregion = sanitize_text(raw)
                    break
        return tile, ecoregion

    # ═══════════════════════════════════════════════════════════════
    # SALVAR AMOSTRA
    # ═══════════════════════════════════════════════════════════════
    def save_sample(self, geom):
        if not self.user_info:
            self._log('Faça login primeiro.')
            return False
        code     = self.combo.currentData()
        cls_name = self.combo.currentText()
        if not code: return False
        username = self.user_info['username']
        px   = self.pixel_size
        if self.get_draw_mode() == 'square':
            area = (px * PIXEL_SIZE_M) ** 2
        else:
            geom_copy = QgsGeometry(geom)
            src_crs = self.canvas.mapSettings().destinationCrs()
            if not src_crs.isValid():
                src_crs = QgsCoordinateReferenceSystem('EPSG:4674')
            dest_crs = QgsCoordinateReferenceSystem('EPSG:5880')
            if src_crs != dest_crs:
                tr = QgsCoordinateTransform(src_crs, dest_crs, QgsProject.instance())
                geom_copy.transform(tr)
            area = geom_copy.area()
            if area <= 0:
                self._log('Área do polígono inválida (zero ou negativa).')
                return False

        year = datetime.now().year
        prodes_str = f"{year-1}-{year}"
        auditor_name = username if self.is_auditor else None

        if not self._is_local_geopackage and username != 'local' and self.biome:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            srid = canvas_crs.postgisSrid()
            if not srid or srid == 0:
                auth = canvas_crs.authid()
                if ':' in auth:
                    try: srid = int(auth.split(':')[1])
                    except ValueError: srid = 4674
            fid, err = self.db.insert_feature(
                self.biome, self.project_type, username, geom.asWkt(), srid,
                code, area, int(PIXEL_SIZE_M), px, prodes_str,
                audit=auditor_name, label_audit=None
            )
            if fid is None:
                self._log(f'Erro ao salvar: {err}')
                return False
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
            self._undo_stack.append({
                'fid': fid, 'code': code, 'cls_name': cls_name,
                'geom_wkt': geom.asWkt(), 'srid': srid,
                'area': area, 'px': px
            })
            self._redo_stack.clear()
        else:
            layer = self._get_layer() if self._is_local_geopackage else None
            if not self._layer_ok(layer):
                self._new_memory_layer()
                layer = self.layer
            fn = [f.name() for f in layer.fields()]
            feat = QgsFeature(layer.fields())
            feat.setGeometry(geom)
            a = {}
            today = QDate.currentDate()
            if not self._is_local_geopackage:
                if 'fid' in fn: a['fid'] = self._next_fid
            if self._is_local_geopackage:
                tile, eco = self._local_intersect(geom)
                if 'tile'      in fn and tile:  a['tile']      = tile
                if 'ecoregion' in fn and eco:   a['ecoregion'] = eco
            if 'label'       in fn: a['label']       = code
            if 'analyst'     in fn: a['analyst']     = username
            if 'biome'       in fn: a['biome']       = sanitize_text(self.biome) if self.biome else ''
            if 'date'        in fn: a['date']        = today
            if 'prodes'      in fn: a['prodes']      = prodes_str
            if 'area_m2'     in fn: a['area_m2']     = area
            if 'px_size'     in fn: a['px_size']     = int(PIXEL_SIZE_M)
            if 'window_px'   in fn: a['window_px']   = px
            if 'audit'       in fn and auditor_name:
                a['audit'] = auditor_name
            for k, v in a.items():
                feat.setAttribute(k, v)
            ok, added = layer.dataProvider().addFeatures([feat])
            if not ok:
                self._log('Erro ao salvar (local).')
                return False
            fid_saved = added[0].id() if added else self._next_fid
            self._undo_stack.append({
                'provider_fid': fid_saved, 'code': code, 'cls_name': cls_name,
                'geom_wkt': geom.asWkt(), 'srid': None,
                'area': area, 'px': px
            })
            self._redo_stack.clear()
            layer.updateExtents()
            self.canvas.refresh()
            if not self._is_local_geopackage:
                self._next_fid += 1

        self.total += 1
        self.counts[code] = self.counts.get(code, 0) + 1
        self._update_counters()
        if not self._is_local_geopackage:
            self._refresh_filtros()
        if self._is_local_geopackage:
            self._refresh_filtros()
        self._log(f'#{self.total}  {cls_name}')
        return True

    # ═══════════════════════════════════════════════════════════════
    # DESFAZER / REFAZER
    # ═══════════════════════════════════════════════════════════════
    def _undo(self):
        if not self._undo_stack:
            self._log('Nada para desfazer.')
            return
        entry    = self._undo_stack.pop()
        username = self.user_info['username'] if self.user_info else 'local'
        is_admin = getattr(self, 'is_admin', False) and not self._is_local_geopackage
        if not self._is_local_geopackage and username != 'local' and self.biome and 'fid' in entry:
            ok, err = self.db.delete_feature(self.biome, self.project_type, entry['fid'], username, is_admin)
            if not ok:
                self._log(f'Erro: {err}')
                self._undo_stack.append(entry)
                return
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
        else:
            layer = self._get_layer()
            if self._layer_ok(layer) and 'provider_fid' in entry:
                layer.dataProvider().deleteFeatures([entry['provider_fid']])
                layer.updateExtents()
                self.canvas.refresh()
        self._redo_stack.append(entry)
        self.total     = max(0, self.total - 1)
        if not self._is_local_geopackage:
            self._next_fid = max(1, self._next_fid - 1)
        code = entry.get('code')
        if code and code in self.counts:
            self.counts[code] = max(0, self.counts[code] - 1)
        self._update_counters()
        if not self._is_local_geopackage:
            self._refresh_filtros()
        if self._is_local_geopackage:
            self._refresh_filtros()
        self._log(f'↩ {entry["cls_name"]}')

    def _redo(self):
        if not self._redo_stack:
            self._log('Nada para refazer.')
            return
        entry    = self._redo_stack.pop()
        username = self.user_info['username'] if self.user_info else 'local'
        is_admin = getattr(self, 'is_admin', False) and not self._is_local_geopackage
        if not self._is_local_geopackage and username != 'local' and self.biome:
            prodes_str = f"{datetime.now().year-1}-{datetime.now().year}"
            fid, err = self.db.insert_feature(
                self.biome, self.project_type, username,
                entry['geom_wkt'], entry.get('srid', 4326),
                entry['code'], entry['area'], int(PIXEL_SIZE_M), entry['px'],
                prodes_str, audit=None, label_audit=None
            )
            if fid is None:
                self._log(f'Erro: {err}')
                self._redo_stack.append(entry)
                return
            entry['fid'] = fid
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
        else:
            from qgis.core import QgsGeometry as QG
            layer = self._get_layer()
            if self._layer_ok(layer):
                feat = QgsFeature(layer.fields())
                feat.setGeometry(QG.fromWkt(entry['geom_wkt']))
                a = {}
                if self._is_local_geopackage:
                    tile, eco = self._local_intersect(QG.fromWkt(entry['geom_wkt']))
                    if 'tile'      in [f.name() for f in layer.fields()]: a['tile']      = tile
                    if 'ecoregion' in [f.name() for f in layer.fields()]: a['ecoregion'] = eco
                if 'label' in [f.name() for f in layer.fields()]:
                    a['label'] = entry['code']
                if 'analyst' in [f.name() for f in layer.fields()]:
                    a['analyst'] = username
                if 'biome' in [f.name() for f in layer.fields()]:
                    a['biome'] = sanitize_text(self.biome) if self.biome else ''
                for k, v in a.items():
                    feat.setAttribute(k, v)
                ok, added = layer.dataProvider().addFeatures([feat])
                if added:
                    entry['provider_fid'] = added[0].id()
                layer.updateExtents()
                self.canvas.refresh()
        self._undo_stack.append(entry)
        self.total += 1
        if not self._is_local_geopackage:
            self._next_fid += 1
        code = entry.get('code')
        if code:
            self.counts[code] = self.counts.get(code, 0) + 1
        self._update_counters()
        if not self._is_local_geopackage:
            self._refresh_filtros()
        if self._is_local_geopackage:
            self._refresh_filtros()
        self._log(f'↪ {entry["cls_name"]}')

    # ═══════════════════════════════════════════════════════════════
    # RELATÓRIO (inalterado)
    # ═══════════════════════════════════════════════════════════════
    def _gerar_relatorio(self):
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
        )
        from qgis.PyQt.QtGui import QColor, QPixmap, QPainter
        from qgis.PyQt.QtCore import Qt
        if not self.user_info: return
        tile = self.combo_tile.currentText()
        eco_sanitized = self.combo_eco.currentData()
        eco_display   = self.combo_eco.currentText()
        if self._is_local_geopackage or self.user_info.get('username') == 'local':
            rows = [(code, self.counts.get(code, 0)) for code, _, _ in self.classes if self.counts.get(code, 0) > 0]
        else:
            rows = self.db.get_contagem(self.biome, self.project_type, username=None,
                                        tile=tile if tile != 'Todos' else None,
                                        ecoregion=eco_sanitized,
                                        all_interpreters=True)
        if not rows:
            QMessageBox.information(self, 'Relatório', 'Nenhuma amostra no filtro atual.')
            return
        total = sum(n for _, n in rows)
        color_map = {code: color for code, _, color in self.classes}
        dlg = QDialog(self)
        dlg.setWindowTitle('Relatório amostral')
        dlg.setMinimumWidth(500); dlg.setMinimumHeight(500)
        dlg.setStyleSheet(f"""
            QDialog, QWidget {{ background:{C_BG}; font-family:'Segoe UI',sans-serif; color:{C_TEXT}; }}
            QTableWidget {{ border:1px solid {C_BORDER}; border-radius:6px; font-size:8.5pt; background:{C_SURFACE}; gridline-color:{C_BORDER}; }}
            QHeaderView::section {{ background:{C_BG}; font-weight:700; font-size:8pt; padding:5px 8px; border:none; border-bottom:1.5px solid {C_BORDER}; }}
            QTableWidget::item {{ padding:5px 8px; }}
            QTableWidget::item:alternate {{ background:#F5F7FA; }}
            QLabel {{ background:transparent; color:{C_TEXT}; }}
        """)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(24, 24, 24, 20); lay.setSpacing(10)
        titulo = QLabel('Relatório amostral')
        titulo.setStyleSheet(f'font-size:14pt; font-weight:700; color:{C_TEXT};')
        lay.addWidget(titulo)
        subtitulo = QLabel(f'Bioma: {self.biome or "—"}  ·  Tile: {tile}  ·  Ecorregião: {eco_display}')
        subtitulo.setStyleSheet(f'font-size:9pt; color:{C_TEXT};')
        lay.addWidget(subtitulo)
        total_label = QLabel(f'Total de amostras: {total}')
        total_label.setStyleSheet(f'font-size:12pt; font-weight:700;')
        lay.addWidget(total_label)
        pie = PieChartWidget(); pie.setFixedHeight(180)
        pie.set_data([(self._code_to_label(code), n, color_map.get(code, '#888888')) for code, n in rows if n > 0])
        lay.addWidget(pie)
        tbl = QTableWidget(len(rows), 3)
        tbl.setHorizontalHeaderLabels(['Classe', 'Amostras', '%'])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tbl.verticalHeader().setVisible(False)
        tbl.verticalHeader().setDefaultSectionSize(30)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.setSelectionMode(QTableWidget.NoSelection)
        for i, (code, n) in enumerate(rows):
            pct = f'{n / total * 100:.1f}%'
            cor = color_map.get(code, '#888888')
            px = QPixmap(14, 14); px.fill(QColor(cor))
            pp = QPainter(px); pp.setPen(QColor('#00000033')); pp.drawRect(0, 0, 13, 13); pp.end()
            display = self._code_to_label(code)
            item_cls = QTableWidgetItem(QIcon(px), display)
            item_cls.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_n   = QTableWidgetItem(str(n)); item_n.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            item_pct = QTableWidgetItem(pct); item_pct.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            tbl.setItem(i, 0, item_cls); tbl.setItem(i, 1, item_n); tbl.setItem(i, 2, item_pct)
        lay.addWidget(tbl)
        btn_row = QHBoxLayout()
        btn_pdf = QPushButton('⬇  Exportar PDF'); btn_pdf.setStyleSheet(_BTN_ACT)
        btn_pdf.clicked.connect(lambda: self._exportar_pdf(dlg, tile, eco_display, eco_sanitized, rows, total))
        btn_fechar = QPushButton('Fechar'); btn_fechar.setStyleSheet(_BTN_ACT)
        btn_fechar.clicked.connect(dlg.close)
        btn_row.addWidget(btn_pdf); btn_row.addStretch(); btn_row.addWidget(btn_fechar)
        lay.addLayout(btn_row)
        dlg.exec_()

    def _code_to_label(self, code):
        for c, label, _ in self.classes:
            if c == code:
                return label
        return code

    def _exportar_pdf(self, parent, tile, eco_display, eco_sanitized, rows, total):
        from qgis.PyQt.QtPrintSupport import QPrinter
        from qgis.PyQt.QtGui import QPainter, QFont, QColor, QBrush, QPen
        from qgis.PyQt.QtCore import QRectF, Qt
        path, _ = QFileDialog.getSaveFileName(parent, 'Salvar PDF', 'relatorio_amostral', 'PDF (*.pdf)')
        if not path: return
        if not path.endswith('.pdf'): path += '.pdf'
        printer = QPrinter(QPrinter.HighResolution); printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path); printer.setPageSize(QPrinter.A4)
        p = QPainter(printer); p.setRenderHint(QPainter.Antialiasing)
        dpi = printer.resolution(); W = printer.pageRect().width(); M = int(dpi * 0.7); y = M
        def pt(inches): return int(dpi * inches)
        def txt(text, yy, size=10, bold=False, color='#2D3142', x=None, w=None, align=Qt.AlignLeft | Qt.AlignVCenter):
            nonlocal y
            f = QFont('Arial', size); f.setBold(bold); p.setFont(f); p.setPen(QColor(color))
            rx = x if x is not None else M; rw = w if w is not None else W - M * 2; rh = pt(0.35)
            p.drawText(QRectF(rx, yy, rw, rh), align, text)
            return yy + rh + pt(0.05)
        y = txt('Relatório amostral', y, size=14, bold=True)
        y = txt(f'Bioma: {self.biome or "—"}  ·  Tile: {tile}  ·  Ecorregião: {eco_display}', y, size=9)
        y = txt(f'Total de amostras: {total}', y, size=12, bold=True); y += pt(0.15)
        pie_size = pt(2.2)
        pie_rect = QRectF(M, y, pie_size, pie_size)
        color_map = {code: color for code, _, color in self.classes}
        total_v = sum(n for _, n in rows); angle = 90 * 16
        for code, n in rows:
            span = int(round(n / total_v * 360 * 16))
            cor = color_map.get(code, '#888888')
            p.setBrush(QBrush(QColor(cor))); p.setPen(QPen(QColor('#FFFFFF'), 3))
            p.drawPie(pie_rect, angle, -span); angle -= span
        lx = M + pie_size + pt(0.3); ly = y + pt(0.1); p.setFont(QFont('Arial', 9))
        for code, n in rows:
            cor = color_map.get(code, '#888888'); p.setBrush(QBrush(QColor(cor))); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(lx, ly, pt(0.15), pt(0.15)), 3, 3)
            p.setPen(QColor('#2D3142')); pct = f'{n / total_v * 100:.1f}%'
            display = self._code_to_label(code)
            p.drawText(QRectF(lx + pt(0.2), ly - pt(0.02), W - lx - M - pt(0.2), pt(0.22)),
                       Qt.AlignLeft | Qt.AlignVCenter, f'{display}  —  {n} ({pct})')
            ly += pt(0.26)
        y += pie_size + pt(0.4)
        col_w = [(W - M * 2) * 0.6, (W - M * 2) * 0.2, (W - M * 2) * 0.2]; row_h = pt(0.28); hdr_h = pt(0.32)
        p.setBrush(QBrush(QColor('#F0F4F8'))); p.setPen(Qt.NoPen); p.drawRect(QRectF(M, y, W - M * 2, hdr_h))
        p.setPen(QColor('#2D3142')); p.setFont(QFont('Arial', 9, QFont.Bold))
        for j, (htext, cw, cx) in enumerate(zip(['Classe', 'Amostras', '%'], col_w, [M, M + col_w[0], M + col_w[0] + col_w[1]])):
            align = Qt.AlignCenter if j > 0 else Qt.AlignLeft | Qt.AlignVCenter
            p.drawText(QRectF(cx + 4, y, cw - 4, hdr_h), align, htext)
        y += hdr_h
        p.setFont(QFont('Arial', 9))
        for i, (code, n) in enumerate(rows):
            bg = QColor('#FFFFFF') if i % 2 == 0 else QColor('#F8FAFC'); p.setBrush(QBrush(bg)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(M, y, W - M * 2, row_h))
            cor = color_map.get(code, '#888888'); p.setBrush(QBrush(QColor(cor)))
            p.drawRoundedRect(QRectF(M + 4, y + row_h / 2 - pt(0.07), pt(0.12), pt(0.12)), 2, 2)
            pct = f'{n / total * 100:.1f}%'; p.setPen(QColor('#2D3142'))
            display = self._code_to_label(code)
            cx0 = M + pt(0.18)
            p.drawText(QRectF(cx0, y, col_w[0] - pt(0.18), row_h), Qt.AlignLeft | Qt.AlignVCenter, display)
            p.drawText(QRectF(M + col_w[0], y, col_w[1], row_h), Qt.AlignCenter, str(n))
            p.drawText(QRectF(M + col_w[0] + col_w[1], y, col_w[2], row_h), Qt.AlignCenter, pct)
            p.setPen(QPen(QColor(C_BORDER), 1))
            p.drawLine(QRectF(M, y + row_h, W - M * 2, 0).topLeft(), QRectF(M, y + row_h, W - M * 2, 0).topRight())
            y += row_h
        p.end()
        QMessageBox.information(parent, 'Sample Design', f'PDF salvo!\n{path}')

    def _sep(self, layout=None, top=4, bottom=4):
        w = QWidget(); wl = QVBoxLayout(w); wl.setContentsMargins(0, top, 0, bottom)
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        wl.addWidget(line)
        if layout is not None: layout.addWidget(w)
        return w

    def _small(self, text):
        l = QLabel(text); l.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;'); return l

    def _export(self):
        layer = self._get_layer()
        if not self._layer_ok(layer) or layer.featureCount() == 0:
            QMessageBox.warning(self, 'Sample Design', 'Nenhuma amostra para exportar.')
            return
        path, filt = QFileDialog.getSaveFileName(self, 'Exportar', 'amostras', 'GeoPackage (*.gpkg);;Shapefile (*.shp)')
        if not path: return
        driver = 'GPKG' if 'gpkg' in filt.lower() or path.endswith('.gpkg') else 'ESRI Shapefile'
        if driver == 'GPKG' and not path.endswith('.gpkg'): path += '.gpkg'
        elif driver == 'ESRI Shapefile' and not path.endswith('.shp'): path += '.shp'
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = driver; opts.fileEncoding = 'UTF-8'
        err, msg = QgsVectorFileWriter.writeAsVectorFormatV2(layer, path, QgsCoordinateTransformContext(), opts)
        if err == QgsVectorFileWriter.NoError:
            self._log(f'Exportado: {os.path.basename(path)}')
            QMessageBox.information(self, 'Sample Design', f'Exportado!\n{path}')
        else:
            self._log(f'Erro: {msg}')
            QMessageBox.critical(self, 'Sample Design', f'Erro:\n{msg}')

    # ═══════════════════════════════════════════════════════════════
    # EXPORTAR PARA WFS (inalterado)
    # ═══════════════════════════════════════════════════════════════
    def _export_to_wfs(self):
        if not self._is_local_geopackage:
            QMessageBox.warning(self, 'WFS', 'Esta função só está disponível no modo GeoPackage.')
            return

        layers = [l for l in QgsProject.instance().mapLayers().values() if l.type() == QgsMapLayer.VectorLayer]
        if not layers:
            QMessageBox.critical(self, 'WFS', 'Nenhuma camada vetorial carregada.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle('Exportar para WFS')
        dlg.setMinimumWidth(450)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel('Camada WFS de destino:'))
        wfs_row = QHBoxLayout()
        self.wfs_combo = QComboBox()
        for l in layers:
            self.wfs_combo.addItem(l.name(), l.id())
        wfs_row.addWidget(self.wfs_combo)
        btn_browse_wfs = QPushButton('Procurar...')
        btn_browse_wfs.clicked.connect(self._browse_wfs_file)
        wfs_row.addWidget(btn_browse_wfs)
        layout.addLayout(wfs_row)

        layout.addWidget(QLabel('Camada de entrada (entrada_amostras):'))
        entry_row = QHBoxLayout()
        self.entry_combo = QComboBox()
        for l in layers:
            self.entry_combo.addItem(l.name(), l.id())
        if self._layer_ok(self.layer) and self.layer.id() in [l.id() for l in layers]:
            self.entry_combo.setCurrentIndex(self.entry_combo.findData(self.layer.id()))
        entry_row.addWidget(self.entry_combo)
        btn_browse_entry = QPushButton('Procurar...')
        btn_browse_entry.clicked.connect(self._browse_entry_file)
        entry_row.addWidget(btn_browse_entry)
        layout.addLayout(entry_row)

        layout.addWidget(QLabel('Tile:'))
        edit_tile = QLineEdit()
        layout.addWidget(edit_tile)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton('Executar')
        btn_cancel = QPushButton('Cancelar')
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        def run_export():
            wfs_layer = None
            entry_layer = None

            wfs_id = self.wfs_combo.currentData()
            if wfs_id:
                wfs_layer = QgsProject.instance().mapLayer(wfs_id)
            if not self._layer_ok(wfs_layer):
                QMessageBox.critical(dlg, 'Erro', 'Selecione uma camada WFS válida.')
                return

            entry_id = self.entry_combo.currentData()
            if entry_id:
                entry_layer = QgsProject.instance().mapLayer(entry_id)
            if not self._layer_ok(entry_layer):
                QMessageBox.critical(dlg, 'Erro', 'Selecione uma camada de entrada válida.')
                return

            tile = edit_tile.text().strip()
            if not tile:
                QMessageBox.critical(dlg, 'Erro', 'Informe o tile.')
                return

            dlg.accept()

            feedback = QgsProcessingMultiStepFeedback(4, feedback=QgsProcessingFeedback())
            fix_result = processing.run('native:fixgeometries', {'INPUT': wfs_layer, 'METHOD': 1, 'OUTPUT': 'memory:'})
            wfs_fixed = fix_result['OUTPUT']

            extract_result = processing.run('native:extractbyattribute', {'FIELD': 'tile', 'INPUT': entry_layer, 'OPERATOR': 0, 'VALUE': tile, 'OUTPUT': 'memory:'})
            entry_tile = extract_result['OUTPUT']

            diff_result = processing.run('native:difference', {'INPUT': entry_tile, 'OVERLAY': wfs_fixed, 'OUTPUT': 'memory:'})
            diff_layer = diff_result['OUTPUT']

            source_crs = entry_layer.crs()
            target_crs = wfs_layer.crs()
            tr = None
            if source_crs.isValid() and target_crs.isValid() and source_crs != target_crs:
                tr = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())

            wfs_provider = wfs_layer.dataProvider()
            wfs_fields = wfs_layer.fields()

            geom_field_name = None
            for i in range(wfs_fields.count()):
                fn = wfs_fields.field(i)
                if geom_field_name is None:
                    if fn.name() in ('geom', 'geometry', 'the_geom', 'GEOMETRY'):
                        geom_field_name = fn.name()
                    elif 'geom' in fn.typeName().lower():
                        geom_field_name = fn.name()
            if geom_field_name is None:
                geom_field_name = 'geom'

            features = []
            for feat in diff_layer.getFeatures():
                new_feat = QgsFeature(wfs_fields)
                geom = QgsGeometry(feat.geometry())
                if tr is not None:
                    try:
                        geom.transform(tr)
                    except Exception:
                        pass
                new_feat.setGeometry(geom)
                for i, field in enumerate(wfs_fields):
                    if field.name() == geom_field_name:
                        continue
                    idx = diff_layer.fields().indexOf(field.name())
                    if idx >= 0:
                        new_feat.setAttribute(field.name(), feat.attribute(field.name()))
                for i, field in enumerate(wfs_fields):
                    if field.name() == geom_field_name:
                        new_feat.setAttribute(i, None)
                features.append(new_feat)

            if not features:
                QMessageBox.information(self, 'WFS', 'Nenhuma feição nova para enviar.')
                return
            ok, added = wfs_provider.addFeatures(features)
            if not ok:
                QMessageBox.critical(self, 'WFS', 'Falha ao adicionar feições à camada WFS.')
                return
            wfs_layer.updateExtents()
            QMessageBox.information(self, 'WFS', f'{len(added)} feições exportadas com sucesso.')

        btn_ok.clicked.connect(run_export)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec_()

    def _browse_wfs_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Selecione o GeoPackage WFS', '', 'GeoPackage (*.gpkg)')
        if not path: return
        layer = QgsVectorLayer(path, 'wfs_target', 'ogr')
        if not layer.isValid():
            QMessageBox.critical(self, 'Erro', 'Não foi possível carregar o GeoPackage.')
            return
        QgsProject.instance().addMapLayer(layer, False)
        self.wfs_combo.addItem(layer.name(), layer.id())
        self.wfs_combo.setCurrentIndex(self.wfs_combo.count() - 1)

    def _browse_entry_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Selecione o arquivo de entrada', '', 'GeoPackage (*.gpkg)')
        if not path: return
        layer = QgsVectorLayer(path, 'entry', 'ogr')
        if not layer.isValid():
            QMessageBox.critical(self, 'Erro', 'Não foi possível carregar o GeoPackage.')
            return
        QgsProject.instance().addMapLayer(layer, False)
        self.entry_combo.addItem(layer.name(), layer.id())
        self.entry_combo.setCurrentIndex(self.entry_combo.count() - 1)

    # ═══════════════════════════════════════════════════════════════
    # SUBMETER GEOPACKAGE (admin) – COM SELEÇÃO DE DESTINO
    # ═══════════════════════════════════════════════════════════════
    def _submit_geopackage(self):
        if not self.user_info or not self.is_admin:
            return

        ok, err = self.db.test_connection()
        if not ok:
            QMessageBox.critical(self, 'Erro', f'Sem conexão com o banco: {err}')
            return

        path, _ = QFileDialog.getOpenFileName(self, 'Selecionar GeoPackage', '', 'GeoPackage (*.gpkg)')
        if not path:
            return

        entrada = self._find_layer_by_keyword(path, 'entrada_amostras')
        tiles   = self._find_layer_by_keyword(path, 'tile')
        subreg  = self._find_layer_by_keyword(path, 'subregio')

        if not entrada or not entrada.isValid():
            QMessageBox.critical(self, 'Erro', 'Camada "entrada_amostras" não encontrada.')
            return
        if not tiles or not tiles.isValid():
            QMessageBox.warning(self, 'Aviso', 'Camada de tiles não encontrada – tile ficará vazio.')
        if not subreg or not subreg.isValid():
            QMessageBox.warning(self, 'Aviso', 'Camada de subregiões não encontrada – ecoregion ficará vazio.')

        # ── Escolher camada de destino ────────────────────────
        dest_dlg = QDialog(self)
        dest_dlg.setWindowTitle('Selecionar destino')
        dest_dlg.setMinimumWidth(350)
        dest_layout = QVBoxLayout(dest_dlg)
        dest_layout.addWidget(QLabel('Bioma e projeto de destino:'))
        combo_dest = QComboBox()
        targets = list(self.db.SCHEMA_MAP.keys())
        target_names = [f"{bioma} - {proj}" for bioma, proj in targets]
        combo_dest.addItems(target_names)
        dest_layout.addWidget(combo_dest)
        btn_dest_ok = QPushButton('OK')
        btn_dest_cancel = QPushButton('Cancelar')
        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_dest_ok)
        btn_row.addWidget(btn_dest_cancel)
        dest_layout.addLayout(btn_row)

        target_biome = None
        target_proj = None

        def set_target():
            nonlocal target_biome, target_proj
            idx = combo_dest.currentIndex()
            if idx >= 0:
                target_biome, target_proj = targets[idx]
            dest_dlg.accept()

        btn_dest_ok.clicked.connect(set_target)
        btn_dest_cancel.clicked.connect(dest_dlg.reject)

        if dest_dlg.exec_() != QDialog.Accepted or not target_biome:
            return

        n_feats = entrada.featureCount()
        reply = QMessageBox.question(self, 'Confirmar',
            f'Submeter {n_feats} feições para {target_biome} - {target_proj}?\nContinuar?',
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # CRS da camada de entrada
        crs = entrada.crs()
        srid = crs.postgisSrid()
        if not srid or srid == 0:
            authid = crs.authid()
            if ':' in authid:
                try:
                    srid = int(authid.split(':')[1])
                except:
                    srid = 4674
            else:
                srid = 4674

        entrada_fields = {f.name(): i for i, f in enumerate(entrada.fields())}
        default_analyst = self.user_info['username']

        progress = QProgressDialog('Submetendo amostras…', 'Cancelar', 0, n_feats, self)
        progress.setWindowModality(Qt.WindowModal)

        success = 0
        errors = 0

        for i, feat in enumerate(entrada.getFeatures()):
            if progress.wasCanceled():
                break
            progress.setValue(i)

            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                self._log(f'Feição {i}: geometria vazia, ignorada.')
                errors += 1
                continue

            # Tile
            tile = None
            if tiles:
                for tf in tiles.getFeatures():
                    if tf.geometry().intersects(geom):
                        tile = tf['tile']
                        break

            # Ecoregion
            ecoregion = None
            if subreg:
                for sf in subreg.getFeatures():
                    if sf.geometry().intersects(geom):
                        raw = sf['eco']
                        if raw:
                            ecoregion = sanitize_text(raw)
                        break

            def get_attr(name, default=None):
                idx = entrada_fields.get(name)
                if idx is not None:
                    val = feat.attribute(idx)
                    if val is not None and str(val) != '':
                        return val
                return default

            analyst = get_attr('analyst', default_analyst)
            label   = get_attr('label', '')
            date    = get_attr('date')
            if isinstance(date, QDate):
                date = date.toPyDate()
            prodes  = get_attr('prodes', f"{datetime.now().year-1}-{datetime.now().year}")
            area_m2 = get_attr('area_m2')
            if area_m2 is None:
                try:
                    geom_copy = QgsGeometry(geom)
                    src_crs = entrada.crs()
                    dest_crs = QgsCoordinateReferenceSystem('EPSG:5880')
                    if src_crs != dest_crs:
                        tr = QgsCoordinateTransform(src_crs, dest_crs, QgsProject.instance())
                        geom_copy.transform(tr)
                    area_m2 = geom_copy.area()
                except:
                    area_m2 = 0.0
            px_size = get_attr('px_size')
            window_px = get_attr('window_px')

            fid, err = self.db.insert_feature(
                target_biome, target_proj, analyst, geom.asWkt(), srid,
                label, area_m2, px_size, window_px, prodes,
                ecoregion_raw=ecoregion, audit=None, label_audit=None,
                date_val=date
            )
            if fid is None:
                self._log(f'Erro feição {i}: {err}')
                errors += 1
            else:
                success += 1
                self._log(f'Inserida feição {i} (fid={fid})')

        progress.setValue(n_feats)
        self.lbl_upload_status.setText(f'Sucesso: {success}, Erros: {errors}')
        self._log(f'Submissão concluída: {success} inseridas, {errors} erros.')

        # Atualizar mapa se estiver na mesma combinação
        if (self.biome == target_biome and self.project_type == target_proj
                and not self._is_local_geopackage):
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
            self._sync_counts(self.user_info['username'])
            self._refresh_filtros()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)