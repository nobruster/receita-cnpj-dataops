# Arquitetura

## Visão geral

```text
               ┌──────────────────────── Componente A (determinístico) ────────────────────────┐
 SERPRO+       │ Airflow 3 (LocalExecutor, pool duckdb_writer = 1)                              │
 WebDAV  ────▶ │ descobrir → baixar → carregar_raw → dbt bronze → silver → gold → qualidade →   │
 37 zips/mês   │ publicar_postgres → concluir                                                   │
               │        │                  │                               │          │         │
               │  /data/landing      DuckDB /data/warehouse/cnpj.duckdb   ops.*      Postgres   │
               │  (zips + manifest)  raw · bronze · silver(+rejects) · gold (ledger)  gold.*    │
               └────────────────────────────────────────────────────────────────────────────────┘
                        ▲ só leitura (I1–I4)                              ▲ só leitura
               ┌────────┴──────────── Componente B (probabilístico) ─────┐ ┌──┴───────────────┐
               │ Sentinel: gatilho → crew hierárquico (OpenAI) | Flow    │ │ MCP (intenções)  │
               │ escreve SÓ ops.diagnoses e /data/sentinel/{proposed,    │ │ Claude Desktop   │
               │ postmortems}; pontuado contra origin='chaos'            │ └──────────────────┘
               └─────────────────────────────────────────────────────────┘
```

## Camadas de dados

| Schema | Materialização | Conteúdo |
|---|---|---|
| `raw` | tabela (1 competência) | Espelho do CSV, tudo VARCHAR + `_arquivo`, `_competencia`, `_carregado_em`; `raw_load_log` |
| `ref` | seed dbt | Domínios que a Receita não publica em CSV (porte, situação, matriz/filial, tipo de sócio, faixa etária, UF) |
| `bronze` | view | Nomes estáveis, trim, datas/dinheiro tipados com `TRY_*`, CEP com 8 dígitos, `***000000**` → nulo |
| `silver` | tabela `_classificado` + view aceita + tabela `_rejects` | `reject_rule` = primeira regra violada = `failure_key`; flags `_orphan_*` |
| `gold` | tabela | `gold_empresa_detalhe`, `gold_socios_detalhe`, `gold_rede_societaria`, `gold_cnae_secundaria`, `gold_painel_prospeccao`, `gold_resumo_competencia` |

### Regras de quarentena (silver)

| reject_rule | Entidades | Regra |
|---|---|---|
| `invalid_cnpj` | todas | forma `[0-9A-Z]{8}` (+ ordem `[0-9A-Z]{4}`, DV `\d{2}`) e DV módulo 11 alfanumérico |
| `duplicate_key` | estabelecimentos, empresas, simples | 2ª+ ocorrência da chave (a 1ª segue) |
| `invalid_date` | estabelecimentos, sócios, simples | data real fora de 1900..hoje ou impossível (`0`/`00000000` = nulo, não defeito) |
| `invalid_domain` | todas | código fora do domínio fixo (situação, matriz/filial, UF, porte, tipo de sócio, faixa etária, S/N) |
| `invalid_capital` | empresas | capital não numérico ou negativo |
| `encoding_mojibake` | empresas, estabelecimentos, sócios | `[ÃÂ][\x80-\xBF]` = UTF-8 lido como latin-1 |
| `orphan_socio` | sócios | `cnpj_basico` sem empresa |

Órfãos de domínio publicado (CNAE, município, motivo, país, natureza, qualificação) **não** são rejeitados: viram flag. Motivo 32 e alguns países são defeitos conhecidos da fonte.

## Interfaces lidas pelo Sentinel (somente leitura)

| ID | Superfície | Ferramenta | Agente |
|---|---|---|---|
| I1 | `/data/logs/pipeline.log` (`PIPELINE_FAILURE`, `DQ_FINDING`) | `read_pipeline_logs` | A2 Log Analyst |
| I2 | `/data/dbt/target/run_results.json` | `read_dbt_run_results` | A2 |
| I3 | DuckDB `silver_*_rejects`, flags, gold (modo read-only) | `profile_rejects`, `query_warehouse` | A3 Data Profiler |
| I4 | `ops.dq_metrics` + `ops.incidents` (sem `origin='chaos'`) | `read_quality_metrics` | A3 |
| I5 | post-mortems + `ops.diagnoses` | `query_incident_history` | A5 Incident Commander |

Escritas do Sentinel: `propose_patch` (A4) → `/data/sentinel/proposed/`; `write_postmortem` (A5) → `/data/sentinel/postmortems/`; o gatilho → `ops.diagnoses`.

## Mapa falha → detecção → capacidade CrewAI

| failure_key | Quem detecta | Evidência | Capacidade exercitada |
|---|---|---|---|
| invalid_cnpj, invalid_date, invalid_domain | A3 + monitor | `silver_estabelecimentos_rejects` | crew base |
| duplicate_key | A3 + monitor | `silver_estabelecimentos_rejects` | HITL (correção destrutiva) |
| invalid_capital | A3 + monitor | `silver_empresas_rejects` | crew base |
| encoding_mojibake | A3 + monitor | `silver_empresas_rejects` | Guardrail + `output_pydantic` |
| orphan_socio | A3 + monitor | `silver_socios_rejects` | crew base |
| volume_drop | monitor | `ops.dq_metrics` | HITL (reprocessar) |
| orphan_domain | monitor | `silver_estabelecimentos._orphan_cnae` | Knowledge/RAG (runbook) |
| layout_drift, missing_file, corrupt_zip | pipeline | `pipeline_logs` | Tool reliability (`max_retry_limit`) |
| multi_failure_cascade | Flow | várias | Flows + roteamento condicional |

## Concorrência e o DuckDB

DuckDB é **um escritor por arquivo**. Toda tarefa que escreve usa o pool `duckdb_writer` (1 vaga) e a DAG tem `max_active_runs=1`. Leitores (MCP, Sentinel, evals) abrem **read-only por chamada** e fecham em seguida, com nova tentativa se a DAG estiver escrevendo.

## Ledger `ops` (PostgreSQL, banco `cnpj`)

- `ops.competencias` — status por competência (`descoberta → baixando → baixada → carregada → transformada → publicada | falhou`), tempos e bytes.
- `ops.dq_metrics` — métricas por competência/entidade (histórico para comparação mês a mês).
- `ops.incidents` — `origin` = `pipeline` | `monitor` | `chaos` (verdade de referência).
- `ops.diagnoses` — rota, diagnóstico tipado e nota (`score_tier`, `match_score`, `evidence_score`).
