# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

import os
import math
import json
import time
from datetime import datetime, date
from functools import partial

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QDate, QDateTime, Qt, QTimer, QSize, QMetaType, QPointF, QRectF, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QApplication, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QTextEdit, QFrame, QFileDialog,
    QMessageBox, QSizePolicy, QSpacerItem, QScrollArea, QDialog,
    QInputDialog, QLineEdit, QRadioButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView,
    QTabWidget, QListWidget, QListWidgetItem, QAbstractItemView, QSplitter,
    QStackedWidget, QStyle
)
from qgis.PyQt.QtGui import (
    QPixmap, QIcon, QColor, QBrush, QFont, QPalette,
    QPainter, QPen, QPolygonF
)

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature,
    QgsProject, QgsWkbTypes, QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol, QgsMarkerSymbol,
    QgsSingleSymbolRenderer, QgsEditorWidgetSetup,
    QgsGeometry, QgsFeatureRequest, QgsMapLayer, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsExpression, QgsDataSourceUri,
    QgsVectorDataProvider, QgsPointXY, QgsRectangle, QgsSettings, Qgis
)
from qgis.gui import QgsMapTool, QgsRubberBand

from .db_manager import DBManager, sanitize_text
from .db_config  import BIOMAS, CLASSES_POR_BIOMA, API_PROJECTS
try:
    from .db_config import API_ADMINS
except ImportError:
    API_ADMINS = []
from .login_dialog import LoginDialog
from .api_local  import PantanalVSApi, ApiError, geojson_to_wkt, now_iso
from .api_endpoint import (ApiEndpointDialog, ApiEndpointWidget, apply_saved_endpoint,
                           save_endpoint)
from .bdc_images  import (load_tile_images, remove_images, IMAGE_YEARS, LAYER_PROP as IMAGES_PROP,
                          best_aligned_composites, load_tile_composites)
from . import terraclass
from .prodes_masks import (fetch_tile_mask, write_mask, style_mask, add_above_images,
                           remove_masks, MASK_PROP, MASK_VERSION)
from .class_manager_dialog import ClassManagerDialog
from .connect_nav import ConnectNav
from .time_series import TimeSeriesPanel
from .local_store import (
    WorkPackage, py_value, CAMPOS_API,
    LYR_CELULAS, LYR_TILE, LYR_AMOSTRAS, LYR_PONTOS, LYR_MASCARA,
    STATUS_PENDENTE, STATUS_ENVIADA, STATUS_ALTERADA,
    PKG_EM_ANDAMENTO, PKG_FINALIZADO, PKG_LIMPO,
    registry_add, registry_remove, registry_find, registry_latest,
    suggested_filename, default_dir, remember_dir, hash_password,
)

EXCLUIR_CODE = "EXCLUIR"
EXCLUIR_LABEL = "EXCLUIR"
EXCLUIR_COLOR = "#FF0000"

PIXEL_SIZE_M = 10.0

VS_BIOME   = 'Pantanal'
VS_PROJECT = 'Vegetação Secundária'
VS_LAYER_CELLS = 'Grid Ativo Pantanal VS'
VS_LAYER_TILE  = 'Tile Ativo Pantanal VS'
# layer names of the other API projects (short name of the project in the layer list)
VS_LAYER_SIGLA = {('Amazônia', 'Não Floresta'): 'NF'}
VS_LAYER_NAMES = (VS_LAYER_CELLS, VS_LAYER_TILE) + tuple(
    n for sig in VS_LAYER_SIGLA.values() for n in (f'Grid Ativo {sig}', f'Tile Ativo {sig}'))

# projection of the BDC_SM grid (BDC Albers equal-area)
BDC_ALBERS = ('+proj=aea +lat_0=-12 +lon_0=-54 +lat_1=-2 +lat_2=-22 +x_0=5000000 '
              '+y_0=10000000 +ellps=GRS80 +units=m +no_defs')

# drawing modes: radio label and tipo_geom value sent to the API
DRAW_MODES = {'point': 'ponto', 'square': 'quadrado', 'polygon': 'poligono'}
DEFAULT_DRAW_MODES = ('square', 'polygon')     # PostgreSQL projects and local GeoPackage

# main tabs of the dock
TAB_COLETA, TAB_IMAGENS, TAB_SERIE = 0, 1, 2  # Coleta | Connect | Série temporal

def _detect_dark_theme():
    try:
        app = QApplication.instance()
        if app is None:
            return False
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    except Exception:
        return False

_DARK_THEME = _detect_dark_theme()

if _DARK_THEME:
    C_BG      = '#2B2B2B'
    C_SURFACE = '#363636'
    C_BORDER  = '#4A4A4A'
    C_TEXT    = '#E8E8E8'
    C_MUTED   = '#A8A8A8'
    C_HEADER  = '#3A3A3A'   # table/list headers
    C_HOVER   = '#404850'   # light hover background
    C_BORDER_HOVER = '#6B7785'
    C_BTN_HOVER = '#5B6B7A'  # outline buttons on hover
    C_BTN_PRESS = '#4A5866'
    C_DISABLED_BG = '#3A3A3A'
    C_DISABLED_TXT = '#7A7A7A'
    C_SCROLL = '#555555'
else:
    C_BG      = '#FAFBFC'
    C_SURFACE = '#FFFFFF'
    C_BORDER  = '#E8ECF0'
    C_TEXT    = '#2D3142'
    C_MUTED   = '#8A93A2'
    C_HEADER  = '#F5F7FA'
    C_HOVER   = '#F1F5FB'
    C_BORDER_HOVER = '#C5CDD8'
    C_BTN_HOVER = '#2D3142'
    C_BTN_PRESS = '#1A1E2E'
    C_DISABLED_BG = '#E2E8F0'
    C_DISABLED_TXT = '#A0AEC0'
    C_SCROLL = '#D1D9E0'

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
        QPushButton:disabled {{ background: {C_DISABLED_BG}; color: {C_DISABLED_TXT}; }}
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
        background: {C_BTN_HOVER}; color: #FFFFFF;
        border-color: {C_BTN_HOVER};
    }}
    QPushButton:pressed {{
        background: {C_BTN_PRESS}; color: #FFFFFF;
        border-color: {C_BTN_PRESS};
    }}
    QPushButton:disabled {{
        background: {C_DISABLED_BG}; color: {C_DISABLED_TXT}; border-color: {C_BORDER};
    }}
