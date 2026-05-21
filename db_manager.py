# -*- coding: utf-8 -*-

import hashlib
import re
from datetime import datetime, timedelta

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
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def sanitize_text(text: str) -> str:
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
    r = text
    for k, v in replacements.items():
        r = r.replace(k, v)
    r = re.sub(r'[^A-Za-z0-9]', '_', r)
    r = re.sub(r'_+', '_', r).strip('_')
    return r


class DBManager:

    SCHEMA_MAP = {
        ('Amazônia', 'Prodes'): {
            'schema': 'prodes',
            'table': 'prodes_amz_2026',
            'tiles': ('public', 'tiles_amz'),
            'subregioes': None,
        },
        ('Amazônia', 'Vegetação Secundária'): {
            'schema': 'veg_sec',
            'table': 'vs_amz_2026',
            'tiles': ('public', 'tiles_amz'),
            'subregioes': None,
        },
        ('Pantanal', 'Prodes'): {
            'schema': 'prodes',
            'table': 'prodes_ptn_2026',
            'tiles': ('public', 'tiles_ptn'),
            'subregioes': ('public', 'subregioes_ptn'),
        },
        ('Pantanal', 'Vegetação Secundária'): {
            'schema': 'veg_sec',
            'table': 'vs_ptn_2024',
            'tiles': ('public', 'tiles_ptn'),
            'subregioes': ('public', 'subregioes_ptn'),
        },
    }

    def __init__(self):
        self._conn = None

    def _admin_conn(self):
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
        if not PSYCOPG2_OK:
            return False, 'psycopg2 não instalado.'
        try:
            conn = self._admin_conn()
            conn.close()
            return True, ''
        except Exception as e:
            return False, str(e)

    def bootstrap(self):
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.biome_config (
                    bioma     VARCHAR(80) PRIMARY KEY,
                    max_scale INTEGER DEFAULT 10000
                );
            """)
            for bioma in BIOMAS.keys():
                cur.execute("""
                    INSERT INTO public.biome_config (bioma, max_scale)
                    VALUES (%s, 10000)
                    ON CONFLICT (bioma) DO NOTHING;
                """, (bioma,))

            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.user_biomes (
                    username   VARCHAR(80) NOT NULL,
                    biome      VARCHAR(80) NOT NULL,
                    PRIMARY KEY (username, biome)
                );
            """)
            cur.execute("""
                INSERT INTO public.user_biomes (username, biome)
                SELECT username, bioma_padrao
                FROM public.interpreters
                WHERE bioma_padrao IS NOT NULL
                ON CONFLICT (username, biome) DO NOTHING;
            """)

            for (biome, project), config in self.SCHEMA_MAP.items():
                schema = config['schema']
                table = config['table']
                tiles_schema, tiles_table = config['tiles']
                sub_info = config.get('subregioes')

                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.{table} (
                        fid         SERIAL PRIMARY KEY,
                        label       VARCHAR(150),
                        analyst     VARCHAR(100),
                        biome       VARCHAR(50),
                        date        DATE DEFAULT CURRENT_DATE,
                        prodes      VARCHAR(10),
                        area_m2     DOUBLE PRECISION,
                        px_size     INTEGER,
                        window_px   INTEGER,
                        ecoregion   VARCHAR(150),
                        tile        VARCHAR(150),
                        audit       VARCHAR(100),
                        label_audit VARCHAR(150),
                        geom        GEOMETRY(Polygon, 4674)
                    );
                """)

                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_geom
                    ON {schema}.{table} USING GIST(geom);
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_analyst
                    ON {schema}.{table}(analyst);
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_biome
                    ON {schema}.{table}(biome);
                """)

                if biome == 'Amazônia' and project == 'Prodes':
                    cur.execute(f"""
                        CREATE OR REPLACE FUNCTION {schema}.fill_tile_{table}()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            SELECT t.tile INTO NEW.tile
                            FROM {tiles_schema}.{tiles_table} t
                            WHERE ST_Intersects(NEW.geom, t.geom)
                            LIMIT 1;
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql;
                    """)
                    cur.execute(f"DROP TRIGGER IF EXISTS trg_tile ON {schema}.{table};")
                    cur.execute(f"""
                        CREATE TRIGGER trg_tile
                        BEFORE INSERT OR UPDATE ON {schema}.{table}
                        FOR EACH ROW EXECUTE FUNCTION {schema}.fill_tile_{table}();
                    """)
                else:
                    sub_schema, sub_table = sub_info
                    cur.execute(f"""
                        CREATE OR REPLACE FUNCTION {schema}.fill_info_{table}()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            SELECT t.tile INTO NEW.tile
                            FROM {tiles_schema}.{tiles_table} t
                            WHERE ST_Intersects(NEW.geom, t.geom)
                            LIMIT 1;

                            SELECT public.sanitize_text(s.eco) INTO NEW.ecoregion
                            FROM {sub_schema}.{sub_table} s
                            WHERE ST_Intersects(NEW.geom, s.geom)
                            LIMIT 1;

                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql;
                    """)
                    cur.execute(f"DROP TRIGGER IF EXISTS trg_info ON {schema}.{table};")
                    cur.execute(f"""
                        CREATE TRIGGER trg_info
                        BEFORE INSERT OR UPDATE ON {schema}.{table}
                        FOR EACH ROW EXECUTE FUNCTION {schema}.fill_info_{table}();
                    """)

                cur.execute(f"""
                    CREATE OR REPLACE VIEW {schema}.vw_contagem_{table} AS
                    SELECT analyst, tile, ecoregion, label, COUNT(*) as total
                    FROM {schema}.{table}
                    GROUP BY analyst, tile, ecoregion, label;
                """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.interpreters (
                    id           SERIAL PRIMARY KEY,
                    username     VARCHAR(80)  UNIQUE NOT NULL,
                    nome_completo VARCHAR(150),
                    senha_hash   VARCHAR(64)  NOT NULL,
                    bioma_padrao VARCHAR(80),
                    criado_em    TIMESTAMP DEFAULT NOW(),
                    is_admin     BOOLEAN DEFAULT FALSE,
                    is_auditor   BOOLEAN DEFAULT FALSE,
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

    def _get_config(self, biome, project_type):
        key = (biome, project_type)
        config = self.SCHEMA_MAP.get(key)
        if not config:
            raise ValueError(f'Bioma/projeto desconhecido: {biome} / {project_type}')
        return config

    def get_biome_config(self, biome: str):
        conn = self._admin_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute("SELECT max_scale FROM public.biome_config WHERE bioma = %s", (biome,))
            row = cur.fetchone()
            return {'max_scale': row['max_scale']} if row else {'max_scale': 10000}
        except:
            return {'max_scale': 10000}
        finally:
            cur.close()
            conn.close()

    def set_biome_config(self, biome: str, max_scale: int):
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO public.biome_config (bioma, max_scale)
                VALUES (%s, %s)
                ON CONFLICT (bioma) DO UPDATE SET max_scale = EXCLUDED.max_scale;
            """, (biome, max_scale))
            conn.commit()
        except:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    def authenticate(self, username: str, password: str):
        conn = self._admin_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(
                "SELECT * FROM public.interpreters WHERE username=%s AND ativo=TRUE",
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

    def register_user(self, username, nome_completo, password, bioma_padrao, is_auditor=False):
        if len(username.strip()) < 3:
            return False, 'Nome de usuário deve ter ao menos 3 caracteres.'
        if len(password) < 6:
            return False, 'Senha deve ter ao menos 6 caracteres.'
        if bioma_padrao not in BIOMAS:
            return False, f'Bioma inválido: {bioma_padrao}'
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO public.interpreters
                   (username, nome_completo, senha_hash, bioma_padrao, is_auditor)
                   VALUES (%s, %s, %s, %s, %s)""",
                (username.strip(), nome_completo.strip(),
                 _hash_password(password), bioma_padrao, is_auditor)
            )
            cur.execute(
                """INSERT INTO public.user_biomes (username, biome)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                (username.strip(), bioma_padrao)
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

    def set_user_admin(self, username: str, is_admin: bool):
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE public.interpreters SET is_admin = %s WHERE username = %s",
                        (is_admin, username))
            conn.commit()
        except:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    def ensure_user_biome(self, username, biome):
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO public.user_biomes (username, biome)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                (username, biome)
            )
            conn.commit()
        except:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    def delete_user(self, username: str):
        """Exclui permanentemente o usuário da tabela interpreters."""
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM public.user_biomes WHERE username = %s", (username,))
            cur.execute("DELETE FROM public.interpreters WHERE username = %s", (username,))
            conn.commit()
            return True, ''
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    # ── get_active_users agora inclui is_auditor ──
    def get_active_users(self):
        conn = self._admin_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute("""
                SELECT username, nome_completo, bioma_padrao, is_admin, is_auditor
                FROM public.interpreters
                WHERE ativo = TRUE
                ORDER BY username
            """)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f'Erro ao buscar usuários: {e}')
            return []
        finally:
            cur.close()
            conn.close()

    # Os métodos abaixo permanecem inalterados ...
    # (get_contagem, get_tiles_ecorregioes, get_ecoregion_display_map,
    #  get_custom_classes, save_custom_classes, get_postgis_layer,
    #  insert_feature, delete_feature)
    # (incluídos para completar o arquivo)
    def get_contagem(self, biome, project_type, username=None, tile=None, ecoregion=None, all_interpreters=False):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            conditions = ['biome = %s']
            params = [sanitize_text(biome)]
            if not all_interpreters and username:
                conditions.append('analyst = %s')
                params.append(username)
            if tile:
                conditions.append('tile = %s')
                params.append(tile)
            if ecoregion:
                conditions.append('ecoregion = %s')
                params.append(ecoregion)
            where = ' AND '.join(conditions)
            cur.execute(f"""
                SELECT label, COUNT(*)::int as total
                FROM {schema}.{table}
                WHERE {where}
                GROUP BY label
                ORDER BY total DESC
            """, params)
            return cur.fetchall()
        except:
            return []
        finally:
            cur.close()
            conn.close()

    def get_tiles_ecorregioes(self, biome, project_type, username):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            cur.execute(f"""
                SELECT DISTINCT tile FROM {schema}.{table}
                WHERE analyst = %s AND biome = %s AND tile IS NOT NULL
                ORDER BY tile
            """, (username, sanitize_text(biome)))
            tiles = [r[0] for r in cur.fetchall()]

            cur.execute(f"""
                SELECT DISTINCT ecoregion FROM {schema}.{table}
                WHERE analyst = %s AND biome = %s AND ecoregion IS NOT NULL
                ORDER BY ecoregion
            """, (username, sanitize_text(biome)))
            ecos = [r[0] for r in cur.fetchall()]
            return tiles, ecos
        except:
            return [], []
        finally:
            cur.close()
            conn.close()

    def get_ecoregion_display_map(self, biome, project_type):
        config = self._get_config(biome, project_type)
        sub = config.get('subregioes')
        if not sub:
            return {}
        schema, table = sub
        mapping = {}
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT DISTINCT eco FROM {schema}.{table}")
            for row in cur.fetchall():
                original = row[0]
                sanitized = sanitize_text(original)
                mapping[sanitized] = original
        except:
            pass
        finally:
            cur.close()
            conn.close()
        return mapping

    def get_custom_classes(self, biome, project_type, username):
        config = self._get_config(biome, project_type)
        classes_schema = config['schema']
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {classes_schema}.classes_custom (
                    id         SERIAL PRIMARY KEY,
                    analyst    VARCHAR(100),
                    code       VARCHAR(150) NOT NULL,
                    label      VARCHAR(150) NOT NULL,
                    color      VARCHAR(10)  DEFAULT '#888888',
                    ordem      INTEGER      DEFAULT 99,
                    ativo      BOOLEAN      DEFAULT TRUE,
                    criado_em  TIMESTAMP    DEFAULT NOW()
                );
            """)
            cur.execute(f"""
                SELECT code, label, color
                FROM {classes_schema}.classes_custom
                WHERE analyst=%s AND ativo=TRUE
                ORDER BY ordem, id
            """, (username,))
            rows = cur.fetchall()
            if rows:
                return [(r[0], r[1], r[2]) for r in rows]
            return list(CLASSES_POR_BIOMA.get((biome, project_type), []))
        except:
            return list(CLASSES_POR_BIOMA.get((biome, project_type), []))
        finally:
            cur.close()
            conn.close()

    def save_custom_classes(self, biome, project_type, username, classes):
        config = self._get_config(biome, project_type)
        schema = config['schema']
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"DELETE FROM {schema}.classes_custom WHERE analyst=%s", (username,))
            for ordem, (code, label, color) in enumerate(classes):
                cur.execute(f"""
                    INSERT INTO {schema}.classes_custom
                    (analyst, code, label, color, ordem)
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

    def get_postgis_layer(self, biome, project_type, username, filter_by_user=True):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        uri = QgsDataSourceUri()
        uri.setConnection(DB_HOST, str(DB_PORT), DB_NAME, DB_USER_USER, DB_USER_PASS)

        if filter_by_user:
            filter_sql = f"analyst = '{username}' AND biome = '{sanitize_text(biome)}'"
        else:
            filter_sql = f"biome = '{sanitize_text(biome)}'"

        uri.setDataSource(schema, table, 'geom', filter_sql, 'fid')
        uri.setParam('srid', '4674')
        layer_name = f'Amostras {project_type} {biome} [{username}]'
        layer = QgsVectorLayer(uri.uri(False), layer_name, 'postgres')
        if not layer.isValid():
            return None, 'Não foi possível conectar à tabela.'
        return layer, ''

    def insert_feature(self, biome, project_type, username, geom_wkt, crs_srid, code,
                   area_m2, px_size, window_px, prodes_str, ecoregion_raw=None,
                   audit=None, label_audit=None, date_val=None):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        conn = self._admin_conn()
        cur  = conn.cursor()
        try:
            date_col   = ', date'    if date_val is not None else ''
            date_ph    = ', %s'      if date_val is not None else ''
            date_param = [date_val]  if date_val is not None else []

            cur.execute(f"""
                INSERT INTO {schema}.{table}
                    (label, analyst, biome, prodes,
                    area_m2, px_size, window_px, geom,
                    audit, label_audit{date_col})
                VALUES (%s, %s, %s, %s,
                        %s, %s, %s,
                        ST_Transform(ST_GeomFromText(%s, %s), 4674),
                        %s, %s{date_ph})
                RETURNING fid
            """, (
                code, username, sanitize_text(biome), prodes_str,
                area_m2, px_size, window_px,
                geom_wkt, crs_srid,
                audit, label_audit,
                *date_param
            ))
            fid = cur.fetchone()[0]
            conn.commit()
            return fid, ''
        except Exception as e:
            conn.rollback()
            return None, str(e)
        finally:
            cur.close()
            conn.close()

    def delete_feature(self, biome, project_type, fid, username, is_admin=False):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        conn = self._admin_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(f"""
                SELECT analyst, date FROM {schema}.{table}
                WHERE fid = %s
            """, (fid,))
            row = cur.fetchone()
            if row is None:
                return False, 'Amostra não encontrada.'
            owner = row['analyst']
            ts    = row['date']
            if is_admin:
                pass
            elif owner != username:
                return False, 'Você só pode apagar suas próprias amostras.'
            elif datetime.now().date() - ts > timedelta(days=1):
                return False, 'A amostra foi criada há mais de 24 horas e não pode ser apagada.'
            cur.execute(f"DELETE FROM {schema}.{table} WHERE fid=%s", (fid,))
            conn.commit()
            return True, ''
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()