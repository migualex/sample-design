# Sample Design
<p align="center">
  <img src="icons/sample_design_icon.png" alt="Sample Design" width="80"/>
</p>

<p align="center">
  <strong>Ferramenta interativa para coleta de amostras de uso e cobertura da terra</strong><br/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-GPL--3.0-blue" />
  <img src="https://img.shields.io/badge/lifecycle-experimental-orange.svg" />
</p>

---

O **Sample Design** é um plugin para QGIS que permite a coleta interativa de amostras, com integração direta ao banco de dados PostgreSQL/PostGIS.

O analista move o cursor sobre a imagem e visualiza um quadrado de _preview_ configurável, por exemplo uma janela de 10 × 10 pixels. Ao confirmar a amostra, os polígonos são salvos automaticamente no banco de dados, permitindo que toda a equipe visualize, em tempo real.

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

### 3. Ativar no QGIS

**Complementos → Gerenciar e Instalar Complementos → Instalar a partir do ZIP → selecionar arquivo ZIP**

---

## Como usar

### 1. Abrir o plugin
Clique no ícone **Sample Design** na barra de ferramentas.

### 2. Fazer login
Informe usuário, senha e o bioma de trabalho. Caso não tenha conta, clique em **Criar conta**.

### 3. Coletar amostras
- Selecione a classe no menu suspenso
- Mova o cursor sobre a imagem: o quadrado de _preview_ aparece em vermelho tracejado
- **Botão direito** → confirma a amostra (pisca verde)
- **ESC** → desativa a ferramenta

This project is distributed under the GNU General Public License v3.0 (GPL-3.0).
