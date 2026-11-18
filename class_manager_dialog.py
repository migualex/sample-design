# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QColor, QPalette
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QApplication, QColorDialog, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .db_manager import sanitize_text as _to_code   # same rule used for the "label" codes


def _dark_theme():
    app = QApplication.instance()
    return bool(app) and app.palette().color(QPalette.ColorRole.Window).lightness() < 128


# same palette as the dock (sampler_dock.py)
if _dark_theme():
    C_BG, C_SURFACE, C_BORDER, C_TEXT, C_MUTED = '#2B2B2B', '#363636', '#4A4A4A', '#E8E8E8', '#A8A8A8'
    C_SELECT = '#3A4A57'
    C_DISABLED_BG, C_DISABLED_TXT = '#3A3A3A', '#7A7A7A'
    C_BTN_HOVER = '#5B6B7A'
else:
    C_BG, C_SURFACE, C_BORDER, C_TEXT, C_MUTED = '#FAFBFC', '#FFFFFF', '#E8ECF0', '#2D3142', '#8A93A2'
    C_SELECT = '#EAF4FA'
    C_DISABLED_BG, C_DISABLED_TXT = '#E2E8F0', '#A0AEC0'
    C_BTN_HOVER = '#2D3142'
C_STEEL = '#7EB8D4'
C_LINK = '#5B9BBF'
C_ROSE = '#D4908A'

_BTN_OUTLINE = f"""
    QPushButton {{
        background: {C_SURFACE}; color: {C_TEXT}; border: 1.5px solid {C_BORDER};
        border-radius: 7px; font-size: 8.5pt; font-weight: 600; padding: 0 12px; min-height: 30px;
    }}
    QPushButton:hover {{ background: {C_BTN_HOVER}; color: #FFFFFF; border-color: {C_BTN_HOVER}; }}
    QPushButton:disabled {{ background: transparent; color: #B8C0CC; border-color: {C_BORDER}; }}
"""


def _pill(bg):
    return f"""
        QPushButton {{
            background: {bg}; color: #FFFFFF; border: none; border-radius: 7px;
            font-size: 9pt; font-weight: 600; padding: 0 18px; min-height: 32px;
        }}
        QPushButton:hover {{ background: {bg}CC; }}
        QPushButton:pressed {{ background: {bg}99; }}
        QPushButton:disabled {{ background: {C_DISABLED_BG}; color: {C_DISABLED_TXT}; }}
    """


def _swatch_css(color, size=14):
    return (f'background:{color}; border:1px solid rgba(0,0,0,60); border-radius:{size // 4}px;'
            f'min-width:{size}px; max-width:{size}px; min-height:{size}px; max-height:{size}px;')


class _ClassRow(QWidget):
    """List row: colour swatch, class name and its code."""

    def __init__(self, code, label, color, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)
        sw = QLabel()
        sw.setStyleSheet(_swatch_css(color))
        name = QLabel(label)
        name.setStyleSheet(f'color:{C_TEXT}; font-size:9pt; background:transparent;')
        cod = QLabel(code)
        cod.setStyleSheet(f'color:{C_MUTED}; font-size:7.5pt; font-family:Consolas,monospace;'
                          'background:transparent;')
        lay.addWidget(sw)
        lay.addWidget(name, 1)
        lay.addWidget(cod)


