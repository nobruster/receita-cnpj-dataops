import json

import duckdb
import pytest

from pipeline.bi import allowlist
from pipeline.bi.allowlist import AllowlistRecusada, colunas_aprovadas


def _con(ddl="CREATE TABLE gold.gold_x (a VARCHAR, b BIGINT, razao_social VARCHAR)"):
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA gold")
    con.execute(ddl)
    con.execute("CREATE TABLE gold.gold_resumo_competencia (competencia VARCHAR)")
    return con


def _escrever(tmp_path, con, aprovadas=("a", "b"), assinar=True, hash_=None, nao_publicar=True):
    esquema = allowlist._listar_colunas(con)
    cols = {n: {"tipo": t, "classe": None, "aprovado": n in aprovadas} for n, t in esquema["gold_x"]}
    dados = {
        "esquema_hash": hash_ or allowlist.hash_esquema(esquema),
        "assinatura": {"por": "Bruno", "em": "2026-10-10"} if assinar else {"por": "", "em": ""},
        "tabelas": {"gold_x": {"colunas": cols}},
        "excluidas": {"gold_resumo_competencia": {"modo": "delete_copy_legado", "colunas": {}}},
        "nao_publicar": {"razao_social": {"publicar": False}} if nao_publicar else {},
    }
    caminho = tmp_path / "allowlist.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def test_aprovadas_em_ordem(tmp_path):
    con = _con()
    assert colunas_aprovadas(con, "gold_x", _escrever(tmp_path, con)) == ["a", "b"]


def test_tabela_fora_da_allowlist(tmp_path):
    con = _con()
    with pytest.raises(AllowlistRecusada, match="gold_y"):
        colunas_aprovadas(con, "gold_y", _escrever(tmp_path, con))


def test_tabela_excluida(tmp_path):
    con = _con()
    with pytest.raises(AllowlistRecusada, match="gold_resumo_competencia.*fora da troca"):
        colunas_aprovadas(con, "gold_resumo_competencia", _escrever(tmp_path, con))


def test_coluna_nao_aprovada_fica_fora(tmp_path):
    con = _con()
    assert colunas_aprovadas(con, "gold_x", _escrever(tmp_path, con, aprovadas=("b",))) == ["b"]


def test_unica_coluna_nao_aprovada_recusa(tmp_path):
    con = _con()
    with pytest.raises(AllowlistRecusada, match="gold_x"):
        colunas_aprovadas(con, "gold_x", _escrever(tmp_path, con, aprovadas=()))


def test_sem_assinatura(tmp_path):
    con = _con()
    with pytest.raises(AllowlistRecusada, match="assinatura"):
        colunas_aprovadas(con, "gold_x", _escrever(tmp_path, con, assinar=False))


def test_hash_divergente_apos_coluna_nova(tmp_path):
    con = _con()
    caminho = _escrever(tmp_path, con)
    con.execute("ALTER TABLE gold.gold_x ADD COLUMN nova VARCHAR")
    with pytest.raises(AllowlistRecusada, match="hash"):
        colunas_aprovadas(con, "gold_x", caminho)


@pytest.mark.parametrize("tipo", ["STRUCT(k INTEGER)", "INTEGER[]"])
def test_tipo_composto(tmp_path, tipo):
    con = _con(f"CREATE TABLE gold.gold_x (a VARCHAR, b {tipo})")
    with pytest.raises(AllowlistRecusada, match="gold_x.b"):
        colunas_aprovadas(con, "gold_x", _escrever(tmp_path, con))


def test_razao_social_aprovada_recusa(tmp_path):
    con = _con()
    caminho = _escrever(tmp_path, con, aprovadas=("a", "razao_social"))
    with pytest.raises(AllowlistRecusada, match="gold_x.razao_social"):
        colunas_aprovadas(con, "gold_x", caminho)


def test_template_versionado_sem_aprovadas():
    dados = json.loads(allowlist.ALLOWLIST.read_text(encoding="utf-8"))
    cols = [c for t in dados["tabelas"].values() for c in t["colunas"].values()]
    cols += [c for t in dados["excluidas"].values() for c in (t["colunas"].values() if isinstance(t["colunas"], dict) else [])]
    assert all(c["aprovado"] is not True for c in cols)
    assert dados["assinatura"] == {"por": "", "em": ""}
