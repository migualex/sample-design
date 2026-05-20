# -*- coding: utf-8 -*-
"""
db_config.py — Configurações de conexão PostgreSQL e classes por bioma.
"""

# ── Conexão PostgreSQL ──────────────────────────────────────────
DB_HOST = '150.163.2.224'
DB_PORT = 5432
DB_NAME = 'biomas_amostras'

DB_ADMIN_USER = 'adm_amz'
DB_ADMIN_PASS = '@dm@mz'

DB_USER_USER = 'user_amz'
DB_USER_PASS = 'biomaamazonia'

# ── Biomas disponíveis (apenas para tela de login) ──────────────
BIOMAS = {
    'Amazônia': 'Amazônia',
    'Pantanal': 'Pantanal',
}

# ── Classes padrão por (bioma, project_type) ───────────────────
# Cada item: (código_sem_acento, nome_com_acento, cor_hex)
CLASSES_POR_BIOMA = {

    ('Amazônia', 'Prodes'): [
        ('Corte_Raso_Com_Arvores_Remanescentes', 'Corte Raso com Árvores Remanescentes', '#D2A679'),
        ('Corte_Raso',                           'Corte Raso',                           '#E3509F'),
        ('Corte_Raso_Antigo',                    'Corte Raso Antigo',                    '#E3BCDC'),
        ('Corte_Raso_Com_Vegetacao',             'Corte Raso com Vegetação',             '#EBEB1E'),
        ('Corte_Raso_Antigo_Com_Vegetacao',      'Corte Raso com Vegetação Antigo',      '#F4E4A6'),
        ('Degradacao',                           'Degradação',                           '#7D9D5A'),
        ('Degradacao_Por_Fogo',                  'Degradação por Fogo',                  '#B82815'),
        ('Floresta',                             'Floresta',                             '#1E8449'),
        ('Floresta_Transicional',                'Floresta Transicional',                '#55AA52'),
        ('Vegetacao_Natural_Nao_Florestal',      'Vegetação Natural Não-Florestal',      '#8BCF5B'),
        ('Corpo_Dagua',                          "Corpo D'Água",                         '#0394F2'),
        ('Area_Inundavel',                       'Área Inundável',                       '#89E1E1'),
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
        ('Hidrografia_Rio', 'Hidrografia Rio', '#0288D1'),
        ('Queimada', 'Queimada', '#B71C1C'),
        ('Supressao_com_solo_exposto_e_leiras', 'Supressão com Solo Exposto e Leiras', '#A1887F'),
        ('Supressao_com_solo_exposto_e_vegetacao_remanescente', 'Supressão com Solo Exposto e Vegetação Remanescente', '#8D6E63'),
        ('Campo_Limpo_umido', 'Campo Limpo Úmido', '#AEEEEE'),
        ('Campo_Limpo_seco', 'Campo Limpo Seco', '#CDEB8B'),
        ('Campo_Sujo_umido', 'Campo Sujo Úmido', '#9CCC65'),
        ('Campo_Sujo_seco', 'Campo Sujo Seco', '#7CB342'),
        ('Savana_Florestada', 'Savana Florestada', '#6B8E23'),
        ('Savana_Arborizada', 'Savana Arborizada', '#7CB342'),
        ('Supressao_com_vegetacao_remanescente_antigo', 'Supressão com Vegetação Remanescente Antigo', '#7D5A50'),
        ('Supressao_com_vegetacao_remanescente', 'Supressão com Vegetação Remanescente', '#6D4C41'),
        ('Supressao_com_solo_exposto_antigo', 'Supressão com Solo Exposto Antigo', '#BCAAA4'),
        ('Supressao_com_solo_exposto', 'Supressão com Solo Exposto', '#D7CCC8'),
        ('Supressao_com_solo_exposto_e_vegetacao_remanescente_antigo', 'Supressão com Solo Exposto e Vegetação Remanescente Antigo', '#8E735B'),
        ('Supressao_com_solo_exposto_e_vegetacao_remanescente', 'Supressão com Solo Exposto e Vegetação Remanescente', '#A1887F'),
        ('Supressao_com_solo_exposto_e_leiras', 'Supressão com Solo Exposto e Leiras', '#A1887F'),
        ('Supressao_com_vegetacao_e_leiras', 'Supressão com Vegetação e Leiras', '#6D4C41'),
        ('Supressao_com_pasto_exotico', 'Supressão com Pasto Exótico', '#6D4C41'),
        ('Pastagem_Antigo', 'Pastagem Antigo', '#A1887F'),
        ('Pastagem_em_rebrota_antigo', 'Pastagem em Rebrota Antigo', '#8D6E63'),
        ('VS_Terra_Firme', 'VS Terra Firme', '#2E7D32'),
        ('VS_Inundacao_Ocasional', 'VS Inundação Ocasional', '#6EC6C6'),
        ('Areas_umidas_com_vegetacao', 'Áreas Úmidas com Vegetação', '#4DD0E1'),
        ('Hidrografia_Lago', 'Hidrografia Lago', '#03A9F4'),
        ('natural_pos_fogo', 'Natural Pós Fogo', '#D32F2F')
    ],

    ('Pantanal', 'Vegetação Secundária'): [
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
        ('Campo_Sujo_Umido',                    'Campo Sujo Úmido',                            '#9CCC65'),
        ('Campo_Sujo_Seco',                     'Campo Sujo Seco',                             '#7CB342'),
        ('Savana_Florestada',                   'Savana Florestada',                           '#6B8E23'),
        ('Savana_Arborizada',                   'Savana Arborizada',                           '#7CB342'),
        ('Wetlands',                            'Wetlands',                                    '#00ACC1'),
        ('Area_Umida_Vegetada',                 'Áreas Úmidas com Vegetação',                  '#4DD0E1'),
        ('Hidrografia_Rio',                     'Hidrografia Rio',                             '#0288D1'),
        ('Hidrografia_Lago',                    'Hidrografia Lago',                            '#03A9F4'),
        ('Manejo',                              'Manejo',                                      '#FF7043')
    ]
}