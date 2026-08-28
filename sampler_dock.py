# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

import os
import sip
import math
from datetime import datetime, date

from qgis.PyQt.QtCore import QDate, Qt, QTimer, QSize, QVariant
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QTextEdit, QFrame, QFileDialog,
    QMessageBox, QSizePolicy, QScrollArea, QDialog,
    QInputDialog, QLineEdit, QRadioButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView,
    QTabWidget
)
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtGui import QPixmap, QIcon, QColor, QBrush, QFont, QPalette

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature,
    QgsProject, QgsWkbTypes, QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
    QgsSingleSymbolRenderer, QgsAttributeTableConfig, QgsEditorWidgetSetup,
    QgsProcessingMultiStepFeedback,
    QgsGeometry, QgsFeatureRequest, QgsMapLayer, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsFields,
    QgsExpression, QgsFeatureRequest as QgsFeatReq,
    QgsDataSourceUri,
    QgsProcessingContext, QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterString,
    QgsVectorDataProvider, QgsWkbTypes,
    QgsPointXY, QgsRectangle
)
from qgis.gui import QgsMapTool, QgsRubberBand

from qgis.utils import iface

import processing

from .db_manager import DBManager, sanitize_text
from .db_config  import BIOMAS, CLASSES_POR_BIOMA
from .login_dialog         import LoginDialog

EXCLUIR_CODE = "EXCLUIR"
EXCLUIR_LABEL = "EXCLUIR"
EXCLUIR_COLOR = "#FF0000"

PIXEL_SIZE_M = 10.0

def _detect_dark_theme():
    try:
        app = QApplication.instance()
        if app is None:
            return False
        return app.palette().color(QPalette.Window).lightness() < 128
    except Exception:
        return False

_DARK_THEME = _detect_dark_theme()

if _DARK_THEME:
    C_BG      = '#2B2B2B'
    C_SURFACE = '#363636'
    C_BORDER  = '#4A4A4A'
    C_TEXT    = '#E8E8E8'
    C_MUTED   = '#A8A8A8'
else:
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
C_OK      = '#16A34A'
C_DANGER  = '#DC2626'

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

_BTN_RESET = f"""
    QPushButton {{
        background: {C_ROSE}; color: #FFFFFF;
        border: none; border-radius: 5px;
        font-size: 7.5pt; font-weight: 600;
        padding: 0 8px; min-height: 22px;
    }}
    QPushButton:hover   {{ background: {C_ROSE}CC; }}
    QPushButton:pressed {{ background: {C_ROSE}99; }}
"""

class PieChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._slices = []

    def set_data(self, slices):
        self._slices = [s for s in slices if s[1] > 0]
        self.update()
        self.repaint()

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


