---
id: T-20260911-03-historico-parquet
title: Arquivo histórico Parquet de 12 meses (G1/AC-8)
status: ready
format_version: 2
effort: M
budget_iterations: 15
agent: any
depends_on: [T-20260911-02-tempos-e-fonte]
touches_paths:
  - pipeline/steps.py
  - dags/receita_cnpj.py
  - intelligence/intents.py
  - pipeline/evals.py
  - tests
source_note: docs/converge/p4-consensus.md + sketch/receita-backbone.md
created: 2026-09-11T00:00:00Z
tags: [receita, v1]
owner: bruno
priority: P1
severity: feature
due_date: (none)
precondition: (none)
blocked_reason: (none)
security_class: (none)
source_action_item: (none)
linear_ref: (none)
execution_backend: any
signed_off: false
signed_off_by: (none)
signed_off_at: (none)
---

# Arquivo histórico Parquet de 12 meses (G1/AC-8)

> **Why:** AC-8 exige 12 competências consultáveis e comparáveis; hoje só existe a última foto.

---

## Goal

Nova etapa `arquivar_historico` exporta o silver aceito para `/data/history/competencia=AAAA-MM/<entidade>.parquet` (zstd), aplica retenção de 12, e a consulta curada `diferenca_competencias(a, b)` lista mudanças de situação e entradas/saídas de sócios.

---

## Context

- `pipeline/history.py` (novo), `pipeline/steps.py`, `dags/receita_cnpj.py` (tarefa entre qualidade e publicação), `intelligence/intents.py`, `pipeline/evals.py` (AC-8), `tests/test_historico.py`.

Pré-requisitos dos evals: rodar da raiz do repo com `uv sync` feito e `PG_HOST/PG_USER/PG_PASSWORD/PG_DB` apontando para um Postgres de teste.

---

## Success Criteria

```bash
# eval-1: módulo de histórico existe
eval_1() {
  test -f pipeline/history.py && grep -q 'RETENCAO' pipeline/history.py
}

# eval-2: DAG tem a tarefa de arquivo
eval_2() {
  grep -q 'arquivar_historico' dags/receita_cnpj.py
}

# eval-3: teste de histórico e diferença
eval_3() {
  uv run pytest -q tests/test_historico.py
}
```

---

## Validation Card

```yaml
success_criteria:
  - id: eval_1
    description: módulo de histórico existe
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_2
    description: DAG tem a tarefa de arquivo
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_3
    description: teste de histórico e diferença
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 60
retry_policy:
  max_iterations: 15
  circuit_breaker_no_progress: 3
  on_terminal_failure: park_with_context
agent_contract:
  version: 2
  read: [intent, contract, guardrails, operations]
  produce:
    - code
    - tests
    - docs
  required_tools: [git, bash]
  timeout_minutes: 30
  sandbox_type: host
  output_artifacts: []
  mcp_dependencies: []
  emit:
    - pass
    - fail
    - retry_with_reason
    - parked_with_context
  codex_metadata: {}
  kimi_metadata: {}
```

---

## Exit Check

```bash
eval_1 && eval_2 && eval_3
```

---

## Rollback Plan

(none — mudança aditiva; reverter com git se preciso)

---

## Observability Hooks

(none — sem observabilidade de runtime além dos evals)

---

## Anti-Patterns

- **Don't arquivar o raw** — o histórico é do silver aceito.
- **Don't depender do DuckDB para ler o histórico** — Parquet puro, legível sem o warehouse.
- **Don't apagar além de 12** — retenção exata, a mais antiga sai primeiro.

---

## Do-Not-Touch

- chaos/failures.py (exceto quando a task diz o contrário)
- docs/engineering-brief.md (consenso travado)

---

## Open Questions

(none — task totalmente especificada)
