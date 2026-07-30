---
name: score
description: "One-shot Clarity Gate score of a request or draft spec, with no interview and no card. Use when the user says 'z score', wants to check how clear a request is, or asks 'is this spec clear enough?'."
---

# /z:score

Score a request's ambiguity **once** and report the breakdown. No questioning loop, no
spec card written — this is the read-only diagnostic version of `z gate`.

## Instructions

### Step 1 — Get the text

Take the draft spec / goal from the skill argument, or ask for it. Detect `mode`
(greenfield vs brownfield) the same way `z gate` does.

### Step 2 — Score against the rubric

Read `${CLAUDE_PLUGIN_ROOT}/agents/clarity-interviewer.md` and score each dimension in
`[0,1]` using its anchors. Do **not** invent missing information to inflate a score — an
unstated constraint or success criterion scores low, and that is the point.

Compute:

```
WEIGHTS (greenfield) : goal 0.40 | constraint 0.30 | success 0.30
WEIGHTS (brownfield) : goal 0.34 | constraint 0.26 | success 0.26 | context 0.14
ambiguity = 1 − Σ(weightᵢ × clarityᵢ)
PASS ⇔ ambiguity ≤ 0.20
```

### Step 3 — Report

Show a table of `dimension | weight | clarity | contribution (weight×clarity)`, the total
ambiguity, and PASS/OPEN against the 0.2 threshold. For every dimension below ~0.8, give
**one concrete question** that would raise it (drawn from the agent's questioning
strategy). Do not write any file.

End with:

```
◆ score=0.34 (goal 0.9 / constraint 0.6 / success 0.4) → next: run `z gate` to close the gaps
```

## Notes

- Use this to decide whether a request is worth taking to a full `z gate` interview, or to
  sanity-check a spec someone else wrote.
