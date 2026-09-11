---
id: T-20260911-05-endurecimento
title: Endurecimento: escritor único, memória, retenção do landing (O5/O6/O7/G6)
status: ready
format_version: 2
effort: S
budget_iterations: 15
agent: any
depends_on: [T-20260911-04-eval-ac6]
touches_paths:
  - pipeline/warehouse.py
  - pipeline/steps.py
  - dags/receita_cnpj.py
  - tests
source_note: docs/converge/p4-consensus.md + sketch/receita-backbone.md
created: 2026-09-11T00:00:00Z
tags: [receita, v1]
owner: bruno
priority: P1
severity: refactor
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

# Endurecimento: escritor único, memória, retenção do landing (O5/O6/O7/G6)

> **Why:** Segundo escritor fora do Airflow falhava com erro críptico; memory_limit podia exceder o container; comentário herdado do Dagster; zips acumulavam ~6 GB/mês.

---

## Goal

`connect_rw` traduz a trava do DuckDB em mensagem clara; `memory_limit` efetivo ≤ 60% da memória do container; comentários sem Dagster; etapa `limpar_landing` mantém 2 competências de zips.

---

## Context

- `pipeline/warehouse.py`, `pipeline/steps.py`, `dags/receita_cnpj.py`, `tests/test_endurecimento.py`.

Pré-requisitos dos evals: rodar da raiz do repo com `uv sync` feito e `PG_HOST/PG_USER/PG_PASSWORD/PG_DB` apontando para um Postgres de teste.

---

## Success Criteria

```bash
# eval-1: sem menção a Dagster no código
eval_1() {
  ! grep -rqi --include='*.py' 'dagster' pipeline dags intelligence sentinel chaos
}

# eval-2: tarefa de retenção na DAG
eval_2() {
  grep -q 'limpar_landing' dags/receita_cnpj.py
}

# eval-3: testes de endurecimento
eval_3() {
  uv run pytest -q tests/test_endurecimento.py
}
```

---

## Validation Card

```yaml
success_criteria:
  - id: eval_1
    description: sem menção a Dagster no código
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_2
    description: tarefa de retenção na DAG
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_3
    description: testes de endurecimento
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

- **Don't criar lock externo** — a trava do DuckDB já garante exclusão; só melhore a mensagem.
- **Don't apagar a competência em processamento** — retenção só de competências concluídas.
- **Don't aumentar o limite do usuário** — o teto só reduz.

---

## Do-Not-Touch

- chaos/failures.py (exceto quando a task diz o contrário)
- docs/engineering-brief.md (consenso travado)

---

## Open Questions

(none — task totalmente especificada)
