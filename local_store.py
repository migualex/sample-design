# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# SQLite work package of the Pantanal Secondary Vegetation workflow.
#
# The package is a GeoPackage (.gpkg), i.e. a plain SQLite 3 database: QGIS
# opens it as editable layers and any SQLite tool can read it. It is the
# exchange file between the plugin and the API.
#
# The user chooses where the file is saved; the plugin creates no folders or
# temporary layers. QGIS settings keep only the paths of packages in progress
# (to offer resuming) and the last folder used - never sample data.
#
# Layout (schema version 1):
#
#   celulas   (Polygon, EPSG:4674)  cells locked for the user
#   tile      (Polygon, EPSG:4674)  outline of the task tile
#   amostras  (Polygon, EPSG:4674)  collected samples (squares/polygons) with sync control
#   pontos    (Point, EPSG:4674)    point samples (only projects that collect points)
#   mascara   (MultiPolygon)        PRODES mask of the tile (only projects with a mask)
#   sessao    (table)               key/value: user, phase, tile, status...
#   envios    (table)               log of every upload to the API
#   exclusoes (table)               uploaded samples deleted locally
#
# amostras.sync_status:
#   'pendente'  created locally, not uploaded yet (api_fid empty)
#   'enviada'   same as on the API (api_fid set)
#   'alterada'  uploaded, then changed (needs another upload)
#
# sessao.status: 'em_andamento' | 'finalizado' | 'limpo'

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime

from qgis.PyQt.QtCore import QMetaType, QVariant
from qgis.core import (
    QgsVectorLayer, QgsVectorFileWriter, QgsCoordinateTransformContext,
    QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsField, QgsFields,
    QgsWkbTypes, QgsSettings, NULL, Qgis,
)

try:
    from .db_config import PACOTES_DIR
except Exception:  # pragma: no cover
    PACOTES_DIR = ''

SCHEMA_VERSION = '1'
CRS_AUTHID = 'EPSG:4674'

LYR_CELULAS = 'celulas'
LYR_TILE = 'tile'
LYR_AMOSTRAS = 'amostras'
LYR_PONTOS = 'pontos'
LYR_MASCARA = 'mascara'

STATUS_PENDENTE = 'pendente'
STATUS_ENVIADA = 'enviada'
STATUS_ALTERADA = 'alterada'

PKG_EM_ANDAMENTO = 'em_andamento'
PKG_FINALIZADO = 'finalizado'
PKG_LIMPO = 'limpo'

# fields of the API 'output' collection (table order)
CAMPOS_API = ['label', 'analyst', 'biome', 'date', 'prodes', 'area_m2', 'px_size',
              'window_px', 'ecoregion', 'tile', 'audit', 'label_audit']

# extra fields a project may send (API_PROJECTS[...]['campos'])
CAMPOS_EXTRA = ['data_ref', 'tipo_geom']

# local control fields (never sent to the API)
CAMPOS_CONTROLE = ['cell_oid', 'api_fid', 'sync_status', 'created_at', 'sent_at']

_FIELDS = {
    LYR_CELULAS: [
        ('cell_oid', 'string', 150), ('tile', 'string', 150), ('fase', 'string', 20),
        ('analyst', 'string', 100), ('status', 'string', 20),
        ('locked_at', 'datetime', 0), ('finished_at', 'datetime', 0),
    ],
    LYR_TILE: [
        ('tile', 'string', 150),
    ],
    LYR_AMOSTRAS: [
        ('label', 'string', 150), ('analyst', 'string', 100), ('biome', 'string', 50),
        ('date', 'date', 0), ('prodes', 'string', 10), ('area_m2', 'double', 0),
        ('px_size', 'integer', 0), ('window_px', 'integer', 0), ('ecoregion', 'string', 150),
        ('tile', 'string', 150), ('audit', 'string', 100), ('label_audit', 'string', 150),
        ('data_ref', 'date', 0), ('tipo_geom', 'string', 20),
        ('cell_oid', 'string', 150), ('api_fid', 'integer', 0), ('sync_status', 'string', 20),
        ('created_at', 'datetime', 0), ('sent_at', 'datetime', 0),
    ],
}
_FIELDS[LYR_PONTOS] = _FIELDS[LYR_AMOSTRAS]
_FIELDS[LYR_MASCARA] = [('origem', 'string', 40), ('ano', 'integer', 0), ('classe', 'string', 60)]
_GEOM_TYPES = {LYR_PONTOS: Qgis.WkbType.Point, LYR_MASCARA: Qgis.WkbType.MultiPolygon}

