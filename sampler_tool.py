# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

from qgis.core import (
    QgsGeometry, QgsRectangle, QgsCoordinateTransform,
    QgsCoordinateReferenceSystem, QgsProject, QgsWkbTypes, Qgis
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

PIXEL_SIZE_M = 10.0


class SamplerTool(QgsMapTool):

    def __init__(self, canvas, dock):
        super().__init__(canvas)
        self.canvas = canvas
        self.dock   = dock
        self.mode   = 'square'

        self.rubber = QgsRubberBand(canvas, Qgis.GeometryType.Polygon)
        self.rubber.setColor(QColor(255, 100, 100, 100))
        self.rubber.setWidth(2)
        self.rubber.setFillColor(QColor(255, 0, 0, 30))

        self.polygon_points = []
        self.polygon_rubber = QgsRubberBand(canvas, Qgis.GeometryType.Line)
        self.polygon_rubber.setColor(QColor(255, 200, 100, 200))
        self.polygon_rubber.setWidth(2)
        self.polygon_rubber.setFillColor(QColor(255, 200, 100, 30))

    def set_mode(self, mode):
        """'square', 'polygon' or 'point'."""
        self.mode = mode
        self.rubber.reset(Qgis.GeometryType.Polygon)
        self._reset_polygon()

    def _reset_polygon(self):
        self.polygon_points.clear()
        self.polygon_rubber.reset(Qgis.GeometryType.Line)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.dock._log('Coleta ativada: clique no mapa.')
        self._reset_polygon()

    def deactivate(self):
        self.rubber.reset(Qgis.GeometryType.Polygon)
        self._reset_polygon()
        super().deactivate()

    def canvasMoveEvent(self, event):
        if self.mode == 'point':
            return
        if self.mode == 'square':
            point = self.toMapCoordinates(event.pixelPoint())
            geom = self._square_geom(point)
            if geom:
                self.rubber.setToGeometry(geom, None)
            else:
                self.rubber.reset(Qgis.GeometryType.Polygon)
        else:
            if self.polygon_points:
                point = self.toMapCoordinates(event.pixelPoint())
                temp_points = self.polygon_points + [point]
                polyline_geom = QgsGeometry.fromPolylineXY(temp_points)
                self.polygon_rubber.setToGeometry(polyline_geom, None)

    def canvasReleaseEvent(self, event):
        if self.mode == 'point':
            if event.button() == Qt.MouseButton.LeftButton:
                point = self.toMapCoordinates(event.pixelPoint())
                self.dock._log(f'Salvando ponto em {point}')
                self.dock.save_sample(QgsGeometry.fromPointXY(point))
            return
        if self.mode == 'square':
            if event.button() == Qt.MouseButton.LeftButton:
                point = self.toMapCoordinates(event.pixelPoint())
                geom = self._square_geom(point)
                if geom is None:
                    self.dock._log('Não foi possível criar a geometria. Verifique o CRS do mapa.')
                    return
                self.dock._log(f'Salvando quadrado em {point}')
                self.dock.save_sample(geom)
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                point = self.toMapCoordinates(event.pixelPoint())
                self.polygon_points.append(point)

                if len(self.polygon_points) >= 2:
                    polyline_geom = QgsGeometry.fromPolylineXY(self.polygon_points)
                    self.polygon_rubber.setToGeometry(polyline_geom, None)

                if len(self.polygon_points) >= 3:
                    polygon_geom = QgsGeometry.fromPolygonXY([self.polygon_points])
                    self.rubber.setToGeometry(polygon_geom, None)
            elif event.button() == Qt.MouseButton.RightButton:
                if len(self.polygon_points) >= 3:

                    polygon_geom = QgsGeometry.fromPolygonXY([self.polygon_points])
                    self.dock._log(f'Salvando polígono com {len(self.polygon_points)} vértices')
                    self.dock.save_sample(polygon_geom)
                else:
                    self.dock._log('O polígono precisa de pelo menos 3 pontos.')
                self._reset_polygon()
                self.rubber.reset(Qgis.GeometryType.Polygon)
                self.polygon_rubber.reset(Qgis.GeometryType.Line)

    def _square_geom(self, point):
        """
        Square of the configured window size in EPSG:4674, centred on the point.
        """
        layer_crs = QgsCoordinateReferenceSystem('EPSG:4674')
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        if canvas_crs != layer_crs:
            try:
                tr = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
                point = tr.transform(point)
            except Exception as e:
                self.dock._log(f'Erro de transformação: {e}')
                return None

        half_side_metres = (self.dock.pixel_size * PIXEL_SIZE_M) / 2.0

        half_dx = half_side_metres / 111320.0
        half_dy = half_side_metres / 110540.0

        x = point.x()
        y = point.y()
        rect = QgsRectangle(x - half_dx, y - half_dy,
                            x + half_dx, y + half_dy)
        return QgsGeometry.fromRect(rect)
