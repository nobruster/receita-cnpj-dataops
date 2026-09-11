# Converge · Pass 4 — Consensus

**Engine:** Codex (the adversary) + Claude (defends & revises) + the docs as ground truth. Disagreement needs a *different* model — Claude won't refute itself hard enough.
**Inputs:** `sketch/receita-backbone.md` · `sketch/sentinel-engine.md` · `docs/tech-spec.md` · `docs/engineering-brief.pdf` (when it exists).
**Output:** the **same two plans, sharpened in place**, plus a short open-questions list (each objection → fixed, or accepted-risk with an owner).
**Gate:** no open objection remains — every attack is resolved in the plan or recorded as an owned, accepted risk.

Three steps: **attack → grill against docs → sharpen.**

> Teaching note: plan → adversarially sharpen → build. The cheapest place to kill a wrong idea is the plan, before any code exists. We don't ask Claude "is this good?" — it agrees with itself. We bring a *different engine* (Codex) to refute. That cross-model disagreement is the whole point of this pass.

---

## Step 1 · Attack — let Codex refute the plans

Run via the Codex plugin (e.g. `/codex` or the codex review skill). Prompt:

```text
You are a skeptical principal engineer reviewing two implementation plans you
did NOT write. Your job is to REFUTE them, not bless them.

Read sketch/receita-backbone.md and sketch/sentinel-engine.md. Find the
things that will bite us at build time:

- Where is a plan vague, hand-wavy, or assuming something unproven?
- Where will the build order break — a component that needs something not yet
  built?
- Is the backbone→sentinel interface actually complete, or does the Sentinel
  need something from the backbone that isn't in the contract?
- Any mismatch of KIND (e.g. a real-time expectation served by a batch
  pipeline)?

Give me the 5-7 highest-leverage objections, ranked by how much damage each
would cause if we built as-is. Be specific and cite the plan section. Default
to refuted — if something is merely plausible, say why it might be wrong.
```

**Why:** Codex is a different model with no ego investment in Claude's plans. "Default to refuted" forces it to attack rather than rubber-stamp. Ranking by damage tells you what to fix first.

## Step 2 · Grill against the docs — ground truth check

```text
Now check both plans against the source documents: the tech-spec and the
engineering-brief. For each plan, find where it CONTRADICTS or DRIFTS from the
docs:

- Does it claim to satisfy an acceptance criterion it doesn't actually cover?
- Does it contradict the tech-spec's architecture or the brief's scope (e.g.
  something the brief marked out-of-scope)?
- Does any number, freshness target, or success metric in the plan disagree
  with the docs?

List each drift as: plan section ↔ doc section ↔ the conflict. No hand-waving —
cite both sides.
```

**Why:** the plans must answer to the brief and the spec, not to Claude's memory of them. This catches the silent drift where a plan *sounds* right but quietly contradicts the agreed source of truth.

## Step 3 · Sharpen — resolve every objection

Back in Claude Code, with Codex's objections in hand:

```text
Here are the objections from the adversarial review [paste them]. For EACH one,
do exactly one of:

1. FIX — revise the relevant plan (receita-backbone.md or sentinel-engine.md)
   in place to resolve it, or
2. ACCEPT — record it as a known risk with an owner and a reason we're
   proceeding anyway.

Nothing may be silently dropped. When done, give me the updated plans and a
short "open questions" list: each remaining item, its owner, and whether it
blocks the build or not.
```

**Why:** the gate made operational. Every attack must land somewhere — fixed in the plan or accepted on the record. That binary (fix or own) is what "no open objection remains" actually means.

---

## Gate — confirm before leaving Pass 4

- [ ] Codex (a different engine) attacked the plans — not Claude self-reviewing.
- [ ] Plans were grilled against the tech-spec AND the brief for drift.
- [ ] Every objection is FIXED in a plan or ACCEPTED with an owner.
- [ ] The backbone→sentinel interface survived scrutiny (or was corrected).
- [ ] Open questions list exists; blockers are flagged.

When these hold, the sharpened plans are ready for the next phase — cutting each into atomic, buildable units.

---

### Notes

- **Codex is the engine, not a courtesy.** If you run this with Claude reviewing its own plans, you get agreement, not consensus. The cross-model refutation is the value. (Fallback if Codex is down: a fresh Claude session with no memory of writing the plans — weaker, but better than self-review in the same context.)
- **Known live ammunition** for the adversary against the current plans: the **freshness gap** (batch pipeline vs. real-time intent, already flagged in receita-backbone.md), the **Sentinel's hard dependency** (can't test until the backbone emits logs/tables — does the build order respect it?), and **interface completeness** (does the Sentinel need anything not in the contract table?).
- **Sharpen in place.** Pass 4 doesn't create new files — it hardens the two existing plans. The diff on those files IS the record of what consensus changed.
- **This is where the dark-factory gate lives.** Today Codex objects and you decide fix-vs-accept. Tomorrow the adversarial pass is automated and "no unresolved objection" is the eval that gates the build.