_QTYPES = {
    'string': (QMetaType.Type.QString, 'String'),
    'integer': (QMetaType.Type.Int, 'Integer'),
    'double': (QMetaType.Type.Double, 'Real'),
    'date': (QMetaType.Type.QDate, 'Date'),
    'datetime': (QMetaType.Type.QDateTime, 'DateTime'),
}

_SETTINGS_PACOTES = 'SampleDesign/pacotes_vs_pantanal'
_SETTINGS_ULTIMA_PASTA = 'SampleDesign/pacotes_vs_pantanal_ultima_pasta'


def _now():
    return datetime.now().replace(microsecond=0).isoformat()


def _slug(text):
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', str(text or '')).strip('_')
    return s or 'x'


def py_value(v):
    """QGIS values (NULL, QDate, QDateTime) to Python/JSON."""
    if v is None or v == NULL:
        return None
    if isinstance(v, QVariant):
        if v.isNull():
            return None
        v = v.value()
    if hasattr(v, 'toPyDateTime') and hasattr(v, 'time'):
        try:
            return v.toPyDateTime().replace(microsecond=0).isoformat()
        except Exception:
            return None
    if hasattr(v, 'toString') and hasattr(v, 'year') and not isinstance(v, str):
        try:
            return v.toString('yyyy-MM-dd') if v.isValid() else None
        except Exception:
            return None
    return v


# ═══════════════════════════════════════════════════════════════════════
# Suggested paths and registry of packages in progress (paths only)
# ═══════════════════════════════════════════════════════════════════════
def suggested_filename(username, tile, fase):
    """Default package name: workspace_<tile>.gpkg (user and phase are stored inside)."""
    return f'workspace_{_slug(tile)}.gpkg'


def default_dir():
    """Suggested save folder: last used, PACOTES_DIR or Documents."""
    for d in (QgsSettings().value(_SETTINGS_ULTIMA_PASTA, '', type=str), PACOTES_DIR,
              os.path.join(os.path.expanduser('~'), 'Documents'),
              os.path.join(os.path.expanduser('~'), 'Documentos'),
              os.path.expanduser('~')):
        if d and os.path.isdir(d):
            return d
    return os.path.expanduser('~')


def remember_dir(path):
    d = os.path.dirname(os.path.abspath(path))
    if os.path.isdir(d):
        QgsSettings().setValue(_SETTINGS_ULTIMA_PASTA, d)


def _registry_load():
    raw = QgsSettings().value(_SETTINGS_PACOTES, '[]', type=str)
    try:
        data = json.loads(raw or '[]')
        return [r for r in data if isinstance(r, dict) and r.get('path')]
    except ValueError:
        return []


def _registry_save(items):
    QgsSettings().setValue(_SETTINGS_PACOTES, json.dumps(items))


def registry_add(path, username, tile, fase):
    path = os.path.abspath(path)
    items = [r for r in _registry_load() if os.path.abspath(r['path']) != path]
    items.append({'path': path, 'username': username, 'tile': str(tile), 'fase': fase})
    _registry_save(items)


def registry_remove(path):
    path = os.path.abspath(path)
    _registry_save([r for r in _registry_load() if os.path.abspath(r['path']) != path])


