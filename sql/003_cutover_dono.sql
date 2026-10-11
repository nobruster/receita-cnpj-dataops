-- T-014: corte do publicador antigo. Idempotente. Executado manualmente pelo Bruno em PRD,
-- com o usuario admin/dono atual das tabelas (nao pelo publisher):
--   psql -v ON_ERROR_STOP=1 -f sql/003_cutover_dono.sql
--
-- 1) Transfere o dono so das tabelas trocadas (DROP/RENAME) para publisher.
-- 2) Excecao explicita: o historico (gold_resumo_competencia) continua com o dono cnpj,
--    fica fora do loop abaixo e mantem o caminho legado de DELETE + COPY.
-- 3) Garante SELECT do bi_reader em todo o gold, incluindo o historico.
-- Nada aqui apaga ou reescreve dados.

\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT c.relname, pg_get_userbyid(c.relowner) AS dono
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'gold'
          AND c.relkind IN ('r', 'p')
          AND c.relname <> 'gold_resumo_competencia'
          AND c.relname NOT LIKE '%\_\_novo'
    LOOP
        IF t.dono <> 'publisher' THEN
            EXECUTE format('ALTER TABLE gold.%I OWNER TO publisher', t.relname);
            RAISE NOTICE 'dono de gold.% transferido de % para publisher', t.relname, t.dono;
        END IF;
    END LOOP;
END
$$;

-- Historico: dono continua cnpj; so a leitura do BI e garantida.
GRANT USAGE ON SCHEMA gold TO bi_reader;
GRANT SELECT ON gold.gold_resumo_competencia TO bi_reader;

-- Tabelas trocadas: o novo dono nao herda os GRANTs antigos; repete o SELECT do BI.
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO bi_reader;

COMMIT;
