# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# TerraClass Amazônia (Embrapa/INPE) as auxiliary layers of the task tile.
#
# Raster, not vector: the TerraClass GeoServer serves the maps as WCS coverages, so only
# the piece of the tile is downloaded (about 5-10 s and 14 MB per year, ~0.4 MB once
# stored compressed), while the vector data is only offered for the whole biome. The clip
# is requested at ~30 m (the native TerraClass resolution; the coverage is resampled to
# 10 m in EPSG:3857), reprojected to EPSG:4674 (the CRS of every other layer of the task),
# cut to the tile outline and kept in a temporary folder of the QGIS session (not in the
# workspace). The folder is deleted when the package or the plugin is closed, and folders
# left by earlier sessions (QGIS killed) are deleted the next time.

import glob
import os
import shutil
import tempfile
import urllib.parse
import urllib.request

from osgeo import gdal, ogr, osr
from qgis.core import (QgsColorRampShader, QgsPalettedRasterRenderer, QgsProject,
                       QgsRasterLayer)
from qgis.PyQt.QtGui import QColor

WCS_URL = 'https://www.terraclass.gov.br/geoserver/ows'
COVERAGE = 'TerraClass__tc_amazonia_{year}_raster'
SCALE = '0.3333'          # 10 m coverage -> ~30 m
_TIMEOUT = 300
TC_PROP = 'sampledesign/terraclass'   # marks the TerraClass layers in the project
GROUP_NAME = 'TerraClass'

# official legend (same codes and colours in 2022 and 2024, from the GeoServer SLD)
LEGEND = [
    (1, '#005500', 'Vegetação Natural Florestal Primária'),
    (2, '#0fc80f', 'Vegetação Natural Florestal Secundária'),
    (9, '#a8a800', 'Silvicultura'),
    (10, '#e6a04b', 'Pastagem Arbustiva/Arbórea'),
    (11, '#ffec87', 'Pastagem Herbácea'),
    (12, '#ff8828', 'Cultura Agrícola Perene'),
    (13, '#996400', 'Cultura Agrícola Semiperene'),
    (14, '#ffe300', 'Cultura Agrícola Temporária de 1 Ciclo'),
    (15, '#ffff00', 'Cultura Agrícola Temporária de Mais de 1 Ciclo'),
    (16, '#ad89cd', 'Mineração'),
    (17, '#ffa8c0', 'Urbanizada'),
    (20, '#e1e1e1', 'Outros Usos'),
    (22, '#ff0000', 'Desflorestamento no Ano'),
    (23, '#0000ff', "Corpo D'Água"),
    (25, '#ffffff', 'Não Observado'),
    (51, '#b4d79e', 'Natural Não Florestal'),
]


_TMP_PREFIX = 'sampledesign_terraclass_'
_tmp_dir = None


def _session_dir():
    """Temporary folder of this QGIS session (created on first use)."""
    global _tmp_dir
    if _tmp_dir is None or not os.path.isdir(_tmp_dir):
        _remove_stale_dirs()
        _tmp_dir = tempfile.mkdtemp(prefix=_TMP_PREFIX)
    return _tmp_dir


def _remove_stale_dirs():
    """Folders of earlier sessions (a folder still in use is locked and stays)."""
    for d in glob.glob(os.path.join(tempfile.gettempdir(), _TMP_PREFIX + '*')):
        if d != _tmp_dir:
            shutil.rmtree(d, ignore_errors=True)


def tile_file(package_path, year):
    base = os.path.splitext(os.path.basename(package_path))[0]
    return os.path.join(_session_dir(), f'{base}_terraclass_{year}.tif')


def cleanup(package_path=None):
    """
    Removes the TerraClass layers and every temporary file they used (clips, .part,
    .aux.xml); with package_path, also clips stored next to the package by older versions.
    """
    global _tmp_dir
    remove_layers()
    if _tmp_dir:
        shutil.rmtree(_tmp_dir, ignore_errors=True)
        _tmp_dir = None
    if package_path:
        base = os.path.splitext(package_path)[0]
        for f in glob.glob(glob.escape(base) + '_terraclass_*'):
            try:
                os.remove(f)
            except OSError:
                pass


