# receita-cnpj-dataops

Plataforma **DataOps on-premises** para processar **todos os arquivos abertos do CNPJ** da Receita Federal (empresas, estabelecimentos, sócios, Simples/MEI e domínios). Um time de agentes de IA (**Sentinel**, CrewAI) vigia a qualidade e diagnostica falhas, e sua nota é medida contra casos de verdade conhecida.

Adaptação da arquitetura de [owshq-mec/ws-3-crew-ai-multi-agent](https://github.com/owshq-mec/ws-3-crew-ai-multi-agent) para arquivos da Receita, com **Airflow + DuckDB** no lugar de Dagster + Postgres-fonte.

> **Documentos:** [índice de docs](docs/README.md) · [BRD](docs/business-requirements-document.md) · [Engineering brief](docs/engineering-brief.md) · [Tech spec](docs/tech-spec.md) · [Planos](sketch/) · [Consenso P4](docs/converge/p4-consensus.md) · [Gate dos closers](docs/converge/closers-review.md) · [Tasks](tasks/) · [Guia passo a passo](docs/GUIA.md) · [Arquitetura](docs/ARQUITETURA.md) · [ADRs](docs/adrs/README.md)
>
> **Método e agentes:** [prompts do Converge](prompts/) · [AGENTS.md](AGENTS.md) (índice multiferramenta) · [frota e KBs](.claude/) · [deck](presentation/)
>
> **Escopo v1** (ADR-0003): backbone. Sentinel e MCP são **fase 2** (`docker compose --profile fase2`).

## O que é

| Camada | Pasta | O que faz |
|---|---|---|
| C1 Fonte | `pipeline/receita/` | WebDAV do SERPRO+ (`arquivos.receitafederal.gov.br/index.php/s/<RFB_SHARE_TOKEN>`): descobre a última competência e baixa 37 zips com retomada e validação de CRC |
| C2 Ingestão | `dags/` + `pipeline/receita/loader.py` | Airflow 3 orquestra; o raw no DuckDB é fiel ao arquivo; mudança de layout é bloqueada antes da carga |
| C3 Transformação | `transform/` (dbt) | bronze → silver (quarentena `*_rejects`, CNPJ alfanumérico + DV) → gold |
| C4 Warehouse | DuckDB | `/data/warehouse/cnpj.duckdb`, um único escritor (pool do Airflow) |
| C5 Inteligência | `intelligence/` | Servidor MCP com intenções curadas, somente leitura |
| C6 Consumo | `pipeline/publish.py` | Tabelas gold publicadas no PostgreSQL (Power BI) |
| C7 Qualidade | `pipeline/quality.py` | Métricas mês a mês e incidentes em `ops.*` |
| B Sentinel | `sentinel/` | Crew hierárquico de 5 agentes (OpenAI) + fluxo determinístico + nota |
| Chaos | `chaos/` | Amostra sintética no formato da Receita + 12 falhas injetáveis (verdade de referência) |

Casos de uso atendidos: **crédito e risco** (`gold_empresa_detalhe`), **KYC/PLD** (`gold_socios_detalhe`, `gold_rede_societaria`) e **prospecção** (`gold_painel_prospeccao`, `gold_cnae_secundaria`).

## Início rápido (Windows + Docker Desktop)

```powershell
copy .env.example .env      # edite as senhas (OPENAI_API_KEY só na fase 2)
.\cnpj.ps1 up               # build + sobe o backbone v1 (Postgres + Airflow)
.\cnpj.ps1 fase2            # (opcional) + Sentinel e MCP
# Airflow: http://localhost:8080  ->  ative a DAG receita_cnpj_mensal
.\cnpj.ps1 rodar            # processa a última competência publicada
.\cnpj.ps1 status           # competências, incidentes e diagnósticos
.\cnpj.ps1 evals            # critérios de aceite AC-1..AC-8 medidos
```

Sem internet ou para testar primeiro: coloque `OFFLINE_MODE=true` no `.env`, gere uma amostra com `.\cnpj.ps1 amostra 2026-08` e rode. O passo a passo completo está em [docs/GUIA.md](docs/GUIA.md).

## Fluxo da DAG `receita_cnpj_mensal`

```text
descobrir → baixar → carregar_raw → dbt_bronze → dbt_silver → dbt_gold → qualidade
          → arquivar_historico → publicar_postgres → limpar_landing → concluir
```

- Roda todo dia às 06:00 e processa **só a última competência publicada**, sem carga retroativa. Só trabalha quando há competência nova (a última concluída fica em `ops.competencias`).
- Para reprocessar a última competência, use **Trigger DAG** com `{"competencia": "2026-08"}`. Meses antigos ficam no histórico Parquet de 12 meses.

## Desenvolvimento

```bash
uv sync
uv run ruff check .
PG_HOST=localhost PG_USER=... PG_PASSWORD=... PG_DB=... uv run pytest -q   # 67 testes; e2e precisa de Postgres
```

A suíte de ponta a ponta injeta **cada uma das 12 falhas mais a cascata**, roda o pipeline de verdade (DuckDB + dbt) e pontua o diagnóstico contra a verdade de referência.

## Stack

Airflow 3.3.1 · DuckDB 1.5.5 · dbt-core 1.12 / dbt-duckdb 1.11 · PostgreSQL 17 · MCP (FastMCP) · CrewAI 1.15 · OpenAI API (Ollama opcional) · Docker Compose · Python 3.12
