# -*- coding: utf-8 -*-
"""
db_config.py — Configurações de conexão PostgreSQL e classes por bioma.
"""

# ─────────────────────────────────────────────────────────────────
# Conexão PostgreSQL
# ─────────────────────────────────────────────────────────────────
DB_HOST = '150.163.2.224'
DB_PORT = 5432
DB_NAME = 'biomas_amostras'

# Credenciais administrativas (usadas apenas internamente para criar usuários)
DB_ADMIN_USER = 'adm_amz'
DB_ADMIN_PASS = '@dm@mz'

# Credenciais de leitura/escrita para intérpretes
DB_USER_USER = 'user_amz'
DB_USER_PASS = 'biomaamazonia'

# ─────────────────────────────────────────────────────────────────
# Biomas disponíveis e seus schemas no banco
# ─────────────────────────────────────────────────────────────────
BIOMAS = {
    'Amazônia':  'amz',
    'Pantanal':  'pan',
}

# ─────────────────────────────────────────────────────────────────
# Classes por bioma — (código_sem_acento, nome_com_acento, cor_hex)
#   código_sem_acento → gravado em coluna 'label'
#   nome_com_acento   → gravado em coluna 'class'  (exibido no combo)
# ─────────────────────────────────────────────────────────────────
CLASSES_POR_BIOMA = {

    'Amazônia': [
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

    'Pantanal': [
        ('Campo_Inundavel',                      'Campo Inundável',                      '#89E1E1'),
        ('Floresta_Ciliar',                      'Floresta Ciliar',                      '#1E8449'),
        ('Cerrado',                              'Cerrado',                              '#C8A200'),
        ('Cerradao',                             'Cerradão',                             '#8B6914'),
        ('Campo_Limpo',                          'Campo Limpo',                          '#D4E8A0'),
        ('Campo_Sujo',                           'Campo Sujo',                           '#A8C460'),
        ('Vegetacao_Aquatica',                   'Vegetação Aquática',                   '#55AACC'),
        ('Baio',                                 'Baio',                                 '#D2A679'),
        ('Queimada_Recente',                     'Queimada Recente',                     '#B82815'),
        ('Area_Antropica',                       'Área Antrópica',                       '#E3509F'),
        ('Corpo_Dagua',                          "Corpo D'Água",                         '#0394F2'),
        ('Solo_Exposto',                         'Solo Exposto',                         '#C8966E'),
    ],
}
