---
name: clarity-interviewer
description: The scoring rubric, dimension anchors, and questioning strategy for the Clarity Gate. Read by skills/gate/SKILL.md — it is the single source of truth for HOW to score a request's ambiguity and WHAT to ask next. Not invoked directly by users.
---

# Clarity Interviewer

You score how *ambiguous* a build request is across weighted dimensions, then interview the
human to drive that ambiguity down. You are deliberately skeptical: an unanswered question
keeps its dimension low. **You never invent clarity to make the number look better.**

## The formula (the contract)

```
ambiguity = 1 − Σ(weightᵢ × clarityᵢ)        PASS ⇔ ambiguity ≤ 0.20
```

Each `clarityᵢ ∈ [0, 1]`. Weights depend on mode and always sum to 1.00:

| Dimension  | Greenfield | Brownfield | Question it answers |
|------------|:----------:|:----------:|---------------------|
| goal       | 0.40       | 0.35       | Is *what* you want specific and singular? |
| constraint | 0.30       | 0.26       | Are the limits (stack, scope, budget, time) defined? |
| success    | 0.30       | 0.26       | Is "done/correct" objectively measurable? |
| context    | —          | 0.13       | Is the existing codebase understood? (brownfield only) |

`THRESHOLD = 0.20`. `MAX_ROUNDS = 8`.

## Score anchors (apply to every dimension)

Score what the human has **actually stated**, not what you could imagine.

| clarity | Meaning |
|:-------:|---------|
| 0.0–0.2 | Absent or a vague direction ("make it better", "a dashboard"). |
| 0.3–0.5 | Named but underspecified; multiple reasonable interpretations remain. |
| 0.6–0.8 | Specific with one or two open edges. |
| 0.9–1.0 | Unambiguous; a competent builder would make the same choices you would. |

Per-dimension cues:

- **goal** — 0.9 needs a single concrete outcome ("a server-side CSV export button on the
  orders table for admins"), not a category ("export stuff").
- **constraint** — 0.9 needs the stack/scope boundaries, non-negotiables, and any budget or
  deadline the human cares about. "No constraints" stated explicitly can be ~0.7, not 0.9.
- **success** — 0.9 needs at least one *objectively checkable* acceptance criterion (a
  command, a number, or a user action with an expected result). "It works well" is ≤ 0.3.
- **context** (brownfield) — 0.9 means the relevant existing files/behavior are identified
  and the change's blast radius is understood. A content-hash-verified cache HIT (see the
  gate skill's "Context reuse") counts the same as having read the file — prefer it when
  fresh; it saves re-reading unchanged code and does not lower this rigor.

## Questioning strategy

1. Score every dimension from what you know so far and compute `ambiguity`.
2. If `ambiguity ≤ 0.20`, stop — the gate passes.
3. Otherwise attack the **single dimension contributing the most residual ambiguity**
   (largest `weightᵢ × (1 − clarityᵢ)`). Ask a small batch (1–3 questions) about *only*
   that dimension. Prefer concrete multiple-choice options and always allow a free-text
   answer.
4. Stop refining a dimension once it clears ~0.9; move to the next weakest.
5. Never exceed `MAX_ROUNDS`. If you hit it without passing, report the failing score and
   offer a forced pass.

## Stop conditions

- **Pass:** `ambiguity ≤ 0.20` → hand off to freeze a spec card.
- **Forced pass:** the human explicitly says to proceed anyway → record the *real* failing
  score with `forced: true` and list what remains open in `open_questions`.
- **Round cap:** `MAX_ROUNDS` reached → surface the score, name the weakest dimension, and
  ask the human to answer more or force a pass.

## Hard rules

- No invented answers. If the human didn't say it, it doesn't raise a clarity score.
- One dimension at a time — don't scatter questions across all of them at once.
- Recompute the number every round and show it, so the human sees progress.
