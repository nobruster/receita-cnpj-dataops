"""Regressões dos achados do reviewer independente (gate dos closers, T-06)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pytest

from pipeline import ops, publish, steps
from pipeline.config import get_settings
from pipeline.warehouse import connect_ro, connect_rw


def test_leitura_sem_acesso_a_arquivos(data_dir):
    connect_rw().close()  # garante que o arquivo existe
    con = connect_ro()
    try:
        with pytest.raises(duckdb.Error):
            con.execute("SELECT * FROM read_text('/proc/self/environ')").fetchall()
        with pytest.raises(duckdb.Error):
            con.execute("SET enable_external_access = true")
    finally:
        con.close()


def test_llm_nao_alcanca_coluna_pessoal(data_dir):
    from intelligence.sql_guard import run_guarded_select
    from sentinel.tools.readers import PII_COLUMNS

    con = connect_rw()
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")
        con.execute("CREATE OR REPLACE TABLE gold.gold_pii_teste AS "
                    "SELECT '12345678' AS cnpj_basico, 'FULANO DE TAL' AS nome_socio, 'a@b.com' AS correio_eletronico")
    finally:
        con.close()
    try:
        for sql in ("SELECT g FROM gold.gold_pii_teste g", "SELECT to_json(g) FROM gold.gold_pii_teste g",
                    "SELECT * FROM gold.gold_pii_teste", "SELECT COLUMNS('.*') FROM gold.gold_pii_teste"):
            out = run_guarded_select(sql, deny_columns=PII_COLUMNS)
            assert "12345678" in out, out
            assert "FULANO" not in out and "a@b.com" not in out, (sql, out)
        assert "recusado" in run_guarded_select("SELECT nome_socio FROM gold.gold_pii_teste", deny_columns=PII_COLUMNS)
        assert "recusado" in run_guarded_select("SELECT * FROM cnpj.gold.gold_pii_teste", deny_columns=PII_COLUMNS)
    finally:
        con = connect_rw()
        con.execute("DROP TABLE gold.gold_pii_teste")
        con.close()


def test_falha_generica_vira_incidente_e_status_final(pg, monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(steps.loader, "load_all", quebra)
    with pytest.raises(RuntimeError):
        steps.load_raw("2031-02")
    assert ops.has_incident("pipeline_error", "2031-02")
    with ops.session() as conn:
        st = conn.execute("SELECT status FROM ops.competencias WHERE competencia='2031-02'").fetchone()
        conn.execute("DELETE FROM ops.competencias WHERE competencia='2031-02'")
    assert st["status"] == "falhou"


def test_forcar_competencia_antiga_e_recusado(pg):
    ops.set_status("2031-05", "publicada", "teste")
    try:
        with pytest.raises(ValueError, match="anterior"):
            steps.discover("2031-04")
    finally:
        with ops.session() as conn:
            conn.execute("DELETE FROM ops.competencias WHERE competencia LIKE '2031-%'")


def test_sentinel_nao_pega_caso_em_andamento(pg):
    from sentinel.trigger import pending_cases

    ops.set_status("2031-07", "publicada", "já concluída antes")
    ops.open_incident("invalid_cnpj", "chaos", "2031-07", "injetada depois da conclusão")
    try:
        assert "2031-07" not in pending_cases()  # a DAG ainda vai reprocessar
        ops.set_status("2031-07", "publicada", "reprocessada")
        assert "2031-07" in pending_cases()
    finally:
        with ops.session() as conn:
            conn.execute("DELETE FROM ops.incidents WHERE competencia='2031-07'")
            conn.execute("DELETE FROM ops.competencias WHERE competencia='2031-07'")


def test_monitor_nao_duplica_incidente(pg):
    a = ops.open_incident_once("volume_drop", "monitor", "2031-08", "x")
    b = ops.open_incident_once("volume_drop", "monitor", "2031-08", "x de novo")
    with ops.session() as conn:
        conn.execute("DELETE FROM ops.incidents WHERE competencia='2031-08'")
    assert a == b


def test_publicacao_em_uma_transacao_e_colunas_novas(pg, data_dir):
    con = connect_rw()
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")
        con.execute("CREATE OR REPLACE TABLE gold.gold_resumo_competencia AS SELECT '2031-09' AS competencia, 1 AS n")
        con.execute("CREATE OR REPLACE TABLE gold.gold_painel_prospeccao AS SELECT 'DF' AS uf, '5611201' "
                    "AS cnae_fiscal_principal, 3 AS ativos")
        publish.publish_all(con, ["gold_resumo_competencia", "gold_painel_prospeccao"], "2031-09")
        con.execute("CREATE OR REPLACE TABLE gold.gold_resumo_competencia AS "
                    "SELECT '2031-09' AS competencia, 2 AS n, 7 AS coluna_nova")
        rows = publish.publish_all(con, ["gold_resumo_competencia", "gold_painel_prospeccao"], "2031-09")
    finally:
        con.close()
    assert rows == {"gold_resumo_competencia": 1, "gold_painel_prospeccao": 1}
    with ops.session() as conn:
        r = conn.execute("SELECT n, coluna_nova FROM gold.gold_resumo_competencia WHERE competencia='2031-09'"
                         ).fetchone()
        conn.execute("DELETE FROM gold.gold_resumo_competencia WHERE competencia='2031-09'")
    assert r["n"] == 2 and r["coluna_nova"] == 7


def test_teste_de_vazamento_do_gold_roda_no_dbt(pg):
    """Depende do e2e ter rodado a camada gold nesta sessão (ordem dos arquivos de teste)."""
    rr = Path(os.environ.get("DBT_TARGET_PATH", str(get_settings().data_dir / "dbt" / "target"))) / "run_results.json"
    if not rr.exists():
        pytest.skip("dbt ainda não rodou nesta sessão")
    ids = [r["unique_id"] for r in json.loads(rr.read_text())["results"]]
    if not any(".gold_" in i for i in ids):
        pytest.skip("último dbt não foi a camada gold")
    assert any("no_reject_leaks_to_gold" in i for i in ids)
