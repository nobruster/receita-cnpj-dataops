"""T-006: o bi_reader continua lendo depois da troca DROP/RENAME (OR-001, R-1/R-3).

Postgres real, sem skip: publica como publisher e lê como bi_reader, em conexões separadas.
"""

from __future__ import annotations

import json
import os
from functools import partial

import duckdb
import psycopg
import pytest

from pipeline.bi import allowlist, publicar
from pipeline.config import Settings
from tests.conftest import PUBLISHER_PASSWORD

TABELA = "t006_probe"
LINHAS = 7


def settings_publisher() -> Settings:
    return Settings(
        pg_host=os.environ.get("PG_HOST", "127.0.0.1"),
        pg_port=int(os.environ.get("PG_PORT", "5434")),
        pg_db=os.environ.get("PG_DB", "postgres"),
        publisher_user="publisher",
        publisher_password=PUBLISHER_PASSWORD,
        publish_schema="gold",
    )


def criar_duckdb(tmp_path, linhas: int = LINHAS) -> duckdb.DuckDBPyConnection:
    """DuckDB temporário em arquivo com gold.<TABELA> e allowlist de fixture assinada."""
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


def publicar_fixture(monkeypatch, con, tmp_path) -> int:
    """Publica TABELA lendo a allowlist de fixture (o default do módulo aponta para a versionada)."""
    monkeypatch.setattr(
        publicar, "colunas_aprovadas", partial(allowlist.colunas_aprovadas, caminho=tmp_path / "allowlist.json")
    )
    return publicar.publicar_tabela(con, TABELA, settings=settings_publisher())


def limpar(pg_publisher) -> None:
    pg_publisher.execute(f'DROP TABLE IF EXISTS gold."{TABELA}"')
    pg_publisher.execute(f'DROP TABLE IF EXISTS gold."{TABELA}__novo"')


@pytest.fixture
def publicado(tmp_path, monkeypatch, pg_publisher):
    limpar(pg_publisher)
    con = criar_duckdb(tmp_path)
    publicar_fixture(monkeypatch, con, tmp_path)
    yield con
    limpar(pg_publisher)
    con.close()


@pytest.mark.docker
def test_bi_reader_le_depois_da_troca(publicado, pg_bi_reader):
    """B-1: após a troca o bi_reader faz SELECT."""
    assert pg_bi_reader.execute(f"SELECT count(*) FROM gold.{TABELA}").fetchone() == (LINHAS,)


@pytest.mark.docker
def test_sem_grant_o_teste_detecta(publicado, pg_admin, pg_bi_reader):
    """B-2: com o GRANT revogado o acesso é negado — o teste enxerga a falta."""
    pg_admin.execute(f"REVOKE SELECT ON gold.{TABELA} FROM bi_reader")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        pg_bi_reader.execute(f"SELECT count(*) FROM gold.{TABELA}")
