# `sketch/` — os dois planos (Passo 3 · Decomposition)

Planos no nível de desenho. Cada um descreve **o que será construído e em que ordem**: componentes, fronteiras, dependências e mapa de ACs. **Não trazem tarefas atômicas nem código.** As tarefas ficam em `tasks/` (task-spec) e o código em `pipeline/`, `transform/`, `dags/` e `sentinel/`.

| Arquivo | Componente | Camadas | Natureza | Escopo |
|---|---|---|---|---|
| [`receita-backbone.md`](receita-backbone.md) | **A — Backbone** | 1–5 (+ monitores da 6) | Determinístico: verificado por asserção | **v1** |
| [`sentinel-engine.md`](sentinel-engine.md) | **B — Sentinel** | 6 (agentes) | Probabilístico: pontuado contra a verdade de referência | **Fase 2** (D-3) |

**Por que a fronteira fica aqui.** O backbone produz fatos verificáveis (linhas, contagens, tempos). O Sentinel produz julgamentos que só podem ser *pontuados*. São dois tipos de trabalho, com duas formas de verificação e dois riscos. A dependência é de mão única: B lê A somente leitura pela interface I1–I5 e A nunca chama B (regra R3).

## Vocabulário de ids
| Prefixo | O que identifica |
|---|---|
| `C#` | Componentes do backbone |
| `A#` | Agentes do Sentinel |
| `B#` | Infraestrutura do Sentinel |
| `I#` | Superfícies da interface |
| `U#` | Decisões abertas ou fechadas |
| `AC-#` | Critérios de aceite do **engineering brief**, que é a fonte canônica |

| id | Componente |
|---|---|
| C0 | Fundação |
| C1 | Fonte |
| C2 | Ingestão |
| C3 | Transformação |
| C4 | Warehouse |
| C4a | Arquivo histórico |
| C5 | Consumo |
| C6 | Monitores |
| C7 | Chaos |
| A1 | Gerente |
| A2 | Log Analyst |
| A3 | Data Profiler |
| A4 | Data Engineer |
| A5 | Incident Commander |
| B1 | Gatilho |
| B2 | Histórico de incidentes |
| B3 | Oráculo de pontuação |
| I1 | `pipeline.log` |
| I2 | dbt `run_results` |
| I3 | DuckDB silver/gold |
| I4 | `ops.dq_metrics` + `ops.incidents` |
| I5 | Post-mortems + `ops.diagnoses` |
