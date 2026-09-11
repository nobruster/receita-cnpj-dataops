# Plano B — Sentinel (Camada 6, agentes) — FASE 2

> **Flag de escopo:** fora do v1 (D-3). O código existe e é testado, mas só é **aceito** depois que o AC-1 for provado com uma competência real. **Natureza:** probabilística. É pontuado contra a verdade de referência, nunca declarado correto (R5).

## Componentes

### B1 · Gatilho — construído
- Faz polling de `ops.incidents` por competência cuja DAG terminou (status `publicada` ou `falhou`).
- **Rotas:**
  - 2 ou mais chaves observadas → Flow determinístico de cascata;
  - 1 chave com LLM disponível → crew;
  - sem LLM → Flow determinístico;
  - erro → `no-run`.

### A1–A5 · Crew hierárquico — construído, com fiação testada por LLM roteirizado
| Agente | Papel | Ferramentas | Superfície |
|---|---|---|---|
| A1 Gerente | Delega e sintetiza o `Diagnosis` | nenhuma | — |
| A2 Log Analyst | Falhas de pipeline | `read_pipeline_logs`, `read_dbt_run_results` | I1, I2 |
| A3 Data Profiler | Defeitos de dado | `profile_rejects`, `read_quality_metrics`, `query_warehouse` | I3, I4 |
| A4 Data Engineer | Patch proposto (HITL em `duplicate_key` e `volume_drop`) | `propose_patch` | escreve só em `/data/sentinel` |
| A5 Incident Commander | Post-mortem tipado, com guardrail | `query_incident_history`, `write_postmortem` | I5 |

### B2 · Histórico de incidentes — construído
RAG leve por termos, sem embedder.

### B3 · Oráculo de pontuação — construído
- **Tier de match:**
  - exato: 1,0;
  - alias: 0,7;
  - cascata: 0,5 + 0,5 × acerto;
  - erro: 0.
- **Tier de evidência:** pontuado à parte.

## Interface necessária do backbone (somente leitura)
| ID | Superfície | Produzida por | Consumida por | Completa? |
|---|---|---|---|---|
| I1 | `/data/logs/pipeline.log` (`PIPELINE_FAILURE`, `DQ_FINDING`) | C1, C2, C6 | A2 | sim; `source_unavailable` entra com o G3 |
| I2 | `/data/dbt/target/run_results.json` | C3 | A2 | sim |
| I3 | DuckDB silver (`*_rejects`, `_classificado`) e gold, read-only | C3/C4 | A3 | sim |
| I4 | `ops.dq_metrics`, `ops.incidents` (origin pipeline/monitor) | C6 | A3, B1 | sim |
| I5 | Post-mortems e `ops.diagnoses` | B (próprio) | A5 | sim |

## Mapa falha → capacidade
Fica em `chaos/failures.py` e `docs/ARQUITETURA.md`. Toda falha nova do C7 precisa de detector e superfície.

## Ordem de build (fase 2)
B3 → A2/A3 → A1 + síntese → B1 → A4/A5 → scorecard com a chave OpenAI em todas as falhas.

## Critério de aceite da fase 2 — F2-1
**F2-1:** match médio ≥ 0,8 com a rota **crew** em todas as falhas do chaos, incluindo `source_unavailable`. Não é um AC do v1: os AC-1..AC-8 do brief são só do backbone. Enquanto não for medido com LLM real, fica registrado como **não provado**. No `pipeline.evals`, a linha se chama "F2-1 Sentinel" (O1 do Passo 4).

## Implantação
Os serviços `sentinel` e `mcp` ficam no profile `fase2` do compose e não sobem no `up` padrão (O3).
