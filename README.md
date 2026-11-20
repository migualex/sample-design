# Sample Design

<p align="center">
  <img src="https://img.shields.io/badge/versão-0.76-F5A800" />
  <img src="https://img.shields.io/badge/QGIS-3.40%20a%204.x-589632?logo=qgis&logoColor=white" />
  <img src="https://img.shields.io/badge/licença-GPLv3-5A7080" />
</p>

<img src="assets/wand.svg" align="right" alt="Sample Design" width="120"/>

O Sample Design coleta amostras para o treinamento de modelos de classificação de imagens Sentinel-2 com o pacote [sits](https://e-sensing.github.io/sitsbook/). Foi desenvolvido no Programa BiomasBR do INPE, no âmbito da semiautomatização do PRODES.

O plugin funciona com PostgreSQL/PostGIS na rede interna do INPE ou, fora dela, com a API do projeto, gravando o trabalho em um pacote local (GeoPackage).

## Requisitos

- QGIS 3.40 ou mais recente, incluindo a série 4.x
- `psycopg2`, para uso na rede interna

## Instalação

1. Baixe o arquivo `.zip` do plugin.
2. No QGIS, acesse **Complementos → Gerenciar e Instalar Complementos → Instalar a partir do ZIP**.
3. Selecione o arquivo e clique em **Instalar complemento**.

## Configuração

Os dados de conexão com o banco não ficam no repositório. Copie `db_secrets.example.py` para `db_secrets.py` e preencha host, usuários e senhas. Sem esse arquivo, o plugin funciona apenas pela API.

## Uso

1. Clique no ícone **Sample Design** e faça login.
2. Selecione o tile e as células da tarefa.
3. Escolha a classe e o modo de desenho (ponto, quadrado ou polígono) e colete as amostras no mapa.
4. Clique em **Finalizar** para enviar as amostras.

O passo a passo completo está no [manual](MANUAL.md).

## Licença

Distribuído sob a [GNU General Public License v3.0](LICENSE.txt).
