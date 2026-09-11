"""AC-7 (fonte fora do ar, publicação atrasada) e âncoras de tempo do AC-2/AC-3."""

from __future__ import annotations

from datetime import date

import pytest

from pipeline import ops, steps
from pipeline.config import get_settings
from pipeline.errors import SourceUnavailableError


@pytest.fixture
def fonte_fora_do_ar(pg, monkeypatch):
    monkeypatch.setenv("OFFLINE_MODE", "false")
    monkeypatch.setenv("RFB_WEBDAV_URL", "http://127.0.0.1:9/public.php/webdav")
    monkeypatch.setenv("RFB_CONNECT_TIMEOUT", "2")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_fonte_indisponivel_vira_incidente(fonte_fora_do_ar):
    with pytest.raises(SourceUnavailableError):
        steps.discover()
    assert ops.has_incident("source_unavailable", ops.FONTE)
    with ops.session() as conn:
        st = conn.execute("SELECT status FROM ops.competencias WHERE competencia = %s", [ops.FONTE]).fetchone()
    assert st["status"] == "falhou"
    log = (get_settings().logs_dir / "pipeline.log").read_text(encoding="utf-8")
    assert "PIPELINE_FAILURE key=source_unavailable" in log


def test_publicacao_atrasada_uma_vez_por_competencia(pg):
    assert steps._check_stale("2026-01", 45, today=date(2026, 9, 11)) is True
    assert steps._check_stale("2026-01", 45, today=date(2026, 9, 12)) is False  # não duplica
    assert steps._check_stale("2026-09", 45, today=date(2026, 9, 11)) is False  # dentro do prazo


def test_deteccao_guarda_a_primeira_hora(pg):
    ops.mark_detected("2031-01")
    with ops.session() as conn:
        t1 = conn.execute("SELECT detectado_em FROM ops.competencias WHERE competencia='2031-01'").fetchone()
        ops.mark_detected("2031-01")
        t2 = conn.execute("SELECT detectado_em FROM ops.competencias WHERE competencia='2031-01'").fetchone()
        conn.execute("DELETE FROM ops.competencias WHERE competencia='2031-01'")
    assert t1["detectado_em"] is not None and t1 == t2


def test_ultima_processada_ignora_pseudo_competencia(pg):
    ops.set_status(ops.FONTE, "publicada", "nunca deveria contar")
    try:
        assert ops.last_processed() != ops.FONTE
    finally:
        ops.set_status(ops.FONTE, "falhou", "restaurado")
