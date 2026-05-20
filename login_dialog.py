# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QFrame,
    QStackedWidget, QWidget, QMessageBox, QCheckBox
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap

from .db_config import BIOMAS
from .db_manager import DBManager

C_BG      = '#FAFBFC'
C_SURFACE = '#FFFFFF'
C_TEXT    = '#2D3142'
C_MUTED   = '#8A93A2'
C_BORDER  = '#E8ECF0'
C_FOCUS   = '#7EB8D4'
C_BTN_PRI = '#7EB8D4'
C_BTN_SEC = '#9BBFA8'
C_ERR     = '#D97070'
C_LINK    = '#5B9BBF'


def _field_css():
    return f"""
        QLineEdit, QComboBox {{
            background: {C_SURFACE};
            border: 1.5px solid {C_BORDER};
            border-radius: 7px;
            padding: 7px 12px;
            color: {C_TEXT};
            font-size: 9.5pt;
        }}
        QLineEdit:focus, QComboBox:focus  {{ border-color: {C_FOCUS}; }}
        QLineEdit:hover, QComboBox:hover  {{ border-color: #C5CDD8; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
    """


def _pill(color, txt='#FFFFFF'):
    return f"""
        QPushButton {{
            background: {color}; color: {txt};
            border: none; border-radius: 7px;
            font-size: 9.5pt; font-weight: 600;
            padding: 8px 16px;
        }}
        QPushButton:hover   {{ background: {color}CC; }}
        QPushButton:pressed {{ background: {color}99; }}
    """


