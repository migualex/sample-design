# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha
#
# Reference layers of the task tile (for NF: TerraBrasilis "Máscara de área acumulada de
# supressão da vegetação nativa não florestal (2000)" and "Hidrografia em não floresta"),
# read only inside the tile and stored in the work package (layer "mascara"), so they also
# work offline. They are drawn as outlines only, as a visual reference over the images.
#
# A source is either an API collection (the NF layers are only published as shapefiles, so
# criar_banco_nf.py loads them into the NF database and the API serves them by bbox) or a
# TerraBrasilis WFS layer ('workspace:layer').

import json
import urllib.parse
import urllib.request

from qgis.core import (Qgis, QgsWkbTypes, QgsFeature, QgsFillSymbol, QgsGeometry,
                       QgsProject, QgsCategorizedSymbolRenderer, QgsRendererCategory)

from .api_local import geojson_to_wkt

WFS_URL = 'https://terrabrasilis.dpi.inpe.br/geoserver/ows'
MASK_PROP = 'sampledesign/mascara'   # marks the mask layer in the project
# bump when the processing or the layers change, so packages download the mask again
# (2: invalid TerraBrasilis polygons repaired before clipping; 3: NF reference layers)
MASK_VERSION = 5   # 4: NF increments and residue; 5: general hydrography and forest counter-mask
_TIMEOUT = 180

# names shown in the legend for each origem
ORIGEM_NOMES = {
    'supressao_nf': 'Supressão da vegetação nativa não florestal (acumulada 2000)',
    'hidrografia_nf': 'Hidrografia em não floresta',
    'incremento_nf': 'Incrementos de supressão da vegetação nativa não florestal',
    'residuo_nf': 'Resíduo anual na supressão da vegetação nativa não florestal',
    'hidrografia': 'Hidrografia',
    'contramascara_floresta': 'Contramáscara das áreas florestais',
}
# origens drawn as a translucent fill (no outline) instead of an outline
FILLED = {'contramascara_floresta'}


def _fetch_wfs(typename, bbox):
    """GeoJSON features of a WFS layer inside bbox (lon/lat: xmin, ymin, xmax, ymax)."""
    params = {
        'service': 'WFS', 'version': '1.1.0', 'request': 'GetFeature',
        'typeName': typename, 'outputFormat': 'application/json',
        'BBOX': ','.join(f'{v:.6f}' for v in bbox) + ',EPSG:4326',
    }
    req = urllib.request.Request(f'{WFS_URL}?{urllib.parse.urlencode(params)}',
                                 headers={'User-Agent': 'SampleDesign-QGIS'})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8')).get('features') or []


def _fetch_api(client, collection, bbox):
    """Features of an API collection intersecting bbox (lon/lat)."""
    if client is None:
        raise RuntimeError(f'API indisponível para ler {collection}')
    # bbox in the storage CRS (EPSG:4674, lon/lat): pygeoapi 0.21 swaps the axes when it
    # converts a CRS84 bbox to EPSG:4674 and then finds nothing; in the storage CRS the bbox
    # is used as is
    return client.list_items(collection, {
        'bbox': ','.join(f'{v:.6f}' for v in bbox),
        'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4674',
    })


# kept for older callers/tests
_fetch_layer = _fetch_wfs


