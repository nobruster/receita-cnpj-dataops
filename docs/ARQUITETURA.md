# Arquitetura

## Visão geral

```text
               ┌──────────────────────── Componente A (determinístico) ────────────────────────┐
 SERPRO+       │ Airflow 3 (LocalExecutor, pool duckdb_writer = 1)                              │
 WebDAV  ────▶ │ descobrir → baixar → carregar_raw → dbt bronze → silver → gold → qualidade →   │
 37 zips/mês   │ arquivar_historico → publicar_postgres → limpar_landing → concluir  (11 tarefas)│
               │        │                  │                               │          │         │
               │  /data/landing      DuckDB /data/warehouse/cnpj.duckdb   ops.*      Postgres   │
               │  (zips + manifest)  raw · bronze · silver(+rejects) · gold (ledger)  gold.*    │
               │  /data/history/competencia=AAAA-MM/*.parquet (12 meses, AC-8)                  │
               └────────────────────────────────────────────────────────────────────────────────┘
                        ▲ só leitura (I1–I4)                              ▲ só leitura
               ┌────────┴──────────── Componente B (probabilístico) ─────┐ ┌──┴───────────────┐
               │ Sentinel: gatilho → crew hierárquico (OpenAI) | Flow    │ │ MCP (intenções)  │
               │ escreve SÓ ops.diagnoses e /data/sentinel/{proposed,    │ │ Claude Desktop   │
               │ postmortems}; pontuado contra origin='chaos'            │ └──────────────────┘
               │ FASE 2 (ADR-0003): docker compose --profile fase2       │
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
| source_unavailable | pipeline (competência `fonte`) | `pipeline_logs` | Tool reliability |
| stale_release | monitor (`DQ_STALE_DAYS`, 45) | `ops.incidents` | — (alerta humano) |
| parse_errors | monitor | `raw.raw_load_log` | crew base |
| multi_failure_cascade | Flow | várias | Flows + roteamento condicional |

## Histórico e AC-8

Depois do gold, `arquivar_historico` grava `empresas`, `estabelecimentos`, `socios` e `simples` em
`/data/history/competencia=AAAA-MM/<entidade>.parquet` (zstd), mantendo **12 competências** (ADR-0003 / D-1).
O warehouse guarda **só a última**; a comparação mês a mês (AC-8) lê os Parquet:
`intelligence.intents.diferenca_competencias`, exposta no MCP e em `cnpj.ps1 diferenca A B [raiz]`.
`limpar_landing` apaga os zips antigos (mantém a competência atual + `LANDING_RETENTION`, mínimo 1).

## Concorrência e o DuckDB

DuckDB é **um escritor por arquivo**. Toda tarefa que escreve usa o pool `duckdb_writer` (1 vaga) e a DAG tem `max_active_runs=1`. Leitores (MCP, Sentinel, evals) abrem **read-only por chamada** e fecham em seguida. Um leitor aberto não derruba mais a DAG: `connect_rw` e o dbt esperam a trava até `DUCKDB_LOCK_WAIT_S` (600 s) antes de falhar com `WarehouseBusyError`.

## Superfície de rede e dados pessoais

- Postgres (5433), Airflow (8080) e MCP (8000) publicam **só em `127.0.0.1`**: o MCP não tem autenticação e serve e-mail, telefone e sócios (LGPD, D-2).
- Leitura por SQL (`cnpj.ps1 consulta`, ferramentas do Sentinel) passa pelo `sql_guard`: um único `SELECT`, tabelas conferidas pelo parser do DuckDB e conexão com `enable_external_access=False` + `lock_configuration=True` — nenhum SQL lê arquivo do container.
- O que vai para o **LLM** é mais restrito ainda: no máximo 20 linhas e views **sem** as colunas pessoais (`connect_ro_masked`), então nem `SELECT linha_inteira` alcança nome, CPF, telefone, e-mail ou endereço.

## Ledger `ops` (PostgreSQL, banco `cnpj`)

- `ops.competencias` — status por competência (`descoberta → baixando → baixada → carregando → carregada → transformada → publicada | falhou`), tempos (`detectado_em`, `processamento_iniciado_em`, `finalizado_em`, `atualizado_em`) e bytes. A pseudo-competência **`fonte`** guarda o estado da origem (indisponível, publicação atrasada) e é ignorada pela "última processada".
- `ops.dq_metrics` — métricas por competência/entidade (histórico para comparação mês a mês).
- `ops.incidents` — `origin` = `pipeline` | `monitor` | `chaos` (verdade de referência).
- `ops.diagnoses` — rota, diagnóstico tipado e nota (`score_tier`, `match_score`, `evidence_score`). É aqui que mora o "já diagnosticado": um incidente citado em `incident_ids` sai da fila do Sentinel (`ops.UNDIAGNOSED`), e o Componente B nunca escreve em `ops.incidents` (R3).

Tempos e ACs: AC-2 mede `processamento_iniciado_em → finalizado_em` (sem o download) e AC-3 mede `detectado_em → finalizado_em`. Um reprocessamento forçado reinicia `detectado_em` para não gerar FAIL falso.

## Gate dos closers

Os 16 achados do reviewer independente e o destino de cada um estão em [`docs/converge/closers-review.md`](converge/closers-review.md).