class LoginDialog(QDialog):

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db           = db
        self.user_info    = None
        self.biome        = None
        self.project_type = None

        self.setWindowTitle('Sample Design')
        self.setMinimumWidth(360)
        self.setMaximumWidth(400)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet(f"""
            QDialog  {{ background: {C_BG}; }}
            QWidget  {{ background: {C_BG}; color: {C_TEXT};
                        font-family: 'Segoe UI', 'Inter', sans-serif; }}
            QLabel   {{ background: transparent; }}
            QCheckBox {{ color: {C_TEXT}; font-size: 9pt; }}
            {_field_css()}
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 30, 32, 26)
        root.setSpacing(0)

        # ── Logo + título ────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path  = os.path.join(plugin_dir, 'icons', 'sample_design_icon.png')
        if os.path.exists(icon_path):
            ico_lbl = QLabel()
            px = QPixmap(icon_path).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ico_lbl.setPixmap(px)
            ico_lbl.setFixedSize(36, 36)
            hdr.addWidget(ico_lbl)

        col = QVBoxLayout()
        col.setSpacing(1)
        t1 = QLabel('Sample Design')
        t1.setStyleSheet(f'font-size: 15pt; font-weight: 700; color: {C_TEXT}; letter-spacing: -0.4px;')
        t2 = QLabel('Coleta de Amostras')
        t2.setStyleSheet(f'font-size: 8.5pt; color: {C_MUTED};')
        col.addWidget(t1)
        col.addWidget(t2)
        hdr.addLayout(col)
        hdr.addStretch()
        root.addLayout(hdr)

        root.addSpacing(22)
        root.addWidget(self._sep())
        root.addSpacing(18)

        # ── Stack ────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet('QStackedWidget { background: transparent; }')
        self.stack.addWidget(self._page_login())
        self.stack.addWidget(self._page_register())
        root.addWidget(self.stack)

    def _page_login(self):
        pg  = QWidget()
        lay = QVBoxLayout(pg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(self._lbl('Usuário'))
        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText('nome de usuário')
        self.edit_user.setMinimumHeight(36)
        lay.addWidget(self.edit_user)

        lay.addWidget(self._lbl('Senha'))
        self.edit_pass = QLineEdit()
        self.edit_pass.setPlaceholderText('••••••••')
        self.edit_pass.setEchoMode(QLineEdit.Password)
        self.edit_pass.setMinimumHeight(36)
        self.edit_pass.returnPressed.connect(self._do_login)
        lay.addWidget(self.edit_pass)

        lay.addWidget(self._lbl('Bioma'))
        self.combo_bioma = QComboBox()
        self.combo_bioma.setMinimumHeight(36)
        self.combo_bioma.addItems(['Amazônia', 'Pantanal'])
        self.combo_bioma.currentIndexChanged.connect(self._on_biome_changed)
        lay.addWidget(self.combo_bioma)

        lay.addWidget(self._lbl('Projeto'))
        self.combo_projeto = QComboBox()
        self.combo_projeto.setMinimumHeight(36)
        self.combo_projeto.addItems(['Prodes', 'Vegetação Secundária'])
        lay.addWidget(self.combo_projeto)

        lay.addSpacing(8)

        self.lbl_err = QLabel('')
        self.lbl_err.setStyleSheet(f'color: {C_ERR}; font-size: 8pt;')
        self.lbl_err.setWordWrap(True)
        lay.addWidget(self.lbl_err)

        lay.addSpacing(4)
        btn = QPushButton('Entrar')
        btn.setMinimumHeight(38)
        btn.setStyleSheet(_pill(C_BTN_PRI))
        btn.clicked.connect(self._do_login)
        lay.addWidget(btn)

        lay.addSpacing(16)
        lay.addWidget(self._sep())
        lay.addSpacing(12)

        row = QHBoxLayout()
        row.addWidget(self._small('Ainda não tem acesso?'))
        btn2 = QPushButton('Criar conta')
        btn2.setFlat(True)
        btn2.setCursor(Qt.PointingHandCursor)
        btn2.setStyleSheet(
            f'color:{C_LINK}; font-weight:600; font-size:8.5pt;'
            f'border:none; background:transparent; padding:0;'
        )
        btn2.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        row.addWidget(btn2)
        row.addStretch()
        lay.addLayout(row)
        return pg

    def _on_biome_changed(self, idx):
        # All biomes now have both project types, so always visible
        pass

    def _page_register(self):
        pg  = QWidget()
        lay = QVBoxLayout(pg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        t = QLabel('Criar conta')
        t.setStyleSheet(f'font-size: 11pt; font-weight: 700; color: {C_TEXT};')
        lay.addWidget(t)
        lay.addSpacing(4)

        for attr, label, hint in [
            ('edit_reg_nome', 'Nome completo',  'Ana Lima'),
            ('edit_reg_user', 'Usuário',        'ana.lima  (sem espaços)'),
            ('edit_reg_pass', 'Senha',          'mínimo 6 caracteres'),
            ('edit_reg_pass2','Confirmar senha','••••••••'),
        ]:
            lay.addWidget(self._lbl(label))
            field = QLineEdit()
            field.setPlaceholderText(hint)
            field.setMinimumHeight(36)
            if 'pass' in attr:
                field.setEchoMode(QLineEdit.Password)
            setattr(self, attr, field)
            lay.addWidget(field)
            if attr != 'edit_reg_pass2':
                lay.addSpacing(2)

        lay.addSpacing(2)
        lay.addWidget(self._lbl('Bioma principal'))
        self.combo_reg_bioma = QComboBox()
        self.combo_reg_bioma.setMinimumHeight(36)
        self.combo_reg_bioma.addItems(['Amazônia', 'Pantanal'])
        lay.addWidget(self.combo_reg_bioma)

        # Auditor checkbox
        self.chk_auditor = QCheckBox('Auditor')
        self.chk_auditor.setStyleSheet(f'QCheckBox {{ color: {C_TEXT}; font-size: 9pt; }}')
        lay.addWidget(self.chk_auditor)

        lay.addSpacing(6)
        self.lbl_reg_err = QLabel('')
        self.lbl_reg_err.setStyleSheet(f'color:{C_ERR}; font-size:8pt;')
        self.lbl_reg_err.setWordWrap(True)
        lay.addWidget(self.lbl_reg_err)

        btn = QPushButton('Criar conta')
        btn.setMinimumHeight(38)
        btn.setStyleSheet(_pill(C_BTN_SEC))
        btn.clicked.connect(self._do_register)
        lay.addWidget(btn)

        lay.addSpacing(14)
        lay.addWidget(self._sep())
        lay.addSpacing(10)

        row = QHBoxLayout()
        btn2 = QPushButton('← Voltar')
        btn2.setFlat(True)
        btn2.setCursor(Qt.PointingHandCursor)
        btn2.setStyleSheet(
            f'color:{C_LINK}; font-weight:600; font-size:8.5pt;'
            f'border:none; background:transparent; padding:0;'
        )
        btn2.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        row.addWidget(btn2)
        row.addStretch()
        lay.addLayout(row)
        return pg

    def _do_login(self):
        user  = self.edit_user.text().strip()
        pwd   = self.edit_pass.text()
        bioma = self.combo_bioma.currentText()
        projeto = self.combo_projeto.currentText()

        if not user or not pwd:
            self.lbl_err.setText('Preencha usuário e senha.')
            return
        self.lbl_err.setText('Verificando...')
        ok, result = self.db.authenticate(user, pwd)
        if not ok:
            self.lbl_err.setText(f'✗  {result}')
            return
        self.user_info = result
        self.biome     = bioma
        self.project_type = projeto
        self.accept()

    def _do_register(self):
        nome  = self.edit_reg_nome.text().strip()
        user  = self.edit_reg_user.text().strip()
        pwd   = self.edit_reg_pass.text()
        pwd2  = self.edit_reg_pass2.text()
        bioma = self.combo_reg_bioma.currentText()
        is_auditor = self.chk_auditor.isChecked()
        self.lbl_reg_err.setText('')

        if not all([nome, user, pwd, pwd2]):
            self.lbl_reg_err.setText('Preencha todos os campos.')
            return
        if ' ' in user:
            self.lbl_reg_err.setText('Usuário não pode ter espaços.')
            return
        if len(pwd) < 6:
            self.lbl_reg_err.setText('Senha deve ter ao menos 6 caracteres.')
            return
        if pwd != pwd2:
            self.lbl_reg_err.setText('As senhas não coincidem.')
            return

        self.lbl_reg_err.setText('Criando...')
        ok, msg = self.db.register_user(user, nome, pwd, bioma, is_auditor)
        if not ok:
            self.lbl_reg_err.setText(f'✗  {msg}')
            return

        QMessageBox.information(self, 'Sample Design', f'Bem-vindo(a), {nome}!')
        self.edit_user.setText(user)
        self.edit_pass.clear()
        self.stack.setCurrentIndex(0)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f'color:{C_MUTED}; font-size:8pt; font-weight:600;'
            f'letter-spacing:0.3px; margin-bottom:2px;'
        )
        return l

    def _small(self, text):
        l = QLabel(text)
        l.setStyleSheet(f'color:{C_MUTED}; font-size:8.5pt;')
        return l

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f'color:{C_BORDER}; max-height:1px;')
        return line