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
