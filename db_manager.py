# -*- coding: utf-8 -*-
# Created by Miguel Alexandre da Cunha

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
    BIOMAS, CLASSES_POR_BIOMA,
    DATABASE_CONFIG,
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
            'schema': 'vs_2024',
            'table': 'output',
            'tiles': ('public', 'tiles_ptn'),
            'subregioes': None,
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

    def _get_project_conn_params(self, biome, project_type):
        return DATABASE_CONFIG.get((biome, project_type),
                                   {'host': DB_HOST, 'port': DB_PORT,
                                    'dbname': DB_NAME,
                                    'admin_user': DB_ADMIN_USER,
                                    'admin_pass': DB_ADMIN_PASS,
                                    'user_user': DB_USER_USER,
                                    'user_pass': DB_USER_PASS})

    def _project_admin_conn(self, biome, project_type):
        if not PSYCOPG2_OK:
            raise RuntimeError('psycopg2 não instalado.')
        params = self._get_project_conn_params(biome, project_type)
        conn = psycopg2.connect(
            host=params['host'], port=params['port'],
            dbname=params['dbname'],
            user=params['admin_user'], password=params['admin_pass'],
            connect_timeout=8
        )
        conn.autocommit = False
        return conn

    def _project_user_conn(self, biome, project_type):
        if not PSYCOPG2_OK:
            raise RuntimeError('psycopg2 não instalado.')
        params = self._get_project_conn_params(biome, project_type)
        conn = psycopg2.connect(
            host=params['host'], port=params['port'],
            dbname=params['dbname'],
            user=params['user_user'], password=params['user_pass'],
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
                if (biome, project) in DATABASE_CONFIG:
                    continue

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
                    sub_schema, sub_table = sub_info if sub_info else (None, None)
                    if sub_info:
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
                    else:
                        cur.execute(f"""
                            CREATE OR REPLACE FUNCTION {schema}.fill_info_{table}()
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

    def ensure_pantanal_vs_tables(self):
        """Creates/updates ptn_grade_tarefas table and backup table, ensuring audit columns."""
        conn = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.ptn_grade_tarefas (
                    cell_oid      VARCHAR(150) PRIMARY KEY,
                    geom          GEOMETRY(Polygon, 4674),
                    analyst_1     VARCHAR(100),
                    start_date_1  DATE,
                    finished_1    BOOLEAN DEFAULT FALSE,
                    end_date_1    DATE,
                    analyst_2     VARCHAR(100),
                    start_date_2  DATE,
                    finished_2    BOOLEAN DEFAULT FALSE,
                    end_date_2    DATE
                );
            """)

            colunas_v1 = ['geom', 'analyst_1', 'start_date_1', 'finished_1', 'end_date_1']
            for col in colunas_v1:
                cur.execute(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name   = 'ptn_grade_tarefas'
                              AND column_name  = '{col}'
                        ) THEN
                            ALTER TABLE public.ptn_grade_tarefas ADD COLUMN {col}
                            {'GEOMETRY(Polygon,4674)' if col == 'geom' else 'VARCHAR(100)' if col == 'analyst_1' else 'DATE' if col in ('start_date_1','end_date_1') else 'BOOLEAN'};
                        END IF;
                    END $$;
                """)

            colunas_v2 = ['analyst_2', 'start_date_2', 'finished_2', 'end_date_2']
            for col in colunas_v2:
                cur.execute(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name   = 'ptn_grade_tarefas'
                              AND column_name  = '{col}'
                        ) THEN
                            ALTER TABLE public.ptn_grade_tarefas ADD COLUMN {col}
                            {'VARCHAR(100)' if col == 'analyst_2' else 'DATE' if col in ('start_date_2','end_date_2') else 'BOOLEAN'};
                        END IF;
                    END $$;
                """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS vs_2024.output_backup (LIKE vs_2024.output INCLUDING ALL);
            """)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    def get_pantanal_vs_tiles(self):
        """Returns list of available tile names from tiles_ptn."""
        conn = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("SELECT tile FROM public.tiles_ptn ORDER BY tile")
            return [r[0] for r in cur.fetchall()]
        except:
            return []
        finally:
            cur.close()
            conn.close()

    def get_pantanal_vs_tiles_with_status(self):
        """Returns list of dicts with tile, status (free/locked/finished), analyst, etc."""
        conn = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("SELECT tile FROM public.tiles_ptn ORDER BY tile")
            tiles = [row[0] for row in cur.fetchall()]
            tile_status = {}
            for tile in tiles:
                tile_status[tile] = {'tile': tile, 'status': 'free', 'analyst': '', 'start_date': '', 'finished': False}
            cur.execute("""
                SELECT t.tile, g.analyst_1, g.start_date_1, g.finished_1, g.end_date_1
                FROM public.tiles_ptn t
                JOIN public.ptn_grade_tarefas g
                ON ST_Intersects(t.geom, g.geom)
            """)
            for row in cur.fetchall():
                tile, analyst, start, finished, end = row
                if tile not in tile_status:
                    continue
                if analyst and not finished:
                    tile_status[tile]['status'] = 'locked'
                    tile_status[tile]['analyst'] = analyst
                    tile_status[tile]['start_date'] = start.strftime('%Y-%m-%d') if start else ''
                elif finished:
                    if tile_status[tile]['status'] != 'locked':
                        tile_status[tile]['status'] = 'finished'
                        tile_status[tile]['analyst'] = analyst
                        tile_status[tile]['end_date'] = end.strftime('%Y-%m-%d') if end else ''
            return list(tile_status.values())
        except:
            return []
        finally:
            cur.close()
            conn.close()

    def get_grids_for_tile_with_status(self, tile_name):
        """ Returns cells with interpretation (1) and audit (2) status """
        conn = self._project_user_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        cur.execute("""
            SELECT cell_oid,
                analyst_1, start_date_1, finished_1, end_date_1,
                analyst_2, start_date_2, finished_2, end_date_2
            FROM public.ptn_grade_tarefas
            WHERE tile_2 = %s
            ORDER BY cell_oid
        """, (tile_name,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                'cell_oid': r[0],
                'analyst_1': r[1],
                'start_date_1': r[2],
                'finished_1': r[3],
                'end_date_1': r[4],
                'analyst_2': r[5],
                'start_date_2': r[6],
                'finished_2': r[7],
                'end_date_2': r[8],
            }
            for r in rows
        ]

    def get_cell_analyst(self, cell_oid):
        """ Returns the interpreter (analyst_1) of the cell """
        conn = self._project_user_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        cur.execute("SELECT analyst_1 FROM public.ptn_grade_tarefas WHERE cell_oid = %s", (cell_oid,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None

    def lock_cell(self, cell_oid, username):
        """ Locks cell for interpretation – fills analyst_1 and start_date_1 """
        conn = self._project_user_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE public.ptn_grade_tarefas
                SET analyst_1 = %s,
                    start_date_1 = CURRENT_TIMESTAMP,
                    finished_1 = FALSE,
                    end_date_1 = NULL
                WHERE cell_oid = %s
                AND analyst_1 IS NULL
                AND finished_1 IS NOT TRUE
                RETURNING cell_oid
            """, (username, cell_oid))
            if cur.fetchone() is None:
                conn.rollback()
                return False, "Célula já ocupada ou não disponível."
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    def unlock_cell(self, cell_oid, username):
        """ Finalizes interpretation: sets finished_1 = TRUE, end_date_1 = NOW """
        conn = self._project_user_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE public.ptn_grade_tarefas
                SET finished_1 = TRUE,
                    end_date_1 = CURRENT_TIMESTAMP
                WHERE cell_oid = %s
                AND analyst_1 = %s
                AND finished_1 IS NOT TRUE
            """, (cell_oid, username))
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    def lock_cell_for_audit(self, cell_oid, auditor_username):
        """ Auditor locks already interpreted cell (finished_1 = TRUE) not yet audited (finished_2 not TRUE) """
        conn = self._project_user_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE public.ptn_grade_tarefas
                SET analyst_2 = %s,
                    start_date_2 = CURRENT_TIMESTAMP,
                    finished_2 = FALSE,
                    end_date_2 = NULL
                WHERE cell_oid = %s
                AND finished_1 = TRUE
                AND (finished_2 IS FALSE OR finished_2 IS NULL)
                AND (analyst_2 IS NULL OR analyst_2 = %s)
                RETURNING cell_oid
            """, (auditor_username, cell_oid, auditor_username))
            if cur.fetchone() is None:
                conn.rollback()
                return False, "Célula não disponível para auditoria (já auditada ou interpretação não finalizada)."
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    def finish_audit(self, cell_oid, auditor_username, interpreter_username):
        """
        Finishes cell audit:
        1. Copies label to label_audit where label_audit IS NULL (implicit agreement)
        2. Sets finished_2 = TRUE, end_date_2 = NOW
        """
        config = self._get_config('Pantanal', 'Vegetação Secundária')
        schema = config['schema']
        table  = config['table']

        conn_admin = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn_admin.cursor()
        try:
            cur.execute(f"""
                UPDATE {schema}.{table} AS a
                SET label_audit = a.label
                FROM public.ptn_grade_tarefas AS g
                WHERE g.cell_oid = %s
                AND ST_Intersects(a.geom, g.geom)
                AND a.analyst = %s
                AND a.audit = %s
                AND a.label_audit IS NULL
            """, (cell_oid, interpreter_username, auditor_username))

            cur.execute("""
                UPDATE public.ptn_grade_tarefas
                SET finished_2 = TRUE,
                    end_date_2 = CURRENT_TIMESTAMP
                WHERE cell_oid = %s
                AND analyst_2 = %s
                AND finished_1 = TRUE
                AND finished_2 IS NOT TRUE
            """, (cell_oid, auditor_username))

            conn_admin.commit()
            return True, None
        except Exception as e:
            conn_admin.rollback()
            return False, str(e)
        finally:
            cur.close()
            conn_admin.close()

    def fill_audit_for_cell(self, cell_oid, auditor_username, interpreter_username):
        """
        Fills the 'audit' column with the auditor's name for all polygons
        of the interpreter belonging to the cell that still have no auditor.
        """
        config = self._get_config('Pantanal', 'Vegetação Secundária')
        schema = config['schema']
        table  = config['table']
        conn = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute(f"""
                UPDATE {schema}.{table} AS a
                SET audit = %s
                FROM public.ptn_grade_tarefas AS g
                WHERE g.cell_oid = %s
                AND ST_Intersects(a.geom, g.geom)
                AND a.analyst = %s
                AND a.audit IS NULL
            """, (auditor_username, cell_oid, interpreter_username))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

    def admin_reset_cell(self, cell_oid):
        """ Completely resets a cell (admin) – clears analyst_1/2, dates, etc. """
        conn = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE public.ptn_grade_tarefas
                SET analyst_1 = NULL, start_date_1 = NULL, finished_1 = FALSE, end_date_1 = NULL,
                    analyst_2 = NULL, start_date_2 = NULL, finished_2 = FALSE, end_date_2 = NULL
                WHERE cell_oid = %s
            """, (cell_oid,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

    def get_cell_geom(self, cell_oid):
        """Returns cell geometry as WKT or None."""
        conn = self._project_admin_conn('Pantanal', 'Vegetação Secundária')
        cur = conn.cursor()
        try:
            cur.execute("SELECT ST_AsText(geom) FROM public.ptn_grade_tarefas WHERE cell_oid = %s", (cell_oid,))
            row = cur.fetchone()
            return row[0] if row else None
        except:
            return None
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

    def register_user(self, username, nome_completo, password, bioma_padrao):
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
                   VALUES (%s, %s, %s, %s, FALSE)""",
                (username.strip(), nome_completo.strip(),
                 _hash_password(password), bioma_padrao)
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

    def set_user_auditor(self, username: str, is_auditor: bool):
        conn = self._admin_conn()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE public.interpreters SET is_auditor = %s WHERE username = %s",
                        (is_auditor, username))
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

    def get_all_users(self):
        conn = self._admin_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute("""
                SELECT username, nome_completo, bioma_padrao, is_admin, is_auditor, ativo
                FROM public.interpreters
                ORDER BY username
            """)
            return [dict(row) for row in cur.fetchall()]
        except:
            return []
        finally:
            cur.close()
            conn.close()

    def delete_user(self, username: str):
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

    def get_user_polygon_counts(self, biome, project_type):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        conn = self._project_admin_conn(biome, project_type)
        cur = conn.cursor()
        try:
            cur.execute(f"""
                SELECT analyst, COUNT(*) as total
                FROM {schema}.{table}
                WHERE biome = %s
                GROUP BY analyst
                ORDER BY total DESC
            """, (sanitize_text(biome),))
            return cur.fetchall()
        except:
            return []
        finally:
            cur.close()
            conn.close()

    def get_contagem(self, biome, project_type, username=None, tile=None, ecoregion=None, all_interpreters=False):
        config = self._get_config(biome, project_type)
        schema, table = config['schema'], config['table']
        conn = self._project_admin_conn(biome, project_type)
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
        conn = self._project_admin_conn(biome, project_type)
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
        conn = self._project_admin_conn(biome, project_type)
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
        conn = self._project_admin_conn(biome, project_type)
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
        conn = self._project_admin_conn(biome, project_type)
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
        params = self._get_project_conn_params(biome, project_type)
        uri = QgsDataSourceUri()
        uri.setConnection(params['host'], str(params['port']),
                          params['dbname'], params['user_user'], params['user_pass'])

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
        conn = self._project_admin_conn(biome, project_type)
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
        conn = self._project_admin_conn(biome, project_type)
        cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(f"""
                SELECT analyst, date FROM {schema}.{table}
                WHERE fid = %s
            """, (fid,))
            row = cur.fetchone()
            if row is None:
                return False, 'Amostra não encontrada.'

            if biome == 'Pantanal' and project_type == 'Vegetação Secundária':
                cur.execute("""
                    SELECT g.finished_1
                    FROM public.ptn_grade_tarefas g, vs_2024.output o
                    WHERE o.fid = %s AND ST_Intersects(o.geom, g.geom)
                    LIMIT 1
                """, (fid,))
                finished_row = cur.fetchone()
                if finished_row and finished_row['finished_1']:
                    if not is_admin:
                        return False, 'O polígono pertence a um trabalho finalizado e não pode ser removido.'
            else:
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

    def get_pantanal_tiles_layer(self):
        """Returns the tiles_ptn layer as a QgsVectorLayer (filtering done in the sampler)."""
        params = self._get_project_conn_params('Pantanal', 'Vegetação Secundária')
        uri = QgsDataSourceUri()
        uri.setConnection(params['host'], str(params['port']),
                          params['dbname'], params['user_user'], params['user_pass'])
        uri.setDataSource('public', 'tiles_ptn', 'geom', '', 'tile')
        uri.setParam('srid', '4674')
        layer = QgsVectorLayer(uri.uri(False), 'Tiles Pantanal VS', 'postgres')
        return layer
