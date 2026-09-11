# Airflow 3.3.1 + pipeline (DuckDB/httpx/psycopg) + dbt-duckdb em venv isolado.
FROM apache/airflow:3.3.1-python3.12

ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.12
ENV CONSTRAINTS=https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt

COPY requirements/airflow.txt requirements/dbt.txt /tmp/req/

# Pacotes do pipeline respeitando as constraints (não atualiza o Airflow por acidente)
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/req/airflow.txt --constraint "${CONSTRAINTS}"

# dbt isolado: /opt/airflow/dbt-venv/bin/dbt
RUN python -m venv /opt/airflow/dbt-venv \
 && /opt/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/req/dbt.txt

ENV DBT_BIN=/opt/airflow/dbt-venv/bin/dbt \
    PYTHONPATH=/opt/airflow/project \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false
