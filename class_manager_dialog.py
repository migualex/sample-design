# -*- coding: utf-8 -*-
"""
class_manager_dialog.py — Gerenciador de classes personalizadas por bioma/usuário.
Salva no banco PostgreSQL e retorna a lista atualizada.
"""

import re

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QListWidget, QListWidgetItem,
    QDialogButtonBox, QColorDialog, QAbstractItemView,
    QFrame, QWidget, QMessageBox
)
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap, QPainter

C_BG     = '#FFFFFF'
C_TEXT   = '#1A1D23'
C_MUTED  = '#6B7280'
C_ACCENT = '#2563EB'
C_BORDER = '#ECEFF3'
C_OK     = '#16A34A'
C_DANGER = '#DC2626'


def _to_code(label: str) -> str:
    """Converte nome legível → código sem acento com underscores."""
    repl = {
        'á':'a','à':'a','ã':'a','â':'a','ä':'a',
        'é':'e','ê':'e','ë':'e','è':'e',
        'í':'i','î':'i','ï':'i','ì':'i',
        'ó':'o','ô':'o','õ':'o','ö':'o','ò':'o',
        'ú':'u','û':'u','ü':'u','ù':'u',
        'ç':'c','ñ':'n',
        'Á':'A','À':'A','Ã':'A','Â':'A',
        'É':'E','Ê':'E','Í':'I','Ó':'O',
        'Ô':'O','Õ':'O','Ú':'U','Ç':'C',
    }
    r = label
    for k, v in repl.items():
        r = r.replace(k, v)
    r = re.sub(r"[^A-Za-z0-9]", '_', r)
    r = re.sub(r'_+', '_', r).strip('_')
    return r


def _color_swatch(hex_color, size=16):
    px = QPixmap(size, size)
    px.fill(QColor(hex_color))
    p = QPainter(px)
    p.setPen(QColor('#00000044'))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(px)


