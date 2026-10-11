"""ops.runs (T-010): SQL, gravação pelo cursor da transação do swap e ausência de valores de dados."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

from pipeline.bi import runs

RAIZ = Path(__file__).resolve().parents[1]
SQL = (RAIZ / "sql" / "002_ops_runs.sql").read_text(encoding="utf-8")
PUBLICAR = (RAIZ / "pipeline" / "bi" / "publicar.py").read_text(encoding="utf-8")
RUNS = (RAIZ / "pipeline" / "bi" / "runs.py").read_text(encoding="utf-8")


class CursorFalso:
    """Simula uma transação: o que foi gravado só vira definitivo no commit."""

    def __init__(self):
        self.pendente: list[tuple] = []
        self.confirmado: list[tuple] = []

    def execute(self, sql, params=()):
        assert "ops.runs" in sql
        chave = tuple(params[:2])
        if all(chave != tuple(p[:2]) for p in self.pendente + self.confirmado):  # ON CONFLICT DO NOTHING
            self.pendente.append(tuple(params))

    def commit(self):
        self.confirmado += self.pendente
        self.pendente = []

    def rollback(self):
        self.pendente = []


def test_chave_unica():
    assert "ops.runs" in SQL
    assert re.search(r"\b(UNIQUE|PRIMARY\s+KEY)\s*\(", SQL, re.IGNORECASE)


def test_grava_metadados_no_commit():
    cur = CursorFalso()
    runs.gravar(cur, "t", 10, 25, 7, "abc", run_id="r1")
    cur.commit()
    assert cur.confirmado == [("t", "r1", 10, 25, 7, "abc", None)]


def test_rollback_sem_linha_de_sucesso():
    cur = CursorFalso()
    runs.gravar(cur, "t", 10, 25, 7, "abc", run_id="r1")
    cur.rollback()
    assert cur.confirmado == []


def test_retry_nao_duplica():
    cur = CursorFalso()
    for _ in range(2):
        runs.gravar(cur, "t", 10, 25, 7, "abc", run_id="r1")
        cur.commit()
    assert len(cur.confirmado) == 1
    assert "ON CONFLICT (tabela, run_id) DO NOTHING" in runs.SQL_GRAVAR


def test_gravacao_na_transacao_do_swap():
    swap = PUBLICAR.index("RENAME TO")
    grava = PUBLICAR.index("runs.gravar(")
    fim = PUBLICAR.index("log.info(\"publicado")
    assert swap < grava < fim
    assert "psycopg.connect" not in RUNS


def test_menor_n_e_hash(tmp_path):
    con = duckdb.connect()
    con.execute("CREATE SCHEMA gold")
    con.execute("CREATE TABLE gold.t AS SELECT * FROM (VALUES ('a'),('a'),('a'),('b'),('b')) v(k)")
    assert runs.menor_n(con, "t", ["k"]) == 2
    assert runs.menor_n(con, "t", []) is None
    arq = tmp_path / "al.json"
    arq.write_text("{}", encoding="utf-8")
    assert len(runs.hash_allowlist(arq)) == 64
    assert runs.hash_allowlist(tmp_path / "nao_existe.json") is None


def test_menor_n_nao_vaza_valores_no_erro():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA gold")
    con.execute("CREATE TABLE gold.t AS SELECT 'segredo' AS k")
    assert runs.menor_n(con, "t", ["inexistente"]) is None


def test_sem_logs_de_valores():
    assert "log" not in RUNS.lower().replace("allowlist", "")
    assert "print(" not in RUNS
