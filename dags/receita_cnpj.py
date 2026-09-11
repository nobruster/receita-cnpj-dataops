"""DAG mensal dos dados abertos do CNPJ (Airflow 3).

Roda todo dia às 06:00, mas só trabalha quando a Receita publica uma competência
nova: ``descobrir`` compara a última pasta do WebDAV com a última competência
concluída em ``ops.competencias`` e pula o resto da DAG se não houver novidade.
Para reprocessar um mês: *Trigger DAG w/ config* ``{"competencia": "2026-08"}``.

Toda tarefa que escreve no DuckDB usa o pool ``duckdb_writer`` (1 vaga): o
DuckDB aceita um único processo escritor. A lógica vive em ``pipeline.steps``
(testável sem Airflow); esta DAG só orquestra.

    descobrir → baixar → carregar_raw → dbt_bronze → dbt_silver → dbt_gold
              → qualidade → publicar_postgres → concluir
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.sdk import Asset, Param, dag, task
from airflow.sdk.exceptions import AirflowSkipException

GOLD = Asset("duckdb://warehouse/gold")
POOL = "duckdb_writer"


@dag(
    dag_id="receita_cnpj_mensal",
    description="Receita Federal CNPJ: WebDAV -> DuckDB (raw/bronze/silver/gold) -> PostgreSQL",
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "dados", "retries": 1, "retry_delay": timedelta(minutes=10)},
    params={
        "competencia": Param(None, type=["null", "string"], pattern=r"^\d{4}-\d{2}$",
                             description="AAAA-MM para forçar (vazio = última publicada)"),
    },
    tags=["receita", "cnpj", "duckdb", "dbt"],
    doc_md=__doc__,
)
def receita_cnpj_mensal():
    @task
    def descobrir(params=None) -> str:
        from pipeline import steps

        alvo = steps.discover((params or {}).get("competencia"))
        if alvo["skip"]:
            raise AirflowSkipException(alvo["motivo"])
        print(alvo["motivo"])
        return alvo["competencia"]

    @task(retries=3, retry_delay=timedelta(minutes=15), execution_timeout=timedelta(hours=8))
    def baixar(competencia: str) -> dict:
        from pipeline import steps

        return steps.download(competencia)

    @task(pool=POOL, execution_timeout=timedelta(hours=4))
    def carregar_raw(competencia: str) -> dict:
        from pipeline import steps

        return steps.load_raw(competencia)

    def dbt_task(layer: str, select: str):
        @task(task_id=f"dbt_{layer}", pool=POOL, execution_timeout=timedelta(hours=4))
        def _run(competencia: str) -> None:
            from pipeline import steps

            steps.transform(competencia, select)

        return _run

    @task(pool=POOL)
    def qualidade(competencia: str) -> list[int]:
        from pipeline import steps

        return steps.check_quality(competencia)

    @task(pool=POOL, execution_timeout=timedelta(hours=2))
    def publicar_postgres(competencia: str) -> dict:
        from pipeline import steps

        return steps.publish_postgres(competencia)

    @task(outlets=[GOLD])
    def concluir(competencia: str) -> str:
        from pipeline import steps

        steps.finish(competencia)
        return competencia

    comp = descobrir()
    raw = carregar_raw(comp)
    baixar(comp) >> raw
    bronze = dbt_task("bronze", "resource_type:seed bronze")(comp)
    silver = dbt_task("silver", "silver")(comp)
    gold = dbt_task("gold", "gold")(comp)
    dq = qualidade(comp)
    pub = publicar_postgres(comp)
    fim = concluir(comp)
    raw >> bronze >> silver >> gold >> dq >> pub >> fim


receita_cnpj_mensal()
