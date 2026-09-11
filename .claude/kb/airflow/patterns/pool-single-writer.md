# Padrão: pool de 1 vaga para o DuckDB

DuckDB aceita **um processo escritor** por arquivo. No Airflow:
1. `airflow pools set duckdb_writer 1 "..."` (feito pelo serviço `airflow-setup`).
2. Toda `@task` que chama `connect_rw()` recebe `pool="duckdb_writer"`.
3. `max_active_runs=1` na DAG.
4. Leitores (consultas, Sentinel, evals) usam `connect_ro()` por chamada e fecham logo — nunca seguram o arquivo.
5. Fora do Airflow (CLI), um segundo escritor recebe erro claro de `connect_rw` (trava de arquivo do DuckDB) — nunca corrompe.

Sintoma de pool faltando: tarefas presas em *scheduled*.
