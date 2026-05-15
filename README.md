# Sample Design — QGIS Plugin

<p align="center">
  <img src="sd_pg/icons/sample_design_icon.png" alt="Sample Design" width="80"/>
</p>

<p align="center">
  <strong>Ferramenta interativa de coleta de amostras de uso e cobertura da terra</strong><br/>
  Desenvolvida para o projeto de monitoramento de biomas brasileiros — INPE
</p>

<p align="center">
  <img src="https://img.shields.io/badge/QGIS-3.22+-green?logo=qgis" />
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python" />
  <img src="https://img.shields.io/badge/PostgreSQL-PostGIS-336791?logo=postgresql" />
  <img src="https://img.shields.io/badge/versão-1.0.0-orange" />
  <img src="https://img.shields.io/badge/licença-GPL--2.0-lightgrey" />
</p>

---

## Visão Geral

O **Sample Design** é um plugin para QGIS que permite a coleta interativa de amostras de referência sobre imagens de satélite (Sentinel-2, Landsat etc.), com integração direta ao banco de dados PostgreSQL/PostGIS.

O analista move o cursor sobre a imagem, visualiza um quadrado de _preview_ configurável em tempo real e confirma a amostra com o botão direito do mouse. Os polígonos são salvos automaticamente no banco, permitindo que toda a equipe veja as amostras dos outros analistas em tempo real.

---

## Funcionalidades

- **Preview em tempo real** — quadrado configurável (padrão 10×10 pixels = 100×100 m para Sentinel-2)
- **Integração PostgreSQL/PostGIS** — amostras salvas diretamente no banco
- **Multi-usuário** — cada analista tem sua conta; as amostras de todos ficam visíveis no mapa
- **Multi-bioma** — Amazônia e Pantanal com classes e schemas independentes
- **Gerenciador de classes** — adicionar, remover, recolorir e reordenar classes por usuário/bioma
- **Desfazer / Refazer** — pilha de histórico por sessão
- **Modo local** — funciona offline com camada de memória quando sem conexão ao banco
- **Exportação** — GeoPackage (`.gpkg`) e Shapefile (`.shp`)
- **Refresh automático** — mapa atualizado a cada 30 segundos

---

## Requisitos

| Requisito | Versão mínima |
|---|---|
| QGIS LTS | 3.22 |
| Python | 3.9 |
| psycopg2 | qualquer |
| PostgreSQL | 12+ |
| PostGIS | 3.0+ |

---

## Instalação

### 1. Instalar a dependência Python

No **OSGeo4W Shell** (Windows) ou terminal (Linux/macOS):

```bash
pip install psycopg2-binary
```

### 2. Copiar o plugin para o QGIS

Clone o repositório e copie a pasta `sd_pg` para o diretório de plugins do QGIS:

```bash
git clone https://github.com/seu-usuario/sample-design.git
```

