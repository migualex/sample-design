# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# Client for the pygeoapi (OGC API - Features) used by the Pantanal Secondary
# Vegetation workflow since version 0.70.
#
# No PostgreSQL or WFS here: every read and write is an HTTP request.
#
# Standard library only, so it works on any QGIS install without extra packages.

import base64
import http.client
import json
import re
import html
import socket
import ssl
import time
import urllib.parse
from datetime import datetime, date

try:
    from . import db_config as _cfg
except Exception:  # pragma: no cover - module tested standalone
    _cfg = None

API_LOCAL_URL = getattr(_cfg, 'API_LOCAL_URL', 'http://127.0.0.1:5000')
API_TIMEOUT_S = getattr(_cfg, 'API_TIMEOUT_S', 20)
API_PAGE_SIZE = getattr(_cfg, 'API_PAGE_SIZE', 1000)
API_COLLECTIONS = getattr(_cfg, 'API_COLLECTIONS',
                          {'amostras': 'output', 'tarefas': 'ptn_tasks', 'tiles': 'tiles_ptn'})
API_PROJECTS = getattr(_cfg, 'API_PROJECTS', {})
API_USER = getattr(_cfg, 'API_USER', '')
API_PASSWORD = getattr(_cfg, 'API_PASSWORD', '')
API_KEY = getattr(_cfg, 'API_KEY', '')
API_CA_BUNDLE = getattr(_cfg, 'API_CA_BUNDLE', '')


# ═══════════════════════════════════════════════════════════════════════
# GeoJSON geometry helpers (no QGIS dependency)
# ═══════════════════════════════════════════════════════════════════════
def _ring_wkt(ring):
    return '(' + ', '.join(f'{p[0]!r} {p[1]!r}' for p in ring) + ')'


def geojson_to_wkt(geom):
    """GeoJSON Point/MultiPoint/Polygon/MultiPolygon to WKT."""
    if not geom:
        return None
    gtype = geom.get('type')
    coords = geom.get('coordinates')
    if gtype == 'Point':
        return f'POINT({coords[0]!r} {coords[1]!r})'
    if gtype == 'MultiPoint':
        return 'MULTIPOINT(' + ', '.join(f'({c[0]!r} {c[1]!r})' for c in coords) + ')'
    if gtype == 'Polygon':
        return 'POLYGON(' + ', '.join(_ring_wkt(r) for r in coords) + ')'
    if gtype == 'MultiPolygon':
        return 'MULTIPOLYGON(' + ', '.join(
            '(' + ', '.join(_ring_wkt(r) for r in poly) + ')' for poly in coords
        ) + ')'
    return None


def geojson_bbox(geom):
    """(xmin, ymin, xmax, ymax) of a GeoJSON geometry."""
    xs, ys = [], []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for sub in c:
                walk(sub)

    if not geom or not geom.get('coordinates'):
        return None
    walk(geom['coordinates'])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def parse_datetime(value):
    """ISO text returned by the API to datetime (or None)."""
    if value is None or isinstance(value, (datetime, date)):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    txt = txt.replace('Z', '')
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(txt[:26], fmt)
        except ValueError:
            continue
    return None


def _fmt_dt(value):
    dt = parse_datetime(value)
    return dt.strftime('%Y-%m-%d %H:%M') if dt else ''


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# Generic OGC API - Features HTTP client
# ═══════════════════════════════════════════════════════════════════════
class ApiError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


CRS_4674 = 'http://www.opengis.net/def/crs/EPSG/0/4674'
CRS_84 = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'


