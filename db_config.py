# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

# Host, users and passwords of the PostgreSQL servers live in db_secrets.py, which is not
# versioned (template: db_secrets.example.py) and goes only in the zip given to the analysts.
# Without it the plugin has no database and works in API mode only.
DB_HOST = ''
DB_PORT = 5432
DB_NAME = 'biomas_amostras'

DB_ADMIN_USER = ''
DB_ADMIN_PASS = ''

DB_USER_USER = ''
DB_USER_PASS = ''

# Pantanal Vegetação Secundária database
PTN_DB = {'host': '', 'port': 5432, 'dbname': 'vs_pantanal',
          'admin_user': '', 'admin_pass': '', 'user_user': '', 'user_pass': ''}

try:
    from .db_secrets import *  # noqa: F401,F403
except ImportError:
    pass

DATABASE_CONFIG = {
    ('Pantanal', 'Vegetação Secundária'): PTN_DB,
}

BIOMAS = {
    'Amazônia': 'Amazônia',
    'Pantanal': 'Pantanal',
}

CLASSES_POR_BIOMA = {

    ('Amazônia', 'Prodes'): [
        ('Corte_Raso_Solo_Exposto',              'Corte Raso com Solo Exposto',          '#E3509F'),
        ('Corte_Raso_Herbaceas',                 'Corte Raso com Herbáceas',             '#EBEB1E'),
        ('Corte_Raso_Fogo',                      'Corte Raso com Fogo',                  '#000000'),
        ('Corte_Raso_Arvores_Remanescentes',     'Corte Raso com Árvores Remanescentes', '#EBEB1E'),
        ('Corte_Raso_Herbaceas_Arvores_Remanescentes', 'Corte Raso com Herbáceas e Árvores Remanescentes',  '#C49077'),
        ('Mineracao',                            'Mineração',                            '#7372C8'),
        ('Degradacao',                           'Degradação',                           '#B0BB5C'),
        ('Degradacao_Por_Fogo',                  'Degradação por Fogo',                  '#B82815'),
        ('Duna',                                 'Duna',                                 '#FFFFFF'),
        ('Banco_Areia',                          'Banco de Areia',                       '#FFF2CC'),
        ('Floresta',                             'Floresta',                             '#1E8449'),
        ('Floresta_Riparia',                     'Floresta Ripária',                     '#00FF00'),
        ('Floresta_De_Encosta',                  'Floresta de Encosta',                  '#55AA52'),
        ('Floresta_Transicional',                'Floresta Transicional',                '#8BCF5B'),
        ('Vegetacao_Natural_Nao_Florestal',      'Vegetação Natural Não-Florestal',      '#8BFCAC'),
        ('Corpo_Dagua',                          "Corpo D'Água",                         '#0394F2'),
        ('Area_Inundavel',                       'Área Inundável',                       '#89E1E1')
    ],

    # disabled project, kept for when it is enabled again
    # ('Amazônia', 'Vegetação Secundária'): [
    #     ('VS_Terra_Firme',                      'VS Terra Firme',                        '#2E7D32'),
    #     ('VS_Inundacao_Ocasional',              'VS Inundação Ocasional',                '#6EC6C6'),
    #     ('Area_Urbanizada',                     'Áreas Urbanizadas',                     '#E91E63'),
    #     ('Edificacoes',                         'Edificações',                           '#C2185B'),
    #     ('Agua_Cultura_Aquatica',               'Água: Artificial/Cultura Aquática',     '#0394F2'),
    #     ('Silvicultura',                        'Silvicultura',                          '#2E7D32'),
    #     ('Silvicultura_Caducifolia',            'Silvicultura de Espécie Caducifólia',   '#1B5E20'),
    #     ('Cultura_Perenne',                     'Cultura Perene',                        '#66BB6A'),
    #     ('Cultura_Temporaria',                  'Cultura Temporária',                    '#43A047'),
    #     ('Supressao_Mineracao',                 'Supressão Mineração',                   '#8D6E63'),
    #     ('Solo_Exposto',                        'Supressão com Solo Exposto',            '#D7CCC8'),
    #     ('Solo_Exposto_Antigo',                 'Supressão com Solo Exposto Antigo',     '#BCAAA4'),
    #     ('Solo_Exposto_Leiras',                 'Supressão com Solo Exposto e Leiras',   '#A1887F'),
    #     ('Vegetacao_Remanescente_Antiga',       'Supressão com Vegetação Remanescente Antiga', '#8E735B'),
    #     ('Vegetacao_Remanescente',              'Supressão com Vegetação Remanescente',        '#7D5A50'),
    #     ('Vegetacao_Remanescente_Leiras',       'Supressão com Vegetação e Leiras',            '#6D4C41'),
    #     ('Vegetacao_Campestre_Supressao',       'Supressão em Vegetação Campestre',            '#5D4037'),
    #     ('Pastagem_Antiga',                     'Pastagem Antiga',                             '#A1887F'),
    #     ('Pastagem_Rebrota_Antiga',             'Pastagem em Rebrota Antiga',                  '#8D6E63'),
    #     ('Pasto_Exotico_Supressao',             'Supressão com Pasto Exótico',                 '#6D4C41'),
    #     ('Fogo_Manejo_Pastagem',                'Fogo para Manejo da Pastagem',                '#D84315'),
    #     ('Queimada',                            'Queimada',                                    '#B71C1C'),
    #     ('Natural_Pos_Fogo',                    'Natural Pós Fogo',                            '#D32F2F'),
    #     ('Campo_Limpo_Umido',                   'Campo Limpo Úmido',                           '#AEEEEE'),
    #     ('Campo_Limpo_Seco',                    'Campo Limpo Seco',                            '#CDEB8B'),
    #     ('Campo_Sujo_Umido',                    'Campo Sujo Úmido',                            '#9CCC65'),
    #     ('Campo_Sujo_Seco',                     'Campo Sujo Seco',                             '#7CB342'),
    #     ('Savana_Florestada',                   'Savana Florestada',                           '#6B8E23'),
    #     ('Savana_Arborizada',                   'Savana Arborizada',                           '#7CB342'),
    #     ('Wetlands',                            'Wetlands',                                    '#00ACC1'),
    #     ('Area_Umida_Vegetada',                 'Áreas Úmidas com Vegetação',                  '#4DD0E1'),
    #     ('Hidrografia_Rio',                     'Hidrografia Rio',                             '#0288D1'),
    #     ('Hidrografia_Lago',                    'Hidrografia Lago',                            '#03A9F4'),
    #     ('Manejo',                              'Manejo',                                      '#FF7043')
    # ],

    ('Pantanal', 'Prodes'): [
    ('Area_Umida_Vegetada',                 'Áreas Úmidas com Vegetação',                  '#4DD0E1'),
    ('Campo_Com_Murunduns',                 'Campo com Murunduns',                         '#A5D6A7'),
    ('Campo_Limpo_Seco',                    'Campo Limpo Seco',                            '#CDEB8B'),
    ('Campo_Limpo_Umido',                   'Campo Limpo Úmido',                           '#AEEEEE'),
    ('Campo_Limpo_Umido_Mais_Biomassa',     'Campo Limpo Úmido Mais Biomassa',             '#81C784'),
    ('Campo_Limpo_Umido_Menos_Biomassa',    'Campo Limpo Úmido Menos Biomassa',            '#43A047'),
    ('Campo_Sujo_Seco',                     'Campo Sujo Seco',                             '#7CB342'),
    ('Campo_Sujo_Umido',                    'Campo Sujo Úmido',                            '#66BB6A'),
    ('Hidrografia',                         'Hidrografia',                                 '#0288D1'),
    ('Natural_Pos_Fogo_Savana',             'Natural Pós Fogo Savana',                     '#D32F2F'),
    ('Natural_Pos_Fogo_Herbacea',           'Natural Pós Fogo Herbácea',                   '#EF5350'),
    ('Queimada',                            'Queimada',                                    '#B71C1C'),
    ('Savana_Arborizada',                   'Savana Arborizada',                           '#7CB342'),
    ('Savana_Florestada',                   'Savana Florestada',                           '#6B8E23'),
    ('Supressao_Com_Arv_Remanescentes',     'Supressão com Arv. Remanescentes',            '#8E735B'),
    ('Supressao_Com_Pasto_Exotico',         'Supressão com Pasto Exótico',                 '#6D4C41'),
    ('Supressao_Com_Vegetacao_e_Leiras',    'Supressão com Vegetação e Leiras',            '#6D4C41'),
    ('Supressao_Com_SE',                    'Supressão com SE',                            '#D7CCC8'),
    ('Supressao_Com_SE_e_Arv_Remanescentes','Supressão com SE e Arv. Remanescentes',       '#BCAAA4'),
    ('Supressao_Com_SE_e_Leiras',           'Supressão com SE e Leiras',                   '#A1887F')
    ],

    ('Pantanal', 'Vegetação Secundária'): [
        ('vs',              'Vegetação Secundária',                '#29F300'),
        ('nao_vs',          'Não Vegetação Secundária',            '#000000')
    ],

    # starting list only: the classes of API projects are read from the API
    ('Amazônia', 'Não Floresta'): [
        # fallback only: the API list (nf_classes) is the one used
        ('Lago', 'Lago', '#1F78B4'),
        ('Rio', 'Rio', '#0394F2'),
        ('Ecotono', 'Ecótono', '#B2DF8A'),
        ('Herbacea_Seca_Mais_Biomassa', 'Herbácea Seca Mais Biomassa', '#E6C35C'),
        ('Herbacea_Seca_Menos_Biomassa', 'Herbácea Seca Menos Biomassa', '#F3E3A0'),
        ('Herbacea_Seca_Pos_Fogo', 'Herbácea Seca Pós-Fogo', '#C9A27E'),
        ('Herbacea_Umida', 'Herbácea Úmida', '#8BFCAC'),
        ('Mata', 'Mata', '#1E8449'),
        ('Vereda', 'Vereda', '#33A02C'),
        ('Fogo_Recente', 'Fogo Recente', '#E31A1C'),
        ('Fogo_Antigo', 'Fogo Antigo', '#8B1A1A'),
        ('Supressao_Para_Agricultura', 'Supressão Para Agricultura', '#E3509F'),
        ('Supressao_Para_Reservatorio', 'Supressão Para Reservatório', '#6A3D9A'),
        ('Supressao_Para_Solo_Exposto', 'Supressão Para Solo Exposto', '#FF7F00'),
        ('Supressao_Antiga_Com_Agricultura', 'Supressão Antiga Com Agricultura', '#F4A6CF'),
        ('Supressao_Antiga_Com_Reservatorio', 'Supressão Antiga Com Reservatório', '#CAB2D6'),
        ('Supressao_Antiga_Com_Solo_Exposto', 'Supressão Antiga Com Solo Exposto', '#FDBF6F'),
    ],
}

