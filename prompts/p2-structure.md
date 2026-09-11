# Converge · Pass 2 — Structure

**Engine:** Claude Code — open the repo. We check the spec against what actually exists.
**Inputs:** `docs/tech-spec.md` (the spec, written with the team from the engineering-brief) · `docs/engineering-brief.pdf` (the *what*) · the repo (`pipeline/`, `transform/`, `dags/`).
**Output:** none — Pass 2 produces **shared understanding, held in the session**, not a file.
**Gate:** you can explain the whole system and its parts, and it is consistent with the brief and the repo.

Three steps: **comprehend → ground & interrogate → confirm.** Run them in **one Claude Code session** and keep it open into Pass 3 — the understanding is the handoff.

> Teaching note: Pass 2 is comprehension, not creation. The tech-spec already exists (built in meetings, from the brief). Our job here is to *understand it deeply, grounded against the real repo*, so decomposition stands on solid ground. You don't decompose what you don't understand.

---

## Step 1 · Comprehend

```text
Read the tech-spec PDF and the engineering-brief PDF, then look at the repo
(src/). Explain the system back to me end to end: what are the components, what
does each do, and how do they connect — source to monitoring? Plain language,
no restating the doc verbatim.
```

## Step 2 · Ground & interrogate

```text
Now pressure-test it. Check the spec against the real repo and the brief. Where
is it vague, internally inconsistent, or hard to build as written? Does what it
describes match what's actually in src/ (the schema, the generator)? Does it
satisfy the brief's acceptance criteria, or are there gaps? Give me the 3-4
things that would bite us if we decomposed it as-is.
```

## Step 3 · Confirm

```text
Good. Restate the system as a clean component-and-dependency map — each major
piece, what it depends on, and the order things have to be built in. This is
the picture we'll break into tasks next. Keep it tight; flag anything still
unresolved.
```

---

## Gate — confirm before leaving Pass 2

- [ ] You can explain the full system and each component in plain language.
- [ ] The spec is consistent with what's actually in `src/` (schema, generator).
- [ ] The spec satisfies the engineering-brief's criteria — or gaps are named.
- [ ] You have a clear component + dependency map and a sane build order.
- [ ] Open/unresolved items are flagged, not glossed.

When these hold, stay in the session and descend to **Pass 3 — Decomposition**, where this understanding is broken into the plans under `sketch/`.

---

### Notes

- **No artifact, so don't lose the session.** Pass 2's output is the loaded understanding in Claude Code's context. Run Pass 3 in the same session — close it and the understanding is gone.
- **Why Code, not Chat:** understanding the spec means checking it against the real `pipeline/`/`transform/`. The repo is evidence the spec must honor — "o doc diz 37 zips por competência com layout X; confirme que é isso que `pipeline/receita/layout.py` descreve."
- **The senior move is Step 2** — interrogating a handed-down spec instead of trusting it. The likely catch here: the spec implies near-real-time, but a Airflow→dbt batch pipeline delivers hours-fresh. Name gaps now; they're cheapest to fix before decomposition.
- **Unattended later?** These are short because you're driving. To hand a step to an unwatched agent, make it precise — and have it emit the component map as a file so the next step has an input.
