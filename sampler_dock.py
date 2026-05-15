# -*- coding: utf-8 -*-

import os
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QTextEdit, QFrame, QFileDialog,
    QMessageBox, QSizePolicy, QScrollArea, QDialog
)
from qgis.PyQt.QtCore import Qt, QTimer, QSize
from qgis.PyQt.QtGui import QPixmap, QIcon

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature,
    QgsProject, QgsWkbTypes, QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
)
from qgis.PyQt.QtCore import QVariant

from .db_manager import DBManager
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

# Botões pastel
C_SAGE    = '#9BBFA8'   # verde-sálvia  → ação principal (salvar/exportar)
C_STEEL   = '#7EB8D4'   # azul-aço      → entrar/atualizar
C_SAND    = '#C9B99A'   # areia         → desfazer
C_SLATE   = '#A0AEC0'   # ardósia       → refazer
C_ROSE    = '#D4908A'   # rosa-terracota → sair/danger
C_LINK    = '#5B9BBF'


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


def _ghost(border, txt):
    return f"""
        QPushButton {{
            background: transparent; color: {txt};
            border: 1.5px solid {border}; border-radius: 7px;
            font-size: 8.5pt; font-weight: 600;
            padding: 0 12px; min-height: 30px;
        }}
        QPushButton:hover   {{ background: {border}18; }}
        QPushButton:pressed {{ background: {border}30; }}
        QPushButton:checked {{ background: {border}; color: #FFFFFF; }}
    """


