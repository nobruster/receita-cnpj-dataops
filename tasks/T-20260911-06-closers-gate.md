---
id: T-20260911-06-closers-gate
title: Gate dos closers: review → simplify → fix → document
status: ready
format_version: 2
effort: M
budget_iterations: 15
agent: any
depends_on: [T-20260911-05-endurecimento]
touches_paths:
  - pipeline
  - dags
  - docs
  - README.md
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

# Gate dos closers: review → simplify → fix → document

> **Why:** Método da referência: nada é dado como pronto sem revisão independente e documentação alinhada ao código.

---

## Goal

Reviewer independente (outro contexto) aponta defeitos; cada achado é corrigido ou justificado; lint, testes, `airflow dags test` e docs ficam coerentes.

---

## Context

- Todo o repositório; agentes `code-reviewer`, `code-simplifier`, `code-documenter` em `.claude/agents/`.

Pré-requisitos dos evals: rodar da raiz do repo com `uv sync` feito e `PG_HOST/PG_USER/PG_PASSWORD/PG_DB` apontando para um Postgres de teste.

---

## Success Criteria

```bash
# eval-1: lint limpo
eval_1() {
  uv run ruff check .
}

# eval-2: suíte completa
eval_2() {
  uv run pytest -q
}

# eval-3: docs citam as novas etapas
eval_3() {
  grep -q 'arquivar_historico' docs/GUIA.md && grep -q 'fase2' README.md
}
```

---

## Validation Card

```yaml
success_criteria:
  - id: eval_1
    description: lint limpo
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_2
    description: suíte completa
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 60
  - id: eval_3
    description: docs citam as novas etapas
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
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

- **Don't aceitar achado sem destino** — corrigir ou justificar, nunca ignorar.
- **Don't reescrever o que funciona** — simplificar só o que o reviewer apontar.
- **Don't deixar doc divergente do código** — o documenter confere cada comando.

---

## Do-Not-Touch

- docs/engineering-brief.md (consenso travado)

---

## Open Questions

(none — task totalmente especificada)
