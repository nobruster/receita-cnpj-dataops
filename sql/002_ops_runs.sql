-- T-010: trilha de publicacao em ops.runs. Idempotente.
-- Aplicar com o usuario admin: psql -f sql/002_ops_runs.sql
-- So metadados (contagens, duracao, hash); nenhum valor de celula.

\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS ops.runs (
    tabela          text        NOT NULL,
    run_id          text        NOT NULL,
    contagem        bigint,
    duracao_ms      bigint,
    menor_n         bigint,
    allowlist_hash  text,
    motivo_recusa   text,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    -- retry do Airflow regrava a mesma publicacao sem duplicar linha (KO-003)
    CONSTRAINT runs_chave_unica UNIQUE (tabela, run_id)
);

GRANT INSERT, SELECT ON ops.runs TO publisher;
REVOKE ALL ON ops.runs FROM bi_reader;
