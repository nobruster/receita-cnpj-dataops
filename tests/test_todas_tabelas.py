"""T-011: publicar todas as tabelas da allowlist (M1, M3, R-7). Postgres real, sem skip.

Escrito manualmente (oráculo de autoria humana): o executor não cria arquivos congelados.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from pipeline.bi import allowlist, publicar
from tests.test_grant_after_swap import settings_publisher

APROVADAS = {"t011_a": 5, "t011_b": 6}
HISTORICO = "gold_resumo_competencia"


def _criar_duckdb(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"))
    con.execute("CREATE SCHEMA gold")
    for tabela, linhas in APROVADAS.items():
        con.execute(f"CREATE TABLE gold.{tabela} (a VARCHAR, b BIGINT)")
        con.execute(f"INSERT INTO gold.{tabela} SELECT 'x' || i, i FROM range({linhas}) t(i)")
    con.execute(f"CREATE TABLE gold.{HISTORICO} (competencia VARCHAR, total BIGINT)")
    con.execute(f"INSERT INTO gold.{HISTORICO} VALUES ('2026-08', 1), ('2026-09', 2), ('2026-10', 3)")
    esquema = allowlist._listar_colunas(con)
    dados = {
        "esquema_hash": allowlist.hash_esquema(esquema),
        "assinatura": {"por": "Bruno", "em": "2026-10-10"},
        "tabelas": {
            t: {"colunas": {n: {"tipo": ty, "classe": None, "aprovado": True} for n, ty in esquema[t]}}
            for t in APROVADAS
        },
        "excluidas": {
            HISTORICO: {"modo": "delete_copy_legado", "motivo": "teste T-011", "colunas": {}}
        },
        "nao_publicar": {},
    }
    (tmp_path / "allowlist.json").write_text(json.dumps(dados), encoding="utf-8")
    return con


def _limpar(pg) -> None:
    for t in [*APROVADAS, HISTORICO]:
        pg.execute(f'DROP TABLE IF EXISTS gold."{t}" CASCADE')
        pg.execute(f'DROP TABLE IF EXISTS gold."{t}__novo"')


@pytest.fixture
def cenario(tmp_path, pg_publisher):
    _limpar(pg_publisher)
    pg_publisher.execute(f'CREATE TABLE gold."{HISTORICO}" (competencia varchar, total bigint)')
    pg_publisher.execute(f"INSERT INTO gold.\"{HISTORICO}\" VALUES ('2026-08', 1), ('2026-09', 2), ('2026-10', 3)")
    con = _criar_duckdb(tmp_path)
    yield con, tmp_path
    con.close()
    _limpar(pg_publisher)


def _contagem(pg, tabela: str) -> int:
    return pg.execute(f'SELECT count(*) FROM gold."{tabela}"').fetchone()[0]


def _oid(pg, tabela: str) -> int:
    return pg.execute(f"SELECT '\"gold\".\"{tabela}\"'::regclass::oid").fetchone()[0]


def test_publicar_todas_publica_aprovadas_e_pula_excluidas(cenario, pg_publisher):
    con, tmp_path = cenario
    oid_hist = _oid(pg_publisher, HISTORICO)
    publicar.publicar_todas(con, settings=settings_publisher(), caminho=tmp_path / "allowlist.json")
    for tabela, linhas in APROVADAS.items():  # M1/M3: 100% das tabelas aprovadas, contagem igual ao DuckDB
        assert _contagem(pg_publisher, tabela) == linhas
    assert _oid(pg_publisher, HISTORICO) == oid_hist  # histórico não foi trocado
    assert _contagem(pg_publisher, HISTORICO) == 3


def test_entrada_main():
    assert Path(publicar.__file__).parent.joinpath("__main__.py").is_file()
