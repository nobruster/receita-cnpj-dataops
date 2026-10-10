"""T-003: papéis e DDL idempotente contra um Postgres real (R-2)."""

from __future__ import annotations

import tomllib

import psycopg
import pytest

from tests.conftest import ROOT, apply_ddl

TABELA = "gold.t003_probe"


def test_fixture_falha_sem_banco():
    src = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    inicio = src.index("def _connect_or_fail")
    fim = src.index("def apply_ddl")
    assert "pytest.fail(" in src[inicio:fim]
    # as fixtures novas não podem pular sem banco
    assert "pytest.skip" not in src[src.index("# --- Postgres real") :]


def test_marker_docker():
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = cfg["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.split(":")[0].strip() == "docker" for m in markers)


@pytest.fixture
def tabela_publisher(pg_publisher, pg_admin):
    pg_publisher.execute(f"DROP TABLE IF EXISTS {TABELA}")
    pg_publisher.execute(f"CREATE TABLE {TABELA} (id int, nome text)")
    pg_publisher.execute(f"INSERT INTO {TABELA} VALUES (1, 'a')")
    yield TABELA
    pg_publisher.execute(f"DROP TABLE IF EXISTS {TABELA}")


@pytest.mark.docker
def test_ddl_idempotente(pg_admin):
    apply_ddl(pg_admin)
    apply_ddl(pg_admin)


@pytest.mark.docker
def test_publisher_nao_e_superuser(pg_publisher):
    assert pg_publisher.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user").fetchone() == (False,)


@pytest.mark.docker
def test_bi_reader_le_e_nao_escreve_em_gold(tabela_publisher, pg_bi_reader):
    assert pg_bi_reader.execute(f"SELECT count(*) FROM {tabela_publisher}").fetchone() == (1,)
    for stmt in (
        f"INSERT INTO {tabela_publisher} VALUES (2, 'b')",
        f"UPDATE {tabela_publisher} SET nome = 'x'",
        f"DELETE FROM {tabela_publisher}",
        "CREATE TABLE gold.t003_bi_reader (id int)",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pg_bi_reader.execute(stmt)


@pytest.mark.docker
def test_bi_reader_sem_acesso_a_ops(pg_admin, pg_bi_reader):
    pg_admin.execute("CREATE TABLE IF NOT EXISTS ops.t003_probe (id int)")
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pg_bi_reader.execute("SELECT * FROM ops.t003_probe")
    finally:
        pg_admin.execute("DROP TABLE IF EXISTS ops.t003_probe")
