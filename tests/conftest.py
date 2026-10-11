"""Fixtures compartilhadas.

Os testes de ponta a ponta precisam de um PostgreSQL (ledger ``ops``). Aponte com
as variáveis PG_* (ou use ``docker compose up -d postgres``); sem banco eles são
PULADOS com motivo claro — nunca fingem que passaram.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _pg_ok() -> bool:
    from pipeline.config import get_settings

    try:
        with psycopg.connect(get_settings().pg_dsn, connect_timeout=3):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("cnpjdata")
    os.environ["DATA_DIR"] = str(d)
    os.environ["DUCKDB_MEMORY_LIMIT"] = "1GB"
    os.environ["DUCKDB_THREADS"] = "2"
    os.environ["OFFLINE_MODE"] = "true"
    os.environ["SENTINEL_LLM_PROVIDER"] = "none"
    os.environ.setdefault("DBT_BIN", shutil.which("dbt") or str(ROOT / ".venv" / "bin" / "dbt"))
    from pipeline.config import get_settings

    get_settings.cache_clear()
    get_settings().ensure_dirs()
    return d


@pytest.fixture(scope="session")
def pg(data_dir: Path):
    if not _pg_ok():
        pytest.skip("PostgreSQL indisponível (defina PG_HOST/PG_USER/PG_PASSWORD/PG_DB)")
    from pipeline import ops

    ops.ensure_schema()
    with ops.session() as conn:
        conn.execute("TRUNCATE ops.incidents, ops.dq_metrics, ops.competencias, ops.diagnoses RESTART IDENTITY")
    return True


# --- Postgres real para papéis/DDL (T-003) -------------------------------------------------
# Container descartável só em loopback. Estas fixtures FALHAM (pytest.fail) sem banco:
# um skip daria falso verde, porque o pytest sai com 0.

DDL_PATH = ROOT / "sql" / "001_schemas_roles.sql"
BI_READER_PASSWORD = os.environ.get("BI_READER_PASSWORD", "test-reader")
PUBLISHER_PASSWORD = os.environ.get("PUBLISHER_PASSWORD", "test-publisher")


def _pg_conninfo(user: str, password: str) -> str:
    host = os.environ.get("PG_HOST", "127.0.0.1")
    port = os.environ.get("PG_PORT", "5434")
    db = os.environ.get("PG_DB", "postgres")
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def _connect_or_fail(user: str, password: str) -> psycopg.Connection:
    try:
        return psycopg.connect(_pg_conninfo(user, password), connect_timeout=3, autocommit=True)
    except Exception as exc:
        pytest.fail(
            f"PostgreSQL não respondeu como '{user}' em "
            f"{os.environ.get('PG_HOST', '127.0.0.1')}:{os.environ.get('PG_PORT', '5434')}: {exc}. "
            "Suba o container de teste (loopback, porta 5434) ou ajuste PG_HOST/PG_PORT/PG_DB.",
            pytrace=False,
        )


def apply_ddl(conn: psycopg.Connection) -> None:
    """Aplica sql/001_schemas_roles.sql sem o psql: troca os meta-comandos por parâmetros."""
    conn.execute("SELECT set_config('bi.reader_password', %s, false)", (BI_READER_PASSWORD,))
    conn.execute("SELECT set_config('bi.publisher_password', %s, false)", (PUBLISHER_PASSWORD,))
    lines = DDL_PATH.read_text(encoding="utf-8").splitlines()
    body = [ln for ln in lines if not ln.startswith("\\") and "set_config('bi." not in ln]
    conn.execute("\n".join(body))


@pytest.fixture(scope="session")
def pg_admin():
    admin_user = os.environ.get("PG_ADMIN_USER", "postgres")
    conn = _connect_or_fail(admin_user, os.environ.get("PG_ADMIN_PASSWORD", ""))
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def pg_ddl(pg_admin):
    apply_ddl(pg_admin)
    # T-010: publicar grava em ops.runs (sql/002); sem essa tabela o publicador falha
    ops = Path(ROOT / "sql" / "002_ops_runs.sql").read_text(encoding="utf-8")
    pg_admin.execute("\n".join(ln for ln in ops.splitlines() if not ln.startswith("\\")))
    return True


@pytest.fixture
def pg_publisher(pg_ddl):
    conn = _connect_or_fail("publisher", PUBLISHER_PASSWORD)
    yield conn
    conn.close()


@pytest.fixture
def pg_bi_reader(pg_ddl):
    conn = _connect_or_fail("bi_reader", BI_READER_PASSWORD)
    yield conn
    conn.close()
