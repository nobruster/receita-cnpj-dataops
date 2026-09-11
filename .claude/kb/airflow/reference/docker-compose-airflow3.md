# Referência: compose do Airflow 3 (LocalExecutor) usado aqui

Serviços: `postgres` (metadado + banco `cnpj`), `airflow-init` (root: diretórios, chown, migração, usuário), `airflow-setup` (uid 50000: pool + schema `ops`), `airflow-apiserver` (:8080), `airflow-scheduler`, `airflow-dag-processor`. Perfil `fase2`: `sentinel`, `mcp`. Perfil `ollama`.

Variáveis obrigatórias: `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`, `AIRFLOW__CORE__EXECUTION_API_SERVER_URL`, `AIRFLOW__API_AUTH__JWT_SECRET` (mesmo valor em todos), `AIRFLOW__CORE__AUTH_MANAGER` (FAB).

Volumes: `dags/`, `pipeline/` (ro), `transform/`, `intelligence/` (ro, consultas do AC-5), logs, `/data` (nomeado por padrão; bind mount no Windows é lento).
Base: `apache/airflow:3.3.1-python3.12` + constraints 3.3.1.
