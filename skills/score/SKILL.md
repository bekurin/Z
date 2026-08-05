---
name: score
description: "One-shot clarity score of a goal or draft spec. No interview and no card — just an ambiguity breakdown and what to tighten. Use when the user says 'z score', or wants a quick read on how clear a request is before committing to the full gate."
---

# /z:score

A single, non-interactive read of how ambiguous a request is. Unlike `z gate`, it does not
ask questions and does not write a card — it just shows the breakdown and points at the
weakest dimension.

## Constants

```
WEIGHTS (greenfield) : goal 0.40 | constraint 0.30 | success 0.30
THRESHOLD            : 0.20
ambiguity = 1 − Σ(weightᵢ × clarityᵢ)
```

Scoring anchors and dimension definitions come from
`${CLAUDE_PLUGIN_ROOT}/agents/clarity-interviewer.md`.

## Instructions

1. Take the text from the skill argument (a goal or a draft spec). If none, ask for it.
2. Read `${CLAUDE_PLUGIN_ROOT}/agents/clarity-interviewer.md` and score each dimension in
   `[0,1]` from **only what the text states** — never invent clarity.
3. Compute `ambiguity = 1 − Σ(weightᵢ × clarityᵢ)` with the greenfield weights (use
   brownfield if the text clearly concerns an existing codebase).
4. Print the breakdown table and the verdict:

   ```
   dimension    weight  clarity  contribution
   goal          0.40    0.3       0.12
   constraint    0.30    0.1       0.03
   success       0.30    0.1       0.03
   ──────────────────────────────────────────
   ambiguity = 0.82   → OPEN (needs ≤ 0.20)
   ◆ next: run `z gate` — which users? which data? what actions?
   ```

5. End with a one-line pointer at the weakest dimension and the most useful next question.
   If `ambiguity ≤ 0.20`, say it would pass and suggest `z gate` to freeze a card.

## Notes

- No card is written and no state changes — this is a read-only estimate.
- Keep it to one message; if the user wants to actually drive the number down, that's `z gate`.
