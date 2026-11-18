# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# "Série temporal" tab: time series (indices and spectral bands) of the samples,
# read from the Brazil Data Cube WTSS (Web Time Series Service, same service as
# the BDC code-gallery wtss-introduction notebook), smoothed with a
# Savitzky-Golay filter and plotted with matplotlib.

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import urllib.request
from datetime import date, datetime

from qgis.PyQt.QtCore import QDate, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QPalette
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

try:
    import numpy as np
except ImportError:  # pragma: no cover - QGIS always ships numpy
    np = None
try:
    from scipy.signal import savgol_filter as _scipy_savgol
except Exception:
    _scipy_savgol = None
try:
    from matplotlib.figure import Figure
    try:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    except ImportError:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    import matplotlib.dates as mdates
except Exception:
    Figure = FigureCanvas = mdates = None

WTSS_URL = 'https://data.inpe.br/bdc/wtss/v4'
COVERAGES = ['S2-16D-2', 'LANDSAT-16D-1', 'CBERS4-WFI-16D-2', 'mod13q1-6.1']
ATTRIBUTES = ['NDVI', 'EVI']
MAX_SAMPLES = 25
_TIMEOUT = 40
_WORKERS = 6                      # parallel WTSS queries (one per sample)
_PREFETCH = ('NDVI', 'EVI', 'NBR')  # indices fetched with the first query of each sample


# ═══════════════════════════════════════════════════════════════════════
# WTSS client
# ═══════════════════════════════════════════════════════════════════════
def _get_json(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/json',
                                               'User-Agent': 'SampleDesign-QGIS'})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


_nodata_cache = {}


def nodata_values(coverage):
    """{attribute: scaled nodata value} of a coverage (WTSS returns scaled values)."""
    if coverage not in _nodata_cache:
        out = {}
        try:
            for b in _get_json(f'{WTSS_URL}/{urllib.parse.quote(coverage)}').get('bands', []):
                if b.get('nodata') is not None:
                    out[str(b.get('name'))] = float(b['nodata']) * float(b.get('scale') or 1)
        except Exception:
            pass
        _nodata_cache[coverage] = out
    return _nodata_cache[coverage]


def fetch_series(coverage, lon, lat, start, end, attributes=ATTRIBUTES):
    """
    Time series of one location. start/end are date objects.
    Returns (dates, {attribute: [float | None]}); nodata becomes None.
    """
    params = {
        'attributes': ','.join(attributes),
        'geom': json.dumps({'type': 'Point', 'coordinates': [round(lon, 7), round(lat, 7)]}),
        'start_datetime': f'{start:%Y-%m-%d}T00:00:00Z',
        'end_datetime': f'{end:%Y-%m-%d}T23:59:59Z',
    }
    url = f'{WTSS_URL}/{urllib.parse.quote(coverage)}/timeseries?{urllib.parse.urlencode(params)}'
    js = _get_json(url)
    results = js.get('results') or []
    if not results:
        raise RuntimeError(js.get('description') or 'sem resultado do WTSS')
    ts = results[0].get('time_series') or {}
    dates = [datetime.strptime(d[:10], '%Y-%m-%d').date() for d in ts.get('timeline', [])]
    nodata = nodata_values(coverage)
    values = {}
    for attr, vals in (ts.get('values') or {}).items():
        nd = nodata.get(attr)
        clean = []
        for v in vals:
            bad = (v is None or (nd is not None and abs(v - nd) < 1e-6)
                   or not -1.0 <= v <= 1.0 or (isinstance(v, float) and math.isnan(v)))
            clean.append(None if bad else float(v))
        values[attr] = clean
    return dates, values


# ═══════════════════════════════════════════════════════════════════════
# Savitzky-Golay
# ═══════════════════════════════════════════════════════════════════════
def _fill_gaps(values):
    """Linear interpolation over missing values (ends take the nearest valid value)."""
    idx = [i for i, v in enumerate(values) if v is not None]
    if not idx:
        return None
    out = list(values)
    for i in range(len(out)):
        if out[i] is not None:
            continue
        left = max((k for k in idx if k < i), default=None)
        right = min((k for k in idx if k > i), default=None)
        if left is None:
            out[i] = values[right]
        elif right is None:
            out[i] = values[left]
        else:
            w = (i - left) / (right - left)
            out[i] = values[left] * (1 - w) + values[right] * w
    return out


