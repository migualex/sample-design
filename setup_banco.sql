-- ─────────────────────────────────────────────────────────────────
-- setup_banco.sql
-- Executar UMA VEZ no servidor PostgreSQL como superusuário
-- Banco: biomas_amostras
-- ─────────────────────────────────────────────────────────────────

-- 1. Extensão PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- 2. Tabela de intérpretes (schema public)
CREATE TABLE IF NOT EXISTS public.interpretes (
    id             SERIAL PRIMARY KEY,
    username       VARCHAR(80)  UNIQUE NOT NULL,
    nome_completo  VARCHAR(150),
    senha_hash     TEXT NOT NULL, 
    bioma_padrao   VARCHAR(80),
    criado_em      TIMESTAMP DEFAULT NOW(),
    ativo          BOOLEAN   DEFAULT TRUE
);

-- 3. Schema e tabelas para Amazônia
CREATE SCHEMA IF NOT EXISTS amz;

CREATE TABLE IF NOT EXISTS amz.amostras (
    gid        SERIAL PRIMARY KEY,
    fid        INTEGER,
    "class"    VARCHAR(150),          -- nome com acento (ex: "Corte Raso")
    label      VARCHAR(150),          -- código sem acento (ex: "Corte_Raso")
    interprete VARCHAR(100),          -- username do intérprete
    data_col   TIMESTAMP DEFAULT NOW(),
    area_m2    DOUBLE PRECISION,
    px_size    INTEGER,
    janela_px  INTEGER,
    geom       GEOMETRY(Polygon, 4674) -- SIRGAS 2000
);
CREATE INDEX IF NOT EXISTS idx_amz_amostras_geom       ON amz.amostras USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_amz_amostras_interprete ON amz.amostras(interprete);

CREATE TABLE IF NOT EXISTS amz.classes_custom (
    id         SERIAL PRIMARY KEY,
    interprete VARCHAR(100),
    code       VARCHAR(150) NOT NULL,   -- sem acento
    label      VARCHAR(150) NOT NULL,   -- com acento
    color      VARCHAR(10)  DEFAULT '#888888',
    ordem      INTEGER      DEFAULT 99,
    ativo      BOOLEAN      DEFAULT TRUE,
    criado_em  TIMESTAMP    DEFAULT NOW()
);

-- 4. Schema e tabelas para Pantanal
CREATE SCHEMA IF NOT EXISTS pan;

CREATE TABLE IF NOT EXISTS pan.amostras (
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
CREATE INDEX IF NOT EXISTS idx_pan_amostras_geom       ON pan.amostras USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_pan_amostras_interprete ON pan.amostras(interprete);

CREATE TABLE IF NOT EXISTS pan.classes_custom (
    id         SERIAL PRIMARY KEY,
    interprete VARCHAR(100),
    code       VARCHAR(150) NOT NULL,
    label      VARCHAR(150) NOT NULL,
    color      VARCHAR(10)  DEFAULT '#888888',
    ordem      INTEGER      DEFAULT 99,
    ativo      BOOLEAN      DEFAULT TRUE,
    criado_em  TIMESTAMP    DEFAULT NOW()
);

-- 5. Permissões para o usuário de aplicação (user_amz)
GRANT USAGE ON SCHEMA amz TO user_amz;
GRANT USAGE ON SCHEMA pan TO user_amz;
GRANT SELECT, INSERT, UPDATE, DELETE ON amz.amostras       TO user_amz;
GRANT SELECT, INSERT, UPDATE, DELETE ON amz.classes_custom TO user_amz;
GRANT SELECT, INSERT, UPDATE, DELETE ON pan.amostras       TO user_amz;
GRANT SELECT, INSERT, UPDATE, DELETE ON pan.classes_custom TO user_amz;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.interpretes TO user_amz;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA amz    TO user_amz;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pan    TO user_amz;
GRANT USAGE, SELECT ON SEQUENCE public.interpretes_id_seq TO user_amz;