class ClassManagerDialog(QDialog):
    """
    Diálogo para adicionar, remover, recolorir e reordenar classes.
    Se db e username forem fornecidos, salva no banco ao confirmar.
    """

    def __init__(self, classes, db=None, bioma=None, username=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Gerenciar Classes')
        self.setMinimumWidth(460)
        self.setMinimumHeight(500)
        self.db       = db
        self.bioma    = bioma
        self.username = username
        # Cópia local mutável
        self._classes = [list(c) for c in classes]
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog, QWidget {{ background:{C_BG}; color:{C_TEXT};
                                font-family:'Segoe UI',sans-serif; font-size:9pt; }}
            QListWidget {{ border:1.5px solid {C_BORDER}; border-radius:6px;
                           padding:4px; background:{C_BG}; }}
            QListWidget::item {{ padding:5px 6px; border-radius:4px; }}
            QListWidget::item:selected {{ background:#EFF6FF; color:{C_TEXT}; }}
            QLineEdit {{ border:1.5px solid {C_BORDER}; border-radius:6px;
                         padding:5px 10px; background:{C_BG}; }}
            QLineEdit:focus {{ border-color:{C_ACCENT}; }}
            QPushButton {{ border-radius:6px; font-weight:600;
                           padding:5px 14px; border:none; min-height:28px; }}
            QLabel {{ background:transparent; }}
            QGroupBox {{ border:1px solid {C_BORDER}; border-radius:8px;
                         margin-top:8px; padding:10px 10px 8px 10px;
                         font-weight:600; font-size:8.5pt; color:{C_MUTED}; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:10px;
                                padding:0 4px; background:{C_BG}; }}
        """)

        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(16, 16, 16, 16)

        # Título
        ttl = QLabel('Gerenciar Classes')
        ttl.setStyleSheet(f'font-size:12pt; font-weight:700;')
        main.addWidget(ttl)

        sub = QLabel(
            'Adicione, remova ou altere a cor das classes. '
            'As alterações são salvas no banco e aplicadas imediatamente.'
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        main.addWidget(sub)

        # Lista
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setIconSize(QSize(18, 18))
        self.list_widget.itemSelectionChanged.connect(self._on_sel)
        main.addWidget(self.list_widget)

        # Ações sobre item selecionado
        act = QHBoxLayout()
        act.setSpacing(6)

        self.btn_color = QPushButton('🎨  Cor')
        self.btn_color.setEnabled(False)
        self.btn_color.clicked.connect(self._change_color)
        self.btn_color.setStyleSheet(
            f'QPushButton{{background:{C_ACCENT};color:white;}}'
            f'QPushButton:hover{{background:#1D4ED8;}}'
            f'QPushButton:disabled{{background:#D1D5DB;color:#9CA3AF;}}'
        )

        self.btn_remove = QPushButton('🗑  Remover')
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self._remove_class)
        self.btn_remove.setStyleSheet(
            f'QPushButton{{background:{C_DANGER};color:white;}}'
            f'QPushButton:hover{{background:#B91C1C;}}'
            f'QPushButton:disabled{{background:#D1D5DB;color:#9CA3AF;}}'
        )

        self.btn_up   = QPushButton('▲')
        self.btn_down = QPushButton('▼')
        for b in (self.btn_up, self.btn_down):
            b.setFixedWidth(34)
            b.setEnabled(False)
            b.setStyleSheet(
                'QPushButton{background:#F3F4F6;color:#374151;}'
                'QPushButton:hover{background:#E5E7EB;}'
                'QPushButton:disabled{background:#F9FAFB;color:#D1D5DB;}'
            )
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)

        act.addWidget(self.btn_color)
        act.addWidget(self.btn_remove)
        act.addStretch()
        act.addWidget(self.btn_up)
        act.addWidget(self.btn_down)
        main.addLayout(act)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f'color:{C_BORDER};')
        main.addWidget(sep)

        # Adicionar nova classe
        grp = QGroupBox('Adicionar nova classe')
        gl  = QVBoxLayout(grp)
        gl.setSpacing(8)

        gl.addWidget(self._lbl('Nome legível (com acentos):'))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText('Ex: Área Queimada')
        self.edit_name.textChanged.connect(self._on_name_changed)
        gl.addWidget(self.edit_name)

        gl.addWidget(self._lbl('Código gerado (campo "label"):'))
        self.lbl_code = QLabel('')
        self.lbl_code.setStyleSheet(
            f'color:{C_ACCENT}; font-family:monospace; font-size:8.5pt;'
            f'background:#EFF6FF; border-radius:4px; padding:3px 8px;'
        )
        gl.addWidget(self.lbl_code)

        crow = QHBoxLayout()
        crow.setSpacing(8)
        crow.addWidget(self._lbl('Cor:'))
        self._new_color = '#888888'
        self.btn_pick   = QPushButton()
        self.btn_pick.setFixedSize(36, 26)
        self.btn_pick.clicked.connect(self._pick_color)
        self._refresh_color_btn(self.btn_pick, self._new_color)
        crow.addWidget(self.btn_pick)
        crow.addStretch()
        gl.addLayout(crow)

        self.btn_add = QPushButton('＋  Adicionar classe')
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self._add_class)
        self.btn_add.setStyleSheet(
            f'QPushButton{{background:{C_OK};color:white;}}'
            f'QPushButton:hover{{background:#15803D;}}'
            f'QPushButton:disabled{{background:#D1D5DB;color:#9CA3AF;}}'
        )
        gl.addWidget(self.btn_add)
        main.addWidget(grp)

        # OK / Cancelar
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText('Aplicar')
        btns.button(QDialogButtonBox.Ok).setStyleSheet(
            f'QPushButton{{background:{C_ACCENT};color:white;'
            f'padding:6px 18px;border-radius:6px;font-weight:600;border:none;}}'
            f'QPushButton:hover{{background:#1D4ED8;}}'
        )
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            'QPushButton{background:#F3F4F6;color:#374151;'
            'padding:6px 18px;border-radius:6px;font-weight:600;border:none;}'
            'QPushButton:hover{background:#E5E7EB;}'
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        main.addWidget(btns)

    # ── Lista ─────────────────────────────────────────────────────
    def _refresh_list(self, keep=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for code, label, color in self._classes:
            item = QListWidgetItem(_color_swatch(color), label)
            item.setData(Qt.UserRole, color)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        if keep is not None and keep < self.list_widget.count():
            self.list_widget.setCurrentRow(keep)
        self._on_sel()

    def _on_sel(self):
        r = self.list_widget.currentRow()
        n = self.list_widget.count()
        has = r >= 0
        self.btn_color.setEnabled(has)
        self.btn_remove.setEnabled(has)
        self.btn_up.setEnabled(has and r > 0)
        self.btn_down.setEnabled(has and r < n - 1)

    def _change_color(self):
        r = self.list_widget.currentRow()
        if r < 0: return
        c = QColorDialog.getColor(QColor(self._classes[r][2]), self, 'Cor')
        if c.isValid():
            self._classes[r][2] = c.name().upper()
            self._refresh_list(keep=r)

    def _remove_class(self):
        r = self.list_widget.currentRow()
        if r < 0: return
        if QMessageBox.question(
            self, 'Remover', f'Remover "{self._classes[r][1]}"?',
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._classes.pop(r)
            self._refresh_list(keep=min(r, len(self._classes) - 1))

    def _move_up(self):
        r = self.list_widget.currentRow()
        if r > 0:
            self._classes[r], self._classes[r-1] = self._classes[r-1], self._classes[r]
            self._refresh_list(keep=r-1)

    def _move_down(self):
        r = self.list_widget.currentRow()
        if r < len(self._classes) - 1:
            self._classes[r], self._classes[r+1] = self._classes[r+1], self._classes[r]
            self._refresh_list(keep=r+1)

    def _on_name_changed(self, text):
        code = _to_code(text.strip())
        self.lbl_code.setText(code)
        self.btn_add.setEnabled(bool(code))

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._new_color), self, 'Cor')
        if c.isValid():
            self._new_color = c.name().upper()
            self._refresh_color_btn(self.btn_pick, self._new_color)

    def _refresh_color_btn(self, btn, hex_c):
        btn.setStyleSheet(
            f'QPushButton{{background:{hex_c};border:1.5px solid #D1D5DB;border-radius:4px;}}'
            f'QPushButton:hover{{border-color:#9CA3AF;}}'
        )

    def _add_class(self):
        name = self.edit_name.text().strip()
        code = _to_code(name)
        if not code: return
        existing = [c[0] for c in self._classes]
        base = code
        i = 2
        while code in existing:
            code = f'{base}_{i}'; i += 1
        self._classes.append([code, name, self._new_color])
        self._refresh_list(keep=len(self._classes)-1)
        self.edit_name.clear()
        self._new_color = '#888888'
        self._refresh_color_btn(self.btn_pick, self._new_color)

    def _on_accept(self):
        if not self._classes:
            QMessageBox.warning(self, 'Sample Design', 'A lista não pode ficar vazia.')
            return
        # Salva no banco se db disponível
        if self.db and self.bioma and self.username:
            ok, msg = self.db.save_custom_classes(
                self.bioma, self.username, self._classes
            )
            if not ok:
                QMessageBox.warning(self, 'Sample Design',
                    f'Aviso: não foi possível salvar no banco.\n{msg}\n\n'
                    'As alterações serão aplicadas apenas localmente.')
        self.accept()

    def get_classes(self):
        return [tuple(c) for c in self._classes]

    # Helpers
    def _lbl(self, t):
        l = QLabel(t)
        l.setStyleSheet(f'color:{C_MUTED}; font-size:8pt;')
        return l
