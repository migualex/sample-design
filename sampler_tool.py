# -*- coding: utf-8 -*-

from qgis.core import (
    QgsGeometry, QgsRectangle, QgsCoordinateTransform,
    QgsCoordinateReferenceSystem, QgsProject, QgsWkbTypes
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

PIXEL_SIZE_M = 10.0   # 10 × 10 m → 100 m²


class SamplerTool(QgsMapTool):

    def __init__(self, canvas, dock):
        super().__init__(canvas)
        self.canvas = canvas
        self.dock   = dock

        self.rubber = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber.setColor(QColor(255, 100, 100, 100))
        self.rubber.setWidth(2)
        self.rubber.setFillColor(QColor(255, 0, 0, 30))

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        self.dock._log('Ferramenta de coleta ATIVADA – clique no mapa')

    def deactivate(self):
        self.rubber.reset(QgsWkbTypes.PolygonGeometry)
        super().deactivate()

    def canvasMoveEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        geom = self._square_geom(point)
        if geom:
            self.rubber.setToGeometry(geom, None)
        else:
            self.rubber.reset(QgsWkbTypes.PolygonGeometry)

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        point = self.toMapCoordinates(event.pos())
        geom = self._square_geom(point)
        if geom is None:
            self.dock._log('Não foi possível criar a geometria – verifique o CRS do mapa')
            return
        self.dock._log(f'Salvando polígono em {point}')
        self.dock.save_sample(geom)

    def _square_geom(self, point):
        """
        Build a 10×10 m square in EPSG:4674 centred on the given point.
        The point is first transformed to EPSG:4674 if needed.
        """
        layer_crs = QgsCoordinateReferenceSystem('EPSG:4674')
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        # Transform point to EPSG:4674
        if canvas_crs != layer_crs:
            try:
                tr = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
                point = tr.transform(point)
            except Exception as e:
                self.dock._log(f'Erro de transformação: {e}')
                return None

        half_side_metres = (self.dock.pixel_size * PIXEL_SIZE_M) / 2.0

        # Approximate degree conversions
        half_dx = half_side_metres / 111320.0
        half_dy = half_side_metres / 110540.0

        x = point.x()
        y = point.y()
        rect = QgsRectangle(x - half_dx, y - half_dy,
                            x + half_dx, y + half_dy)
        return QgsGeometry.fromRect(rect)