# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# BDC Sentinel-2 images (S2-16D-2 cube, R11 G08 B04 composite) for the tile
# of the Pantanal Secondary Vegetation task.
#
# Nothing is written to disk: each year is a VRT in GDAL memory (/vsimem/)
# pointing to the BDC COGs over HTTP (/vsicurl/), so QGIS reads only the
# visible blocks. VRTs and layers are removed when the package is
# submitted, on logout and when the plugin is unloaded.

import json
import urllib.request
from datetime import date, timedelta

from osgeo import gdal

from xml.sax.saxutils import escape

from qgis.core import QgsContrastEnhancement, QgsProject, QgsRasterLayer, QgsLayerTreeGroup

STAC_URL = 'https://data.inpe.br/bdc/stac/v1/search'
DATA_URL = 'https://data.inpe.br/bdc/data/s2-16d/v2'
COLLECTION = 'S2-16D-2'
BANDS = ('B11', 'B08', 'B04')           # R, G, B
IMAGE_YEARS = (2026, 2025, 2024)
REF_MONTH, REF_DAY = 7, 28  # always the July 28 image of each year

GROUP_PREFIX = 'Imagens BDC'
VSIMEM_DIR = '/vsimem/sampledesign_bdc'
LAYER_PROP = 'sampledesign/bdc_image'  # marks the layers/groups created here

_TIMEOUT = 30

# Fixed contrast of the mapping image (S2-16D_V2_..._B11B08B04_contraste.tif): raw reflectance
# mapped to 0 and 255 per band, measured by fitting that image against the raw BDC bands.
# The VRT is written as 8-bit RGB with this stretch, so QGIS shows it as is (no auto-stretch)
# and every year and tile look alike.
STRETCH = {'B11': (1198, 4630), 'B08': (-1477, 5830), 'B04': (121, 1738)}


def _configure_gdal():
    """Faster remote reads, scoped to the BDC files only."""
    setp = getattr(gdal, 'SetPathSpecificOption', None)     # GDAL >= 3.6
    if setp is None:
        return
    prefix = '/vsicurl/https://data.inpe.br/'
    for k, v in (('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR'),
                 ('GDAL_HTTP_MULTIRANGE', 'YES'),
                 ('GDAL_HTTP_MERGE_CONSECUTIVE_RANGES', 'YES')):
        try:
            setp(prefix, k, v)
        except Exception:
            pass


def _unlink(path):
    """
    Deletes a /vsimem file, ignoring a missing one. QGIS enables
    gdal.UseExceptions(), and then gdal.Unlink() on a missing file raises.
    """
    try:
        gdal.Unlink(path)
    except Exception:
        pass


DEFAULT_REF = (REF_MONTH, REF_DAY)


def _ddmm(ref):
    return f'{ref[1]:02d}/{ref[0]:02d}'


def vrt_name(tile, year, ref=DEFAULT_REF):
    """
    Same name as option 1 of the BDC Downloader for the reference day:
    S2-16D_V2_<tile>_<YYYYMMDD>.vrt (e.g. ..._20240728.vrt, whose cube starts on July 27).
    """
    return f'S2-16D_V2_{tile}_{year}{ref[0]:02d}{ref[1]:02d}.vrt'


