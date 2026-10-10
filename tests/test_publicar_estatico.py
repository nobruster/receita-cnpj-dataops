"""Checagens estáticas do publicador (sem Postgres): leem o código-fonte."""
from __future__ import annotations

from pathlib import Path

CODIGO = (Path(__file__).resolve().parents[1] / "pipeline" / "bi" / "publicar.py").read_text(encoding="utf-8")


def test_sem_select_estrela():
    assert "SELECT *" not in CODIGO


def test_sem_csv():
    assert "csv" not in CODIGO.lower()


def test_drop_if_exists():
    assert "DROP TABLE IF EXISTS" in CODIGO


def test_grant_select():
    assert "GRANT SELECT" in CODIGO


def test_lock_timeout():
    assert "lock_timeout" in CODIGO


def test_history_tables():
    assert "HISTORY_TABLES" in CODIGO


def test_antes_do_rename():
    assert "antes_do_rename" in CODIGO
