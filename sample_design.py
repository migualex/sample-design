# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt

from .sampler_tool import SamplerTool
from .sampler_dock import SamplerDock


class SampleDesign:

    def __init__(self, iface):
        self.iface     = iface
        self.canvas    = iface.mapCanvas()
        self.plugin_dir = os.path.dirname(__file__)
        self.action    = None
        self.dock      = None
        self.tool      = None
        self.prev_tool = None

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icons', 'sample_design_icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, 'Sample Design', self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip('Ativar ferramenta de coleta de amostras')
        self.action.triggered.connect(self.toggle_tool)

        self.iface.addPluginToMenu('&Sample Design', self.action)
        self.iface.addToolBarIcon(self.action)

        # NÃO criamos o dock nem a ferramenta aqui – só quando o ícone for clicado

    def toggle_tool(self, checked):
        if checked:
            # Cria o dock e a ferramenta apenas na primeira ativação
            if self.dock is None:
                self.dock = SamplerDock(self.iface, self)
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
                self.dock.hide()   # oculta inicialmente; será mostrado a seguir
                self.tool = SamplerTool(self.canvas, self.dock)

                # Synchronise initial mode
                self.tool.set_mode(self.dock.get_draw_mode())
                # Connect mode change signal (via the dock's radio buttons)
                self.dock.radio_square.toggled.connect(lambda: self.tool.set_mode(self.dock.get_draw_mode()))
                self.dock.radio_polygon.toggled.connect(lambda: self.tool.set_mode(self.dock.get_draw_mode()))

            self.prev_tool = self.canvas.mapTool()
            self.canvas.setMapTool(self.tool)
            self.dock.show()
        else:
            if self.prev_tool:
                self.canvas.setMapTool(self.prev_tool)
            if self.dock:
                self.dock.hide()

    def deactivate_tool(self):
        self.action.setChecked(False)
        if self.prev_tool:
            self.canvas.setMapTool(self.prev_tool)

    def unload(self):
        self.iface.removePluginMenu('&Sample Design', self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()