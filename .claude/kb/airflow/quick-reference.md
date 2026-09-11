# Airflow 3 — referência rápida (validada neste repo com 3.3.1)

| Tema | Como fazemos | Fonte |
|---|---|---|
| Imports de autoria | `from airflow.sdk import dag, task, Param, Asset` · `from airflow.sdk.exceptions import AirflowSkipException` | verificado: `airflow dags test` OK em 3.3.1 |
| Pular o resto da DAG | `raise AirflowSkipException(motivo)` na primeira tarefa; as seguintes ficam *skipped* | `dags/receita_cnpj.py::descobrir` |
| Forçar competência | `params={"competencia": Param(None, type=["null","string"], pattern=...)}` + `@task def f(params=None)` | idem |
| Um escritor no DuckDB | `pool="duckdb_writer"` (1 vaga) em toda tarefa que escreve + `max_active_runs=1` | `airflow pools set duckdb_writer 1 ...` no `airflow-setup` |
| DAG fina | `@task` importa `pipeline.steps` **dentro** da função (parse leve do dag-processor) | boas práticas de parse |
| Executor | LocalExecutor; componentes: `api-server`, `scheduler`, `dag-processor` (+ `triggerer` se houver deferrable) | compose oficial 3.3.1 adaptado |
| Auth (UI) | `FabAuthManager` + `_AIRFLOW_WWW_USER_CREATE` no init | compose oficial |
| Execução das tarefas | `AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow-apiserver:8080/execution/` + `AIRFLOW__API_AUTH__JWT_SECRET` igual em todos os componentes | compose oficial |
| Teste local sem scheduler | `airflow dags test <dag_id>` (roda tudo em processo; SQLite serve) | usado no build |
| Constraints | `pip install "apache-airflow==3.3.1" -r req.txt --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.3.1/constraints-3.12.txt` | `docker/airflow/Dockerfile` |
| dbt | venv separado (`/opt/airflow/dbt-venv`) chamado por subprocess; **mesma versão do duckdb** do pipeline | ADR-0001 |

Armadilhas vistas: listener de Flow/handler com o mesmo nome do evento (CrewAI, não Airflow); `from __future__ import annotations` quebra validações que inspecionam anotações em runtime.
