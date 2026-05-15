# -*- coding: utf-8 -*-
"""
db_manager.py — Gerenciador de conexão PostgreSQL/PostGIS.

Responsabilidades:
  • Conectar ao banco usando psycopg2
  • Autenticar intérpretes
  • Criar novos usuários (registro)
  • Garantir que schemas e tabelas existem
  • Retornar QgsVectorLayer apontando para a tabela PostGIS do usuário
  • Listar classes personalizadas do usuário
  • Salvar/remover classes personalizadas
"""

import hashlib
import re
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_OK = True
except ImportError:
    PSYCOPG2_OK = False

from qgis.core import QgsVectorLayer, QgsDataSourceUri

from .db_config import (
    DB_HOST, DB_PORT, DB_NAME,
    DB_ADMIN_USER, DB_ADMIN_PASS,
    DB_USER_USER, DB_USER_PASS,
    BIOMAS, CLASSES_POR_BIOMA
)


def _hash_password(password: str) -> str:
    """SHA-256 simples. Em produção use bcrypt."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _to_code(label: str) -> str:
    """Converte nome legível em código sem acento para campo 'label'."""
    replacements = {
        'á':'a','à':'a','ã':'a','â':'a','ä':'a',
        'é':'e','ê':'e','ë':'e','è':'e',
        'í':'i','î':'i','ï':'i','ì':'i',
        'ó':'o','ô':'o','õ':'o','ö':'o','ò':'o',
        'ú':'u','û':'u','ü':'u','ù':'u',
        'ç':'c','ñ':'n',
        'Á':'A','À':'A','Ã':'A','Â':'A',
        'É':'E','Ê':'E','Í':'I','Ó':'O',
        'Ô':'O','Õ':'O','Ú':'U','Ç':'C',
    }
    r = label
    for k, v in replacements.items():
        r = r.replace(k, v)
    r = re.sub(r"[^A-Za-z0-9]", '_', r)
    r = re.sub(r'_+', '_', r).strip('_')
    return r


class DBManager:

    def __init__(self):
        self._conn = None      # conexão admin (psycopg2)

    # ─────────────────────────────────────────────────────────────
    # Conexão
    # ─────────────────────────────────────────────────────────────
    def _admin_conn(self):
        """Conexão administrativa (para criar schemas, tabelas, usuários)."""
        if not PSYCOPG2_OK:
            raise RuntimeError(
                'A biblioteca psycopg2 não está instalada.\n'
                'No OSGeo4W Shell execute:\n'
                '  pip install psycopg2-binary'
            )
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_ADMIN_USER, password=DB_ADMIN_PASS,
            connect_timeout=8
        )
        conn.autocommit = False
        return conn

    def test_connection(self):
        """Testa se o banco está acessível. Retorna (True, '') ou (False, msg)."""
        if not PSYCOPG2_OK:
            return False, 'psycopg2 não instalado. Execute: pip install psycopg2-binary'
        try:
            conn = self._admin_conn()
            conn.close()
            return True, ''
        except Exception as e:
            return False, str(e)

    # ─────────────────────────────────────────────────────────────
    # Bootstrap — cria schemas e tabelas necessárias
    # ─────────────────────────────────────────────────────────────
    def bootstrap(self):
        """
        Garante que todos os schemas e tabelas existem.
        Chamado uma vez na inicialização do plugin (pelo admin).
        """
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            # Extensão PostGIS
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

            # Schema e tabelas para cada bioma
            for bioma, schema in BIOMAS.items():
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS {schema};')

                # Tabela de amostras por usuário
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.amostras (
                        gid        SERIAL PRIMARY KEY,
                        fid        INTEGER,
                        "class"    VARCHAR(150),
                        label      VARCHAR(150),
                        interprete VARCHAR(100),
                        data_col   TIMESTAMP DEFAULT NOW(),
                        area_m2    DOUBLE PRECISION,
                        px_size    INTEGER,
                        janela_px  INTEGER,
                        geom       GEOMETRY(Polygon, 4674)
                    );
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{schema}_amostras_geom
                    ON {schema}.amostras USING GIST(geom);
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{schema}_amostras_interprete
                    ON {schema}.amostras(interprete);
                """)

                # Tabela de classes customizadas por bioma/usuário
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.classes_custom (
                        id         SERIAL PRIMARY KEY,
                        interprete VARCHAR(100),
                        code       VARCHAR(150) NOT NULL,
                        label      VARCHAR(150) NOT NULL,
                        color      VARCHAR(10)  DEFAULT '#888888',
                        ordem      INTEGER      DEFAULT 99,
                        ativo      BOOLEAN      DEFAULT TRUE,
                        criado_em  TIMESTAMP    DEFAULT NOW()
                    );
                """)

            # Tabela de usuários no schema public
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.interpretes (
                    id           SERIAL PRIMARY KEY,
                    username     VARCHAR(80)  UNIQUE NOT NULL,
                    nome_completo VARCHAR(150),
                    senha_hash   VARCHAR(64)  NOT NULL,
                    bioma_padrao VARCHAR(80),
                    criado_em    TIMESTAMP DEFAULT NOW(),
                    ativo        BOOLEAN   DEFAULT TRUE
                );
            """)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    # ─────────────────────────────────────────────────────────────
    # Autenticação
    # ─────────────────────────────────────────────────────────────
    def authenticate(self, username: str, password: str):
        """
        Autentica um intérprete.
        Retorna (True, dict_usuario) ou (False, msg_erro).
        """
        conn = self._admin_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(
                "SELECT * FROM public.interpretes WHERE username=%s AND ativo=TRUE",
                (username.strip(),)
            )
            row = cur.fetchone()
            if row is None:
                return False, 'Usuário não encontrado.'
            if row['senha_hash'] != _hash_password(password):
                return False, 'Senha incorreta.'
            return True, dict(row)
        except Exception as e:
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    # ─────────────────────────────────────────────────────────────
    # Registro de novo usuário
    # ─────────────────────────────────────────────────────────────
    def register_user(self, username: str, nome_completo: str,
                      password: str, bioma_padrao: str):
        """
        Cria um novo intérprete.
        Retorna (True, '') ou (False, msg_erro).
        """
        if len(username.strip()) < 3:
            return False, 'Nome de usuário deve ter ao menos 3 caracteres.'
        if len(password) < 6:
            return False, 'Senha deve ter ao menos 6 caracteres.'
        if bioma_padrao not in BIOMAS:
            return False, f'Bioma inválido: {bioma_padrao}'

        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO public.interpretes
                   (username, nome_completo, senha_hash, bioma_padrao)
                   VALUES (%s, %s, %s, %s)""",
                (username.strip(), nome_completo.strip(),
                 _hash_password(password), bioma_padrao)
            )
            conn.commit()
            return True, ''
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return False, f'Usuário "{username}" já existe.'
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    # ─────────────────────────────────────────────────────────────
    # Classes personalizadas
    # ─────────────────────────────────────────────────────────────
    def get_custom_classes(self, bioma: str, username: str):
        """
        Retorna lista de classes customizadas do usuário para o bioma.
        Cada item: (code, label, color).
        Se não houver classes custom, retorna as classes padrão do bioma.
        """
        schema = BIOMAS.get(bioma)
        if not schema:
            return list(CLASSES_POR_BIOMA.get(bioma, []))

        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            cur.execute(f"""
                SELECT code, label, color
                FROM {schema}.classes_custom
                WHERE interprete=%s AND ativo=TRUE
                ORDER BY ordem, id
            """, (username,))
            rows = cur.fetchall()
            if rows:
                return [(r[0], r[1], r[2]) for r in rows]
            return list(CLASSES_POR_BIOMA.get(bioma, []))
        except Exception:
            return list(CLASSES_POR_BIOMA.get(bioma, []))
        finally:
            cur.close()
            conn.close()

    def save_custom_classes(self, bioma: str, username: str, classes: list):
        """
        Salva a lista completa de classes customizadas para o usuário/bioma.
        Substitui todas as anteriores.
        classes: lista de (code, label_com_acento, color)
        """
        schema = BIOMAS.get(bioma)
        if not schema:
            return False, 'Bioma inválido.'
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            # Remove as antigas
            cur.execute(f"""
                DELETE FROM {schema}.classes_custom WHERE interprete=%s
            """, (username,))
            # Insere as novas
            for ordem, (code, label, color) in enumerate(classes):
                cur.execute(f"""
                    INSERT INTO {schema}.classes_custom
                    (interprete, code, label, color, ordem)
                    VALUES (%s, %s, %s, %s, %s)
                """, (username, code, label, color, ordem))
            conn.commit()
            return True, ''
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    # ─────────────────────────────────────────────────────────────
    # Camada PostGIS via QGIS
    # ─────────────────────────────────────────────────────────────
    def get_postgis_layer(self, bioma: str, username: str):
        """
        Retorna uma QgsVectorLayer conectada à tabela PostGIS do bioma,
        filtrada pelo intérprete logado, mas exibindo amostras de todos
        (somente o intérprete logado pode editar as suas).
        """
        schema = BIOMAS.get(bioma)
        if not schema:
            return None, f'Bioma desconhecido: {bioma}'

        uri = QgsDataSourceUri()
        uri.setConnection(DB_HOST, str(DB_PORT), DB_NAME, DB_USER_USER, DB_USER_PASS)
        uri.setDataSource(schema, 'amostras', 'geom', '', 'gid')
        uri.setParam('srid', '4674')

        layer_name = f'Amostras — {bioma} [{username}]'
        layer = QgsVectorLayer(uri.uri(False), layer_name, 'postgres')

        if not layer.isValid():
            return None, (
                f'Não foi possível conectar à tabela {schema}.amostras.\n'
                'Verifique a conexão com o banco.'
            )
        return layer, ''

    # ─────────────────────────────────────────────────────────────
    # Inserir feição diretamente via SQL (mais rápido e seguro)
    # ─────────────────────────────────────────────────────────────
    def insert_feature(self, bioma: str, username: str,
                       geom_wkt: str, crs_srid: int,
                       cls_name: str, code: str,
                       area_m2: float, px_size: int, janela_px: int):
        """
        Insere uma feição diretamente via psycopg2.
        Retorna (gid, '') ou (None, msg_erro).
        """
        schema = BIOMAS.get(bioma)
        if not schema:
            return None, 'Bioma inválido.'
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            cur.execute(f"""
                INSERT INTO {schema}.amostras
                    ("class", label, interprete, data_col,
                     area_m2, px_size, janela_px, geom)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        ST_Transform(
                            ST_GeomFromText(%s, %s),
                            4674
                        ))
                RETURNING gid
            """, (
                cls_name, code, username, datetime.now(),
                area_m2, px_size, janela_px,
                geom_wkt, crs_srid
            ))
            gid = cur.fetchone()[0]
            conn.commit()
            return gid, ''
        except Exception as e:
            conn.rollback()
            return None, str(e)
        finally:
            cur.close()
            conn.close()

    def delete_feature(self, bioma: str, gid: int):
        """Remove uma feição pelo gid."""
        schema = BIOMAS.get(bioma)
        if not schema:
            return False, 'Bioma inválido.'
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            cur.execute(f"DELETE FROM {schema}.amostras WHERE gid=%s", (gid,))
            conn.commit()
            return True, ''
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()
