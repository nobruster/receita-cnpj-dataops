# Converge · Pass 3 — Decomposition

**Engine:** Claude Code (Auto Mode) — same session as Pass 2, so the understanding carries over.
**Inputs:** the Pass 2 understanding (in session) · the tech-spec · the repo (`pipeline/`, `transform/`, `dags/`).
**Output:** `sketch/receita-backbone.md` and `sketch/sentinel-engine.md` — the two plans.
**Gate:** the system is split into its two components along the spec's own seam; each plan lists its features, components, dependencies, and build order; the Sentinel names what it needs from the backbone.

Three steps: **decompose → plan the backbone → plan the sentinel.**

> Teaching note: we don't guess the boundaries — the architecture reveals them. The tech-spec itself splits the system into "two distinct logical systems: the Analytical Platform (Layers 1-5)" and "the Autonomous DataOps Engine (Layer 6)." Pass 3 follows that seam. Plan altitude only — features and components, not atomic tasks yet (that's the next phase).

---

## Step 1 · Decompose — find the seam

```text
From everything we just understood, split this system into its top-level
components. Don't plan yet — just give me the decomposition and justify the
boundary: why does the split fall HERE? Group the layers under each component
and tell me how the two depend on each other.
```

*Expected:* two components along the spec's seam —
**Analytical Backbone** (Layers 1-5, deterministic: SERPRO+/WebDAV → Airflow 3 → dbt → DuckDB → Postgres/MCP) and **Sentinel Engine** (Layer 6, probabilistic: the CrewAI hierarchical crew that monitors it).

## Step 2 · Plan the backbone

```text
Write sketch/receita-backbone.md — the plan for the deterministic platform
(Layers 1-5). Include: the features/components, what each does, the
dependencies between them, and the order to build them. Tie the components back
to the brief's acceptance criteria where they apply. Plan altitude — no atomic
tasks yet, no code. Keep it tight and skimmable.
```

## Step 3 · Plan the sentinel

```text
Now write sketch/sentinel-engine.md — the plan for the autonomous monitoring
system (Layer 6, CrewAI). Same shape: features/components (the agents, their
roles, the remediation loop), dependencies, build order. Crucially, name the
INTERFACE it needs from the backbone — what it consumes (logs do Airflow/dbt,
DuckDB tables, the failure signals) — so the seam between the two plans is
explicit. Plan altitude, no tasks, no code.
```

---

## Gate — confirm before leaving Pass 3

- [ ] Two plans exist: `sketch/receita-backbone.md`, `sketch/sentinel-engine.md`.
- [ ] The split follows the spec's seam (Layers 1-5 vs. Layer 6), and the boundary is justified.
- [ ] Each plan lists features/components, dependencies, and a sane build order.
- [ ] Components trace back to the brief's acceptance criteria where they apply.
- [ ] `sentinel-engine.md` names the interface it needs from the backbone.
- [ ] Plan altitude held — no atomic tasks, no code yet.

When these hold, the two plans are the input to the next phase, where each is cut into atomic, buildable units.

---

### Notes

- **Two plans, not one.** The split is the lesson — a deterministic platform and a probabilistic agent system are different kinds of work and decompose differently. Forcing them into one plan hides that.
- **The seam is documented, the plans stay separate.** The Sentinel depends on the backbone (it monitors it), but only through a named interface — not by reaching into its internals. That interface is what keeps the two buildable independently.
- **Auto Mode earns its keep here** — decomposition is exploratory; let it read across the spec and repo and draft both plans, then you gate.
- **Still no decomposition into tasks.** Plans describe *what* and *in what order*. Cutting them into atomic, self-verifying units is the next phase — keep the altitude.
