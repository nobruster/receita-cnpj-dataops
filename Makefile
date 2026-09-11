# Atalhos para Linux/WSL (no Windows puro use .\cnpj.ps1 — mesmos comandos).
.DEFAULT_GOAL := help
.PHONY: help up fase2 down status logs rodar amostra injetar falhas sentinel evals test lint

COMP ?= $(shell date +%Y-%m)
PG_USER ?= $(shell grep -E '^PG_USER=' .env 2>/dev/null | cut -d= -f2)
PG_DB ?= $(shell grep -E '^PG_DB=' .env 2>/dev/null | cut -d= -f2)
help: ## Lista os comandos
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'
up: ## Constrói e sobe o backbone v1
	docker compose up -d --build
fase2: ## Sobe também Sentinel e MCP
	docker compose --profile fase2 up -d --build
down: ## Para os containers
	docker compose down
status: ## Containers e competências
	docker compose ps
	docker compose exec -T postgres psql -U $(or $(PG_USER),cnpj) -d $(or $(PG_DB),cnpj) -c "SELECT * FROM ops.competencias ORDER BY 1 DESC LIMIT 5"
logs: ## Logs do scheduler
	docker compose logs -f --tail 200 airflow-scheduler
rodar: ## Dispara a DAG (FORCAR=AAAA-MM opcional; sem ele = última publicada)
	docker compose exec airflow-apiserver airflow dags unpause receita_cnpj_mensal
	docker compose exec airflow-apiserver airflow dags trigger receita_cnpj_mensal $(if $(FORCAR),--conf '{"competencia":"$(FORCAR)"}',)
amostra: ## Gera amostra sintética (COMP=AAAA-MM)
	docker compose --profile fase2 run --rm sentinel python -m chaos.cli sample --competencia $(COMP)
injetar: ## Injeta falha (KEY=... COMP=AAAA-MM)
	docker compose --profile fase2 run --rm sentinel python -m chaos.cli inject $(KEY) --competencia $(COMP)
falhas: ## Lista falhas injetáveis
	docker compose --profile fase2 run --rm sentinel python -m chaos.cli list
sentinel: ## Roda o Sentinel agora
	docker compose --profile fase2 exec sentinel python -m sentinel.trigger --once
evals: ## Mede os critérios de aceite (REPROC=1 mede também o AC-6)
	docker compose exec airflow-scheduler python -m pipeline.evals $(if $(REPROC),--reprocessar,)
test: ## Testes (precisa de Postgres: PG_HOST/PG_USER/PG_PASSWORD/PG_DB)
	uv run pytest -q
lint: ## Ruff
	uv run ruff check .
