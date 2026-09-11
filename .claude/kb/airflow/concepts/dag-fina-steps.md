# DAG fina sobre `pipeline.steps`

**Regra:** a DAG só orquestra. Toda lógica (descobrir, baixar, carregar, dbt, qualidade, publicar, arquivar) vive em `pipeline/steps.py`, testável sem Airflow e executável por `python -m pipeline.run`.

Por quê:
- testes de ponta a ponta rodam sem scheduler (e2e em `tests/test_e2e.py`);
- o parse da DAG não importa duckdb/psycopg (import dentro da `@task`);
- a mesma sequência vale para Airflow, CLI e testes — um só comportamento.

`@step` (decorador em `steps.py`) converte `PipelineFailure` em incidente `origin='pipeline'` + status `falhou`, e relança para o Airflow marcar a tarefa como falha.