def composite_date(year, ref=DEFAULT_REF):
    """
    Start date of the 16-day cube containing the reference day. Cubes start on
    January 1 and step 16 days (in 2024 the cube with July 28 starts on July 27).
    """
    doy = date(year, ref[0], ref[1]).timetuple().tm_yday
    return date(year, 1, 1) + timedelta(days=((doy - 1) // 16) * 16)


def _stac_item(tile, year, ref=DEFAULT_REF):
    """STAC item whose period contains the reference day of the year (or None)."""
    body = json.dumps({
        'collections': [COLLECTION],
        'datetime': f'{year}-{ref[0]:02d}-{ref[1]:02d}T12:00:00Z',
        'query': {'bdc:tile': {'eq': tile}},
        'limit': 5,
    }).encode('utf-8')
    req = urllib.request.Request(STAC_URL, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Accept': 'application/geo+json',
        'User-Agent': 'SampleDesign-QGIS'})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        feats = json.loads(resp.read().decode('utf-8')).get('features') or []
    for f in feats:
        assets = f.get('assets') or {}
        if all(b in assets for b in BANDS):
            d = str((f.get('properties') or {}).get('datetime') or '')[:10]
            return d, [assets[b]['href'] for b in BANDS]
    return None


def _fallback_hrefs(tile, year, ref=DEFAULT_REF):
    """URLs built from the BDC naming pattern, used if STAC fails."""
    d = composite_date(year, ref)
    ds = d.strftime('%Y%m%d')
    base = f'{DATA_URL}/{tile[:3]}/{tile[3:]}/{d:%Y}/{d:%m}/{d:%d}/S2-16D_V2_{tile}_{ds}'
    return d.isoformat(), [f'{base}_{b}.tif' for b in BANDS]


def find_image(tile, year, ref=DEFAULT_REF):
    """(iso_date, [href_R, href_G, href_B], source) of the image of the reference day."""
    try:
        hit = _stac_item(tile, year, ref)
        if hit:
            return hit[0], hit[1], 'STAC'
    except Exception:
        pass
    d, hrefs = _fallback_hrefs(tile, year, ref)
    return d, hrefs, 'padrão de URL'


def build_vrt(tile, year, ref=DEFAULT_REF):
    """
    Builds the RGB VRT in memory (/vsimem). Returns (path, iso_date, error).
    """
    _configure_gdal()
    d, hrefs, origem = find_image(tile, year, ref)
    path = f'{VSIMEM_DIR}/{vrt_name(tile, year, ref)}'
    _unlink(path)
    err = write_rgb_vrt(path, hrefs)
    if err:
        return None, d, f'{err} (fonte: {origem})'
    return path, d, None


# ═══════════════════════════════════════════════════════════════════════
# Least-cloud composites of a month (PRODES protocol)
# ═══════════════════════════════════════════════════════════════════════
def month_composites(tile, year, month=7):
    """
    16-day composites of the tile that START in the month: [{date, slot, cloud, hrefs}],
    slot = position of the composite in the year (same slot = nearly the same dates every year).
    """
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    body = json.dumps({
        'collections': [COLLECTION],
        'datetime': f'{year}-{month:02d}-01T00:00:00Z/{year}-{month:02d}-{last:02d}T23:59:59Z',
        'query': {'bdc:tile': {'eq': tile}},
        'limit': 20,
    }).encode('utf-8')
    req = urllib.request.Request(STAC_URL, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Accept': 'application/geo+json',
        'User-Agent': 'SampleDesign-QGIS'})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        feats = json.loads(resp.read().decode('utf-8')).get('features') or []
    out = []
    for f in feats:
        props = f.get('properties') or {}
        assets = f.get('assets') or {}
        start = str(props.get('start_datetime') or props.get('datetime') or '')[:10]
        if not start or int(start[5:7]) != month or not all(b in assets for b in BANDS):
            continue
        d = date(int(start[:4]), int(start[5:7]), int(start[8:10]))
        out.append({'date': start, 'slot': (d - date(d.year, 1, 1)).days // 16,
                    'cloud': float(props.get('eo:cloud_cover') if props.get('eo:cloud_cover') is not None else 100),
                    'hrefs': [assets[b]['href'] for b in BANDS]})
    return sorted(out, key=lambda c: c['date'])


def best_aligned_composites(tile, years, month=7):
    """
    One composite per year, all in the same 16-day slot of the month (dates stay
    close across years), choosing the slot with the lowest total cloud cover. If no
    slot exists in every year, each year takes its own least-cloud composite.
    Returns {year: composite | None}.
    """
    by_year = {}
    for y in years:
        try:
            by_year[y] = month_composites(tile, y, month)
        except Exception:
            by_year[y] = []
    slots = None
    for comps in by_year.values():
        s = {c['slot'] for c in comps}
        slots = s if slots is None else slots & s
    if slots:
        def total(slot):
            return sum(next(c['cloud'] for c in by_year[y] if c['slot'] == slot) for y in years)
        best = min(sorted(slots), key=total)
        return {y: next(c for c in by_year[y] if c['slot'] == best) for y in years}
    return {y: (min(by_year[y], key=lambda c: c['cloud']) if by_year[y] else None) for y in years}


