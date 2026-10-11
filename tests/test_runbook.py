"""T-013: runbook de operação e corte (R-10). Confere o conteúdo de docs/runbook-publicacao-bi.md.

Escrito manualmente (oráculo de autoria humana): o executor não cria arquivos congelados.
"""

from __future__ import annotations

from pathlib import Path

RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "runbook-publicacao-bi.md"


def _texto() -> str:
    assert RUNBOOK.is_file(), "runbook ausente"
    return RUNBOOK.read_text(encoding="utf-8")


def test_reprocessar():
    assert "reprocessar" in _texto()


def test_list_import_errors():
    assert "list-import-errors" in _texto()


def test_publish_tables():
    assert "PUBLISH_TABLES=gold_resumo_competencia" in _texto()


def test_k_5():
    assert "k = 5" in _texto()