def download_tile(year, tile_wkt_4674, out_path, log=None):
    """Clip of TerraClass `year` for the tile (WKT in EPSG:4674), saved as a compressed GeoTIFF."""
    log = log or (lambda m: None)
    gdal.UseExceptions()
    src = osr.SpatialReference(); src.ImportFromEPSG(4674)
    dst = osr.SpatialReference(); dst.ImportFromEPSG(3857)
    for s in (src, dst):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geom = ogr.CreateGeometryFromWkt(tile_wkt_4674)
    geom.Transform(osr.CoordinateTransformation(src, dst))
    x0, x1, y0, y1 = geom.GetEnvelope()
    q = [('service', 'WCS'), ('version', '2.0.1'), ('request', 'GetCoverage'),
         ('coverageId', COVERAGE.format(year=year)), ('format', 'image/tiff'),
         ('subset', f'X({x0:.2f},{x1:.2f})'), ('subset', f'Y({y0:.2f},{y1:.2f})'),
         ('scaleFactor', SCALE)]
    log(f'TerraClass {year}: baixando o recorte do tile...')
    req = urllib.request.Request(f'{WCS_URL}?{urllib.parse.urlencode(q)}',
                                 headers={'User-Agent': 'SampleDesign-QGIS'})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = resp.read()
    if not data.startswith((b'II*', b'MM\x00*')):
        raise RuntimeError(f'resposta inesperada do TerraClass: {data[:200]!r}')
    raw = f'/vsimem/tc_{year}_raw.tif'
    cut = f'/vsimem/tc_{year}_cut.shp'
    gdal.FileFromMemBuffer(raw, data)
    try:
        # cut to the tile outline (outside = no data)
        drv = ogr.GetDriverByName('ESRI Shapefile')
        ds_cut = drv.CreateDataSource(cut)
        lyr = ds_cut.CreateLayer('tile', dst, ogr.wkbPolygon)
        f = ogr.Feature(lyr.GetLayerDefn()); f.SetGeometry(geom); lyr.CreateFeature(f)
        f = None; ds_cut = None
        tmp = out_path + '.part'
        out = gdal.Warp(tmp, raw, options=gdal.WarpOptions(
            format='GTiff', dstSRS='EPSG:4674', cutlineDSName=cut, cropToCutline=True,
            dstNodata=0, resampleAlg='near',
            creationOptions=['COMPRESS=DEFLATE', 'TILED=YES']))
        out = None   # closes the file (written to disk only now)
        os.replace(tmp, out_path)
    finally:
        gdal.Unlink(raw)
        for ext in ('shp', 'shx', 'dbf', 'prj'):
            try:
                gdal.Unlink(cut[:-3] + ext)
            except RuntimeError:
                pass
    return out_path


def raster_layer(path, year):
    """TerraClass layer with the official classes and colours."""
    lyr = QgsRasterLayer(path, f'TerraClass {year}')
    if not lyr.isValid():
        return None
    classes = [QgsPalettedRasterRenderer.Class(v, QColor(c), label) for v, c, label in LEGEND]
    lyr.setRenderer(QgsPalettedRasterRenderer(lyr.dataProvider(), 1, classes))
    lyr.setCustomProperty(TC_PROP, str(year))
    return lyr


def add_layers(layers, below_prop):
    """
    Adds the layers in a "TerraClass" group placed right above the node marked with
    `below_prop` (the images group), so the reference outlines stay on top. The layers
    come unchecked: they are opaque and would hide the images.
    """
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    idx = len(root.children())
    for i, node in enumerate(root.children()):
        if node.customProperty(below_prop) is not None:
            idx = i
            break
    group = root.insertGroup(idx, GROUP_NAME)
    group.setCustomProperty(TC_PROP, '1')
    for lyr in layers:
        project.addMapLayer(lyr, False)
        node = group.addLayer(lyr)
        node.setItemVisibilityChecked(False)
    group.setExpanded(False)
    return group


def remove_layers():
    project = QgsProject.instance()
    ids = [lid for lid, lyr in project.mapLayers().items() if lyr.customProperty(TC_PROP) is not None]
    if ids:
        project.removeMapLayers(ids)
    root = project.layerTreeRoot()
    for g in [g for g in root.findGroups(True) if g.customProperty(TC_PROP) is not None]:
        (g.parent() or root).removeChildNode(g)
