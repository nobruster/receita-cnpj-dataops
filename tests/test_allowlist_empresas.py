from scripts import inventario_gold
from tests.test_inventario_gold import _Con

ROWS = [
    ("gold_x", "cnpj", "VARCHAR"),
    ("gold_x", "razao_social", "VARCHAR"),
    ("gold_resumo_competencia", "competencia", "VARCHAR"),
    ("gold_resumo_competencia", "total", "BIGINT"),
]


def _gerar():
    return inventario_gold.gerar(_Con(ROWS))


def test_negada_por_padrao():
    dados = _gerar()
    cols = [c for t in dados["tabelas"].values() for c in t["colunas"].values()]
    cols += list(dados["excluidas"]["gold_resumo_competencia"]["colunas"].values())
    assert cols
    assert all(c["aprovado"] is False and c["classe"] is None for c in cols)
    assert dados["assinatura"] == {"por": "", "em": ""}
    assert dados["esquema_hash"]


def test_delete_copy_legado():
    exc = _gerar()["excluidas"]["gold_resumo_competencia"]
    assert exc["modo"] == "delete_copy_legado"
    assert exc["motivo"]


def test_excluidas():
    dados = _gerar()
    assert "gold_resumo_competencia" not in dados["tabelas"]
    assert set(dados["excluidas"]["gold_resumo_competencia"]["colunas"]) == {"competencia", "total"}
    assert dados["nao_publicar"]["razao_social"]["publicar"] is False
