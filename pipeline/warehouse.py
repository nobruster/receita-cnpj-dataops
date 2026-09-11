"""C4 — o único lugar que abre o arquivo DuckDB.

DuckDB é *single-writer*: um processo escreve por vez. Todos os escritores
(carga raw, dbt, monitores, publicação) passam por :func:`connect_rw` e rodam em
série (job Dagster com ``max_concurrent=1``). Leitores (MCP, Sentinel) usam
:func:`connect_ro`, que fisicamente não consegue escrever.
"""

from __future__ import annotations

import duckdb

from pipeline.config import Settings, get_settings


def _pragmas(con: duckdb.DuckDBPyConnection, s: Settings) -> None:
    con.execute(f"SET memory_limit = '{s.duckdb_memory_limit}'")
    con.execute(f"SET threads = {int(s.duckdb_threads)}")
    con.execute(f"SET temp_directory = '{s.duckdb_temp_dir.as_posix()}'")
    con.execute("SET preserve_insertion_order = false")  # menos memória em cargas grandes


def connect_rw(settings: Settings | None = None) -> duckdb.DuckDBPyConnection:
    s = settings or get_settings()
    s.ensure_dirs()
    con = duckdb.connect(str(s.warehouse_path))
    _pragmas(con, s)
    return con


def connect_ro(settings: Settings | None = None) -> duckdb.DuckDBPyConnection:
    s = settings or get_settings()
    con = duckdb.connect(str(s.warehouse_path), read_only=True)
    con.execute(f"SET memory_limit = '{s.duckdb_memory_limit}'")
    con.execute(f"SET threads = {int(s.duckdb_threads)}")
    return con


def table_exists(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
            [schema, table],
        ).fetchone()[0]
    )
