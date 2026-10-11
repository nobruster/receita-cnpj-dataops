"""T-007: guarda LGPD bloqueante fail-closed (OR-002, R-6).

Fixtures sintéticas e fixas em DuckDB em memória; o teste de "nada escrito" usa o Postgres real.
"""

from __future__ import annotations

import json

import duckdb
import pytest

from pipeline.bi import allowlist, guarda, publicar
from tests.test_grant_after_swap import settings_publisher

TABELA = "t007_probe"
SEGREDO = "VALOR-SECRETO-123"


def montar(grupos: list[tuple[str | None, int]], coluna_extra: str | None = None):
    """DuckDB em memória com gold.TABELA(uf quase-identificador, valor); grupos = (uf, n)."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA gold")
    extra = f", {coluna_extra} VARCHAR" if coluna_extra else ""
    con.execute(f"CREATE TABLE gold.{TABELA} (uf VARCHAR, valor BIGINT{extra})")
    for uf, n in grupos:
        for i in range(n):
            ins = f"INSERT INTO gold.{TABELA} (uf, valor) VALUES (?, ?)"
            con.execute(ins, [uf, i])
    return con


def rodar(con, colunas=("uf", "valor"), declaradas=("uf", "valor"), quase=("uf",)):
    guarda.verificar(con, TABELA, list(colunas), set(declaradas), set(quase))


def test_n4_recusa():
    with pytest.raises(guarda.GuardaRecusada) as exc:
        rodar(montar([("SP", 4)]))
    assert TABELA in str(exc.value) and "uf" in str(exc.value)


def test_n5_e_n6_passam():
    rodar(montar([("SP", 5), ("RJ", 6)]))


def test_um_grupo_pequeno_entre_grandes_recusa():
    with pytest.raises(guarda.GuardaRecusada):
        rodar(montar([("SP", 50), ("RJ", 4)]))


def test_coluna_fora_da_allowlist_recusa():
    with pytest.raises(guarda.GuardaRecusada) as exc:
        rodar(montar([("SP", 5)]), declaradas=("uf",))
    assert f"{TABELA}.valor" in str(exc.value)


@pytest.mark.parametrize("nome", ["cpf", "nome_socio", "data_nasc", "NASCIMENTO"])
def test_nome_pessoal_recusa(nome):
    con = montar([("SP", 5)], coluna_extra=nome)
    with pytest.raises(guarda.GuardaRecusada) as exc:
        rodar(con, colunas=("uf", "valor", nome), declaradas=("uf", "valor", nome))
    assert nome in str(exc.value)


def test_grupo_com_null_e_deterministico():
    with pytest.raises(guarda.GuardaRecusada):
        rodar(montar([("SP", 5), (None, 4)]))
    rodar(montar([("SP", 5), (None, 5)]))


def test_tabela_vazia_e_deterministica():
    rodar(montar([]))
    rodar(montar([]))


def test_sem_quase_identificador_nao_testa_k():
    rodar(montar([("SP", 1)]), quase=())


def test_mensagem_nao_contem_valores():
    con = montar([(SEGREDO, 2)])
    with pytest.raises(guarda.GuardaRecusada) as exc:
        rodar(con)
    assert SEGREDO not in str(exc.value)
    assert exc.value.__cause__ is None


def test_allowlist_ilegivel_ou_tabela_ausente_recusa(tmp_path):
    with pytest.raises(guarda.GuardaRecusada):
        guarda.quase_identificadores(TABELA, tmp_path / "nao_existe.json")
    (tmp_path / "a.json").write_text(json.dumps({"tabelas": {}}), encoding="utf-8")
    with pytest.raises(guarda.GuardaRecusada):
        guarda.quase_identificadores(TABELA, tmp_path / "a.json")


def allowlist_com_quase(con, tmp_path):
    esquema = allowlist._listar_colunas(con)
    classes = {"uf": "quase-identificador", "valor": "agregado"}
    dados = {
        "esquema_hash": allowlist.hash_esquema(esquema),
        "assinatura": {"por": "Bruno", "em": "2026-10-10"},
        "tabelas": {
            TABELA: {"colunas": {n: {"tipo": t, "classe": classes[n], "aprovado": True} for n, t in esquema[TABELA]}}
        },
        "excluidas": {},
        "nao_publicar": {},
    }
    caminho = tmp_path / "allowlist.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


@pytest.mark.docker
def test_aborto_nao_escreve_no_postgres(tmp_path, monkeypatch, pg_admin, pg_publisher):
    """B-1/OR-002: célula n=4 aborta antes de qualquer escrita (nem __novo nem a tabela final)."""
    from functools import partial

    con = montar([("SP", 4)])
    caminho = allowlist_com_quase(con, tmp_path)
    monkeypatch.setattr(publicar, "colunas_aprovadas", partial(allowlist.colunas_aprovadas, caminho=caminho))
    with pytest.raises(guarda.GuardaRecusada) as exc:
        publicar.publicar_tabela(con, TABELA, settings=settings_publisher())
    assert "SP" not in str(exc.value)
    achadas = pg_admin.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'gold' AND table_name LIKE %s",
        [f"{TABELA}%"],
    ).fetchone()[0]
    assert achadas == 0
