# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# Address and access key of the pygeoapi API used by the Pantanal Secondary
# Vegetation workflow. The user enters the HTTPS address of the online API
# before selecting cells and again when submitting the work package.
#
# The last address and the keys are kept in this computer's QGIS settings
# (QgsSettings); none of it is written to the SQLite package.

import ipaddress
import json
import urllib.parse

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)
from qgis.core import QgsSettings

from .api_local import ApiClient

try:
    from .db_config import API_LOCAL_URL, API_KEY
except Exception:  # pragma: no cover
    API_LOCAL_URL, API_KEY = 'http://127.0.0.1:5000', ''

_S_URL = 'SampleDesign/api/url'
_S_RECENTES = 'SampleDesign/api/recentes'
_S_CHAVES = 'SampleDesign/api/chaves'  # {url: key}
_S_LEMBRAR = 'SampleDesign/api/lembrar_chave'
_MAX_RECENTES = 8


# ═══════════════════════════════════════════════════════════════════════
# Saved settings
# ═══════════════════════════════════════════════════════════════════════
def _json_setting(key, default):
    try:
        val = json.loads(QgsSettings().value(key, '') or 'null')
    except (TypeError, ValueError):
        val = None
    return val if isinstance(val, type(default)) else default


def normalizar_url(url):
    url = (url or '').strip()
    if url and '://' not in url:
        url = 'https://' + url
    return url.rstrip('/')


def saved_url():
    return normalizar_url(QgsSettings().value(_S_URL, '') or API_LOCAL_URL)


def recent_urls():
    urls = [normalizar_url(u) for u in _json_setting(_S_RECENTES, []) if u]
    atual = saved_url()
    return [atual] + [u for u in urls if u != atual]


def saved_key(url):
    return _json_setting(_S_CHAVES, {}).get(normalizar_url(url), '') or API_KEY or ''


def remember_key_enabled():
    return str(QgsSettings().value(_S_LEMBRAR, 'true')).lower() in ('true', '1')


def save_endpoint(url, key, remember=True):
    url = normalizar_url(url)
    s = QgsSettings()
    s.setValue(_S_URL, url)
    recentes = [url] + [u for u in recent_urls() if u != url]
    s.setValue(_S_RECENTES, json.dumps(recentes[:_MAX_RECENTES]))
    chaves = _json_setting(_S_CHAVES, {})
    if remember and key:
        chaves[url] = key
    else:
        chaves.pop(url, None)
    s.setValue(_S_CHAVES, json.dumps(chaves))
    s.setValue(_S_LEMBRAR, 'true' if remember else 'false')


def apply_saved_endpoint(vs_api):
    """Points the client to the last address/key used on this computer."""
    url = saved_url()
    vs_api.set_endpoint(url, saved_key(url))


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════
def _host_local(host):
    if host in ('localhost', ''):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_rede_interna(host):
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return host.endswith('.local') or '.' not in host


def validar_url(url):
    """
    Returns (normalized_url, error, warning). Plain HTTP is accepted silently only
    for this computer, with a warning on the internal network, and refused on the
    internet (the access key would travel unencrypted).
    """
    url = normalizar_url(url)
    if not url:
        return url, 'Informe o endereço da API.', None
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ('http', 'https') or not u.hostname:
        return url, 'Endereço inválido. Exemplo: https://servidor.exemplo.org', None
    if u.username or u.password:
        return url, 'Não coloque usuário/senha no endereço; use o campo "Chave de acesso".', None
    if u.query or u.fragment:
        return url, 'O endereço não deve ter "?" nem "#".', None
    if u.scheme == 'http' and not _host_local(u.hostname):
        if _host_rede_interna(u.hostname):
            return url, None, ('HTTP não tem criptografia: use só na rede interna, para testes.')
        return url, ('Use HTTPS (https://...). Com HTTP, a chave e as amostras trafegam sem criptografia.'), None
    return url, None, None