def _savgol_numpy(y, window, order):
    """Savitzky-Golay by least-squares convolution (used if scipy is missing)."""
    half = window // 2
    x = np.arange(-half, half + 1, dtype=float)
    coeffs = np.linalg.pinv(np.vander(x, order + 1, increasing=True))[0]
    padded = np.concatenate([np.full(half, y[0]), y, np.full(half, y[-1])])
    return np.convolve(padded, coeffs[::-1], mode='valid')


def savitzky_golay(values, window=7, order=2):
    """
    Smoothed copy of `values` (None = missing, interpolated first). The window
    is forced odd and shrunk to the series length. Returns None if not possible.
    """
    filled = _fill_gaps(values)
    if filled is None or np is None:
        return None
    n = len(filled)
    window = min(window, n if n % 2 else n - 1)
    if window % 2 == 0:
        window -= 1
    order = min(order, window - 1)
    if window < 3 or order < 1:
        return filled
    y = np.asarray(filled, dtype=float)
    if _scipy_savgol is not None:
        return list(_scipy_savgol(y, window, order, mode='interp'))
    return list(_savgol_numpy(y, window, order))


# ═══════════════════════════════════════════════════════════════════════
# Coverage attributes
# ═══════════════════════════════════════════════════════════════════════
_INDICES = ('NDVI', 'EVI', 'NBR')
# bands checked by default in "Bandas" mode (Sentinel-2/CBERS names, Landsat/MODIS common names)
_DEFAULT_BANDS = {'B02', 'B03', 'B04', 'B08', 'B11', 'B12', 'BAND13', 'BAND14', 'BAND15', 'BAND16',
                  'blue', 'green', 'red', 'nir08', 'swir16', 'swir22',
                  'blue_reflectance', 'red_reflectance', 'NIR_reflectance', 'MIR_reflectance'}
# attributes of S2-16D-2 shown before the WTSS answers (the list is refreshed from the WTSS later)
_S2_ATTRS = [('NDVI', 'NDVI'), ('EVI', 'EVI'), ('NBR', 'NBR'), ('B01', 'B01 (coastal)'), ('B02', 'B02 (blue)'),
             ('B04', 'B04 (red)'), ('B08', 'B08 (nir)'), ('B8A', 'B8A (nir08)'), ('B09', 'B09 (nir09)'),
             ('B03', 'B03 (green)'), ('B11', 'B11 (swir16)'), ('B12', 'B12 (swir22)'), ('B05', 'B05 (rededge)'),
             ('B06', 'B06 (rededge)'), ('B07', 'B07 (rededge)')]
_BAND_COLORS = ['#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#ff7f0e', '#8c564b',
                '#e377c2', '#17becf', '#bcbd22', '#7f7f7f', '#393b79', '#637939']
_SKIP_COMMON = {'quality', 'clearob', 'totalob', 'provenance', 'dataset', ''}
_attr_cache = {}


def coverage_attributes(coverage):
    """
    [(name, label)] of the attributes worth plotting: vegetation indices first,
    then the spectral bands (quality/auxiliary bands are left out).
    """
    if coverage not in _attr_cache:
        out = []
        try:
            bands = _get_json(f'{WTSS_URL}/{urllib.parse.quote(coverage)}').get('bands', [])
            idx = [b for b in bands if str(b.get('name')).upper() in _INDICES]
            idx.sort(key=lambda b: _INDICES.index(str(b['name']).upper()))
            spec = [b for b in bands if b not in idx
                    and str(b.get('common_name') or '').lower() not in _SKIP_COMMON]
            for b in idx + spec:
                name, common = str(b['name']), str(b.get('common_name') or '')
                out.append((name, name if b in idx or common.lower() == name.lower()
                            else f'{name} ({common})'))
        except Exception:
            pass
        _attr_cache[coverage] = out or [(a, a) for a in ATTRIBUTES]
    return _attr_cache[coverage]


