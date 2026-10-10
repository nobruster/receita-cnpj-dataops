"""T-006: contagem igual ao DuckDB e idempotência da publicação (M3, M4; R-3/R-4).

Postgres real, sem skip.
"""

from __future__ import annotations

import pytest

from tests.test_grant_after_swap import TABELA, criar_duckdb, limpar, publicar_fixture


def _novos_em_gold(pg_admin) -> list[tuple]:
    return pg_admin.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'gold' AND tablename LIKE %s",
        (r"%\_\_novo",),
    ).fetchall()


@pytest.mark.docker
@pytest.mark.parametrize("linhas", [1, 12, 1234])
def test_contagem_igual_ao_duckdb(tmp_path, monkeypatch, pg_publisher, pg_bi_reader, linhas):
    """B-3: N linhas no DuckDB => exatamente N no Postgres."""
    limpar(pg_publisher)
    con = criar_duckdb(tmp_path, linhas)
    try:
        esperado = con.execute(f"SELECT count(*) FROM gold.{TABELA}").fetchone()[0]
        assert esperado == linhas
        assert publicar_fixture(monkeypatch, con, tmp_path) == linhas
        assert pg_bi_reader.execute(f"SELECT count(*) FROM gold.{TABELA}").fetchone() == (linhas,)
    finally:
        limpar(pg_publisher)
        con.close()


@pytest.mark.docker
def test_duas_execucoes_mesmo_count_sem_novo(tmp_path, monkeypatch, pg_publisher, pg_admin, pg_bi_reader):
    """B-4: a mesma publicação duas vezes mantém o count e não deixa __novo em gold."""
    limpar(pg_publisher)
    con = criar_duckdb(tmp_path, 25)
    try:
        publicar_fixture(monkeypatch, con, tmp_path)
        primeira = pg_bi_reader.execute(f"SELECT count(*) FROM gold.{TABELA}").fetchone()
        publicar_fixture(monkeypatch, con, tmp_path)
        segunda = pg_bi_reader.execute(f"SELECT count(*) FROM gold.{TABELA}").fetchone()
        assert primeira == segunda == (25,)
        assert _novos_em_gold(pg_admin) == []
    finally:
        limpar(pg_publisher)
        con.close()
