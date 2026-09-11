#!/bin/bash
# Cria os dois bancos: metadado do Airflow e o banco da plataforma (ops + gold publicado).
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
  CREATE USER airflow WITH PASSWORD '${AIRFLOW_DB_PASSWORD}';
  CREATE DATABASE airflow OWNER airflow;
  CREATE USER ${PG_USER} WITH PASSWORD '${PG_PASSWORD}';
  CREATE DATABASE ${PG_DB} OWNER ${PG_USER};
SQL