def _dark():
    app = QApplication.instance()
    return bool(app) and app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _theme_axes(fig, ax):
    """Chart colours that follow the QGIS light/dark theme."""
    if _dark():
        bg, fg, grid = '#2B2B2B', '#E8E8E8', '#555555'
    else:
        bg, fg, grid = '#FFFFFF', '#2D3142', '#CCCCCC'
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.tick_params(colors=fg)
    ax.yaxis.label.set_color(fg)
    ax.title.set_color(fg)
    for sp in ax.spines.values():
        sp.set_color(grid)
    ax.grid(True, alpha=0.3, color=grid)
    leg = ax.get_legend()
    if leg is not None:
        leg.get_frame().set_facecolor(bg)
        leg.get_frame().set_edgecolor(grid)
        for t in leg.get_texts():
            t.set_color(fg)


def is_index(attr):
    return str(attr).upper() in _INDICES


# ═══════════════════════════════════════════════════════════════════════
# Panel
# ═══════════════════════════════════════════════════════════════════════
class TimeSeriesPanel(QWidget):
    """
    Time series of the samples. Samples are dicts {id, label, color, geom
    (QgsGeometry), crs, layer_id?, fid?}:
      samples_provider()  -> samples selected on the map
      on_focus(sample)    -> dock highlights the sample on the map
    Clicking a sample in the list shows only that sample; "Ver todas" shows the
    checked ones again.
    """

    def __init__(self, samples_provider=None, btn_style='', parent=None):
        super().__init__(parent)
        self.samples_provider = samples_provider or (lambda: [])
        self.on_focus = None
        self.analysis_date = None
        self._samples = []          # sample dicts, in list order
        self._series = {}           # sample id -> (dates, {attr: values})
        self._focus = None          # id of the sample shown alone (None = checked ones)
        self._cache = {}
        self._attrs_loaded = False  # coverage bands are read from the WTSS on first use
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(6)

        hint = QLabel(('Série temporal das amostras (BDC/WTSS), suavizada com Savitzky-Golay. '
            'Clique numa amostra da lista para ver só ela.'))
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#8A93A2; font-size:7.5pt;')
        lay.addWidget(hint)

        box = QGroupBox('Consulta')
        g = QGridLayout(box)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(4)
        self.combo_cov = QComboBox()
        self.combo_cov.addItems(COVERAGES)
        self.combo_attr = QComboBox()
        for name in ATTRIBUTES:
            self.combo_attr.addItem(name, name)
        self.date_start = QDateEdit()
        self.date_end = QDateEdit()
        for d in (self.date_start, self.date_end):
            d.setCalendarPopup(True)
            d.setDisplayFormat('dd/MM/yyyy')
        self.set_analysis_date(None)
        g.addWidget(QLabel('Cubo:'), 0, 0)
        g.addWidget(self.combo_cov, 0, 1, 1, 3)
        self.combo_attr.setVisible(False)   # kept internally; the checkboxes below choose what to plot
        g.addWidget(QLabel('De:'), 2, 0)
        g.addWidget(self.date_start, 2, 1)
        g.addWidget(QLabel('até:'), 2, 2)
        g.addWidget(self.date_end, 2, 3)
        # single "Bandas e índices" mode: one checked attribute without a chosen sample compares
        # all samples; otherwise the checked bands/indices of one sample are plotted together
        lbl_b = QLabel('Bandas e índices:')
        g.addWidget(lbl_b, 3, 0, 1, 4)
        self.bands_box = QWidget()
        self.bands_grid = QGridLayout(self.bands_box)
        self.bands_grid.setContentsMargins(0, 0, 0, 0)
        self.bands_grid.setHorizontalSpacing(8)
        self.bands_grid.setVerticalSpacing(2)
        self.band_checks = {}
        g.addWidget(self.bands_box, 4, 0, 1, 4)
        self._build_checks(_S2_ATTRS)
        lay.addWidget(box)

        box_f = QGroupBox('Filtro Savitzky-Golay')
        f = QHBoxLayout(box_f)
        self.chk_raw = QCheckBox('Original')
        self.chk_raw.setChecked(True)
        self.chk_sg = QCheckBox('Suavizada')
        self.chk_sg.setChecked(True)
        self.spin_window = QSpinBox()
        self.spin_window.setRange(3, 31)
        self.spin_window.setSingleStep(2)
        self.spin_window.setValue(7)
        self.spin_window.setToolTip('Janela (número ímpar de observações)')
        self.spin_order = QSpinBox()
        self.spin_order.setRange(1, 5)
        self.spin_order.setValue(2)
        self.spin_order.setToolTip('Grau do polinômio')
        f.addWidget(self.chk_raw)
        f.addWidget(self.chk_sg)
        f.addStretch()
        f.addWidget(QLabel('Janela:'))
        f.addWidget(self.spin_window)
        f.addWidget(QLabel('Grau:'))
        f.addWidget(self.spin_order)
        lay.addWidget(box_f)

        row = QHBoxLayout()
        self.btn_load = QPushButton('Selecionadas no mapa')
        self.btn_load.setToolTip('Carrega as amostras selecionadas no mapa (pontos, quadrados e polígonos).')
        self.btn_clear = QPushButton('Limpar')
        for b in (self.btn_load, self.btn_clear):
            if btn_style:
                b.setStyleSheet(btn_style)
            row.addWidget(b)
        lay.addLayout(row)

        self.lbl_status = QLabel('')
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet('color:#8A93A2; font-size:8pt;')
        lay.addWidget(self.lbl_status)

        if FigureCanvas is not None:
            self.figure = Figure(figsize=(4, 3), tight_layout=True)
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setMinimumHeight(260)
            lay.addWidget(self.canvas, 1)
        else:
            self.figure = self.canvas = None
            lay.addWidget(QLabel('matplotlib não está disponível nesta instalação do QGIS.'))

        row_l = QHBoxLayout()
        self.lbl_list = QLabel('Amostras carregadas (clique para ver só uma):')
        self.lbl_list.setStyleSheet('color:#8A93A2; font-size:7.5pt;')
        self.btn_show_all = QPushButton('Ver todas')
        if btn_style:
            self.btn_show_all.setStyleSheet(btn_style)
        self.btn_show_all.setEnabled(False)
        row_l.addWidget(self.lbl_list, 1)
        row_l.addWidget(self.btn_show_all)
        lay.addLayout(row_l)
        self.list = QListWidget()
        self.list.setMaximumHeight(130)
        self.list.setToolTip('Clique para ver só esta amostra. Desmarque para escondê-la em "Ver todas".')
        lay.addWidget(self.list)

        self.btn_load.clicked.connect(lambda: self.load(self.samples_provider()))
        self.btn_clear.clicked.connect(self.clear)
        self.btn_show_all.clicked.connect(lambda: self.set_focus(None))
        self.list.itemChanged.connect(lambda _: self.redraw())
        self.list.itemClicked.connect(self._on_item_clicked)
        self.combo_cov.currentIndexChanged.connect(self._on_coverage_changed)
        self.combo_attr.currentIndexChanged.connect(self._on_attr_changed)
        for w in (self.chk_raw, self.chk_sg):
            w.toggled.connect(lambda _: self.redraw())
        for w in (self.spin_window, self.spin_order):
            w.valueChanged.connect(lambda _: self.redraw())
        self.redraw()  # empty chart already in the theme colours

    # ------------------------------------------------------------------ state
    def set_analysis_date(self, value):
        """Analysis date of the package: default period = the two years before it."""
        if isinstance(value, str) and value:
            try:
                value = datetime.strptime(value[:10], '%Y-%m-%d').date()
            except ValueError:
                value = None
        self.analysis_date = value if isinstance(value, date) else None
        end = self.analysis_date or date.today()
        self.date_end.setDate(QDate(end.year, end.month, end.day))
        self.date_start.setDate(QDate(end.year - 2, end.month, min(end.day, 28)))

    def attribute(self):
        return self.combo_attr.currentData() or self.combo_attr.currentText()

    def clear(self):
        self._samples = []
        self._series = {}
        self._focus = None
        self.list.clear()
        self.btn_show_all.setEnabled(False)
        self.lbl_status.setText('')
        self.redraw()

    def _on_coverage_changed(self, _):
        self._fill_attributes()
        self._series = {}
        self._fetch(self._samples)

    def _fill_attributes(self):
        """Index/band list of the selected coverage, keeping the current choice."""
        current = self.attribute()
        self.combo_attr.blockSignals(True)
        self.combo_attr.clear()
        for name, label in coverage_attributes(self.combo_cov.currentText()):
            self.combo_attr.addItem(label, name)
        i = self.combo_attr.findData(current)
        self.combo_attr.setCurrentIndex(i if i >= 0 else 0)
        self.combo_attr.blockSignals(False)
        self._build_checks(coverage_attributes(self.combo_cov.currentText()))

    def _build_checks(self, attrs):
        """Checkboxes of the coverage: indices first (unchecked), then the spectral bands."""
        previous = {n for n, c in self.band_checks.items() if c.isChecked()} if self.band_checks else None
        while self.bands_grid.count():
            w = self.bands_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.band_checks = {}
        for k, (name, label) in enumerate(attrs):
            chk = QCheckBox(label)
            chk.setChecked(name in previous if previous else name in _DEFAULT_BANDS)
            chk.toggled.connect(self._on_band_toggled)
            self.band_checks[name] = chk
            self.bands_grid.addWidget(chk, k // 4, k % 4)

    def _on_band_toggled(self, _):
        attrs = self.wanted_attributes()
        if all(a in self._series.get(s['id'], (None, {}))[1] for s in self._samples for a in attrs):
            self._refresh_list()   # data already loaded (indices come with the first query)
            self.redraw()
            return
        # several boxes ticked in a row become a single query
        if not hasattr(self, '_fetch_timer'):
            self._fetch_timer = QTimer(self)
            self._fetch_timer.setSingleShot(True)
            self._fetch_timer.timeout.connect(lambda: self._fetch(self._samples))
        self._fetch_timer.start(350)

    def wanted_attributes(self):
        """Checked bands/indices."""
        return [n for n, c in self.band_checks.items() if c.isChecked()]

    def _on_attr_changed(self, _):
        self._fetch(self._samples)

    # ------------------------------------------------------------------ data
    def load(self, samples):
        """Replaces the loaded samples."""
        if not samples:
            self.lbl_status.setText('Selecione amostras no mapa e clique em "Selecionadas no mapa".')
            return
        extra = len(samples) - MAX_SAMPLES
        self._samples = list(samples[:MAX_SAMPLES])
        self._series = {}
        self._focus = None
        self._fetch(self._samples)
        if extra > 0:
            self.lbl_status.setText(self.lbl_status.text() +
                                    f' Mostrando as {MAX_SAMPLES} primeiras ({extra} ficaram de fora).')

    def _period(self):
        return self.date_start.date().toPyDate(), self.date_end.date().toPyDate()

    def _fetch(self, samples):
        """Fetches the current attribute for the samples that do not have it yet, then redraws."""
        if not self._attrs_loaded:
            self._attrs_loaded = True
            self._fill_attributes()
        cov, attrs = self.combo_cov.currentText(), self.wanted_attributes()
        attr = ', '.join(attrs) if attrs else '-'
        start, end = self._period()
        if start >= end:
            self.lbl_status.setText('A data inicial deve ser anterior à final.')
            return
        dst = QgsCoordinateReferenceSystem('EPSG:4326')
        erros = []
        def missing(s):
            have = self._series.get(s['id'], (None, {}))[1]
            return [a for a in attrs if a not in have]
        todo = [s for s in samples if missing(s)]
        if todo:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # the indices come along with the first query of each sample, so ticking them
            # later needs no new request
            available = {n for n in self.band_checks} or set(_PREFETCH)
            prefetch = [a for a in _PREFETCH if a in available]
            jobs = []
            for s in todo:
                pt = s['geom'].centroid().asPoint()  # the point itself for point samples
                src = s.get('crs')
                if src is not None and src.isValid() and src != dst:
                    pt = QgsCoordinateTransform(src, dst, QgsProject.instance()).transform(pt)
                have = self._series.get(s['id'], (None, {}))[1]
                need = missing(s) + [a for a in prefetch if a not in have and a not in attrs]
                jobs.append((s, (cov, tuple(need), round(pt.x(), 6), round(pt.y(), 6), start, end)))
            nodata_values(cov)  # filled once here, read by the worker threads
            # samples are queried in parallel (network only in the threads; Qt stays here)
            pending = {}
            with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
                for s, key in jobs:
                    if key not in self._cache:
                        pending[s['id']] = pool.submit(fetch_series, cov, key[2], key[3], start, end,
                                                       list(key[1]))
                while any(not f.done() for f in pending.values()):
                    done = sum(1 for f in pending.values() if f.done())
                    self.lbl_status.setText(f'Consultando o WTSS ({cov}, {attr}): '
                                            f'{done} de {len(pending)} amostra(s)...')
                    QApplication.processEvents()
                    time.sleep(0.05)
            for s, key in jobs:
                try:
                    if key not in self._cache:
                        self._cache[key] = pending[s['id']].result()
                    dates, values = self._cache[key]
                except Exception as e:
                    erros.append(f'{s["id"]}: {e}')
                    continue
                old = self._series.get(s['id'])
                merged = dict(old[1]) if old and old[0] == dates else {}
                merged.update(values)
                self._series[s['id']] = (dates, merged)
        finally:
            if todo:
                QApplication.restoreOverrideCursor()
        self._refresh_list()
        n = sum(1 for s in self._samples if s['id'] in self._series)
        msg = f'{n} série(s) de {cov}, {start:%d/%m/%Y} a {end:%d/%m/%Y}.'
        if erros:
            msg += f' {len(erros)} erro(s): {erros[0]}'
        self.lbl_status.setText(msg)
        self.redraw()

    # ------------------------------------------------------------------ selection
    def _refresh_list(self):
        checked = {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                   if self.list.item(i).checkState() == Qt.CheckState.Checked}
        first = self.list.count() == 0
        attr = (self.wanted_attributes() or [self.attribute()])[0]
        self.list.blockSignals(True)
        self.list.clear()
        for s in self._samples:
            vals = self._series.get(s['id'], (None, {}))[1].get(attr, [])
            n = sum(v is not None for v in vals)
            prefix = '▶ ' if s['id'] == self._focus else '● '
            it = QListWidgetItem(f'{prefix}{s["id"]} · {s["label"]} ({n} obs.)')
            it.setData(Qt.ItemDataRole.UserRole, s['id'])
            it.setForeground(QColor(s['color'] if QColor(s['color']).lightness() < 235 else '#888888'))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if first or s['id'] in checked or s['id'] == self._focus
                             else Qt.CheckState.Unchecked)
            self.list.addItem(it)
            if s['id'] == self._focus:
                it.setSelected(True)
        self.list.blockSignals(False)

    def _on_item_clicked(self, item):
        sid = item.data(Qt.ItemDataRole.UserRole)
        self.set_focus(None if sid == self._focus else sid)

    def set_focus(self, sample_id):
        """Shows only this sample (None: every checked sample)."""
        self._focus = sample_id
        self.btn_show_all.setEnabled(sample_id is not None)
        self._refresh_list()
        self.redraw()
        if sample_id is not None and self.on_focus is not None:
            s = next((x for x in self._samples if x['id'] == sample_id), None)
            if s is not None:
                self.on_focus(s)

    def _visible_samples(self):
        if self._focus is not None:
            return [s for s in self._samples if s['id'] == self._focus]
        checked = {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                   if self.list.item(i).checkState() == Qt.CheckState.Checked}
        return [s for s in self._samples if s['id'] in checked]

    # ------------------------------------------------------------------ plot
    def redraw(self):
        if self.figure is None:
            return
        wanted = self.wanted_attributes()
        # one attribute and no sample chosen: compare that attribute across the samples
        if len(wanted) != 1 or self._focus is not None or len(self._visible_samples()) < 2:
            return self._redraw_bands()
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        attr = wanted[0]
        label_attr = self.band_checks[attr].text() if attr in self.band_checks else attr
        window, order = self.spin_window.value(), self.spin_order.value()
        if window % 2 == 0:
            window += 1
        sozinha = self._focus is not None
        shown = 0
        for s in self._visible_samples():
            dates, values = self._series.get(s['id'], (None, {}))
            vals = values.get(attr) or []
            if not vals:
                continue
            color = s['color'] if QColor(s['color']).lightness() < 235 else '#888888'
            label = f'{s["id"]} · {s["label"]}'
            if self.chk_raw.isChecked():
                xs = [d for d, v in zip(dates, vals) if v is not None]
                ys = [v for v in vals if v is not None]
                ax.plot(xs, ys, color=color, alpha=0.45 if self.chk_sg.isChecked() else 0.9,
                        linewidth=1.0 if sozinha else 0.8, marker='o',
                        markersize=3.5 if sozinha else 2.5,
                        label=('original' if sozinha else None) if self.chk_sg.isChecked() else label)
            if self.chk_sg.isChecked():
                smooth = savitzky_golay(vals, window, order)
                if smooth is not None:
                    ax.plot(dates, smooth, color=color, linewidth=2.4 if sozinha else 1.8,
                            label=f'Savitzky-Golay ({window}, {order})' if sozinha else label)
            shown += 1
        if self.analysis_date:
            ax.axvline(self.analysis_date, color='#DC2626', linestyle='--', linewidth=1)
            ax.text(self.analysis_date, 0.98, 'data de análise ', color='#DC2626', fontsize=7,
                    va='top', ha='right', transform=ax.get_xaxis_transform())
        if sozinha:
            s = next((x for x in self._samples if x['id'] == self._focus), None)
            if s is not None:
                ax.set_title(f'{s["id"]} · {s["label"]}', fontsize=8, color='#888888')
        ax.set_ylabel(label_attr, fontsize=8)
        if is_index(attr):
            ax.set_ylim(-0.2, 1.0)
        else:
            ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
        if mdates is not None:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        if shown:
            ax.legend(fontsize=6, loc='lower left', ncol=1 if sozinha else 2)
        else:
            ax.text(0.5, 0.5, 'Nenhuma série carregada', ha='center', va='center',
                    transform=ax.transAxes, color='#8A93A2', fontsize=9)
        self.figure.autofmt_xdate()
        _theme_axes(self.figure, ax)
        self.canvas.draw_idle()

    def _redraw_bands(self):
        """Several spectral bands of one sample (the one clicked, else the first visible)."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        window, order = self.spin_window.value(), self.spin_order.value()
        if window % 2 == 0:
            window += 1
        vis = self._visible_samples()
        s = vis[0] if vis else None
        dates, values = self._series.get(s['id'], (None, {})) if s else (None, {})
        shown = 0
        for k, name in enumerate(self.wanted_attributes()):
            vals = values.get(name) or []
            if not vals or not dates:
                continue
            color = _BAND_COLORS[k % len(_BAND_COLORS)]
            label = self.band_checks[name].text() if name in self.band_checks else name
            if self.chk_raw.isChecked():
                xs = [d for d, v in zip(dates, vals) if v is not None]
                ys = [v for v in vals if v is not None]
                ax.plot(xs, ys, color=color, alpha=0.35 if self.chk_sg.isChecked() else 0.9,
                        linewidth=0.8, marker='o', markersize=2.5,
                        label=None if self.chk_sg.isChecked() else label)
            if self.chk_sg.isChecked():
                smooth = savitzky_golay(vals, window, order)
                if smooth is not None:
                    ax.plot(dates, smooth, color=color, linewidth=1.8, label=label)
            shown += 1
        if self.analysis_date:
            ax.axvline(self.analysis_date, color='#DC2626', linestyle='--', linewidth=1)
            ax.text(self.analysis_date, 0.02, 'data de análise ', color='#DC2626', fontsize=7,
                    va='bottom', ha='right', transform=ax.get_xaxis_transform())
        if s is not None:
            extra = '' if self._focus is not None or len(vis) == 1 else ' (clique numa amostra da lista para trocar)'
            ax.set_title(f'{s["id"]} · {s["label"]}{extra}', fontsize=8, color='#888888')
        com_indice = any(is_index(n) for n in self.wanted_attributes())
        ax.set_ylabel('Reflectância / índice' if com_indice else 'Reflectância', fontsize=8)
        if com_indice:
            ax.set_ylim(-0.2, 1.0)
        else:
            ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
        if mdates is not None:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        if shown:
            ax.legend(fontsize=6, loc='upper left', ncol=3)
        else:
            ax.text(0.5, 0.5, 'Carregue amostras e marque as bandas', ha='center', va='center',
                    transform=ax.transAxes, color='#8A93A2', fontsize=9)
        self.figure.autofmt_xdate()
        _theme_axes(self.figure, ax)
        self.canvas.draw_idle()
