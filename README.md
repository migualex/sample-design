# Sample Design
<p align="center">
  <img src="icons/sample_design_icon.png" alt="Sample Design" width="80"/>
</p>

<p align="center">
  <strong>Ferramenta interativa para coleta de amostras de uso e cobertura da terra</strong><br/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/QGIS-3.22+-green?logo=qgis" />
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python" />
  <img src="https://img.shields.io/badge/PostgreSQL-PostGIS-336791?logo=postgresql" />
  <img src="https://img.shields.io/badge/versão-0.5.0-orange" />
  <img src="https://img.shields.io/badge/licença-GPL--2.0-lightgrey" />
</p>

---

O **Sample Design** é um plugin para QGIS que permite a coleta interativa de amostras, com integração direta ao banco de dados PostgreSQL/PostGIS.

O analista move o cursor sobre a imagem, visualiza em tempo real um quadrado de _preview_ configurável, por exemplo uma janela de 10 × 10 pixels, e confirma a amostra. Os polígonos são salvos automaticamente no banco de dados, permitindo que toda a equipe visualize, em tempo real, as amostras registradas.

---

## Instalação

### 1. Instalar a dependência Python

No **OSGeo4W Shell** (Windows) ou terminal (Linux/macOS):

```bash
pip install psycopg2-binary
```

### 2. Copiar o plugin para o QGIS

Clone o repositório e copie a pasta `sample-design` para o diretório de plugins do QGIS:

```bash
git clone https://github.com/migualex/sample-design.git
```

| Sistema | Caminho |
|---|---|
| Windows | `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\` |
| Linux | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |

### 3. Ativar no QGIS

**Complementos → Gerenciar e Instalar Complementos → Instalar a partir do ZIP → selecionar arquivo ZIP**

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
