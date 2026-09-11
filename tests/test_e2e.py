"""Ponta a ponta: amostra -> raw -> dbt -> monitores -> Sentinel -> nota (AC-4 e AC-6).

Para CADA falha do registro (e para a cascata): regenera a competência limpa (R7),
injeta, roda o pipeline, deixa o Sentinel diagnosticar pelo caminho determinístico
e pontua contra a verdade de referência. Prova a FIAÇÃO de ponta a ponta; a nota
de um LLM de verdade é medida à parte (``python -m sentinel.trigger`` com chave).
"""

from __future__ import annotations

import shutil

import pytest

from chaos.cli import inject
from chaos.failures import CASCADE_KEY, FAILURES
from chaos.sample import generate
from pipeline import ops, steps
from pipeline.config import get_settings
from pipeline.errors import PipelineFailure
from pipeline.warehouse import connect_ro
from sentinel.trigger import run_case

EMPRESAS = 1200


def _run_pipeline(comp: str) -> None:
    try:
        steps.discover(comp)
        steps.download(comp)
        steps.load_raw(comp)
        for sel in steps.DBT_LAYERS:
            steps.transform(comp, sel)
        steps.check_quality(comp)
        steps.finish(comp)
    except PipelineFailure:
        pass  # já virou incidente origin='pipeline' e status 'falhou'


def _fresh(comp: str) -> None:
    s = get_settings()
    shutil.rmtree(s.landing_dir / comp, ignore_errors=True)
    generate(comp, s.landing_dir, EMPRESAS, seed=42)


@pytest.fixture(scope="module")
def baseline(pg):
    _fresh("2026-07")
    _run_pipeline("2026-07")
    return "2026-07"


def test_baseline_limpa_sem_incidentes(baseline):
    with ops.session() as conn:
        n = conn.execute("SELECT count(*) AS n FROM ops.incidents").fetchone()["n"]
    assert n == 0, "amostra limpa (com defeitos CONHECIDOS da fonte) não pode abrir incidente"
    con = connect_ro()
    try:
        rej = sum(con.execute(f"SELECT count(*) FROM silver.silver_{e}_rejects").fetchone()[0]
                  for e in ("empresas", "estabelecimentos", "socios", "simples"))
        gold = con.execute("SELECT count(*) FROM gold.gold_empresa_detalhe").fetchone()[0]
        alfa = con.execute("SELECT count(*) FROM gold.gold_empresa_detalhe WHERE regexp_matches(cnpj,'[A-Z]')"
                           ).fetchone()[0]
    finally:
        con.close()
    assert rej == 0 and gold > EMPRESAS and alfa > 0
    assert ops.last_processed() == "2026-07"


@pytest.mark.parametrize("key", [*FAILURES, CASCADE_KEY])
def test_injetar_detectar_pontuar(baseline, key):
    comp = "2026-08"
    _fresh(comp)
    inject(key, comp)
    _run_pipeline(comp)
    res = run_case(comp)
    assert res.score.match == 1.0, (key, res.route, res.observed, res.score)
    if key in FAILURES and FAILURES[key].detected_by != "log_analyst":
        con = connect_ro()
        try:  # AC-4: nada quarentenado vaza para o gold
            vaz = con.execute(
                "SELECT count(*) FROM gold.gold_empresa_detalhe g JOIN silver.silver_estabelecimentos_rejects r "
                "ON r.cnpj = g.cnpj AND r.reject_rule <> 'duplicate_key'").fetchone()[0]
        finally:
            con.close()
        assert vaz == 0
