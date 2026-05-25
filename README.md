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


Plugin para QGIS que permite a coleta coloborativa e interativa de amostras de treinamento, diretamente integrado ao banco de dados PostgreSQL/PostGIS.

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
Informe usuário, senha, bioma e o projeto de trabalho. Caso não tenha conta, clique em **Criar conta**.

### 3. Coletar amostras
- Selecione a classe no menu suspenso (ex.: "Corte Raso", "Floresta").
- Escolha o modo de desenho: a) Quadrado pré-definido: uma janela fixa com tamanho de pixel. b) Polígono livre: desenhe qualquer forma.
- Mova o cursor sobre a imagem: uma pré-visualização quadrada vermelha tracejada aparece (no modo quadrado).
- **Botão esquerdo** para confirmar a amostra.
- **ESC** para desativar a ferramenta de amostragem.
  
This project is distributed under the GNU General Public License v3.0 (GPL-3.0).
