# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# Layer-group navigation (from the "Connect" plugin), used only in the
# API projects (Pantanal VS and Amazônia NF). The panel lives in the "Connect" tab:
#
#   • the BDC image year subgroups (2026, 2025, 2024) are added automatically;
#   • other groups can be added from the legend context menu;
#   • ↑ / ↓ show the previous/next group (one visible at a time);
#   • F9 switches to/from the "Connect" tab (on_f9 callback set by the dock).
#
# Keys are only captured with the QGIS main window active, no modal dialog
# open and focus outside text fields, lists and combo boxes, so the arrows
# keep working there.

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEvent, QObject, Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QComboBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPlainTextEdit, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)
from qgis.core import Qgis, QgsLayerTreeGroup
# QAction lives in QtWidgets on Qt5 and in QtGui on Qt6 (QGIS 4)
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

# Sample Design palette (same values as sampler_dock.py)
C_ATIVO = '#7EB8D4'
C_INATIVO = '#A0AEC0'
C_ITEM_ATIVO = '#5B9BBF'

_TEXT_WIDGETS = (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
                 QAbstractItemView)


class ConnectNav(QObject):

    def __init__(self, iface, btn_style='', parent=None):
        super().__init__(parent)
        self.iface = iface
        self._btn_style = btn_style
        self._groups = []  # QgsLayerTreeGroup, in navigation order
        self._current = -1
        self._enabled = False
        self._status = None
        self.on_f9 = None            # set by the dock: switches to the "Connect" tab
        self.panel = self._build_panel()
        QApplication.instance().installEventFilter(self)
        try:
            iface.layerTreeView().contextMenuAboutToShow.connect(self._add_context_menu)
        except Exception:
            pass

    # ------------------------------------------------------------------ UI
    def _build_panel(self):
        box = QWidget()
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        head = QHBoxLayout()
        ttl = QLabel('Navegação de imagens')
        ttl.setStyleSheet('font-size:9.5pt; font-weight:700;')
        keys = QLabel('↑ ↓ alternam · F9 volta à Coleta')
        keys.setStyleSheet('color:#8A93A2; font-size:7.5pt;')
        head.addWidget(ttl)
        head.addStretch()
        head.addWidget(keys)
        lay.addLayout(head)

        self.list = QListWidget()
        self.list.setObjectName('lista_connect')
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.setMinimumHeight(70)
        self.list.setMaximumHeight(120)
        self.list.setToolTip('Duplo clique mostra o grupo; arraste para reordenar.')
        self.list.setStyleSheet('QListWidget { border:1px solid #E2E8F0; border-radius:6px; padding:2px; }'
                                'QListWidget::item { padding:3px; font-size:8.5pt; }')
        self.list.itemDoubleClicked.connect(self._jump_to_item)
        self.list.model().rowsMoved.connect(self._order_from_list)
        lay.addWidget(self.list)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_prev = QPushButton('▲ Anterior')
        self.btn_next = QPushButton('▼ Próxima')
        self.btn_remove = QPushButton('Remover')
        for b in (self.btn_prev, self.btn_next, self.btn_remove):
            if self._btn_style:
                b.setStyleSheet(self._btn_style)
            row.addWidget(b)
        self.btn_prev.clicked.connect(lambda: self.navigate(-1))
        self.btn_next.clicked.connect(lambda: self.navigate(1))
        self.btn_remove.clicked.connect(self._remove_selected)
        lay.addLayout(row)

        dica = QLabel('Para incluir outro grupo: botão direito nele na legenda → '
                      '"Connect: Adicionar grupo".')
        dica.setWordWrap(True)
        dica.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        dica.setStyleSheet('color:#8A93A2; font-size:7.5pt;')
        lay.addWidget(dica)
        self._paint_current()
        return box

    def _status_label(self):
        if self._status is None:
            self._status = QLabel('')
            try:
                self.iface.mainWindow().statusBar().insertWidget(0, self._status)
            except Exception:
                pass
        return self._status

    # ------------------------------------------------------------ state
    def set_enabled(self, enabled):
        """Turns navigation (keys, context menu, status label) on/off."""
        self._enabled = bool(enabled)
        self.panel.setEnabled(self._enabled)
        if not self._enabled:
            self.clear()
        self._paint_current()

    def _prune(self):
        vivos = [g for g in self._groups if not sip.isdeleted(g) and g.parent() is not None]
        if len(vivos) != len(self._groups):
            atual = self._groups[self._current] if 0 <= self._current < len(self._groups) else None
            self._groups = vivos
            self._current = vivos.index(atual) if atual in vivos else -1
            self._refresh_list()
            self._paint_current()

    def set_groups(self, groups, show_first=True):
        """Replaces the list (e.g. image year subgroups) and shows the first one."""
        self._groups = [g for g in groups if g is not None and not sip.isdeleted(g)]
        self._current = -1
        for g in self._groups:
            g.setItemVisibilityChecked(False)
        if show_first and self._groups:
            self._current = 0
            self._groups[0].setItemVisibilityChecked(True)
        self._refresh_list()
        self._paint_current()

    def add_group(self, group):
        self._prune()
        if group in self._groups:
            return
        self._groups.append(group)
        group.setItemVisibilityChecked(False)
        self._refresh_list()
        self.iface.messageBar().pushMessage(
            'Sample Design', f"Grupo '{group.name()}' incluído na navegação.",
            level=Qgis.Success, duration=2)

    def remove_group(self, group):
        self._prune()
        if group not in self._groups:
            return
        idx = self._groups.index(group)
        self._groups.pop(idx)
        if idx == self._current:
            self._current = -1
        elif idx < self._current:
            self._current -= 1
        self._refresh_list()
        self._paint_current()

    def clear(self):
        self._groups = []
        self._current = -1
        self._refresh_list()
        self._paint_current()

    def navigate(self, direction):
        self._prune()
        if not self._groups:
            self.iface.messageBar().pushMessage(
                'Sample Design', 'Nenhum grupo na navegação de imagens.',
                level=Qgis.Warning, duration=2)
            return
        if 0 <= self._current < len(self._groups):
            self._groups[self._current].setItemVisibilityChecked(False)
        if self._current < 0:
            self._current = 0 if direction > 0 else len(self._groups) - 1
        else:
            self._current = (self._current + direction) % len(self._groups)
        self._show_current()

    def _show_current(self):
        g = self._groups[self._current]
        g.setItemVisibilityChecked(True)
        # the parent group ("Imagens BDC — Tile ...") must be visible too
        p = g.parent()
        while isinstance(p, QgsLayerTreeGroup) and p.parent() is not None:
            p.setItemVisibilityChecked(True)
            p = p.parent()
        self.iface.mapCanvas().refresh()
        self._refresh_list()
        self._paint_current()

    # ------------------------------------------------------------ list
    def _refresh_list(self):
        self.list.blockSignals(True)
        self.list.clear()
        for i, g in enumerate(self._groups):
            if sip.isdeleted(g):
                continue
            it = QListWidgetItem(('▶ ' if i == self._current else '   ') + self._label(g))
            it.setData(Qt.ItemDataRole.UserRole, i)
            if i == self._current:
                it.setForeground(QColor(C_ITEM_ATIVO))
            self.list.addItem(it)
        if 0 <= self._current < self.list.count():
            self.list.setCurrentRow(self._current)
        self.list.blockSignals(False)

    @staticmethod
    def _label(g):
        p = g.parent()
        if isinstance(p, QgsLayerTreeGroup) and p.parent() is not None:
            return f'{g.name()}  ·  {p.name()}'
        return g.name()

    def _order_from_list(self, *args):
        atual = self._groups[self._current] if 0 <= self._current < len(self._groups) else None
        nova = []
        for r in range(self.list.count()):
            i = self.list.item(r).data(Qt.ItemDataRole.UserRole)
            if isinstance(i, int) and 0 <= i < len(self._groups):
                nova.append(self._groups[i])
        if len(nova) == len(self._groups):
            self._groups = nova
            self._current = nova.index(atual) if atual in nova else -1
        self._refresh_list()

    def _jump_to_item(self, item):
        self._prune()
        i = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(i, int) or not 0 <= i < len(self._groups):
            return
        if 0 <= self._current < len(self._groups):
            self._groups[self._current].setItemVisibilityChecked(False)
        self._current = i
        self._show_current()

    def _remove_selected(self):
        it = self.list.currentItem()
        if it is None:
            return
        i = it.data(Qt.ItemDataRole.UserRole)
        if isinstance(i, int) and 0 <= i < len(self._groups):
            self.remove_group(self._groups[i])

    def _paint_current(self):
        # the active group is marked (▶) in the list and shown on the QGIS status bar
        ativo = 0 <= self._current < len(self._groups)
        if self._enabled and ativo:
            lbl = self._status_label()
            lbl.setText(f'  {self._label(self._groups[self._current])}  ')
            lbl.setStyleSheet(f'color:white; background:{C_ATIVO}; font-size:10px; '
                              'padding:2px 10px; border-radius:3px; font-weight:bold;')
            lbl.setVisible(True)
        elif self._status is not None:
            self._status.setVisible(False)

    # ------------------------------------------------------- legend
    def _add_context_menu(self, menu):
        if not self._enabled:
            return
        try:
            nodes = self.iface.layerTreeView().selectedNodes()
        except Exception:
            return
        self._prune()
        grupos = [n for n in nodes if isinstance(n, QgsLayerTreeGroup)]
        add = [g for g in grupos if g not in self._groups]
        rem = [g for g in grupos if g in self._groups]
        if not add and not rem:
            return
        menu.addSeparator()
        if add:
            a = QAction('Connect: Adicionar grupo' if len(add) == 1
                        else f'Connect: Adicionar {len(add)} grupos', menu)
            a.triggered.connect(lambda: [self.add_group(g) for g in add])
            menu.addAction(a)
        if rem:
            r = QAction('Connect: Remover grupo' if len(rem) == 1
                        else f'Connect: Remover {len(rem)} grupos', menu)
            r.triggered.connect(lambda: [self.remove_group(g) for g in rem])
            menu.addAction(r)

    # --------------------------------------------------------- keyboard
    def _keys_allowed(self):
        if not self._enabled or QApplication.activeModalWidget() is not None:
            return False
        if QApplication.activeWindow() is not self.iface.mainWindow():
            return False
        return not isinstance(QApplication.focusWidget(), _TEXT_WIDGETS)

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key not in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_F9):
            return False
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier |
                                Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.MetaModifier):
            return False
        if not self._keys_allowed():
            return False
        if key == Qt.Key.Key_F9:
            if self.on_f9 is not None:
                self.on_f9()
            return True
        if not self._groups:
            return False  # no groups: let QGIS handle the arrows
        self.navigate(1 if key == Qt.Key.Key_Down else -1)
        return True

    # ------------------------------------------------------------ teardown
    def unload(self):
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        try:
            self.iface.layerTreeView().contextMenuAboutToShow.disconnect(self._add_context_menu)
        except Exception:
            pass
        if self._status is not None:
            try:
                self.iface.mainWindow().statusBar().removeWidget(self._status)
                self._status.deleteLater()
            except Exception:
                pass
            self._status = None