"""

# radio buttons with a clearly visible circle (the default one is too faint on this palette)
_RADIO_CSS = f"""
    QRadioButton {{ background: transparent; border: none; color: {C_TEXT}; spacing: 6px; }}
    QRadioButton::indicator {{
        width: 14px; height: 14px; border-radius: 8px;
        border: 2px solid {C_SLATE}; background: {C_SURFACE};
    }}
    QRadioButton::indicator:hover {{ border-color: {C_STEEL}; }}
    QRadioButton::indicator:checked {{
        border: 2px solid {C_LINK};
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                    stop:0 {C_LINK}, stop:0.5 {C_LINK},
                                    stop:0.6 {C_SURFACE}, stop:1 {C_SURFACE});
    }}
    QRadioButton::indicator:disabled {{ border-color: #CBD5E0; background: #EDF2F7; }}
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

_CELL_BOUNDARY_FILL    = '#D7E1FB'
_CELL_BOUNDARY_BORDER  = '#A9B7E6'

_CELL_STATUS_STYLE = {
    'free':           ('#98A2B3', _CELL_BOUNDARY_FILL),
    'locked':         ('#FF0000', "#FA9393"), 
    'finished':       ('#22A55A', "#96F8B8"),
    'audit_finished': ('#6B7280', '#E4E6EA'),
}
_CELL_SELECTED_FILL    = '#3358EA'
_CELL_SELECTED_BORDER  = '#1D3FA8'
_CELL_GRID_BORDER      = '#4FAE7A'
_CELL_HOVER_BORDER     = '#3358EA'


def _parse_iso_date(value):
    """'YYYY-MM-DD...' -> datetime.date (or None)."""
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date() if value else None
    except ValueError:
        return None


def _sql_str(value):
    """SQL string literal (single quotes doubled) for provider subset filters."""
    return "'" + str(value).replace("'", "''") + "'"


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def _count_row(layout, row, color, text, value, min_width=22):
    """Adds a "● class ...... n" row to a counter grid and returns the number label."""
    dot = QLabel('●')
    dot.setFixedWidth(14)
    dot.setStyleSheet(f'color:{color}; font-size:10pt; padding:0;')
    name = QLabel(text)
    name.setStyleSheet(f'color:{C_TEXT}; font-size:7.5pt;')
    num = QLabel(str(value))
    num.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:{min_width}px;')
    layout.addWidget(dot, row, 0)
    layout.addWidget(name, row, 1)
    layout.addWidget(num, row, 2)
    return name, num


def _total_row(layout, row, value):
    total_label = QLabel('Total')
    total_label.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT};')
    total_num = QLabel(str(value))
    total_num.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    total_num.setStyleSheet(f'font-weight:700; font-size:7.5pt; color:{C_TEXT}; min-width:22px;')
    layout.addWidget(total_label, row, 1)
    layout.addWidget(total_num, row, 2)
    return total_num


def _status_dot_icon(hex_color, size=12):
    """Small round status icon for lists."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(hex_color))
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(px)


def _boundary_points_from_wkt(wkt):
    """Outer ring vertices of a (multi)polygon WKT, for the selection preview."""
    if not wkt:
        return None
    try:
        geom = QgsGeometry.fromWkt(wkt)
    except Exception:
        return None
    if geom is None or geom.isEmpty():
        return None
    try:
        if geom.isMultipart():
            polys = geom.asMultiPolygon()
            if not polys or not polys[0]:
                return None
            ring = polys[0][0]
        else:
            poly = geom.asPolygon()
            if not poly:
                return None
            ring = poly[0]
        return [(pt.x(), pt.y()) for pt in ring]
    except Exception:
        return None



def _event_pos(event):
    """Widget position of a mouse event as QPointF (the cell rects are QRectF, and PyQt6
    does not convert QPoint to QPointF): position() on Qt6, pos() on Qt5."""
    return QPointF(event.position()) if hasattr(event, 'position') else QPointF(event.pos())

class CellGridPreview(QWidget):
    """
    Draws the cell grid of a tile like TerraAmazon's cell selection screen:
    tile outline in the background, one rectangle per cell coloured by status,
    selected cells in blue. Clicking a cell toggles its selection.
    """

    cellToggled = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 220)
        self.setMouseTracking(True)
        self.setStyleSheet(f'background:{C_SURFACE}; border:1px solid {C_BORDER}; border-radius:8px;')
        self._cells = []
        self._selected = set()
        self._boundary = None
        self._world_bbox = None
        self._rects = {}
        self._hover_oid = None
        self._empty_message = 'Selecione um tile para\nver as células'

    def set_data(self, cells, boundary_pts=None, empty_message=None):
        # Draw in the BDC Albers projection of the grid: BDC_SM cells are squares there
        # (in lon/lat they are tilted, more so far from 54°W, e.g. in the Amazon).
        src_crs = QgsCoordinateReferenceSystem('EPSG:4674')
        dst_crs = QgsCoordinateReferenceSystem.fromProj(BDC_ALBERS)
        if not dst_crs.isValid():
            dst_crs = QgsCoordinateReferenceSystem('EPSG:5880')
        transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())

        transformed_cells = []
        for c in cells:
            try:
                # real outline when available; otherwise the lon/lat bounding box corners
                pts = c.get('ring') or [(c['xmin'], c['ymin']), (c['xmax'], c['ymax'])]
                tp = [transform.transform(QgsPointXY(p[0], p[1])) for p in pts]
                xs, ys = [p.x() for p in tp], [p.y() for p in tp]
                transformed_cells.append({
                    'cell_oid': c['cell_oid'],
                    'xmin': min(xs), 'ymin': min(ys),
                    'xmax': max(xs), 'ymax': max(ys),
                    'status': c.get('status', 'free'),
                })
            except Exception:
                transformed_cells.append(c)

        self._cells = transformed_cells or []

        if boundary_pts:
            transformed_boundary = []
            for (x, y) in boundary_pts:
                try:
                    pt = QgsPointXY(x, y)
                    pt_t = transform.transform(pt)
                    transformed_boundary.append((pt_t.x(), pt_t.y()))
                except Exception:
                    transformed_boundary.append((x, y))
            self._boundary = transformed_boundary
        else:
            self._boundary = None

        if empty_message:
            self._empty_message = empty_message

        xs, ys = [], []
        for c in self._cells:
            xs += [c['xmin'], c['xmax']]
            ys += [c['ymin'], c['ymax']]
        if self._boundary:
            xs += [p[0] for p in self._boundary]
            ys += [p[1] for p in self._boundary]
        self._world_bbox = (min(xs), min(ys), max(xs), max(ys)) if xs and ys else None
        self._rects = {}
        self.update()

    def set_selected(self, oids):
        self._selected = set(oids)
        self.update()

    def _transform(self):
        if not self._world_bbox:
            return None
        xmin, ymin, xmax, ymax = self._world_bbox
        w = max(xmax - xmin, 1e-9)
        h = max(ymax - ymin, 1e-9)
        pad = 0.06
        xmin -= w * pad; xmax += w * pad
        ymin -= h * pad; ymax += h * pad
        w = xmax - xmin; h = ymax - ymin
        widget_w = max(self.width() - 8, 10)
        widget_h = max(self.height() - 8, 10)
        scale = min(widget_w / w, widget_h / h)
        draw_w, draw_h = w * scale, h * scale
        off_x = (self.width() - draw_w) / 2.0
        off_y = (self.height() - draw_h) / 2.0
        return scale, xmin, ymin, off_x, off_y

    def _world_to_px(self, x, y, tr):
        scale, xmin, ymin, off_x, off_y = tr
        px = off_x + (x - xmin) * scale
        py = self.height() - (off_y + (y - ymin) * scale)
        return px, py

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(C_SURFACE))

        if not self._cells or not self._world_bbox:
            painter.setPen(QColor(C_MUTED))
            f = painter.font(); f.setPointSizeF(8.5); painter.setFont(f)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_message)
            painter.end()
            return

        tr = self._transform()

        if self._boundary:
            poly = QPolygonF()
            for (x, y) in self._boundary:
                px, py = self._world_to_px(x, y, tr)
                poly.append(QPointF(px, py))
            painter.setPen(QPen(QColor(_CELL_BOUNDARY_BORDER), 1.4))
            painter.setBrush(QBrush(QColor(_CELL_BOUNDARY_FILL)))
            painter.drawPolygon(poly)

        self._rects = {}
        dash_pen = QPen(QColor(_CELL_GRID_BORDER), 1.1, Qt.PenStyle.DashLine)
        sel_pen = QPen(QColor(_CELL_SELECTED_BORDER), 1.6)

        for c in self._cells:
            x0, y0 = self._world_to_px(c['xmin'], c['ymin'], tr)
            x1, y1 = self._world_to_px(c['xmax'], c['ymax'], tr)
            rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            self._rects[c['cell_oid']] = rect

            selected = c['cell_oid'] in self._selected
            if selected:
                painter.setBrush(QBrush(QColor(_CELL_SELECTED_FILL)))
                painter.setPen(sel_pen)
            else:
                _, fill = _CELL_STATUS_STYLE.get(c.get('status', 'free'), _CELL_STATUS_STYLE['free'])
                painter.setBrush(QBrush(QColor(fill)))
                painter.setPen(dash_pen)
            painter.drawRect(rect)

            if c['cell_oid'] == self._hover_oid and not selected:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(_CELL_HOVER_BORDER), 1.4, Qt.PenStyle.DashLine))
                painter.drawRect(rect.adjusted(1, 1, -1, -1))

        painter.end()

    def _cell_at(self, pos):
        for oid, rect in self._rects.items():
            if rect.contains(pos):
                return oid
        return None

    def mousePressEvent(self, event):
        oid = self._cell_at(_event_pos(event))
        if oid:
            self.cellToggled.emit(oid)

    def mouseMoveEvent(self, event):
        oid = self._cell_at(_event_pos(event))
        if oid != self._hover_oid:
            self._hover_oid = oid
            self.setCursor(Qt.CursorShape.PointingHandCursor if oid else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        if self._hover_oid is not None:
            self._hover_oid = None
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()


class PieChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._slices = []

    def set_data(self, slices):
        self._slices = [s for s in slices if s[1] > 0]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
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
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect)
            p.setPen(QColor('#8A93A2'))
            p.setFont(QFont('Segoe UI', 8))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, 'sem dados')
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
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self._reset()
        super().deactivate()

    def _reset(self):
        for rb in self.rubber_bands.values():
            rb.reset(Qgis.GeometryType.Polygon)
        self.rubber_bands = {}
        self.orig_geoms = {}
        self.rotating = False
        self.center = None
        self.start_angle = None
        self.layer = None

    def canvasPressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
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
                'Selecione as feições antes de rotacionar.'
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

        pt = self.toMapCoordinates(event.pixelPoint())
        self.start_angle = math.degrees(math.atan2(pt.y() - self.center.y(), pt.x() - self.center.x()))
        self.rotating = True

        self.rubber_bands = {}
        for fid, g in self.orig_geoms.items():
            rb = QgsRubberBand(self.canvas, Qgis.GeometryType.Polygon)
            rb.setColor(QColor(255, 165, 0, 180))
            rb.setWidth(2)
            rb.setFillColor(QColor(255, 165, 0, 40))
            rb.setToGeometry(g, layer)
            self.rubber_bands[fid] = rb

        self.dock._log('Arraste para rotacionar as feições selecionadas e solte para aplicar.')

    def canvasMoveEvent(self, event):
        if not self.rotating or self.center is None:
            return
        pt = self.toMapCoordinates(event.pixelPoint())
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
        pt = self.toMapCoordinates(event.pixelPoint())
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
        self.pixel_size   = 10
        self.is_admin     = False
        self.max_scale    = 10000
        self._enforcing_scale = False
        self._is_local_geopackage = False
        self._logging_out = False  # guards against re-entrant logout

        self.tile_layer   = None
        self.subregion_layer = None

        self.pantanal_vs_current_tile = None
        self.pantanal_vs_locked_cells = []
        self.pantanal_vs_locked_cell_geoms = []
        self.audit_interpreter = None

        # API projects (Pantanal VS, Amazônia NF): API + SQLite package. The _vs_*
        # methods below serve every API project, not only Pantanal VS.
        self.vs_api = PantanalVSApi()
        self.point_layer = None  # point samples of the package (projects with point mode)
        self.analysis_date = None  # datetime.date chosen before saving the package
        self._vs_conns = []  # (signal, slot) wired on the package layers
        self._vs_restored_workspace = False
        apply_saved_endpoint(self.vs_api)  # last address/key used on this computer
        self._api_confirmed = False  # address just confirmed at login (API-only mode)
        self.work_package = None
        self.pantanal_vs_cell_interpreters = {}
        self._api_samples_cache = None
        self._api_samples_cache_t = 0.0
        self._api_last_error = None
        self._session_pw = None  # (salt, hash) of the login password, memory only
        self._vs_package_to_open = None

        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        self.db = DBManager()
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))

        self.edit_layer = None
        self.rotate_tool = None

        self._build_ui()
        self.canvas.scaleChanged.connect(self._on_scale_changed)

    def _vs_cleanup_terraclass(self):
        """TerraClass layers and their temporary files (and old clips next to the package)."""
        try:
            wp = getattr(self, 'work_package', None)
            terraclass.cleanup(wp.path if wp is not None else None)
        except Exception as e:
            self._log(f'Aviso ao limpar os arquivos do TerraClass: {e}')

    def unload(self):
        self._refresh_timer.stop()
        try:
            remove_images()
        except Exception:
            pass
        self._vs_cleanup_terraclass()
        self.connect_nav.unload()

    @staticmethod
    def _safe_set_enabled(widget, enabled):
        if widget and not sip.isdeleted(widget):
            widget.setEnabled(enabled)

    @staticmethod
    def _layer_ok(layer):
        return layer and not sip.isdeleted(layer)

    def _is_vs_project(self):
        return self.biome == VS_BIOME and self.project_type == VS_PROJECT

    def _api_cfg(self):
        """API_PROJECTS entry of the current biome/project (or None)."""
        return API_PROJECTS.get((self.biome, self.project_type))

    def _vs_layer_names(self):
        """(cells, tile) layer names of the current API project."""
        sig = VS_LAYER_SIGLA.get((self.biome, self.project_type))
        if sig:
            return f'Grid Ativo {sig}', f'Tile Ativo {sig}'
        return VS_LAYER_CELLS, VS_LAYER_TILE

    def _is_api_project(self):
        """Project served by the API + SQLite package (not a local GeoPackage)."""
        return self._api_cfg() is not None and not self._is_local_geopackage

    def _draw_modes(self):
        cfg = self._api_cfg()
        return tuple(cfg['modos']) if cfg and not self._is_local_geopackage else DEFAULT_DRAW_MODES

    def _sample_layers(self):
        """Valid sample layers of the session: polygons/squares and, if any, points."""
        return [lyr for lyr in (self.layer, self.point_layer) if self._layer_ok(lyr)]

    def _api_fields(self):
        """Sample fields sent to/read from the API for the current project."""
        cfg = self._api_cfg() or {}
        return CAMPOS_API + list(cfg.get('campos', ()))

    def _connect_commit_signals(self, layer, connect=True):
        """(Dis)connects the signals that refresh the counters after the layer is saved."""
        if not self._layer_ok(layer):
            return
        for sig in (layer.committedFeaturesAdded, layer.committedFeaturesRemoved,
                    layer.committedAttributeValuesChanges):
            try:
                if connect:
                    sig.connect(self._on_layer_edits_committed)
                else:
                    sig.disconnect(self._on_layer_edits_committed)
            except Exception:
                pass

    def _vs_backend(self):
        return self.vs_api if self._is_api_project() else self.db

    def _request_login(self):
        self._api_confirmed = False
        pg_ok, err = self.db.test_connection()
        if not pg_ok:
            api_ok, api_err = self.vs_api.ping()
            if not api_ok:
                # outside the database network: ask for the online API address
                api_ok = self._vs_ask_api(
                    'API online',
                    'Sem acesso ao banco de dados nesta rede. Informe o endereço da API e sua chave de acesso.')
                self._api_confirmed = api_ok
            if not api_ok:
                self._log(f'Sem conexão: {err}')
                self._log(f'API: {api_err}')
                self._log('Use "Abrir GeoPackage" para trabalhar offline.')
                return
            self._log('PostgreSQL indisponível. Usando a API.')
        else:
            try:
                self.db.bootstrap()
            except Exception as e:
                self._log(f'Aviso: {e}')

        dlg = LoginDialog(self.db, parent=self, api_only=not pg_ok, vs_api=self.vs_api)
        if not dlg.exec():
            return

        self.user_info    = dlg.user_info
        self.biome        = dlg.biome
        self.project_type = dlg.project_type
        self._session_pw  = hash_password(dlg.edit_pass.text())

        if not self.biome or not self.project_type:
            QMessageBox.critical(self, 'Erro', 'Selecione o bioma e o projeto.')
            self._logout()
            return

        self.is_admin     = self.user_info.get('is_admin', False)
        self.is_auditor   = self.user_info.get('is_auditor', False)
        self.audit_mode   = bool(dlg.audit_mode and self.is_auditor)
        self._is_local_geopackage = False
        if self._is_api_project():
            self.max_scale = self._api_max_scale()
        else:
            config = self.db.get_biome_config(self.biome)
            self.max_scale = config['max_scale']
        self._on_session_started()
        if self.user_info:  # the session may have been cancelled
            self._refresh_filtros()

    def _on_session_started(self):
        if not self.biome or not self.project_type:
            QMessageBox.critical(self, 'Erro', 'Selecione o bioma e o projeto.')
            self._logout()
            return

        username = self.user_info['username']
        nome     = self.user_info.get('nome_completo', username)

        self.lbl_user.setText(nome)
        self.lbl_biome_val.setText(f"{self.biome} - {self.project_type}" if self.project_type else self.biome)
        self.btn_session.setText('Sair')
        self.btn_session.setStyleSheet(_pill(C_ROSE))

        self.btn_geopackage.setVisible(False)
        self.btn_open_pacote.setVisible(False)
        # Pantanal VS hides "Atualizar mapa"; "Atualizar mapa"
        # (reload from PostgreSQL) means nothing for any API project
        eh_vs = self._is_vs_project()
        self.btn_ref.setVisible(not eh_vs and not self._is_api_project())
        self.btn_export_gpkg.setVisible(False)
        self.btn_wfs.setVisible(False)

        if not self._is_local_geopackage and username != 'local' and not self._is_api_project():
            self.db.ensure_user_biome(username, self.biome)

        if self._is_local_geopackage or self._is_api_project():
            self.classes = list(CLASSES_POR_BIOMA.get((self.biome, self.project_type), []))
        else:
            self.classes = self.db.get_custom_classes(self.biome, self.project_type, username)

        self.counts = {c[0]: 0 for c in self.classes}
        is_admin = self.user_info.get('is_admin', False) and not self._is_local_geopackage
        self.btn_manage_users.setVisible(is_admin)
        # class list: administrators and auditors, in every project (API or PostgreSQL)
        self.btn_manage_classes.setVisible(
            bool((self.is_admin or self.is_auditor) and not self._is_local_geopackage))

        # API projects: fixed max scale
        cfg = self._api_cfg() if self._is_api_project() else None
        if cfg:
            self.max_scale = self._api_max_scale()
            self.spin_max_scale.setVisible(True)
            self.spin_max_scale.setValue(self.max_scale)
            self.spin_max_scale.setEnabled(is_admin)  # only ADM changes the max mapping scale
            self.lbl_scale.setText('Escala máx.:')
            self.lbl_scale.setMinimumWidth(75)
            self.lbl_scale.setStyleSheet(f'color:{C_TEXT}; font-size:8pt; font-weight:400; background:transparent;')
            self.lbl_suffix.setText(f'(1:{self.max_scale:,})'.replace(',', '.'))
            self.lbl_suffix.setVisible(True)
        else:
            self.spin_max_scale.setVisible(True)
            self.spin_max_scale.setEnabled(is_admin)
            self.lbl_scale.setText('Escala máx.:')
            self.lbl_scale.setMinimumWidth(75)
            self.lbl_scale.setStyleSheet(f'color:{C_TEXT}; font-size:8pt; font-weight:400; background:transparent;')
            self.lbl_suffix.setText('(1:x)')
            self.lbl_suffix.setVisible(True)
            self.spin_max_scale.setValue(self.max_scale)

        self._safe_set_enabled(self.spin, is_admin)

        if not (self.is_auditor and not self._is_local_geopackage):
            self.audit_mode = False

        self._populate_combo()

        self.btn_reclass.setVisible(self.audit_mode)
        if self.audit_mode:
            self._log('Modo auditoria: use a reclassificação.')

        self.grp_grade.setVisible(False)
        self.btn_finish_work.setVisible(False)
        self.btn_save_workspace.setVisible(False)
        self.lbl_pacote.setVisible(False)
        # "Connect" and "Série temporal" tabs: API projects only
        self.connect_nav.set_enabled(self._is_api_project())
        self.main_tabs.setTabEnabled(TAB_IMAGENS, self._is_api_project())
        self.main_tabs.setTabEnabled(TAB_SERIE, self._is_api_project())

        self._apply_draw_modes(self._draw_modes())
        # Pantanal VS no longer uses the window size (polygons only)
        self._set_size_row_visible(not eh_vs or self._is_local_geopackage)

        if self._is_api_project() and self._vs_package_to_open is not None:
            # work package opened from disk: nothing is downloaded from the API
            wp, self._vs_package_to_open = self._vs_package_to_open, None
            self.vs_api.set_project(self._api_cfg())
            self.grp_grade.setVisible(True)
            ok_pkg, err_pkg = self._vs_resume_package(wp)
            if not ok_pkg:
                QMessageBox.critical(self, 'Pacote de Trabalho',
                                     f'Não foi possível abrir o pacote:\n{err_pkg}')
                self._logout()
                return
        elif self._is_api_project():
            # API project: no PostgreSQL/WFS, everything goes through the API + SQLite;
            # the API address is confirmed before selecting cells.
            self.vs_api.set_project(self._api_cfg())
            if not self._vs_prepare_api():
                self._logout()
                return
            self._vs_reload_classes()
            self.grp_grade.setVisible(True)
            self._pantanal_vs_choose_tile()
            # "Cancelar" in the task dialog ends the session: stop here
            # (it used to raise "Bioma/projeto desconhecido: None / None").
            if not self.user_info:
                return

        if self.is_auditor and not self._is_local_geopackage:
            self._populate_audit_filters()

        self._rebuild_counters_grid()

        if not self._is_local_geopackage and not self._is_api_project():
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

        if self._is_api_project():
            # the samples layer (SQLite) was already loaded by _vs_open_work_package
            self._sync_counts(username)
        else:
            self._apply_style()
            self._configure_layer_visibility(is_admin)
            if self._layer_ok(self.layer):
                QgsProject.instance().addMapLayer(self.layer, False)
                QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
            self._sync_counts(username)
            self._connect_commit_signals(self.layer)
        self._refresh_timer.start()
        self._log(f'Sessão iniciada: {nome} · {self.biome} · {self.project_type}')
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
        if self._logging_out:
            return
        self._logging_out = True
        try:
            self._refresh_timer.stop()
            self._connect_commit_signals(self.layer, connect=False)
            self._vs_remove_work_layers()  # sample layers, cells, tile and images
            self.connect_nav.set_enabled(False)
            self.main_tabs.setCurrentIndex(TAB_COLETA)
            self.main_tabs.setTabEnabled(TAB_IMAGENS, False)
            self.main_tabs.setTabEnabled(TAB_SERIE, False)
            self.ts_panel.clear()
            self.analysis_date = None
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
            if self.work_package is not None:
                self._log(f'Pacote mantido em: {self.work_package.path}')
            self.work_package = None
            self.pantanal_vs_cell_interpreters = {}
            self._api_samples_cache = None
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
            self.btn_open_pacote.setVisible(True)
            self._session_pw = None
            self._vs_package_to_open = None
            self.btn_ref.setVisible(False)
            self.btn_wfs.setVisible(False)
            self.btn_export_gpkg.setVisible(False)
            self.btn_reclass.setVisible(False)
            self.btn_manage_users.setVisible(False)
            self.btn_manage_classes.setVisible(False)
            self._apply_draw_modes(DEFAULT_DRAW_MODES)
            self._set_size_row_visible(True)
            self.grp_grade.setVisible(False)
            self.btn_finish_work.setVisible(False)
            self.btn_save_workspace.setVisible(False)
            self.lbl_pacote.setVisible(False)
            self.btn_select_grade.setEnabled(True)
            self.lbl_grade_info.setText('Nenhuma célula selecionada')
            self.session_totals_tabs.setTabVisible(1, False)
            self.session_totals_tabs.setTabVisible(2, False)
        finally:
            self._logging_out = False

    @staticmethod
    def _remove_layers_named(*names):
        project = QgsProject.instance()
        for name in names:
            for lyr in project.mapLayersByName(name):
                project.removeMapLayer(lyr)

    def _sync_counts(self, username):
        if not self._layer_ok(self.layer):
            return
        self.total = 0
        self.counts = {c[0]: 0 for c in self.classes}
        for layer in self._sample_layers():
            layer.dataProvider().reloadData()
            analyst_idx = layer.fields().indexOf('analyst')
            label_idx = layer.fields().indexOf('label')
            for feat in layer.getFeatures():
                if analyst_idx >= 0 and feat[analyst_idx] != username:
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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                self._logout()
        else:
            self._request_login()

    # ═══════════════════════════════════════════════════════════════
    # Online API address (Pantanal VS)
    # ═══════════════════════════════════════════════════════════════
    def _vs_key_owner_ok(self):
        """
        Each user works only with his own access key: the key in use must belong to the
        logged user. Returns (ok, message). Without a key (test API) there is nothing to check.
        """
        client = getattr(self.vs_api, 'client', None)
        user = (self.user_info or {}).get('username')
        if client is None or not client.api_key or not user:
            return True, None
        who = client.whoami()
        if not who:
            return False, 'A API não confirmou o dono da chave de acesso. Atualize a API.'
        if who[0].strip().lower() != user.strip().lower():
            return False, (f'Esta chave de acesso é de "{who[0]}". '
                           'Use a sua própria chave.')
        return True, None

    def _vs_ask_api(self, title, message, parent=None, url=None, ok_text='Conectar'):
        """Asks for (and tests) the API address and key. True if connected."""
        dlg = ApiEndpointDialog(parent or self, title, message,
                                url=url or self.vs_api.client.base_url,
                                btn_style=_BTN_ACT, ok_text=ok_text)
        if not dlg.exec():
            return False
        url, key = dlg.endpoint()
        self.vs_api.set_endpoint(url, key)
        self._api_samples_cache = None
        ok, msg = self._vs_key_owner_ok()
        if not ok:
            QMessageBox.warning(parent or self, title, msg)
            return False
        self._log(f'API conectada: {url}')
        return True

    def _vs_prepare_api(self, parent=None):
        """
        Before cell selection: the user confirms the API address (where cells are
        locked and the package will be sent) and the collections are checked.
        """
        if self._api_confirmed:  # just entered at login
            self._api_confirmed = False
        elif not self._vs_ask_api(
                'API: seleção de células',
                ('Informe o endereço da API. As células são bloqueadas nela e as amostras são enviadas '
                    'para ela ao finalizar.'), parent=parent, ok_text='Conectar e continuar'):
            return False
        try:
            erros, avisos = self.vs_api.diagnose()
        except ApiError as e:
            erros, avisos = [str(e)], []
        for a in avisos:
            self._log(f'Aviso API: {a}')
        if erros:
            for e in erros:
                self._log(f'Erro API: {e}')
            QMessageBox.critical(parent or self, self.project_type or 'Sample Design',
                                 'A API está com problemas de configuração:\n\n• '
                                 + '\n\n• '.join(erros))
            return False
        return True

    def _on_select_grade_clicked(self):
        if self._is_api_project() and not self._vs_prepare_api():
            return
        self._pantanal_vs_choose_tile()

    def _pantanal_vs_choose_tile(self):
        backend = self._vs_backend()
        try:
            tiles = backend.get_pantanal_vs_tiles_with_status()
        except ApiError as e:
            QMessageBox.critical(self, self.project_type or 'Sample Design', f'Erro ao consultar a API:\n{e}')
            return
        if not tiles:
            QMessageBox.warning(self, self.project_type or 'Sample Design', 'Nenhum tile disponível.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle('Check-out')
        icon_path = os.path.join(self._plugin_dir, 'icons', 'sample_design_icon.png')
        if os.path.exists(icon_path):
            dlg.setWindowIcon(QIcon(icon_path))
        dlg.setMinimumWidth(940)
        dlg.setMinimumHeight(620)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {C_BG};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QLabel {{
                color: {C_TEXT};
                font-family: 'Segoe UI', 'Inter', sans-serif;
                background: transparent;
            }}
            QComboBox, QLineEdit {{
                background: {C_SURFACE};
                border: 1.5px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 9pt;
                color: {C_TEXT};
            }}
            QComboBox:hover, QLineEdit:hover {{ border-color: {C_BORDER_HOVER}; }}
            QComboBox:focus, QLineEdit:focus {{ border-color: {C_STEEL}; }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            QSplitter::handle {{
                background: transparent;
                width: 10px;
            }}
            QTableWidget {{
                background: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                gridline-color: {C_BORDER};
                font-size: 9pt;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QHeaderView::section {{
                background: {C_HEADER};
                color: {C_MUTED};
                font-weight: 700;
                font-size: 8pt;
                padding: 8px 10px;
                border: none;
                border-bottom: 1px solid {C_BORDER};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
            }}
            QTableWidget::item:selected {{
                background: {_CELL_SELECTED_FILL};
                color: #FFFFFF;
            }}
        """)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)

        # header text changes with the wizard step
        hdr = QVBoxLayout(); hdr.setSpacing(1)
        lbl_title = QLabel('')
        lbl_title.setStyleSheet(f'font-size:13pt; font-weight:700; color:{C_TEXT}; letter-spacing:-0.2px;')
        lbl_subtitle = QLabel('')
        lbl_subtitle.setStyleSheet(f'font-size:8.3pt; color:{C_MUTED};')
        lbl_subtitle.setWordWrap(True)
        hdr.addWidget(lbl_title)
        hdr.addWidget(lbl_subtitle)
        root.addLayout(hdr)

        sep_hdr = QFrame(); sep_hdr.setFrameShape(QFrame.Shape.HLine); sep_hdr.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        root.addWidget(sep_hdr)

        def set_header(title, subtitle):
            lbl_title.setText(title)
            lbl_subtitle.setText(subtitle)

        stack = QStackedWidget()
        root.addWidget(stack, 1)

        # ════════════════════════════════════════════════════════
        # Page 1 - task composition
        # ════════════════════════════════════════════════════════
        page0 = QWidget()
        p0 = QVBoxLayout(page0)
        p0.setContentsMargins(0, 0, 0, 0)
        p0.setSpacing(10)

        def _field(label_text, value_text):
            col = QVBoxLayout(); col.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f'color:{C_MUTED}; font-size:8pt; font-weight:600;')
            combo = QComboBox()
            combo.setMinimumHeight(32)
            combo.addItem(value_text)
            col.addWidget(lbl)
            col.addWidget(combo)
            return col

        row_fields = QHBoxLayout(); row_fields.setSpacing(16)
        nome_usuario = self.user_info.get('nome_completo') or self.user_info['username']
        row_fields.addLayout(_field('Usuário', nome_usuario))
        row_fields.addLayout(_field('Projeto', self.project_type or ''))
        row_fields.addLayout(_field('Fase', 'Auditoria' if self.audit_mode else 'Interpretação'))
        p0.addLayout(row_fields)

        sep0 = QFrame(); sep0.setFrameShape(QFrame.Shape.HLine); sep0.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        p0.addWidget(sep0)

        row_lbl0 = QHBoxLayout(); row_lbl0.setSpacing(10)
        lbl_tiles = QLabel('Lista de Tiles')
        lbl_tiles.setStyleSheet(f'color:{C_TEXT}; font-size:9.5pt; font-weight:700;')
        row_lbl0.addWidget(lbl_tiles)
        rule0 = QFrame(); rule0.setFrameShape(QFrame.Shape.HLine); rule0.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        row_lbl0.addWidget(rule0, 1)
        lbl_count0 = QLabel('0 tile(s)')
        lbl_count0.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        row_lbl0.addWidget(lbl_count0)
        p0.addLayout(row_lbl0)

        row_filter0 = QHBoxLayout(); row_filter0.setSpacing(8)
        lbl_filter0 = QLabel('Filtrar tile:')
        lbl_filter0.setStyleSheet(f'color:{C_MUTED}; font-size:8.3pt;')
        filter_tile_edit = QLineEdit()
        filter_tile_edit.setPlaceholderText('Código do tile')
        row_filter0.addWidget(lbl_filter0)
        row_filter0.addWidget(filter_tile_edit, 1)
        p0.addLayout(row_filter0)

        tile_table = QTableWidget(0, 9)
        tile_table.setHorizontalHeaderLabels([
            'Scene ID', 'Status', 'Responsável',
            'Início Interp.', 'Fim Interp.',
            'Auditor', 'Status Audit.', 'Início Audit.', 'Fim Audit.'
        ])
        tile_table.verticalHeader().setVisible(False)
        tile_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tile_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tile_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tile_table.horizontalHeader().setStretchLastSection(True)
        tile_table.setAlternatingRowColors(False)
        p0.addWidget(tile_table, 1)

        stack.addWidget(page0)

        # ════════════════════════════════════════════════════════
        # Page 2 - cell selection
        # ════════════════════════════════════════════════════════
        page1 = QWidget()
        p1 = QVBoxLayout(page1)
        p1.setContentsMargins(0, 0, 0, 0)
        p1.setSpacing(8)

        row_lbl1 = QHBoxLayout(); row_lbl1.setSpacing(10)
        lbl_cells = QLabel('Lista de Células')
        lbl_cells.setStyleSheet(f'color:{C_TEXT}; font-size:9.5pt; font-weight:700;')
        row_lbl1.addWidget(lbl_cells)
        rule1 = QFrame(); rule1.setFrameShape(QFrame.Shape.HLine); rule1.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        row_lbl1.addWidget(rule1, 1)
        lbl_count1 = QLabel('0 célula(s)')
        lbl_count1.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        row_lbl1.addWidget(lbl_count1)
        p1.addLayout(row_lbl1)

        row_filter1 = QHBoxLayout(); row_filter1.setSpacing(8)
        lbl_filter1 = QLabel('Filtrar célula:')
        lbl_filter1.setStyleSheet(f'color:{C_MUTED}; font-size:8.3pt;')
        filter_cell_edit = QLineEdit()
        filter_cell_edit.setPlaceholderText('Código da célula')
        row_filter1.addWidget(lbl_filter1)
        row_filter1.addWidget(filter_cell_edit, 1)
        p1.addLayout(row_filter1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        list_header = QLabel('Id')
        list_header.setStyleSheet(f"""
            background: {C_HEADER};
            color: {C_MUTED};
            font-size: 8pt;
            font-weight: 700;
            padding: 7px 12px;
            border: 1px solid {C_BORDER};
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        """)
        left_lay.addWidget(list_header)

        list_widget = QListWidget()
        list_widget.setMinimumWidth(230)
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 4px;
                font-size: 9pt;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 7px 10px;
                border-radius: 6px;
                margin: 1px 0;
                color: {C_TEXT};
            }}
            QListWidget::item:hover {{
                background: {C_HOVER};
            }}
            QListWidget::item:selected {{
                background: {_CELL_SELECTED_FILL};
                color: #FFFFFF;
                font-weight: 600;
            }}
        """)
        left_lay.addWidget(list_widget, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)
        grid_canvas = CellGridPreview()
        right_lay.addWidget(grid_canvas, 1)

        def _legend_entry(color, text):
            row = QHBoxLayout(); row.setSpacing(5)
            sq = QLabel(); sq.setFixedSize(9, 9)
            sq.setStyleSheet(f'background:{color}; border-radius:2px;')
            txt = QLabel(text)
            txt.setStyleSheet(f'color:{C_MUTED}; font-size:7.6pt;')
            row.addWidget(sq)
            row.addWidget(txt)
            return row

        legend = QHBoxLayout(); legend.setSpacing(13)
        for key, label in [('free', 'Livre'), ('locked', 'Bloqueado'),
                            ('finished', 'Finalizado'), ('audit_finished', 'Auditado')]:
            dot_color, _ = _CELL_STATUS_STYLE[key]
            legend.addLayout(_legend_entry(dot_color, label))
        legend.addLayout(_legend_entry(_CELL_SELECTED_FILL, 'Selecionada'))
        legend.addStretch()
        right_lay.addLayout(legend)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 580])
        p1.addWidget(splitter, 1)

        stack.addWidget(page1)

        # footer: same navigation as TerraAmazon
        footer = QHBoxLayout(); footer.setSpacing(8)
        btn_back = QPushButton('< Voltar')
        btn_back.setStyleSheet(_BTN_ACT)
        btn_back.setMinimumHeight(34)
        btn_next = QPushButton('Próximo >')
        btn_next.setStyleSheet(_BTN_ACT)
        btn_next.setMinimumHeight(34)
        btn_cancel = QPushButton('Cancelar')
        btn_cancel.setStyleSheet(_BTN_ACT)
        btn_cancel.setMinimumHeight(34)
        # admin only: free cells locked by other users
        btn_admin_unlock = QPushButton('Desbloquear selecionadas')
        btn_admin_unlock.setStyleSheet(_BTN_ACT)
        btn_admin_unlock.setMinimumHeight(34)
        btn_admin_unlock.setToolTip(('Apaga na API todas as amostras das células selecionadas e deixa as células livres, '
                                    'inclusive as finalizadas. Não pode ser desfeito.'))
        btn_admin_unlock.setVisible(False)
        footer.addWidget(btn_admin_unlock)
        # admin only (testing): free every cell of the tile and delete its samples
        btn_clear_tile = QPushButton('Limpar tile')
        btn_clear_tile.setStyleSheet(_BTN_ACT)
        btn_clear_tile.setMinimumHeight(34)
        btn_clear_tile.setToolTip('Libera todas as células do tile e apaga as amostras dele na API. Não pode ser desfeito.')
        btn_clear_tile.setVisible(False)
        footer.addWidget(btn_clear_tile)
        # auditors (audit mode) and administrators: reopen finished/locked cells to revisit
        # them, keeping every sample
        btn_reopen = QPushButton('Reabrir selecionadas')
        btn_reopen.setStyleSheet(_BTN_ACT)
        btn_reopen.setMinimumHeight(34)
        btn_reopen.setToolTip('Reabre as células selecionadas para revisão. Nenhuma amostra é apagada.')
        btn_reopen.setVisible(False)
        footer.addWidget(btn_reopen)
        btn_reopen_tile = QPushButton('Reabrir tile')
        btn_reopen_tile.setStyleSheet(_BTN_ACT)
        btn_reopen_tile.setMinimumHeight(34)
        btn_reopen_tile.setToolTip('Reabre todas as células do tile para revisão. Nenhuma amostra é apagada.')
        btn_reopen_tile.setVisible(False)
        footer.addWidget(btn_reopen_tile)
        footer.addStretch()
        footer.addWidget(btn_back)
        footer.addWidget(btn_next)
        footer.addWidget(btn_cancel)
        root.addSpacing(4)
        root.addLayout(footer)

        # state / logic
        current_cells = []
        canceled = False

        def get_selected_tile_name():
            row = tile_table.currentRow()
            if row < 0:
                return None
            item = tile_table.item(row, 0)
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def refresh_tile_table(filter_text=''):
            tile_table.setSortingEnabled(False)
            tile_table.setRowCount(0)
            ft = (filter_text or '').strip().lower()
            status_map = {'free': 'Livre', 'locked': 'Bloqueado', 'finished': 'Finalizado'}
            shown = 0
            for t in tiles:
                if ft and ft not in t['tile'].lower():
                    continue
                row = tile_table.rowCount()
                tile_table.insertRow(row)
                item_id = QTableWidgetItem(t['tile'])
                item_id.setData(Qt.ItemDataRole.UserRole, t['tile'])
                item_status = QTableWidgetItem(status_map.get(t.get('status'), '—'))
                item_resp = QTableWidgetItem(t.get('analyst') or '—')
                item_start1 = QTableWidgetItem(t.get('start_date_1') or '—')
                item_end1 = QTableWidgetItem(t.get('end_date_1') or '—')
                item_auditor = QTableWidgetItem(t.get('analyst_2') or '—')
                audit_status = 'Finalizada' if t.get('finished_2') else ('Em andamento' if t.get('analyst_2') else '—')
                item_audit_status = QTableWidgetItem(audit_status)
                item_start2 = QTableWidgetItem(t.get('start_date_2') or '—')
                item_end2 = QTableWidgetItem(t.get('end_date_2') or '—')

                for it in (item_id, item_status, item_resp, item_start1, item_end1,
                           item_auditor, item_audit_status, item_start2, item_end2):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                tile_table.setItem(row, 0, item_id)
                tile_table.setItem(row, 1, item_status)
                tile_table.setItem(row, 2, item_resp)
                tile_table.setItem(row, 3, item_start1)
                tile_table.setItem(row, 4, item_end1)
                tile_table.setItem(row, 5, item_auditor)
                tile_table.setItem(row, 6, item_audit_status)
                tile_table.setItem(row, 7, item_start2)
                tile_table.setItem(row, 8, item_end2)
                shown += 1
            tile_table.setSortingEnabled(True)
            lbl_count0.setText(f'{shown} tile(s)')

        filter_tile_edit.textChanged.connect(refresh_tile_table)
        refresh_tile_table()

        def collect_selected_cells():
            return [it.data(Qt.ItemDataRole.UserRole) for it in list_widget.selectedItems()]

        def apply_cell_filter(text):
            t = (text or '').strip().lower()
            for i in range(list_widget.count()):
                it = list_widget.item(i)
                it.setHidden(bool(t) and t not in it.text().lower())

        filter_cell_edit.textChanged.connect(apply_cell_filter)

        def populate_cells(tile_name):
            nonlocal current_cells
            current_cells = backend.get_grids_for_tile_with_status(tile_name)
            username = self.user_info['username']

            list_widget.blockSignals(True)
            list_widget.clear()

            pre_selected = []
            status_by_oid = {}

            for c in current_cells:
                oid = c['cell_oid']

                if self.audit_mode:
                    if c.get('finished_1') and not c.get('finished_2'):
                        pre_checked = (c.get('analyst_2') == username)
                    else:
                        pre_checked = False
                else:
                    pre_checked = (c.get('analyst_1') == username and not c.get('finished_1'))

                if self.audit_mode:
                    if c.get('finished_2'):
                        status_key, status_text = 'audit_finished', 'Auditoria finalizada'
                    elif c.get('finished_1'):
                        status_key, status_text = 'finished', 'Interpretação finalizada'
                    else:
                        status_key, status_text = 'free', '—'
                else:
                    if c.get('finished_1'):
                        status_key, status_text = 'finished', 'Interpretação finalizada'
                    elif c.get('analyst_1'):
                        status_key, status_text = 'locked', 'Bloqueado'
                    else:
                        status_key, status_text = 'free', 'Livre'

                status_by_oid[oid] = status_key

                responsavel = c.get('analyst_1') if not self.audit_mode else c.get('analyst_2')
                responsavel = responsavel or '—'

                data_val = c.get('start_date_1') if not self.audit_mode else c.get('start_date_2')
                if isinstance(data_val, (datetime, date)):
                    data_val = data_val.strftime('%Y-%m-%d')
                elif data_val is None:
                    data_val = '—'

                item = QListWidgetItem(oid)
                item.setData(Qt.ItemDataRole.UserRole, oid)
                if status_key != 'free':
                    dot_color, _ = _CELL_STATUS_STYLE[status_key]
                    item.setIcon(_status_dot_icon(dot_color))
                tip = f'Status: {status_text}\nResponsável: {responsavel}\nInício: {data_val}'
                if c.get('area_nf_km2') is not None:
                    tip += f'\nÁrea de Não Floresta: {c["area_nf_km2"]:.1f} km²'
                item.setToolTip(tip)
                list_widget.addItem(item)
                item.setSelected(pre_checked)

                if pre_checked:
                    pre_selected.append(oid)

            list_widget.blockSignals(False)

            bounds = backend.get_cell_bounds_for_tile(tile_name)
            canvas_cells = []
            for b in bounds:
                oid = b['cell_oid']
                canvas_cells.append({
                    'cell_oid': oid,
                    'xmin': b['xmin'], 'ymin': b['ymin'],
                    'xmax': b['xmax'], 'ymax': b['ymax'], 'ring': b.get('ring'),
                    'status': status_by_oid.get(oid, 'free'),
                })
            boundary_pts = _boundary_points_from_wkt(backend.get_tile_boundary(tile_name))
            empty_msg = None
            if current_cells and not canvas_cells:
                empty_msg = 'Pré-visualização indisponível\npara este tile.'
            grid_canvas.set_data(canvas_cells, boundary_pts, empty_message=empty_msg)
            grid_canvas.set_selected(pre_selected)

            lbl_count1.setText(f'{len(current_cells)} célula(s)')
            filter_cell_edit.clear()
            apply_cell_filter('')

        def sync_canvas_selection():
            grid_canvas.set_selected(collect_selected_cells())

        list_widget.itemSelectionChanged.connect(sync_canvas_selection)

        def on_canvas_cell_toggled(oid):
            for i in range(list_widget.count()):
                it = list_widget.item(i)
                if it.data(Qt.ItemDataRole.UserRole) == oid:
                    it.setSelected(not it.isSelected())
                    list_widget.scrollToItem(it)
                    break

        grid_canvas.cellToggled.connect(on_canvas_cell_toggled)

        admin_can_unlock = bool(self.is_admin and self._is_api_project()
                                and hasattr(backend, 'reset_cell'))
        can_clear_tile = bool(self.is_admin and self._is_api_project()
                              and hasattr(backend, 'reset_tile_cells'))

        can_reopen = bool((self.audit_mode or self.is_admin) and self._is_api_project()
                          and hasattr(backend, 'reopen_cell'))

        def update_nav_state():
            idx = stack.currentIndex()
            btn_reopen.setVisible(can_reopen and idx == 1)
            btn_reopen_tile.setVisible(can_reopen and idx == 0)
            btn_reopen_tile.setEnabled(get_selected_tile_name() is not None)
            btn_back.setEnabled(idx > 0)
            btn_admin_unlock.setVisible(admin_can_unlock and idx == 1)
            btn_clear_tile.setVisible(can_clear_tile and idx == 0)
            btn_clear_tile.setEnabled(get_selected_tile_name() is not None)
            if idx == 0:
                btn_next.setEnabled(get_selected_tile_name() is not None)
            else:
                btn_next.setEnabled(True)

        tile_table.itemSelectionChanged.connect(update_nav_state)

        def lock_selected_cells_and_finish():
            tile_name = self.pantanal_vs_current_tile
            if not tile_name:
                return
            username = self.user_info['username']
            selected = collect_selected_cells()
            if not selected:
                QMessageBox.warning(dlg, 'Atenção', 'Selecione pelo menos uma célula.')
                return

            pacote = (None, False, None)
            if self._is_api_project():
                fase = 'auditoria' if self.audit_mode else 'interpretacao'
                pacote = self._vs_choose_package(tile_name, fase, dlg)
                if not pacote[0]:
                    return  # no saved package, no lock

            interpreters = {}
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
                    ok, msg = backend.lock_cell_for_audit(oid, username)
                    if not ok:
                        QMessageBox.critical(dlg, 'Erro', f'{oid}: {msg}')
                        return
                    backend.fill_audit_for_cell(oid, username, interpreter)
                    interpreters[oid] = interpreter
                self.pantanal_vs_locked_cells = selected
                geoms = [QgsGeometry.fromWkt(backend.get_cell_geom(oid)) for oid in selected]
                self.pantanal_vs_locked_cell_geoms = geoms
                self.audit_interpreter = interpreter
                self.lbl_grade_info.setText(f'Tile: {tile_name}  |  Células: {", ".join(selected)} (auditoria)')
            else:
                for oid in selected:
                    ok, msg = backend.lock_cell(oid, username)
                    if not ok:
                        QMessageBox.critical(dlg, 'Erro', f'{oid}: {msg}')
                        return
                self.pantanal_vs_locked_cells = selected
                geoms = [QgsGeometry.fromWkt(backend.get_cell_geom(oid)) for oid in selected]
                self.pantanal_vs_locked_cell_geoms = geoms
                self.audit_interpreter = None
                self.lbl_grade_info.setText(f'Tile: {tile_name}  |  Células: {", ".join(selected)}')
            self.pantanal_vs_cell_interpreters = interpreters

            if self._is_api_project():
                # create/resume the SQLite package and load cells, tile and samples
                ok_pkg, err_pkg = self._vs_open_work_package(tile_name, selected,
                                                             pacote[0], pacote[1], pacote[2])
                if not ok_pkg:
                    QMessageBox.critical(dlg, 'Pacote SQLite',
                                         f'Não foi possível preparar o pacote local:\n{err_pkg}')
                    return
            self.btn_finish_work.setVisible(True)
            self.btn_select_grade.setEnabled(False)
            if self._is_api_project():
                self._vs_zoom_to_tile()
            else:
                self.canvas.zoomScale(self.max_scale)
                self._add_grid_boundary_layer(tile_name, selected)
            dlg.accept()
            self._log(f'Células bloqueadas: {selected}')

        def go_next():
            idx = stack.currentIndex()
            if idx == 0:
                tile_name = get_selected_tile_name()
                if not tile_name:
                    QMessageBox.warning(dlg, 'Atenção', 'Selecione um tile.')
                    return
                self.pantanal_vs_current_tile = tile_name
                try:
                    populate_cells(tile_name)
                except ApiError as e:
                    QMessageBox.critical(dlg, 'Erro', f'Erro ao consultar a API:\n{e}')
                    return
                set_header('Seleção de células',
                           'Selecione pelo menos uma célula.')
                stack.setCurrentIndex(1)
                update_nav_state()
            else:
                try:
                    lock_selected_cells_and_finish()
                except ApiError as e:
                    QMessageBox.critical(dlg, 'Erro', f'Erro na API:\n{e}')

        def admin_unlock_selected():
            """Admin only: resets the selected cells (samples and locks)."""
            tile_name = self.pantanal_vs_current_tile
            selecionadas = collect_selected_cells()
            if not selecionadas:
                QMessageBox.warning(dlg, 'Desbloquear células', 'Selecione pelo menos uma célula.')
                return
            if self._vs_clear_cells(selecionadas, dlg):
                try:
                    populate_cells(tile_name)
                except ApiError as e:
                    QMessageBox.warning(dlg, 'Desbloquear células', str(e))

        btn_admin_unlock.clicked.connect(admin_unlock_selected)

        def clear_selected_tile():
            tile_name = get_selected_tile_name()
            if not tile_name:
                QMessageBox.warning(dlg, 'Limpar tile', 'Selecione um tile.')
                return
            if self._vs_clear_tile(tile_name, dlg):
                try:
                    tiles[:] = backend.get_pantanal_vs_tiles_with_status()
                except ApiError as e:
                    QMessageBox.warning(dlg, 'Limpar tile', str(e))
                refresh_tile_table(filter_tile_edit.text())
                update_nav_state()

        btn_clear_tile.clicked.connect(clear_selected_tile)

        def reopen_cells(oids, title):
            """Reopens the cells (no sample deleted); True if anything changed."""
            if QMessageBox.question(
                    dlg, title,
                    (f'Reabrir {len(oids)} célula(s)?\n\n'
                    '• auditorias finalizadas voltam para auditoria\n'
                    '• bloqueios em andamento são liberados\n'
                    '• nenhuma amostra é apagada'),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return False
            linhas, mudou = [], False
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                for oid in oids:
                    ok, msg = backend.reopen_cell(oid)
                    mudou = mudou or ok
                    linhas.append(f'• {oid}: {msg}')
            finally:
                QApplication.restoreOverrideCursor()
            self._api_samples_cache = None
            self._log(f'[{self.user_info["username"]}] reabrir células: ' + '; '.join(linhas))
            QMessageBox.information(dlg, title, '\n'.join(linhas[:20]))
            return mudou

        def reopen_selected():
            tile_name = self.pantanal_vs_current_tile
            selecionadas = collect_selected_cells()
            if not selecionadas:
                QMessageBox.warning(dlg, 'Reabrir células', 'Selecione pelo menos uma célula.')
                return
            if reopen_cells(selecionadas, 'Reabrir células'):
                try:
                    populate_cells(tile_name)
                except ApiError as e:
                    QMessageBox.warning(dlg, 'Reabrir células', str(e))

        btn_reopen.clicked.connect(reopen_selected)

        def reopen_tile():
            tile_name = get_selected_tile_name()
            if not tile_name:
                QMessageBox.warning(dlg, 'Reabrir tile', 'Selecione um tile.')
                return
            try:
                oids = sorted({c['cell_oid'] for c in backend.get_grids_for_tile_with_status(tile_name)
                               if c.get('finished_2') or c.get('analyst_2')
                               or (c.get('analyst_1') and not c.get('finished_1'))})
            except ApiError as e:
                QMessageBox.warning(dlg, 'Reabrir tile', str(e))
                return
            if not oids:
                QMessageBox.information(dlg, 'Reabrir tile',
                                        f'O tile {tile_name} não tem células para reabrir.')
                return
            if reopen_cells(oids, 'Reabrir tile'):
                try:
                    tiles[:] = backend.get_pantanal_vs_tiles_with_status()
                except ApiError as e:
                    QMessageBox.warning(dlg, 'Reabrir tile', str(e))
                refresh_tile_table(filter_tile_edit.text())
                update_nav_state()

        btn_reopen_tile.clicked.connect(reopen_tile)

        def go_back():
            set_header('Composição de Tarefa',
                       'Escolha o tile e as células da tarefa.')
            stack.setCurrentIndex(0)
            update_nav_state()

        btn_next.clicked.connect(go_next)
        btn_back.clicked.connect(go_back)

        # "Cancelar" ends the session
        def on_cancel():
            nonlocal canceled
            canceled = True
            dlg.reject()

        btn_cancel.clicked.connect(on_cancel)

        set_header('Composição de Tarefa',
                   'Escolha o tile e as células da tarefa.')
        stack.setCurrentIndex(0)
        update_nav_state()

        if not dlg.exec() and canceled:
            self._logout()
            self._log('Seleção de tile cancelada. Sessão encerrada.')
        elif not self.pantanal_vs_locked_cells:
            # closed without a selection (e.g. the X button): keep the session
            self._log('Seleção de tile cancelada.')

    # ═══════════════════════════════════════════════════════════════
    # Pantanal Secondary Vegetation - API + SQLite work package
    # ═══════════════════════════════════════════════════════════════
    def _vs_to_4674(self, geom):
        """Drawn geometry (map CRS) to EPSG:4674."""
        src = self.canvas.mapSettings().destinationCrs()
        dst = QgsCoordinateReferenceSystem('EPSG:4674')
        g = QgsGeometry(geom)
        if src.isValid() and src != dst:
            g.transform(QgsCoordinateTransform(src, dst, QgsProject.instance()))
        return g

    def _vs_cell_of(self, geom):
        for oid, cg in zip(self.pantanal_vs_locked_cells, self.pantanal_vs_locked_cell_geoms):
            if cg is not None and cg.intersects(geom):
                return oid
        return None

    def _vs_control_attrs(self, geom):
        return {
            'cell_oid': self._vs_cell_of(geom),
            'sync_status': STATUS_PENDENTE,
            'created_at': QDateTime.currentDateTime(),
        }

    def _vs_sample_attrs(self, geom, code, area, px, username, mode=None):
        year = datetime.now().year
        mode = mode or self.get_draw_mode()
        attrs = {
            'label': code, 'analyst': username,
            'biome': sanitize_text(self.biome) if self.biome else '',
            'date': QDate.currentDate(), 'prodes': f'{year-1}-{year}',
            'area_m2': area, 'px_size': int(PIXEL_SIZE_M),
            'window_px': px if mode == 'square' else None,  # the window size only means something for squares
            'tipo_geom': DRAW_MODES.get(mode),
        }
        if self.analysis_date:
            attrs['data_ref'] = QDate(self.analysis_date.year, self.analysis_date.month,
                                      self.analysis_date.day)
        tile, eco = self._local_intersect(geom)
        if tile:
            attrs['tile'] = tile
        if eco:
            attrs['ecoregion'] = eco
        if self.audit_mode:
            attrs['audit'] = username
        attrs.update(self._vs_control_attrs(geom))
        return attrs

    def _vs_load_images(self, tile):
        """
        BDC Sentinel-2 images (R11 G08 B04) of July 28, 2026/2025/2024 for the task
        tile, one subgroup per year, read over HTTP (in-memory VRT). A failure here
        does not block the work.
        """
        if not tile:
            return
        cfg = self._api_cfg() or {}
        if cfg.get('imagens') == 'mes_menor_nuvem':
            return self._vs_load_month_images(tile, cfg)
        if cfg.get('imagens') == 'data_analise' and self.analysis_date:
            d = self.analysis_date
            years, ref = (d.year, d.year - 1, d.year - 2), (d.month, d.day)
        else:
            years, ref = IMAGE_YEARS, (7, 28)
        anos = ', '.join(str(y) for y in years)
        self._log(f'Carregando imagens BDC do tile {tile} ({ref[1]:02d}/{ref[0]:02d} de {anos})...')
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            _group, subgroups = load_tile_images(tile, log=self._log, years=years, ref=ref)
            com_imagem = [g for g in subgroups if g.findLayers()]
            self.connect_nav.set_groups(com_imagem, show_first=True)
            if not com_imagem:
                self._log('Nenhuma imagem do BDC pôde ser carregada para este tile.')
        except Exception as e:
            self._log(f'Aviso: não foi possível carregar as imagens do BDC ({e}).')
        finally:
            QApplication.restoreOverrideCursor()

    def _vs_load_month_images(self, tile, cfg):
        """
        PRODES protocol: composites of the month in each image year, all in the same
        16-day slot (close dates) with the lowest total cloud cover. The most recent
        composite becomes the reference date (series and data_ref).
        """
        years, month = tuple(cfg['anos_imagens']), cfg.get('mes_imagens', 7)
        self._log(f'Carregando imagens BDC do tile {tile}: julho de '
                  f'{", ".join(str(y) for y in years)}, menor cobertura de nuvem...')
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            picks = best_aligned_composites(tile, years, month)
            _group, subgroups = load_tile_composites(tile, picks, log=self._log, month=month)
            com_imagem = [g for g in subgroups if g.findLayers()]
            self.connect_nav.set_groups(com_imagem, show_first=True)
            ref = picks.get(years[0])
            if ref:
                self._set_analysis_date(_parse_iso_date(ref['date']))
                if self.work_package is not None:
                    self.work_package.set_meta({
                        'data_analise': ref['date'],
                        'imagens': json.dumps({str(y): (c['date'], round(c['cloud'], 2)) if c else None
                                               for y, c in picks.items()})})
            if not com_imagem:
                self._log('Nenhuma imagem do BDC pôde ser carregada para este tile.')
        except Exception as e:
            self._log(f'Aviso: não foi possível carregar as imagens do BDC ({e}).')
        finally:
            QApplication.restoreOverrideCursor()

    def _vs_load_mask(self, wp, restored=False):
        """
        Reference layers of the tile (NF: non-forest suppression up to 2000 in yellow and
        non-forest hydrography in blue), outlines only, right above the images. Downloaded
        once (API or TerraBrasilis) and kept in the package; afterwards read from it.
        """
        cfg = (self._api_cfg() or {}).get('mascara')
        if not cfg or wp is None:
            return
        try:
            if not wp.has_layer(LYR_MASCARA):
                wp.ensure_schema(mask=True)
            lyr = self._package_layer(wp, LYR_MASCARA) if restored else None
            novo = lyr is None
            if novo:
                lyr = wp.open_layer(LYR_MASCARA, 'Máscaras de referência')
            if lyr is None:
                self._log('Falha ao abrir a camada de máscara do pacote.')
                return
            if (str(wp.get_meta('mascara_ano') or '') != str(cfg['ano'])
                    or str(wp.get_meta('mascara_versao') or '') != str(MASK_VERSION)):
                tile_geom = None
                if self._layer_ok(self.tile_layer):
                    first = next(self.tile_layer.getFeatures(), None)
                    tile_geom = QgsGeometry(first.geometry()) if first is not None else None
                if tile_geom is None or tile_geom.isEmpty():
                    self._log('Máscara não carregada: o pacote não tem o contorno do tile.')
                    return
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    feats = fetch_tile_mask(tile_geom, cfg['ano'], cfg['camadas'], log=self._log,
                                            client=self.vs_api.client)
                    n = write_mask(lyr, feats)
                finally:
                    QApplication.restoreOverrideCursor()
                wp.set_meta({'mascara_ano': cfg['ano'], 'mascara_versao': MASK_VERSION,
                             'mascara_em': now_iso()})
                self._log(f'Máscaras de referência gravadas no pacote: {n} polígono(s).')
            lyr.setName('Máscaras de referência')
            style_mask(lyr, cfg.get('cores') or {o: '#FFFF00' for _s, o, _y in cfg['camadas']})
            if novo:
                add_above_images(lyr, IMAGES_PROP)
            else:
                lyr.setCustomProperty(MASK_PROP, '1')
        except Exception as e:
            self._log(f'Aviso: não foi possível carregar as máscaras de referência ({e}).')

    def _vs_remove_images(self):
        """Removes the images and their in-memory VRTs."""
        try:
            remove_images()
        except Exception as e:
            self._log(f'Aviso ao remover imagens: {e}')
        self.connect_nav.clear()

    def _vs_load_terraclass(self, wp):
        """
        TerraClass years of the project (NF: 2024 and 2022) clipped to the tile, in a
        "TerraClass" group above the images (unchecked). Downloaded once next to the package.
        """
        years = (self._api_cfg() or {}).get('terraclass')
        if not years or wp is None:
            return
        try:
            project = QgsProject.instance()
            # layers restored with the workspace count only if their file still exists (the
            # clips live in a temporary folder deleted when QGIS or the package closes)
            loaded = {lyr.customProperty(terraclass.TC_PROP) for lyr in project.mapLayers().values()
                      if lyr.customProperty(terraclass.TC_PROP) is not None and lyr.isValid()
                      and os.path.exists(lyr.source())}
            if all(str(y) in loaded for y in years) and loaded <= {str(y) for y in years}:
                return   # restored with the workspace (and no year that left the config)
            terraclass.remove_layers()
            tile_geom = None
            if self._layer_ok(self.tile_layer):
                first = next(self.tile_layer.getFeatures(), None)
                tile_geom = QgsGeometry(first.geometry()) if first is not None else None
            if tile_geom is None or tile_geom.isEmpty():
                self._log('TerraClass não carregado: o pacote não tem o contorno do tile.')
                return
            layers = []
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                for year in years:
                    path = terraclass.tile_file(wp.path, year)
                    if not os.path.exists(path):
                        try:
                            terraclass.download_tile(year, tile_geom.asWkt(), path, log=self._log)
                        except Exception as e:
                            self._log(f'Aviso: TerraClass {year} não pôde ser baixado ({e}).')
                            continue
                    lyr = terraclass.raster_layer(path, year)
                    if lyr is not None:
                        layers.append(lyr)
            finally:
                QApplication.restoreOverrideCursor()
            if layers:
                terraclass.add_layers(layers, IMAGES_PROP)
                self._log(f'TerraClass {", ".join(l.name()[-4:] for l in layers)} carregado (desmarcado).')
        except Exception as e:
            self._log(f'Aviso: não foi possível carregar o TerraClass ({e}).')

    def _vs_remove_work_layers(self):
        self._vs_remove_images()
        remove_masks()
        self._vs_cleanup_terraclass()
        self._remove_layers_named(*VS_LAYER_NAMES)
        self._vs_disconnect_layers()
        for lyr in self._sample_layers():
            QgsProject.instance().removeMapLayer(lyr)
        self.layer = None
        self.layer_id = None
        self.point_layer = None
        self.tile_layer = None
        self.subregion_layer = None

    def _vs_connect_layers(self):
        """Wires counters, deletion log and change flags on every package sample layer."""
        self._vs_disconnect_layers()
        for lyr in self._sample_layers():
            before = partial(self._vs_before_commit, lyr)
            for sig, slot in ((lyr.committedFeaturesAdded, self._on_layer_edits_committed),
                              (lyr.committedFeaturesRemoved, self._on_layer_edits_committed),
                              (lyr.committedAttributeValuesChanges, self._on_layer_edits_committed),
                              (lyr.beforeCommitChanges, before),
                              (lyr.committedAttributeValuesChanges, self._vs_on_attr_committed),
                              (lyr.committedGeometriesChanges, self._vs_on_geom_committed)):
                sig.connect(slot)
                self._vs_conns.append((sig, slot))

    def _vs_disconnect_layers(self):
        for sig, slot in self._vs_conns:
            try:
                sig.disconnect(slot)
            except Exception:
                pass
        self._vs_conns = []

    def _vs_choose_package(self, tile_name, fase, parent=None):
        """
        Asks where to save the task package, suggesting the package in progress for
        this task if there is one. The reference dates come from the project protocol
        (images), so date is always None. Returns (path, existed, date) or (None, False, None).
        """
        parent = parent or self
        username = self.user_info['username']
        existente = registry_find(username, tile_name, fase)
        sugestao = existente or os.path.join(default_dir(),
                                             suggested_filename(username, tile_name, fase))

        dlg = QDialog(parent)
        dlg.setWindowTitle('Pacote SQLite da tarefa')
        dlg.setMinimumWidth(620)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        ttl = QLabel('Onde salvar o pacote desta tarefa?')
        ttl.setStyleSheet(f'font-size:11pt; font-weight:700; color:{C_TEXT};')
        lay.addWidget(ttl)
        txt = QLabel(
            (f'Tile {tile_name} · {"Auditoria" if fase == "auditoria" else "Interpretação"}\n\n'
             'O trabalho fica salvo neste arquivo (.gpkg) enquanto você coleta. As amostras '
             'são enviadas à API a partir dele, e ele serve para continuar o trabalho depois.'))
        txt.setWordWrap(True)
        txt.setStyleSheet(f'color:{C_MUTED}; font-size:8.5pt;')
        lay.addWidget(txt)
        row = QHBoxLayout()
        edit = QLineEdit(sugestao)
        edit.setObjectName('edit_pacote')
        edit.setMinimumHeight(32)
        btn_browse = QPushButton('Procurar...')
        btn_browse.setStyleSheet(_BTN_ACT)
        row.addWidget(edit, 1)
        row.addWidget(btn_browse)
        lay.addLayout(row)
        info = QLabel('')
        info.setWordWrap(True)
        info.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        lay.addWidget(info)
        foot = QHBoxLayout()
        foot.addStretch()
        btn_ok = QPushButton('Salvar e continuar')
        btn_ok.setStyleSheet(_BTN_ACT)
        btn_cancel = QPushButton('Cancelar')
        btn_cancel.setStyleSheet(_BTN_ACT)
        foot.addWidget(btn_ok)
        foot.addWidget(btn_cancel)
        lay.addLayout(foot)

        def atualizar_info():
            p = edit.text().strip()
            if p and os.path.exists(p) and WorkPackage(p).matches(username, tile_name, fase) \
                    and WorkPackage(p).get_meta('status', PKG_EM_ANDAMENTO) == PKG_EM_ANDAMENTO:
                info.setText('Pacote em andamento desta tarefa: o trabalho será retomado.')
            elif p and os.path.exists(p):
                info.setText('Já existe um arquivo com este nome. Ele será substituído.')
            else:
                info.setText('Será criado um pacote novo.')

        def procurar():
            atual = edit.text().strip() or sugestao
            caminho, _ = QFileDialog.getSaveFileName(
                dlg, 'Salvar pacote SQLite', atual, 'Pacote SQLite (GeoPackage) (*.gpkg)',
                options=QFileDialog.Option.DontConfirmOverwrite)
            if caminho:
                if not caminho.lower().endswith('.gpkg'):
                    caminho += '.gpkg'
                edit.setText(caminho)

        resultado = {'path': None, 'existed': False, 'data': None}

        def confirmar():
            p = edit.text().strip()
            if not p:
                QMessageBox.warning(dlg, 'Pacote SQLite', 'Informe onde salvar o arquivo.')
                return
            if not p.lower().endswith('.gpkg'):
                p += '.gpkg'
            p = os.path.abspath(p)
            pasta = os.path.dirname(p)
            if not os.path.isdir(pasta):
                QMessageBox.warning(dlg, 'Pacote SQLite', f'A pasta não existe:\n{pasta}')
                return
            if not os.access(pasta, os.W_OK):
                QMessageBox.warning(dlg, 'Pacote SQLite', f'Sem permissão de gravação em:\n{pasta}')
                return
            existed = False
            if os.path.exists(p):
                wp = WorkPackage(p)
                if (wp.matches(username, tile_name, fase)
                        and wp.get_meta('status', PKG_EM_ANDAMENTO) == PKG_EM_ANDAMENTO):
                    existed = True
                else:
                    if QMessageBox.question(
                            dlg, 'Pacote SQLite',
                            f'O arquivo já existe:\n{p}\n\nSubstituir?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                        return
                    try:
                        os.remove(p)
                    except OSError as e:
                        QMessageBox.warning(dlg, 'Pacote SQLite',
                                            f'Não foi possível substituir o arquivo (está aberto em '
                                            f'outro programa?):\n{e}')
                        return
            resultado['path'], resultado['existed'] = p, existed
            dlg.accept()

        edit.textChanged.connect(atualizar_info)
        btn_browse.clicked.connect(procurar)
        btn_ok.clicked.connect(confirmar)
        btn_cancel.clicked.connect(dlg.reject)
        atualizar_info()
        if not dlg.exec() or not resultado['path']:
            self._log('Pacote não salvo. As células não foram bloqueadas.')
            return None, False, None
        remember_dir(resultado['path'])
        return resultado['path'], resultado['existed'], resultado['data']

    def _vs_open_work_package(self, tile_name, cell_ids, path, existed=False, analysis_date=None):
        """
        Creates (or resumes) the task package at the chosen path and loads the
        cells, tile and samples layers.
        """
        username = self.user_info['username']
        fase = 'auditoria' if self.audit_mode else 'interpretacao'
        try:
            wp = WorkPackage(path)
            meta = {
                'versao_plugin': '0.71',
                'api_url': self.vs_api.client.base_url,
                'username': username,
                'nome_completo': self.user_info.get('nome_completo') or username,
                'bioma': self.biome, 'projeto': self.project_type,
                'fase': fase, 'tile': tile_name,
                'classes': json.dumps(self.classes, ensure_ascii=False),
            }
            if analysis_date:
                meta['data_analise'] = analysis_date.isoformat()
                self._set_analysis_date(analysis_date)
            if self.audit_mode:
                meta['interpretes'] = json.dumps(self.pantanal_vs_cell_interpreters)
            if not existed and self._session_pw:
                meta['senha_salt'], meta['senha_hash'] = self._session_pw
            wp.ensure_schema(meta, points='point' in self._draw_modes(),
                             mask=bool((self._api_cfg() or {}).get('mascara')))
            cells = [(oid, g.asWkt()) for oid, g in
                     zip(cell_ids, self.pantanal_vs_locked_cell_geoms) if g is not None]
            wp.upsert_cells(cells, tile_name, fase, username)
            wp.set_tile(tile_name, self.vs_api.get_tile_boundary(tile_name))
            registry_add(path, username, tile_name, fase)
        except Exception as e:
            return False, str(e)
        return self._vs_attach_package(wp, cell_ids, existed, import_server=True)

    def _vs_attach_package(self, wp, cell_ids, existed, import_server=True):
        """Adds the package cells, tile and samples layers to the project."""
        ok_key, msg_key = self._vs_key_owner_ok()
        if not ok_key:
            return False, msg_key
        username = self.user_info['username']
        restored = existed and self._vs_offer_workspace(wp)
        if not restored:
            self._vs_remove_work_layers()
        self.work_package = wp
        ids = ', '.join(_sql_str(c) for c in cell_ids)

        # cells layer (same name and style as 0.69); reused when the workspace was restored
        lyr_cells = self._package_layer(wp, LYR_CELULAS) if restored else None
        if lyr_cells is not None:
            lyr_cells.setSubsetString(f'"cell_oid" IN ({ids})')
            lyr_cells.setName(self._vs_layer_names()[0])   # workspaces saved with older names
        else:
            lyr_cells = wp.open_layer(LYR_CELULAS, self._vs_layer_names()[0])
            if lyr_cells is not None:
                lyr_cells.setSubsetString(f'"cell_oid" IN ({ids})')
                lyr_cells.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
                    'color': '0,0,0,0', 'outline_color': '0,255,0',
                    'outline_width': '0.8', 'style': 'no'})))
                QgsProject.instance().addMapLayer(lyr_cells)
                self._log('Camada de células adicionada.')
            else:
                self._log('Falha ao carregar camada de células.')

        # tile layer (same name and style as 0.69)
        lyr_tile = self._package_layer(wp, LYR_TILE) if restored else None
        if lyr_tile is not None:
            lyr_tile.setName(self._vs_layer_names()[1])
        else:
            lyr_tile = wp.open_layer(LYR_TILE, self._vs_layer_names()[1])
            if lyr_tile is not None:
                lyr_tile.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
                    'color': '0,0,0,0', 'outline_color': '255,0,0',
                    'outline_width': '0.8', 'style': 'no'})))
                QgsProject.instance().addMapLayer(lyr_tile)
                self._log('Camada do tile adicionada.')
            else:
                self._log('Falha ao carregar camada do tile.')
        self.tile_layer = lyr_tile

        nome = f'{self.project_type} {self.biome} [{username}]'
        lyr_am = self._package_layer(wp, LYR_AMOSTRAS) if restored else None
        novo_am = lyr_am is None
        if novo_am:
            lyr_am = wp.open_layer(LYR_AMOSTRAS, nome)
        if lyr_am is None:
            return False, 'Camada de amostras inválida no pacote.'
        self.layer = lyr_am
        self.layer_id = lyr_am.id()

        self.point_layer = None
        if 'point' in self._draw_modes():
            if not wp.has_layer(LYR_PONTOS):
                wp.ensure_schema(points=True)  # package created before points existed
            lyr_pt = self._package_layer(wp, LYR_PONTOS) if restored else None
            novo_pt = lyr_pt is None
            if novo_pt:
                lyr_pt = wp.open_layer(LYR_PONTOS, f'Pontos {self.project_type} [{username}]')
            if lyr_pt is not None:
                self.point_layer = lyr_pt
                if novo_pt:
                    QgsProject.instance().addMapLayer(lyr_pt, False)
                    QgsProject.instance().layerTreeRoot().insertLayer(0, lyr_pt)

        self._apply_style()
        self._configure_layer_visibility(self.is_admin and not self._is_local_geopackage)
        if novo_am:
            QgsProject.instance().addMapLayer(lyr_am, False)
            QgsProject.instance().layerTreeRoot().insertLayer(0, lyr_am)
        try:
            self.iface.setActiveLayer(self.point_layer if self.get_draw_mode() == 'point'
                                     and self.point_layer else lyr_am)
        except Exception:
            pass
        self._vs_connect_layers()
        # every layer of the task is in SIRGAS 2000 (EPSG:4674): the map too, so the masks,
        # cells and samples are drawn without reprojection
        try:
            QgsProject.instance().setCrs(QgsCoordinateReferenceSystem('EPSG:4674'))
        except Exception:
            pass

        if import_server:
            try:
                n = self._vs_import_server_samples()
                if n:
                    self._log(f'{n} amostra(s) da API carregada(s) no pacote.')
            except ApiError as e:
                self._log(f'Aviso: não foi possível baixar amostras da API ({e}).')

        self._vs_load_images(self.pantanal_vs_current_tile)
        self._vs_load_mask(wp, restored)
        self._vs_load_terraclass(wp)
        self._vs_restored_workspace = restored

        self._log(('Pacote SQLite retomado: ' if existed else 'Pacote SQLite salvo em: ') + wp.path)
        self.lbl_pacote.setVisible(True)
        self.btn_save_workspace.setVisible(True)
        self._vs_update_pacote_label()
        self._sync_counts(username)
        self._refresh_filtros()
        return True, None

    def _vs_open_package_dialog(self):
        """
        Resumes work saved in a SQLite package, as in TerraAmazon. Downloads
        nothing and works without PostgreSQL/API (upload can happen later).
        """
        dlg = QDialog(self)
        dlg.setWindowTitle('Conexão com o Pacote de Trabalho')
        dlg.setMinimumWidth(480)
        icon_path = os.path.join(self._plugin_dir, 'icons', 'sample_design_icon.png')
        if os.path.exists(icon_path):
            dlg.setWindowIcon(QIcon(icon_path))
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        cab = QFrame()
        cab.setStyleSheet(f'QFrame {{ background:{C_SURFACE}; border:1px solid {C_BORDER}; }}')
        hc = QHBoxLayout(cab)
        hc.setContentsMargins(12, 12, 12, 12)
        ttl = QLabel('Conectar a um Pacote de Trabalho')
        ttl.setStyleSheet(f'font-size:11pt; font-weight:700; color:{C_TEXT}; border:none;')
        hc.addWidget(ttl, 1)
        if os.path.exists(icon_path):
            ico = QLabel()
            ico.setPixmap(QPixmap(icon_path).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
            ico.setStyleSheet('border:none;')
            hc.addWidget(ico)
        lay.addWidget(cab)

        g1 = QGroupBox('Informações sobre o Pacote de Trabalho')
        l1 = QHBoxLayout(g1)
        btn_dots = QPushButton('...')
        btn_dots.setFixedWidth(30)
        edit_path = QLineEdit(registry_latest() or '')
        edit_path.setObjectName('edit_pacote_abrir')
        l1.addWidget(btn_dots)
        l1.addWidget(edit_path, 1)
        lay.addWidget(g1)

        g2 = QGroupBox('Informações do Usuário')
        l2 = QGridLayout(g2)
        edit_user = QLineEdit()
        edit_user.setObjectName('edit_usuario_pacote')
        edit_pass = QLineEdit()
        edit_pass.setObjectName('edit_senha_pacote')
        edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        l2.addWidget(QLabel('Usuário:'), 0, 0, Qt.AlignmentFlag.AlignRight)
        l2.addWidget(edit_user, 0, 1)
        l2.addWidget(QLabel('Senha:'), 1, 0, Qt.AlignmentFlag.AlignRight)
        l2.addWidget(edit_pass, 1, 1)
        lay.addWidget(g2)

        def preencher_usuario():
            p = edit_path.text().strip()
            if p and os.path.exists(p) and not edit_user.text().strip():
                edit_user.setText(WorkPackage(p).get_meta('username', '') or '')

        def escolher():
            ini = edit_path.text().strip() or default_dir()
            caminho, _ = QFileDialog.getOpenFileName(
                dlg, 'Abrir Pacote de Trabalho', ini,
                'Pacote de Trabalho (*.gpkg *.sqlite);;Todos os arquivos (*.*)')
            if caminho:
                edit_path.setText(caminho)
                preencher_usuario()

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet(f'color:{C_BORDER};')
        lay.addWidget(sep)
        foot = QHBoxLayout()
        foot.addStretch()
        btn_ok = QPushButton('Conectar')
        btn_cancel = QPushButton('Cancelar')
        foot.addWidget(btn_ok)
        foot.addWidget(btn_cancel)
        lay.addLayout(foot)
        resultado = {}

        def conectar():
            p = edit_path.text().strip()
            user = edit_user.text().strip()
            pwd = edit_pass.text()
            if not p or not os.path.exists(p):
                QMessageBox.warning(dlg, 'Pacote de Trabalho', 'Escolha o arquivo do pacote.')
                return
            wp = WorkPackage(p)
            meta = wp.get_all_meta()
            if not meta.get('schema_version'):
                QMessageBox.warning(dlg, 'Pacote de Trabalho',
                                    'Este arquivo não é um Pacote de Trabalho do Sample Design.')
                return
            if (meta.get('bioma'), meta.get('projeto')) not in API_PROJECTS:
                QMessageBox.warning(dlg, 'Pacote de Trabalho',
                                    'Este pacote não é de um projeto da API.')
                return
            status = meta.get('status', PKG_EM_ANDAMENTO)
            if status != PKG_EM_ANDAMENTO:
                QMessageBox.warning(dlg, 'Pacote de Trabalho',
                                    f'Este pacote está "{status}" e não pode mais ser aberto '
                                    'para trabalho.')
                return
            if not user:
                QMessageBox.warning(dlg, 'Pacote de Trabalho', 'Informe o usuário.')
                return
            if user != meta.get('username'):
                QMessageBox.warning(dlg, 'Pacote de Trabalho',
                                    f'Este pacote pertence ao usuário "{meta.get("username")}".')
                return
            if meta.get('senha_hash'):
                if hash_password(pwd, meta.get('senha_salt'))[1] != meta.get('senha_hash'):
                    QMessageBox.warning(dlg, 'Pacote de Trabalho', 'Senha incorreta.')
                    return
                pw = (meta.get('senha_salt'), meta.get('senha_hash'))
            else:
                # package without a stored password: check against PostgreSQL when available
                pg_ok, _ = self.db.test_connection()
                if pg_ok:
                    ok_auth, res = self.db.authenticate(user, pwd)
                    if not ok_auth:
                        QMessageBox.warning(dlg, 'Pacote de Trabalho', f'✗  {res}')
                        return
                pw = hash_password(pwd)
            resultado['info'] = {
                'username': user, 'nome_completo': meta.get('nome_completo') or user,
                'is_admin': user in API_ADMINS,
                'is_auditor': meta.get('fase') == 'auditoria', 'auth_local': True,
            }
            resultado['wp'], resultado['meta'], resultado['pw'] = wp, meta, pw
            dlg.accept()

        btn_dots.clicked.connect(escolher)
        edit_path.editingFinished.connect(preencher_usuario)
        btn_ok.clicked.connect(conectar)
        btn_cancel.clicked.connect(dlg.reject)
        preencher_usuario()
        if not dlg.exec() or 'wp' not in resultado:
            return

        meta = resultado['meta']
        self.user_info = resultado['info']
        self._session_pw = resultado['pw']
        self.biome, self.project_type = meta.get('bioma'), meta.get('projeto')
        self.is_admin = self.user_info['is_admin']
        self.is_auditor = self.user_info['is_auditor']
        self.audit_mode = meta.get('fase') == 'auditoria'
        self._is_local_geopackage = False
        self.max_scale = self._api_max_scale()
        self._vs_package_to_open = resultado['wp']
        self._on_session_started()
        if self.user_info:
            self._refresh_filtros()

    def _vs_resume_package(self, wp):
        """Resumes the task stored in the package, without the API."""
        meta = wp.get_all_meta()
        tile = meta.get('tile')
        cells = wp.locked_cells()
        if not cells:
            return False, 'O pacote não tem células em andamento.'
        self.pantanal_vs_current_tile = tile
        self.pantanal_vs_locked_cells = [oid for oid, _ in cells]
        self.pantanal_vs_locked_cell_geoms = [QgsGeometry.fromWkt(w) for _, w in cells]
        try:
            self.pantanal_vs_cell_interpreters = json.loads(meta.get('interpretes') or '{}')
        except ValueError:
            self.pantanal_vs_cell_interpreters = {}
        interpretes = [v for v in self.pantanal_vs_cell_interpreters.values() if v]
        self.audit_interpreter = interpretes[0] if interpretes else None
        self._set_analysis_date(_parse_iso_date(meta.get('data_analise')))
        self._vs_reload_classes(meta, quiet=True)
        sufixo = ' (auditoria)' if self.audit_mode else ''
        self.lbl_grade_info.setText(
            f'Tile: {tile}  |  Células: {", ".join(self.pantanal_vs_locked_cells)}{sufixo}')
        ok, err = self._vs_attach_package(wp, self.pantanal_vs_locked_cells, True,
                                          import_server=False)
        if not ok:
            return False, err
        registry_add(wp.path, self.user_info['username'], tile, meta.get('fase'))
        self.btn_finish_work.setVisible(True)
        self.btn_select_grade.setEnabled(False)
        if not getattr(self, '_vs_restored_workspace', False):
            self._vs_zoom_to_tile()
        self._log(f'Pacote aberto: {wp.path}')
        return True, None

    def _vs_zoom_to_tile(self):
        """Zooms the map to the whole task tile (falls back to the locked cells)."""
        project = QgsProject.instance()
        candidates = [self.tile_layer] + project.mapLayersByName(self._vs_layer_names()[0])
        for lyr in candidates:
            if not self._layer_ok(lyr) or not lyr.isValid():
                continue
            lyr.updateExtents()
            extent = lyr.extent()
            if extent.isNull() or extent.isEmpty():
                continue
            ext = self.canvas.mapSettings().layerExtentToOutputExtent(lyr, extent)
            ext.scale(1.05)                     # small margin around the outline
            self.canvas.setExtent(ext)
            self.canvas.refresh()
            return
        self.canvas.zoomScale(self.max_scale)

    def _vs_import_server_samples(self):
        """Downloads the API samples that already exist in the task cells."""
        if not self._layer_ok(self.layer) or self.work_package is None:
            return 0
        username = self.user_info['username']
        known = set()
        for lyr in self._sample_layers():
            known |= self.work_package.known_api_fids(lyr)
        novos_por_camada = {}
        if self.audit_mode:
            analysts = sorted({a for a in self.pantanal_vs_cell_interpreters.values() if a})
        else:
            analysts = [username]
        for analyst in analysts:
            for f in self.vs_api.list_samples({'analyst': analyst}, with_geometry=True):
                try:
                    fid = int(f.get('id'))
                except (TypeError, ValueError):
                    continue
                if fid in known:
                    continue
                wkt = geojson_to_wkt(f.get('geometry'))
                if not wkt:
                    continue
                g = QgsGeometry.fromWkt(wkt)
                cell = self._vs_cell_of(g)
                if cell is None:
                    continue
                layer = self._layer_for_geometry(g)
                if layer is None:
                    continue
                p = f.get('properties') or {}
                feat = QgsFeature(layer.fields())
                feat.setGeometry(g)
                for k in self._api_fields():
                    if layer.fields().indexOf(k) < 0:
                        continue
                    v = p.get(k)
                    if k in ('date', 'data_ref') and v:
                        v = QDate.fromString(str(v)[:10], 'yyyy-MM-dd')
                    feat.setAttribute(k, v)
                status = STATUS_ENVIADA
                if self.audit_mode and not p.get('audit'):
                    feat.setAttribute('audit', username)  # same as fill_audit_for_cell
                    status = STATUS_ALTERADA
                feat.setAttribute('api_fid', fid)
                feat.setAttribute('cell_oid', cell)
                feat.setAttribute('sync_status', status)
                feat.setAttribute('sent_at', QDateTime.currentDateTime())
                novos_por_camada.setdefault(layer.id(), (layer, []))[1].append(feat)
                known.add(fid)
        total = 0
        for layer, novos in novos_por_camada.values():
            layer.dataProvider().addFeatures(novos)
            layer.updateExtents()
            layer.triggerRepaint()
            total += len(novos)
        return total

    def _vs_flag_altered_in_changes(self, layer, changes):
        i_status = layer.fields().indexOf('sync_status')
        if i_status < 0:
            return
        for fid in list(changes.keys()):
            f = layer.getFeature(fid)
            if f.isValid() and py_value(f['api_fid']) is not None:
                changes[fid][i_status] = STATUS_ALTERADA

    def _vs_register_delete(self, layer, fids):
        if self.work_package is None:
            return
        for fid in fids:
            f = layer.getFeature(fid)
            if f.isValid():
                api_fid = py_value(f['api_fid'])
                if api_fid is not None:
                    self.work_package.add_pending_delete(api_fid)

    def _vs_before_commit(self, layer, *args):
        """Records the api_fid of samples deleted with the QGIS editor."""
        if not self._layer_ok(layer) or self.work_package is None:
            return
        buf = layer.editBuffer()
        if buf is None:
            return
        ids = list(buf.deletedFeatureIds())
        if not ids:
            return
        req = QgsFeatureRequest().setFilterFids(ids)
        for f in layer.dataProvider().getFeatures(req):
            api_fid = py_value(f['api_fid'])
            if api_fid is not None:
                self.work_package.add_pending_delete(api_fid)

    def _vs_on_attr_committed(self, layer_id, changes):
        self._vs_mark_altered(QgsProject.instance().mapLayer(layer_id), list(changes.keys()))

    def _vs_on_geom_committed(self, layer_id, changes):
        self._vs_mark_altered(QgsProject.instance().mapLayer(layer_id), list(changes.keys()))

    def _vs_mark_altered(self, layer, fids):
        if not self._layer_ok(layer) or not fids:
            return
        i_status = layer.fields().indexOf('sync_status')
        if i_status < 0:
            return
        upd = {}
        for f in layer.getFeatures(QgsFeatureRequest().setFilterFids(fids)):
            if py_value(f['api_fid']) is not None and py_value(f['sync_status']) != STATUS_ALTERADA:
                upd[f.id()] = {i_status: STATUS_ALTERADA}
        if upd:
            layer.dataProvider().changeAttributeValues(upd)
        self._vs_update_pacote_label()

    def _vs_feature_payload(self, f, defaults):
        g = QgsGeometry(f.geometry())
        if g.isMultipart():
            parts = g.asGeometryCollection()
            if len(parts) == 1:
                g = parts[0]
        props = {}
        for k in self._api_fields():
            if f.fields().indexOf(k) >= 0:
                props[k] = py_value(f[k])
        for k, v in defaults.items():
            if props.get(k) in (None, ''):
                props[k] = v
        return {'type': 'Feature', 'geometry': json.loads(g.asJson()), 'properties': props}

    def _vs_push(self, tipo='parcial'):
        """
        Uploads the package to the API: pending deletions, then new samples (POST),
        then changed samples (PUT).
        """
        wp = self.work_package
        if not self._layer_ok(self.layer) or wp is None:
            return False, 'Nenhum pacote de trabalho aberto.'
        for layer in self._sample_layers():
            if layer.isEditable() and layer.isModified():
                ans = QMessageBox.question(
                    self, 'Sample Design',
                    f'A camada "{layer.name()}" tem edições não salvas.\n'
                    'Salvar as edições antes de enviar?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if ans != QMessageBox.StandardButton.Yes or not layer.commitChanges(False):
                    return False, 'Envio cancelado: salve ou descarte as edições da camada.'

        username = self.user_info['username']
        defaults = {
            'analyst': username,
            'biome': sanitize_text(self.biome) if self.biome else None,
            'date': QDate.currentDate().toString('yyyy-MM-dd'),
            'tile': self.pantanal_vs_current_tile,
        }
        if 'data_ref' in self._api_fields() and self.analysis_date:
            defaults['data_ref'] = self.analysis_date.isoformat()
        enviadas = atualizadas = excluidas = 0
        erros = []
        offline = False

        for api_fid in wp.pending_deletes():
            try:
                self.vs_api.delete_sample(api_fid)
                wp.clear_pending_delete(api_fid)
                excluidas += 1
            except ApiError as e:
                erros.append(str(e))
                offline = 'indisponível' in str(e)
                break

        for layer in ([] if offline else self._sample_layers()):
            stop = self._vs_push_layer(layer, defaults, erros)
            enviadas += stop[0]
            atualizadas += stop[1]
            if stop[2]:
                break

        msg = (f'{enviadas} amostra(s) enviada(s), {atualizadas} atualizada(s), '
               f'{excluidas} exclusão(ões).')
        if erros:
            msg += f'\n{len(erros)} erro(s): ' + erros[0]
        try:
            wp.log_envio(tipo, enviadas, atualizadas, excluidas, len(erros), msg)
            wp.set_meta({'ultimo_envio': now_iso()})
        except Exception:
            pass
        self._api_samples_cache = None
        self._vs_update_pacote_label()
        return (not erros), msg

    def _vs_push_layer(self, layer, defaults, erros):
        """POST/PUT the pending samples of one layer. Returns (sent, updated, api_offline)."""
        enviadas = atualizadas = 0
        offline = False
        fields = layer.fields()
        i_api, i_status, i_sent = (fields.indexOf('api_fid'), fields.indexOf('sync_status'),
                                   fields.indexOf('sent_at'))
        fill_idx = {k: fields.indexOf(k) for k in defaults}
        updates = {}
        for f in layer.getFeatures():
            api_fid = py_value(f['api_fid'])
            status = py_value(f['sync_status'])
            if api_fid is not None and status != STATUS_ALTERADA:
                continue
            payload = self._vs_feature_payload(f, defaults)
            ch = {}
            for k, idx in fill_idx.items():
                if idx >= 0 and py_value(f[k]) in (None, '') and payload['properties'].get(k):
                    v = payload['properties'][k]
                    ch[idx] = QDate.fromString(v, 'yyyy-MM-dd') if k in ('date', 'data_ref') else v
            try:
                if api_fid is None:
                    new_id = self.vs_api.create_sample(payload)
                    ch[i_api] = int(new_id)
                    enviadas += 1
                else:
                    self.vs_api.update_sample(int(api_fid), payload)
                    atualizadas += 1
                ch[i_status] = STATUS_ENVIADA
                ch[i_sent] = QDateTime.currentDateTime()
                updates[f.id()] = ch
            except ApiError as e:
                erros.append(str(e))
                if 'indisponível' in str(e):
                    offline = True
                    break
        if updates:
            layer.dataProvider().changeAttributeValues(updates)
            layer.triggerRepaint()
        return enviadas, atualizadas, offline

    def _vs_check_password(self, username, password):
        """Checks user/password against the package hash, the session or PostgreSQL."""
        if username != self.user_info.get('username'):
            return False, f'O trabalho em andamento é do usuário "{self.user_info.get("username")}".'
        ref = None
        if self.work_package is not None:
            m = self.work_package.get_all_meta()
            if m.get('senha_hash'):
                ref = (m.get('senha_salt'), m.get('senha_hash'))
        ref = ref or self._session_pw
        if ref and ref[0] and ref[1]:
            if hash_password(password, ref[0])[1] == ref[1]:
                return True, None
            return False, 'Senha incorreta.'
        pg_ok, _ = self.db.test_connection()
        if pg_ok:
            ok, res = self.db.authenticate(username, password)
            return (True, None) if ok else (False, str(res))
        return False, 'Não foi possível conferir a senha.'

    def _vs_confirm_finish(self):
        """
        Finish dialog: asks for the target API and the user's credentials again.
        Returns (url, key) when confirmed, otherwise None.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle('Finalizar trabalho')
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        ttl = QLabel('Finalizar o trabalho e liberar as células?')
        ttl.setStyleSheet(f'font-size:11pt; font-weight:700; color:{C_TEXT};')
        lay.addWidget(ttl)
        n_cel = len(self.pantanal_vs_locked_cells)
        txt = QLabel((f'Tile {self.pantanal_vs_current_tile} · {n_cel} célula(s)\n\n'
             'As amostras do pacote vão para a API abaixo e as células serão liberadas. '
             'Confira o endereço e digite usuário e senha para confirmar.'))
        txt.setWordWrap(True)
        txt.setStyleSheet(f'color:{C_MUTED}; font-size:8.5pt;')
        lay.addWidget(txt)

        # target API: the one where the cells were locked (stored in the package)
        url_pacote = None
        if self.work_package is not None:
            try:
                url_pacote = self.work_package.get_meta('api_url')
            except Exception:
                url_pacote = None
        g_api = QGroupBox('API de destino')
        l_api = QVBoxLayout(g_api)
        api_widget = ApiEndpointWidget(g_api, url=url_pacote or self.vs_api.client.base_url,
                                       btn_style=_BTN_ACT)
        l_api.addWidget(api_widget)
        lay.addWidget(g_api)

        # compact confirmation row: user and password side by side
        row_user = QHBoxLayout()
        row_user.setSpacing(6)
        edit_user = QLineEdit()
        edit_user.setObjectName('edit_usuario_finalizar')
        edit_user.setPlaceholderText('usuário')
        edit_pass = QLineEdit()
        edit_pass.setObjectName('edit_senha_finalizar')
        edit_pass.setPlaceholderText('senha')
        edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        for e in (edit_user, edit_pass):
            e.setFixedHeight(26)
            e.setStyleSheet(f'QLineEdit {{ background:{C_SURFACE}; border:1px solid {C_BORDER}; '
                            f'border-radius:5px; padding:2px 8px; font-size:8.5pt; }}'
                            f'QLineEdit:focus {{ border-color:{C_STEEL}; }}')
        lbl_conf = QLabel('Confirme:')
        lbl_conf.setStyleSheet(f'color:{C_MUTED}; font-size:8pt; font-weight:600;')
        row_user.addWidget(lbl_conf)
        row_user.addWidget(edit_user, 1)
        row_user.addWidget(edit_pass, 1)
        lay.addLayout(row_user)
        foot = QHBoxLayout()
        foot.addStretch()
        btn_ok = QPushButton('Finalizar e enviar')
        btn_ok.setStyleSheet(_BTN_ACT)
        btn_cancel = QPushButton('Cancelar')
        btn_cancel.setStyleSheet(_BTN_ACT)
        foot.addWidget(btn_ok)
        foot.addWidget(btn_cancel)
        lay.addLayout(foot)

        def confirmar():
            user = edit_user.text().strip()
            if not user:
                QMessageBox.warning(dlg, 'Finalizar trabalho', 'Informe o usuário.')
                return
            ok, msg = self._vs_check_password(user, edit_pass.text())
            if not ok:
                QMessageBox.warning(dlg, 'Finalizar trabalho', msg)
                edit_pass.clear()
                return
            ok, msg = api_widget.test()
            if not ok:
                QMessageBox.warning(dlg, 'Finalizar trabalho',
                                    f'Não foi possível conectar à API:\n{msg}\n\nNada foi enviado. O trabalho continua salvo no pacote.')
                return
            url, key = api_widget.endpoint()
            if url_pacote and url.rstrip('/') != str(url_pacote).rstrip('/'):
                if QMessageBox.question(
                        dlg, 'Finalizar trabalho',
                        (f'As células foram bloqueadas em:\n{url_pacote}\n\nmas o envio vai para:\n{url}\n\n'
                    'Só continue se for o mesmo servidor. Continuar?'),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
            save_endpoint(url, key, api_widget.remember())
            resultado['endpoint'] = (url, key)
            dlg.accept()

        resultado = {}
        btn_ok.clicked.connect(confirmar)
        btn_cancel.clicked.connect(dlg.reject)
        edit_pass.returnPressed.connect(confirmar)
        if not dlg.exec():
            return None
        return resultado.get('endpoint')

    def _vs_close_work_ui(self):
        """Closes the task in the UI: removes the package layers and resets counters."""
        self.pantanal_vs_locked_cells = []
        self.pantanal_vs_locked_cell_geoms = []
        self.pantanal_vs_cell_interpreters = {}
        self.audit_interpreter = None
        self.lbl_grade_info.setText('Nenhuma célula selecionada')
        self.btn_finish_work.setVisible(False)
        self.btn_save_workspace.setVisible(False)
        self.lbl_pacote.setVisible(False)
        self.btn_select_grade.setEnabled(True)
        self._vs_remove_work_layers()
        self.work_package = None
        self.canvas.refresh()
        self.total = 0
        self.counts = {c[0]: 0 for c in self.classes}
        self._update_counters()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _vs_discard_lost_package(self, perdidas):
        """
        An admin freed cells of this package. It is not uploaded; the user may close
        it (marked 'limpo') and the cells still held are released.
        """
        username = self.user_info['username']
        restantes = [o for o in self.pantanal_vs_locked_cells if o not in perdidas]
        txt = ((f'O administrador liberou estas células:\n{", ".join(perdidas)}\n\n'
                 'O pacote não pode mais ser enviado, porque recriaria amostras apagadas na API.\n\n'
                 'Encerrar o pacote sem enviar?'))
        if restantes:
            txt += f'\nAs demais células do pacote ({", ".join(restantes)}) serão liberadas.'
        if QMessageBox.question(self, 'Finalizar trabalho', txt,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes) != QMessageBox.StandardButton.Yes:
            return
        erros = []
        for oid in restantes:
            ok, err = self.vs_api.release_cell(oid, username, self.audit_mode)
            if not ok:
                erros.append(f'{oid}: {err}')
        wp = self.work_package
        if wp is not None:
            try:
                wp.set_meta({'status': PKG_LIMPO, 'limpo_em': now_iso()})
                wp.log_envio('descartado', mensagem='células liberadas pelo administrador: '
                             + ', '.join(perdidas))
                registry_remove(wp.path)
            except Exception as e:
                self._log(f'Aviso ao atualizar o pacote: {e}')
        self._vs_close_work_ui()
        self._log('Pacote encerrado sem envio (células liberadas pelo administrador).'
                  + (f' Arquivo mantido em: {wp.path}' if wp is not None else ''))
        self._refresh_filtros()
        self._refresh_statistics()
        if erros:
            QMessageBox.warning(self, 'Finalizar trabalho',
                                'Algumas células não foram liberadas:\n' + '\n'.join(erros))

    def _vs_finish_work(self):
        endpoint = self._vs_confirm_finish()
        if not endpoint:
            return
        api_url, api_key = endpoint
        if api_url != self.vs_api.client.base_url or api_key != self.vs_api.client.api_key:
            self.vs_api.set_endpoint(api_url, api_key)
            self._api_samples_cache = None
        ok_key, msg_key = self._vs_key_owner_ok()
        if not ok_key:
            QMessageBox.warning(self, 'Finalizar trabalho', msg_key + ' Nada foi enviado.')
            return
        if self.work_package is not None:
            try:
                self.work_package.set_meta({'api_url': api_url})
            except Exception as e:
                self._log(f'Aviso ao atualizar o pacote: {e}')
        self._log(f'Envio do pacote para a API: {api_url}')
        username = self.user_info['username']

        # cells freed by an admin while the package was open: uploading would
        # recreate samples the admin deleted
        try:
            perdidas = [oid for oid in self.pantanal_vs_locked_cells
                        if not self.vs_api.cell_held_by(oid, username, self.audit_mode)]
        except ApiError as e:
            QMessageBox.warning(self, 'Finalizar trabalho', f'Erro ao consultar a API:\n{e}')
            return
        if perdidas:
            self._vs_discard_lost_package(perdidas)
            return

        # audit: implicit agreement (label_audit = label), as in 0.69
        for layer in (self._sample_layers() if self.audit_mode else []):
            i_la = layer.fields().indexOf('label_audit')
            i_st = layer.fields().indexOf('sync_status')
            changes = {}
            for f in layer.getFeatures():
                if (py_value(f['audit']) == username and py_value(f['label_audit']) is None
                        and py_value(f['analyst']) != username):
                    ch = {i_la: f['label']}
                    if py_value(f['api_fid']) is not None:
                        ch[i_st] = STATUS_ALTERADA
                    changes[f.id()] = ch
            if changes:
                layer.dataProvider().changeAttributeValues(changes)

        ok, msg = self._vs_push('finalizacao')
        self._log(f'Envio à API: {msg}')
        if not ok:
            QMessageBox.warning(
                self, 'Finalizar trabalho',
                ('Não foi possível enviar as amostras.\n'
                'As células continuam bloqueadas e os dados estão salvos no pacote.\n\n') + msg)
            return

        erros, finalizadas = [], []
        for oid in self.pantanal_vs_locked_cells:
            if self.audit_mode:
                interpreter = (self.pantanal_vs_cell_interpreters.get(oid)
                               or self.audit_interpreter or self.vs_api.get_cell_analyst(oid))
                ok_c, err = self.vs_api.finish_audit(oid, username, interpreter)
            else:
                ok_c, err = self.vs_api.unlock_cell(oid, username)
            if ok_c:
                finalizadas.append(oid)
            else:
                erros.append(f'{oid}: {err}')
                self._log(f'Erro ao finalizar célula {oid}: {err}')

        wp = self.work_package
        if wp is not None:
            try:
                wp.mark_cells_finished(finalizadas)
                wp.log_envio('finalizacao_celulas', mensagem=f'{len(finalizadas)} célula(s) finalizada(s)')
                if not erros:
                    wp.set_meta({'status': PKG_FINALIZADO, 'finalizado_em': now_iso()})
                    registry_remove(wp.path)
            except Exception as e:
                self._log(f'Aviso ao atualizar o pacote: {e}')

        self._vs_close_work_ui()
        self._log('Trabalho finalizado. Células liberadas.')
        if wp is not None:
            self._log(f'Pacote finalizado. Arquivo: {wp.path}')
        self._refresh_filtros()
        self._refresh_statistics()
        if erros:
            QMessageBox.warning(self, 'Finalizar trabalho',
                                'Algumas células não foram finalizadas na API:\n' + '\n'.join(erros))

    @staticmethod
    def _vs_cell_status_text(rows):
        """Cell status text (from its ptn_tasks rows) for the confirmation."""
        partes = []
        for f in rows:
            p = f.get('properties') or {}
            if p.get('analyst_1'):
                st = 'finalizada' if p.get('finished_1') is True else 'em andamento'
                partes.append(f'interpretação de {p["analyst_1"]} ({st})')
            if p.get('analyst_2'):
                st = 'finalizada' if p.get('finished_2') is True else 'em andamento'
                partes.append(f'auditoria de {p["analyst_2"]} ({st})')
        partes = list(dict.fromkeys(partes))
        return ', '.join(partes) if partes else 'livre'

    def _vs_samples_in_cells(self, cell_geoms, tiles):
        """
        API sample fids inside each cell (sharing area with it; touching the border
        does not count). Reads the samples of the cell tiles plus those without a
        tile value. Returns {cell_oid: set(fid)}.
        """
        cand = {}
        for t in sorted(tiles):
            for f in self.vs_api.list_samples({'tile': t}, with_geometry=True):
                cand[f.get('id')] = f
        for p in self.vs_api.sample_properties(fields=['tile']):
            if not p.get('tile') and p['fid'] not in cand:
                f = self.vs_api.client.get_item(self.vs_api.col_amostras, p['fid'])
                if f:
                    cand[p['fid']] = f
        out = {oid: set() for oid in cell_geoms}
        for fid, f in cand.items():
            wkt = geojson_to_wkt(f.get('geometry'))
            if not wkt:
                continue
            g = QgsGeometry.fromWkt(wkt)
            for oid, cg in cell_geoms.items():
                if cg is not None and g.intersects(cg) and not g.touches(cg):
                    out[oid].add(fid)
        return out

    def _vs_clear_cells(self, cell_ids, parent=None):
        """
        Admin only (testing): deletes every API sample in the cells (all analysts)
        and frees the cells, finished work included. Local packages with these cells
        are marked 'limpo'.
        """
        parent = parent or self
        if not self.is_admin:
            QMessageBox.warning(parent, 'Desbloquear células',
                                'Somente administradores podem desbloquear células.')
            return False
        username = self.user_info['username']
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rows_by_cell, geoms, tiles = {}, {}, set()
            for oid in cell_ids:
                rows = self.vs_api.cell_rows(oid)
                rows_by_cell[oid] = rows
                g = None
                for f in rows:
                    tiles.add((f.get('properties') or {}).get('tile_2'))
                    wkt = geojson_to_wkt(f.get('geometry'))
                    if wkt and g is None:
                        g = QgsGeometry.fromWkt(wkt)
                geoms[oid] = g
            tiles.discard(None)
            fids_by_cell = self._vs_samples_in_cells(geoms, tiles)
        except ApiError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(parent, 'Desbloquear células', f'Erro ao consultar a API:\n{e}')
            return False
        QApplication.restoreOverrideCursor()

        todas_fids = set().union(*fids_by_cell.values()) if fids_by_cell else set()
        com_trabalho = [oid for oid in cell_ids
                        if fids_by_cell.get(oid)
                        or any(self.vs_api._row_has_work(f) for f in rows_by_cell[oid])]
        if not com_trabalho:
            QMessageBox.information(parent, 'Desbloquear células',
                                    'As células selecionadas já estão livres e sem amostras.')
            return False
        linhas = [f'• {oid} — {self._vs_cell_status_text(rows_by_cell[oid])}, '
                  f'{len(fids_by_cell.get(oid, ()))} amostra(s)' for oid in com_trabalho]
        if QMessageBox.question(
                parent, 'Desbloquear células',
                'Limpar estas células?\n\n' + '\n'.join(linhas) + (f'\n\n• {len(todas_fids)} amostra(s) serão APAGADAS da API, de todos os analistas\n'
                 '• as células voltam a ficar livres, inclusive as finalizadas\n\n'
                 'Não pode ser desfeito.'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        erros, apagadas, alteradas = [], 0, 0
        try:
            for fid in sorted(todas_fids):
                try:
                    self.vs_api.delete_sample(fid)
                    apagadas += 1
                except ApiError as e:
                    erros.append(f'amostra {fid}: {e}')
                    if 'indisponível' in str(e):
                        break
            for oid in com_trabalho:
                n, err = self.vs_api.reset_cell(oid)
                alteradas += n
                erros.extend(err)
            arquivados = WorkPackage.archive_cells(com_trabalho)
        finally:
            QApplication.restoreOverrideCursor()
        self._api_samples_cache = None
        self._log(f'[admin {username}] células {", ".join(com_trabalho)} limpas: '
                  f'{apagadas} amostra(s) apagada(s), {alteradas} registro(s) de célula liberado(s), '
                  f'{len(arquivados)} pacote(s) SQLite deste computador marcado(s) como "limpo".')
        if erros:
            QMessageBox.warning(parent, 'Desbloquear células',
                                'A limpeza terminou com erros:\n' + '\n'.join(erros[:10]))
        else:
            QMessageBox.information(parent, 'Desbloquear células',
                                    f'{len(com_trabalho)} célula(s) livre(s).\n'
                                    f'{apagadas} amostra(s) apagada(s) da API.')
        return True

    def _vs_clear_tile(self, tile_name, parent=None):
        """
        Admin only (testing): deletes every API sample of the tile and frees all its
        cells. Local packages for the tile are archived.
        """
        parent = parent or self
        if not self.is_admin:
            QMessageBox.warning(parent, 'Limpar tile', 'Somente administradores podem limpar um tile.')
            return False
        username = self.user_info['username']
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            tile_wkt = self.vs_api.get_tile_boundary(tile_name)
            tile_geom = QgsGeometry.fromWkt(tile_wkt) if tile_wkt else None
            fids = set()
            sem_tile = []
            for p in self.vs_api.sample_properties(fields=['tile']):
                if str(p.get('tile') or '') == str(tile_name):
                    fids.add(p['fid'])
                elif not p.get('tile'):
                    sem_tile.append(p['fid'])
            # samples without a tile value: decide by geometry
            if tile_geom is not None:
                for fid in sem_tile:
                    f = self.vs_api.client.get_item(self.vs_api.col_amostras, fid)
                    wkt = geojson_to_wkt((f or {}).get('geometry'))
                    if wkt and QgsGeometry.fromWkt(wkt).intersects(tile_geom):
                        fids.add(fid)
            n_cel, n_tot = self.vs_api.tile_lock_summary(tile_name)
        except ApiError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(parent, 'Limpar tile', f'Erro ao consultar a API:\n{e}')
            return False
        QApplication.restoreOverrideCursor()

        if not fids and not n_cel:
            QMessageBox.information(parent, 'Limpar tile',
                                    f'O tile {tile_name} já está limpo (sem amostras e sem bloqueios).')
            return False
        if QMessageBox.question(
                parent, 'Limpar tile',
                f'Limpar o tile {tile_name}?\n\n'
                f'• {len(fids)} amostra(s) serão APAGADAS da API (de todos os analistas)\n'
                f'• {n_cel} de {n_tot} registro(s) de célula voltam para "Livre" '
                f'(interpretação e auditoria)\n\n'
                'Esta ação não pode ser desfeita.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        erros, apagadas = [], 0
        try:
            for fid in sorted(fids):
                try:
                    self.vs_api.delete_sample(fid)
                    apagadas += 1
                except ApiError as e:
                    erros.append(f'amostra {fid}: {e}')
                    if 'indisponível' in str(e):
                        break
            alteradas, err_cel = self.vs_api.reset_tile_cells(tile_name)
            erros.extend(err_cel)
            arquivados = WorkPackage.archive_tile(tile_name)
        finally:
            QApplication.restoreOverrideCursor()
        self._api_samples_cache = None
        self._log(f'[{username}] tile {tile_name} limpo: {apagadas} amostra(s) apagada(s), '
                  f'{alteradas} registro(s) de célula liberado(s), '
                  f'{arquivados} pacote(s) SQLite em andamento marcado(s) como "limpo".')
        if erros:
            QMessageBox.warning(parent, 'Limpar tile',
                                'A limpeza terminou com erros:\n' + '\n'.join(erros[:10]))
        else:
            QMessageBox.information(parent, 'Limpar tile',
                                    f'Tile {tile_name} limpo.\n{apagadas} amostra(s) apagada(s) e '
                                    f'{alteradas} registro(s) de célula liberado(s).')
        return True

    def _vs_update_pacote_label(self):
        if not hasattr(self, 'lbl_pacote') or self.work_package is None:
            return
        pend = alt = 0
        for layer in self._sample_layers():
            for f in layer.getFeatures():
                if py_value(f['api_fid']) is None:
                    pend += 1
                elif py_value(f['sync_status']) == STATUS_ALTERADA:
                    alt += 1
        try:
            exc = len(self.work_package.pending_deletes())
        except Exception:
            exc = 0
        nome = os.path.basename(self.work_package.path)
        self.lbl_pacote.setText(f'Pacote: {nome}\nNão enviadas: {pend} · Alteradas: {alt} · '
                                f'Exclusões: {exc}')
        self.lbl_pacote.setToolTip(self.work_package.path)

    # ---------------------------------------------------- statistics over the API
    def _vs_stats_visible(self):
        tabs = getattr(self, 'session_totals_tabs', None)
        return tabs is not None and tabs.currentIndex() in (1, 2)

    def _vs_on_stats_tab_changed(self, idx):
        if self._is_api_project() and idx in (1, 2):
            self._populate_stats_combos()
            self._refresh_statistics()

    def _vs_api_samples(self, force=False):
        """
        API sample properties for the Totais/Auditoria tabs. Queried only while one
        of those tabs is open (or force=True for the report), cached for 60 s.
        """
        now = time.time()
        if self._api_samples_cache is not None and now - self._api_samples_cache_t < 60:
            return self._api_samples_cache
        if not force and not self._vs_stats_visible():
            return self._api_samples_cache or []
        try:
            data = self.vs_api.sample_properties(fields=self.vs_api.STATS_FIELDS)
        except ApiError as e:
            if str(e) != self._api_last_error:
                self._log(f'API: {e}')
                self._api_last_error = str(e)
            return []
        self._api_last_error = None
        biome_s = sanitize_text(self.biome) if self.biome else None
        data = [p for p in data if biome_s is None or p.get('biome') == biome_s]
        self._api_samples_cache = data
        self._api_samples_cache_t = now
        return data

    def _get_contagem(self, biome, project_type, username=None, tile=None,
                      ecoregion=None, all_interpreters=False, force=False):
        if self._is_api_project():
            counts = {}
            for p in self._vs_api_samples(force=force):
                if not all_interpreters and username and p.get('analyst') != username:
                    continue
                if tile and str(p.get('tile')) != tile:
                    continue
                if ecoregion is not None and p.get('ecoregion') != ecoregion:
                    continue
                lbl = p.get('label')
                if lbl is None:
                    continue
                counts[lbl] = counts.get(lbl, 0) + 1
            return sorted(counts.items(), key=lambda kv: -kv[1])
        return self.db.get_contagem(biome, project_type, username=username, tile=tile,
                                    ecoregion=ecoregion, all_interpreters=all_interpreters)

    def _populate_stats_combos_api(self, analyst_filter=None):
        tiles, ecos, analysts = set(), set(), set()
        for p in self._vs_api_samples():
            if p.get('analyst'):
                analysts.add(p['analyst'])
            if analyst_filter and self.is_auditor and p.get('analyst') != analyst_filter:
                continue
            if p.get('tile'):
                tiles.add(str(p['tile']))
            if p.get('ecoregion'):
                ecos.add(p['ecoregion'])
        self._fill_stats_combos(sorted(tiles), sorted(ecos),
                                sorted(analysts) if self.is_auditor else None)

    def _fill_stats_combos(self, tiles, ecos, analysts=None, eco_map=None):
        """Refills the Tile/Ecoregion/Analyst filters of the "Totais" tab, keeping the selection."""
        eco_map = eco_map or {}
        current_tile = self.stats_tile_combo.currentText()
        current_eco = self.stats_eco_combo.currentData()
        current_analyst = self.stats_analyst_combo.currentText()

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
            self.stats_eco_combo.addItem(eco_map.get(eco_s, eco_s), userData=eco_s)
        idx = self.stats_eco_combo.findData(current_eco)
        self.stats_eco_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.stats_eco_combo.blockSignals(False)

        self.stats_analyst_combo.blockSignals(True)
        self.stats_analyst_combo.clear()
        self.stats_analyst_combo.addItem('Todos')
        if analysts is not None:
            self.stats_analyst_combo.addItems(analysts)
            idx = self.stats_analyst_combo.findText(current_analyst)
            self.stats_analyst_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.stats_analyst_combo.blockSignals(False)

    def _populate_audit_filters_api(self, analyst_filter=None):
        audited = [p for p in self._vs_api_samples() if p.get('label_audit') is not None]
        analysts = sorted({p['analyst'] for p in audited if p.get('analyst')})
        sub = [p for p in audited if not analyst_filter or p.get('analyst') == analyst_filter]
        tiles = sorted({str(p['tile']) for p in sub if p.get('tile')})
        ecos = sorted({p['ecoregion'] for p in sub if p.get('ecoregion')})
        self._fill_audit_combos(analysts, tiles, ecos, analyst_filter)

    def _fill_audit_combos(self, analysts, tiles, ecos, analyst_filter=None, eco_map=None):
        """Refills the Tile/Ecoregion/Analyst filters of the "Auditoria" tab, keeping the selection."""
        eco_map = eco_map or {}
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
            self.audit_eco_combo.addItem(eco_map.get(eco_s, eco_s), userData=eco_s)
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

    def _vs_audit_counts(self, analyst, tile, eco):
        total = agree = disagree = 0
        for p in self._vs_api_samples():
            if p.get('label_audit') is None:
                continue
            if analyst and p.get('analyst') != analyst:
                continue
            if tile and str(p.get('tile')) != tile:
                continue
            if eco is not None and p.get('ecoregion') != eco:
                continue
            total += 1
            if p.get('label') == p.get('label_audit'):
                agree += 1
            else:
                disagree += 1
        return total, agree, disagree

    def _add_grid_boundary_layer(self, tile_name, cell_ids=None):
        self._remove_layers_named(*VS_LAYER_NAMES)
        params = self.db._get_project_conn_params(VS_BIOME, VS_PROJECT)

        uri_cells = QgsDataSourceUri()
        uri_cells.setConnection(params['host'], str(params['port']),
                                params['dbname'], params['user_user'], params['user_pass'])
        if cell_ids:
            cells_str = ', '.join(_sql_str(c) for c in cell_ids)
            filter_cells = f"cell_oid IN ({cells_str})"
        else:
            filter_cells = f"tile_2 = {_sql_str(tile_name)}"
        uri_cells.setDataSource('public', 'ptn_tasks', 'geom', filter_cells, 'cell_oid')
        uri_cells.setParam('srid', '4674')
        layer_cells = QgsVectorLayer(uri_cells.uri(False), VS_LAYER_CELLS, 'postgres')
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
        uri_tile.setDataSource('public', 'tiles_ptn', 'geom', f"tile = {_sql_str(tile_name)}", 'tile')
        uri_tile.setParam('srid', '4674')
        layer_tile = QgsVectorLayer(uri_tile.uri(False), VS_LAYER_TILE, 'postgres')
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
        if self._is_api_project():
            return self._vs_finish_work()
        reply = QMessageBox.question(
            self, 'Finalizar trabalho',
            'Deseja realmente finalizar o trabalho e liberar as células?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
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

            self._remove_layers_named(*VS_LAYER_NAMES)
            if self._layer_ok(self.layer):
                QgsProject.instance().removeMapLayer(self.layer)
                self.layer = None
                self.layer_id = None

            self.canvas.refresh()
            self._log('Trabalho finalizado. Células liberadas.')
            self._sync_counts(username)
            self._refresh_filtros()

    def _build_ui(self):
        root = QWidget()
        root.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
            /* text inside a card takes the card colour, not the darker page colour */
            QGroupBox QLabel, QGroupBox QRadioButton, QGroupBox QCheckBox {{ background: transparent; }}
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
            QComboBox:hover {{ border-color: {C_BORDER_HOVER}; }}
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
            px  = QPixmap(icon_path).scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ico.setPixmap(px); ico.setFixedSize(30, 30); hdr.addWidget(ico)
        t1 = QLabel('Sample Design')
        t1.setStyleSheet(f'font-size: 13pt; font-weight: 700; color: {C_TEXT}; letter-spacing: -0.3px;')
        hdr.addWidget(t1); hdr.addStretch(); lay.addLayout(hdr)
        self._sep(lay, top=6, bottom=2)

        grp_s = QGroupBox('Sessão'); gs = QVBoxLayout(grp_s); gs.setSpacing(5)
        row_u = QHBoxLayout(); row_u.setSpacing(4)
        lbl_u_full = QLabel('Usuário:'); lbl_u_full.setMinimumWidth(55); lbl_u_full.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:700; background:transparent;')
        self.lbl_user = QLabel('—'); self.lbl_user.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        row_u.addWidget(lbl_u_full); row_u.addWidget(self.lbl_user); row_u.addStretch(); gs.addLayout(row_u)
        row_b = QHBoxLayout(); row_b.setSpacing(4)
        lbl_b_full = QLabel('Bioma:'); lbl_b_full.setMinimumWidth(55); lbl_b_full.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:700; background:transparent;')
        self.lbl_biome_val = QLabel('—'); self.lbl_biome_val.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; font-weight:400; background:transparent;')
        row_b.addWidget(lbl_b_full); row_b.addWidget(self.lbl_biome_val); row_b.addStretch(); gs.addLayout(row_b)
        self.btn_session = QPushButton('Entrar'); self.btn_session.setMinimumHeight(30); self.btn_session.setStyleSheet(_pill(C_STEEL)); self.btn_session.clicked.connect(self._on_session_btn)
        gs.addWidget(self.btn_session)

        self.btn_geopackage = QPushButton('Abrir GeoPackage')
        self.btn_geopackage.setMinimumHeight(30)
        self.btn_geopackage.setStyleSheet(_BTN_ACT)
        self.btn_geopackage.clicked.connect(self._open_geopackage)
        gs.addWidget(self.btn_geopackage)

        self.btn_open_pacote = QPushButton('Abrir Pacote de Trabalho')
        self.btn_open_pacote.setMinimumHeight(30)
        self.btn_open_pacote.setStyleSheet(_BTN_ACT)
        self.btn_open_pacote.clicked.connect(self._vs_open_package_dialog)
        gs.addWidget(self.btn_open_pacote)

        lay.addWidget(grp_s)

        self.grp_grade = QGroupBox('Área de Trabalho')
        self.grp_grade.setVisible(False)
        gv = QVBoxLayout(self.grp_grade)
        self.lbl_grade_info = QLabel('Nenhuma célula selecionada')
        self.lbl_grade_info.setStyleSheet(f'color:{C_TEXT}; font-size:8.5pt; font-weight:600; background:transparent;')
        self.lbl_grade_info.setWordWrap(True)
        gv.addWidget(self.lbl_grade_info)
        h_grade = QVBoxLayout()  # stacked buttons: they always fit the panel width
        h_grade.setSpacing(6)
        self.btn_select_grade = QPushButton('Selecionar Tile / Células')
        self.btn_select_grade.setStyleSheet(_BTN_ACT)
        self.btn_select_grade.clicked.connect(self._on_select_grade_clicked)
        h_grade.addWidget(self.btn_select_grade)
        self.btn_finish_work = QPushButton('Finalizar Trabalho')
        self.btn_finish_work.setStyleSheet(_pill(C_STEEL))
        self.btn_finish_work.clicked.connect(self._finish_work)
        self.btn_finish_work.setVisible(False)
        h_grade.addWidget(self.btn_finish_work)
        gv.addLayout(h_grade)
        self.btn_save_workspace = QPushButton('Salvar workspace')
        self.btn_save_workspace.setStyleSheet(_BTN_ACT)
        self.btn_save_workspace.setToolTip('Salva no pacote as camadas, os estilos e os ajustes do projeto, para restaurar ao reabrir.')
        self.btn_save_workspace.clicked.connect(self._vs_save_workspace)
        self.btn_save_workspace.setVisible(False)
        gv.addWidget(self.btn_save_workspace)
        self.lbl_pacote = QLabel('')
        self.lbl_pacote.setWordWrap(True)
        self.lbl_pacote.setStyleSheet(f'color:{C_MUTED}; font-size:7.5pt; background:transparent;')
        self.lbl_pacote.setVisible(False)
        gv.addWidget(self.lbl_pacote)
        lay.addWidget(self.grp_grade)

        # navigation between image years: "Connect" tab, API projects only
        self.connect_nav = ConnectNav(self.iface, btn_style=_BTN_ACT, parent=self)
        self.connect_nav.on_f9 = self._toggle_images_tab

        grp_cls = QGroupBox('Classe'); lc = QVBoxLayout(grp_cls); lc.setSpacing(6)
        self.cls_color_bar = QFrame(); self.cls_color_bar.setFixedHeight(3); self.cls_color_bar.setStyleSheet(f'background: {C_BORDER_HOVER}; border-radius: 2px;')
        self.combo = QComboBox(); self.combo.setMinimumHeight(34); self.combo.currentIndexChanged.connect(self._on_class_changed)
        lc.addWidget(self.combo); lc.addWidget(self.cls_color_bar)

        self.btn_reclass = QPushButton('Reclass (Auditoria)')
        self.btn_reclass.setStyleSheet(_BTN_ACT)
        self.btn_reclass.clicked.connect(self._reclass_audit)
        self.btn_reclass.setVisible(False)
        lc.addWidget(self.btn_reclass)

        self.btn_manage_users = QPushButton('Gerenciar usuários')
        self.btn_manage_users.setMinimumHeight(26)
        self.btn_manage_users.setStyleSheet(f'QPushButton {{ background:transparent; color:{C_LINK}; border:1.5px solid {C_BORDER}; border-radius:7px; font-size:8pt; font-weight:600; padding:0 10px; min-height:26px; }} QPushButton:hover {{ background:{C_HOVER}; border-color:{C_STEEL}; }}')
        self.btn_manage_users.clicked.connect(self._manage_users)
        self.btn_manage_users.setVisible(False)
        lc.addWidget(self.btn_manage_users)

        self.btn_manage_classes = QPushButton('Gerenciar classes')
        self.btn_manage_classes.setMinimumHeight(26)
        self.btn_manage_classes.setStyleSheet(self.btn_manage_users.styleSheet())
        self.btn_manage_classes.setToolTip('Adicionar, remover, reordenar ou mudar a cor das classes (administradores e auditores).')
        self.btn_manage_classes.clicked.connect(self._manage_classes)
        self.btn_manage_classes.setVisible(False)
        lc.addWidget(self.btn_manage_classes)

        lay.addWidget(grp_cls)

        grp_w = QGroupBox('Janela de Amostragem'); lw = QVBoxLayout(grp_w); lw.setSpacing(4)
        grp_w.setStyleSheet("""
            QSpinBox, QLabel {
                background: transparent;
            }
        """)
        row_size = QHBoxLayout(); row_size.setSpacing(8)
        self.lbl_size = lbl_size = self._small('Tamanho:')
        lbl_size.setMinimumWidth(75)
        row_size.addWidget(lbl_size)
        self.spin = QSpinBox(); self.spin.setRange(1, 50); self.spin.setValue(10); self.spin.setSuffix(' px'); self.spin.setMinimumWidth(78)
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
        self.spin_max_scale.setMinimumWidth(78)
        self.spin_max_scale.valueChanged.connect(self._on_max_scale_changed)
        row_max_scale.addWidget(self.spin_max_scale)
        self.lbl_suffix = QLabel('(1:x)')
        self.lbl_suffix.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        row_max_scale.addWidget(self.lbl_suffix)
        row_max_scale.addStretch()
        lw.addLayout(row_max_scale)
        lay.addWidget(grp_w)

        grp_mode = QGroupBox('Modo de desenho')
        grp_mode.setStyleSheet(_RADIO_CSS)
        self.mode_layout = mode_layout = QGridLayout(grp_mode)
        mode_layout.setContentsMargins(2, 4, 2, 0)
        mode_layout.setHorizontalSpacing(6)
        mode_layout.setVerticalSpacing(2)
        self.grp_mode = grp_mode   # height set by _apply_draw_modes from the number of rows
        self.radio_point = QRadioButton('Ponto')
        self.radio_square = QRadioButton('Quadrado pré-definido')
        self.radio_polygon = QRadioButton('Polígono livre')
        self.radio_square.setChecked(True)
        self.radio_point.setVisible(False)
        for r in (self.radio_point, self.radio_square, self.radio_polygon):
            r.setMinimumHeight(24)  # room for the 18 px circle
        mode_layout.addWidget(self.radio_point, 0, 0)
        mode_layout.addWidget(self.radio_square, 0, 1)
        mode_layout.addWidget(self.radio_polygon, 1, 0)
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
        self.radio_point.toggled.connect(self._on_mode_changed)
        self.radio_square.toggled.connect(self._on_mode_changed)
        self.radio_polygon.toggled.connect(self._on_mode_changed)
        self.mode_layout.setColumnStretch(0, 1)
        self.mode_layout.setColumnStretch(1, 1)
        self._apply_draw_modes(DEFAULT_DRAW_MODES)  # aligned from the start (hidden "Ponto" leaves no gap)
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
        session_tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        session_layout = QVBoxLayout(session_tab)
        session_layout.setSpacing(4)
        session_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_total = QLabel('0')
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_total.setStyleSheet(f'font-size:26pt; font-weight:700; color:{C_TEXT}; padding:2px; letter-spacing:-1px;')
        session_layout.addWidget(self.lbl_total)

        self._sep(session_layout, top=2, bottom=4)
        self.pie_widget = PieChartWidget()
        self.pie_widget.setFixedHeight(170)
        self.pie_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.cnt_grid_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        scroll_session.setFrameShape(QFrame.Shape.NoFrame)
        scroll_session.setMinimumHeight(400)
        scroll_session.setWidget(session_tab)
        self.session_totals_tabs.addTab(scroll_session, "Sessão")

        totais_tab = QWidget()
        totais_tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        totais_layout = QVBoxLayout(totais_tab)
        totais_layout.setSpacing(6)
        totais_layout.setContentsMargins(0, 0, 0, 0)

        self.stats_total_big = QLabel('0')
        self.stats_total_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.stats_pie_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.stats_grid_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stats_grid_layout = QGridLayout(self.stats_grid_widget)
        self.stats_grid_layout.setSpacing(3)
        self.stats_grid_layout.setColumnStretch(1, 1)
        totais_layout.addWidget(self.stats_grid_widget)

        self.scroll_totais = QScrollArea()
        self.scroll_totais.setWidgetResizable(True)
        self.scroll_totais.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_totais.setMinimumHeight(400)
        self.scroll_totais.setWidget(totais_tab)
        self.session_totals_tabs.addTab(self.scroll_totais, "Totais")
        self.session_totals_tabs.setTabVisible(1, False)

        audit_tab = QWidget()
        audit_tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        audit_layout = QVBoxLayout(audit_tab)
        audit_layout.setSpacing(6)
        audit_layout.setContentsMargins(0, 0, 0, 0)

        self.audit_total_label = QLabel('0')
        self.audit_total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.audit_pie_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.audit_grid_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.audit_grid_widget.setMinimumHeight(80)
        self.audit_grid_layout = QGridLayout(self.audit_grid_widget)
        self.audit_grid_layout.setSpacing(3)
        self.audit_grid_layout.setColumnStretch(1, 1)
        audit_layout.addWidget(self.audit_grid_widget)

        scroll_audit = QScrollArea()
        scroll_audit.setWidgetResizable(True)
        scroll_audit.setFrameShape(QFrame.Shape.NoFrame)
        scroll_audit.setMinimumHeight(400)
        scroll_audit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_audit.setWidget(audit_tab)
        self.session_totals_tabs.addTab(scroll_audit, "Auditoria")
        self.session_totals_tabs.setTabVisible(2, False)
        self.session_totals_tabs.currentChanged.connect(self._vs_on_stats_tab_changed)

        lay.addWidget(grp_cnt)

        self._sep(lay)


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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # safety net: scroll, never clip
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""QScrollArea {{ border:none; background:{C_BG}; }} QScrollBar:vertical {{ background:transparent; width:8px; }} QScrollBar::handle:vertical {{ background:{C_SCROLL}; border-radius:4px; min-height:20px; }} QScrollBar::handle:vertical:hover {{ background:#A0AEC0; }} QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }} QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}""")
        scroll.setWidget(root)

        self.ts_panel = TimeSeriesPanel(self._ts_selected_samples, btn_style=_BTN_ACT)
        self.ts_panel.on_focus = self._ts_flash_sample
        tab_img = QWidget()
        tab_img.setObjectName('tabConnect')
        tab_img.setStyleSheet(f'QWidget#tabConnect {{ background:{C_BG}; }} QLabel {{ color:{C_TEXT}; }}')
        l_img = QVBoxLayout(tab_img)
        l_img.setContentsMargins(8, 10, 8, 8)
        l_img.addWidget(self.connect_nav.panel)
        l_img.addStretch()
        self.ts_panel.setObjectName('tabSerie')
        self.ts_panel.setStyleSheet(f'QWidget#tabSerie {{ background:{C_BG}; }} '
                                    f'QLabel, QCheckBox {{ color:{C_TEXT}; }}' + _RADIO_CSS)
        self._coleta_scroll = scroll

        def _tab_scroll(widget):
            # each tab scrolls on its own, so no tab forces a minimum width on the panel
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            sa.setStyleSheet(scroll.styleSheet())
            sa.setWidget(widget)
            return sa

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(scroll, 'Coleta')
        self.main_tabs.addTab(_tab_scroll(tab_img), 'Connect')
        self.main_tabs.addTab(_tab_scroll(self.ts_panel), 'Série temporal')
        self.main_tabs.setTabEnabled(TAB_IMAGENS, False)
        self.main_tabs.setTabEnabled(TAB_SERIE, False)
        self.setWidget(self.main_tabs)
        self.setMinimumWidth(300)  # replaced in _fit_min_width by what the content needs
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumHeight(550)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_min_width)

    def _fit_min_width(self):
        """
        Minimum panel width = what the "Coleta" content really needs with the current
        fonts/screen scaling (125%, 150%...), so the panel is never cut on the right.
        """
        try:
            sa = self._coleta_scroll
            need = (sa.widget().minimumSizeHint().width() + sa.verticalScrollBar().sizeHint().width()
                    + 2 * sa.frameWidth() + 6)
            self.main_tabs.setMinimumWidth(need)
            # the dock's own minimum must follow too, otherwise Qt keeps it narrower and cuts the content
            self.setMinimumWidth(need + 2 * self.style().pixelMetric(QStyle.PixelMetric.PM_DockWidgetFrameWidth) + 4)
        except RuntimeError:
            pass

    def _on_mode_changed(self):
        if self.radio_point.isChecked():
            self._draw_mode = 'point'
        elif self.radio_square.isChecked():
            self._draw_mode = 'square'
        elif self.radio_polygon.isChecked():
            self._draw_mode = 'polygon'
        if self._layer_ok(self.point_layer) and self._layer_ok(self.layer):
            try:
                self.iface.setActiveLayer(self.point_layer if self._draw_mode == 'point' else self.layer)
            except Exception:
                pass

        if hasattr(self, 'tool') and self.tool:
            self.tool.set_mode(self._draw_mode)

        self._update_rotate_btn_state()

    def get_draw_mode(self):
        return self._draw_mode

    def _apply_draw_modes(self, modes):
        """Shows only the radios of the allowed modes and selects the first one."""
        radios = {'point': self.radio_point, 'square': self.radio_square, 'polygon': self.radio_polygon}
        visible = [m for m in radios if m in modes]
        for mode, radio in radios.items():
            self.mode_layout.removeWidget(radio)
            radio.setVisible(mode in modes)
        # all modes side by side in one row, evenly spaced from the left (the empty
        # stretch column at the end takes the rest of the width)
        for i, mode in enumerate(visible):
            self.mode_layout.addWidget(radios[mode], 0, i)
        for c in range(4):
            self.mode_layout.setColumnStretch(c, 1 if c == 3 else 0)
        self.mode_layout.setHorizontalSpacing(18)
        if not getattr(self, '_mode_spacer', None):
            self._mode_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.mode_layout.addItem(self._mode_spacer, 0, 3)
        for r in range(2):
            self.mode_layout.setRowMinimumHeight(r, 24 if r == 0 else 0)
        if hasattr(self, 'grp_mode'):
            self.grp_mode.setFixedHeight(44 + 26)
        if self._draw_mode not in modes:
            radios[modes[0]].setChecked(True)
        self._on_mode_changed()
        self.btn_rotate_feature.setVisible('square' in modes)  # square mode only
        QTimer.singleShot(0, self._fit_min_width)

    def _set_size_row_visible(self, visible):
        for w in (self.lbl_size, self.spin, self.lbl_m):
            w.setVisible(visible)

    def _toggle_images_tab(self):
        """F9: Connect tab <-> Coleta tab."""
        if not self.main_tabs.isTabEnabled(TAB_IMAGENS):
            return
        self.main_tabs.setCurrentIndex(TAB_COLETA if self.main_tabs.currentIndex() == TAB_IMAGENS
                                       else TAB_IMAGENS)
        if self.isHidden():
            self.show()

    # ═══════════════════════════════════════════════════════════════
    # Analysis date, workspace, classes and time series (API projects)
    # ═══════════════════════════════════════════════════════════════
    def _set_analysis_date(self, value):
        self.analysis_date = value
        self.ts_panel.set_analysis_date(value)

    def _package_layer(self, wp, name):
        """Layer of the current project that reads `name` from the package (restored workspace)."""
        target = os.path.normcase(os.path.abspath(wp.path))
        for lyr in QgsProject.instance().mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer) or lyr.providerType() != 'ogr':
                continue
            src = lyr.source().split('|')
            if os.path.normcase(os.path.abspath(src[0])) != target:
                continue
            if any(part == f'layername={name}' for part in src[1:]):
                return lyr
        return None

    def _layer_for_geometry(self, geom):
        """Sample layer that stores this geometry type (points or polygons)."""
        if geom.type() == Qgis.GeometryType.Point:
            return self.point_layer if self._layer_ok(self.point_layer) else None
        return self.layer if self._layer_ok(self.layer) else None

    def _vs_offer_workspace(self, wp):
        """
        If the package has a saved workspace, offers to restore it (replaces the
        current QGIS project). Returns True when it was restored.
        """
        if not wp.has_workspace():
            return False
        if QMessageBox.question(
                self, 'Workspace',
                'Este pacote tem um workspace salvo.\n\nRestaurar? O projeto aberto no QGIS será substituído.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes) != QMessageBox.StandardButton.Yes:
            return False
        self._vs_disconnect_layers()
        self.layer = self.point_layer = self.tile_layer = None
        self.connect_nav.clear()
        if not QgsProject.instance().read(wp.workspace_uri()):
            self._log(f'Não foi possível restaurar o workspace: {QgsProject.instance().error()}')
            return False
        remove_images()  # in-memory images are not valid in a reloaded project: rebuilt below
        self._log('Workspace restaurado do pacote.')
        return True

    def _vs_save_workspace(self):
        """Stores the current QGIS project inside the package (qgis_projects table)."""
        wp = self.work_package
        if wp is None:
            return
        for lyr in self._sample_layers():
            if lyr.isEditable() and lyr.isModified():
                QMessageBox.warning(self, 'Workspace', f'Salve as edições da camada "{lyr.name()}" '
                                    'antes de salvar o workspace.')
                return
        project = QgsProject.instance()
        old_name = project.fileName()
        ok = project.write(wp.workspace_uri())
        if old_name != project.fileName():
            project.setFileName(old_name)  # keep the user's own project file as the current one
        if ok:
            wp.set_meta({'workspace_salvo_em': now_iso()})
            self._log(f'Workspace salvo no pacote: {os.path.basename(wp.path)}')
            QMessageBox.information(self, 'Workspace', 'Workspace salvo no pacote.')
        else:
            QMessageBox.warning(self, 'Workspace', f'Não foi possível salvar o workspace:\n'
                                f'{project.error()}')

    def _vs_reload_classes(self, meta=None, quiet=False):
        """
        Class list of an API project: from the API; offline, the copy stored in the
        package (meta['classes']); last resort, CLASSES_POR_BIOMA.
        """
        classes = None
        try:
            classes = self.vs_api.list_classes() or None
        except Exception as e:
            if not quiet:
                self._log(f'Não foi possível ler as classes da API ({e}). Usando a lista local.')
        if classes is None and meta and meta.get('classes'):
            try:
                classes = [tuple(c) for c in json.loads(meta['classes'])]
            except (ValueError, TypeError):
                classes = None
        if classes is None:
            classes = list(CLASSES_POR_BIOMA.get((self.biome, self.project_type), []))
        self._set_classes(classes)

    def _set_classes(self, classes):
        self.classes = [tuple(c) for c in classes]
        old = self.counts
        self.counts = {c[0]: old.get(c[0], 0) for c in self.classes}
        self._populate_combo()
        self._rebuild_counters_grid()
        self._apply_style()
        self._configure_layer_visibility(self.is_admin and not self._is_local_geopackage)
        if self.work_package is not None:
            try:
                self.work_package.set_meta({'classes': json.dumps(self.classes, ensure_ascii=False)})
            except Exception:
                pass
        if self.user_info:
            self._sync_counts(self.user_info['username'])

    def _manage_classes(self):
        """Class editor for administrators and auditors (API or PostgreSQL project)."""
        if not (self.is_admin or self.is_auditor) or self._is_local_geopackage:
            return
        if self._is_api_project():
            save_fn = self.vs_api.save_classes
            sub = ('As classes ficam na API e valem para todos os usuários. '
                   'Remover uma classe não apaga amostras.')
        else:
            def save_fn(classes):
                return self.db.save_project_classes(self.biome, self.project_type, classes)
            sub = ('As classes ficam no banco do projeto e valem para todos os usuários.')
        dlg = ClassManagerDialog(self.classes, save_fn=save_fn, parent=self, subtitle=sub)
        if dlg.exec():
            self._set_classes(dlg.get_classes())
            self._log(f'Classes do projeto atualizadas ({len(self.classes)}).')

    def _ts_sample_dict(self, layer, f):
        code = py_value(f['label_audit']) if self.audit_mode and 'label_audit' in \
            layer.fields().names() and py_value(f['label_audit']) else py_value(f['label'])
        color = next((c for k, _, c in self.classes if k == code), '#888888')
        ident = py_value(f['api_fid']) if 'api_fid' in layer.fields().names() else None
        local = f'ponto {f.id()}' if layer is self.point_layer else f'local {f.id()}'
        return {'id': f'#{ident}' if ident is not None else local,
                'label': self._code_to_label(code), 'color': color,
                'geom': QgsGeometry(f.geometry()), 'crs': layer.crs(),
                'layer_id': layer.id(), 'fid': f.id()}

    def _ts_flash_sample(self, sample):
        """Blinks the sample shown alone in the chart (centres the map on it if needed)."""
        layer = QgsProject.instance().mapLayer(sample.get('layer_id') or '')
        if not self._layer_ok(layer) or sample.get('fid') is None:
            return
        try:
            ext = self.canvas.mapSettings().layerExtentToOutputExtent(layer, sample['geom'].boundingBox())
            if not self.canvas.extent().contains(ext):
                self.canvas.setCenter(ext.center())
                self.canvas.refresh()
            self.canvas.flashFeatureIds(layer, [sample['fid']])
        except Exception:
            pass

    def _ts_selected_samples(self):
        out = []
        for lyr in self._sample_layers():
            out += [self._ts_sample_dict(lyr, f) for f in lyr.selectedFeatures() if f.hasGeometry()]
        return out

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
                'Nenhuma feição selecionada.\n\nSelecione as feições no mapa e clique de novo em "Rotacionar Feição".'
            )
            self.iface.actionSelect().trigger()
            return

        if self.rotate_tool is None or sip.isdeleted(self.rotate_tool):
            self.rotate_tool = _RotateFeatureMapTool(self.canvas, self)
        self.canvas.setMapTool(self.rotate_tool)
        self._log('Rotação ativada: arraste sobre a seleção para girar.')

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
            pr.addAttributes([QgsField('analyst', QMetaType.Type.QString, 'string', 100)])
            sample_layer.updateFields()
        if fields.indexOf('biome') == -1:
            pr.addAttributes([QgsField('biome', QMetaType.Type.QString, 'string', 50)])
            sample_layer.updateFields()

        if self._layer_ok(self.layer):
            self._connect_commit_signals(self.layer, connect=False)
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
        self.lbl_scale.setMinimumWidth(75)
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
        self.btn_reclass.setVisible(False)
        self._populate_combo()
        self._rebuild_counters_grid()
        self._apply_style()
        self._configure_layer_visibility(False)
        QgsProject.instance().addMapLayer(self.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, self.layer)
        self._connect_commit_signals(self.layer)

        self.session_totals_tabs.setTabVisible(1, self._get_prodes_totals_layer() is not None)
        self.session_totals_tabs.setTabVisible(2, False)
        self._refresh_filtros()
        self._sync_counts(analyst)
        self._populate_stats_combos()
        self._refresh_statistics()
        self._refresh_timer.start()
        self._log(f'GeoPackage aberto: {path} — {analyst} · {biome} · {project_type}')

    def _configure_layer_visibility(self, is_admin):
        always_hidden = {'área', 'ações'}
        if is_admin:
            hidden = set()
        elif self.is_auditor:
            hidden = {'area_m2', 'px_size', 'window_px', 'audit'}
        else:
            hidden = {'area_m2', 'px_size', 'window_px', 'analyst', 'audit', 'label_audit'}
        options = {label: code for code, label, _ in self.classes}
        for layer in self._sample_layers():
            cfg = layer.attributeTableConfig()
            columns = cfg.columns()
            for col in columns:
                col.hidden = col.name in always_hidden or col.name in hidden
            cfg.setColumns(columns)
            layer.setAttributeTableConfig(cfg)
            idx_audit = layer.fields().indexOf('label_audit')
            if idx_audit >= 0:
                layer.setEditorWidgetSetup(idx_audit, QgsEditorWidgetSetup('ValueMap', {'map': options}))

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

    def _api_scale_key(self):
        return f'SampleDesign/escala_max/{self.biome}/{self.project_type}'

    def _api_max_scale(self):
        """Max scale of an API project: the one set by ADM on this computer, else the default."""
        default = self._api_cfg()['max_scale']
        try:
            return int(QgsSettings().value(self._api_scale_key(), default))
        except (TypeError, ValueError):
            return default

    def _on_max_scale_changed(self, value):
        self.max_scale = value
        if self._is_api_project():
            self.lbl_suffix.setText(f'(1:{value:,})'.replace(',', '.'))
            if self.is_admin and self.spin_max_scale.isEnabled():
                QgsSettings().setValue(self._api_scale_key(), int(value))
        elif (not self._is_local_geopackage and self.user_info
                and self.user_info.get('username') != 'local'):
            self.db.set_biome_config(self.biome, value)

    def _reclass_audit(self):
        if not self._layer_ok(self.layer) or not self.user_info:
            return
        if not self.is_auditor or not self.audit_mode:
            return

        selecao = [(lyr, lyr.selectedFeatureIds()) for lyr in self._sample_layers()
                   if lyr.selectedFeatureIds()]
        selected_ids = [fid for _, ids in selecao for fid in ids]
        if not selected_ids:
            if self._is_api_project():
                alvo = self.point_layer if (self.get_draw_mode() == 'point'
                                            and self._layer_ok(self.point_layer)) else self.layer
                try:
                    self.iface.setActiveLayer(alvo)
                    self.iface.actionSelect().trigger()
                except Exception:
                    pass
                QMessageBox.warning(
                    self, 'Auditoria',
                    (f'Nenhuma amostra selecionada em "{alvo.name()}".\n\n'
                 'Selecione as amostras no mapa e clique de novo em "Reclass (Auditoria)".'))
                return
            QMessageBox.warning(self, 'Auditoria', 'Selecione pelo menos um polígono no mapa.')
            return

        code = self.combo.currentData()
        if not code:
            self._log('Nenhuma classe selecionada para reclassificação.')
            return

        if code == EXCLUIR_CODE:
            self._log(f'{len(selected_ids)} polígono(s) marcado(s) para exclusão.')

        auditor = self.user_info['username']
        if any(lyr.fields().indexOf('label_audit') == -1 or lyr.fields().indexOf('audit') == -1
               for lyr, _ in selecao):
            self._log('Campos de auditoria não encontrados na camada.')
            return

        cls_name = self.combo.currentText()
        reply = QMessageBox.question(
            self, 'Confirmar Reclassificação',
            f'Reclassificar {len(selected_ids)} polígono(s) como "{cls_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for layer, ids in selecao:
            fields = layer.fields()
            changes = {fid: {fields.indexOf('label_audit'): code, fields.indexOf('audit'): auditor}
                       for fid in ids}
            if self._is_api_project():
                self._vs_flag_altered_in_changes(layer, changes)
            layer.dataProvider().changeAttributeValues(changes)
            if self._is_local_geopackage:
                layer.updateExtents()
                self.canvas.refreshAllLayers()
            else:
                layer.triggerRepaint()
            if self._is_api_project():
                layer.removeSelection()

        self._log(f'Reclass: {len(selected_ids)} amostra(s) → "{cls_name}" por {auditor}.')
        if self._is_api_project():
            self._vs_update_pacote_label()
            self._log('Reclassificação salva no pacote. Vai para a API ao finalizar.')
        self._sync_counts(self.user_info['username'])
        self._refresh_filtros()
        self._refresh_statistics()

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
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

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
            edit_pass = QLineEdit(); edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
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
            if dlg_add.exec():
                refresh_table()

        def delete_user():
            row = tbl.currentRow()
            if row < 0:
                QMessageBox.warning(dlg, 'Atenção', 'Selecione um usuário.')
                return
            username = users[row]['username']
            if QMessageBox.question(dlg, 'Confirmar exclusão',
                f'Deseja excluir permanentemente o usuário "{username}"?\nEsta ação não pode ser desfeita.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                ok, msg = self.db.delete_user(username)
                if not ok:
                    QMessageBox.critical(dlg, 'Erro', msg)
                else:
                    refresh_table()

        btn_add.clicked.connect(add_user)
        btn_del.clicked.connect(delete_user)
        btn_fechar.clicked.connect(dlg.accept)
        dlg.exec()

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.set_user_auditor(username, novo)
            refresh_callback()
            self._log(f'Auditoria de "{username}" {"ativada" if novo else "desativada"}.')

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
        if code is None:
            return
        if code == EXCLUIR_CODE:
            color = EXCLUIR_COLOR
        else:
            color = next((c for c_code, _, c in self.classes if c_code == code), '#C5CDD8')
        self.cls_color_bar.setStyleSheet(f'background:{color}; border-radius:2px;')

    def _rebuild_counters_grid(self):
        _clear_layout(self.cnt_grid_layout)
        self.count_labels = {}
        for row_i, (code, label, color) in enumerate(self.classes):
            _, num = _count_row(self.cnt_grid_layout, row_i, color, label, self.counts.get(code, 0))
            self.count_labels[code] = num
        self.total_label_widget = _total_row(self.cnt_grid_layout, len(self.classes), self.total)
        self._finish_count_grid(len(self.classes))

    def _finish_count_grid(self, n_rows):
        self.cnt_grid_widget.setMinimumHeight((n_rows + 1) * 22 + 24)
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

        if self._is_local_geopackage or self._is_api_project():
            self.combo_tile.blockSignals(True)
            self.combo_eco.blockSignals(True)
            self.combo_tile.clear()
            self.combo_eco.clear()
            self.combo_tile.addItem('Todos')
            self.combo_eco.addItem('Todas', None)
            if self._layer_ok(self.layer):
                tiles = set()
                ecos = set()
                for layer in self._sample_layers():
                    for feat in layer.getFeatures():
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

        if self._is_local_geopackage or self._is_api_project():
            layer = self.layer
            if layer.fields().indexOf('label') == -1:
                self._log("Campo 'label' não encontrado.")
                return
            filters = []
            if tile != 'Todos':
                filters.append(QgsExpression.createFieldEqualityExpression('tile', tile))
            if eco is not None:
                filters.append(QgsExpression.createFieldEqualityExpression('ecoregion', eco))
            request = (QgsFeatureRequest(QgsExpression(' AND '.join(filters))) if filters
                       else QgsFeatureRequest())
            counts = {code: 0 for code, _, _ in self.classes}
            for lyr in self._sample_layers():
                for feat in lyr.getFeatures(request):
                    code = feat['label']
                    if code in counts:
                        counts[code] += 1
            rows = [(code, n) for code, n in counts.items() if n > 0]
        else:
            if not self.user_info or self.user_info['username'] == 'local':
                return
            rows = self._get_contagem(self.biome, self.project_type, self.user_info['username'],
                                      tile=tile if tile != 'Todos' else None,
                                      ecoregion=eco)

        _clear_layout(self.cnt_grid_layout)
        self.count_labels = {}
        color_map = {code: color for code, _, color in self.classes}
        label_map = {code: label for code, label, _ in self.classes}
        total_f = 0
        for i, (code, n) in enumerate(rows):
            _count_row(self.cnt_grid_layout, i, color_map.get(code, '#888888'),
                       label_map.get(code, code), n)
            total_f += n
        _total_row(self.cnt_grid_layout, len(rows), total_f)
        self.lbl_filtro_total.setText(f'Filtrado: {total_f}')
        self._finish_count_grid(len(rows))
        if tile != 'Todos' or eco is not None:
            self.lbl_total.setText(str(total_f))
            self.pie_widget.set_data([(label_map.get(code, code), n, color_map.get(code, '#888888'))
                                      for code, n in rows if n > 0])
        else:
            self._update_counters()

    def _apply_style(self):
        if not self._layer_ok(self.layer) or not self.classes:
            return
        campo = 'label'
        if self._is_api_project() and self.audit_mode:
            # audit: the auditor's class lives in label_audit (the interpreter's stays
            # in label); colour by the final class so a reclass shows up at once
            campo = 'coalesce("label_audit", "label")'
        for layer in self._sample_layers():
            points = layer is self.point_layer
            cats = []
            for code, label, color in self.classes:
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                if points:
                    sym = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': f'{r},{g},{b},255',
                                                        'outline_color': '30,30,30,220',
                                                        'outline_width': '0.4', 'size': '2.6'})
                else:
                    sym = QgsFillSymbol.createSimple({'color': f'{r},{g},{b},255',
                                                      'outline_color': '50,50,50,200',
                                                      'outline_width': '0.4', 'style': 'solid'})
                cats.append(QgsRendererCategory(code, sym, label))
            if self._is_api_project() and self.audit_mode:
                if points:
                    sym = QgsMarkerSymbol.createSimple({'name': 'cross2', 'color': '255,0,0,255',
                                                        'size': '3.4'})
                else:
                    sym = QgsFillSymbol.createSimple({'color': '255,0,0,90', 'outline_color': '255,0,0,255',
                                                      'outline_width': '0.6', 'style': 'b_diagonal'})
                cats.append(QgsRendererCategory(EXCLUIR_CODE, sym, EXCLUIR_LABEL))
            layer.setRenderer(QgsCategorizedSymbolRenderer(campo, cats))
            layer.triggerRepaint()

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
        if self._is_api_project():
            for layer in self._sample_layers():
                layer.triggerRepaint()
        elif not self._is_local_geopackage:
            layer = self._get_layer()
            if self._layer_ok(layer):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()
        self._refresh_statistics()

    def _manual_refresh(self):
        self._auto_refresh()
        self._refresh_filtros()
        self._log('Mapa atualizado.')

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

    def save_sample(self, geom):
        if not self.user_info:
            self._log('Faça login primeiro.')
            return False
        mode = self.get_draw_mode()
        if self._is_api_project() and mode != 'square':
            # the SQLite package is stored in EPSG:4674 (same SRID as the API table)
            geom = self._vs_to_4674(geom)
        if self._is_api_project():
            if not self.pantanal_vs_locked_cells:
                self._log('Selecione uma célula antes de coletar.')
                return False
            inside = False
            for cell_geom in self.pantanal_vs_locked_cell_geoms:
                if cell_geom.intersects(geom):
                    inside = True
                    break
            if not inside:
                self._log('A amostra está fora das células bloqueadas.')
                return False
        code = self.combo.currentData()
        cls_name = self.combo.currentText()
        if not code:
            return False
        username = self.user_info['username']
        px = self.pixel_size
        if mode == 'point':
            area = None
        elif mode == 'square':
            area = (px * PIXEL_SIZE_M) ** 2
        else:
            geom_copy = QgsGeometry(geom)
            src_crs = (QgsCoordinateReferenceSystem('EPSG:4674') if self._is_api_project()
                       else self.canvas.mapSettings().destinationCrs())
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

        if (not self._is_local_geopackage and not self._is_api_project()
                and username != 'local' and self.biome):
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
            self.total += 1
            self.counts[code] = self.counts.get(code, 0) + 1
        else:
            layer = self.point_layer if mode == 'point' else self._get_layer()
            if not self._layer_ok(layer):
                self._log('Nenhuma camada ativa para salvar.')
                return False
            fn = [f.name() for f in layer.fields()]
            feat = QgsFeature(layer.fields())
            feat.setGeometry(geom)
            a = {}
            today = QDate.currentDate()
            if self._is_api_project():
                a = {k: v for k, v in self._vs_sample_attrs(geom, code, area, px, username, mode).items()
                     if k in fn}
            elif self._is_local_geopackage:
                tile, eco = self._local_intersect(geom)
                if 'tile' in fn and tile:
                    a['tile'] = tile
                if 'ecoregion' in fn and eco:
                    a['ecoregion'] = eco
            if not self._is_api_project():
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
            fid_saved = added[0].id() if added else None
            self._undo_stack.append({
                'provider_fid': fid_saved, 'code': code, 'cls_name': cls_name,
                'geom_wkt': geom.asWkt(), 'srid': None,
                'area': area, 'px': px, 'mode': mode,
            })
            self._redo_stack.clear()
            layer.updateExtents()
            self.canvas.refreshAllLayers()
            self._sync_counts(username)   # recounts from the layer (local GeoPackage / VS package)

        self._update_counters()
        self._refresh_filtros()
        self._refresh_statistics()
        if self._is_api_project():
            self._vs_update_pacote_label()
        self._log(f'#{self.total}  {cls_name}')
        return True

    def _entry_layer(self, entry):
        """Layer an undo/redo entry belongs to (points have their own layer)."""
        if entry.get('mode') == 'point' and self._layer_ok(self.point_layer):
            return self.point_layer
        return self._get_layer()

    def _undo(self):
        if not self._undo_stack:
            self._log('Nada para desfazer.')
            return
        entry = self._undo_stack.pop()
        username = self.user_info['username'] if self.user_info else 'local'
        is_admin = getattr(self, 'is_admin', False) and not self._is_local_geopackage

        if (not self._is_local_geopackage and not self._is_api_project()
                and username != 'local' and self.biome and 'fid' in entry):
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
            layer = self._entry_layer(entry)
            if self._layer_ok(layer) and 'provider_fid' in entry:
                if self._is_api_project():
                    self._vs_register_delete(layer, [entry['provider_fid']])
                layer.dataProvider().deleteFeatures([entry['provider_fid']])
                layer.updateExtents()
                self.canvas.refreshAllLayers()

        self._redo_stack.append(entry)
        self.total = max(0, self.total - 1)
        code = entry.get('code')
        if code and code in self.counts:
            self.counts[code] = max(0, self.counts[code] - 1)
        self._update_counters()
        self._refresh_filtros()
        self._refresh_statistics()
        if self._is_api_project():
            self._vs_update_pacote_label()
        self._log(f'↩ {entry["cls_name"]}')

    def _redo(self):
        if not self._redo_stack:
            self._log('Nada para refazer.')
            return
        entry = self._redo_stack.pop()
        username = self.user_info['username'] if self.user_info else 'local'
        is_admin = getattr(self, 'is_admin', False) and not self._is_local_geopackage

        if (not self._is_local_geopackage and not self._is_api_project()
                and username != 'local' and self.biome):
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
            layer = self._entry_layer(entry)
            if self._layer_ok(layer):
                geom = QgsGeometry.fromWkt(entry['geom_wkt'])
                fn = set(layer.fields().names())
                feat = QgsFeature(layer.fields())
                feat.setGeometry(geom)
                a = {}
                if self._is_api_project():
                    a = {k: v for k, v in self._vs_sample_attrs(
                        geom, entry['code'], entry['area'], entry['px'], username,
                        entry.get('mode')).items() if k in fn}
                else:
                    if self._is_local_geopackage:
                        tile, eco = self._local_intersect(geom)
                        if 'tile' in fn:
                            a['tile'] = tile
                        if 'ecoregion' in fn:
                            a['ecoregion'] = eco
                    if 'label' in fn:
                        a['label'] = entry['code']
                    if 'analyst' in fn:
                        a['analyst'] = username
                    if 'biome' in fn:
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
        code = entry.get('code')
        if code:
            self.counts[code] = self.counts.get(code, 0) + 1
        self._update_counters()
        self._refresh_filtros()
        self._refresh_statistics()
        if self._is_api_project():
            self._vs_update_pacote_label()
        self._log(f'↪ {entry["cls_name"]}')

    def _code_to_label(self, code):
        if code == EXCLUIR_CODE:
            return EXCLUIR_LABEL
        for c, label, _ in self.classes:
            if c == code:
                return label
        return code

    def _sep(self, layout=None, top=4, bottom=4):
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, top, 0, bottom)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        wl.addWidget(line)
        if layout is not None:
            layout.addWidget(w)
        return w

    def _small(self, text):
        l = QLabel(text)
        l.setStyleSheet(f'color:{C_TEXT}; font-size:8pt;')
        return l

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
        if self._is_api_project():
            self._populate_stats_combos_api(analyst_filter)
            return
        config = self.db._get_config(self.biome, self.project_type)
        schema, table = config['schema'], config['table']
        try:
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

                analysts = None
                if self.is_auditor:
                    cur.execute(f"""
                        SELECT DISTINCT analyst FROM {schema}.{table}
                        WHERE biome = %s AND analyst IS NOT NULL
                        ORDER BY analyst
                    """, (biome_sanitized,))
                    analysts = [row[0] for row in cur.fetchall()]
            finally:
                cur.close()
                conn.close()
            eco_map = self.db.get_ecoregion_display_map(self.biome, self.project_type)
            self._fill_stats_combos(tiles, ecos, analysts, eco_map)
        except Exception as e:
            self._log(f'Erro ao carregar os totais: {e}')

    def _populate_stats_combos_local(self, analyst_filter=None):
        layer = self._get_prodes_totals_layer()
        self.session_totals_tabs.setTabVisible(1, layer is not None)
        if layer is None:
            return
        fields = layer.fields().names()
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
        self._fill_stats_combos(sorted(tiles), sorted(ecos), sorted(analysts))

    def _render_stats_grid(self, counts):
        _clear_layout(self.stats_grid_layout)
        color_map = {code: color for code, _, color in self.classes}
        total = 0
        slices = []
        for row_i, (code, count) in enumerate(counts):
            label = self._code_to_label(code)
            color = color_map.get(code, '#888888')
            name, num = _count_row(self.stats_grid_layout, row_i, color, label, count, min_width=30)
            name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            num.setMinimumWidth(30)
            num.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            total += count
            slices.append((label, count, color))

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
            rows = self._get_contagem(
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

    def _on_audit_analyst_changed(self, index):
        analyst = self.audit_analyst_combo.currentText()
        if analyst == 'Todos':
            analyst = None
        self._populate_audit_filters(analyst)
        self._refresh_audit_stats()

    def _populate_audit_filters(self, analyst_filter=None):
        """Fills the Auditoria tab filters, optionally restricted to one analyst."""
        if not self.is_auditor or self._is_local_geopackage or not self.biome:
            return
        if self._is_api_project():
            self._populate_audit_filters_api(analyst_filter)
            return

        try:
            config = self.db._get_config(self.biome, self.project_type)
            schema = config['schema']
            table = config['table']
            biome_sanitized = sanitize_text(self.biome)

            conn = self.db._project_admin_conn(self.biome, self.project_type)
            cur = conn.cursor()
            try:
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
            finally:
                cur.close()
                conn.close()

            eco_map = self.db.get_ecoregion_display_map(self.biome, self.project_type)
            self._fill_audit_combos(analysts, tiles, ecos, analyst_filter, eco_map)
        except Exception as e:
            self._log(f'Erro ao carregar os filtros de auditoria: {e}')

    def _refresh_audit_stats(self):
        """Agreement/disagreement totals of the Auditoria tab for the current filters."""
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
            if self._is_api_project():
                total_audited, agreements, disagreements = self._vs_audit_counts(
                    analyst, tile, eco)
            else:
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
                try:
                    cur.execute(f"""
                        SELECT
                            COUNT(*) AS total_audited,
                            SUM(CASE WHEN label = label_audit THEN 1 ELSE 0 END) AS agreements,
                            SUM(CASE WHEN label != label_audit THEN 1 ELSE 0 END) AS disagreements
                        FROM {schema}.{table}
                        WHERE {where_clause}
                    """, params)
                    row = cur.fetchone()
                finally:
                    cur.close()
                    conn.close()

                total_audited, agreements, disagreements = (
                    (row[0] or 0, row[1] or 0, row[2] or 0) if row else (0, 0, 0))

            self.audit_total_label.setText(str(total_audited))
            self.audit_filtered_label.setText(f'Auditados: {total_audited}')

            slices = []
            if agreements > 0:
                slices.append(('Concordâncias', agreements, C_OK))
            if disagreements > 0:
                slices.append(('Discordâncias', disagreements, C_DANGER))
            self.audit_pie_widget.set_data(slices)

            _clear_layout(self.audit_grid_layout)
            rows = [('Concordâncias', agreements, C_OK), ('Discordâncias', disagreements, C_DANGER)]
            for row_i, (label, count, color) in enumerate(rows):
                num_text = (f'{count} ({count / total_audited * 100:.1f}%)' if total_audited > 0
                            else str(count))
                _count_row(self.audit_grid_layout, row_i, color, label, num_text)
            self.audit_grid_layout.setRowStretch(len(rows), 1)

            self.audit_grid_widget.updateGeometry()

        except Exception as e:
            self._log(f'Erro ao carregar as estatísticas de auditoria: {e}')

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

    def _export_to_wfs(self):
        if not self._is_local_geopackage:
            QMessageBox.warning(self, 'WFS', 'Esta função só está disponível no modo GeoPackage.')
            return

        layers = [l for l in QgsProject.instance().mapLayers().values() if l.type() == Qgis.LayerType.Vector]
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
        dlg.exec()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        self._vs_cleanup_terraclass()
        super().closeEvent(event)
