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
import shutil
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from pipeline import history, ops, publish, quality
from pipeline.config import get_settings
from pipeline.errors import DbtFailure, PipelineFailure, SourceUnavailableError, failure_line, setup_logging
from pipeline.receita import loader, webdav
from pipeline.receita.layout import validate_competencia
from pipeline.warehouse import WarehouseBusyError, connect_rw, effective_memory_limit

log = logging.getLogger("pipeline.steps")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = PROJECT_ROOT / "transform"
# Uma camada por tarefa (visibilidade no Airflow). Seeds de domínio vão junto do bronze.
# O teste singular no_reject_leaks_to_gold (AC-4) tem pais em silver E gold: vai explícito no gold,
# senão a seleção indireta "cautious" o descarta (achado 13 do reviewer).
DBT_LAYERS: tuple[str, ...] = ("resource_type:seed bronze", "silver", "gold no_reject_leaks_to_gold")


def _now() -> datetime:
    return datetime.now(UTC)


def step[F: Callable[..., Any]](fn: F) -> F:
    """Registra falhas de pipeline como incidentes e marca a competência."""

    @wraps(fn)
    def wrapper(competencia: str, *args: Any, **kwargs: Any) -> Any:
        setup_logging(get_settings().logs_dir)
        try:
            return fn(competencia, *args, **kwargs)
        except Exception as exc:
            # Toda falha vira incidente + status final (achado 6 do reviewer): nada fica
            # "baixando"/"transformada" para sempre, e o Sentinel enxerga o caso.
            if isinstance(exc, PipelineFailure):
                key, surface = exc.key, "dbt_run_results" if isinstance(exc, DbtFailure) else "pipeline_logs"
            else:
                key = "warehouse_busy" if isinstance(exc, WarehouseBusyError) else "pipeline_error"
                surface = "pipeline_logs"
                log.error(failure_line(key, competencia=competencia, etapa=fn.__name__, erro=type(exc).__name__))
            ops.open_incident_once(key, "pipeline", competencia, f"{fn.__name__}: {exc}"[:2000], surface)
            ops.set_status(competencia, "falhou", f"{fn.__name__}: {exc}"[:500])
            raise

    return wrapper  # type: ignore[return-value]


def discover(force: str | None = None) -> dict[str, Any]:
    """Qual competência processar? A forçada, ou a última publicada ainda não concluída.

    Fonte fora do ar vira incidente ``source_unavailable`` (pseudo-competência
    ``fonte``) e a tarefa falha; publicação atrasada vira ``stale_release``, uma vez
    por competência (AC-7). A hora da detecção é a âncora do AC-3.
    """
    s = get_settings()
    setup_logging(s.logs_dir)
    ops.ensure_schema()
    if force:
        comp = validate_competencia(force)
        feito = ops.last_processed()
        if feito and comp < feito:
            # Reprocessar um mês antigo faria o gold e o Postgres regredirem (achado 8 do reviewer).
            raise ValueError(f"{comp} é anterior à última competência processada ({feito}). "
                             "Meses antigos ficam no histórico Parquet (diferenca_competencias).")
        ops.mark_detected(comp, reset=True)
        return {"competencia": comp, "skip": False, "motivo": "forçada por parâmetro"}
    if s.offline_mode:
        locais = sorted(p.name for p in s.landing_dir.glob("????-??") if p.is_dir())
        if not locais:
            raise RuntimeError(f"modo offline e nenhuma competência em {s.landing_dir}")
        comp = locais[-1]
    else:
        try:
            comp = webdav.latest_competencia(s)
        except Exception as exc:  # rede, TLS, 4xx/5xx, XML inválido, pasta vazia
            err = SourceUnavailableError(f"fonte da Receita indisponível: {exc}", url=s.rfb_webdav_url)
            log.error(err.contract_line())
            ops.open_incident_once(err.key, "pipeline", ops.FONTE, str(err), "pipeline_logs")
            ops.set_status(ops.FONTE, "falhou", str(err)[:500])
            raise err from exc
        _check_stale(comp, s.dq_stale_days)
    feito = ops.last_processed()
    if feito and comp <= feito:
        return {"competencia": comp, "skip": True, "motivo": f"{comp} já processada (última: {feito})"}
    ops.mark_detected(comp)
    return {"competencia": comp, "skip": False, "motivo": f"nova competência (última processada: {feito})"}


