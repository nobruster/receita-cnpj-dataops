# CLAUDE.md — receita-cnpj-dataops

Manual para agentes (Claude Code etc.) que trabalham neste repositório. Leia antes de mudar código.

## O que é
Plataforma DataOps on-premises para os dados abertos do CNPJ (Receita Federal). Dois componentes:

- **A — backbone (determinístico):** `pipeline/` + `transform/` (dbt) + `dags/` (Airflow 3) + `intelligence/` (MCP).
- **B — Sentinel (probabilístico):** `sentinel/` (CrewAI). Pontuado contra `ops.incidents origin='chaos'` (gerado por `chaos/`).

Documentos: `docs/business-requirements-document.md` (requisitos BR/RF/RNF e AC-1..AC-8), `docs/ARQUITETURA.md`, `docs/adrs/`, `docs/GUIA.md`.

## Regras (herdadas do ws-3, adaptadas)
- **R3 Dependência de mão única:** B lê A somente leitura. A nunca importa `sentinel`. As únicas escritas do B são `ops.diagnoses` e `/data/sentinel/`.
- **R5 Verificar pelo tipo:** A por asserção (testes dbt, `pipeline.evals`); B por nota contra a verdade de referência, nunca "está certo".
- **R6 Mapa falha → capacidade é vinculante:** falha nova em `chaos/failures.py` precisa de regra/monitor que a detecte; o e2e cobre todas automaticamente.
- **R7 Chaos reversível:** todo ciclo injetar→detectar→pontuar começa de amostra limpa (`chaos.cli reset`).
- **R8 Segredos e SQL:** nada de segredo no código; SQL com parâmetros (`?`/`%s`); identificadores só de constantes internas.
- **Layout num lugar só:** `pipeline/receita/layout.py`. Não duplique nomes de coluna em outro lugar do Python.
- **DuckDB tem um escritor:** toda tarefa que escreve usa o pool `duckdb_writer`; leitores abrem read-only por chamada.
- **Verdade escondida:** ferramentas do Sentinel nunca leem `origin='chaos'`.

## Comandos
```bash
uv sync
uv run ruff check .
uv run pytest -q                                  # e2e precisa de Postgres (PG_*); pula sem banco
uv run python -m chaos.cli sample --competencia 2026-08   # DATA_DIR aponta para a pasta de dados
uv run python -m pipeline.run --competencia 2026-08 --sem-download
uv run python -m sentinel.trigger --once
uv run python -m pipeline.evals
```
No Docker: `.\cnpj.ps1 <comando>` (Windows) ou `make <comando>`.
