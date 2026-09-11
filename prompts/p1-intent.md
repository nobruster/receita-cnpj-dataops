# Converge · Pass 1 — Intent

**Engine:** Claude Chat — conversational, no repo, no code.
**Input:** `docs/business-requirements-document.pdf` (attach it to the chat).
**Output:** `engineering-brief.pdf` — a consensus document to circulate with peers and the team.
**Gate:** the read-back of the problem is confirmed correct — pain, who feels it, what "done" means. **No technology choices.**

> The brief is born as a PDF on purpose: at this stage it's a *human consensus object* you discuss and align on, like the tech-spec. It becomes markdown only once consensus is locked and it feeds the build — same lifecycle as the tech-spec.

Three steps, run in order: **understand → interrogate → crystallize.**

---

## Step 1 · Understand

```text
Read this BRD like a senior engineer, not a summarizer. What's the real
problem, who's hurting and how? Cover the pains across the board — financial,
operational, and strategic — not just the dollars. Use their own numbers.
```

## Step 2 · Interrogate

```text
Now grill me. Ask the 2-3 questions that would most change how we build this —
across scope, "done", and any number or claim that looks off. For each: give
your own best default answer so we can keep moving, and name which stakeholder
role should own the real answer if it's above my pay grade.
```

## Step 3 · Crystallize

```text
Turn this into an engineering brief: the problem in plain exec language, in/out
of scope, verifiable acceptance criteria each tied to one of their KPIs,
success metrics as current → target, open assumptions. No technology choices —
this defines the problem, not the solution.

Make it visual and digestible: include diagrams of the PROBLEM and its impact
— how the pain flows through the business, current state vs. desired state,
who's affected and how, the journey from pain to outcome. Use visuals to
clarify the problem, NOT to propose any architecture or tech stack (that comes
in Pass 2).

Output a clean, professionally formatted PDF named engineering-brief.pdf — a
document I can circulate with my team to reach consensus. Cover page, clear
sections, diagrams where they aid understanding, tight.
```

---

## Gate — confirm before leaving Pass 1

- [ ] Problem stated in terms an executive would agree with.
- [ ] Scope (in / out) explicit.
- [ ] Every acceptance criterion is **verifiable**.
- [ ] Success metrics trace to the BRD's KPIs (current → target).
- [ ] Open assumptions recorded.
- [ ] **No technology** — the stack belongs to Pass 2.

Circulate `engineering-brief.pdf` with the team. Once there's consensus, it feeds **Pass 2 — Structure**, where the team generates the tech-spec from it.

---

### Notes

- **PDF now, markdown later.** The brief is a consensus document for humans — keep it PDF while you and the team align on it. It converts to markdown only when consensus is locked and it enters the build (same lifecycle as the tech-spec).
- **The flip in Step 2 is the moment** — narrate it: "watch, I'm having it grill *me*." Against this BRD it should surface real seams (the $233-310M personalization figure ≈46% of GMV; personalization listed as both revenue driver and Out-of-Scope/Phase-2; what "real-time" actually means). If it misses one, push it.
- **Going unattended later?** These prompts are short because *you're watching*. To hand any step to an unwatched agent, make it precise (spell out the output structure) — the conversation can't fix drift when no one's in it. The gate constraints (verifiable, tied to KPIs, no tech) never drop, regardless of length.
