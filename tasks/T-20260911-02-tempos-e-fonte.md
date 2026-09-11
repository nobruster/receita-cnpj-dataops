---
id: T-20260911-02-tempos-e-fonte
title: Tempos de AC-2/AC-3 e alertas da fonte (G2/G3/O2)
status: ready
format_version: 2
effort: M
budget_iterations: 15
agent: any
depends_on: [T-20260911-01-compose-fase2]
touches_paths:
  - pipeline/ops.py
  - pipeline/steps.py
  - pipeline/evals.py
  - dags/receita_cnpj.py
  - chaos/failures.py
  - tests
source_note: docs/converge/p4-consensus.md + sketch/receita-backbone.md
created: 2026-09-11T00:00:00Z
tags: [receita, v1]
owner: bruno
priority: P1
severity: bugfix
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

# Tempos de AC-2/AC-3 e alertas da fonte (G2/G3/O2)

> **Why:** AC-2 media a partir do download e AC-3 a partir da publicação; fonte fora do ar e publicação atrasada não viravam incidente; timeouts inviabilizavam o AC-3.

---

## Goal

Registrar `detectado_em` e `processamento_iniciado_em`; `source_unavailable` e `stale_release` viram incidentes `monitor`; `baixar` com 6h × (1+2); chaos ganha `source_unavailable`; evals medem AC-2/AC-3 pelas colunas certas.

---

## Context

- `pipeline/ops.py` (DDL com ALTER ... ADD COLUMN IF NOT EXISTS), `pipeline/steps.py` (discover com tratamento de rede e checagem de atraso; load_raw grava início do processamento), `pipeline/evals.py`, `dags/receita_cnpj.py`, `chaos/failures.py` (+ `source_unavailable`, detectado pelo monitor), `tests/`.

Pré-requisitos dos evals: rodar da raiz do repo com `uv sync` feito e `PG_HOST/PG_USER/PG_PASSWORD/PG_DB` apontando para um Postgres de teste.

---

## Success Criteria

```bash
# eval-1: colunas novas no ledger
eval_1() {
  grep -q 'detectado_em' pipeline/ops.py && grep -q 'processamento_iniciado_em' pipeline/ops.py
}

# eval-2: timeout do download amarrado ao AC-3
eval_2() {
  grep -q 'execution_timeout=timedelta(hours=6)' dags/receita_cnpj.py
}

# eval-3: testes de fonte indisponível e atraso
eval_3() {
  uv run pytest -q tests/test_fonte.py
}
```

---

## Validation Card

```yaml
success_criteria:
  - id: eval_1
    description: colunas novas no ledger
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_2
    description: timeout do download amarrado ao AC-3
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_3
    description: testes de fonte indisponível e atraso
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

- **Don't medir AC-2 com a rede** — processamento começa na carga.
- **Don't engolir erro de rede** — vira incidente e a tarefa falha.
- **Don't abrir `stale_release` a cada execução** — só uma vez por competência atrasada.

---

## Do-Not-Touch

- docs/engineering-brief.md (consenso travado)

---

## Open Questions

(none — task totalmente especificada)