def fetch_tile_mask(tile_geom, year, layers, log=None, client=None):
    """
    Reference features of the tile: list of (origem, ano, classe, QgsGeometry), clipped to
    the tile. layers = [(source, origem, filter_by_year)]; source 'workspace:layer' is read
    from the TerraBrasilis WFS, any other name from the API collection of that name.
    """
    log = log or (lambda m: None)
    bb = tile_geom.boundingBox()
    bbox = (bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum())
    out = []
    for source, origem, by_year in layers:
        nome = ORIGEM_NOMES.get(origem, origem)
        if ':' in source:
            log(f'Máscara: baixando {nome} do TerraBrasilis...')
            feats = _fetch_wfs(source, bbox)
        else:
            log(f'Máscara: baixando {nome} da API...')
            feats = _fetch_api(client, source, bbox)
        n = 0
        for f in feats:
            p = f.get('properties') or {}
            ano = p.get('year')
            if by_year and ano is not None and int(ano) > year:
                continue
            wkt = geojson_to_wkt(f.get('geometry'))
            if not wkt:
                continue
            g = QgsGeometry.fromWkt(wkt)
            if g.isEmpty():
                continue
            # many TerraBrasilis polygons are invalid (self-intersections): clipped as they
            # are they turn into broken shapes, so repair them first
            if not g.isGeosValid():
                g = g.makeValid()
            if not g.intersects(tile_geom):
                continue
            g = g.intersection(tile_geom)
            if QgsWkbTypes.flatType(g.wkbType()) == Qgis.WkbType.GeometryCollection:
                g.convertGeometryCollectionToSubclass(Qgis.GeometryType.Polygon)
            if g.isEmpty() or g.area() <= 0:
                continue
            try:
                ano = int(ano) if ano not in (None, '') else None
            except (TypeError, ValueError):
                ano = None
            out.append((origem, ano, str(p.get('class_name') or p.get('main_class') or ''), g))
            n += 1
        log(f'Máscara: {n} polígono(s) de {nome}.')
    return out


def write_mask(layer, features):
    """Replaces the content of the package mask layer."""
    pr = layer.dataProvider()
    pr.truncate()
    novos = []
    for origem, ano, classe, g in features:
        g = QgsGeometry(g)
        g.convertToMultiType()
        f = QgsFeature(layer.fields())
        f.setGeometry(g)
        f['origem'] = origem
        f['ano'] = ano
        f['classe'] = classe
        novos.append(f)
    if novos:
        pr.addFeatures(novos)
    layer.updateExtents()
    return len(novos)


MASK_FILL = '0,0,0,155'   # black, alpha 155: fill of every mask


def _outline_symbol(color, width=0.5):
    """Black translucent fill (alpha 155) with the coloured outline of the layer."""
    return QgsFillSymbol.createSimple({
        'style': 'solid', 'color': MASK_FILL,
        'outline_style': 'solid', 'outline_color': color, 'outline_width': str(width),
        'outline_width_unit': 'MM',
    })


def _fill_symbol(color):
    """Black translucent fill without outline (the forest counter-mask)."""
    return QgsFillSymbol.createSimple({'style': 'solid', 'color': color, 'outline_style': 'no'})


def style_mask(layer, colors):
    """
    Every mask: black fill (alpha 155) with one outline colour per origem (e.g. suppression
    yellow, hydrography blue); origens in FILLED (forest counter-mask) are fill only, no
    outline, drawn below the others.
    """
    cats = []
    for origem, color in colors.items():
        filled = origem in FILLED
        sym = _fill_symbol(color) if filled else _outline_symbol(color)
        sym.symbolLayer(0).setRenderingPass(0 if filled else 1)
        cats.append(QgsRendererCategory(origem, sym, ORIGEM_NOMES.get(origem, origem)))
    renderer = QgsCategorizedSymbolRenderer('origem', cats)
    renderer.setUsingSymbolLevels(True)
    layer.setRenderer(renderer)
    layer.setOpacity(1.0)
    layer.triggerRepaint()


def add_above_images(layer, images_prop):
    """Adds the mask layer right above the image group (below the sample layers)."""
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    project.addMapLayer(layer, False)
    idx = len(root.children())
    for i, node in enumerate(root.children()):
        if node.customProperty(images_prop) is not None:
            idx = i
            break
    root.insertLayer(idx, layer)
    layer.setCustomProperty(MASK_PROP, '1')


def remove_masks():
    project = QgsProject.instance()
    ids = [lid for lid, lyr in project.mapLayers().items() if lyr.customProperty(MASK_PROP) is not None]
    if ids:
        project.removeMapLayers(ids)
