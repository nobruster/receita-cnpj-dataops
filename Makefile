# Atalhos para Linux/WSL (no Windows puro use .\cnpj.ps1 — mesmos comandos).
.DEFAULT_GOAL := help
.PHONY: help up down status logs rodar amostra injetar falhas sentinel evals test lint

C ?= $(shell date +%Y-%m)
help: ## Lista os comandos
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'
up: ## Constrói e sobe tudo
	docker compose up -d --build
down: ## Para os containers
	docker compose down
status: ## Containers e competências
	docker compose ps
	docker compose exec -T postgres psql -U $${PG_USER:-cnpj} -d $${PG_DB:-cnpj} -c "SELECT * FROM ops.competencias ORDER BY 1 DESC LIMIT 5"
logs: ## Logs do scheduler
	docker compose logs -f --tail 200 airflow-scheduler
rodar: ## Dispara a DAG (COMP=AAAA-MM opcional)
	docker compose exec airflow-apiserver airflow dags unpause receita_cnpj_mensal
	docker compose exec airflow-apiserver airflow dags trigger receita_cnpj_mensal $(if $(COMP),--conf '{"competencia":"$(COMP)"}',)
amostra: ## Gera amostra sintética (COMP=AAAA-MM)
	docker compose run --rm sentinel python -m chaos.cli sample --competencia $(COMP)
injetar: ## Injeta falha (KEY=... COMP=AAAA-MM)
	docker compose run --rm sentinel python -m chaos.cli inject $(KEY) --competencia $(COMP)
falhas: ## Lista falhas injetáveis
	docker compose run --rm sentinel python -m chaos.cli list
sentinel: ## Roda o Sentinel agora
	docker compose exec sentinel python -m sentinel.trigger --once
evals: ## Mede os critérios de aceite
	docker compose exec mcp python -m pipeline.evals
test: ## Testes (precisa de Postgres: PG_HOST/PG_USER/PG_PASSWORD/PG_DB)
	uv run pytest -q
lint: ## Ruff
	uv run ruff check .
