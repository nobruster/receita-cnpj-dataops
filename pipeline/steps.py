"""Passos do pipeline, independentes do orquestrador.

A DAG do Airflow só chama estas funções (fica fina e testável). O mesmo fluxo
roda sem Airflow com ``python -m pipeline.run`` — útil para testes e para a
primeira validação no Docker.

Toda ``PipelineFailure`` vira incidente ``origin='pipeline'`` e marca a
competência como ``falhou`` antes de ser relançada (o Airflow registra a falha).
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from pipeline import ops, publish, quality
from pipeline.config import get_settings
from pipeline.errors import PipelineFailure, setup_logging
from pipeline.receita import loader, webdav
from pipeline.receita.layout import validate_competencia
from pipeline.warehouse import connect_rw

log = logging.getLogger("pipeline.steps")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = PROJECT_ROOT / "transform"
# Uma camada por tarefa (visibilidade no Airflow). Seeds de domínio vão junto do bronze.
DBT_LAYERS: tuple[str, ...] = ("resource_type:seed bronze", "silver", "gold")


def _now() -> datetime:
    return datetime.now(UTC)


def step[F: Callable[..., Any]](fn: F) -> F:
    """Registra falhas de pipeline como incidentes e marca a competência."""

    @wraps(fn)
    def wrapper(competencia: str, *args: Any, **kwargs: Any) -> Any:
        setup_logging(get_settings().logs_dir)
        try:
            return fn(competencia, *args, **kwargs)
        except PipelineFailure as exc:
            ops.open_incident(exc.key, "pipeline", competencia, str(exc), "pipeline_logs")
            ops.set_status(competencia, "falhou", f"{fn.__name__}: {exc}")
            raise

    return wrapper  # type: ignore[return-value]


def discover(force: str | None = None) -> dict[str, Any]:
    """Qual competência processar? A forçada, ou a última publicada ainda não concluída."""
    s = get_settings()
    setup_logging(s.logs_dir)
    ops.ensure_schema()
    if force:
        comp = validate_competencia(force)
        return {"competencia": comp, "skip": False, "motivo": "forçada por parâmetro"}
    if s.offline_mode:
        locais = sorted(p.name for p in s.landing_dir.glob("????-??") if p.is_dir())
        if not locais:
            raise RuntimeError(f"modo offline e nenhuma competência em {s.landing_dir}")
        comp = locais[-1]
    else:
        comp = webdav.latest_competencia(s)
    feito = ops.last_processed()
    if feito and comp <= feito:
        return {"competencia": comp, "skip": True, "motivo": f"{comp} já processada (última: {feito})"}
    ops.set_status(comp, "descoberta", "nova competência publicada")
    return {"competencia": comp, "skip": False, "motivo": f"nova competência (última processada: {feito})"}


@step
def download(competencia: str) -> dict[str, Any]:
    s = get_settings()
    ops.set_status(competencia, "baixando", iniciado_em=_now())
    if s.offline_mode:
        loader.check_landing(s.landing_dir / competencia, competencia)
        ops.set_status(competencia, "baixada", "modo offline: zips já no landing")
        return {"arquivos": 37, "bytes": None, "offline": True}
    files = webdav.list_files(competencia, s)
    webdav.check_complete(competencia, files)
    dest = s.landing_dir / competencia
    with webdav._client(s) as client, ThreadPoolExecutor(max_workers=s.download_workers) as pool:
        futures = {pool.submit(webdav.download_file, competencia, f, dest, s, client): f for f in files}
        for fut in as_completed(futures):
            fut.result()
            log.info("baixado %s", futures[fut].name)
    webdav.write_manifest(competencia, files, dest)
    pub = webdav.published_at(files)
    total = sum(f.size for f in files)
    ops.set_status(competencia, "baixada", f"{len(files)} arquivos", bytes_total=total, publicada_em=pub)
    return {"arquivos": len(files), "bytes": total}


@step
def load_raw(competencia: str) -> dict[str, Any]:
    s = get_settings()
    landing = s.landing_dir / competencia
    con = connect_rw(s)
    try:
        loads = loader.load_all(con, landing, s.work_dir / competencia, competencia)
    finally:
        con.close()
    ops.set_status(competencia, "carregada", f"{sum(x.linhas for x in loads):,} linhas raw")
    return {"linhas": sum(x.linhas for x in loads), "erros_parse": sum(x.erros_parse for x in loads)}


def dbt(competencia: str, select: str) -> None:
    """``dbt build --select <select>`` com a competência como var."""
    s = get_settings()
    env = {
        **os.environ,
        "DUCKDB_DATABASE": str(s.warehouse_path),
        "DUCKDB_MEMORY_LIMIT": s.duckdb_memory_limit,
        "DUCKDB_THREADS": str(s.duckdb_threads),
        "DBT_TARGET_PATH": os.environ.get("DBT_TARGET_PATH", str(s.data_dir / "dbt" / "target")),
        "DBT_LOG_PATH": os.environ.get("DBT_LOG_PATH", str(s.data_dir / "dbt" / "logs")),
        # testes só rodam quando TODOS os pais estão na seleção (evita testar gold antes de existir)
        "DBT_INDIRECT_SELECTION": "cautious",
    }
    cmd = [os.environ.get("DBT_BIN", "dbt"), "build", "--project-dir", str(DBT_DIR), "--profiles-dir",
           str(DBT_DIR / "profiles"), "--select", select, "--vars", f"{{competencia: '{competencia}'}}"]
    log.info("executando: %s", " ".join(cmd))
    proc = subprocess.run(cmd, env=env, cwd=DBT_DIR, text=True, capture_output=True)
    print(proc.stdout[-20000:])
    if proc.returncode != 0:
        print(proc.stderr[-5000:])
        ops.set_status(competencia, "falhou", f"dbt build --select {select} (exit {proc.returncode})")
        raise RuntimeError(f"dbt build --select {select} falhou (exit {proc.returncode})")


@step
def transform(competencia: str, select: str) -> None:
    dbt(competencia, select)
    ops.set_status(competencia, "transformada", f"dbt {select} ok")


@step
def check_quality(competencia: str) -> list[int]:
    con = connect_rw()
    try:
        ids = quality.run(con, competencia)
    finally:
        con.close()
    return ids


@step
def publish_postgres(competencia: str) -> dict[str, int]:
    s = get_settings()
    if not s.publish_enabled:
        return {}
    con = connect_rw(s)
    try:
        return {t: publish.publish_table(con, t.strip(), competencia, s)
                for t in s.publish_tables.split(",") if t.strip()}
    finally:
        con.close()


def finish(competencia: str) -> None:
    ops.set_status(competencia, "publicada", "pipeline concluído", finalizado_em=_now())
