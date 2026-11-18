# Sample Design
<p align="center">
  <img src="https://img.shields.io/badge/License-GPLv3-blue" />
  <img src="https://img.shields.io/badge/Lifecycle-maturing-green.svg" />
  <img src="https://img.shields.io/badge/QGIS-3.40%20a%204.x-589632?logo=qgis&logoColor=white" />
</p>

<img src="icons/sample_design_icon.png" align="right" alt="Sample Design" width="120"/>

<p>Plugin do QGIS para coleta interativa de amostras usadas no treinamento de modelos de inteligência artificial. Trabalha com PostgreSQL/PostGIS na rede interna do INPE ou, fora dela, com a API do projeto, gravando o trabalho em um pacote local (GeoPackage).</p>

<p>Foi desenvolvido no âmbito da semiautomatização do PRODES, para coletar amostras em diferentes ecorregiões e treinar a classificação de tiles Sentinel-2 com o pacote <a href="https://e-sensing.github.io/sitsbook/" target="_blank">sits</a>.</p>

## Requisitos

- QGIS 3.40 ou mais recente, incluindo a série 4.x (Qt6).
- Para a rede interna: biblioteca `psycopg2` (no OSGeo4W Shell: `pip install psycopg2-binary`).

## Instalação

No QGIS, acesse **Complementos → Gerenciar e Instalar Complementos → Instalar a partir do ZIP** e selecione o arquivo `.zip` do plugin.

## Configuração do banco

Os dados de conexão com o PostgreSQL (host, usuários e senhas) não ficam no repositório. Copie `db_secrets.example.py` para `db_secrets.py` e preencha os dados. Sem esse arquivo o plugin entra direto no modo API.

## Como usar

1. Clique no ícone **Sample Design** na barra de ferramentas.
2. Faça login escolhendo bioma e projeto. Fora da rede interna, informe o endereço da API e a sua chave de acesso.
3. Em **Selecionar Tile / Células**, escolha o tile e as células da tarefa e onde salvar o pacote de trabalho.
4. O plugin carrega as imagens Sentinel-2 do BDC (julho de cada ano, com menor cobertura de nuvem), as máscaras de referência e o TerraClass do tile.
5. Escolha a classe e o modo de desenho (ponto, quadrado pré-definido ou polígono livre) e clique no mapa.
6. Use a aba **Série temporal** para conferir o comportamento das amostras.
7. Ao terminar, clique em **Finalizar** para enviar as amostras e liberar as células.

Auditores entram com a opção **Entrar como auditor** e podem reabrir células já finalizadas para revisão, sem apagar amostras.

Leia as instruções completas em [MANUAL.md](MANUAL.md).

## Licença

Este projeto é distribuído sob a licença GNU General Public License v3.0.

Você é livre para usar, estudar, modificar e distribuir este software, desde
que mantenha os avisos de copyright e a licença original em qualquer cópia
ou trabalho derivado, conforme exigido pela GPL-3.0.