# projects offered at login, per biome
PROJETOS_POR_BIOMA = {
    'Amazônia': ['Prodes', 'Não Floresta'],
    'Pantanal': ['Prodes', 'Vegetação Secundária'],
}


# ─────────────────────────────────────────────────────────────────────
# pygeoapi (OGC API Features) - projects that work through the API and a
# SQLite work package instead of PostgreSQL/WFS.
# ─────────────────────────────────────────────────────────────────────
# Use 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 first
# and each request may lose ~2 s. For a published API use the HTTPS link,
# e.g. 'https://servidor.inpe.br/sampledesign/api'
API_LOCAL_URL     = 'http://127.0.0.1:5000'
API_TIMEOUT_S     = 60   # slow links (Tailscale Funnel) need time for pages with geometry
API_PAGE_SIZE     = 1000  # must be <= pygeoapi server.limits.max_items

# Published API access (leave empty for the local API without password).
# API_USER/API_PASSWORD → HTTP basic auth (e.g. Caddy/nginx basic_auth)
# API_KEY               → sent in the X-API-Key header
# API_CA_BUNDLE         → CA .crt/.pem file, only for a self-signed
#                         certificate (e.g. Caddy "tls internal")
API_USER      = ''
API_PASSWORD  = ''
API_KEY       = ''
API_CA_BUNDLE = ''

