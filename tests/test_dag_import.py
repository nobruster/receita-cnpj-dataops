"""T-012: DAG diária do publicador (R-9, R-10). Lê dags/publicar_gold_bi.py por ast, sem Airflow.

Escrito manualmente (oráculo de autoria humana): o executor não cria arquivos congelados.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DAG = Path(__file__).resolve().parents[1] / "dags" / "publicar_gold_bi.py"
_SEM_VALOR = object()


def _arvore() -> ast.Module:
    return ast.parse(DAG.read_text(encoding="utf-8"))


def _constantes(arvore: ast.Module) -> dict[str, object]:
    out: dict[str, object] = {}
    for no in arvore.body:
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name):
                    out[alvo.id] = no.value.value
    return out


def _kw(arvore: ast.Module, nome: str) -> ast.expr | None:
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            for kw in no.keywords:
                if kw.arg == nome:
                    return kw.value
    return None


def _valor(arvore: ast.Module, nome: str):
    """Valor literal do argumento `nome`, resolvendo constantes do módulo. Falha se não conseguir."""
    expr = _kw(arvore, nome)
    if expr is None:
        pytest.fail(f"argumento {nome} ausente na DAG")
    if isinstance(expr, ast.Constant):
        return expr.value
    if isinstance(expr, ast.Name) and expr.id in _constantes(arvore):
        return _constantes(arvore)[expr.id]
    pytest.fail(f"não consegui resolver {nome} por ast (use literal ou constante do módulo)")


def test_on_failure_callback():
    assert _kw(_arvore(), "on_failure_callback") is not None, "falta on_failure_callback"


def test_pool_duckdb_writer():
    assert _valor(_arvore(), "pool") == "duckdb_writer"


def test_max_active_runs_1():
    assert _valor(_arvore(), "max_active_runs") == 1


def test_catchup_false():
    assert _valor(_arvore(), "catchup") is False


def test_retries_2():
    assert _valor(_arvore(), "retries") == 2


def test_execution_timeout_presente():
    assert _kw(_arvore(), "execution_timeout") is not None


def test_schedule_com_timezone():
    assert _kw(_arvore(), "schedule") is not None
    assert "timezone" in DAG.read_text(encoding="utf-8")
