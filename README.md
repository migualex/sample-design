# Sample Design
<p align="center">
  <img src="icons/sample_design_icon.png" alt="Sample Design" width="80"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-GPL--3.0-blue" />
  <img src="https://img.shields.io/badge/lifecycle-maturing-green.svg" />
</p>

Plugin desenvolvido no âmbito do Programa BiomasBR-INPE para coleta interativa de amostras destinadas ao treinamento de modelos de inteligência artificial. As funcionalidades incluem integração ao PostgreSQL/PostGIS, autenticação de usuários, gerenciamento de classes personalizadas e acompanhamento em tempo real, com sincronização por WFS. 

## Instalação

Baixe o arquivo `.zip`.

No QGIS, acesse: **Complementos → Gerenciar e Instalar Complementos → Instalar a partir do ZIP**

Selecione o arquivo e conclua a instalação.

## Como usar

### 1. Abrir o plugin
Clique no ícone **Sample Design** na barra de ferramentas.

### 2. Fazer login
Informe usuário, senha, bioma e o projeto de trabalho. Caso não tenha conta, clique em **Criar conta**.

### 3. Coletar amostras
- Selecione a classe no menu suspenso (ex.: "Corte Raso", "Floresta").
- Escolha o modo de desenho:
  a) Quadrado pré-definido: uma janela fixa com tamanho de pixel.
  b) Polígono livre.
- **Botão esquerdo** para confirmar a amostra.
- **ESC** para desativar a ferramenta de amostragem.

Leia as instruções completas em [MANUAL.md](MANUAL.md).

## Licença

Este projeto é distribuído sob a licença GNU General Public License v3.0.

Você é livre para usar, estudar, modificar e distribuir este software, desde 
que mantenha os avisos de copyright e a licença original em qualquer cópia 
ou trabalho derivado, conforme exigido pela GPL-3.0.
