# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

DB_HOST = '150.163.2.224'
DB_PORT = 5432
DB_NAME = 'biomas_amostras'

DB_ADMIN_USER = 'adm_amz'
DB_ADMIN_PASS = '@dm@mz'

DB_USER_USER = 'user_amz'
DB_USER_PASS = 'biomaamazonia'

DATABASE_CONFIG = {
    ('Pantanal', 'Vegetação Secundária'): {
        'host': '150.163.2.224',
        'port': 5432,
        'dbname': 'vs_pantanal',
        'admin_user': 'ptn_wfs',
        'admin_pass': 'PTN@1',
        'user_user': 'ptn_wfs',     
        'user_pass': 'PTN@1',
    },
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

    ('Amazônia', 'Vegetação Secundária'): [
        ('VS_Terra_Firme',                      'VS Terra Firme',                        '#2E7D32'),
        ('VS_Inundacao_Ocasional',              'VS Inundação Ocasional',                '#6EC6C6'),
        ('Area_Urbanizada',                     'Áreas Urbanizadas',                     '#E91E63'),
        ('Edificacoes',                         'Edificações',                           '#C2185B'),
        ('Agua_Cultura_Aquatica',               'Água: Artificial/Cultura Aquática',     '#0394F2'),
        ('Silvicultura',                        'Silvicultura',                          '#2E7D32'),
        ('Silvicultura_Caducifolia',            'Silvicultura de Espécie Caducifólia',   '#1B5E20'),
        ('Cultura_Perenne',                     'Cultura Perene',                        '#66BB6A'),
        ('Cultura_Temporaria',                  'Cultura Temporária',                    '#43A047'),
        ('Supressao_Mineracao',                 'Supressão Mineração',                   '#8D6E63'),
        ('Solo_Exposto',                        'Supressão com Solo Exposto',            '#D7CCC8'),
        ('Solo_Exposto_Antigo',                 'Supressão com Solo Exposto Antigo',     '#BCAAA4'),
        ('Solo_Exposto_Leiras',                 'Supressão com Solo Exposto e Leiras',   '#A1887F'),
        ('Vegetacao_Remanescente_Antiga',       'Supressão com Vegetação Remanescente Antiga', '#8E735B'),
        ('Vegetacao_Remanescente',              'Supressão com Vegetação Remanescente',        '#7D5A50'),
        ('Vegetacao_Remanescente_Leiras',       'Supressão com Vegetação e Leiras',            '#6D4C41'),
        ('Vegetacao_Campestre_Supressao',       'Supressão em Vegetação Campestre',            '#5D4037'),
        ('Pastagem_Antiga',                     'Pastagem Antiga',                             '#A1887F'),
        ('Pastagem_Rebrota_Antiga',             'Pastagem em Rebrota Antiga',                  '#8D6E63'),
        ('Pasto_Exotico_Supressao',             'Supressão com Pasto Exótico',                 '#6D4C41'),
        ('Fogo_Manejo_Pastagem',                'Fogo para Manejo da Pastagem',                '#D84315'),
        ('Queimada',                            'Queimada',                                    '#B71C1C'),
        ('Natural_Pos_Fogo',                    'Natural Pós Fogo',                            '#D32F2F'),
        ('Campo_Limpo_Umido',                   'Campo Limpo Úmido',                           '#AEEEEE'),
        ('Campo_Limpo_Seco',                    'Campo Limpo Seco',                            '#CDEB8B'),
        ('Campo_Sujo_Umido',                    'Campo Sujo Úmido',                            '#9CCC65'),
        ('Campo_Sujo_Seco',                     'Campo Sujo Seco',                             '#7CB342'),
        ('Savana_Florestada',                   'Savana Florestada',                           '#6B8E23'),
        ('Savana_Arborizada',                   'Savana Arborizada',                           '#7CB342'),
        ('Wetlands',                            'Wetlands',                                    '#00ACC1'),
        ('Area_Umida_Vegetada',                 'Áreas Úmidas com Vegetação',                  '#4DD0E1'),
        ('Hidrografia_Rio',                     'Hidrografia Rio',                             '#0288D1'),
        ('Hidrografia_Lago',                    'Hidrografia Lago',                            '#03A9F4'),
        ('Manejo',                              'Manejo',                                      '#FF7043')
    ],

    ('Pantanal', 'Prodes'): [
        ('VS_Inundacao_Ocasional',              'VS Inundação Ocasional',                '#6EC6C6'),
        ('VS_Terra_Firme',                      'VS Terra Firme',                        '#2E7D32'),
        ('Area_Urbanizada',                     'Áreas Urbanizadas',                     '#E91E63'),
        ('Edificacoes',                         'Edificações',                           '#C2185B'),
        ('Agua_Cultura_Aquatica',               'Água: Artificial/Cultura Aquática',     '#0394F2'),
        ('Silvicultura',                        'Silvicultura',                          '#2E7D32'),
        ('Silvicultura_Caducifolia',            'Silvicultura de Espécie Caducifólia',   '#1B5E20'),
        ('Cultura_Perenne',                     'Cultura Perene',                        '#66BB6A'),
        ('Cultura_Temporaria',                  'Cultura Temporária',                    '#43A047'),
        ('Supressao_Mineracao',                 'Supressão Mineração',                   '#8D6E63'),
        ('Solo_Exposto',                        'Supressão com Solo Exposto',            '#D7CCC8'),
        ('Solo_Exposto_Antigo',                 'Supressão com Solo Exposto Antigo',     '#BCAAA4'),
        ('Solo_Exposto_Leiras',                 'Supressão com Solo Exposto e Leiras',   '#A1887F'),
        ('Vegetacao_Remanescente_Antiga',       'Supressão com Vegetação Remanescente Antiga', '#8E735B'),
        ('Vegetacao_Remanescente',              'Supressão com Vegetação Remanescente',        '#7D5A50'),
        ('Vegetacao_Remanescente_Leiras',       'Supressão com Vegetação e Leiras',            '#6D4C41'),
        ('Vegetacao_Campestre_Supressao',       'Supressão em Vegetação Campestre',            '#5D4037'),
        ('Pastagem_Antiga',                     'Pastagem Antiga',                             '#A1887F'),
        ('Pastagem_Rebrota_Antiga',             'Pastagem em Rebrota Antiga',                  '#8D6E63'),
        ('Pasto_Exotico_Supressao',             'Supressão com Pasto Exótico',                 '#6D4C41'),
        ('Fogo_Manejo_Pastagem',                'Fogo para Manejo da Pastagem',                '#D84315'),
        ('Queimada',                            'Queimada',                                    '#B71C1C'),
        ('Natural_Pos_Fogo',                    'Natural Pós Fogo',                            '#D32F2F'),
        ('Campo_Limpo_Umido',                   'Campo Limpo Úmido',                           '#AEEEEE'),
        ('Campo_Limpo_Seco',                    'Campo Limpo Seco',                            '#CDEB8B'),
        ('Campo_Sujo_Umido',                    'Campo Sujo Úmido',                            '#66BB6A'),
        ('Campo_Limpo_Umido_Mais_Biomassa',     'Campo Limpo Umido Mais Biomassa',             '#81C784'),
        ('Campo_Limpo_Umido_Menos_Biomassa',    'Campo Limpo Umido Menos Biomassa',            '#43A047'),
        ('Campo_Limpo_Menos_Biomassa',          'Campo Limpo Menos Biomassa',                  '#2E7D32'),
        ('Campo_Com_Murunduns',                 'Campo Com Murunduns',                         '#A5D6A7'),
        ('Campo_Sujo_Seco',                     'Campo Sujo Seco',                             '#7CB342'),
        ('Savana_Florestada',                   'Savana Florestada',                           '#6B8E23'),
        ('Savana_Arborizada',                   'Savana Arborizada',                           '#7CB342'),
        ('Wetlands',                            'Wetlands',                                    '#00ACC1'),
        ('Area_Umida_Vegetada',                 'Áreas Úmidas com Vegetação',                  '#4DD0E1'),
        ('Hidrografia_Rio',                     'Hidrografia Rio',                             '#0288D1'),
        ('Hidrografia_Lago',                    'Hidrografia Lago',                            '#03A9F4'),
        ('Manejo',                              'Manejo',                                      '#FF7043')
    ],

    ('Pantanal', 'Vegetação Secundária'): [
        ('vs',              'Vegetação Secundária',                '#29F300'),
        ('nao_vs',          'Não Vegetação Secundária',            '#000000')
    ]
}
