"""T-008: falha induzida no meio do swap e __novo órfão (R-5, R-6, KO-003). Postgres real, sem skip.

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

TABELA = "t008_probe"


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
    pg.execute(f'DROP TABLE IF EXISTS gold."{TABELA}__novo"')
    pg.execute(f'DROP TABLE IF EXISTS gold."{TABELA}" CASCADE')


def _contagem(pg) -> int:
    return pg.execute(f'SELECT count(*) FROM gold."{TABELA}"').fetchone()[0]


def _bi_reader_le(pg) -> bool:
    return pg.execute(f"SELECT has_table_privilege('bi_reader', 'gold.\"{TABELA}\"', 'SELECT')").fetchone()[0]


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


def test_falha_entre_drop_e_rename_mantem_tabela_antiga(cenario, pg_publisher):
    antes = _contagem(pg_publisher)

    def falha_induzida() -> None:
        raise RuntimeError("falha induzida entre DROP e RENAME")

    with pytest.raises(RuntimeError):
        publicar.publicar_tabela(cenario, TABELA, settings=settings_publisher(), antes_do_rename=falha_induzida)
    assert _contagem(pg_publisher) == antes  # tabela antiga intacta
    assert _bi_reader_le(pg_publisher)  # GRANT da tabela antiga preservado
    assert pg_publisher.execute(f"SELECT to_regclass('gold.\"{TABELA}__novo\"')").fetchone()[0] is None


def test_pg_terminate_backend_no_meio_do_swap_nao_perde_tabela(cenario, pg_publisher, pg_admin):
    antes = _contagem(pg_publisher)

    def derruba_publicador() -> None:
        pg_admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE usename = 'publisher' AND state = 'idle in transaction' AND pid <> pg_backend_pid()"
        )

    with pytest.raises(psycopg.Error):  # o publicador morre no RENAME e a transação é desfeita
        publicar.publicar_tabela(cenario, TABELA, settings=settings_publisher(), antes_do_rename=derruba_publicador)
    assert _contagem(pg_publisher) == antes
    assert _bi_reader_le(pg_publisher)


def test_novo_orfao_e_removido_no_proximo_run(cenario, pg_publisher):
    pg_publisher.execute(f'CREATE TABLE gold."{TABELA}__novo" (x int)')  # sobra de execução anterior
    assert pg_publisher.execute(f"SELECT to_regclass('gold.\"{TABELA}__novo\"')").fetchone()[0] is not None
    publicadas = publicar.publicar_tabela(cenario, TABELA, settings=settings_publisher())
    assert publicadas == 5
    assert pg_publisher.execute(f"SELECT to_regclass('gold.\"{TABELA}__novo\"')").fetchone()[0] is None
    assert _contagem(pg_publisher) == 5
