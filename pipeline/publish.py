"""C6 — publica tabelas gold do DuckDB no PostgreSQL (Power BI / SQL).

Sem extensão ``postgres`` do DuckDB (que exige download em tempo de execução e
costuma ser bloqueada em rede corporativa): o DuckDB exporta CSV e o psycopg faz
``COPY FROM STDIN`` em streaming.

Tudo numa ÚNICA transação (achado 9 do reviewer): cada tabela é carregada em
``<tabela>__novo``; só no fim, com ``lock_timeout``, as antigas saem e as novas entram.
Ou o Postgres vê a competência nova inteira, ou continua na anterior inteira.
``gold_resumo_competencia`` acumula histórico (uma linha por competência) e ganha
colunas novas automaticamente se o modelo dbt evoluir.
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
LOCK_TIMEOUT = "60s"


def _pg_type(duck_type: str) -> str:
    if duck_type.startswith("DECIMAL"):
        return duck_type.replace("DECIMAL", "numeric")
    return _TYPE_MAP.get(duck_type, "text")


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    cols = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'gold' AND table_name = ? ORDER BY ordinal_position", [table]
    ).fetchall()
    if not cols:
        raise ValueError(f"gold.{table} não existe no warehouse")
    return cols


def _copy(cur: psycopg.Cursor, target: str, names: str, csv_path: Path) -> None:
    with cur.copy(f"COPY {target} ({names}) FROM STDIN (FORMAT csv, NULL '')") as cp, csv_path.open("rb") as fh:
        while chunk := fh.read(8 * 1024 * 1024):
            cp.write(chunk)


def publish_all(con: duckdb.DuckDBPyConnection, tables: list[str], competencia: str,
                settings: Settings | None = None) -> dict[str, int]:
    s = settings or get_settings()
    schema = s.publish_schema
    specs = {t: _columns(con, t) for t in tables}
    csvs: dict[str, Path] = {}
    try:
        for t in tables:
            csvs[t] = s.work_dir / f"publish_{t}.csv"
            con.execute(f"COPY gold.{t} TO '{csvs[t].as_posix()}' (HEADER false, DELIMITER ',', QUOTE '\"', NULL '')")
        rows: dict[str, int] = {}
        with psycopg.connect(s.pg_dsn) as pg, pg.cursor() as cur:  # uma transação para tudo
            cur.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            for t, cols in specs.items():
                ddl = ", ".join(f'"{c}" {_pg_type(ty)}' for c, ty in cols)
                names = ", ".join(f'"{c}"' for c, _ in cols)
                if t in HISTORY_TABLES:
                    cur.execute(f'CREATE TABLE IF NOT EXISTS {schema}."{t}" ({ddl})')
                    existentes = {r[0] for r in cur.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema = %s "
                        "AND table_name = %s", [schema, t]).fetchall()}
                    for c, ty in cols:
                        if c not in existentes:
                            cur.execute(f'ALTER TABLE {schema}."{t}" ADD COLUMN "{c}" {_pg_type(ty)}')
                    cur.execute(f'DELETE FROM {schema}."{t}" WHERE competencia = %s', [competencia])
                    _copy(cur, f'{schema}."{t}"', names, csvs[t])
                    rows[t] = cur.execute(f'SELECT count(*) FROM {schema}."{t}" WHERE competencia = %s',
                                          [competencia]).fetchone()[0]
                else:
                    cur.execute(f'DROP TABLE IF EXISTS {schema}."{t}__novo"')
                    cur.execute(f'CREATE TABLE {schema}."{t}__novo" ({ddl})')
                    _copy(cur, f'{schema}."{t}__novo"', names, csvs[t])
                    for col in INDEXES.get(t, []):
                        cur.execute(f'CREATE INDEX ON {schema}."{t}__novo" ("{col}")')
                    rows[t] = cur.execute(f'SELECT count(*) FROM {schema}."{t}__novo"').fetchone()[0]
            for t in specs:  # troca: tudo ou nada
                if t not in HISTORY_TABLES:
                    cur.execute(f'DROP TABLE IF EXISTS {schema}."{t}"')
                    cur.execute(f'ALTER TABLE {schema}."{t}__novo" RENAME TO "{t}"')
            pg.commit()
    finally:
        for p in csvs.values():
            p.unlink(missing_ok=True)
    for t, n in rows.items():
        log.info("publicado %s.%s: %s linhas", schema, t, f"{n:,}")
    return rows


def publish_table(con: duckdb.DuckDBPyConnection, table: str, competencia: str,
                  settings: Settings | None = None) -> int:
    """Atalho para uma tabela (mantido para compatibilidade)."""
    return publish_all(con, [table], competencia, settings)[table]
