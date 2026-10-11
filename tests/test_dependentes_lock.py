"""T-009: view dependente e leitura longa no swap (R-8, KO-004). Postgres real, sem skip.

Escrito manualmente (oráculo de autoria humana): o executor não cria arquivos congelados.
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import duckdb
import psycopg
import pytest

from pipeline.bi import allowlist, publicar
from tests.test_grant_after_swap import settings_publisher
from tests.conftest import PUBLISHER_PASSWORD  # noqa: F401  (garante a mesma configuração de papéis)

TABELA = "t009_probe"
VIEW = "v_t009_probe"


def _criar_duckdb(tmp_path: Path, linhas: int = 5) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"))
    con.execute("CREATE SCHEMA gold")
    con.execute(f"CREATE TABLE gold.{TABELA} (a VARCHAR, b BIGINT)")
    con.execute(f"INSERT INTO gold.{TABELA} SELECT 'x' || i, i FROM range({linhas}) t(i)")
    esquema = allowlist._listar_colunas(con)
    dados = {
        "esquema_hash": allowlist.hash_esquema(esquema),
        "assinatura": {"por": "Bruno", "em": "2026-10-10"},
        "tabelas": {
            TABELA: {"colunas": {n: {"tipo": t, "classe": None, "aprovado": True} for n, t in esquema[TABELA]}}
        },
        "excluidas": {},
        "nao_publicar": {},
    }
    (tmp_path / "allowlist.json").write_text(json.dumps(dados), encoding="utf-8")
    return con


def _limpar(pg) -> None:
    pg.execute(f"DROP VIEW IF EXISTS gold.{VIEW}")
    pg.execute(f'DROP TABLE IF EXISTS gold."{TABELA}__novo"')
    pg.execute(f'DROP TABLE IF EXISTS gold."{TABELA}" CASCADE')


def _contagem(pg) -> int:
    return pg.execute(f'SELECT count(*) FROM gold."{TABELA}"').fetchone()[0]


@pytest.fixture
def cenario(tmp_path, monkeypatch, pg_publisher):
    _limpar(pg_publisher)
    con = _criar_duckdb(tmp_path)
    monkeypatch.setattr(
        publicar, "colunas_aprovadas", partial(allowlist.colunas_aprovadas, caminho=tmp_path / "allowlist.json")
    )
    publicar.publicar_tabela(con, TABELA, settings=settings_publisher())
    yield con
    con.close()
    _limpar(pg_publisher)


def test_view_dependente_recusa_drop_sem_perder_tabela(cenario, pg_publisher):
    pg_publisher.execute(f'CREATE VIEW gold.{VIEW} AS SELECT * FROM gold."{TABELA}"')
    antes = _contagem(pg_publisher)
    with pytest.raises(psycopg.Error):  # DROP sem CASCADE falha por causa da view
        publicar.publicar_tabela(cenario, TABELA, settings=settings_publisher())
    assert _contagem(pg_publisher) == antes  # tabela antiga intacta
    assert pg_publisher.execute(f"SELECT to_regclass('gold.\"{TABELA}__novo\"')").fetchone()[0] is None


def test_leitura_longa_no_swap_falha_com_lock_timeout(cenario, pg_publisher, pg_bi_reader):
    antes = _contagem(pg_publisher)
    pg_bi_reader.execute("BEGIN")
    pg_bi_reader.execute(f'SELECT count(*) FROM gold."{TABELA}"')  # segura lock de leitura
    try:
        with pytest.raises(psycopg.errors.LockNotAvailable):
            publicar.publicar_tabela(cenario, TABELA, settings=settings_publisher(), lock_timeout="1s")
    finally:
        pg_bi_reader.execute("ROLLBACK")
    assert _contagem(pg_publisher) == antes


def test_publicar_sem_cascade():
    fonte = Path(publicar.__file__).read_text(encoding="utf-8")
    assert "CASCADE" not in fonte