class ApiClient:

    # id_field of each collection (pygeoapi-config.yml)
    ID_FIELDS = {'output': 'fid', 'ptn_tasks': 'id', 'tiles_ptn': 'tile',
                 'nf_output': 'fid', 'nf_tasks': 'id', 'tiles_nf': 'tile'}

    def __init__(self, base_url=None, timeout=None, page_size=None,
                 user=None, password=None, api_key=None, ca_bundle=None):
        self._base_url = None
        self._conn = None
        self.base_url = base_url or API_LOCAL_URL
        self.timeout = timeout or API_TIMEOUT_S
        self.page_size = page_size or API_PAGE_SIZE
        self.user = API_USER if user is None else user
        self.password = API_PASSWORD if password is None else password
        self.api_key = API_KEY if api_key is None else api_key
        self.ca_bundle = API_CA_BUNDLE if ca_bundle is None else ca_bundle
        self._info_cache = {}
        # POST strategy that worked per collection (missing = not tried yet)
        self._post_explicit_id = {}
        # CRS requested when reading each collection (None = server default)
        self._crs_cache = {}
        self._storage_crs = {}

    # ------------------------------------------------------------------
    @property
    def base_url(self):
        return self._base_url

    @base_url.setter
    def base_url(self, value):
        self._base_url = str(value).rstrip('/')
        u = urllib.parse.urlsplit(self._base_url)
        self._scheme = (u.scheme or 'http').lower()
        host = u.hostname or '127.0.0.1'
        # On Windows "localhost" tries IPv6 (::1) first; pygeoapi listens on IPv4
        # only, so every request would lose ~2 s before falling back.
        self._host = '127.0.0.1' if host == 'localhost' else host
        self._port = u.port or (443 if self._scheme == 'https' else 80)
        self._prefix = u.path.rstrip('/')
        self._host_header = u.netloc.rsplit('@', 1)[-1] or host
        self.close()

    def close(self):
        """Closes the kept-alive connection (a new one is opened on the next request)."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    def _new_conn(self):
        if self._scheme == 'https':
            ctx = ssl.create_default_context(cafile=self.ca_bundle or None)
            return http.client.HTTPSConnection(self._host, self._port,
                                               timeout=self.timeout, context=ctx)
        return http.client.HTTPConnection(self._host, self._port, timeout=self.timeout)

    def _headers(self, has_body):
        h = {'Accept': 'application/geo+json, application/json',
             'Host': self._host_header, 'Connection': 'keep-alive',
             'User-Agent': 'SampleDesign-QGIS'}
        if has_body:
            h['Content-Type'] = 'application/geo+json'
        if self.user:
            tok = base64.b64encode(f'{self.user}:{self.password or ""}'.encode('utf-8')).decode()
            h['Authorization'] = f'Basic {tok}'
        if self.api_key:
            h['X-API-Key'] = self.api_key
        return h

    def _url(self, path, params=None):
        url = self._prefix + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += '?' + urllib.parse.urlencode(clean)
        return url

    def _request(self, method, path, params=None, body=None):
        """
        HTTP request on a kept-alive connection, so HTTPS does not repeat the TLS
        handshake on every call.
        """
        data = json.dumps(body).encode('utf-8') if body is not None else None
        url = self._url(path, params)
        for tentativa in (1, 2):
            reused = self._conn is not None
            try:
                if self._conn is None:
                    self._conn = self._new_conn()
                self._conn.request(method, url, body=data, headers=self._headers(data is not None))
                resp = self._conn.getresponse()
                raw = resp.read()
                headers = {k: v for k, v in resp.getheaders()}
                if resp.version == 10 or (resp.getheader('Connection') or '').lower() == 'close':
                    self.close()
                if resp.status == 401:
                    raise ApiError(f'A API em {self.base_url} recusou a chave de acesso (HTTP 401). Confira a chave.', 401, raw)
                return resp.status, headers, raw
            except ApiError:
                raise
            except ssl.SSLError as e:
                self.close()
                raise ApiError(f'Erro de certificado HTTPS em {self.base_url} ({e}). Se o '
                               f'certificado for próprio, informe o arquivo em API_CA_BUNDLE.')
            except (http.client.HTTPException, socket.timeout, ConnectionError, OSError) as e:
                self.close()
                # kept-alive connection already closed by the server: retry once
                if tentativa == 1 and reused and isinstance(
                        e, (http.client.RemoteDisconnected, BrokenPipeError,
                            ConnectionResetError, ConnectionAbortedError)):
                    continue
                raise ApiError(f'API indisponível em {self.base_url} ({e})')

    @staticmethod
    def _json(raw):
        if not raw:
            return None
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return None

    @staticmethod
    def _error_text(status, raw):
        js = ApiClient._json(raw)
        if isinstance(js, dict) and js.get('description'):
            return f'HTTP {status}: {js.get("description")}'
        txt = (raw or b'').decode('utf-8', 'replace').strip()
        if '<html' in txt.lower() or '<!doctype' in txt.lower():
            # pygeoapi debug mode: the page title carries the server exception
            m = re.search(r'<title>(.*?)</title>', txt, re.S | re.I)
            title = html.unescape(m.group(1)).replace('// Werkzeug Debugger', '').strip() if m else ''
            if title and 'internal server error' not in title.lower():
                return f'HTTP {status}: {title[:400]}'
            return f'HTTP {status} (veja o traceback na janela do pygeoapi ou no pygeoapi.log)'
        if len(txt) > 300:
            txt = txt[:300] + '...'
        return f'HTTP {status}' + (f': {txt}' if txt else '')

    def collection_info(self, collection):
        if collection in self._info_cache:
            return self._info_cache[collection]
        status, _, raw = self._request(
            'GET', f'/collections/{urllib.parse.quote(collection, safe="")}', {'f': 'json'})
        info = (self._json(raw) or {}) if status == 200 else {}
        if info:
            self._info_cache[collection] = info
        return info

    def read_crs(self, collection):
        """
        CRS to request so coordinates come back exactly as stored (lon/lat
        SIRGAS 2000), without server-side reprojection.

        With storage_crs = EPSG:4674, pygeoapi converts its default output to
        CRS84 and swaps the axis order. Asking for crs=EPSG:4674 skips that, so
        what is read can be written back (PUT) unchanged.
        """
        if collection not in self._crs_cache:
            info = self.collection_info(collection)
            storage = str(info.get('storageCrs') or '')
            self._storage_crs[collection] = storage
            offered = [str(c) for c in (info.get('crs') or [])]
            use = None
            if storage and 'CRS84' not in storage.upper() and storage in offered:
                use = storage
            self._crs_cache[collection] = use
        return self._crs_cache[collection]

    def _read_params(self, collection, params):
        crs = self.read_crs(collection)
        if crs:
            params['crs'] = crs
        return params

    def _item_path(self, collection, item_id=None):
        p = f'/collections/{urllib.parse.quote(collection, safe="")}/items'
        if item_id is not None:
            p += '/' + urllib.parse.quote(str(item_id), safe='')
        return p

    # ------------------------------------------------------------------
    def ping(self, required=None):
        """Checks that the API answers and has the required collections."""
        try:
            status, _, raw = self._request('GET', '/collections', {'f': 'json'})
        except ApiError as e:
            return False, str(e)
        if status != 200:
            return False, self._error_text(status, raw)
        js = self._json(raw) or {}
        ids = {c.get('id') for c in js.get('collections', [])}
        required = API_COLLECTIONS.values() if required is None else required
        faltando = [c for c in required if c not in ids]
        if faltando:
            return False, f'Coleções ausentes na API: {", ".join(faltando)}'
        return True, ''

    def whoami(self):
        """(user, profile) that owns the access key, or None if the API does not say."""
        try:
            status, _, raw = self._request('GET', '/sampledesign/quem-sou')
        except ApiError:
            return None
        if status != 200:
            return None
        # the gatekeeper answers {'code': 'OK', 'description': '<json>'}
        try:
            info = json.loads((self._json(raw) or {}).get('description') or '{}')
        except ValueError:
            return None
        return (info.get('usuario'), info.get('perfil')) if info.get('usuario') else None

    def first_item(self, collection, skip_geometry=False):
        """One feature of the collection (limit=1), for checks: a full page of cells with
        geometry is several MB and times out on slow links."""
        params = self._read_params(collection, {'f': 'json', 'limit': 1})
        if skip_geometry:
            params['skipGeometry'] = 'true'
        status, _, raw = self._request('GET', self._item_path(collection), params)
        if status != 200:
            raise ApiError(f'Erro ao consultar {collection}: ' + self._error_text(status, raw), status, raw)
        feats = (self._json(raw) or {}).get('features') or []
        return feats[0] if feats else None

    def iter_items(self, collection, filters=None, skip_geometry=False, properties=None):
        """Iterates over every feature of a collection (paged)."""
        offset = 0
        while True:
            # no sortby: pygeoapi orders by id_field, which keeps paging stable
            # even with repeated cell_oid
            params = self._read_params(collection,
                                       {'f': 'json', 'limit': self.page_size, 'offset': offset})
            if skip_geometry:
                params['skipGeometry'] = 'true'
            if properties:
                params['properties'] = ','.join(properties)
            for k, v in (filters or {}).items():
                if v is not None:
                    params[k] = v
            status, _, raw = self._request('GET', self._item_path(collection), params)
            if status != 200:
                raise ApiError(f'Erro ao consultar {collection}: ' + self._error_text(status, raw),
                               status, raw)
            js = self._json(raw) or {}
            feats = js.get('features') or []
            for f in feats:
                yield f
            returned = js.get('numberReturned', len(feats))
            if not feats or returned < self.page_size:
                break
            offset += returned

    def list_items(self, collection, filters=None, skip_geometry=False, properties=None):
        return list(self.iter_items(collection, filters, skip_geometry, properties))

    def number_matched(self, collection, filters=None):
        """Row count on the server (COUNT), repeated rows included."""
        params = {'f': 'json', 'limit': 1, 'skipGeometry': 'true'}
        params.update({k: v for k, v in (filters or {}).items() if v is not None})
        status, _, raw = self._request('GET', self._item_path(collection), params)
        if status != 200:
            return None
        return (self._json(raw) or {}).get('numberMatched')

    def queryables(self, collection):
        status, _, raw = self._request(
            'GET', f'/collections/{urllib.parse.quote(collection, safe="")}/queryables', {'f': 'json'})
        if status != 200:
            return None
        js = self._json(raw) or {}
        return set((js.get('properties') or {}).keys())

    def get_item(self, collection, item_id):
        status, _, raw = self._request('GET', self._item_path(collection, item_id),
                                       self._read_params(collection, {'f': 'json'}))
        if status == 404:
            return None
        if status != 200:
            raise ApiError(f'Erro ao ler {collection}/{item_id}: ' + self._error_text(status, raw),
                           status, raw)
        return self._json(raw)

    def _max_id(self, collection):
        id_field = self.ID_FIELDS.get(collection, 'id')
        params = {'f': 'json', 'limit': 1, 'skipGeometry': 'true', 'sortby': f'-{id_field}'}
        status, _, raw = self._request('GET', self._item_path(collection), params)
        if status != 200:
            return 0
        feats = (self._json(raw) or {}).get('features') or []
        try:
            return int(feats[0]['id']) if feats else 0
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _clean_feature(feature, item_id=None):
        out = {
            'type': 'Feature',
            'geometry': feature.get('geometry'),
            'properties': dict(feature.get('properties') or {}),
        }
        if item_id is not None:
            out['id'] = item_id
        return out

    def create_item(self, collection, feature):
        """
        Creates a feature and returns the id generated by the server.

        On a 5xx answer (typically an out-of-sync fid sequence in the PostgreSQL
        behind the API) it retries with the next free id.
        """
        body = self._clean_feature(feature)
        use_explicit = self._post_explicit_id.get(collection, False)
        tentativas = [use_explicit] if use_explicit else [False, True]
        last_err = None
        for explicit in tentativas:
            if explicit:
                body['id'] = self._max_id(collection) + 1
            else:
                body.pop('id', None)
            status, headers, raw = self._request('POST', self._item_path(collection), body=body)
            if status in (200, 201):
                self._post_explicit_id[collection] = explicit
                loc = headers.get('Location') or headers.get('location') or ''
                new_id = loc.rstrip('/').rsplit('/', 1)[-1] if loc else body.get('id')
                try:
                    return int(new_id)
                except (TypeError, ValueError):
                    return new_id
            last_err = self._error_text(status, raw)
            h = self._hint_for(collection, status, last_err)
            if status < 500 or h:
                last_err += h
                tentativas = [explicit]
                break
        hint = ''
        if tentativas == [False, True]:
            hint = (' — verifique a tabela no banco da API (sequência do fid, '
                    'tipo da geometria, triggers).')
        raise ApiError(f'Falha ao gravar em {collection}: {last_err}{hint}')

    def _storage_is_crs84(self, collection):
        try:
            self.read_crs(collection)
        except ApiError:
            return False
        st = self._storage_crs.get(collection, '')
        return not st or 'CRS84' in st.upper()

    def _hint_for(self, collection, status, err_text):
        h = self._hint(err_text)
        if not h and status >= 500 and self._storage_is_crs84(collection):
            h = (' — causa provável: o storage_crs da coleção está como CRS84 e a API grava a '
                 'geometria sem SRID (GeoAlchemy2 0.20 ou anterior). No pygeoapi-config.yml use '
                 'storage_crs: ' + CRS_4674 + ' e inclua esse CRS na lista "crs".')
        return h

    @staticmethod
    def _hint(err_text):
        if 'SRID=None' in err_text or 'parse error - invalid geometry' in err_text:
            return (' — a API grava a geometria sem SRID porque o storage_crs da coleção está '
                    'como CRS84. No pygeoapi-config.yml use storage_crs: ' + CRS_4674 +
                    ' (e inclua esse CRS na lista "crs").')
        return ''

    def replace_item(self, collection, item_id, feature):
        body = self._clean_feature(feature, item_id)
        status, _, raw = self._request('PUT', self._item_path(collection, item_id), body=body)
        if status not in (200, 204):
            err = self._error_text(status, raw)
            raise ApiError(f'Falha ao atualizar {collection}/{item_id}: '
                           f'{err}{self._hint_for(collection, status, err)}', status, raw)
        return True

    def delete_item(self, collection, item_id):
        status, _, raw = self._request('DELETE', self._item_path(collection, item_id))
        if status in (200, 204, 404):
            return True
        raise ApiError(f'Falha ao excluir {collection}/{item_id}: ' +
                       self._error_text(status, raw), status, raw)


# ═══════════════════════════════════════════════════════════════════════
# Pantanal Secondary Vegetation backend over the API
#
# Same method names and return shapes as the DBManager equivalents, so the
# task composition dialog (tile and cell selection) works unchanged.
# ═══════════════════════════════════════════════════════════════════════
# values that put a ptn_tasks row back to "free" (interpretation / audit)
FREE_1 = {'analyst_1': None, 'start_date_1': None, 'finished_1': False, 'end_date_1': None}
FREE_2 = {'analyst_2': None, 'start_date_2': None, 'finished_2': False, 'end_date_2': None}


# class lists live in collections without real geometry: pygeoapi needs one, so a fixed point is sent
_CLASS_GEOM = {'type': 'Point', 'coordinates': [0.0, 0.0]}


class PantanalVSApi:
    """
    Backend of the API projects (Pantanal VS and Amazônia NF): set_project()
    selects the collections of the project in use.
    """

    TASK_FIELDS = ['tile_2', 'analyst_1', 'start_date_1', 'finished_1', 'end_date_1',
                   'analyst_2', 'start_date_2', 'finished_2', 'end_date_2']
    BASE_SAMPLE_FIELDS = ['label', 'analyst', 'biome', 'prodes', 'area_m2', 'px_size',
                          'window_px', 'ecoregion', 'tile', 'audit', 'label_audit']

    def __init__(self, client=None, project=None):
        self.client = client or ApiClient()
        self.set_project(project)
        self.current_tile = None
        self._ping_ok_t = 0.0
        self._diag_ok_t = 0.0
        self._scan = None  # (timestamp, ptn_tasks rows without geometry)
        self._tile_rows = {}  # tile -> (timestamp, rows with geometry)
        self._rows_cache = {}  # cell_oid -> rows read on the last lock

    def set_project(self, project=None):
        """Uses the collections of an API_PROJECTS entry (default: Pantanal VS)."""
        project = project or {'amostras': API_COLLECTIONS['amostras'],
                              'tarefas': API_COLLECTIONS['tarefas'],
                              'tiles': API_COLLECTIONS['tiles'],
                              'classes': API_COLLECTIONS.get('classes', 'ptn_classes')}
        self.project = project
        self.col_amostras = project['amostras']
        self.col_tarefas = project['tarefas']
        self.col_tiles = project['tiles']
        self.col_classes = project.get('classes')
        # pygeoapi leaves DATE columns out of /queryables, so they are not checked by diagnose()
        self.SAMPLE_FIELDS = self.BASE_SAMPLE_FIELDS + [c for c in project.get('campos', ())
                                                        if c not in ('date', 'data_ref')]
        self._ping_ok_t = 0.0
        self._diag_ok_t = 0.0
        self._rows_cache = {}
        self._invalidate()

    def collections(self):
        return [c for c in (self.col_amostras, self.col_tarefas, self.col_tiles) if c]

    def set_endpoint(self, base_url, api_key=None):
        """Switches API address/key and drops everything cached from the previous one."""
        if self.client is not None:
            self.client.close()
        self.client = ApiClient(base_url=base_url, api_key=api_key or '')
        self._ping_ok_t = 0.0
        self._diag_ok_t = 0.0
        self._rows_cache = {}
        self._invalidate()

    def _invalidate(self):
        self._scan = None
        self._tile_rows = {}

    def _scan_tasks(self, ttl=5):
        """All ptn_tasks rows (no geometry), briefly cached."""
        if self._scan and time.time() - self._scan[0] < ttl:
            return self._scan[1]
        rows = list(self.client.iter_items(self.col_tarefas, skip_geometry=True))
        self._scan = (time.time(), rows)
        return rows

    # ---------------------------------------------------------- cells
    @staticmethod
    def _row_cell_oid(f):
        """cell_oid of a ptn_tasks row, whatever the API's id_field is."""
        p = f.get('properties') or {}
        return p['cell_oid'] if 'cell_oid' in p else f.get('id')

    @staticmethod
    def _cell_is_item_id(f):
        return 'cell_oid' not in (f.get('properties') or {})

    def _task_rows(self, cell_oid):
        rows = self._task_rows_fetch(cell_oid)
        self._rows_cache[cell_oid] = (time.time(), rows)
        return rows

    def _task_rows_fetch(self, cell_oid):
        """
        Every ptn_tasks row of the cell. A cell on the border of two tiles shows
        up once per tile; locks apply to all rows, like the PostgreSQL version's
        UPDATE ... WHERE cell_oid = ...
        """
        rows = []
        try:
            rows = [f for f in self.client.iter_items(self.col_tarefas, {'cell_oid': cell_oid})
                    if str(self._row_cell_oid(f)) == str(cell_oid)]
        except ApiError:
            rows = []
        if not rows:
            f = self.client.get_item(self.col_tarefas, cell_oid)
            rows = [f] if f else []
        n_linhas = len(rows)
        if rows and self._cell_is_item_id(rows[0]):
            n_linhas = self.client.number_matched(self.col_tarefas, {'cell_oid': cell_oid}) or len(rows)
        if n_linhas > 1 and self._cell_is_item_id(rows[0]):
            raise ApiError(
                f'A célula {cell_oid} aparece {n_linhas} vezes em {self.col_tarefas} '
                f'(célula de borda entre tiles), mas a API usa cell_oid como identificador (id_field). '
                f'A gravação (PUT) atualiza mais de uma linha e o pygeoapi responde HTTP 500. '
                f'Use no pygeoapi-config.yml, na coleção {self.col_tarefas}, um id_field '
                f'único por linha (ex.: id_field: id) e reinicie a API.')
        return rows

    def _row_for_tile(self, rows):
        if self.current_tile:
            for r in rows:
                if (r.get('properties') or {}).get('tile_2') == self.current_tile:
                    return r
        return rows[0] if rows else None

    # ---------------------------------------------------------- reading
    def ping(self):
        if time.time() - self._ping_ok_t < 20:
            return True, ''
        ok, msg = self.client.ping(self.collections())
        self._ping_ok_t = time.time() if ok else 0.0
        return ok, msg

    def get_pantanal_vs_tiles(self):
        tiles = {f['properties'].get('tile_2') for f in self._scan_tasks()}
        return sorted(t for t in tiles if t)

    def get_pantanal_vs_tiles_with_status(self):
        """Same aggregation as DBManager.get_pantanal_vs_tiles_with_status."""
        agg = {}
        for f in self._scan_tasks():
            p = f.get('properties') or {}
            tile = p.get('tile_2')
            if not tile:
                continue
            a = agg.setdefault(tile, {
                'locked': 0, 'finished': 0, 'locked_analyst': None, 'finished_analyst': None,
                'min_start1': None, 'max_end1': None, 'min_start2': None, 'max_end2': None,
                'any_analyst2': None, 'any_finished2': False,
            })
            if p.get('analyst_1') and p.get('finished_1') is False:
                a['locked'] += 1
                a['locked_analyst'] = a['locked_analyst'] or p.get('analyst_1')
            if p.get('finished_1') is True:
                a['finished'] += 1
                a['finished_analyst'] = a['finished_analyst'] or p.get('analyst_1')
            for key, field, fn in (('min_start1', 'start_date_1', min), ('max_end1', 'end_date_1', max),
                                   ('min_start2', 'start_date_2', min), ('max_end2', 'end_date_2', max)):
                v = parse_datetime(p.get(field))
                if v is not None:
                    a[key] = v if a[key] is None else fn(a[key], v)
            if p.get('analyst_2'):
                a['any_analyst2'] = max(a['any_analyst2'] or '', p['analyst_2'])
            if p.get('finished_2') is True:
                a['any_finished2'] = True

        results = []
        for tile in sorted(agg):
            a = agg[tile]
            if a['locked'] == 0 and a['finished'] == 0:
                status, analyst = 'free', ''
            elif a['locked'] > 0:
                status, analyst = 'locked', a['locked_analyst'] or ''
            else:
                status, analyst = 'finished', a['finished_analyst'] or ''
            results.append({
                'tile': tile,
                'status': status,
                'analyst': analyst,
                'start_date_1': _fmt_dt(a['min_start1']),
                'end_date_1': _fmt_dt(a['max_end1']),
                'start_date_2': _fmt_dt(a['min_start2']),
                'end_date_2': _fmt_dt(a['max_end2']),
                'analyst_2': a['any_analyst2'] or '',
                'finished_2': a['any_finished2'],
            })
        return results

    def _cell_dict(self, f):
        p = f.get('properties') or {}
        return {
            'cell_oid': self._row_cell_oid(f),
            'analyst_1': p.get('analyst_1'),
            'start_date_1': parse_datetime(p.get('start_date_1')),
            'finished_1': p.get('finished_1'),
            'end_date_1': parse_datetime(p.get('end_date_1')),
            'analyst_2': p.get('analyst_2'),
            'start_date_2': parse_datetime(p.get('start_date_2')),
            'finished_2': p.get('finished_2'),
            'end_date_2': parse_datetime(p.get('end_date_2')),
            'area_nf_km2': p.get('area_nf_km2'),
        }

    def _tile_features(self, tile_name, ttl=30):
        hit = self._tile_rows.get(tile_name)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        feats = self.client.list_items(self.col_tarefas, {'tile_2': tile_name})
        self._tile_rows[tile_name] = (time.time(), feats)
        return feats

    def get_grids_for_tile_with_status(self, tile_name):
        # a single read (with geometry) feeds both the list and the preview
        self.current_tile = tile_name
        self._tile_rows.pop(tile_name, None)
        feats = self._tile_features(tile_name)
        cells = [self._cell_dict(f) for f in feats]
        cells.sort(key=lambda c: str(c['cell_oid']))
        return cells

    def get_cell_analyst(self, cell_oid):
        f = self._row_for_tile(self._task_rows(cell_oid))
        return (f.get('properties') or {}).get('analyst_1') if f else None

    def get_cell_geom(self, cell_oid):
        hit = self._rows_cache.get(cell_oid)
        rows = hit[1] if hit and time.time() - hit[0] < 60 else self._task_rows(cell_oid)
        f = self._row_for_tile(rows)
        return geojson_to_wkt(f.get('geometry')) if f else None

    def get_cell_features(self, cell_ids):
        """Full features (with geometry) of the given cells."""
        out = []
        for oid in cell_ids:
            f = self._row_for_tile(self._task_rows(oid))
            if f:
                out.append(f)
        return out

    def get_cell_bounds_for_tile(self, tile_name):
        out = []
        for f in self._tile_features(tile_name):
            bb = geojson_bbox(f.get('geometry'))
            if not bb:
                continue
            geom = f.get('geometry') or {}
            coords = geom.get('coordinates') or []
            ring = (coords[0][0] if geom.get('type') == 'MultiPolygon' else coords[0]) if coords else None
            out.append({'cell_oid': self._row_cell_oid(f), 'xmin': bb[0], 'ymin': bb[1],
                        'xmax': bb[2], 'ymax': bb[3], 'ring': ring})
        out.sort(key=lambda c: str(c['cell_oid']))
        return out

    def get_tile_feature(self, tile_name):
        f = self.client.get_item(self.col_tiles, tile_name)
        if f:
            return f
        feats = self.client.list_items(self.col_tiles, {'tile': tile_name})
        return feats[0] if feats else None

    def get_tile_boundary(self, tile_name):
        f = self.get_tile_feature(tile_name)
        return geojson_to_wkt(f.get('geometry')) if f else None

    # ---------------------------------------------------------- locks
    def _update_task(self, cell_oid, changes, guard=None, require_all=False):
        """
        GET the cell rows → check the guard → PUT each row.
        require_all=True writes only if ALL rows pass (used for locking).
        """
        rows = self._task_rows(cell_oid)
        if not rows:
            return False, 'Célula não encontrada na API.'
        alvo = [r for r in rows if not guard or guard(r.get('properties') or {})]
        if not alvo or (require_all and len(alvo) != len(rows)):
            return False, None
        self._invalidate()
        for f in alvo:
            props = dict(f.get('properties') or {})
            props.update(changes)
            f['properties'] = props
            self.client.replace_item(self.col_tarefas, f.get('id'), f)
        return True, None

    def lock_cell(self, cell_oid, username):
        try:
            ok, _ = self._update_task(
                cell_oid,
                {'analyst_1': username, 'start_date_1': now_iso(),
                 'finished_1': False, 'end_date_1': None},
                guard=lambda p: (p.get('analyst_1') in (None, '', username)
                                 and p.get('finished_1') is not True),
                require_all=True)
            if not ok:
                return False, 'Célula já ocupada ou não disponível.'
            # optimistic check: another user may have written at the same time
            if self.get_cell_analyst(cell_oid) != username:
                return False, 'Célula já ocupada ou não disponível.'
            return True, None
        except ApiError as e:
            return False, str(e)

    def unlock_cell(self, cell_oid, username):
        try:
            self._update_task(
                cell_oid, {'finished_1': True, 'end_date_1': now_iso()},
                guard=lambda p: p.get('analyst_1') == username and p.get('finished_1') is not True)
            return True, None
        except ApiError as e:
            return False, str(e)

    def lock_cell_for_audit(self, cell_oid, auditor_username):
        try:
            ok, _ = self._update_task(
                cell_oid,
                {'analyst_2': auditor_username, 'start_date_2': now_iso(),
                 'finished_2': False, 'end_date_2': None},
                guard=lambda p: (p.get('finished_1') is True
                                 and p.get('finished_2') in (False, None)
                                 and p.get('analyst_2') in (None, '', auditor_username)))
            if not ok:
                return False, 'Célula não disponível para auditoria.'
            return True, None
        except ApiError as e:
            return False, str(e)

    def finish_audit(self, cell_oid, auditor_username, interpreter_username=None):
        """
        Marks the cell audit as finished (finished_2/end_date_2). The implicit
        agreement copy label → label_audit is done earlier in the SQLite package
        and uploaded with the other samples.
        """
        try:
            self._update_task(
                cell_oid, {'finished_2': True, 'end_date_2': now_iso()},
                guard=lambda p: (p.get('analyst_2') == auditor_username
                                 and p.get('finished_1') is True
                                 and p.get('finished_2') is not True))
            return True, None
        except ApiError as e:
            return False, str(e)

    def fill_audit_for_cell(self, cell_oid, auditor_username, interpreter_username):
        # 'audit' is filled in the SQLite package when the interpreter's samples
        # are downloaded (SamplerDock._vs_import_server_samples).
        return True

    def admin_unlock_cell(self, cell_oid):
        """
        Admin: releases the lock in progress without touching finished work
        (interpretation in progress → clears analyst_1; audit in progress →
        clears analyst_2). Returns (ok, message).
        """
        try:
            rows = self._task_rows(cell_oid)
            if not rows:
                return False, 'Célula não encontrada na API.'
            feitos = set()
            for f in rows:
                p = dict(f.get('properties') or {})
                if p.get('finished_1') is not True and p.get('analyst_1'):
                    feitos.add(f'interpretação de {p.get("analyst_1")}')
                    p.update(FREE_1)
                elif (p.get('finished_1') is True and p.get('finished_2') is not True
                      and p.get('analyst_2')):
                    feitos.add(f'auditoria de {p.get("analyst_2")}')
                    p.update(FREE_2)
                else:
                    continue
                f['properties'] = p
                self._invalidate()
                self.client.replace_item(self.col_tarefas, f.get('id'), f)
            if not feitos:
                return False, 'a célula não tem bloqueio em andamento.'
            return True, 'liberada (' + ', '.join(sorted(feitos)) + ')'
        except ApiError as e:
            return False, str(e)

    def reopen_cell(self, cell_oid):
        """
        Auditors and administrators: makes a cell available again WITHOUT deleting any
        sample. A finished audit is reopened (analyst_2/finished_2 cleared, so any auditor
        can lock the cell and revisit it); a lock in progress (interpretation or audit) is
        released. Finished interpretation stays finished (it is what the audit reviews).
        Returns (ok, message).
        """
        try:
            rows = self._task_rows(cell_oid)
            if not rows:
                return False, 'célula não encontrada na API.'
            feitos = set()
            for f in rows:
                p = dict(f.get('properties') or {})
                if p.get('finished_2') is True:
                    feitos.add(f'auditoria finalizada de {p.get("analyst_2") or "?"} reaberta')
                    p.update(FREE_2)
                elif p.get('finished_1') is True and p.get('analyst_2'):
                    feitos.add(f'auditoria de {p.get("analyst_2")} desbloqueada')
                    p.update(FREE_2)
                elif p.get('finished_1') is not True and p.get('analyst_1'):
                    feitos.add(f'interpretação de {p.get("analyst_1")} desbloqueada')
                    p.update(FREE_1)
                else:
                    continue
                f['properties'] = p
                self._invalidate()
                self.client.replace_item(self.col_tarefas, f.get('id'), f)
            if not feitos:
                return False, 'nada para reabrir.'
            return True, ', '.join(sorted(feitos))
        except ApiError as e:
            return False, str(e)

    # ---------------------------------------------------------- tile reset
    LOCK_FIELDS = ('analyst_1', 'start_date_1', 'end_date_1',
                   'analyst_2', 'start_date_2', 'end_date_2')

    def _tile_task_rows(self, tile_name):
        """
        ptn_tasks rows (with geometry) of the tile cells, including the rows of
        the same cells in neighbouring tiles (border cells).
        """
        rows = self.client.list_items(self.col_tarefas, {'tile_2': tile_name})
        oids = {str(self._row_cell_oid(f)) for f in rows}
        ids = {str(f.get('id')) for f in rows}
        for f in self._scan_tasks(ttl=0):
            p = f.get('properties') or {}
            if (str(self._row_cell_oid(f)) in oids and p.get('tile_2') != tile_name
                    and str(f.get('id')) not in ids):
                full = self.client.get_item(self.col_tarefas, f.get('id'))
                if full:
                    rows.append(full)
        return rows

    def tile_lock_summary(self, tile_name):
        """(rows with a lock or work, total rows) of the tile cells."""
        rows = self._tile_task_rows(tile_name)
        sujas = [f for f in rows if self._row_has_work(f)]
        return len(sujas), len(rows)

    def _row_has_work(self, f):
        p = f.get('properties') or {}
        return (any(p.get(k) for k in self.LOCK_FIELDS)
                or p.get('finished_1') is True or p.get('finished_2') is True)

    def reset_tile_cells(self, tile_name):
        """
        Puts every cell of the tile back to free (interpretation and audit),
        border rows in neighbouring tiles included. Returns (changed_rows, errors).
        """
        alteradas, erros = 0, []
        self._invalidate()
        for f in self._tile_task_rows(tile_name):
            if not self._row_has_work(f):
                continue
            p = dict(f.get('properties') or {})
            p.update(self.FREE_VALUES)
            f['properties'] = p
            try:
                self.client.replace_item(self.col_tarefas, f.get('id'), f)
                alteradas += 1
            except ApiError as e:
                erros.append(f'{self._row_cell_oid(f)}: {e}')
        self._invalidate()
        return alteradas, erros

    # ---------------------------------------------------------- cell reset
    FREE_VALUES = {**FREE_1, **FREE_2}

    def cell_rows(self, cell_oid):
        """Every ptn_tasks row (with geometry) of the cell."""
        return self._task_rows(cell_oid)

    def reset_cell(self, cell_oid, rows=None):
        """
        Admin (testing): puts ALL rows of the cell back to free, interpretation
        and audit, in progress or finished. Returns (changed_rows, errors).
        """
        alteradas, erros = 0, []
        self._invalidate()
        try:
            rows = rows if rows is not None else self._task_rows(cell_oid)
        except ApiError as e:
            return 0, [f'{cell_oid}: {e}']
        for f in rows:
            if not self._row_has_work(f):
                continue
            p = dict(f.get('properties') or {})
            p.update(self.FREE_VALUES)
            f['properties'] = p
            try:
                self.client.replace_item(self.col_tarefas, f.get('id'), f)
                alteradas += 1
            except ApiError as e:
                erros.append(f'{cell_oid}: {e}')
        self._invalidate()
        self._rows_cache.pop(cell_oid, None)
        return alteradas, erros

    def cell_held_by(self, cell_oid, username, audit=False):
        """True if the cell is still locked by the user (in the given phase)."""
        rows = self._task_rows(cell_oid)
        if not rows:
            return False
        for f in rows:
            p = f.get('properties') or {}
            if audit:
                if not (p.get('analyst_2') == username and p.get('finished_2') is not True):
                    return False
            elif not (p.get('analyst_1') == username and p.get('finished_1') is not True):
                return False
        return True

    def release_cell(self, cell_oid, username, audit=False):
        """The user gives the cell up: clears only that user's lock."""
        if audit:
            changes = FREE_2
            guard = lambda p: p.get('analyst_2') == username and p.get('finished_2') is not True
        else:
            changes = FREE_1
            guard = lambda p: p.get('analyst_1') == username and p.get('finished_1') is not True
        try:
            self._update_task(cell_oid, changes, guard=guard)
            return True, None
        except ApiError as e:
            return False, str(e)

    def admin_reset_cell(self, cell_oid):
        try:
            ok, _ = self._update_task(cell_oid, self.FREE_VALUES)
            return ok
        except ApiError:
            return False

    # ---------------------------------------------------------- diagnostics
    @staticmethod
    def _in_degrees(geom):
        bb = geojson_bbox(geom)
        return bb is None or (-180 <= bb[0] <= 180 and -180 <= bb[2] <= 180
                              and -90 <= bb[1] <= 90 and -90 <= bb[3] <= 90)

    def diagnose(self):
        """
        Checks that the cells, tiles and samples collections have what the plugin
        needs. Returns (errors, warnings) as lists of messages.
        """
        if time.time() - self._diag_ok_t < 600:
            return [], []
        erros, avisos = self._diagnose()
        self._diag_ok_t = time.time() if not erros else 0.0
        return erros, avisos

    def _diagnose(self):
        erros, avisos = [], []
        # storage CRS of each collection
        for col in (self.col_tarefas, self.col_tiles, self.col_amostras):
            try:
                info = self.client.collection_info(col)
            except ApiError as e:
                return [f'{col}: {e}'], avisos
            storage = str(info.get('storageCrs') or '')
            offered = [str(c) for c in (info.get('crs') or [])]
            if not storage or 'CRS84' in storage.upper():
                avisos.append(f'{col}: storage_crs é CRS84, mas as tabelas são SRID 4674. Com o '
                              f'GeoAlchemy2 0.20 ou anterior a gravação falha ("SRID=None"). '
                              f'Use storage_crs: {CRS_4674}.')
            elif storage not in offered:
                erros.append(f'{col}: storage_crs é {storage}, mas ele não está na lista "crs" '
                             f'da coleção. Sem isso a API devolve lat/lon trocados. Inclua '
                             f'{storage} em "crs" no pygeoapi-config.yml.')
        if erros:
            return erros, avisos
        # cells
        try:
            amostra = self.client.first_item(self.col_tarefas)
        except ApiError as e:
            return [f'{self.col_tarefas}: {e}'], avisos
        if amostra is None:
            erros.append(f'{self.col_tarefas}: coleção vazia.')
        else:
            props = set((amostra.get('properties') or {}).keys())
            falta = [c for c in self.TASK_FIELDS if c not in props]
            if falta:
                erros.append(f'{self.col_tarefas}: colunas ausentes: {", ".join(falta)}')
            if not self._in_degrees(amostra.get('geometry')):
                erros.append(f'{self.col_tarefas}: a geometria não está em graus '
                             f'(lon/lat SIRGAS 2000). Verifique o SRID da tabela.')
            contagem = {}
            for f in self._scan_tasks():
                oid = self._row_cell_oid(f)
                contagem[oid] = contagem.get(oid, 0) + 1
            repetidas = [o for o, n in contagem.items() if n > 1]
            if self._cell_is_item_id(amostra):
                # With id_field = cell_oid pygeoapi merges repeated rows in listings;
                # the server total (numberMatched) reveals the difference.
                total = self.client.number_matched(self.col_tarefas)
                if total is not None and total > len(contagem):
                    erros.append(
                        f'{self.col_tarefas}: há {total} linhas para {len(contagem)} cell_oid '
                        f'distintos (células de borda repetidas em mais de um tile) e a API usa '
                        f'cell_oid como id_field. O bloqueio dessas células falha com HTTP 500. '
                        f'No pygeoapi-config.yml, use em {self.col_tarefas} um id_field único '
                        f'por linha (ex.: id_field: id) e reinicie a API.')
            elif repetidas:
                avisos.append(f'{self.col_tarefas}: {len(repetidas)} células aparecem em mais de '
                              f'um tile — o bloqueio é aplicado em todas as linhas da célula.')
        # tiles
        try:
            t = self.client.first_item(self.col_tiles)
            if t is None:
                erros.append(f'{self.col_tiles}: coleção vazia.')
            else:
                if 'tile' not in (t.get('properties') or {}) and t.get('id') is None:
                    erros.append(f'{self.col_tiles}: coluna "tile" ausente.')
                if not self._in_degrees(t.get('geometry')):
                    erros.append(f'{self.col_tiles}: a geometria não está em graus.')
        except ApiError as e:
            erros.append(f'{self.col_tiles}: {e}')
        # samples
        try:
            q = self.client.queryables(self.col_amostras)
            if q is not None:
                falta = [c for c in self.SAMPLE_FIELDS if c not in q]
                if falta:
                    erros.append(f'{self.col_amostras}: colunas ausentes: {", ".join(falta)}')
            self.client.first_item(self.col_amostras, skip_geometry=True)
        except ApiError as e:
            erros.append(f'{self.col_amostras}: {e}')
        return erros, avisos

    # ---------------------------------------------------------- classes
    def _class_rows(self):
        if not self.col_classes:
            return []
        rows = []
        for f in self.client.iter_items(self.col_classes, skip_geometry=True):
            p = dict(f.get('properties') or {})
            p['id'] = f.get('id')
            rows.append(p)
        rows.sort(key=lambda r: (r.get('ordem') if r.get('ordem') is not None else 999, r['id']))
        return rows

    def list_classes(self):
        """Active classes of the project as [(code, label, color)], in display order."""
        return [(r['code'], r.get('label') or r['code'], r.get('color') or '#888888')
                for r in self._class_rows() if r.get('code') and r.get('ativo') is not False]

    def save_classes(self, classes):
        """
        Makes the API list match `classes` [(code, label, color)]: updates or adds
        each one in order and deactivates (never deletes) the others, so samples
        that use a removed class keep a valid code. Returns (ok, message).
        """
        if not self.col_classes:
            return False, 'Este projeto não tem coleção de classes na API.'
        try:
            existing = {r['code']: r for r in self._class_rows() if r.get('code')}
            wanted = set()
            for ordem, (code, label, color) in enumerate(classes):
                wanted.add(code)
                props = {'code': code, 'label': label, 'color': color, 'ordem': ordem, 'ativo': True}
                row = existing.get(code)
                feature = {'type': 'Feature', 'geometry': _CLASS_GEOM, 'properties': props}
                if row is None:
                    self.client.create_item(self.col_classes, feature)
                elif any(row.get(k) != v for k, v in props.items()):
                    self.client.replace_item(self.col_classes, row['id'], feature)
            for code, row in existing.items():
                if code not in wanted and row.get('ativo') is not False:
                    props = {k: row.get(k) for k in ('code', 'label', 'color', 'ordem')}
                    props['ativo'] = False
                    self.client.replace_item(self.col_classes, row['id'],
                                             {'type': 'Feature', 'geometry': _CLASS_GEOM,
                                              'properties': props})
        except ApiError as e:
            if e.status == 403 or 'HTTP 403' in str(e):
                return False, ('Sua chave de acesso não tem permissão para alterar as classes.')
            return False, str(e)
        return True, ''

    # ---------------------------------------------------------- samples
    def list_samples(self, filters=None, with_geometry=False):
        return self.client.list_items(self.col_amostras, filters, skip_geometry=not with_geometry)

    STATS_FIELDS = ['label', 'analyst', 'biome', 'tile', 'ecoregion', 'label_audit']

    def sample_properties(self, filters=None, fields=None):
        return [dict(f.get('properties') or {}, fid=f.get('id'))
                for f in self.client.iter_items(self.col_amostras, filters, skip_geometry=True,
                                                properties=fields)]

    def create_sample(self, feature):
        return self.client.create_item(self.col_amostras, feature)

    def update_sample(self, fid, feature):
        return self.client.replace_item(self.col_amostras, fid, feature)

    def delete_sample(self, fid):
        return self.client.delete_item(self.col_amostras, fid)
