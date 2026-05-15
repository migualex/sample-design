# -*- coding: utf-8 -*-
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import (
    QgsPointXY, QgsGeometry, QgsWkbTypes,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject
)
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor, QCursor

PIXEL_SIZE_M = 10.0


class SamplerTool(QgsMapTool):

    def __init__(self, canvas, dock):
        super().__init__(canvas)
        self.canvas  = canvas
        self.dock    = dock
        self.rubber  = None
        self.current = None
        self._init_rubber()
        self.setCursor(QCursor(Qt.CrossCursor))

    def _init_rubber(self):
        if self.rubber:
            self.rubber.reset()
        self.rubber = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self._color_idle()
        self.rubber.setWidth(2)
        self.rubber.setLineStyle(Qt.DashLine)

    def _color_idle(self):
        self.rubber.setColor(QColor(220, 50, 50, 210))
        self.rubber.setFillColor(QColor(220, 50, 50, 30))

    def _color_ok(self):
        self.rubber.setColor(QColor(40, 180, 40, 230))
        self.rubber.setFillColor(QColor(40, 180, 40, 55))

    def _square_geom(self, center):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        merc = QgsCoordinateReferenceSystem('EPSG:3857')
        to_merc   = QgsCoordinateTransform(canvas_crs, merc,        QgsProject.instance())
        to_canvas = QgsCoordinateTransform(merc,        canvas_crs, QgsProject.instance())
        c    = to_merc.transform(center)
        half = self.dock.window_size_m() / 2.0
        x, y = c.x(), c.y()
        pts  = [
            QgsPointXY(x - half, y + half),
            QgsPointXY(x + half, y + half),
            QgsPointXY(x + half, y - half),
            QgsPointXY(x - half, y - half),
        ]
        corners = [to_canvas.transform(p) for p in pts]
        return QgsGeometry.fromPolygonXY([corners])

    def canvasMoveEvent(self, event):
        self.current = self.toMapCoordinates(event.pos())
        self.rubber.setToGeometry(self._square_geom(self.current), None)
        self.rubber.show()

    def canvasPressEvent(self, event):
        if event.button() == Qt.RightButton and self.current:
            geom = self._square_geom(self.current)
            if self.dock.save_sample(geom):
                self._color_ok()
                self.canvas.update()
                QTimer.singleShot(280, lambda: (self._color_idle(), self.canvas.update()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dock.plugin.deactivate_tool()

    def deactivate(self):
        if self.rubber:
            self.rubber.reset()
            self.rubber.hide()
        super().deactivate()

    def isZoomTool(self):  return False
    def isTransient(self): return False
    def isEditTool(self):  return True