| Sistema | Caminho |
|---|---|
| Windows | `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\` |
| Linux | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |

Renomeie a pasta de `sd_pg` para `sample_design` após copiar.

### 3. Ativar no QGIS

**Plugins → Gerenciar e Instalar Plugins → Instalados → marcar Sample Design**

---

## Configuração do Banco de Dados

### Executar o script de setup

Conecte ao banco `biomas_amostras` como superusuário e execute:

```bash
psql -h 150.163.2.224 -p 5432 -U adm_amz -d biomas_amostras -f sd_pg/setup_banco.sql
```

O script cria:
- Extensão PostGIS
- Schema `amz` (Amazônia) com tabelas `amostras` e `classes_custom`
- Schema `pan` (Pantanal) com tabelas `amostras` e `classes_custom`
- Tabela `public.interpretes` para autenticação
- Índices espaciais e permissões para `user_amz`

### Estrutura das tabelas

**`amz.amostras` / `pan.amostras`**

| Campo | Tipo | Descrição |
|---|---|---|
| `gid` | serial | Chave primária |
| `class` | varchar | Nome da classe com acento (ex: `Corte Raso`) |
| `label` | varchar | Código sem acento (ex: `Corte_Raso`) |
| `interprete` | varchar | Usuário que coletou |
| `data_col` | timestamp | Data e hora da coleta |
| `area_m2` | double | Área do polígono em m² |
| `px_size` | integer | Resolução do pixel em metros |
| `janela_px` | integer | Tamanho da janela em pixels |
| `geom` | geometry | Polígono em SIRGAS 2000 (EPSG:4674) |

---

## Como usar

### 1. Abrir o plugin
Clique no ícone **Sample Design** na barra de ferramentas ou acesse **Plugins → Sample Design**.

### 2. Fazer login
Informe usuário, senha e o bioma de trabalho. Caso não tenha conta, clique em **Criar conta**.

### 3. Coletar amostras
- Selecione a classe no menu suspenso
- Mova o cursor sobre a imagem — o quadrado de _preview_ aparece em vermelho tracejado
- **Botão direito** → confirma a amostra (pisca verde)
- **ESC** → desativa a ferramenta

### 4. Gerenciar classes
Clique em **Gerenciar classes** para adicionar, remover, recolorir ou reordenar as classes do seu bioma. As alterações ficam salvas no banco.

---

## Estrutura do Projeto

```
sample_design/
├── __init__.py                # Ponto de entrada do plugin
├── metadata.txt               # Metadados (QGIS Plugin Manager)
├── sample_design.py           # Classe principal do plugin
├── sampler_tool.py            # Ferramenta de mapa (rubber band + coleta)
├── sampler_dock.py            # Painel lateral principal
├── login_dialog.py            # Tela de login e cadastro
├── class_manager_dialog.py    # Gerenciador de classes
├── db_manager.py              # Toda a lógica PostgreSQL/PostGIS
├── db_config.py               # Configurações de conexão e classes padrão
├── setup_banco.sql            # Script SQL de configuração do banco
└── icons/
    ├── sample_design_icon.png
    └── sample_design_icon.svg
```

---

## Biomas e Classes

### Amazônia (`schema: amz`)

| Classe | Código |
|---|---|
| Corte Raso com Árvores Remanescentes | `Corte_Raso_Com_Arvores_Remanescentes` |
| Corte Raso | `Corte_Raso` |
| Corte Raso Antigo | `Corte_Raso_Antigo` |
| Corte Raso com Vegetação | `Corte_Raso_Com_Vegetacao` |
| Corte Raso com Vegetação Antigo | `Corte_Raso_Antigo_Com_Vegetacao` |
| Degradação | `Degradacao` |
| Degradação por Fogo | `Degradacao_Por_Fogo` |
| Floresta | `Floresta` |
| Floresta Transicional | `Floresta_Transicional` |
| Vegetação Natural Não-Florestal | `Vegetacao_Natural_Nao_Florestal` |
| Corpo D'Água | `Corpo_Dagua` |
| Área Inundável | `Area_Inundavel` |

### Pantanal (`schema: pan`)

| Classe | Código |
|---|---|
| Campo Inundável | `Campo_Inundavel` |
| Floresta Ciliar | `Floresta_Ciliar` |
| Cerrado | `Cerrado` |
| Cerradão | `Cerradao` |
| Campo Limpo | `Campo_Limpo` |
| Campo Sujo | `Campo_Sujo` |
| Vegetação Aquática | `Vegetacao_Aquatica` |
| Baio | `Baio` |
| Queimada Recente | `Queimada_Recente` |
| Área Antrópica | `Area_Antropica` |
| Corpo D'Água | `Corpo_Dagua` |
| Solo Exposto | `Solo_Exposto` |

---

## Adicionar Novo Bioma

1. Em `db_config.py`, adicione à dict `BIOMAS` e à dict `CLASSES_POR_BIOMA`
2. Em `setup_banco.sql`, duplique o bloco de criação de schema/tabelas
3. Execute o SQL no banco
4. Conceda permissões ao `user_amz`

---

## Autor

**Miguel Alexandre da Cunha** — INPE

---

## Licença

GPL-2.0 — compatível com QGIS.
