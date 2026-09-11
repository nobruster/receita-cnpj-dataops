"""C4 — o único lugar que abre o arquivo DuckDB.

DuckDB é *single-writer*: um processo escreve por vez. Todos os escritores
(carga raw, dbt, monitores, histórico, publicação) passam por :func:`connect_rw` e,
no Airflow, pelo pool ``duckdb_writer`` (1 vaga) com ``max_active_runs=1``. Leitores
(consultas, evals, Sentinel) usam :func:`connect_ro`, que fisicamente não escreve.

Fora do Airflow (CLI), um segundo escritor é recusado pela trava de arquivo do
próprio DuckDB — nunca há corrupção; aqui a recusa vira mensagem clara (O5 do Passo 4).
O ``memory_limit`` efetivo nunca passa de 60% da memória do container (O6).
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import duckdb

from pipeline.config import Settings, get_settings

log = logging.getLogger("pipeline.warehouse")

MEMORY_SHARE = 0.60
_UNITS = {"KB": 1024, "KIB": 1024, "MB": 1024**2, "MIB": 1024**2, "GB": 1024**3, "GIB": 1024**3,
          "TB": 1024**4, "TIB": 1024**4, "B": 1}


_AVISADOS: set[tuple[str, int]] = set()


class WarehouseBusyError(RuntimeError):
    """Outro processo segura o DuckDB para escrita."""


def parse_size(value: str) -> int:
    m = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]*)\s*", value)
    if not m:
        raise ValueError(f"tamanho inválido: {value!r}")
    return int(float(m.group(1)) * _UNITS.get((m.group(2) or "B").upper(), 1))


def container_memory_bytes() -> int | None:
    """Limite de memória do cgroup (v2 ou v1); sem limite, a memória física da máquina."""
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(f).read_text().strip()
        except OSError:
            continue
        if raw.isdigit() and int(raw) < 1 << 60:
            return int(raw)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def effective_memory_limit(configured: str, available: int | None = None) -> str:
    """Reduz o limite configurado para no máximo 60% da memória disponível (nunca aumenta)."""
    total = available if available is not None else container_memory_bytes()
    pedido = parse_size(configured)
    if not total or pedido <= total * MEMORY_SHARE:
        return configured
    teto_mb = int(total * MEMORY_SHARE / 1024**2)
    if (configured, teto_mb) in _AVISADOS:
        return f"{teto_mb}MB"
    _AVISADOS.add((configured, teto_mb))
    log.warning("DUCKDB_MEMORY_LIMIT=%s excede 60%% da memória do container (%.1f GB); usando %dMB",
                configured, total / 1024**3, teto_mb)
    return f"{teto_mb}MB"


def _pragmas(con: duckdb.DuckDBPyConnection, s: Settings) -> None:
    con.execute(f"SET memory_limit = '{effective_memory_limit(s.duckdb_memory_limit)}'")
    con.execute(f"SET threads = {int(s.duckdb_threads)}")
    con.execute(f"SET temp_directory = '{s.duckdb_temp_dir.as_posix()}'")
    con.execute("SET preserve_insertion_order = false")  # menos memória em cargas grandes


def connect_rw(settings: Settings | None = None, wait_s: int | None = None) -> duckdb.DuckDBPyConnection:
    """Abre para escrita. Se um leitor ou outro escritor segura o arquivo, espera até
    ``duckdb_lock_wait_s`` (leitores abrem e fecham rápido) antes de desistir com mensagem clara."""
    s = settings or get_settings()
    s.ensure_dirs()
    limite = s.duckdb_lock_wait_s if wait_s is None else wait_s
    inicio = time.monotonic()
    while True:
        try:
            con = duckdb.connect(str(s.warehouse_path))
            break
        except duckdb.IOException as exc:
            if time.monotonic() - inicio >= limite:
                raise WarehouseBusyError(
                    f"outro processo segura {s.warehouse_path} há mais de {limite}s (a DAG está rodando?). "
                    "Espere terminar: o DuckDB aceita um único escritor."
                ) from exc
            log.info("warehouse ocupado; nova tentativa em 5s")
            time.sleep(min(5, max(0.5, limite / 10)))
    _pragmas(con, s)
    return con


def connect_ro(settings: Settings | None = None) -> duckdb.DuckDBPyConnection:
    """Somente leitura, SEM acesso a arquivos externos e com configuração travada: nem um SQL
    injetado consegue ler ``/proc``, ``.env`` ou CSVs do container (achado 1 do reviewer)."""
    s = settings or get_settings()
    return duckdb.connect(str(s.warehouse_path), read_only=True, config={
        "enable_external_access": False,
        "memory_limit": effective_memory_limit(s.duckdb_memory_limit),
        "threads": int(s.duckdb_threads),
        "lock_configuration": True,
    })


MASKED_SCHEMAS = ("silver", "gold", "raw")


def connect_ro_masked(deny_columns: tuple[str, ...], settings: Settings | None = None) -> duckdb.DuckDBPyConnection:
    """Leitura para o LLM: banco em memória com o warehouse anexado só-leitura e, por cima,
    views ``schema.tabela`` SEM as colunas negadas. Nem ``SELECT t FROM gold.x t`` (a linha
    inteira como STRUCT) nem ``to_json``/``COLUMNS()`` alcançam dado pessoal: a coluna não
    existe na view. Depois do ATTACH, acesso externo é desligado e a configuração travada."""
    s = settings or get_settings()
    con = duckdb.connect(":memory:", config={
        "memory_limit": effective_memory_limit(s.duckdb_memory_limit),
        "threads": int(s.duckdb_threads),
    })
    alias = s.warehouse_path.stem  # as views do dbt citam o catálogo pelo nome do arquivo ("cnpj")
    try:
        con.execute(f"ATTACH '{s.warehouse_path.as_posix()}' AS \"{alias}\" (READ_ONLY)")
        negadas = {c.lower() for c in deny_columns}
        cols: dict[tuple[str, str], list[str]] = {}
        for schema, table, col in con.execute(
            "SELECT table_schema, table_name, column_name FROM information_schema.columns "
            "WHERE table_catalog = ? AND table_schema IN ('silver', 'gold', 'raw') "
            "ORDER BY table_schema, table_name, ordinal_position", [alias]
        ).fetchall():
            cols.setdefault((schema, table), []).append(col)
        for schema in MASKED_SCHEMAS:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for (schema, table), names in cols.items():
            visiveis = [f'"{c}"' for c in names if c.lower() not in negadas]
            if visiveis:
                con.execute(f'CREATE VIEW {schema}."{table}" AS SELECT {", ".join(visiveis)} '
                            f'FROM "{alias}".{schema}."{table}"')
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
    except Exception:
        con.close()
        raise
    return con


def table_exists(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
            [schema, table],
        ).fetchone()[0]
    )
