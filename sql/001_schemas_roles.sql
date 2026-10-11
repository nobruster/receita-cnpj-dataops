-- T-002: schemas gold/ops e papeis publisher/bi_reader. Idempotente.
-- Aplicar com o usuario admin: make bi-ddl (senhas via psql -v, nunca no arquivo).
--   psql -v bi_reader_password=... -v publisher_password=... -f sql/001_schemas_roles.sql

\set ON_ERROR_STOP on

SELECT set_config('bi.reader_password', :'bi_reader_password', false) \gset
SELECT set_config('bi.publisher_password', :'publisher_password', false) \gset

-- Papeis sao do cluster: checa pg_roles antes de criar.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'publisher') THEN
        CREATE ROLE publisher LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_reader') THEN
        CREATE ROLE bi_reader LOGIN;
    END IF;
    EXECUTE format('ALTER ROLE publisher PASSWORD %L', current_setting('bi.publisher_password'));
    EXECUTE format('ALTER ROLE bi_reader PASSWORD %L', current_setting('bi.reader_password'));
END
$$;

CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS ops;

-- R5: ninguem cria objetos em public por heranca.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- publisher e dono das tabelas novas de gold e escreve em ops.
GRANT USAGE, CREATE ON SCHEMA gold TO publisher;
GRANT USAGE ON SCHEMA ops TO publisher;

-- bi_reader: so SELECT em gold; sem nenhum acesso a ops.
GRANT USAGE ON SCHEMA gold TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO bi_reader;
REVOKE ALL ON SCHEMA ops FROM bi_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA ops FROM bi_reader;

-- Vale so para objetos criados pelo publisher (mem-ccc193da).
ALTER DEFAULT PRIVILEGES FOR ROLE publisher IN SCHEMA gold GRANT SELECT ON TABLES TO bi_reader;