class _RotateFeatureMapTool(QgsMapTool):
    """
    Minimal re-implementation of QGIS's native 'Rotate Feature(s)' tool.

    QgsMapToolRotateFeature is not exposed through the PyQGIS bindings and
    QgisInterface has no actionRotateFeature() shortcut, so the native tool
    cannot be triggered directly from a plugin. This tool reproduces the
    same interaction on top of whatever feature(s) the user has already
    selected with the native 'Select Features by Area or Single Click' tool:
    click-drag on the canvas rotates the selection live around its combined
    bounding-box centre; releasing the mouse commits the rotation to the
    (already-editable) layer.
    """

    def __init__(self, canvas, dock):
        super().__init__(canvas)
        self.canvas = canvas
        self.dock = dock
        self.layer = None
        self.rotating = False
        self.center = None
        self.start_angle = None
        self.orig_geoms = {}
        self.rubber_bands = {}

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)

    def deactivate(self):
        self._reset()
        super().deactivate()

    def _reset(self):
        for rb in self.rubber_bands.values():
            rb.reset(QgsWkbTypes.PolygonGeometry)
        self.rubber_bands = {}
        self.orig_geoms = {}
        self.rotating = False
        self.center = None
        self.start_angle = None
        self.layer = None

    def canvasPressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        layer = self.canvas.currentLayer()
        if layer is None or not isinstance(layer, QgsVectorLayer):
            self.dock._log('Selecione a camada de amostras antes de rotacionar.')
            return
        if not layer.isEditable():
            self.dock._log('Ative o modo de edição da camada antes de rotacionar feições.')
            return
        selected = layer.selectedFeatures()
        if not selected:
            self.dock._log(
                'Nenhuma feição selecionada. Use "Selecionar Feições por Área ou '
                'Clique Único" para selecionar antes de rotacionar.'
            )
            return

        self.layer = layer
        self.orig_geoms = {f.id(): QgsGeometry(f.geometry()) for f in selected}

        bbox = None
        for g in self.orig_geoms.values():
            bb = g.boundingBox()
            if bbox is None:
                bbox = QgsRectangle(bb)
            else:
                bbox.combineExtentWith(bb)
        self.center = bbox.center()

        pt = self.toMapCoordinates(event.pos())
        self.start_angle = math.degrees(math.atan2(pt.y() - self.center.y(), pt.x() - self.center.x()))
        self.rotating = True

        self.rubber_bands = {}
        for fid, g in self.orig_geoms.items():
            rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
            rb.setColor(QColor(255, 165, 0, 180))
            rb.setWidth(2)
            rb.setFillColor(QColor(255, 165, 0, 40))
            rb.setToGeometry(g, layer)
            self.rubber_bands[fid] = rb

        self.dock._log('Arraste para rotacionar a(s) feição(ões) selecionada(s); solte para aplicar.')

    def canvasMoveEvent(self, event):
        if not self.rotating or self.center is None:
            return
        pt = self.toMapCoordinates(event.pos())
        cur_angle = math.degrees(math.atan2(pt.y() - self.center.y(), pt.x() - self.center.x()))
        delta = cur_angle - self.start_angle
        for fid, g in self.orig_geoms.items():
            geom = QgsGeometry(g)
            geom.rotate(delta, self.center)
            if fid in self.rubber_bands:
                self.rubber_bands[fid].setToGeometry(geom, self.layer)

    def canvasReleaseEvent(self, event):
        if not self.rotating:
            return
        pt = self.toMapCoordinates(event.pos())
        cur_angle = math.degrees(math.atan2(pt.y() - self.center.y(), pt.x() - self.center.x()))
        delta = cur_angle - self.start_angle
        layer = self.layer
        for fid, g in self.orig_geoms.items():
            geom = QgsGeometry(g)
            geom.rotate(delta, self.center)
            layer.changeGeometry(fid, geom)
        self.canvas.refresh()
        self.dock._log(f'Feição(ões) rotacionada(s) em {delta:.1f}°.')
        self._reset()


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
        self.audit_mode   = False
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

        self.pantanal_vs_current_tile = None
        self.pantanal_vs_locked_cells = []
        self.pantanal_vs_locked_cell_geoms = []
        self.audit_interpreter = None

        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        self.db = DBManager()
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))

        self.edit_layer = None
        self.rotate_tool = None

        self._build_ui()
        self.canvas.scaleChanged.connect(self._on_scale_changed)

    def unload(self):
        self._refresh_timer.stop()

    @staticmethod
    def _safe_set_enabled(widget, enabled):
        if widget and not sip.isdeleted(widget):
            widget.setEnabled(enabled)

    @staticmethod
    def _layer_ok(layer):
        return layer and not sip.isdeleted(layer)

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _request_login(self):
        ok, err = self.db.test_connection()
        if not ok:
            self._log(f'Sem conexão: {err}')
            self._log('Use "Abrir GeoPackage" para trabalhar offline.')
            return
        try:
            self.db.bootstrap()
        except Exception as e:
            self._log(f'Aviso: {e}')

        dlg = LoginDialog(self.db, parent=self)
        if dlg.exec_() != QDialog.Accepted:
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

    def _show_audit_choice_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Modo de trabalho')
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel('Como deseja prosseguir?'))
        radio_interpret = QRadioButton('Interpretar')
        radio_audit = QRadioButton('Auditar')
        radio_interpret.setChecked(True)
        layout.addWidget(radio_interpret)
        layout.addWidget(radio_audit)
        btn_ok = QPushButton('Confirmar')
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)
        if dlg.exec_() == QDialog.Accepted:
            return 'audit' if radio_audit.isChecked() else 'interpret'
        return 'interpret'

    def _on_session_started(self):
        username = self.user_info['username']
        nome     = self.user_info.get('nome_completo', username)

        self.lbl_user.setText(nome)
        self.lbl_biome_val.setText(f"{self.biome} - {self.project_type}" if self.project_type else self.biome)
        self.btn_session.setText('Sair')
        self.btn_session.setStyleSheet(_pill(C_ROSE))

        self.btn_geopackage.setVisible(False)
        self.btn_ref.setVisible(True)
        self.btn_relatorio.setVisible(True)
        self.btn_export_gpkg.setVisible(False)
        self.btn_wfs.setVisible(False)

        if not self._is_local_geopackage and username != 'local':
            self.db.ensure_user_biome(username, self.biome)

        if self._is_local_geopackage:
            self.classes = list(CLASSES_POR_BIOMA.get((self.biome, self.project_type), []))
        else:
            self.classes = self.db.get_custom_classes(self.biome, self.project_type, username)

        self.counts = {c[0]: 0 for c in self.classes}
        is_admin = self.user_info.get('is_admin', False) and not self._is_local_geopackage
        self.btn_manage_users.setVisible(is_admin)

        if self.biome == 'Pantanal' and self.project_type == 'Vegetação Secundária':
            self.spin_max_scale.setVisible(False)
            self.lbl_scale.setText('Escala máx.: 1:50.000')
            self.lbl_scale.setFixedWidth(150)
            self.lbl_scale.setStyleSheet(f'color:{C_TEXT}; font-size:8pt; font-weight:400; background:transparent;')
            self.lbl_suffix.setVisible(False)
            self.max_scale = 50000
        else:
            self.spin_max_scale.setVisible(True)
            self.lbl_scale.setText('Escala máx.:')
            self.lbl_scale.setFixedWidth(75)
            self.lbl_scale.setStyleSheet(f'color:{C_TEXT}; font-size:8pt; font-weight:400; background:transparent;')
            self.lbl_suffix.setVisible(True)
            self._safe_set_enabled(self.spin_max_scale, is_admin)

        self._safe_set_enabled(self.spin, is_admin)
        self.spin_max_scale.setValue(self.max_scale)

        if self.is_auditor and not self._is_local_geopackage:
            self.audit_mode = (self._show_audit_choice_dialog() == 'audit')
        else:
            self.audit_mode = False

        self._populate_combo()

        self.btn_reclass.setVisible(self.audit_mode)
        if self.audit_mode:
            self._log('Modo auditoria ativado – utilize a reclassificação.')
            if hasattr(self, 'tool') and self.tool:
                self.tool.set_audit_mode(True)
        else:
            if hasattr(self, 'tool') and self.tool:
                self.tool.set_audit_mode(False)

        self.grp_grade.setVisible(False)
        self.btn_finish_work.setVisible(False)
        if (self.biome == 'Pantanal' and self.project_type == 'Vegetação Secundária'
                and not self._is_local_geopackage):
            try:
                self.db.ensure_pantanal_vs_tables()
            except Exception as e:
                self._log(f'Erro ao preparar tiles: {e}')
            self.grp_grade.setVisible(True)
            self._pantanal_vs_choose_tile()

        if self.is_auditor and not self._is_local_geopackage:
            self._populate_audit_filters()

        self._rebuild_counters_grid()

        if not self._is_local_geopackage:
            filter_by_user = not self.is_auditor
            layer, err = self.db.get_postgis_layer(self.biome, self.project_type, username,
                                                filter_by_user=filter_by_user)
            if err:
                self._log(err)
                self._log('Use "Abrir GeoPackage" para continuar offline.')
                return
            layer.setName(f'{self.project_type} {self.biome} [{username}]')
            self.layer    = layer
            self.layer_id = layer.id()

        self.edit_layer = None

        self._apply_style()
        self._configure_layer_visibility(is_admin)
        if self._layer_ok(self.layer):
            QgsProject.instance().addMapLayer(self.layer, False)
            QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        self._sync_counts(username)
        if self._layer_ok(self.layer):
            self.layer.committedFeaturesAdded.connect(self._on_layer_edits_committed)
            self.layer.committedFeaturesRemoved.connect(self._on_layer_edits_committed)
            self.layer.committedAttributeValuesChanges.connect(self._on_layer_edits_committed)
        self._refresh_timer.start()
        self._log(f'Sessão iniciada — {nome} · {self.biome} · {self.project_type}')
        self.btn_wfs.setVisible(False)
        self.btn_export_gpkg.setVisible(False)

        self.session_totals_tabs.setTabVisible(1, not self._is_local_geopackage)
        if self.is_auditor and not self._is_local_geopackage:
            self.session_totals_tabs.setTabVisible(2, True)
            self._populate_audit_filters()
            self._refresh_audit_stats()
        else:
            self.session_totals_tabs.setTabVisible(2, False)

        self._refresh_statistics()
        self._populate_stats_combos()

    def _logout(self):
        self._refresh_timer.stop()
        if self._layer_ok(self.layer):
            try:
                self.layer.committedFeaturesAdded.disconnect(self._on_layer_edits_committed)
                self.layer.committedFeaturesRemoved.disconnect(self._on_layer_edits_committed)
                self.layer.committedAttributeValuesChanges.disconnect(self._on_layer_edits_committed)
            except Exception:
                pass
        if self._layer_ok(self.layer):
            QgsProject.instance().removeMapLayer(self.layer)
            self.layer = None
            self.layer_id = None
        layers_grid = QgsProject.instance().mapLayersByName('Grid Ativo Pantanal VS')
        for lyr in layers_grid:
            QgsProject.instance().removeMapLayer(lyr)
        layers_tile = QgsProject.instance().mapLayersByName('Tile Ativo Pantanal VS')
        for lyr in layers_tile:
            QgsProject.instance().removeMapLayer(lyr)
        self.canvas.refresh()
        self.tile_layer = None
        self.subregion_layer = None
        self.user_info    = None
        self.biome        = None
        self.project_type = None
        self.is_auditor   = False
        self.audit_mode   = False
        self.classes      = []
        self.is_admin     = False
        self.max_scale    = 10000
        self._is_local_geopackage = False
        self.pantanal_vs_current_tile = None
        self.pantanal_vs_locked_cells = []
        self.pantanal_vs_locked_cell_geoms = []
        self.audit_interpreter = None
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
        self.btn_geopackage.setVisible(True)
        self.btn_ref.setVisible(False)
        self.btn_wfs.setVisible(False)
        self.btn_export_gpkg.setVisible(False)
        self.btn_reclass.setVisible(False)
        self.btn_manage_users.setVisible(False)
        self.btn_relatorio.setVisible(False)
        self.grp_grade.setVisible(False)
        self.btn_finish_work.setVisible(False)
        self.session_totals_tabs.setTabVisible(1, False)
        self.session_totals_tabs.setTabVisible(2, False)

    def _sync_counts(self, username):
        if not self._layer_ok(self.layer):
            return
        self.layer.dataProvider().reloadData()
        self.total = 0
        self.counts = {c[0]: 0 for c in self.classes}
        analyst_idx = self.layer.fields().indexOf('analyst')
        label_idx = self.layer.fields().indexOf('label')
        if analyst_idx == -1:
            for feat in self.layer.getFeatures():
                self.total += 1
                code = feat[label_idx] if label_idx >= 0 else ''
                if code in self.counts:
                    self.counts[code] += 1
        else:
            for feat in self.layer.getFeatures():
                if feat[analyst_idx] != username:
                    continue
                self.total += 1
                code = feat[label_idx] if label_idx >= 0 else ''
                if code in self.counts:
                    self.counts[code] += 1
        self._update_counters()

    def _on_layer_edits_committed(self, *args):
        if self.user_info:
            self._sync_counts(self.user_info['username'])
            self._refresh_statistics()

    def _on_session_btn(self):
        if self._is_local_geopackage or (self.user_info is not None):
            if QMessageBox.question(
                self, 'Sample Design', 'Encerrar sessão?',
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self._logout()
        else:
            self._request_login()

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _pantanal_vs_choose_tile(self):
        tiles = self.db.get_pantanal_vs_tiles_with_status()
        if not tiles:
            QMessageBox.warning(self, 'Vegetação Secundária', 'Nenhum tile disponível.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle('Selecionar Tile e Células')
        dlg.setMinimumWidth(700)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {C_BG};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QLabel {{
                color: {C_TEXT};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QTableWidget {{
                background: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                font-size: 8.5pt;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                gridline-color: {C_BORDER};
            }}
            QHeaderView::section {{
                background: {C_BG};
                font-weight: normal;
                font-size: 8pt;
                padding: 6px 8px;
                border: none;
                border-bottom: 1.5px solid {C_BORDER};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
        """)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        tile_combo = QComboBox()
        tile_combo.addItem('Selecione um tile...', None)
        for t in tiles:
            tile_combo.addItem(t['tile'], t['tile'])
        layout.addWidget(QLabel('Tile:'))
        layout.addWidget(tile_combo)

        cell_tbl = QTableWidget(0, 5)
        cell_tbl.setHorizontalHeaderLabels(['', 'Célula', 'Status', 'Responsável', 'Início'])
        cell_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        cell_tbl.setColumnWidth(0, 30)
        for col in range(1, 5):
            cell_tbl.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        cell_tbl.setColumnWidth(1, 100)
        cell_tbl.setColumnWidth(2, 130)
        cell_tbl.setColumnWidth(3, 80)
        cell_tbl.setColumnWidth(4, 80)
        cell_tbl.setSelectionBehavior(QTableWidget.SelectRows)
        cell_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        cell_tbl.setShowGrid(False)
        cell_tbl.verticalHeader().setVisible(False)
        layout.addWidget(cell_tbl)

        btn_box = QHBoxLayout()
        btn_lock = QPushButton('Iniciar / Bloquear células')
        btn_lock.setStyleSheet(_BTN_ACT)
        btn_continue = QPushButton('Continuar')
        btn_continue.setStyleSheet(_BTN_ACT)
        btn_unlock = QPushButton('Desbloquear células')
        btn_unlock.setStyleSheet(_BTN_ACT)
        btn_zoom = QPushButton('Zoom para tile')
        btn_zoom.setStyleSheet(_BTN_ACT)
        btn_add_layer = QPushButton('Criar camada das células')
        btn_add_layer.setStyleSheet(_BTN_ACT)
        btn_close = QPushButton('Fechar')
        btn_close.setStyleSheet(_BTN_ACT)

        btn_box.addWidget(btn_lock)
        btn_box.addWidget(btn_continue)
        if self.is_admin or self.is_auditor:
            btn_box.addWidget(btn_unlock)
        btn_box.addWidget(btn_zoom)
        btn_box.addWidget(btn_add_layer)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

        btn_continue.setVisible(False)
        btn_unlock.setVisible(self.is_admin or (self.is_auditor and not self.audit_mode))

        current_cells = []

        def populate_cells(tile_name):
            nonlocal current_cells
            current_cells = self.db.get_grids_for_tile_with_status(tile_name)
            cell_tbl.setUpdatesEnabled(False)
            cell_tbl.setRowCount(0)
            username = self.user_info['username']

            for i, c in enumerate(current_cells):
                cell_tbl.insertRow(i)
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)

                if self.audit_mode:
                    if c.get('finished_1') and not c.get('finished_2'):
                        if c.get('analyst_2') == username:
                            chk.setCheckState(Qt.Checked)
                        else:
                            chk.setCheckState(Qt.Unchecked)
                    else:
                        chk.setCheckState(Qt.Unchecked)
                else:
                    if c.get('analyst_1') == username and not c.get('finished_1'):
                        chk.setCheckState(Qt.Checked)
                    else:
                        chk.setCheckState(Qt.Unchecked)

                cell_tbl.setItem(i, 0, chk)

                item_oid = QTableWidgetItem(c['cell_oid'])
                cell_tbl.setItem(i, 1, item_oid)

                if self.audit_mode:
                    if c.get('finished_2'):
                        status = 'Auditoria finalizada'
                    elif c.get('finished_1'):
                        status = 'Interpretação finalizada'
                    else:
                        status = '—'
                else:
                    if c.get('finished_1'):
                        status = 'Interpretação finalizada'
                    elif c.get('analyst_1'):
                        status = 'Bloqueado'
                    else:
                        status = 'Livre'

                item_status = QTableWidgetItem(status)
                if status == 'Auditoria finalizada':
                    item_status.setBackground(QColor('#E0E0E0'))
                elif status == 'Interpretação finalizada':
                    item_status.setBackground(QColor('#C8E6C9'))
                elif status == 'Bloqueado':
                    item_status.setBackground(QColor('#FFCDD2'))
                elif status == 'Livre':
                    item_status.setBackground(QColor('#FFFFFF'))
                cell_tbl.setItem(i, 2, item_status)

                responsavel = c.get('analyst_1') if not self.audit_mode else c.get('analyst_2', '')
                if not responsavel:
                    responsavel = '—'
                cell_tbl.setItem(i, 3, QTableWidgetItem(responsavel))

                data = c.get('start_date_1') if not self.audit_mode else c.get('start_date_2')
                if isinstance(data, (datetime, date)):
                    data = data.strftime('%Y-%m-%d')
                elif data is None:
                    data = '—'
                cell_tbl.setItem(i, 4, QTableWidgetItem(str(data)))

            cell_tbl.setUpdatesEnabled(True)

        def on_tile_changed(idx):
            tile_name = tile_combo.itemData(idx)
            if tile_name:
                self.pantanal_vs_current_tile = tile_name
                populate_cells(tile_name)
                btn_lock.setEnabled(True)

                if self.audit_mode:
                    has_own = any(
                        c.get('analyst_2') == self.user_info['username'] and not c.get('finished_2')
                        for c in current_cells
                    )
                else:
                    has_own = any(
                        c.get('analyst_1') == self.user_info['username'] and not c.get('finished_1')
                        for c in current_cells
                    )
                btn_continue.setVisible(has_own)
            else:
                cell_tbl.setRowCount(0)
                btn_lock.setEnabled(False)
                btn_continue.setVisible(False)

        tile_combo.currentIndexChanged.connect(on_tile_changed)

        def lock_selected_cells():
            tile_name = self.pantanal_vs_current_tile
            if not tile_name:
                return
            username = self.user_info['username']
            selected = []
            for row in range(cell_tbl.rowCount()):
                if cell_tbl.item(row, 0).checkState() == Qt.Checked:
                    oid = cell_tbl.item(row, 1).text()
                    selected.append(oid)
            if not selected:
                QMessageBox.warning(dlg, 'Atenção', 'Selecione ao menos uma célula.')
                return

            if self.audit_mode:
                for oid in selected:
                    interpreter = None
                    for c in current_cells:
                        if c['cell_oid'] == oid:
                            interpreter = c['analyst_1']
                            break
                    if not interpreter:
                        QMessageBox.critical(dlg, 'Erro', f'Célula {oid} sem intérprete.')
                        return
                    ok, msg = self.db.lock_cell_for_audit(oid, username)
                    if not ok:
                        QMessageBox.critical(dlg, 'Erro', f'{oid}: {msg}')
                        return
                    self.db.fill_audit_for_cell(oid, username, interpreter)
                self.pantanal_vs_locked_cells = selected
                geoms = [QgsGeometry.fromWkt(self.db.get_cell_geom(oid)) for oid in selected]
                self.pantanal_vs_locked_cell_geoms = geoms
                self.audit_interpreter = interpreter
                self.lbl_grade_info.setText(f'Tile: {tile_name}  |  Células: {", ".join(selected)} (auditoria)')
            else:
                for oid in selected:
                    ok, msg = self.db.lock_cell(oid, username)
                    if not ok:
                        QMessageBox.critical(dlg, 'Erro', f'{oid}: {msg}')
                        return
                self.pantanal_vs_locked_cells = selected
                geoms = [QgsGeometry.fromWkt(self.db.get_cell_geom(oid)) for oid in selected]
                self.pantanal_vs_locked_cell_geoms = geoms
                self.audit_interpreter = None
                self.lbl_grade_info.setText(f'Tile: {tile_name}  |  Células: {", ".join(selected)}')

            self.btn_finish_work.setVisible(True)
            self.btn_select_grade.setEnabled(False)
            self.canvas.zoomScale(self.max_scale)
            self._add_grid_boundary_layer(tile_name, selected)
            dlg.accept()
            self._log(f'Células bloqueadas: {selected}')

        def continue_work():
            lock_selected_cells()

        def unlock_selected_cells():
            rows_to_reset = []
            for row in range(cell_tbl.rowCount()):
                if cell_tbl.item(row, 0).checkState() == Qt.Checked:
                    oid = cell_tbl.item(row, 1).text()
                    rows_to_reset.append(oid)
            if not rows_to_reset:
                QMessageBox.warning(dlg, 'Atenção', 'Selecione as células a desbloquear.')
                return
            reply = QMessageBox.question(dlg, 'Confirmar',
                f'Desbloquear {len(rows_to_reset)} célula(s)?',
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                for oid in rows_to_reset:
                    self.db.admin_reset_cell(oid)
                populate_cells(tile_combo.currentData())
                self._log(f'Células desbloqueadas: {rows_to_reset}')

        def zoom_to_tile():
            tile_name = tile_combo.currentData()
            if tile_name:
                self._zoom_to_tile(tile_name)

        def add_grid_layer():
            tile_name = tile_combo.currentData()
            if not tile_name:
                return
            checked = []
            for row in range(cell_tbl.rowCount()):
                if cell_tbl.item(row, 0).checkState() == Qt.Checked:
                    oid = cell_tbl.item(row, 1).text()
                    checked.append(oid)
            self._add_grid_boundary_layer(tile_name, checked if checked else None)

        btn_lock.clicked.connect(lock_selected_cells)
        btn_continue.clicked.connect(continue_work)
        if self.is_admin or (self.is_auditor and not self.audit_mode):
            btn_unlock.clicked.connect(unlock_selected_cells)
        btn_zoom.clicked.connect(zoom_to_tile)
        btn_add_layer.clicked.connect(add_grid_layer)
        btn_close.clicked.connect(dlg.reject)

        if dlg.exec_() != QDialog.Accepted and not self.pantanal_vs_locked_cells:
            self._log('Nenhuma célula bloqueada – a coleta estará desabilitada.')

    def _zoom_to_tile(self, tile_name):
        conn = self.db._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("SELECT ST_AsText(ST_Envelope(geom)) FROM public.tiles_ptn WHERE tile = %s", (tile_name,))
            row = cur.fetchone()
            if row:
                geom = QgsGeometry.fromWkt(row[0])
                if geom:
                    self.canvas.setExtent(geom.boundingBox())
                    self.canvas.refresh()
        except Exception as e:
            self._log(f'Erro ao zoom: {e}')
        finally:
            cur.close()
            conn.close()

    def _add_grid_boundary_layer(self, tile_name, cell_ids=None):
        for lyr in QgsProject.instance().mapLayersByName('Grid Ativo Pantanal VS'):
            QgsProject.instance().removeMapLayer(lyr)
        for lyr in QgsProject.instance().mapLayersByName('Tile Ativo Pantanal VS'):
            QgsProject.instance().removeMapLayer(lyr)

        params = self.db._get_project_conn_params('Pantanal', 'Vegetação Secundária')

        uri_cells = QgsDataSourceUri()
        uri_cells.setConnection(params['host'], str(params['port']),
                                params['dbname'], params['user_user'], params['user_pass'])
        if cell_ids:
            cells_str = ", ".join([f"'{c}'" for c in cell_ids])
            filter_cells = f"cell_oid IN ({cells_str})"
        else:
            filter_cells = f"tile_2 = '{tile_name}'"
        uri_cells.setDataSource('public', 'ptn_grade_tarefas', 'geom', filter_cells, 'cell_oid')
        uri_cells.setParam('srid', '4674')
        layer_cells = QgsVectorLayer(uri_cells.uri(False), 'Grid Ativo Pantanal VS', 'postgres')
        if layer_cells.isValid():
            symbol_cells = QgsFillSymbol.createSimple({
                'color': '0,0,0,0',
                'outline_color': '0,255,0',
                'outline_width': '0.8',
                'style': 'no'
            })
            layer_cells.setRenderer(QgsSingleSymbolRenderer(symbol_cells))
            QgsProject.instance().addMapLayer(layer_cells)
            self._log('Camada de células adicionada.')
        else:
            self._log('Falha ao carregar camada de células.')

        uri_tile = QgsDataSourceUri()
        uri_tile.setConnection(params['host'], str(params['port']),
                               params['dbname'], params['user_user'], params['user_pass'])
        uri_tile.setDataSource('public', 'tiles_ptn', 'geom', f"tile = '{tile_name}'", 'tile')
        uri_tile.setParam('srid', '4674')
        layer_tile = QgsVectorLayer(uri_tile.uri(False), 'Tile Ativo Pantanal VS', 'postgres')
        if layer_tile.isValid():
            symbol = QgsFillSymbol.createSimple({
                'color': '0,0,0,0',
                'outline_color': '255,0,0',
                'outline_width': '0.8',
                'style': 'no'
            })
            layer_tile.setRenderer(QgsSingleSymbolRenderer(symbol))
            QgsProject.instance().addMapLayer(layer_tile)
            self._log('Camada do tile adicionada.')
        else:
            self._log('Falha ao carregar camada do tile.')

    def _finish_work(self):
        if not self.pantanal_vs_locked_cells:
            return
        reply = QMessageBox.question(
            self, 'Finalizar trabalho',
            'Deseja realmente finalizar o trabalho e liberar as células?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            username = self.user_info['username']
            for oid in self.pantanal_vs_locked_cells:
                if self.audit_mode:
                    interpreter = self.audit_interpreter
                    if not interpreter:
                        interpreter = self.db.get_cell_analyst(oid)
                    if not interpreter:
                        self._log(f'Erro: intérprete não encontrado para célula {oid}')
                        continue
                    ok, err = self.db.finish_audit(oid, username, interpreter)
                    if not ok:
                        self._log(f'Erro ao finalizar auditoria de {oid}: {err}')
                else:
                    ok, err = self.db.unlock_cell(oid, username)
                    if not ok:
                        self._log(f'Erro ao finalizar célula {oid}: {err}')

            self.pantanal_vs_locked_cells = []
            self.pantanal_vs_locked_cell_geoms = []
            self.audit_interpreter = None
            self.lbl_grade_info.setText('Nenhuma célula selecionada')
            self.btn_finish_work.setVisible(False)
            self.btn_select_grade.setEnabled(True)

            layers_grid = QgsProject.instance().mapLayersByName('Grid Ativo Pantanal VS')
            for lyr in layers_grid:
                QgsProject.instance().removeMapLayer(lyr)

            layers_tile = QgsProject.instance().mapLayersByName('Tile Ativo Pantanal VS')
            for lyr in layers_tile:
                QgsProject.instance().removeMapLayer(lyr)

            if self._layer_ok(self.layer):
                QgsProject.instance().removeMapLayer(self.layer)
                self.layer = None
                self.layer_id = None

            self.canvas.refresh()
            self._log('Trabalho finalizado – células liberadas e camadas removidas.')
            if self._layer_ok(self.layer):
                self.layer.dataProvider().reloadData()
                self.layer.triggerRepaint()
            self._sync_counts(username)
            self._refresh_filtros()

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _build_ui(self):
        root = QWidget()
        root.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
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

        self.grp_grade = QGroupBox('Área de Trabalho')
        self.grp_grade.setVisible(False)
        gv = QVBoxLayout(self.grp_grade)
        self.lbl_grade_info = QLabel('Nenhuma célula selecionada')
        self.lbl_grade_info.setStyleSheet(f'color:{C_TEXT}; font-size:8.5pt; font-weight:600;')
        gv.addWidget(self.lbl_grade_info)
        h_grade = QHBoxLayout()
        self.btn_select_grade = QPushButton('Selecionar Tile / Células')
        self.btn_select_grade.setStyleSheet(_BTN_ACT)
        self.btn_select_grade.clicked.connect(self._pantanal_vs_choose_tile)
        h_grade.addWidget(self.btn_select_grade)
        self.btn_finish_work = QPushButton('Finalizar Trabalho')
        self.btn_finish_work.setStyleSheet(_pill(C_STEEL))
        self.btn_finish_work.clicked.connect(self._finish_work)
        self.btn_finish_work.setVisible(False)
        h_grade.addWidget(self.btn_finish_work)
        gv.addLayout(h_grade)
        lay.addWidget(self.grp_grade)

        grp_cls = QGroupBox('Classe'); lc = QVBoxLayout(grp_cls); lc.setSpacing(6)
        self.cls_color_bar = QFrame(); self.cls_color_bar.setFixedHeight(3); self.cls_color_bar.setStyleSheet('background: #C5CDD8; border-radius: 2px;')
        self.combo = QComboBox(); self.combo.setMinimumHeight(34); self.combo.currentIndexChanged.connect(self._on_class_changed)
        lc.addWidget(self.combo); lc.addWidget(self.cls_color_bar)

        self.btn_reclass = QPushButton('Reclass (Auditoria)')
        self.btn_reclass.setStyleSheet(_BTN_ACT)
        self.btn_reclass.clicked.connect(self._reclass_audit)
        self.btn_reclass.setVisible(False)
        lc.addWidget(self.btn_reclass)

        self.btn_manage_users = QPushButton('Gerenciar usuários')
        self.btn_manage_users.setMinimumHeight(26)
        self.btn_manage_users.setStyleSheet(f'QPushButton {{ background:transparent; color:{C_LINK}; border:1.5px solid {C_BORDER}; border-radius:7px; font-size:8pt; font-weight:600; padding:0 10px; min-height:26px; }} QPushButton:hover {{ background:#EEF6FB; border-color:{C_STEEL}; }}')
        self.btn_manage_users.clicked.connect(self._manage_users)
        self.btn_manage_users.setVisible(False)
        lc.addWidget(self.btn_manage_users)

        lay.addWidget(grp_cls)

        grp_w = QGroupBox('Janela de Amostragem'); lw = QVBoxLayout(grp_w); lw.setSpacing(4)
        grp_w.setStyleSheet("""
            QSpinBox, QLabel {
                background: transparent;
            }
        """)
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
        self.lbl_scale = QLabel('Escala máx.:')
        self.lbl_scale.setMinimumWidth(75)
        self.lbl_scale.setStyleSheet(f'color:{C_TEXT}; font-size:8pt; font-weight:400; background:transparent;')
        row_max_scale.addWidget(self.lbl_scale)
        self.spin_max_scale = QSpinBox()
        self.spin_max_scale.setRange(100, 1000000)
        self.spin_max_scale.setValue(10000)
        self.spin_max_scale.setFixedWidth(78)
        self.spin_max_scale.valueChanged.connect(self._on_max_scale_changed)
        row_max_scale.addWidget(self.spin_max_scale)
        self.lbl_suffix = QLabel('(1:x)')
        self.lbl_suffix.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        row_max_scale.addWidget(self.lbl_suffix)
        row_max_scale.addStretch()
        lw.addLayout(row_max_scale)
        lay.addWidget(grp_w)

        grp_mode = QGroupBox('Modo de desenho')
        grp_mode.setStyleSheet(f"QRadioButton {{ background-color: transparent; border: none; color: {C_TEXT}; }}")
        mode_layout = QHBoxLayout(grp_mode)
        self.radio_square = QRadioButton('Quadrado pré-definido')
        self.radio_polygon = QRadioButton('Polígono livre')
        self.radio_square.setChecked(True)
        mode_layout.addWidget(self.radio_square)
        mode_layout.addWidget(self.radio_polygon)
        lay.addWidget(grp_mode)

        self.btn_rotate_feature = QPushButton('↻  Rotacionar Feição')
        self.btn_rotate_feature.setStyleSheet(_BTN_ACT)
        self.btn_rotate_feature.setToolTip(
            'Disponível apenas no modo "Quadrado pré-definido".\n'
            'Ative o modo de edição da camada antes de usar.'
        )
        self.btn_rotate_feature.clicked.connect(self._activate_rotate_tool)
        lay.addWidget(self.btn_rotate_feature)
        self._sep(lay)

        self._draw_mode = 'square'
        self.radio_square.toggled.connect(self._on_mode_changed)
        self.radio_polygon.toggled.connect(self._on_mode_changed)
        self._update_rotate_btn_state()

        grp_cnt = QGroupBox('Amostras')
        lcnt = QVBoxLayout(grp_cnt)

        self.session_totals_tabs = QTabWidget()
        self.session_totals_tabs.setMinimumHeight(400)
        self.session_totals_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                background: {C_SURFACE};
            }}
        """)
        lcnt.addWidget(self.session_totals_tabs)

        session_tab = QWidget()
        session_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        session_layout = QVBoxLayout(session_tab)
        session_layout.setSpacing(4)
        session_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_total = QLabel('0')
        self.lbl_total.setAlignment(Qt.AlignCenter)
        self.lbl_total.setStyleSheet(f'font-size:26pt; font-weight:700; color:{C_TEXT}; padding:2px; letter-spacing:-1px;')
        session_layout.addWidget(self.lbl_total)

        self._sep(session_layout, top=2, bottom=4)
        self.pie_widget = PieChartWidget()
        self.pie_widget.setFixedHeight(170)
        self.pie_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        session_layout.addWidget(self.pie_widget)
        self._sep(session_layout, top=4, bottom=4)

        row_filtros = QHBoxLayout()
        row_filtros.setSpacing(6)
        col_t = QVBoxLayout()
        col_t.setSpacing(2)
        col_t.addWidget(self._small('Tile'))
        self.combo_tile = QComboBox()
        self.combo_tile.setMinimumHeight(26)
        self.combo_tile.addItem('Todos')
        self.combo_tile.currentIndexChanged.connect(self._update_filtered_count)
        col_t.addWidget(self.combo_tile)
        col_e = QVBoxLayout()
        col_e.setSpacing(2)
        col_e.addWidget(self._small('Ecorregião'))
        self.combo_eco = QComboBox()
        self.combo_eco.setMinimumHeight(26)
        self.combo_eco.addItem('Todas')
        self.combo_eco.currentIndexChanged.connect(self._update_filtered_count)
        col_e.addWidget(self.combo_eco)
        row_filtros.addLayout(col_t)
        row_filtros.addLayout(col_e)
        session_layout.addLayout(row_filtros)

        self.lbl_filtro_total = QLabel('Filtrado: 0')
        self.lbl_filtro_total.setStyleSheet(f'font-size:8pt; font-weight:700; color:{C_TEXT};')
        session_layout.addWidget(self.lbl_filtro_total)
        self._sep(session_layout, top=2, bottom=4)

        self.cnt_grid_widget = QWidget()
        self.cnt_grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cnt_grid_layout = QGridLayout(self.cnt_grid_widget)
        self.cnt_grid_layout.setSpacing(2)
        self.cnt_grid_layout.setColumnStretch(1, 1)
        self.count_labels = {}
        session_layout.addWidget(self.cnt_grid_widget)

        bottom_spacer = QWidget()
        bottom_spacer.setFixedHeight(14)
        session_layout.addWidget(bottom_spacer)

        scroll_session = QScrollArea()
        scroll_session.setWidgetResizable(True)
        scroll_session.setFrameShape(QFrame.NoFrame)
        scroll_session.setMinimumHeight(400)
        scroll_session.setWidget(session_tab)
        self.session_totals_tabs.addTab(scroll_session, "Sessão")

        totais_tab = QWidget()
        totais_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        totais_layout = QVBoxLayout(totais_tab)
        totais_layout.setSpacing(6)
        totais_layout.setContentsMargins(0, 0, 0, 0)

        self.stats_total_big = QLabel('0')
        self.stats_total_big.setAlignment(Qt.AlignCenter)
        self.stats_total_big.setStyleSheet(f'font-size:26pt; font-weight:700; color:{C_TEXT}; padding:4px; letter-spacing:-1px;')
        totais_layout.addWidget(self.stats_total_big)

        self.stats_analyst_combo = QComboBox()
        self.stats_analyst_combo.setMinimumHeight(26)
        self.stats_analyst_combo.addItem('Todos')
        self.stats_analyst_combo.currentIndexChanged.connect(self._on_stats_analyst_changed)
        combo_layout = QHBoxLayout()
        combo_layout.addStretch()
        combo_layout.addWidget(self.stats_analyst_combo)
        combo_layout.addStretch()
        totais_layout.addLayout(combo_layout)

        self._sep(totais_layout, top=2, bottom=4)
        self.stats_pie_widget = PieChartWidget()
        self.stats_pie_widget.setFixedHeight(170)
        self.stats_pie_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        totais_layout.addWidget(self.stats_pie_widget)
        self._sep(totais_layout, top=4, bottom=4)

        row_filtros_totais = QHBoxLayout()
        row_filtros_totais.setSpacing(6)
        col_tt = QVBoxLayout()
        col_tt.setSpacing(2)
        col_tt.addWidget(self._small('Tile'))
        self.stats_tile_combo = QComboBox()
        self.stats_tile_combo.setMinimumHeight(26)
        self.stats_tile_combo.addItem('Todos')
        self.stats_tile_combo.currentIndexChanged.connect(self._refresh_statistics)
        col_tt.addWidget(self.stats_tile_combo)
        col_te = QVBoxLayout()
        col_te.setSpacing(2)
        col_te.addWidget(self._small('Ecorregião'))
        self.stats_eco_combo = QComboBox()
        self.stats_eco_combo.setMinimumHeight(26)
        self.stats_eco_combo.addItem('Todas', None)
        self.stats_eco_combo.currentIndexChanged.connect(self._refresh_statistics)
        col_te.addWidget(self.stats_eco_combo)
        row_filtros_totais.addLayout(col_tt)
        row_filtros_totais.addLayout(col_te)
        totais_layout.addLayout(row_filtros_totais)

        self.stats_filtered_label = QLabel('Filtrado: 0')
        self.stats_filtered_label.setStyleSheet(f'font-size:8pt; font-weight:700; color:{C_TEXT};')
        totais_layout.addWidget(self.stats_filtered_label)
        self._sep(totais_layout, top=2, bottom=4)

        self.stats_grid_widget = QWidget()
        self.stats_grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stats_grid_layout = QGridLayout(self.stats_grid_widget)
        self.stats_grid_layout.setSpacing(3)
        self.stats_grid_layout.setColumnStretch(1, 1)
        totais_layout.addWidget(self.stats_grid_widget)

        self.scroll_totais = QScrollArea()
        self.scroll_totais.setWidgetResizable(True)
        self.scroll_totais.setFrameShape(QFrame.NoFrame)
        self.scroll_totais.setMinimumHeight(400)
        self.scroll_totais.setWidget(totais_tab)
        self.session_totals_tabs.addTab(self.scroll_totais, "Totais")
        self.session_totals_tabs.setTabVisible(1, False)

        audit_tab = QWidget()
        audit_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        audit_layout = QVBoxLayout(audit_tab)
        audit_layout.setSpacing(6)
        audit_layout.setContentsMargins(0, 0, 0, 0)

        self.audit_total_label = QLabel('0')
        self.audit_total_label.setAlignment(Qt.AlignCenter)
        self.audit_total_label.setStyleSheet(f'font-size:26pt; font-weight:700; color:{C_TEXT}; padding:4px; letter-spacing:-1px;')
        audit_layout.addWidget(self.audit_total_label)

        self.audit_analyst_combo = QComboBox()
        self.audit_analyst_combo.setMinimumHeight(26)
        self.audit_analyst_combo.addItem('Todos')
        self.audit_analyst_combo.currentIndexChanged.connect(self._on_audit_analyst_changed)

        audit_combo_layout = QHBoxLayout()
        audit_combo_layout.addStretch()
        audit_combo_layout.addWidget(self.audit_analyst_combo)
        audit_combo_layout.addStretch()
        audit_layout.addLayout(audit_combo_layout)

        self._sep(audit_layout, top=2, bottom=4)
        self.audit_pie_widget = PieChartWidget()
        self.audit_pie_widget.setFixedHeight(170)
        self.audit_pie_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        audit_layout.addWidget(self.audit_pie_widget)
        self._sep(audit_layout, top=4, bottom=4)

        row_filtros_audit = QHBoxLayout()
        row_filtros_audit.setSpacing(6)
        col_at = QVBoxLayout()
        col_at.setSpacing(2)
        col_at.addWidget(self._small('Tile'))
        self.audit_tile_combo = QComboBox()
        self.audit_tile_combo.setMinimumHeight(26)
        self.audit_tile_combo.addItem('Todos')
        self.audit_tile_combo.currentIndexChanged.connect(self._refresh_audit_stats)
        col_at.addWidget(self.audit_tile_combo)

        col_ae = QVBoxLayout()
        col_ae.setSpacing(2)
        col_ae.addWidget(self._small('Ecorregião'))
        self.audit_eco_combo = QComboBox()
        self.audit_eco_combo.setMinimumHeight(26)
        self.audit_eco_combo.addItem('Todas', None)
        self.audit_eco_combo.currentIndexChanged.connect(self._refresh_audit_stats)
        col_ae.addWidget(self.audit_eco_combo)

        row_filtros_audit.addLayout(col_at)
        row_filtros_audit.addLayout(col_ae)
        audit_layout.addLayout(row_filtros_audit)

        self.audit_filtered_label = QLabel('Auditados: 0')
        self.audit_filtered_label.setStyleSheet(f'font-size:8pt; font-weight:700; color:{C_TEXT};')
        audit_layout.addWidget(self.audit_filtered_label)
        self._sep(audit_layout, top=2, bottom=4)

        self.audit_grid_widget = QWidget()
        self.audit_grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.audit_grid_widget.setMinimumHeight(80)
        self.audit_grid_layout = QGridLayout(self.audit_grid_widget)
        self.audit_grid_layout.setSpacing(3)
        self.audit_grid_layout.setColumnStretch(1, 1)
        audit_layout.addWidget(self.audit_grid_widget)

        scroll_audit = QScrollArea()
        scroll_audit.setWidgetResizable(True)
        scroll_audit.setFrameShape(QFrame.NoFrame)
        scroll_audit.setMinimumHeight(400)
        scroll_audit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_audit.setWidget(audit_tab)
        self.session_totals_tabs.addTab(scroll_audit, "Auditoria")
        self.session_totals_tabs.setTabVisible(2, False)

        lay.addWidget(grp_cnt)

        self._sep(lay)

        self.btn_relatorio = QPushButton('Gerar relatório')
        self.btn_relatorio.setStyleSheet(_BTN_ACT)
        self.btn_relatorio.clicked.connect(self._gerar_relatorio)
        lay.addWidget(self.btn_relatorio)

        btn_undo = QPushButton('↩  Desfazer'); btn_undo.setStyleSheet(_BTN_ACT); btn_undo.clicked.connect(self._undo); lay.addWidget(btn_undo)
        btn_redo = QPushButton('↪  Refazer'); btn_redo.setStyleSheet(_BTN_ACT); btn_redo.clicked.connect(self._redo); lay.addWidget(btn_redo)
        self.btn_ref = QPushButton('↺  Atualizar mapa')
        self.btn_ref.setStyleSheet(_BTN_ACT)
        self.btn_ref.clicked.connect(self._manual_refresh)
        lay.addWidget(self.btn_ref)

        self.btn_export_gpkg = QPushButton('Exportar')
        self.btn_export_gpkg.setStyleSheet(_BTN_ACT)
        self.btn_export_gpkg.clicked.connect(self._export_to_gpkg)
        self.btn_export_gpkg.setVisible(False)
        lay.addWidget(self.btn_export_gpkg)

        self.btn_wfs = QPushButton('Exportar para WFS')
        self.btn_wfs.setStyleSheet(_BTN_ACT)
        self.btn_wfs.clicked.connect(self._export_to_wfs)
        self.btn_wfs.setVisible(False)
        lay.addWidget(self.btn_wfs)

        self._sep(lay)

        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(80); lay.addWidget(self.log)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""QScrollArea {{ border:none; background:{C_BG}; }} QScrollBar:vertical {{ background:transparent; width:8px; }} QScrollBar::handle:vertical {{ background:#D1D9E0; border-radius:4px; min-height:20px; }} QScrollBar::handle:vertical:hover {{ background:#A0AEC0; }} QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }} QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}""")
        scroll.setWidget(root)

        self.setWidget(scroll)
        self.setMinimumWidth(320)
        self.setMinimumHeight(550)

    def _on_mode_changed(self):
        if self.radio_square.isChecked():
            self._draw_mode = 'square'
        elif self.radio_polygon.isChecked():
            self._draw_mode = 'polygon'

        if hasattr(self, 'tool') and self.tool:
            self.tool.set_mode(self._draw_mode)

        self._update_rotate_btn_state()

    def get_draw_mode(self):
        return self._draw_mode

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _update_rotate_btn_state(self):
        if hasattr(self, 'btn_rotate_feature') and not sip.isdeleted(self.btn_rotate_feature):
            self.btn_rotate_feature.setEnabled(self._draw_mode == 'square')

    def _activate_rotate_tool(self):
        if self._draw_mode != 'square':
            QMessageBox.warning(
                self, 'Sample Design',
                'A rotação de feições só está disponível no modo "Quadrado pré-definido".'
            )
            return
        if not self._layer_ok(self.layer):
            QMessageBox.warning(self, 'Sample Design', 'Nenhuma camada de amostras carregada.')
            return
        if not self.layer.isEditable():
            QMessageBox.warning(
                self, 'Sample Design',
                'Ative o modo de edição da camada antes de rotacionar feições.'
            )
            return

        self.iface.setActiveLayer(self.layer)

        if not self.layer.selectedFeatures():
            QMessageBox.information(
                self, 'Sample Design',
                'Nenhuma feição selecionada.\n\n'
                'Use "Selecionar Feições por Área ou Clique Único" para selecionar '
                'a(s) feição(ões) desejada(s) e clique novamente em "Rotacionar Feição".'
            )
            self.iface.actionSelect().trigger()
            return

        if self.rotate_tool is None or sip.isdeleted(self.rotate_tool):
            self.rotate_tool = _RotateFeatureMapTool(self.canvas, self)
        self.canvas.setMapTool(self.rotate_tool)
        self._log('Ferramenta "Rotacionar Feição" ativada — arraste sobre a seleção para rotacioná-la.')

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

        projetos_disponiveis = []
        for (b, p) in CLASSES_POR_BIOMA.keys():
            if b == biome:
                projetos_disponiveis.append(p)
        if not projetos_disponiveis:
            QMessageBox.critical(self, 'Erro', f'Nenhum projeto disponível para o bioma "{biome}".')
            return

        project_type, ok = QInputDialog.getItem(self, 'Projeto', 'Selecione o projeto:', projetos_disponiveis, 0, False)
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
            try:
                self.layer.committedFeaturesAdded.disconnect(self._on_layer_edits_committed)
                self.layer.committedFeaturesRemoved.disconnect(self._on_layer_edits_committed)
                self.layer.committedAttributeValuesChanges.disconnect(self._on_layer_edits_committed)
            except Exception:
                pass
            QgsProject.instance().removeMapLayer(self.layer)
        self.layer = sample_layer
        self.layer_id = sample_layer.id()
        self._is_local_geopackage = True
        self.user_info = {'username': analyst, 'nome_completo': analyst}
        self.biome = biome
        self.project_type = project_type
        self.is_auditor = False
        self.audit_mode = False
        self.classes = list(CLASSES_POR_BIOMA.get((biome, project_type), []))
        self.counts = {c[0]: 0 for c in self.classes}
        self.is_admin = False
        self.max_scale = 10000
        self.spin_max_scale.setVisible(True)
        self.lbl_scale.setText('Escala máx.:')
        self.lbl_scale.setFixedWidth(75)
        self.lbl_scale.setStyleSheet(f'color:{C_TEXT}; font-size:8pt; font-weight:400; background:transparent;')
        self.lbl_suffix.setVisible(True)
        self._safe_set_enabled(self.spin, False)
        self._safe_set_enabled(self.spin_max_scale, False)
        self.spin_max_scale.setValue(self.max_scale)
        self.lbl_user.setText(analyst)
        self.lbl_biome_val.setText(f"{biome} - {project_type}")
        self.btn_session.setText('Fechar GeoPackage')
        self.btn_session.setStyleSheet(_pill(C_ROSE))
        self.btn_geopackage.setVisible(False)
        self.btn_ref.setVisible(False)
        self.btn_manage_users.setVisible(False)
        self.btn_wfs.setVisible(True)
        self.btn_export_gpkg.setVisible(False)
        self.btn_relatorio.setVisible(False)
        self.btn_reclass.setVisible(False)
        self._populate_combo()
        self._rebuild_counters_grid()
        self._apply_style()
        self._configure_layer_visibility(False)
        QgsProject.instance().addMapLayer(self.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        if self._layer_ok(self.layer):
            self.layer.committedFeaturesAdded.connect(self._on_layer_edits_committed)
            self.layer.committedFeaturesRemoved.connect(self._on_layer_edits_committed)
            self.layer.committedAttributeValuesChanges.connect(self._on_layer_edits_committed)

        self.session_totals_tabs.setTabVisible(1, self._get_prodes_totals_layer() is not None)
        self.session_totals_tabs.setTabVisible(2, False)
        self._refresh_filtros()
        self._sync_counts(analyst)
        self._populate_stats_combos()
        self._refresh_statistics()
        self._refresh_timer.start()
        self._log(f'GeoPackage aberto: {path} — {analyst} · {biome} · {project_type}')

    def _configure_layer_visibility(self, is_admin):
        if not self._layer_ok(self.layer):
            return
        always_hidden = {'área', 'ações'}
        cfg = self.layer.attributeTableConfig()
        columns = cfg.columns()
        for col in columns:
            if col.name in always_hidden:
                col.hidden = True
                continue
            if is_admin:
                col.hidden = False
            elif self.is_auditor:
                if col.name in {'area_m2', 'px_size', 'window_px', 'audit'}:
                    col.hidden = True
                else:
                    col.hidden = False
            else:
                if col.name in {'area_m2', 'px_size', 'window_px', 'analyst', 'audit', 'label_audit'}:
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

    def _on_scale_changed(self, scale):
        if self.pantanal_vs_locked_cells:
            if not self._enforcing_scale and scale < self.max_scale:
                self._enforcing_scale = True
                self.canvas.zoomScale(self.max_scale)
                self._enforcing_scale = False
            return
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
    # ═══════════════════════════════════════════════════════════════
    def _reclass_audit(self):
        if not self._layer_ok(self.layer) or not self.user_info:
            return
        if not self.is_auditor or not self.audit_mode:
            return

        selected_ids = self.layer.selectedFeatureIds()
        if not selected_ids:
            QMessageBox.warning(self, 'Auditoria', 'Selecione pelo menos um polígono no mapa.')
            return

        code = self.combo.currentData()
        if not code:
            self._log('Nenhuma classe selecionada para reclassificação.')
            return

        if code == EXCLUIR_CODE:
            self._log(f'Marcando {len(selected_ids)} polígono(s) para exclusão (label_audit = EXCLUIR).')

        auditor = self.user_info['username']
        layer = self.layer
        fields = layer.fields()
        idx_label_audit = fields.indexOf('label_audit')
        idx_audit = fields.indexOf('audit')

        if idx_label_audit == -1 or idx_audit == -1:
            self._log('Campos de auditoria não encontrados na camada.')
            return

        cls_name = self.combo.currentText()
        reply = QMessageBox.question(
            self, 'Confirmar Reclassificação',
            f'Reclassificar {len(selected_ids)} polígono(s) como "{cls_name}"?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        changes = {}
        for fid in selected_ids:
            changes[fid] = {idx_label_audit: code, idx_audit: auditor}

        if self._is_local_geopackage:
            layer.dataProvider().changeAttributeValues(changes)
            layer.updateExtents()
            self.canvas.refreshAllLayers()
        else:
            layer.dataProvider().changeAttributeValues(changes)
            layer.triggerRepaint()

        self._log(f'Reclass: {len(selected_ids)} polígono(s) → "{cls_name}" por {auditor}.')
        self._sync_counts(self.user_info['username'])
        self._refresh_filtros()
        self._refresh_statistics()

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _manage_users(self):
        if not self.is_admin or self._is_local_geopackage:
            return
        users = self.db.get_active_users()
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
        btn_toggle_auditor = QPushButton('Alternar Auditor')
        btn_toggle_auditor.setStyleSheet(_BTN_ACT)
        btn_toggle_auditor.clicked.connect(lambda: self._toggle_auditor_status(tbl, users, refresh_table))
        btn_fechar = QPushButton('Fechar')
        btn_fechar.setStyleSheet(_BTN_ACT)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_toggle_auditor)
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
                if not username or not senha:
                    QMessageBox.warning(dlg_add, 'Atenção', 'Usuário e senha são obrigatórios.')
                    return
                ok, msg = self.db.register_user(username, nome_completo, senha, bioma)
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

    def _toggle_auditor_status(self, tbl, users, refresh_callback):
        row = tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Atenção', 'Selecione um usuário na tabela.')
            return
        username = users[row]['username']
        current = users[row].get('is_auditor', False)
        novo = not current
        action = "conceder" if novo else "remover"
        reply = QMessageBox.question(
            self, 'Confirmar alteração',
            f'Deseja {action} a permissão de auditor para "{username}"?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.set_user_auditor(username, novo)
            refresh_callback()
            self._log(f'Auditoria de "{username}" {"ativada" if novo else "desativada"}.')

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _populate_combo(self):
        self.combo.blockSignals(True)
        prev = self.combo.currentData()
        self.combo.clear()
        for code, label, color in self.classes:
            self.combo.addItem(label, userData=code)

        if self.is_auditor and self.audit_mode:
            self.combo.addItem(EXCLUIR_LABEL, userData=EXCLUIR_CODE)

        if prev is not None:
            for i in range(self.combo.count()):
                if self.combo.itemData(i) == prev:
                    self.combo.setCurrentIndex(i)
                    break

        if self.combo.currentIndex() < 0 and self.combo.count() > 0:
            self.combo.setCurrentIndex(0)

        self.combo.blockSignals(False)
        self._on_class_changed(self.combo.currentIndex())

    def _on_class_changed(self, idx):
        if idx < 0:
            return
        code = self.combo.itemData(idx)
        if code == EXCLUIR_CODE:
            self.cls_color_bar.setStyleSheet(f'background:{EXCLUIR_COLOR}; border-radius:2px;')
        else:
            if 0 <= idx < self.combo.count():
                if code is None:
                    pass
                else:
                    for c_code, _, color in self.classes:
                        if c_code == code:
                            self.cls_color_bar.setStyleSheet(f'background:{color}; border-radius:2px;')
                            return
                    self.cls_color_bar.setStyleSheet('background:#C5CDD8; border-radius:2px;')
            else:
                self.cls_color_bar.setStyleSheet('background:#C5CDD8; border-radius:2px;')

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
        self.cnt_grid_widget.setMinimumHeight((len(self.classes) + 1) * 22 + 24)
        self.cnt_grid_layout.activate()
        self.cnt_grid_widget.updateGeometry()

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
        prev_tile = self.combo_tile.currentText() if self.combo_tile.count() > 0 else 'Todos'
        prev_eco  = self.combo_eco.currentData() if self.combo_eco.count() > 0 else None

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
            idx_t = self.combo_tile.findText(prev_tile)
            self.combo_tile.setCurrentIndex(idx_t if idx_t >= 0 else 0)
            idx_e = self.combo_eco.findData(prev_eco)
            self.combo_eco.setCurrentIndex(idx_e if idx_e >= 0 else 0)
            self.combo_tile.blockSignals(False)
            self.combo_eco.blockSignals(False)
            self._update_filtered_count()
            return

        if not self.user_info or self.user_info['username'] == 'local':
            return
        tiles, ecos_sanitized = self.db.get_tiles_ecorregioes(self.biome, self.project_type, self.user_info['username'])
        self.combo_tile.blockSignals(True)
        self.combo_eco.blockSignals(True)
        self.combo_tile.clear()
        self.combo_tile.addItem('Todos')
        self.combo_tile.addItems(tiles)
        self.combo_eco.clear()
        self.combo_eco.addItem('Todas', None)
        eco_map = self.db.get_ecoregion_display_map(self.biome, self.project_type)
        for eco_s in ecos_sanitized:
            display = eco_map.get(eco_s, eco_s)
            self.combo_eco.addItem(display, userData=eco_s)
        idx_t = self.combo_tile.findText(prev_tile)
        self.combo_tile.setCurrentIndex(idx_t if idx_t >= 0 else 0)
        idx_e = self.combo_eco.findData(prev_eco)
        self.combo_eco.setCurrentIndex(idx_e if idx_e >= 0 else 0)
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
                if item.widget():
                    item.widget().deleteLater()
            self.count_labels = {}
            color_map = {code: color for code, _, color in self.classes}
            label_map = {code: label for code, label, _ in self.classes}
            row_i = 0
            for code, n in counts.items():
                if n == 0:
                    continue
                display_name = label_map.get(code, code)
                color = color_map.get(code, '#888888')
                dot = QLabel('●')
                dot.setFixedWidth(14)
                dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
                name = QLabel(display_name)
                name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
                num = QLabel(str(n))
                num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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
            self.cnt_grid_widget.setMinimumHeight((row_i + 1) * 22 + 24)
            self.cnt_grid_layout.activate()
            self.cnt_grid_widget.updateGeometry()
            is_filtered = (tile != 'Todos' or eco is not None)
            if is_filtered:
                self.lbl_total.setText(str(total_f))
                slices = [(label_map.get(code, code), n, color_map.get(code, '#888888')) for code, n in counts.items() if n > 0]
                self.pie_widget.set_data(slices)
            else:
                self._update_counters()
        else:
            if not self.user_info or self.user_info['username'] == 'local':
                return
            rows = self.db.get_contagem(self.biome, self.project_type, self.user_info['username'],
                                        tile=tile if tile != 'Todos' else None,
                                        ecoregion=eco)
            while self.cnt_grid_layout.count():
                item = self.cnt_grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.count_labels = {}
            color_map = {code: color for code, _, color in self.classes}
            label_map = {code: label for code, label, _ in self.classes}
            total_f   = 0
            for i, (cls_code, n) in enumerate(rows):
                display_name = label_map.get(cls_code, cls_code)
                color = color_map.get(cls_code, '#888888')
                dot = QLabel('●')
                dot.setFixedWidth(14)
                dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
                name = QLabel(display_name)
                name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
                num = QLabel(str(n))
                num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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
            self.cnt_grid_widget.setMinimumHeight((len(rows) + 1) * 22 + 24)
            self.cnt_grid_layout.activate()
            self.cnt_grid_widget.updateGeometry()
            is_filtered = (tile != 'Todos' or eco is not None)
            if is_filtered:
                self.lbl_total.setText(str(total_f))
                self.pie_widget.set_data([(label_map.get(cls_code, cls_code), n, color_map.get(cls_code, '#888888')) for cls_code, n in rows if n > 0])
            else:
                self._update_counters()

    def _apply_style(self):
        if not self._layer_ok(self.layer) or not self.classes:
            return
        cats = []
        for code, label, color in self.classes:
            r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            sym = QgsFillSymbol.createSimple({'color':f'{r},{g},{b},255','outline_color':'50,50,50,200','outline_width':'0.4','style':'solid'})
            cats.append(QgsRendererCategory(code, sym, label))
        self.layer.setRenderer(QgsCategorizedSymbolRenderer('label', cats))
        self.layer.triggerRepaint()

    def window_size_m(self):
        return self.pixel_size * PIXEL_SIZE_M

    def _on_spin(self, val):
        self.pixel_size = val
        self.lbl_m.setText(f'= {val * PIXEL_SIZE_M:.0f} × {val * PIXEL_SIZE_M:.0f} m')

    def _log(self, msg):
        try:
            if not sip.isdeleted(self.log):
                self.log.append(msg)
                self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        except RuntimeError:
            pass

    def _get_layer(self):
        if not self.layer_id:
            return None
        layer = QgsProject.instance().mapLayer(self.layer_id)
        if not layer or sip.isdeleted(layer):
            self.layer = None
            self.layer_id = None
            return None
        self.layer = layer
        return layer

    def _auto_refresh(self):
        if not self._is_local_geopackage:
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
        self._refresh_statistics()

    def _manual_refresh(self):
        self._auto_refresh()
        self._refresh_filtros()
        self._log('Mapa atualizado.')

    # ═══════════════════════════════════════════════════════════════
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
    # ═══════════════════════════════════════════════════════════════
    def save_sample(self, geom):
        if not self.user_info:
            self._log('Faça login primeiro.')
            return False
        if (self.biome == 'Pantanal' and self.project_type == 'Vegetação Secundária'
                and not self._is_local_geopackage):
            if not self.pantanal_vs_locked_cells:
                self._log('É necessário selecionar e bloquear uma célula antes de coletar amostras.')
                return False
            inside = False
            for cell_geom in self.pantanal_vs_locked_cell_geoms:
                if cell_geom.intersects(geom):
                    inside = True
                    break
            if not inside:
                self._log('O polígono está fora das células bloqueadas.')
                return False
        code = self.combo.currentData()
        cls_name = self.combo.currentText()
        if not code:
            return False
        username = self.user_info['username']
        px = self.pixel_size
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
        auditor_name = username if self.audit_mode else None

        if not self._is_local_geopackage and username != 'local' and self.biome:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            srid = canvas_crs.postgisSrid()
            if not srid or srid == 0:
                auth = canvas_crs.authid()
                if ':' in auth:
                    try:
                        srid = int(auth.split(':')[1])
                    except ValueError:
                        srid = 4674
                else:
                    srid = 4674
            current_date = QDate.currentDate().toPyDate()
            fid, err = self.db.insert_feature(
                self.biome, self.project_type, username, geom.asWkt(), srid,
                code, area, int(PIXEL_SIZE_M), px, prodes_str,
                audit=auditor_name, label_audit=None,
                date_val=current_date
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
            layer = self._get_layer()
            if not self._layer_ok(layer):
                self._log('Nenhuma camada ativa para salvar.')
                return False
            fn = [f.name() for f in layer.fields()]
            feat = QgsFeature(layer.fields())
            feat.setGeometry(geom)
            a = {}
            today = QDate.currentDate()
            if self._is_local_geopackage:
                tile, eco = self._local_intersect(geom)
                if 'tile' in fn and tile:
                    a['tile'] = tile
                if 'ecoregion' in fn and eco:
                    a['ecoregion'] = eco
            if 'label' in fn:
                a['label'] = code
            if 'analyst' in fn:
                a['analyst'] = username
            if 'biome' in fn:
                a['biome'] = sanitize_text(self.biome) if self.biome else ''
            if 'date' in fn:
                a['date'] = today
            if 'prodes' in fn:
                a['prodes'] = prodes_str
            if 'area_m2' in fn:
                a['area_m2'] = area
            if 'px_size' in fn:
                a['px_size'] = int(PIXEL_SIZE_M)
            if 'window_px' in fn:
                a['window_px'] = px
            if 'audit' in fn and auditor_name:
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
            self.canvas.refreshAllLayers()
            self._sync_counts(username)

        self.total += 1
        self.counts[code] = self.counts.get(code, 0) + 1
        self._update_counters()
        if not self._is_local_geopackage:
            self._refresh_filtros()
        if self._is_local_geopackage:
            self._refresh_filtros()
        self._refresh_statistics()
        self._log(f'#{self.total}  {cls_name}')
        return True

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _undo(self):
        if not self._undo_stack:
            self._log('Nada para desfazer.')
            return
        entry = self._undo_stack.pop()
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
                self.canvas.refreshAllLayers()

        self._redo_stack.append(entry)
        self.total = max(0, self.total - 1)
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
        self._refresh_statistics()
        self._log(f'↩ {entry["cls_name"]}')

    def _redo(self):
        if not self._redo_stack:
            self._log('Nada para refazer.')
            return
        entry = self._redo_stack.pop()
        username = self.user_info['username'] if self.user_info else 'local'
        is_admin = getattr(self, 'is_admin', False) and not self._is_local_geopackage

        if not self._is_local_geopackage and username != 'local' and self.biome:
            prodes_str = f"{datetime.now().year-1}-{datetime.now().year}"
            fid, err = self.db.insert_feature(
                self.biome, self.project_type, username,
                entry['geom_wkt'], entry.get('srid', 4326),
                entry['code'], entry['area'], int(PIXEL_SIZE_M), entry['px'],
                prodes_str, audit=None, label_audit=None,
                date_val=datetime.now().date()
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
                    if 'tile' in [f.name() for f in layer.fields()]:
                        a['tile'] = tile
                    if 'ecoregion' in [f.name() for f in layer.fields()]:
                        a['ecoregion'] = eco
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
                self.canvas.refreshAllLayers()

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
        self._refresh_statistics()
        self._log(f'↪ {entry["cls_name"]}')

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _gerar_relatorio(self):
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
        )
        from qgis.PyQt.QtGui import QColor, QPixmap, QPainter
        from qgis.PyQt.QtCore import Qt
        if not self.user_info:
            return
        tile = self.combo_tile.currentText()
        eco_sanitized = self.combo_eco.currentData()
        eco_display = self.combo_eco.currentText()
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
        dlg.setMinimumWidth(500)
        dlg.setMinimumHeight(500)
        dlg.setStyleSheet(f"""
            QDialog, QWidget {{ background:{C_BG}; font-family:'Segoe UI',sans-serif; color:{C_TEXT}; }}
            QTableWidget {{ border:1px solid {C_BORDER}; border-radius:6px; font-size:8.5pt; background:{C_SURFACE}; gridline-color:{C_BORDER}; }}
            QHeaderView::section {{ background:{C_BG}; font-weight:700; font-size:8pt; padding:5px 8px; border:none; border-bottom:1.5px solid {C_BORDER}; }}
            QTableWidget::item {{ padding:5px 8px; }}
            QTableWidget::item:alternate {{ background:#F5F7FA; }}
            QLabel {{ background:transparent; color:{C_TEXT}; }}
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(10)
        titulo = QLabel('Relatório amostral')
        titulo.setStyleSheet(f'font-size:14pt; font-weight:700; color:{C_TEXT};')
        lay.addWidget(titulo)
        subtitulo = QLabel(f'Bioma: {self.biome or "—"}  ·  Tile: {tile}  ·  Ecorregião: {eco_display}')
        subtitulo.setStyleSheet(f'font-size:9pt; color:{C_TEXT};')
        lay.addWidget(subtitulo)
        total_label = QLabel(f'Total de amostras: {total}')
        total_label.setStyleSheet(f'font-size:12pt; font-weight:700;')
        lay.addWidget(total_label)
        pie = PieChartWidget()
        pie.setFixedHeight(180)
        pie.set_data([(self._code_to_label(code), n, color_map.get(code, '#888888')) for code, n in rows if n > 0])
        lay.addWidget(pie)

        tbl = QTableWidget(len(rows), 3)
        tbl.setHorizontalHeaderLabels(['', 'Classe', 'Amostras'])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tbl.setColumnWidth(0, 18)
        tbl.verticalHeader().setVisible(False)
        tbl.verticalHeader().setDefaultSectionSize(26)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setAlternatingRowColors(False)
        tbl.setSelectionMode(QTableWidget.NoSelection)
        tbl.setShowGrid(False)
        tbl.setIconSize(QSize(12, 12))
        for i, (code, n) in enumerate(rows):
            cor = color_map.get(code, '#888888')
            item_cor = QTableWidgetItem()
            item_cor.setBackground(QBrush(QColor(cor)))
            item_cor.setFlags(Qt.ItemIsEnabled)
            tbl.setItem(i, 0, item_cor)
            item_cls = QTableWidgetItem(self._code_to_label(code))
            item_cls.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_cls.setFlags(Qt.ItemIsEnabled)
            tbl.setItem(i, 1, item_cls)
            item_n = QTableWidgetItem(str(n))
            item_n.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            item_n.setFlags(Qt.ItemIsEnabled)
            tbl.setItem(i, 2, item_n)
        lay.addWidget(tbl)

        btn_row = QHBoxLayout()
        btn_pdf = QPushButton('⬇  Exportar PDF')
        btn_pdf.setStyleSheet(_BTN_ACT)
        btn_pdf.clicked.connect(lambda: self._exportar_pdf(dlg, tile, eco_display, eco_sanitized, rows, total))
        btn_fechar = QPushButton('Fechar')
        btn_fechar.setStyleSheet(_BTN_ACT)
        btn_fechar.clicked.connect(dlg.close)
        btn_row.addWidget(btn_pdf)
        btn_row.addStretch()
        btn_row.addWidget(btn_fechar)
        lay.addLayout(btn_row)
        dlg.exec_()

    def _code_to_label(self, code):
        if code == EXCLUIR_CODE:
            return EXCLUIR_LABEL
        for c, label, _ in self.classes:
            if c == code:
                return label
        return code

    def _exportar_pdf(self, parent, tile, eco_display, eco_sanitized, rows, total):
        from qgis.PyQt.QtPrintSupport import QPrinter
        from qgis.PyQt.QtGui import QPainter, QFont, QColor, QBrush, QPen
        from qgis.PyQt.QtCore import QRectF, Qt
        path, _ = QFileDialog.getSaveFileName(parent, 'Salvar PDF', 'relatorio_amostral', 'PDF (*.pdf)')
        if not path:
            return
        if not path.endswith('.pdf'):
            path += '.pdf'
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPrinter.A4)
        p = QPainter(printer)
        p.setRenderHint(QPainter.Antialiasing)
        dpi = printer.resolution()
        W = printer.pageRect().width()
        M = int(dpi * 0.7)
        y = M

        def pt(inches):
            return int(dpi * inches)

        def txt(text, yy, size=10, bold=False, color='#2D3142', x=None, w=None, align=Qt.AlignLeft | Qt.AlignVCenter):
            nonlocal y
            f = QFont('Arial', size)
            f.setBold(bold)
            p.setFont(f)
            p.setPen(QColor(color))
            rx = x if x is not None else M
            rw = w if w is not None else W - M * 2
            rh = pt(0.35)
            p.drawText(QRectF(rx, yy, rw, rh), align, text)
            return yy + rh + pt(0.05)

        y = txt('Relatório amostral', y, size=14, bold=True)
        y = txt(f'Bioma: {self.biome or "—"}  ·  Tile: {tile}  ·  Ecorregião: {eco_display}', y, size=9)
        y = txt(f'Total de amostras: {total}', y, size=12, bold=True)
        y += pt(0.15)
        pie_size = pt(2.4)
        pie_x = (W - pie_size) / 2
        pie_rect = QRectF(pie_x, y, pie_size, pie_size)
        color_map = {code: color for code, _, color in self.classes}
        total_v = sum(n for _, n in rows)
        angle = 90 * 16
        for code, n in rows:
            span = int(round(n / total_v * 360 * 16))
            cor = color_map.get(code, '#888888')
            p.setBrush(QBrush(QColor(cor)))
            p.setPen(QPen(QColor('#FFFFFF'), 3))
            p.drawPie(pie_rect, angle, -span)
            angle -= span
        y += pie_size + pt(0.4)
        col_w = [(W - M * 2) * 0.6, (W - M * 2) * 0.2, (W - M * 2) * 0.2]
        row_h = pt(0.28)
        hdr_h = pt(0.32)
        p.setBrush(QBrush(QColor('#F0F4F8')))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(M, y, W - M * 2, hdr_h))
        p.setPen(QColor('#2D3142'))
        p.setFont(QFont('Arial', 9, QFont.Bold))
        for j, (htext, cw, cx) in enumerate(zip(['Classe', 'Amostras', '%'], col_w, [M, M + col_w[0], M + col_w[0] + col_w[1]])):
            align = Qt.AlignCenter if j > 0 else Qt.AlignLeft | Qt.AlignVCenter
            p.drawText(QRectF(cx + 4, y, cw - 4, hdr_h), align, htext)
        y += hdr_h
        p.setFont(QFont('Arial', 9))
        for i, (code, n) in enumerate(rows):
            bg = QColor('#FFFFFF') if i % 2 == 0 else QColor('#F8FAFC')
            p.setBrush(QBrush(bg))
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(M, y, W - M * 2, row_h))
            cor = color_map.get(code, '#888888')
            p.setBrush(QBrush(QColor(cor)))
            p.drawRoundedRect(QRectF(M + 4, y + row_h / 2 - pt(0.07), pt(0.12), pt(0.12)), 2, 2)
            pct = f'{n / total * 100:.1f}%'
            p.setPen(QColor('#2D3142'))
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
        w = QWidget()
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
        l.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        return l

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _get_prodes_totals_layer(self):
        for lyr in QgsProject.instance().mapLayersByName('prodes_amz_2026'):
            if isinstance(lyr, QgsVectorLayer) and lyr.isValid():
                return lyr
        return None

    def _on_stats_analyst_changed(self, index=None):
        analyst = self.stats_analyst_combo.currentText() if self.stats_analyst_combo.count() > 0 else 'Todos'
        analyst_filter = None if analyst == 'Todos' else analyst
        self._populate_stats_combos(analyst_filter)
        self._refresh_statistics()

    def _populate_stats_combos(self, analyst_filter=None):
        if self._is_local_geopackage:
            self._populate_stats_combos_local(analyst_filter)
            return
        if not self.user_info:
            return
        config = self.db._get_config(self.biome, self.project_type)
        schema, table = config['schema'], config['table']
        conn = self.db._project_admin_conn(self.biome, self.project_type)
        cur = conn.cursor()
        try:
            biome_sanitized = sanitize_text(self.biome)
            params = [biome_sanitized]
            extra_where = ""
            if analyst_filter and self.is_auditor:
                extra_where = " AND analyst = %s"
                params.append(analyst_filter)

            cur.execute(f"""
                SELECT DISTINCT tile FROM {schema}.{table}
                WHERE biome = %s AND tile IS NOT NULL
                {extra_where}
                ORDER BY tile
            """, params)
            tiles = [row[0] for row in cur.fetchall()]

            cur.execute(f"""
                SELECT DISTINCT ecoregion FROM {schema}.{table}
                WHERE biome = %s AND ecoregion IS NOT NULL
                {extra_where}
                ORDER BY ecoregion
            """, params)
            ecos = [row[0] for row in cur.fetchall()]

            eco_map = self.db.get_ecoregion_display_map(self.biome, self.project_type)

            current_tile = self.stats_tile_combo.currentText()
            current_eco = self.stats_eco_combo.currentData()

            self.stats_tile_combo.blockSignals(True)
            self.stats_tile_combo.clear()
            self.stats_tile_combo.addItem('Todos')
            self.stats_tile_combo.addItems(tiles)
            idx = self.stats_tile_combo.findText(current_tile)
            self.stats_tile_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.stats_tile_combo.blockSignals(False)

            self.stats_eco_combo.blockSignals(True)
            self.stats_eco_combo.clear()
            self.stats_eco_combo.addItem('Todas', None)
            for eco_s in ecos:
                display = eco_map.get(eco_s, eco_s)
                self.stats_eco_combo.addItem(display, userData=eco_s)
            idx = self.stats_eco_combo.findData(current_eco)
            self.stats_eco_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.stats_eco_combo.blockSignals(False)

            self.stats_analyst_combo.blockSignals(True)
            current_analyst = self.stats_analyst_combo.currentText()
            self.stats_analyst_combo.clear()
            self.stats_analyst_combo.addItem('Todos')
            if self.is_auditor:
                cur.execute(f"""
                    SELECT DISTINCT analyst FROM {schema}.{table}
                    WHERE biome = %s AND analyst IS NOT NULL
                    ORDER BY analyst
                """, (biome_sanitized,))
                analysts = [row[0] for row in cur.fetchall()]
                self.stats_analyst_combo.addItems(analysts)
                idx = self.stats_analyst_combo.findText(current_analyst)
                self.stats_analyst_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.stats_analyst_combo.blockSignals(False)
        except Exception as e:
            self._log(f'Erro ao popular combos de totais: {e}')
        finally:
            cur.close()
            conn.close()

    def _populate_stats_combos_local(self, analyst_filter=None):
        layer = self._get_prodes_totals_layer()
        self.session_totals_tabs.setTabVisible(1, layer is not None)
        if layer is None:
            return
        fields = [f.name() for f in layer.fields()]

        current_tile = self.stats_tile_combo.currentText() if self.stats_tile_combo.count() > 0 else 'Todos'
        current_eco = self.stats_eco_combo.currentData() if self.stats_eco_combo.count() > 0 else None
        current_analyst = self.stats_analyst_combo.currentText() if self.stats_analyst_combo.count() > 0 else 'Todos'

        tiles, ecos, analysts = set(), set(), set()
        for feat in layer.getFeatures():
            a = feat['analyst'] if 'analyst' in fields else None
            if a:
                analysts.add(str(a))
            if analyst_filter and str(a) != analyst_filter:
                continue
            if 'tile' in fields:
                t = feat['tile']
                if t:
                    tiles.add(str(t))
            if 'ecoregion' in fields:
                e = feat['ecoregion']
                if e:
                    ecos.add(str(e))

        self.stats_tile_combo.blockSignals(True)
        self.stats_tile_combo.clear()
        self.stats_tile_combo.addItem('Todos')
        self.stats_tile_combo.addItems(sorted(tiles))
        idx = self.stats_tile_combo.findText(current_tile)
        self.stats_tile_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.stats_tile_combo.blockSignals(False)

        self.stats_eco_combo.blockSignals(True)
        self.stats_eco_combo.clear()
        self.stats_eco_combo.addItem('Todas', None)
        for eco_s in sorted(ecos):
            self.stats_eco_combo.addItem(eco_s, userData=eco_s)
        idx = self.stats_eco_combo.findData(current_eco)
        self.stats_eco_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.stats_eco_combo.blockSignals(False)

        self.stats_analyst_combo.blockSignals(True)
        self.stats_analyst_combo.clear()
        self.stats_analyst_combo.addItem('Todos')
        self.stats_analyst_combo.addItems(sorted(analysts))
        idx = self.stats_analyst_combo.findText(current_analyst)
        self.stats_analyst_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.stats_analyst_combo.blockSignals(False)

    def _render_stats_grid(self, counts):
        while self.stats_grid_layout.count():
            item = self.stats_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        color_map = {code: color for code, _, color in self.classes}
        total = 0
        slices = []
        row_i = 0
        for code, count in counts:
            label = self._code_to_label(code)
            color = color_map.get(code, '#888888')
            dot = QLabel('●')
            dot.setFixedWidth(14)
            dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
            name = QLabel(label)
            name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
            name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            num = QLabel(str(count))
            num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            num.setMinimumWidth(30)
            num.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:30px;')
            self.stats_grid_layout.addWidget(dot, row_i, 0)
            self.stats_grid_layout.addWidget(name, row_i, 1)
            self.stats_grid_layout.addWidget(num, row_i, 2)
            total += count
            slices.append((label, count, color))
            row_i += 1

        self.stats_total_big.setText(str(total))
        self.stats_filtered_label.setText(f'Filtrado: {total}')
        if hasattr(self, 'stats_pie_widget'):
            self.stats_pie_widget.set_data(slices)
        if hasattr(self, 'scroll_totais') and self.scroll_totais:
            self.scroll_totais.verticalScrollBar().setValue(0)

    def _refresh_statistics(self):
        if not hasattr(self, 'stats_grid_layout') or self.stats_grid_layout is None:
            return
        if self._is_local_geopackage:
            self._refresh_statistics_local()
            return
        if not self.user_info:
            return

        tile = self.stats_tile_combo.currentText() if self.stats_tile_combo else 'Todos'
        eco = self.stats_eco_combo.currentData() if self.stats_eco_combo else None
        analyst = self.stats_analyst_combo.currentText() if self.stats_analyst_combo else 'Todos'

        if tile == 'Todos':
            tile = None
        if analyst == 'Todos':
            analyst = None
        elif not self.is_auditor:
            analyst = None

        try:
            rows = self.db.get_contagem(
                self.biome, self.project_type,
                username=analyst,
                tile=tile,
                ecoregion=eco,
                all_interpreters=(analyst is None)
            )
        except Exception as e:
            self._log(f'Erro ao consultar totais: {e}')
            return

        self._render_stats_grid(rows)

        if self.is_auditor and not self._is_local_geopackage:
            self._refresh_audit_stats()
            self._populate_audit_filters()

    def _refresh_statistics_local(self):
        layer = self._get_prodes_totals_layer()
        if layer is None:
            return
        fields = [f.name() for f in layer.fields()]

        tile = self.stats_tile_combo.currentText() if self.stats_tile_combo.count() > 0 else 'Todos'
        eco = self.stats_eco_combo.currentData() if self.stats_eco_combo.count() > 0 else None
        analyst = self.stats_analyst_combo.currentText() if self.stats_analyst_combo.count() > 0 else 'Todos'
        tile = None if tile == 'Todos' else tile
        analyst = None if analyst == 'Todos' else analyst

        counts = {}
        for feat in layer.getFeatures():
            if tile is not None and 'tile' in fields and str(feat['tile']) != tile:
                continue
            if eco is not None and 'ecoregion' in fields and str(feat['ecoregion']) != eco:
                continue
            if analyst is not None and 'analyst' in fields and str(feat['analyst']) != analyst:
                continue
            code = feat['label'] if 'label' in fields else None
            if code is None:
                continue
            counts[code] = counts.get(code, 0) + 1

        self._render_stats_grid(list(counts.items()))

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _on_audit_analyst_changed(self, index):
        """Callback quando o combo de analista na aba Auditoria muda."""
        analyst = self.audit_analyst_combo.currentText()
        if analyst == 'Todos':
            analyst = None
        self._populate_audit_filters(analyst)
        self._refresh_audit_stats()

    def _populate_audit_filters(self, analyst_filter=None):
        """Popula os combos de Tile e Ecorregião na aba Auditoria, filtrando por analista se fornecido."""
        if not self.is_auditor or self._is_local_geopackage or not self.biome:
            return

        try:
            config = self.db._get_config(self.biome, self.project_type)
            schema = config['schema']
            table = config['table']
            biome_sanitized = sanitize_text(self.biome)

            conn = self.db._project_admin_conn(self.biome, self.project_type)
            cur = conn.cursor()

            cur.execute(f"""
                SELECT DISTINCT analyst
                FROM {schema}.{table}
                WHERE biome = %s AND label_audit IS NOT NULL AND analyst IS NOT NULL
                ORDER BY analyst
            """, (biome_sanitized,))
            analysts = [row[0] for row in cur.fetchall()]

            params = [biome_sanitized]
            extra_where = ""
            if analyst_filter:
                extra_where = " AND analyst = %s"
                params.append(analyst_filter)

            cur.execute(f"""
                SELECT DISTINCT tile
                FROM {schema}.{table}
                WHERE biome = %s AND label_audit IS NOT NULL AND tile IS NOT NULL
                {extra_where}
                ORDER BY tile
            """, params)
            tiles = [row[0] for row in cur.fetchall()]

            cur.execute(f"""
                SELECT DISTINCT ecoregion
                FROM {schema}.{table}
                WHERE biome = %s AND label_audit IS NOT NULL AND ecoregion IS NOT NULL
                {extra_where}
                ORDER BY ecoregion
            """, params)
            ecos = [row[0] for row in cur.fetchall()]

            cur.close()
            conn.close()

            eco_map = self.db.get_ecoregion_display_map(self.biome, self.project_type)

            current_tile = self.audit_tile_combo.currentText()
            current_eco = self.audit_eco_combo.currentData()

            self.audit_tile_combo.blockSignals(True)
            self.audit_tile_combo.clear()
            self.audit_tile_combo.addItem('Todos')
            self.audit_tile_combo.addItems(tiles)
            idx = self.audit_tile_combo.findText(current_tile)
            if idx >= 0:
                self.audit_tile_combo.setCurrentIndex(idx)
            self.audit_tile_combo.blockSignals(False)

            self.audit_eco_combo.blockSignals(True)
            self.audit_eco_combo.clear()
            self.audit_eco_combo.addItem('Todas', None)
            for eco_s in ecos:
                display = eco_map.get(eco_s, eco_s)
                self.audit_eco_combo.addItem(display, userData=eco_s)
            if current_eco is not None:
                idx = self.audit_eco_combo.findData(current_eco)
                if idx >= 0:
                    self.audit_eco_combo.setCurrentIndex(idx)
            self.audit_eco_combo.blockSignals(False)

            self.audit_analyst_combo.blockSignals(True)
            self.audit_analyst_combo.clear()
            self.audit_analyst_combo.addItem('Todos')
            self.audit_analyst_combo.addItems(analysts)
            if analyst_filter:
                idx = self.audit_analyst_combo.findText(analyst_filter)
                if idx >= 0:
                    self.audit_analyst_combo.setCurrentIndex(idx)
            self.audit_analyst_combo.blockSignals(False)

        except Exception as e:
            self._log(f'Erro ao popular filtros de auditoria: {e}')

    def _refresh_audit_stats(self):
        """Atualiza as estatísticas da aba Auditoria com os filtros atuais, exibindo Concordâncias e Discordâncias em linhas separadas e com espaçamento reduzido."""
        if not self.is_auditor or self._is_local_geopackage or not self.biome:
            return

        analyst = self.audit_analyst_combo.currentText()
        tile = self.audit_tile_combo.currentText()
        eco = self.audit_eco_combo.currentData()

        if analyst == 'Todos':
            analyst = None
        if tile == 'Todos':
            tile = None

        try:
            config = self.db._get_config(self.biome, self.project_type)
            schema = config['schema']
            table = config['table']
            biome_sanitized = sanitize_text(self.biome)

            conditions = ["biome = %s", "label_audit IS NOT NULL"]
            params = [biome_sanitized]

            if analyst:
                conditions.append("analyst = %s")
                params.append(analyst)
            if tile:
                conditions.append("tile = %s")
                params.append(tile)
            if eco is not None:
                conditions.append("ecoregion = %s")
                params.append(eco)

            where_clause = " AND ".join(conditions)

            conn = self.db._project_admin_conn(self.biome, self.project_type)
            cur = conn.cursor()

            cur.execute(f"""
                SELECT
                    COUNT(*) AS total_audited,
                    SUM(CASE WHEN label = label_audit THEN 1 ELSE 0 END) AS agreements,
                    SUM(CASE WHEN label != label_audit THEN 1 ELSE 0 END) AS disagreements
                FROM {schema}.{table}
                WHERE {where_clause}
            """, params)
            row = cur.fetchone()
            cur.close()
            conn.close()

            total_audited = row[0] if row else 0
            agreements = row[1] if row else 0
            disagreements = row[2] if row else 0

            self.audit_total_label.setText(str(total_audited))
            self.audit_filtered_label.setText(f'Auditados: {total_audited}')

            slices = []
            if agreements > 0:
                slices.append(('Concordâncias', agreements, C_OK))
            if disagreements > 0:
                slices.append(('Discordâncias', disagreements, C_DANGER))
            self.audit_pie_widget.set_data(slices)

            while self.audit_grid_layout.count():
                item = self.audit_grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            row_i = 0
            for label, count, color in [
                ('Concordâncias', agreements, C_OK),
                ('Discordâncias', disagreements, C_DANGER)
            ]:
                dot = QLabel('●')
                dot.setFixedWidth(14)
                dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
                name = QLabel(label)
                name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
                if total_audited > 0:
                    pct = (count / total_audited) * 100
                    num_text = f'{count} ({pct:.1f}%)'
                else:
                    num_text = str(count)
                num = QLabel(num_text)
                num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')

                self.audit_grid_layout.addWidget(dot, row_i, 0)
                self.audit_grid_layout.addWidget(name, row_i, 1)
                self.audit_grid_layout.addWidget(num, row_i, 2)
                row_i += 1

            self.audit_grid_layout.setRowStretch(row_i, 1)

            self.audit_grid_widget.updateGeometry()

        except Exception as e:
            self._log(f'Erro ao carregar estatísticas de auditoria com filtros: {e}')

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    def _export_to_gpkg(self):
        if not self._layer_ok(self.layer):
            QMessageBox.warning(self, 'GeoPackage', 'Nenhuma camada de amostras ativa.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Salvar camada como GeoPackage', '',
            'GeoPackage (*.gpkg)'
        )
        if not path:
            return
        if not path.endswith('.gpkg'):
            path += '.gpkg'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        options.fileEncoding = 'UTF-8'
        options.layerName = self.layer.name()
        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            self.layer,
            path,
            QgsCoordinateTransformContext(),
            options
        )
        if error[0] == QgsVectorFileWriter.NoError:
            self._log(f'Camada exportada para {path}')
            QMessageBox.information(self, 'Sucesso', f'GeoPackage salvo em:\n{path}')
        else:
            self._log(f'Erro na exportação: {error}')
            QMessageBox.critical(self, 'Erro', f'Falha ao exportar:\n{error}')

    # ═══════════════════════════════════════════════════════════════
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
        layout.addLayout(wfs_row)

        layout.addWidget(QLabel('Camada de entrada:'))
        entry_row = QHBoxLayout()
        self.entry_combo = QComboBox()
        for l in layers:
            self.entry_combo.addItem(l.name(), l.id())
        if self._layer_ok(self.layer) and self.layer.id() in [l.id() for l in layers]:
            self.entry_combo.setCurrentIndex(self.entry_combo.findData(self.layer.id()))
        entry_row.addWidget(self.entry_combo)
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
            wfs_id = self.wfs_combo.currentData()
            wfs_layer = QgsProject.instance().mapLayer(wfs_id) if wfs_id else None
            if not self._layer_ok(wfs_layer):
                QMessageBox.critical(dlg, 'Erro', 'Selecione uma camada WFS válida.')
                return

            entry_id = self.entry_combo.currentData()
            entry_layer = QgsProject.instance().mapLayer(entry_id) if entry_id else None
            if not self._layer_ok(entry_layer):
                QMessageBox.critical(dlg, 'Erro', 'Selecione uma camada de entrada válida.')
                return

            tile = edit_tile.text().strip()
            if not tile:
                QMessageBox.critical(dlg, 'Erro', 'Informe o tile.')
                return

            dlg.accept()

            if not wfs_layer.dataProvider().capabilities() & QgsVectorDataProvider.EditingCapabilities:
                QMessageBox.critical(self, 'Erro', 'A camada WFS não suporta edição (WFS-T).')
                return

            wfs_layer.reload()

            tile_idx = entry_layer.fields().indexOf('tile')
            if tile_idx == -1:
                QMessageBox.critical(self, 'Erro', 'A camada de entrada não possui campo "tile".')
                return

            entry_feats = [f for f in entry_layer.getFeatures() if str(f.attribute(tile_idx)) == tile]
            if not entry_feats:
                QMessageBox.information(self, 'WFS', f'Nenhuma feição com tile="{tile}" encontrada na entrada.')
                return

            TOLERANCE = 6
            existing_keys = set()
            for f in wfs_layer.getFeatures():
                geom = f.geometry()
                if geom and not geom.isEmpty():
                    centroid = geom.centroid().asPoint()
                    existing_keys.add((round(centroid.x(), TOLERANCE), round(centroid.y(), TOLERANCE)))

            sent_keys = set()
            new_feats = []
            empty_skipped = 0
            duplicate_skipped = 0

            for feat in entry_feats:
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    empty_skipped += 1
                    continue
                centroid = geom.centroid().asPoint()
                key = (round(centroid.x(), TOLERANCE), round(centroid.y(), TOLERANCE))

                if key in existing_keys or key in sent_keys:
                    duplicate_skipped += 1
                    continue

                sent_keys.add(key)

                new_feat = QgsFeature(wfs_layer.fields())
                new_feat.setGeometry(geom)
                for field in wfs_layer.fields():
                    fname = field.name()
                    idx = entry_layer.fields().indexOf(fname)
                    if idx >= 0:
                        val = feat.attribute(idx)
                        if val is not None:
                            new_feat.setAttribute(fname, val)
                new_feats.append(new_feat)

            if not new_feats:
                QMessageBox.information(self, 'WFS', f'{len(new_feats)} feições inseridas.\n{duplicate_skipped} duplicadas ignoradas.\n{empty_skipped} geometrias vazias ignoradas.')
                return

            wfs_layer.startEditing()
            success = wfs_layer.dataProvider().addFeatures(new_feats)
            if success:
                wfs_layer.commitChanges()
                QMessageBox.information(self, 'Sucesso', f'{len(new_feats)} feições inseridas com sucesso.\n{duplicate_skipped} duplicadas ignoradas.\n{empty_skipped} geometrias vazias ignoradas.')
            else:
                wfs_layer.rollBack()
                errors = wfs_layer.dataProvider().errors()
                QMessageBox.critical(self, 'Erro', f'Falha ao adicionar feições:\n{errors}')

        btn_ok.clicked.connect(run_export)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec_()

    def _check_overlap(self, geom, target_biome, target_proj):
        config = self.db._get_config(target_biome, target_proj)
        schema = config['schema']
        table = config['table']
        srid = 4674
        conn = self.db._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                SELECT COUNT(*) FROM {schema}.{table}
                WHERE ST_Intersects(
                    ST_Transform(ST_GeomFromText(%s, %s), 4674),
                    geom
                )
            """, (geom.asWkt(), srid))
            count = cur.fetchone()[0]
            return count > 0
        except Exception as e:
            self._log(f'Erro ao verificar sobreposição: {e}')
            return True
        finally:
            cur.close()
            conn.close()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)

# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
class B_exportar_dados_wfs(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('conexo_wfs', 'Conexão WFS', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('entrada', 'Entrada', defaultValue=None))
        self.addParameter(QgsProcessingParameterString('tile', 'Tile', multiLine=False, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(4, model_feedback)
        results = {}
        outputs = {}

        alg_params = {
            'INPUT': parameters['conexo_wfs'],
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CorrigirGeometrias'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        alg_params = {
            'FIELD': 'tile',
            'INPUT': parameters['entrada'],
            'OPERATOR': 0,
            'VALUE': parameters['tile'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtrairPorAtributo'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['ExtrairPorAtributo']['OUTPUT'],
            'OVERLAY': outputs['CorrigirGeometrias']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Diferenca'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        alg_params = {
            'ACTION_ON_DUPLICATE': 0,
            'SOURCE_FIELD': None,
            'SOURCE_LAYER': outputs['Diferenca']['OUTPUT'],
            'TARGET_FIELD': None,
            'TARGET_LAYER': parameters['conexo_wfs']
        }
        outputs['AppendFeaturesToLayer'] = processing.run('etl_load:appendfeaturestolayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        return results

    def name(self):
        return 'b_exportar_dados_wfs'

    def displayName(self):
        return 'b_exportar_dados_wfs'

    def group(self):
        return 'controle_entrada_saida'

    def groupId(self):
        return 'controle_entrada_saida'

    def createInstance(self):
        return B_exportar_dados_wfs()
