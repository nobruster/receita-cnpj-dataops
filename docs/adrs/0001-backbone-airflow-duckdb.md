# ADR-0001 — Backbone: Airflow + DuckDB + dbt, raw fiel e quarentena

- **Status:** aceito (2026-09-11)
- **Contexto:** ~6 GB zipados/mês (37 arquivos, >80 GB de CSV), dezenas de milhões de linhas, fonte instável (SERPRO+/WebDAV), processamento on-premises em estação Windows com Docker Desktop.

## Decisões

1. **Orquestração: Airflow 3 (LocalExecutor).** Decisão do projeto (mercado, operação conhecida). Substitui o Dagster da referência. Concorrência controlada por *pool* `duckdb_writer` (1 vaga) e `max_active_runs=1`. A lógica fica em `pipeline.steps` (a DAG só orquestra), então o mesmo fluxo roda sem Airflow (`python -m pipeline.run`).
2. **Motor: DuckDB.** Colunar, vetorizado, com *spill* em disco (`memory_limit`, `temp_directory`). É o que dá vazão no volume. PostgreSQL fica para ledger e consumo (Power BI), não para processamento.
3. **Fronteira do raw (U2 da referência): a carga é dona do raw.** O raw é fiel ao arquivo (tudo VARCHAR, sem correções), uma competência por vez (`CREATE OR REPLACE`). Checagem de layout (contagem de campos) antes de carregar, porque o DuckDB com `strict_mode=false` truncaria colunas extras em silêncio.
4. **Encoding:** leitura nativa `latin-1`; se o DuckDB recusar bytes 0x80–0x9F, transcodifica em Python (latin-1 → UTF-8) e recarrega. Sem perder linha.
5. **Costura de detecção (U3): quarentena, não descarte.** Silver classifica 100% das linhas; `reject_rule` = `failure_key`. Gold usa só aceitas (teste `no_reject_leaks_to_gold`).
6. **Snapshot mensal, não CDC.** A Receita publica fotos completas; histórico de volume vive em `ops.dq_metrics`.
7. **Publicação no Postgres por COPY em streaming** (sem extensão `postgres` do DuckDB, que baixa binário em tempo de execução e costuma ser bloqueada em rede corporativa). Troca atômica por `RENAME`.

## Consequências

- Leitores precisam tolerar o arquivo travado durante a DAG (retentativa).
- `gold_empresa_detalhe` completo no Postgres é opcional (tamanho).