def registry_find(username, tile, fase):
    """Package in progress for this task, if the file still exists."""
    for r in reversed(_registry_load()):
        if (r.get('username') == username and str(r.get('tile')) == str(tile)
                and r.get('fase') == fase and os.path.exists(r['path'])):
            if WorkPackage(r['path']).get_meta('status', PKG_EM_ANDAMENTO) == PKG_EM_ANDAMENTO:
                return r['path']
    return None


def registry_latest():
    """Most recent package in progress on this computer (or None)."""
    for r in reversed(_registry_load()):
        if os.path.exists(r['path']) and \
                WorkPackage(r['path']).get_meta('status', PKG_EM_ANDAMENTO) == PKG_EM_ANDAMENTO:
            return r['path']
    return None


def hash_password(password, salt_hex=None):
    """Salted PBKDF2-SHA256 (the password is never stored)."""
    salt_hex = salt_hex or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'),
                            bytes.fromhex(salt_hex), 100000).hex()
    return salt_hex, h


def registry_for_tile(tile):
    return [r['path'] for r in _registry_load() if str(r.get('tile')) == str(tile)]


class WorkPackage:
    """SQLite (GeoPackage) file of one task: user + tile + phase."""

    def __init__(self, path):
        self.path = path

    def _sql(self):
        return closing(sqlite3.connect(self.path, timeout=10))

    @classmethod
    def archive_tile(cls, tile):
        """
        Marks this computer's packages in progress for the tile as 'limpo' (an
        admin reset the tile). Files stay where they are but are no longer offered
        for resuming.
        """
        n = 0
        for path in registry_for_tile(tile):
            wp = cls(path)
            try:
                if wp.exists() and wp.get_meta('status', PKG_EM_ANDAMENTO) == PKG_EM_ANDAMENTO:
                    wp.set_meta({'status': PKG_LIMPO, 'limpo_em': _now()})
                    n += 1
            except sqlite3.Error:
                pass
            registry_remove(path)
        return n

    @classmethod
    def archive_cells(cls, cell_ids):
        """
        Marks as 'limpo' this computer's packages in progress that contain any of
        the cells (an admin reset them). Returns the marked paths; files stay put.
        """
        alvo = {str(c) for c in cell_ids}
        marcados = []
        for r in _registry_load():
            wp = cls(r['path'])
            try:
                if not wp.exists() or wp.get_meta('status', PKG_EM_ANDAMENTO) != PKG_EM_ANDAMENTO:
                    continue
                if alvo & {str(c) for c in wp.cell_ids()}:
                    wp.set_meta({'status': PKG_LIMPO, 'limpo_em': _now()})
                    registry_remove(wp.path)
                    marcados.append(wp.path)
            except sqlite3.Error:
                continue
        return marcados

    def cell_ids(self):
        """cell_oid of the cells stored in the package."""
        with self._sql() as con:
            return [r[0] for r in con.execute(f'SELECT cell_oid FROM {LYR_CELULAS}')]

    def exists(self):
        return os.path.exists(self.path)

    def has_layer(self, name):
        return name in self._layer_names()

    # QGIS project ("workspace") stored inside the package
    WORKSPACE = 'workspace'

    def workspace_uri(self):
        return f'geopackage:{self.path}?projectName={self.WORKSPACE}'

    def has_workspace(self):
        try:
            with self._sql() as con:
                return con.execute('SELECT 1 FROM qgis_projects WHERE name = ?',
                                   (self.WORKSPACE,)).fetchone() is not None
        except sqlite3.Error:
            return False

    def is_package(self):
        """True if the file is a Sample Design package (has the sessao table)."""
        return bool(self.get_all_meta().get('schema_version'))

    def matches(self, username, tile, fase):
        m = self.get_all_meta()
        return (m.get('username') == username and str(m.get('tile')) == str(tile)
                and m.get('fase') == fase)

    def uri(self, layer_name):
        return f'{self.path}|layername={layer_name}'

    # ------------------------------------------------------------ creation
    def _layer_names(self):
        if not self.exists():
            return set()
        try:
            with self._sql() as con:
                return {r[0] for r in con.execute('SELECT table_name FROM gpkg_contents')}
        except sqlite3.Error:
            return set()

    def _create_layer(self, name):
        """Creates the spatial table directly in the file."""
        fields = QgsFields()
        for fname, ftype, flen in _FIELDS[name]:
            qtype, tname = _QTYPES[ftype]
            fields.append(QgsField(fname, qtype, tname, flen))
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = 'GPKG'
        opts.fileEncoding = 'UTF-8'
        opts.layerName = name
        opts.layerOptions = ['GEOMETRY_NAME=geom', 'FID=fid']
        opts.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteLayer
                                     if self.exists() else
                                     QgsVectorFileWriter.CreateOrOverwriteFile)
        writer = QgsVectorFileWriter.create(
            self.path, fields, _GEOM_TYPES.get(name, Qgis.WkbType.Polygon),
            QgsCoordinateReferenceSystem(CRS_AUTHID),
            QgsCoordinateTransformContext(), opts)
        erro = writer.hasError() != QgsVectorFileWriter.NoError
        msg = writer.errorMessage()
        del writer  # closes and flushes the file
        if erro:
            raise RuntimeError(f'Não foi possível criar a camada "{name}" em {self.path}: {msg}')

    def ensure_schema(self, meta=None, points=False, mask=False):
        existentes = self._layer_names()
        for name in ((LYR_AMOSTRAS, LYR_CELULAS, LYR_TILE) + ((LYR_PONTOS,) if points else ())
                     + ((LYR_MASCARA,) if mask else ())):
            if name not in existentes:
                self._create_layer(name)
        with self._sql() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS sessao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave TEXT NOT NULL UNIQUE,
                    valor TEXT
                );
                CREATE TABLE IF NOT EXISTS envios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora TEXT NOT NULL,
                    tipo TEXT,
                    enviadas INTEGER DEFAULT 0,
                    atualizadas INTEGER DEFAULT 0,
                    excluidas INTEGER DEFAULT 0,
                    erros INTEGER DEFAULT 0,
                    mensagem TEXT
                );
                CREATE TABLE IF NOT EXISTS exclusoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_fid INTEGER NOT NULL UNIQUE,
                    excluida_em TEXT
                );
            ''')
            # register the tables in the GeoPackage catalogue (data_type=attributes)
            for t, desc in (('sessao', 'Metadados da tarefa'),
                            ('envios', 'Histórico de envios à API'),
                            ('exclusoes', 'Exclusões pendentes de envio')):
                con.execute(
                    "INSERT OR IGNORE INTO gpkg_contents (table_name, data_type, identifier, "
                    "description, last_change) VALUES (?, 'attributes', ?, ?, "
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'))", (t, t, desc))
            con.commit()
        defaults = {'schema_version': SCHEMA_VERSION, 'status': PKG_EM_ANDAMENTO,
                    'criado_em': _now()}
        atual = self.get_all_meta()
        novos = {k: v for k, v in defaults.items() if k not in atual}
        novos.update(meta or {})
        novos['atualizado_em'] = _now()
        self.set_meta(novos)

    # ------------------------------------------------------------ session
    def set_meta(self, values):
        with self._sql() as con:
            for k, v in values.items():
                con.execute('INSERT INTO sessao (chave, valor) VALUES (?, ?) '
                            'ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor',
                            (str(k), None if v is None else str(v)))
            con.commit()

    def get_all_meta(self):
        if not self.exists():
            return {}
        try:
            with self._sql() as con:
                return dict(con.execute('SELECT chave, valor FROM sessao').fetchall())
        except sqlite3.Error:
            return {}

    def get_meta(self, key, default=None):
        return self.get_all_meta().get(key, default)

    def log_envio(self, tipo, enviadas=0, atualizadas=0, excluidas=0, erros=0, mensagem=''):
        with self._sql() as con:
            con.execute('INSERT INTO envios (data_hora, tipo, enviadas, atualizadas, excluidas, '
                        'erros, mensagem) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (_now(), tipo, enviadas, atualizadas, excluidas, erros, mensagem))
            con.commit()

    # ------------------------------------------------------------ deletions
    def add_pending_delete(self, api_fid):
        if api_fid in (None, ''):
            return
        with self._sql() as con:
            con.execute('INSERT OR IGNORE INTO exclusoes (api_fid, excluida_em) VALUES (?, ?)',
                        (int(api_fid), _now()))
            con.commit()

    def pending_deletes(self):
        with self._sql() as con:
            return [r[0] for r in con.execute('SELECT api_fid FROM exclusoes ORDER BY id')]

    def clear_pending_delete(self, api_fid):
        with self._sql() as con:
            con.execute('DELETE FROM exclusoes WHERE api_fid = ?', (int(api_fid),))
            con.commit()

    # ------------------------------------------------------------ layers
    def open_layer(self, name, display_name=None):
        lyr = QgsVectorLayer(self.uri(name), display_name or name, 'ogr')
        return lyr if lyr.isValid() else None

    def upsert_cells(self, cells, tile, fase, analyst):
        """cells: list of (cell_oid, wkt). Adds the missing ones, reopens the others."""
        lyr = self.open_layer(LYR_CELULAS)
        if lyr is None:
            raise RuntimeError('Camada de células inválida no pacote.')
        existentes = {}
        for f in lyr.getFeatures():
            existentes[f['cell_oid']] = f.id()
        novos, reabrir = [], {}
        idx_status = lyr.fields().indexOf('status')
        for oid, wkt in cells:
            if oid in existentes:
                reabrir[existentes[oid]] = {idx_status: 'bloqueada'}
                continue
            feat = QgsFeature(lyr.fields())
            feat.setGeometry(QgsGeometry.fromWkt(wkt))
            feat['cell_oid'] = oid
            feat['tile'] = tile
            feat['fase'] = fase
            feat['analyst'] = analyst
            feat['status'] = 'bloqueada'
            feat['locked_at'] = _now()
            novos.append(feat)
        if novos:
            lyr.dataProvider().addFeatures(novos)
        if reabrir:
            lyr.dataProvider().changeAttributeValues(reabrir)
        return len(novos)

    def set_tile(self, tile, wkt):
        lyr = self.open_layer(LYR_TILE)
        if lyr is None:
            raise RuntimeError('Camada de tile inválida no pacote.')
        if any(f['tile'] == tile for f in lyr.getFeatures()):
            return
        feat = QgsFeature(lyr.fields())
        if wkt:
            feat.setGeometry(QgsGeometry.fromWkt(wkt))
        feat['tile'] = tile
        lyr.dataProvider().addFeatures([feat])

    def mark_cells_finished(self, cell_ids):
        lyr = self.open_layer(LYR_CELULAS)
        if lyr is None:
            return
        i_status = lyr.fields().indexOf('status')
        i_fin = lyr.fields().indexOf('finished_at')
        alvo = set(cell_ids)
        changes = {f.id(): {i_status: 'finalizada', i_fin: _now()}
                   for f in lyr.getFeatures() if f['cell_oid'] in alvo}
        if changes:
            lyr.dataProvider().changeAttributeValues(changes)

    def locked_cells(self):
        lyr = self.open_layer(LYR_CELULAS)
        if lyr is None:
            return []
        return [(f['cell_oid'], f.geometry().asWkt()) for f in lyr.getFeatures()
                if f['status'] == 'bloqueada']

    def known_api_fids(self, amostras_layer):
        idx = amostras_layer.fields().indexOf('api_fid')
        out = set()
        if idx < 0:
            return out
        for f in amostras_layer.getFeatures():
            v = py_value(f[idx])
            if v is not None:
                out.add(int(v))
        return out
