"""C6 — publica tabelas gold do DuckDB no PostgreSQL (Power BI / SQL).

Sem extensão ``postgres`` do DuckDB (que exige download em tempo de execução e
costuma ser bloqueado em rede corporativa): o DuckDB exporta CSV e o psycopg faz
``COPY FROM STDIN`` em streaming — rápido e sem dependência extra.

Troca atômica: carrega em ``<tabela>__novo`` e renomeia numa transação, então o
Power BI nunca vê tabela pela metade. ``gold_resumo_competencia`` é a exceção:
acumula histórico (uma linha por competência).
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import psycopg

from pipeline.config import Settings, get_settings

log = logging.getLogger("pipeline.publish")

HISTORY_TABLES = {"gold_resumo_competencia"}
INDEXES = {
    "gold_empresa_detalhe": ["cnpj", "cnpj_basico", "cnae_fiscal_principal", "municipio"],
    "gold_socios_detalhe": ["cnpj_basico", "cnpj_cpf_socio"],
    "gold_rede_societaria": ["cnpj_basico_socio", "cnpj_basico_investida"],
    "gold_painel_prospeccao": ["uf", "cnae_fiscal_principal"],
}
_TYPE_MAP = {
    "VARCHAR": "text", "DATE": "date", "BIGINT": "bigint", "INTEGER": "integer", "HUGEINT": "numeric",
    "DOUBLE": "double precision", "FLOAT": "real", "BOOLEAN": "boolean",
    "TIMESTAMP WITH TIME ZONE": "timestamptz", "TIMESTAMP": "timestamp",
}


def _pg_type(duck_type: str) -> str:
    if duck_type.startswith("DECIMAL"):
        return duck_type.replace("DECIMAL", "numeric")
    return _TYPE_MAP.get(duck_type, "text")


def publish_table(con: duckdb.DuckDBPyConnection, table: str, competencia: str,
                  settings: Settings | None = None) -> int:
    s = settings or get_settings()
    schema = s.publish_schema
    cols = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'gold' AND table_name = ? ORDER BY ordinal_position", [table]
    ).fetchall()
    if not cols:
        raise ValueError(f"gold.{table} não existe no warehouse")
    tmp = s.work_dir / f"publish_{table}.csv"
    con.execute(f"COPY gold.{table} TO '{tmp.as_posix()}' (HEADER false, DELIMITER ',', QUOTE '\"', NULL '')")
    ddl_cols = ", ".join(f'"{c}" {_pg_type(t)}' for c, t in cols)
    names = ", ".join(f'"{c}"' for c, _ in cols)
    rows = 0
    try:
        with psycopg.connect(s.pg_dsn) as pg, pg.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            if table in HISTORY_TABLES:
                cur.execute(f'CREATE TABLE IF NOT EXISTS {schema}."{table}" ({ddl_cols})')
                cur.execute(f'DELETE FROM {schema}."{table}" WHERE competencia = %s', [competencia])
                target = f'{schema}."{table}"'
            else:
                cur.execute(f'DROP TABLE IF EXISTS {schema}."{table}__novo"')
                cur.execute(f'CREATE UNLOGGED TABLE {schema}."{table}__novo" ({ddl_cols})')
                target = f'{schema}."{table}__novo"'
            with cur.copy(f"COPY {target} ({names}) FROM STDIN (FORMAT csv, NULL '')") as cp, \
                    Path(tmp).open("rb") as fh:
                while chunk := fh.read(8 * 1024 * 1024):
                    cp.write(chunk)
            rows = cur.execute(f"SELECT count(*) FROM {target}").fetchone()[0]
            if table not in HISTORY_TABLES:
                cur.execute(f'ALTER TABLE {schema}."{table}__novo" SET LOGGED')
                for col in INDEXES.get(table, []):
                    cur.execute(f'CREATE INDEX ON {schema}."{table}__novo" ("{col}")')
                cur.execute(f'DROP TABLE IF EXISTS {schema}."{table}"')
                cur.execute(f'ALTER TABLE {schema}."{table}__novo" RENAME TO "{table}"')
            pg.commit()
    finally:
        tmp.unlink(missing_ok=True)
    log.info("publicado %s.%s: %s linhas", schema, table, f"{rows:,}")
    return rows
