"""Endurecimento do Passo 4: escritor único (O5), teto de memória (O6), retenção do landing (G6)."""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from pipeline import steps, warehouse
from pipeline.config import get_settings


def test_teto_de_memoria_reduz_nunca_aumenta():
    oito = 8 * 1024**3
    assert warehouse.effective_memory_limit("4GB", available=oito) == "4GB"        # 50%: mantém
    assert warehouse.effective_memory_limit("8GB", available=oito) == "4915MB"     # 100% -> 60%


def test_parse_size():
    assert warehouse.parse_size("1.5GB") == int(1.5 * 1024**3)
    assert warehouse.parse_size("512MB") == 512 * 1024**2
    with pytest.raises(ValueError):
        warehouse.parse_size("muito")


def test_segundo_escritor_recebe_mensagem_clara(data_dir):
    path = get_settings().warehouse_path
    holder = subprocess.Popen(
        [sys.executable, "-c", f"import duckdb,time; c=duckdb.connect(r'{path}'); print('ok', flush=True); "
                               "time.sleep(20)"], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "ok"
        with pytest.raises(warehouse.WarehouseBusyError, match="único escritor"):
            warehouse.connect_rw()
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.2)
    warehouse.connect_rw().close()  # liberado, volta a abrir


def test_retencao_do_landing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        for c in ("2026-05", "2026-06", "2026-07", "2026-08"):
            (get_settings().landing_dir / c).mkdir(parents=True)
        assert steps.cleanup_landing("2026-08") == ["2026-05", "2026-06"]
        assert sorted(p.name for p in get_settings().landing_dir.iterdir()) == ["2026-07", "2026-08"]
    finally:
        get_settings.cache_clear()