class ClassManagerDialog(QDialog):
    """
    Edits the class list of a project. save_fn(classes) -> (ok, message) stores it
    (API or PostgreSQL); the dialog only closes when the save succeeds.
    """

    def __init__(self, classes, save_fn=None, parent=None, subtitle=None):
        super().__init__(parent)
        self.setWindowTitle('Gerenciar Classes')
        self.setMinimumSize(580, 560)
        self.save_fn = save_fn
        self._subtitle = subtitle
        self._classes = [list(c) for c in classes]
        self._new_color = '#888888'
        self._build_ui()
        self._refresh_list()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{C_BG}; }}
            QWidget {{ color:{C_TEXT}; font-family:'Segoe UI','Inter',sans-serif; font-size:9pt; }}
            QLabel {{ background:transparent; }}
            QListWidget {{ background:{C_SURFACE}; border:1px solid {C_BORDER}; border-radius:8px;
                           padding:4px; outline:0; }}
            QListWidget::item {{ border-radius:6px; margin:1px 0; }}
            QListWidget::item:hover {{ background:{C_SELECT}; }}
            QListWidget::item:selected {{ background:{C_SELECT}; border:1px solid {C_STEEL}; }}
            QLineEdit {{ background:{C_SURFACE}; border:1.5px solid {C_BORDER}; border-radius:7px;
                         padding:6px 10px; font-size:9pt; }}
            QLineEdit:focus {{ border-color:{C_STEEL}; }}
            QFrame#card {{ background:{C_SURFACE}; border:1px solid {C_BORDER}; border-radius:8px; }}
        """)
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 18, 20, 16)
        main.setSpacing(10)

        ttl = QLabel('Classes do projeto')
        ttl.setStyleSheet('font-size:13pt; font-weight:700;')
        main.addWidget(ttl)
        sub = QLabel(self._subtitle or (
            'Adicione, remova, reordene ou mude a cor das classes. Vale para todos os usuários do projeto.'))
        sub.setWordWrap(True)
        sub.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        main.addWidget(sub)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_sel)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._change_color())
        main.addWidget(self.list_widget, 1)

        act = QHBoxLayout()
        act.setSpacing(6)
        self.btn_color = QPushButton('Alterar cor')
        self.btn_remove = QPushButton('Remover')
        self.btn_up = QPushButton('▲')
        self.btn_down = QPushButton('▼')
        self.btn_up.setToolTip('Subir')
        self.btn_down.setToolTip('Descer')
        for b in (self.btn_color, self.btn_remove, self.btn_up, self.btn_down):
            b.setStyleSheet(_BTN_OUTLINE)
            b.setEnabled(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        for b in (self.btn_up, self.btn_down):
            b.setFixedWidth(40)
        self.btn_color.clicked.connect(self._change_color)
        self.btn_remove.clicked.connect(self._remove_class)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)
        act.addWidget(self.btn_color)
        act.addWidget(self.btn_remove)
        act.addStretch()
        act.addWidget(self.btn_up)
        act.addWidget(self.btn_down)
        main.addLayout(act)

        card = QFrame()
        card.setObjectName('card')
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(6)
        lbl_new = QLabel('Nova classe')
        lbl_new.setStyleSheet(f'color:{C_MUTED}; font-size:8pt; font-weight:700;')
        cl.addWidget(lbl_new)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText('Nome da classe, ex.: Área Queimada')
        self.edit_name.textChanged.connect(self._on_name_changed)
        self.edit_name.returnPressed.connect(self._add_class)
        self.btn_pick = QPushButton()
        self.btn_pick.setFixedSize(34, 32)
        self.btn_pick.setToolTip('Cor da nova classe')
        self.btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick.clicked.connect(self._pick_color)
        self._refresh_color_btn(self.btn_pick, self._new_color)
        self.btn_add = QPushButton('Adicionar')
        self.btn_add.setStyleSheet(_pill(C_STEEL))
        self.btn_add.setEnabled(False)
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_class)
        row.addWidget(self.edit_name, 1)
        row.addWidget(self.btn_pick)
        row.addWidget(self.btn_add)
        cl.addLayout(row)
        self.lbl_code = QLabel('')
        self.lbl_code.setStyleSheet(f'color:{C_MUTED}; font-size:7.5pt;')
        cl.addWidget(self.lbl_code)
        main.addWidget(card)

        foot = QHBoxLayout()
        self.lbl_count = QLabel('')
        self.lbl_count.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        foot.addWidget(self.lbl_count)
        foot.addStretch()
        btn_cancel = QPushButton('Cancelar')
        btn_cancel.setStyleSheet(_BTN_OUTLINE)
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton('Salvar')
        btn_ok.setStyleSheet(_pill(C_LINK))
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_accept)
        foot.addWidget(btn_cancel)
        foot.addWidget(btn_ok)
        main.addLayout(foot)

    def _refresh_list(self, keep=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for code, label, color in self._classes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, color)
            item.setToolTip(f'{label}\nCódigo: {code}\nDuplo clique para mudar a cor.')
            item.setSizeHint(QSize(0, 34))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, _ClassRow(code, label, color))
        self.list_widget.blockSignals(False)
        if keep is not None and 0 <= keep < self.list_widget.count():
            self.list_widget.setCurrentRow(keep)
        n = len(self._classes)
        self.lbl_count.setText(f'{n} classe{"s" if n != 1 else ""}')
        self._on_sel()

    def _on_sel(self):
        r = self.list_widget.currentRow()
        n = self.list_widget.count()
        has = r >= 0 and bool(self.list_widget.selectedItems())
        self.btn_color.setEnabled(has)
        self.btn_remove.setEnabled(has)
        self.btn_up.setEnabled(has and r > 0)
        self.btn_down.setEnabled(has and r < n - 1)

    # ------------------------------------------------------------------ actions
    def _change_color(self):
        r = self.list_widget.currentRow()
        if r < 0:
            return
        c = QColorDialog.getColor(QColor(self._classes[r][2]), self, 'Cor da classe')
        if c.isValid():
            self._classes[r][2] = c.name().upper()
            self._refresh_list(keep=r)

    def _remove_class(self):
        r = self.list_widget.currentRow()
        if r < 0:
            return
        if QMessageBox.question(
                self, 'Remover classe', f'Remover a classe "{self._classes[r][1]}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._classes.pop(r)
            self._refresh_list(keep=min(r, len(self._classes) - 1))

    def _move_up(self):
        r = self.list_widget.currentRow()
        if r > 0:
            self._classes[r], self._classes[r - 1] = self._classes[r - 1], self._classes[r]
            self._refresh_list(keep=r - 1)

    def _move_down(self):
        r = self.list_widget.currentRow()
        if 0 <= r < len(self._classes) - 1:
            self._classes[r], self._classes[r + 1] = self._classes[r + 1], self._classes[r]
            self._refresh_list(keep=r + 1)

    def _on_name_changed(self, text):
        code = _to_code(text.strip())
        self.lbl_code.setText(f'Código: {code}' if code else '')
        self.btn_add.setEnabled(bool(code))

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._new_color), self, 'Cor da nova classe')
        if c.isValid():
            self._new_color = c.name().upper()
            self._refresh_color_btn(self.btn_pick, self._new_color)

    @staticmethod
    def _refresh_color_btn(btn, hex_c):
        btn.setStyleSheet(
            f'QPushButton{{background:{hex_c};border:1.5px solid {C_BORDER};border-radius:7px;}}'
            f'QPushButton:hover{{border-color:{C_STEEL};}}')

    def _add_class(self):
        name = self.edit_name.text().strip()
        code = _to_code(name)
        if not code:
            return
        existing = [c[0] for c in self._classes]
        base, i = code, 2
        while code in existing:
            code = f'{base}_{i}'
            i += 1
        self._classes.append([code, name, self._new_color])
        self._refresh_list(keep=len(self._classes) - 1)
        self.list_widget.scrollToBottom()
        self.edit_name.clear()
        self._new_color = '#888888'
        self._refresh_color_btn(self.btn_pick, self._new_color)

    def _on_accept(self):
        if not self._classes:
            QMessageBox.warning(self, 'Sample Design', 'A lista não pode ficar vazia.')
            return
        if self.save_fn is not None:
            ok, msg = self.save_fn(self.get_classes())
            if not ok:
                QMessageBox.warning(self, 'Sample Design',
                                    f'Não foi possível salvar as classes.\n\n{msg}')
                return
        self.accept()

    def get_classes(self):
        return [tuple(c) for c in self._classes]
