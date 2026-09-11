"""AC-8: histórico mensal em Parquet (arquivo, retenção e diferença entre competências)."""

from __future__ import annotations

import random
import shutil

import pytest

from chaos.failures import _fields, _join, _mutate, _read, _write
from chaos.sample import generate
from intelligence.intents import diferenca_competencias
from pipeline import history, steps
from pipeline.config import get_settings


def _processa(comp: str) -> None:
    steps.discover(comp)
    steps.download(comp)
    steps.load_raw(comp)
    for sel in steps.DBT_LAYERS:
        steps.transform(comp, sel)
    steps.check_quality(comp)
    steps.archive_history(comp)
    steps.finish(comp)


@pytest.fixture(scope="module")
def dois_meses(pg):
    s = get_settings()
    for comp in ("2026-05", "2026-06"):
        shutil.rmtree(s.landing_dir / comp, ignore_errors=True)
        generate(comp, s.landing_dir, 600, seed=11)
    landing = s.landing_dir / "2026-06"
    rng = random.Random(3)

    def baixa(f: list[str]) -> list[str]:
        f[5], f[7] = "08", "01"  # estabelecimento baixado no mês seguinte
        return f

    _mutate(landing, "Estabelecimentos1.zip", 10, baixa, rng)
    member, lines = _read(landing / "Socios0.zip")
    novo = _fields(lines[0])
    novo[2] = "SOCIO NOVO DA SILVA"
    _write(landing / "Socios0.zip", member, [*lines, _join(novo)])
    for comp in ("2026-05", "2026-06"):
        _processa(comp)
    return novo[0]


def test_particoes_arquivadas(dois_meses):
    assert {"2026-05", "2026-06"} <= set(history.arquivadas())
    for ent in history.ENTIDADES:
        assert (history.partition("2026-06") / f"{ent}.parquet").exists()


def test_diferenca_mostra_baixas_e_socio_novo(dois_meses):
    d = diferenca_competencias("2026-05", "2026-06")
    assert any(m["situacao_atual"] == "08" for m in d["mudancas_situacao"])
    assert any(x["nome_socio"] == "SOCIO NOVO DA SILVA" for x in d["socios_entraram"])
    so_empresa = diferenca_competencias("2026-05", "2026-06", cnpj_basico=dois_meses)
    assert all(x["cnpj_basico"] == dois_meses for x in so_empresa["socios_entraram"])


def test_retencao_mantem_12(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        for m in range(1, 15):
            (history.partition(f"2025-{m:02d}" if m <= 12 else f"2026-{m - 12:02d}")).mkdir(parents=True)
        removidas = history.apply_retention(12)
        assert removidas == ["2025-01", "2025-02"]
        assert len(history.arquivadas()) == 12
    finally:
        get_settings.cache_clear()