class SamplerDock(QDockWidget):

    def __init__(self, iface, plugin):
        super().__init__('Sample Design')
        self.iface  = iface
        self.plugin = plugin
        self.canvas = iface.mapCanvas()

        self.user_info   = None
        self.bioma       = None
        self.classes     = []
        self.layer       = None
        self.layer_id    = None
        self.total       = 0
        self.counts      = {}
        self._undo_stack = []
        self._redo_stack = []
        self._next_fid   = 1
        self.pixel_size  = 10

        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        self.db = DBManager()
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))

        self._build_ui()
        QTimer.singleShot(200, self._request_login)

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

        self.user_info = dlg.user_info
        self.bioma     = dlg.bioma
        self._on_session_started()

    def _on_session_started(self):
        username = self.user_info['username']
        nome     = self.user_info.get('nome_completo', username)

        self.lbl_user.setText(nome)
        self.lbl_bioma_val.setText(self.bioma)
        self.btn_session.setText('Sair')
        self.btn_session.setStyleSheet(_pill(C_ROSE))

        self.classes = self.db.get_custom_classes(self.bioma, username)
        self.counts  = {c[0]: 0 for c in self.classes}
        self._populate_combo()
        is_admin = self.user_info.get('is_admin', False)
        self.btn_mgr.setVisible(is_admin)
        self._rebuild_counters_grid()

        layer, err = self.db.get_postgis_layer(self.bioma, username)
        if err:
            self._log(err)
            self._start_local_mode()
            return

        self.layer    = layer
        self.layer_id = layer.id()
        self._apply_style()
        QgsProject.instance().addMapLayer(self.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        self._sync_counts(username)
        self._refresh_timer.start()
        self._log(f'Sessão iniciada — {nome} · {self.bioma}')

    def _start_local_mode(self):
        self.user_info = {'username': 'local', 'nome_completo': 'Modo local'}
        self.bioma     = list(BIOMAS.keys())[0]
        self.classes   = list(CLASSES_POR_BIOMA[self.bioma])
        self.counts    = {c[0]: 0 for c in self.classes}
        self.lbl_user.setText('Sem conexão')
        self.lbl_user.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        self.lbl_bioma_val.setText(self.bioma)
        self._populate_combo()
        self._rebuild_counters_grid()
        self._new_memory_layer()
        self._log('Modo local ativo.')
        self.btn_mgr.setVisible(False)

    def _logout(self):
        self._refresh_timer.stop()
        self.user_info = None
        self.bioma     = None
        self.classes   = []
        self.layer     = None
        self.layer_id  = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.total  = 0
        self.counts = {}
        self._update_counters()
        self.lbl_user.setText('—')
        self.lbl_bioma_val.setText('—')
        self.btn_session.setText('Entrar')
        self.btn_session.setStyleSheet(_pill(C_STEEL))
        QTimer.singleShot(100, self._request_login)

    def _sync_counts(self, username):
        if not self.layer:
            return
        self.total  = 0
        self.counts = {c[0]: 0 for c in self.classes}
        for feat in self.layer.getFeatures():
            if feat['interprete'] == username:
                self.total += 1
                code = feat['label']
                if code in self.counts:
                    self.counts[code] += 1
        self._update_counters()

    def _on_session_btn(self):
        if self.user_info and self.user_info.get('username') != 'local':
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

        # ── Header: logo + título ────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        icon_path = os.path.join(self._plugin_dir, 'icons', 'sample_design_icon.png')
        if os.path.exists(icon_path):
            ico = QLabel()
            px  = QPixmap(icon_path).scaled(
                30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            ico.setPixmap(px)
            ico.setFixedSize(30, 30)
            hdr.addWidget(ico)

        t1 = QLabel('Sample Design')
        t1.setStyleSheet(
            f'font-size: 13pt; font-weight: 700; color: {C_TEXT};'
            f'letter-spacing: -0.3px;'
        )
        hdr.addWidget(t1)
        hdr.addStretch()
        lay.addLayout(hdr)

        self._sep(lay, top=6, bottom=2)

        # ── Sessão ───────────────────────────────────────────────
        grp_s = QGroupBox('Sessão')
        gs    = QVBoxLayout(grp_s)
        gs.setSpacing(5)
        grp_s.setStyleSheet(f'QGroupBox {{ background: {C_SURFACE}; border: 1px solid {C_BORDER}; border-radius: 8px; }}')

        row_u = QHBoxLayout()
        row_u.setSpacing(4)
        lbl_u_full = QLabel('Usuário:')
        lbl_u_full.setFixedWidth(55)
        lbl_u_full.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:700; background:transparent;')
        self.lbl_user = QLabel('—')
        self.lbl_user.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        row_u.addWidget(lbl_u_full)
        row_u.addWidget(self.lbl_user)
        row_u.addStretch()
        gs.addLayout(row_u)

        row_b = QHBoxLayout()
        row_b.setSpacing(4)
        lbl_b_full = QLabel('Bioma:')
        lbl_b_full.setFixedWidth(55)
        lbl_b_full.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:700; background:transparent;')
        self.lbl_bioma_val = QLabel('—')
        self.lbl_bioma_val.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        row_b.addWidget(lbl_b_full)
        row_b.addWidget(self.lbl_bioma_val)
        row_b.addStretch()
        gs.addLayout(row_b)

        self.btn_session = QPushButton('Entrar')
        self.btn_session.setMinimumHeight(30)
        self.btn_session.setStyleSheet(_pill(C_STEEL))
        self.btn_session.clicked.connect(self._on_session_btn)
        gs.addWidget(self.btn_session)
        lay.addWidget(grp_s)

        # ── Classe ───────────────────────────────────────────────
        grp_cls = QGroupBox('Classe')
        lc = QVBoxLayout(grp_cls)
        lc.setSpacing(6)

        # barra de cor criada ANTES de conectar o sinal
        self.cls_color_bar = QFrame()
        self.cls_color_bar.setFixedHeight(3)
        self.cls_color_bar.setStyleSheet('background: #C5CDD8; border-radius: 2px;')

        self.combo = QComboBox()
        self.combo.setMinimumHeight(34)
        self.combo.currentIndexChanged.connect(self._on_class_changed)
        lc.addWidget(self.combo)
        lc.addWidget(self.cls_color_bar)

        self.btn_mgr = QPushButton('Gerenciar classes')
        self.btn_mgr.setMinimumHeight(26)
        self.btn_mgr.clicked.connect(self._open_class_manager)
        self.btn_mgr.setStyleSheet(
            f'QPushButton {{'
            f'  background:transparent; color:{C_LINK};'
            f'  border:1.5px solid {C_BORDER}; border-radius:7px;'
            f'  font-size:8pt; font-weight:600; padding:0 10px; min-height:26px;'
            f'}}'
            f'QPushButton:hover {{ background:#EEF6FB; border-color:{C_STEEL}; }}'
        )
        lc.addWidget(self.btn_mgr)
        lay.addWidget(grp_cls)

        # ── Janela ───────────────────────────────────────────────
        grp_w = QGroupBox('Janela de Amostragem')
        lw    = QHBoxLayout(grp_w)
        lw.setSpacing(8)
        lw.addWidget(self._small('Tamanho:'))

        self.spin = QSpinBox()
        self.spin.setRange(1, 50)
        self.spin.setValue(10)
        self.spin.setSuffix(' px')
        self.spin.setFixedWidth(78)
        self.spin.valueChanged.connect(self._on_spin)
        lw.addWidget(self.spin)

        self.lbl_m = QLabel('= 100 × 100 m')
        self.lbl_m.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        lw.addWidget(self.lbl_m)
        lw.addStretch()
        lay.addWidget(grp_w)

        self._sep(lay)

        # ── Contadores ───────────────────────────────────────────
        grp_cnt = QGroupBox('Amostras')
        lcnt    = QVBoxLayout(grp_cnt)
        lcnt.setSpacing(4)

        self.lbl_total = QLabel('0')
        self.lbl_total.setAlignment(Qt.AlignCenter)
        self.lbl_total.setStyleSheet(
            f'font-size:26pt; font-weight:700; color:{C_TEXT};'
            f'padding:4px; letter-spacing:-1px;'
        )
        lcnt.addWidget(self.lbl_total)

        sub = QLabel('coletadas nesta sessão')
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f'color:{C_MUTED}; font-size:7.5pt; margin-bottom:4px;')
        lcnt.addWidget(sub)

        self._sep(lcnt, top=2, bottom=4)

        self.cnt_grid_widget = QWidget()
        self.cnt_grid_layout = QGridLayout(self.cnt_grid_widget)
        self.cnt_grid_layout.setSpacing(3)
        self.cnt_grid_layout.setColumnStretch(1, 1)
        self.count_labels = {}
        lcnt.addWidget(self.cnt_grid_widget)
        lay.addWidget(grp_cnt)

        self._sep(lay)

        # ── Ações ────────────────────────────────────────────────
        _ACT = f"""
    QPushButton {{
        background: {C_SURFACE};
        color: {C_TEXT};
        border: 1.5px solid {C_BORDER};
        border-radius: 7px;
        font-size: 8.5pt; font-weight: 600;
        padding: 0 12px; min-height: 30px;
    }}
    QPushButton:hover   {{ background: #2D3142; color: #FFFFFF; border-color: #2D3142; }}
    QPushButton:pressed {{ background: #1A1E2E; color: #FFFFFF; border-color: #1A1E2E; }}
"""

        btn_undo = QPushButton('↩  Desfazer')
        btn_undo.setStyleSheet(_ACT)
        btn_undo.clicked.connect(self._undo)
        lay.addWidget(btn_undo)

        btn_redo = QPushButton('↪  Refazer')
        btn_redo.setStyleSheet(_ACT)
        btn_redo.clicked.connect(self._redo)
        lay.addWidget(btn_redo)

        btn_ref = QPushButton('↺  Atualizar mapa')
        btn_ref.setStyleSheet(_ACT)
        btn_ref.clicked.connect(self._manual_refresh)
        lay.addWidget(btn_ref)

        btn_exp = QPushButton('↑  Exportar')
        btn_exp.setStyleSheet(_ACT)
        btn_exp.clicked.connect(self._export)
        lay.addWidget(btn_exp)
        self._sep(lay)

        # ── Log ──────────────────────────────────────────────────
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        lay.addWidget(self.log)

        # ── Scroll ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(root)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{C_BG}; }}
            QScrollBar:vertical {{
                background:transparent; width:8px;
            }}
            QScrollBar::handle:vertical {{
                background:#D1D9E0; border-radius:4px; min-height:20px;
            }}
            QScrollBar::handle:vertical:hover {{ background:#A0AEC0; }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height:0; }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{ background:transparent; }}
        """)
        self.setWidget(scroll)
        self.setMinimumWidth(220)

    # ═══════════════════════════════════════════════════════════════
    # COMBO / GRID DINÂMICOS
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
            self.cls_color_bar.setStyleSheet(
                f'background:{self.classes[idx][2]}; border-radius:2px;'
            )

    def _rebuild_counters_grid(self):
        while self.cnt_grid_layout.count():
            item = self.cnt_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.count_labels = {}
        for row_i, (code, label, color) in enumerate(self.classes):
            dot = QLabel('●')
            dot.setFixedWidth(14)
            dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
            name = QLabel(label)
            name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
            num = QLabel(str(self.counts.get(code, 0)))
            num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            num.setStyleSheet(
                f'font-weight:700; font-size:7.5pt; color:{C_MUTED}; min-width:22px;'
            )
            self.cnt_grid_layout.addWidget(dot,  row_i, 0)
            self.cnt_grid_layout.addWidget(name, row_i, 1)
            self.cnt_grid_layout.addWidget(num,  row_i, 2)
            self.count_labels[code] = num

    # ═══════════════════════════════════════════════════════════════
    # GERENCIADOR DE CLASSES
    # ═══════════════════════════════════════════════════════════════
    def _open_class_manager(self):
        if not self.user_info:
            return
        username = self.user_info['username']
        dlg = ClassManagerDialog(
            self.classes,
            db=self.db if username != 'local' else None,
            bioma=self.bioma, username=username,
            parent=self
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        new = dlg.get_classes()
        if not new:
            return
        self.classes = list(new)
        existing = {c[0] for c in self.classes}
        for code in list(self.counts.keys()):
            if code not in existing:
                del self.counts[code]
        for code, _, _ in self.classes:
            if code not in self.counts:
                self.counts[code] = 0
        self._populate_combo()
        self._rebuild_counters_grid()
        self._update_counters()
        if self.layer:
            self._apply_style()
            self.canvas.refresh()
        self._log(f'Classes atualizadas ({len(self.classes)}).')

    # ═══════════════════════════════════════════════════════════════
    # CAMADA DE MEMÓRIA
    # ═══════════════════════════════════════════════════════════════
    def _new_memory_layer(self):
        crs = self.canvas.mapSettings().destinationCrs()
        self.layer = QgsVectorLayer(
            f'Polygon?crs={crs.authid()}', 'Amostras (local)', 'memory'
        )
        pr = self.layer.dataProvider()
        pr.addAttributes([
            QgsField('fid',        QVariant.Int,    'int',    10),
            QgsField('class',      QVariant.String, 'string', 150),
            QgsField('label',      QVariant.String, 'string', 150),
            QgsField('interprete', QVariant.String, 'string', 100),
            QgsField('data_col',   QVariant.String, 'string', 20),
            QgsField('area_m2',    QVariant.Double, 'double', 14, 2),
            QgsField('px_size',    QVariant.Int,    'int',    5),
            QgsField('janela_px',  QVariant.Int,    'int',    5),
        ])
        self.layer.updateFields()
        self._apply_style()
        QgsProject.instance().addMapLayer(self.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        self.layer_id  = self.layer.id()
        self.total     = 0
        self.counts    = {c[0]: 0 for c in self.classes}
        self._next_fid = 1
        self._update_counters()

    def _apply_style(self):
        if not self.layer or not self.classes:
            return
        cats = []
        for code, label, color in self.classes:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            sym = QgsFillSymbol.createSimple({
                'color':         f'{r},{g},{b},255',
                'outline_color': '50,50,50,200',
                'outline_width': '0.4',
                'style':         'solid',
            })
            cats.append(QgsRendererCategory(label, sym, label))
        self.layer.setRenderer(QgsCategorizedSymbolRenderer('class', cats))
        self.layer.triggerRepaint()

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    def window_size_m(self):
        return self.pixel_size * PIXEL_SIZE_M

    def _on_spin(self, val):
        self.pixel_size = val
        self.lbl_m.setText(f'= {val * PIXEL_SIZE_M:.0f} × {val * PIXEL_SIZE_M:.0f} m')

    def _on_class_changed(self, idx):
        if 0 <= idx < len(self.classes):
            self.cls_color_bar.setStyleSheet(
                f'background:{self.classes[idx][2]}; border-radius:2px;'
            )

    def _log(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )

    def _update_counters(self):
        self.lbl_total.setText(str(self.total))
        for code, lbl in self.count_labels.items():
            n = self.counts.get(code, 0)
            lbl.setText(str(n))
            lbl.setStyleSheet(
                f'font-weight:700; font-size:7.5pt;'
                f'color:{C_TEXT if n > 0 else C_MUTED}; min-width:22px;'
            )

    def _sep(self, layout=None, top=4, bottom=4):
        w  = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, top, 0, bottom)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        wl.addWidget(line)
        if layout is not None:
            layout.addWidget(w)
        return w

    def _small(self, text):
        l = QLabel(text)
        l.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        return l

    def _get_layer(self):
        if not self.layer_id:
            return None
        layer = QgsProject.instance().mapLayer(self.layer_id)
        if not layer:
            self.layer = None
            self.layer_id = None
            return None
        self.layer = layer
        return layer

    # ═══════════════════════════════════════════════════════════════
    # REFRESH
    # ═══════════════════════════════════════════════════════════════
    def _auto_refresh(self):
        layer = self._get_layer()
        if layer:
            layer.dataProvider().reloadData()
            layer.triggerRepaint()

    def _manual_refresh(self):
        self._auto_refresh()
        self._log('Mapa atualizado.')

    # ═══════════════════════════════════════════════════════════════
    # SALVAR AMOSTRA
    # ═══════════════════════════════════════════════════════════════
    def save_sample(self, geom):
        if not self.user_info:
            self._log('Faça login primeiro.')
            return False

        code     = self.combo.currentData()
        cls_name = self.combo.currentText()
        if not code:
            return False

        username = self.user_info['username']
        px   = self.pixel_size
        area = (px * PIXEL_SIZE_M) ** 2

        # ── Online ───────────────────────────────────────────────
        if username != 'local' and self.bioma:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            srid       = canvas_crs.postgisSrid()
            if not srid or srid == 0:
                # Fallback: tenta extrair do authid (ex: "EPSG:4326" → 4326)
                auth = canvas_crs.authid()
                if ':' in auth:
                    try:
                        srid = int(auth.split(':')[1])
                    except ValueError:
                        srid = 4674   # SIRGAS 2000 como padrão
            gid, err   = self.db.insert_feature(
                self.bioma, username,
                geom.asWkt(), srid,
                cls_name, code,
                area, int(PIXEL_SIZE_M), px
            )
            if gid is None:
                self._log(f'Erro ao salvar: {err}')
                return False
            layer = self._get_layer()
            if layer:
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
            self._undo_stack.append({
                'gid': gid, 'code': code, 'cls_name': cls_name,
                'geom_wkt': geom.asWkt(), 'srid': srid,
                'area': area, 'px': px
            })
            self._redo_stack.clear()

        # ── Local ────────────────────────────────────────────────
        else:
            layer = self._get_layer()
            if not layer:
                self._new_memory_layer()
                layer = self.layer
            fn = [f.name() for f in layer.fields()]
            feat = QgsFeature(layer.fields())
            feat.setGeometry(geom)
            a = {}
            if 'fid'        in fn: a['fid']        = self._next_fid
            if 'class'      in fn: a['class']       = cls_name
            if 'label'      in fn: a['label']       = code
            if 'interprete' in fn: a['interprete']  = username
            if 'data_col'   in fn: a['data_col']    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if 'area_m2'    in fn: a['area_m2']     = area
            if 'px_size'    in fn: a['px_size']     = int(PIXEL_SIZE_M)
            if 'janela_px'  in fn: a['janela_px']   = px
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

        self._next_fid += 1
        self.total += 1
        self.counts[code] = self.counts.get(code, 0) + 1
        self._update_counters()
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

        if username != 'local' and self.bioma and 'gid' in entry:
            ok, err = self.db.delete_feature(self.bioma, entry['gid'])
            if not ok:
                self._log(f'Erro: {err}')
                self._undo_stack.append(entry)
                return
            layer = self._get_layer()
            if layer:
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
        else:
            layer = self._get_layer()
            if layer and 'provider_fid' in entry:
                layer.dataProvider().deleteFeatures([entry['provider_fid']])
                layer.updateExtents()
                self.canvas.refresh()

        self._redo_stack.append(entry)
        self.total     = max(0, self.total - 1)
        self._next_fid = max(1, self._next_fid - 1)
        code = entry.get('code')
        if code and code in self.counts:
            self.counts[code] = max(0, self.counts[code] - 1)
        self._update_counters()
        self._log(f'↩ {entry["cls_name"]}')

    def _redo(self):
        if not self._redo_stack:
            self._log('Nada para refazer.')
            return
        entry    = self._redo_stack.pop()
        username = self.user_info['username'] if self.user_info else 'local'

        if username != 'local' and self.bioma:
            gid, err = self.db.insert_feature(
                self.bioma, username,
                entry['geom_wkt'], entry.get('srid', 4326),
                entry['cls_name'], entry['code'],
                entry['area'], int(PIXEL_SIZE_M), entry['px']
            )
            if gid is None:
                self._log(f'Erro: {err}')
                self._redo_stack.append(entry)
                return
            entry['gid'] = gid
            layer = self._get_layer()
            if layer:
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
        else:
            from qgis.core import QgsGeometry as QG
            layer = self._get_layer()
            if layer:
                feat = QgsFeature(layer.fields())
                feat.setGeometry(QG.fromWkt(entry['geom_wkt']))
                ok, added = layer.dataProvider().addFeatures([feat])
                if added:
                    entry['provider_fid'] = added[0].id()
                layer.updateExtents()
                self.canvas.refresh()

        self._undo_stack.append(entry)
        self.total += 1
        self._next_fid += 1
        code = entry.get('code')
        if code:
            self.counts[code] = self.counts.get(code, 0) + 1
        self._update_counters()
        self._log(f'↪ {entry["cls_name"]}')

    # ═══════════════════════════════════════════════════════════════
    # EXPORTAR
    # ═══════════════════════════════════════════════════════════════
    def _export(self):
        layer = self._get_layer()
        if not layer or layer.featureCount() == 0:
            QMessageBox.warning(self, 'Sample Design', 'Nenhuma amostra para exportar.')
            return
        path, filt = QFileDialog.getSaveFileName(
            self, 'Exportar', 'amostras',
            'GeoPackage (*.gpkg);;Shapefile (*.shp)'
        )
        if not path:
            return
        driver = 'GPKG' if 'gpkg' in filt.lower() or path.endswith('.gpkg') else 'ESRI Shapefile'
        if driver == 'GPKG' and not path.endswith('.gpkg'):
            path += '.gpkg'
        elif driver == 'ESRI Shapefile' and not path.endswith('.shp'):
            path += '.shp'
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName  = driver
        opts.fileEncoding = 'UTF-8'
        err, msg = QgsVectorFileWriter.writeAsVectorFormatV2(
            layer, path, QgsCoordinateTransformContext(), opts
        )
        if err == QgsVectorFileWriter.NoError:
            self._log(f'Exportado: {os.path.basename(path)}')
            QMessageBox.information(self, 'Sample Design', f'Exportado!\n{path}')
        else:
            self._log(f'Erro: {msg}')
            QMessageBox.critical(self, 'Sample Design', f'Erro:\n{msg}')

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)
