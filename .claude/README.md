# `.claude/` — frota de agentes, KBs e regras

Adaptado de [owshq-mec/ws-3-crew-ai-multi-agent](https://github.com/owshq-mec/ws-3-crew-ai-multi-agent) (mesma estrutura), com **Airflow no lugar do Dagster** e um KB de domínio da **Receita**.

| Pasta | Conteúdo |
|---|---|
| `agents/` | `airflow-*`, `dbt-*`, `duckdb-*`, `mcp-*`, `crewai-*` (architect/developer por tecnologia), closers (`code-reviewer`, `code-simplifier`, `code-documenter`), `codebase-explorer`, `task-architect` |
| `kb/` | KBs por tecnologia + `receita/` (fonte, layout, CNPJ alfanumérico, defeitos conhecidos, quarentena, histórico) — índice em `kb/_index.yaml` |
| `rules/agent-operating-rules.md` | R1–R11 |
| `doctrine.yaml` | matriz de concordância e limiares numéricos |
| `skills/task-spec/` | gerador/validador de `tasks/T-*.md` (Task-Spec v2.1) |

Fluxo Converge usado neste repo: BRD → `docs/engineering-brief.*` (P1) → `docs/tech-spec.md` + `docs/converge/p2-structure-grounding.md` (P2) → `sketch/*` (P3) → `docs/converge/p4-consensus.md` (P4) → `docs/adrs/` → `tasks/` → build → closers.
