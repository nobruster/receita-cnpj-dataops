---
id: T-20260911-01-compose-fase2
title: Sentinel e MCP no profile fase2 (O3/G5)
status: done
format_version: 2
effort: S
budget_iterations: 15
agent: any
depends_on: []
touches_paths:
  - docker-compose.yml
  - cnpj.ps1
  - Makefile
  - docs/GUIA.md
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
signed_off: true
signed_off_by: closers-gate
signed_off_at: 2026-09-11T00:00:00Z
---

# Sentinel e MCP no profile fase2 (O3/G5)

> **Why:** O brief (D-3) tira Sentinel e MCP do v1, mas o compose os sobe por padrão.

---

## Goal

`docker compose up` sobe só o backbone; `--profile fase2` acrescenta sentinel e mcp. Consultas curadas (AC-5) e evals passam a rodar no container do Airflow.

---

## Context

- `docker-compose.yml`: `profiles: [fase2]` em sentinel/mcp; montar `./intelligence` (ro) no Airflow.
- `cnpj.ps1`/`Makefile`: `evals` e `consulta` via `airflow-scheduler`; novo comando `fase2`.
- GUIA atualizado.

Pré-requisitos dos evals: rodar da raiz do repo com `uv sync` feito e `PG_HOST/PG_USER/PG_PASSWORD/PG_DB` apontando para um Postgres de teste.

---

## Success Criteria

```bash
# eval-1: serviços padrão sem sentinel/mcp
eval_1() {
  cp -n .env.example .env.eval 2>/dev/null || true
  out=$(docker compose --env-file .env.example config --services)
  ! grep -qx sentinel <<<"$out" && ! grep -qx mcp <<<"$out"
}

# eval-2: profile fase2 inclui sentinel e mcp
eval_2() {
  out=$(docker compose --env-file .env.example --profile fase2 config --services)
  grep -qx sentinel <<<"$out" && grep -qx mcp <<<"$out"
}

# eval-3: intelligence montado no Airflow
eval_3() {
  grep -q './intelligence:/opt/airflow/project/intelligence' docker-compose.yml
}
```

---

## Validation Card

```yaml
success_criteria:
  - id: eval_1
    description: serviços padrão sem sentinel/mcp
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_2
    description: profile fase2 inclui sentinel e mcp
    runnable: bash
    check_type: deterministic
    terminal: true
    expected_duration_sec: 5
  - id: eval_3
    description: intelligence montado no Airflow
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

- **Don't remover os serviços** — são fase 2, não lixo. Use profiles.
- **Don't mover as consultas curadas para fase 2** — AC-5 é v1.
- **Don't subir fase2 no `cnpj.ps1 up`** — só com `fase2`.

---

## Do-Not-Touch

- chaos/failures.py (exceto quando a task diz o contrário)
- docs/engineering-brief.md (consenso travado)

---

## Open Questions

(none — task totalmente especificada)