API_COLLECTIONS = {
    'amostras': 'output',  # samples (interpretation/audit)
    'tarefas':  'ptn_tasks',  # cells and locks
    'tiles':    'tiles_ptn',  # tile grid (read-only)
}

# Projects served by the API. For each one:
#   amostras/tarefas/tiles/classes  pygeoapi collections
#   modos       drawing modes offered ('point', 'square', 'polygon')
#   campos      extra sample fields of the samples collection
#   max_scale   fixed maximum zoom (1:x)
#   imagens     'fixas' = July 28 of IMAGE_YEARS (bdc_images);
#               'mes_menor_nuvem' = composites of mes_imagens in anos_imagens, same 16-day
#               slot every year, the one with the lowest total cloud cover
#   mascara     reference layers loaded with the images, clipped to the task tile:
#               camadas = [(source, origem, filter_by_year)], where source is an API
#               collection (e.g. 'nf_ref_supressao') or a TerraBrasilis WFS layer
#               ('workspace:layer'); cores = outline colour per origem (no fill)
API_PROJECTS = {
    ('Pantanal', 'Vegetação Secundária'): {
        'amostras': 'output', 'tarefas': 'ptn_tasks', 'tiles': 'tiles_ptn', 'classes': 'ptn_classes',
        'modos': ('polygon',), 'campos': (), 'max_scale': 50000, 'imagens': 'fixas',
    },
    ('Amazônia', 'Não Floresta'): {
        'amostras': 'nf_output', 'tarefas': 'nf_tasks', 'tiles': 'tiles_nf', 'classes': 'nf_classes',
        'modos': ('square', 'polygon', 'point'), 'campos': ('data_ref', 'tipo_geom'),
        'max_scale': 10000,
        # PRODES 2026: images of July 2026, 2025 and 2024 (lowest cloud cover)
        'ano_prodes': 2026, 'imagens': 'mes_menor_nuvem', 'anos_imagens': (2026, 2025, 2024),
        'mes_imagens': 7,
        # visual reference only (outlines): TerraBrasilis non-forest layers, loaded into the
        # NF database by criar_banco_nf.py and served by the API (they are not in the WFS)
        'mascara': {'ano': 2025, 'camadas': [
            # forest counter-mask (biome minus non-forest): black fill, alpha 150, drawn below
            ('nf_ref_contramascara', 'contramascara_floresta', False),
            # "Hidrografia" (general hydrography of the biome, TerraBrasilis)
            ('nf_ref_hidrografia_geral', 'hidrografia', False),
            # "Máscara de área acumulada de supressão da vegetação nativa não florestal (2000)"
            ('nf_ref_supressao', 'supressao_nf', False),
            # "Hidrografia em não floresta"
            ('nf_ref_hidrografia', 'hidrografia_nf', False),
            # "Incrementos de supressão da vegetação nativa não florestal" (up to the mask year)
            ('nf_ref_incremento', 'incremento_nf', True),
            # "Resíduo anual na supressão da vegetação nativa não florestal" (up to the mask year)
            ('nf_ref_residuo', 'residuo_nf', True),
        ], 'cores': {'supressao_nf': '#FFFF00', 'hidrografia_nf': '#0070FF',
                     'incremento_nf': '#FF3030', 'residuo_nf': '#FF00FF',
                     'hidrografia': '#1E90FF', 'contramascara_floresta': '0,0,0,155'}},
        # TerraClass Amazônia auxiliary layers (raster clip of the tile, terraclass.py)
        'terraclass': (2024,),
    },
}

# Administrators in API-only mode (PostgreSQL unreachable, so the login cannot
# be checked). With PostgreSQL available, interpreters.is_admin is used.
API_ADMINS = ['miguel.cunha']

# Suggested folder for the SQLite (GeoPackage) work packages.
# Empty = last folder used, or the user's Documents folder.
PACOTES_DIR = ''
