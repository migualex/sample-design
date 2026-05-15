# Sample Design
<p align="center">
  <img src="icons/sample_design_icon.png" alt="Sample Design" width="80"/>
</p>

<p align="center">
  <strong>Ferramenta interativa para coleta de amostras de uso e cobertura da terra</strong><br/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green" />
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

```
    This file is part of Sample Design.
    Copyright (C) 2026 INPE.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <https://www.gnu.org/licenses/gpl-3.0.html>.
```