# ═══════════════════════════════════════════════════════════════════════
# Widgets
# ═══════════════════════════════════════════════════════════════════════
class ApiEndpointWidget(QWidget):
    """API address and access key fields, with a connection test."""

    def __init__(self, parent=None, url=None, btn_style=''):
        super().__init__(parent)
        self._btn_style = btn_style
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self.combo_url = QComboBox()
        self.combo_url.setObjectName('combo_api_url')
        self.combo_url.setEditable(True)
        self.combo_url.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_url.setMinimumHeight(30)
        self.combo_url.lineEdit().setPlaceholderText('https://servidor.exemplo.org')
        urls = recent_urls()
        url = normalizar_url(url) if url else urls[0]
        if url not in urls:
            urls.insert(0, url)
        self.combo_url.addItems(urls)
        self.combo_url.setCurrentText(url)

        self.edit_key = QLineEdit(saved_key(url))
        self.edit_key.setObjectName('edit_api_chave')
        self.edit_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_key.setMinimumHeight(30)
        self.edit_key.setPlaceholderText('chave fornecida pelo administrador (sd_...)')
        self.chk_show = QCheckBox('mostrar')
        self.chk_show.toggled.connect(lambda on: self.edit_key.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))

        self.chk_remember = QCheckBox('Lembrar a chave neste computador')
        self.chk_remember.setChecked(remember_key_enabled())

        self.btn_test = QPushButton('Testar conexão')
        if btn_style:
            self.btn_test.setStyleSheet(btn_style)
        self.btn_test.clicked.connect(self.test)

        self.lbl_status = QLabel('')
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        grid.addWidget(QLabel('Endereço da API:'), 0, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.combo_url, 0, 1, 1, 2)
        grid.addWidget(QLabel('Chave de acesso:'), 1, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.edit_key, 1, 1)
        grid.addWidget(self.chk_show, 1, 2)
        row = QHBoxLayout()
        row.addWidget(self.chk_remember)
        row.addStretch()
        row.addWidget(self.btn_test)
        grid.addLayout(row, 2, 1, 1, 2)
        grid.addWidget(self.lbl_status, 3, 0, 1, 3)
        grid.setColumnStretch(1, 1)

        self.combo_url.currentTextChanged.connect(self._on_url_changed)
        self.edit_key.textChanged.connect(lambda _: self._status(''))

    def _on_url_changed(self, url):
        self._status('')
        key = saved_key(url)
        if key or not self.edit_key.text():
            self.edit_key.setText(key)

    def _status(self, text, ok=None):
        color = {True: '#16A34A', False: '#DC2626'}.get(ok, '#8A93A2')
        self.lbl_status.setStyleSheet(f'color:{color}; font-size:8.5pt;')
        self.lbl_status.setText(text)

    def endpoint(self):
        return normalizar_url(self.combo_url.currentText()), self.edit_key.text().strip()

    def remember(self):
        return self.chk_remember.isChecked()

    def test(self):
        """Checks address and key against the API. Returns (ok, message)."""
        url, erro, aviso = validar_url(self.combo_url.currentText())
        if erro:
            self._status('✗  ' + erro, False)
            return False, erro
        _, key = self.endpoint()
        self.combo_url.setCurrentText(url)
        self._status('Conectando...')
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            client = ApiClient(base_url=url, api_key=key, timeout=15)
            ok, msg = client.ping()
            client.close()
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            if 'HTTP 401' in msg:
                msg = ('A API recusou a chave de acesso (HTTP 401). Confira a chave ou peça '
                       'uma nova ao administrador.')
            self._status('✗  ' + msg, False)
            return False, msg
        texto = 'API conectada.' + (f'  Atenção: {aviso}' if aviso else '')
        self._status('✓  ' + texto, True)
        return True, texto


class ApiEndpointDialog(QDialog):
    """Dialog to enter and test the API address before using it."""

    def __init__(self, parent=None, title='API online', message='', url=None,
                 btn_style='', ok_text='Conectar'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        ttl = QLabel(title)
        ttl.setStyleSheet('font-size:11pt; font-weight:700;')
        lay.addWidget(ttl)
        if message:
            txt = QLabel(message)
            txt.setWordWrap(True)
            txt.setStyleSheet('color:#8A93A2; font-size:8.5pt;')
            lay.addWidget(txt)
        self.widget = ApiEndpointWidget(self, url=url, btn_style=btn_style)
        lay.addWidget(self.widget)
        foot = QHBoxLayout()
        foot.addStretch()
        self.btn_ok = QPushButton(ok_text)
        self.btn_ok.setDefault(True)
        btn_cancel = QPushButton('Cancelar')
        if btn_style:
            self.btn_ok.setStyleSheet(btn_style)
            btn_cancel.setStyleSheet(btn_style)
        foot.addWidget(self.btn_ok)
        foot.addWidget(btn_cancel)
        lay.addLayout(foot)
        self.btn_ok.clicked.connect(self._confirm)
        btn_cancel.clicked.connect(self.reject)

    def _confirm(self):
        ok, msg = self.widget.test()
        if not ok:
            QMessageBox.warning(self, self.windowTitle(), msg)
            return
        url, key = self.widget.endpoint()
        save_endpoint(url, key, self.widget.remember())
        self.accept()

    def endpoint(self):
        return self.widget.endpoint()