def _check_stale(latest: str, stale_days: int, today: date | None = None) -> bool:
    """Abre ``stale_release`` se a competência mais nova ficou velha demais (uma vez por competência)."""
    hoje = today or datetime.now(UTC).date()
    ano, mes = map(int, latest.split("-"))
    idade = (hoje - date(ano, mes, 1)).days
    if idade <= stale_days or ops.has_incident("stale_release", latest):
        return False
    msg = f"última competência publicada é {latest} ({idade} dias; limite {stale_days})"
    log.warning("DQ_FINDING key=stale_release %s", msg)
    ops.open_incident("stale_release", "monitor", latest, msg, "ops.competencias")
    return True


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
    ops.set_status(competencia, "carregando", "carga raw", processamento_iniciado_em=_now())
    landing = s.landing_dir / competencia
    con = connect_rw(s)
    try:
        loads = loader.load_all(con, landing, s.work_dir / competencia, competencia)
    finally:
        con.close()
    ops.set_status(competencia, "carregada", f"{sum(x.linhas for x in loads):,} linhas raw")
    return {"linhas": sum(x.linhas for x in loads), "erros_parse": sum(x.erros_parse for x in loads)}


def dbt(competencia: str, select: str) -> None:
    """``dbt build --select <select>`` com a competência como var.

    Usa o mesmo teto de memória das conexões Python (achado 5) e, se um leitor segurar o
    DuckDB, espera e tenta de novo em vez de falhar a tarefa (achado 2). Falha real vira
    :class:`DbtFailure` (o ``@step`` registra incidente e status).
    """
    s = get_settings()
    env = {
        **os.environ,
        "DUCKDB_DATABASE": str(s.warehouse_path),
        "DUCKDB_MEMORY_LIMIT": effective_memory_limit(s.duckdb_memory_limit),
        "DUCKDB_THREADS": str(s.duckdb_threads),
        "DBT_TARGET_PATH": os.environ.get("DBT_TARGET_PATH", str(s.data_dir / "dbt" / "target")),
        "DBT_LOG_PATH": os.environ.get("DBT_LOG_PATH", str(s.data_dir / "dbt" / "logs")),
        # testes só rodam quando TODOS os pais estão na seleção (evita testar gold antes de existir)
        "DBT_INDIRECT_SELECTION": "cautious",
    }
    cmd = [os.environ.get("DBT_BIN", "dbt"), "build", "--project-dir", str(DBT_DIR), "--profiles-dir",
           str(DBT_DIR / "profiles"), "--select", select, "--vars", f"{{competencia: '{competencia}'}}"]
    inicio = time.monotonic()
    while True:
        log.info("executando: %s", " ".join(cmd))
        proc = subprocess.run(cmd, env=env, cwd=DBT_DIR, text=True, capture_output=True)
        print(proc.stdout[-20000:])
        if proc.returncode == 0:
            return
        saida = proc.stdout + proc.stderr
        if "Could not set lock" in saida and time.monotonic() - inicio < s.duckdb_lock_wait_s:
            log.info("dbt: warehouse ocupado por um leitor; nova tentativa em 10s")
            time.sleep(10)
            continue
        print(proc.stderr[-5000:])
        err = DbtFailure(f"dbt build --select {select} falhou (exit {proc.returncode})",
                         competencia=competencia, selecao=select.replace(" ", "+"))
        log.error(err.contract_line())
        raise err


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
def archive_history(competencia: str) -> dict[str, Any]:
    """AC-8: foto Parquet do silver aceito + retenção de 12 competências."""
    con = connect_rw()
    try:
        linhas = history.archive(con, competencia)
    finally:
        con.close()
    return {"linhas": linhas, "removidas": history.apply_retention()}


@step
def publish_postgres(competencia: str) -> dict[str, int]:
    s = get_settings()
    if not s.publish_enabled:
        return {}
    tabelas = [t.strip() for t in s.publish_tables.split(",") if t.strip()]
    con = connect_rw(s)
    try:
        return publish.publish_all(con, tabelas, competencia, s)
    finally:
        con.close()


def cleanup_landing(competencia: str) -> list[str]:
    """Mantém só as ``landing_retention`` competências mais recentes de zips (nunca a atual)."""
    s = get_settings()
    comps = sorted(p.name for p in s.landing_dir.glob("????-??") if p.is_dir())
    manter = set(comps[-max(1, s.landing_retention):]) | {competencia}
    removidas = []
    for c in comps:
        if c not in manter:
            shutil.rmtree(s.landing_dir / c, ignore_errors=True)
            removidas.append(c)
    shutil.rmtree(s.work_dir / competencia, ignore_errors=True)  # CSVs temporários da carga
    if removidas:
        log.info("landing: removidas %s (retenção de %d)", removidas, s.landing_retention)
    return removidas


def finish(competencia: str) -> None:
    ops.set_status(competencia, "publicada", "pipeline concluído", finalizado_em=_now())