def write_rgb_vrt(path, hrefs):
    """
    8-bit RGB VRT (R=B11, G=B08, B=B04) reading the BDC COGs directly, with the fixed
    mapping contrast (STRETCH) applied by each source (ScaleOffset/ScaleRatio; GDAL clips
    to 0-255). Nothing is written to disk. Returns an error message or None.
    """
    try:
        src = gdal.Open('/vsicurl/' + hrefs[0])
    except Exception as e:
        return str(e)
    if src is None:
        return f'imagem não encontrada no BDC: {gdal.GetLastErrorMsg()}'
    xs, ys = src.RasterXSize, src.RasterYSize
    gt = ', '.join(repr(v) for v in src.GetGeoTransform())
    srs = escape(src.GetProjection())
    src = None
    bands = []
    for i, (name, href, interp) in enumerate(zip(BANDS, hrefs, ('Red', 'Green', 'Blue')), 1):
        lo, hi = STRETCH[name]
        ratio = 255.0 / (hi - lo)
        bands.append(f'''  <VRTRasterBand dataType="Byte" band="{i}">
    <ColorInterp>{interp}</ColorInterp>
    <ComplexSource>
      <SourceFilename relativeToVRT="0">{escape('/vsicurl/' + href)}</SourceFilename>
      <SourceBand>1</SourceBand>
      <ScaleOffset>{-lo * ratio!r}</ScaleOffset>
      <ScaleRatio>{ratio!r}</ScaleRatio>
      <NODATA>0</NODATA>
    </ComplexSource>
  </VRTRasterBand>''')
    xml = (f'<VRTDataset rasterXSize="{xs}" rasterYSize="{ys}">\n  <SRS>{srs}</SRS>\n'
           f'  <GeoTransform>{gt}</GeoTransform>\n' + '\n'.join(bands) + '\n</VRTDataset>\n')
    gdal.FileFromMemBuffer(path, xml.encode('utf-8'))
    return None


def raster_layer(path, name):
    """Raster layer of an 8-bit RGB VRT shown without any automatic contrast stretch."""
    lyr = QgsRasterLayer(path, name, 'gdal')
    if lyr.isValid():
        lyr.setContrastEnhancement(QgsContrastEnhancement.NoEnhancement)
    return lyr


def build_vrt_from(tile, iso_date, hrefs):
    """RGB VRT in memory for an explicit composite. Returns (path, error)."""
    _configure_gdal()
    path = f'{VSIMEM_DIR}/S2-16D_V2_{tile}_{iso_date.replace("-", "")}.vrt'
    _unlink(path)
    err = write_rgb_vrt(path, hrefs)
    return (None, err) if err else (path, None)


def load_tile_composites(tile, picks, log=None, month=7):
    """
    Loads the chosen composites ({year: composite}) into an "Imagens BDC — Tile X"
    group, one subgroup per year named with the date and cloud cover. Returns (group, subgroups).
    """
    log = log or (lambda m: None)
    remove_images()
    project = QgsProject.instance()
    meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
    group = project.layerTreeRoot().addGroup(f'{GROUP_PREFIX} — Tile {tile} ({meses[month - 1]}, menor nuvem)')
    group.setCustomProperty(LAYER_PROP, tile)
    subgroups = []
    for year, comp in picks.items():
        sub = group.addGroup(str(year))
        sub.setCustomProperty(LAYER_PROP, tile)
        subgroups.append(sub)
        if not comp:
            log(f'Imagem {year} do tile {tile}: nenhuma composição em {meses[month - 1]} no BDC.')
            sub.setName(f'{year} (indisponível)')
            continue
        d = comp['date']
        path, err = build_vrt_from(tile, d, comp['hrefs'])
        lyr = raster_layer(path, f'S2-16D_V2_{tile}_{d.replace("-", "")}.vrt') if path else None
        if err or lyr is None or not lyr.isValid():
            log(f'Imagem {year} do tile {tile}: {err or "o QGIS não conseguiu abrir o VRT."}')
            if path:
                _unlink(path)
            sub.setName(f'{year} (indisponível)')
            continue
        lyr.setCustomProperty(LAYER_PROP, tile)
        project.addMapLayer(lyr, False)
        sub.addLayer(lyr)
        sub.setName(f'{year} ({d[8:10]}/{d[5:7]}, {comp["cloud"]:.0f}% nuvem)')
        log(f'Imagem {year} carregada: composição de {d[8:10]}/{d[5:7]}/{d[:4]} '
            f'({comp["cloud"]:.1f}% de nuvem no tile)')
    return group, subgroups


