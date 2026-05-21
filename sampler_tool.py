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
        self.mode   = 'square'          # updated from dock

        self.rubber = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber.setColor(QColor(255, 100, 100, 100))
        self.rubber.setWidth(2)
        self.rubber.setFillColor(QColor(255, 0, 0, 30))

        # Polygon drawing state
        self.polygon_points = []
        self.polygon_rubber = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.polygon_rubber.setColor(QColor(255, 200, 100, 200))
        self.polygon_rubber.setWidth(2)
        self.polygon_rubber.setFillColor(QColor(255, 200, 100, 30))

    def set_mode(self, mode):
        self.mode = mode
        self._reset_polygon()

    def _reset_polygon(self):
        self.polygon_points.clear()
        self.polygon_rubber.reset(QgsWkbTypes.LineGeometry)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        self.dock._log('Ferramenta de coleta ATIVADA – clique no mapa')
        self._reset_polygon()

    def deactivate(self):
        self.rubber.reset(QgsWkbTypes.PolygonGeometry)
        self._reset_polygon()
        super().deactivate()

    def canvasMoveEvent(self, event):
        if self.mode == 'square':
            point = self.toMapCoordinates(event.pos())
            geom = self._square_geom(point)
            if geom:
                self.rubber.setToGeometry(geom, None)
            else:
                self.rubber.reset(QgsWkbTypes.PolygonGeometry)
        else:   # polygon mode - update temporary line
            if self.polygon_points:
                point = self.toMapCoordinates(event.pos())
                temp_points = self.polygon_points + [point]
                polyline_geom = QgsGeometry.fromPolylineXY(temp_points)
                self.polygon_rubber.setToGeometry(polyline_geom, None)

    def canvasReleaseEvent(self, event):
        if self.mode == 'square':
            if event.button() == Qt.LeftButton:
                point = self.toMapCoordinates(event.pos())
                geom = self._square_geom(point)
                if geom is None:
                    self.dock._log('Não foi possível criar a geometria – verifique o CRS do mapa')
                    return
                self.dock._log(f'Salvando quadrado em {point}')
                self.dock.save_sample(geom)
        else:   # polygon mode
            if event.button() == Qt.LeftButton:
                point = self.toMapCoordinates(event.pos())
                self.polygon_points.append(point)
                # Update rubber band line
                if len(self.polygon_points) >= 2:
                    polyline_geom = QgsGeometry.fromPolylineXY(self.polygon_points)
                    self.polygon_rubber.setToGeometry(polyline_geom, None)
                # Also show a "preview" polygon if enough points
                if len(self.polygon_points) >= 3:
                    polygon_geom = QgsGeometry.fromPolygonXY([self.polygon_points])
                    self.rubber.setToGeometry(polygon_geom, None)
            elif event.button() == Qt.RightButton:
                if len(self.polygon_points) >= 3:
                    # Close the polygon and save
                    polygon_geom = QgsGeometry.fromPolygonXY([self.polygon_points])
                    self.dock._log(f'Salvando polígono com {len(self.polygon_points)} vértices')
                    self.dock.save_sample(polygon_geom)
                else:
                    self.dock._log('Polígono precisa de pelo menos 3 pontos.')
                self._reset_polygon()
                self.rubber.reset(QgsWkbTypes.PolygonGeometry)
                self.polygon_rubber.reset(QgsWkbTypes.LineGeometry)

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