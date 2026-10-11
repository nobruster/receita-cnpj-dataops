"""DAG diária que publica as tabelas aprovadas do gold no Postgres do BI (Airflow 3).

Uma tarefa só: chama ``pipeline.bi.publicar.publicar_todas`` com o DuckDB aberto em leitura
(``connect_ro``). A lógica fica em ``pipeline.bi`` (testável sem Airflow); esta DAG só orquestra.
A tarefa usa o pool ``duckdb_writer`` (1 vaga) para não concorrer com a DAG ``receita_cnpj_mensal``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import dag, task

POOL = "duckdb_writer"
TIMEZONE = ZoneInfo("America/Sao_Paulo")  # timezone explícito: o cron abaixo vale em horário de Brasília
RETRIES = 2
TIMEOUT = timedelta(hours=2)

log = logging.getLogger(__name__)


def registrar_falha(context: dict) -> None:
    """on_failure_callback: registra tarefa e motivo da falha, sem valores de dados."""
    erro = context.get("exception")
    ti = context.get("task_instance")
    motivo = type(erro).__name__
    if isinstance(erro, RuntimeError):  # mensagem do publicador lista só nomes de tabela
        motivo = f"{motivo}: {erro}"
    log.error("publicação do BI falhou: tarefa=%s motivo=%s", getattr(ti, "task_id", "?"), motivo)


@dag(
    dag_id="publicar_gold_bi",
    description="DuckDB gold (allowlist aprovada) -> PostgreSQL do BI",
    schedule="0 7 * * *",
    start_date=datetime(2026, 1, 1, tzinfo=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    tags=["bi", "gold", "postgres"],
    doc_md=__doc__,
)
def publicar_gold_bi():
    @task(
        pool=POOL,
        retries=RETRIES,
        retry_delay=timedelta(minutes=10),
        execution_timeout=TIMEOUT,
        on_failure_callback=registrar_falha,
    )
    def publicar() -> int:
        from pipeline.bi import publicar as bi
        from pipeline.config import get_settings
        from pipeline.warehouse import connect_ro

        settings = get_settings()
        con = connect_ro(settings)
        try:
            return len(bi.publicar_todas(con, settings=settings))
        finally:
            con.close()

    publicar()


publicar_gold_bi()
