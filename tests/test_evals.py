"""AC-6 (reprocessamento idêntico) e rótulos do relatório de evals."""

from __future__ import annotations

import shutil

import pytest

from chaos.failures import _read, _write
from chaos.sample import generate
from pipeline import evals, steps
from pipeline.config import get_settings

COMP = "2027-01"


@pytest.fixture(scope="module")
def processada(pg):
    s = get_settings()
    shutil.rmtree(s.landing_dir / COMP, ignore_errors=True)
    generate(COMP, s.landing_dir, 500, seed=5)
    steps.discover(COMP)
    steps.download(COMP)
    steps.load_raw(COMP)
    for sel in steps.DBT_LAYERS:
        steps.transform(COMP, sel)
    steps.check_quality(COMP)
    steps.archive_history(COMP)
    steps.finish(COMP)
    return COMP


def test_reprocessar_da_contagens_identicas(processada):
    ac, verdict, medido, _ = evals.reprocessar(processada)
    assert ac.startswith("AC-6") and verdict == "PASS", medido


def test_reprocessar_detecta_diferenca(processada):
    landing = get_settings().landing_dir / processada
    member, lines = _read(landing / "Empresas0.zip")
    _write(landing / "Empresas0.zip", member, lines[: len(lines) // 2])  # a "mesma" competência mudou
    ac, verdict, medido, _ = evals.reprocessar(processada)
    assert verdict == "FAIL" and "diferentes" in medido


def test_relatorio_usa_rotulos_do_brief(processada):
    rotulos = [r[0] for r in evals.run(processada)]
    assert any(r.startswith("F2-1") for r in rotulos)
    assert not any(r.startswith("AC-6 Sentinel") for r in rotulos)
    assert any(r.startswith("AC-8") for r in rotulos)
