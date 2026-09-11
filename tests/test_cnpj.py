"""O DV do CNPJ (numérico e alfanumérico) em Python e na macro dbt precisam concordar."""

import random
import string

import duckdb
import pytest
from jinja2 import Environment

from pipeline.receita import cnpj
from tests.conftest import ROOT


@pytest.mark.parametrize("valor", ["11.222.333/0001-81", "11222333000181", "12.ABC.345/01DE-35"])
def test_cnpjs_conhecidos_sao_validos(valor):
    assert cnpj.is_valid(valor)


def test_dv_errado_e_invalido():
    assert not cnpj.is_valid("11222333000180")
    assert not cnpj.is_valid("123")


def test_formatacao():
    assert cnpj.format_cnpj("12ABC34501DE35") == "12.ABC.345/01DE-35"


def _macro_sql() -> str:
    src = (ROOT / "transform" / "macros" / "receita.sql").read_text(encoding="utf-8")
    env = Environment()
    mod = env.from_string(src).module
    return str(mod.cnpj_dv("b"))


def test_macro_dbt_concorda_com_python():
    rng = random.Random(1)
    bases = [f"{rng.randrange(10**11, 10**12)}" for _ in range(200)]
    bases += ["".join(rng.choice(string.digits + string.ascii_uppercase) for _ in range(12)) for _ in range(200)]
    con = duckdb.connect()
    con.execute("CREATE TABLE t (b VARCHAR)")
    con.executemany("INSERT INTO t VALUES (?)", [[b] for b in bases])
    got = dict(con.execute(f"SELECT b, {_macro_sql()} FROM t").fetchall())
    for b in bases:
        assert got[b] == cnpj.dv(b), b