# ═══════════════════════════════════════════════════════════════════════
# Project layers
# ═══════════════════════════════════════════════════════════════════════
def _group_name(tile, ref=DEFAULT_REF):
    return f'{GROUP_PREFIX} — Tile {tile} ({_ddmm(ref)})'


def load_tile_images(tile, log=None, years=IMAGE_YEARS, ref=DEFAULT_REF):
    """
    Loads the images of the reference day (month, day) of the given years into an
    "Imagens BDC — Tile XXXXXX" group with one subgroup per year. Returns (group, subgroups).
    """
    log = log or (lambda m: None)
    remove_images()
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group = root.addGroup(_group_name(tile, ref))  # bottom of the legend: samples stay on top
    group.setCustomProperty(LAYER_PROP, tile)
    subgroups = []
    for year in years:
        sub = group.addGroup(str(year))
        sub.setCustomProperty(LAYER_PROP, tile)
        subgroups.append(sub)
        try:
            _load_year(project, sub, tile, year, log, ref)
        except Exception as e:  # one failing year does not stop the others
            log(f'Imagem {year} do tile {tile}: {e}')
            sub.setName(f'{year} (indisponível)')
    return group, subgroups


def _load_year(project, sub, tile, year, log, ref=DEFAULT_REF):
    """RGB VRT (R11 G08 B04) of the reference day of the year, as a layer in the subgroup."""
    path, d, err = build_vrt(tile, year, ref)
    if err:
        log(f'Imagem {year} do tile {tile}: {err}')
        sub.setName(f'{year} (indisponível)')
        return
    lyr = raster_layer(path, vrt_name(tile, year, ref))
    if not lyr.isValid():
        log(f'Imagem {year} do tile {tile}: o QGIS não conseguiu abrir o VRT.')
        _unlink(path)
        sub.setName(f'{year} (indisponível)')
        return
    lyr.setCustomProperty(LAYER_PROP, tile)
    project.addMapLayer(lyr, False)
    sub.addLayer(lyr)
    dia = f'{d[8:10]}/{d[5:7]}/{d[0:4]}'
    nota = '' if d.endswith(f'-{ref[0]:02d}-{ref[1]:02d}') else \
        f' (cubo de 16 dias iniciado em {dia}, que contém {_ddmm(ref)})'
    log(f'Imagem {year} carregada: {lyr.name()}{nota}')


def remove_images():
    """Removes the image layers/groups from the project and the VRTs from memory."""
    project = QgsProject.instance()
    ids = [lid for lid, lyr in project.mapLayers().items()
           if lyr.customProperty(LAYER_PROP) is not None]
    if ids:
        project.removeMapLayers(ids)
    root = project.layerTreeRoot()
    # top-level groups only: year subgroups go with their parent
    topo = [n for n in root.findGroups(True)
            if n.customProperty(LAYER_PROP) is not None
            and not (isinstance(n.parent(), QgsLayerTreeGroup)
                     and n.parent().customProperty(LAYER_PROP) is not None)]
    for g in topo:
        g.parent().removeChildNode(g)
    _clear_vsimem()


def _clear_vsimem():
    try:
        files = gdal.ReadDirRecursive(VSIMEM_DIR) or []
    except Exception:
        files = []
    for f in files:
        _unlink(f'{VSIMEM_DIR}/{f}')
    try:
        gdal.RmdirRecursive(VSIMEM_DIR)
    except Exception:
        pass
