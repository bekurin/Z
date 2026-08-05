# Z — Clarity Gate

> Before you ask an AI to build something, prove the spec is clear.

**Z** is a lightweight [Claude Code](https://claude.com/claude-code) plugin that scores the
*ambiguity* of a request and refuses to hand off to coding until ambiguity drops to
**≤ 0.20**, then freezes an immutable **spec card** you can build against.

---

## Key concept

Z scores your request across weighted dimensions, each in `[0, 1]`:

| Dimension | Weight | Question it answers |
|-----------|:------:|---------------------|
| **Goal** | 0.40 | Is *what* you want specific and unambiguous? |
| **Constraint** | 0.30 | Are the limits (stack, scope, budget, deadlines) defined? |
| **Success criteria** | 0.30 | Are "done" and "correct" *measurable*? |

```
ambiguity = 1 − Σ(clarityᵢ × weightᵢ)
PASS  ⇔  ambiguity ≤ 0.20        (i.e. ≥ 80% weighted clarity)
```

If you score below the bar you are still guessing at the architecture, so Z keeps
interviewing (up to 8 rounds), always attacking the *weakest* dimension first. Brownfield
work adds a fourth dimension, **Context**, renormalizing the weights to
`0.35 / 0.26 / 0.26 / 0.13`.

---

## Quick start

Install (local dev — registers this directory as a plugin marketplace and installs `z`):

```
./install.sh
```

Then use the three commands:

```
z gate "<goal>"     # interview → score → freeze an immutable spec card (.z/spec-cards/)
z score "<text>"    # one-shot ambiguity breakdown, no interview, no card
z card              # show the latest spec card and its lineage
```

Example — a vague goal gets interviewed until it clears the bar, then a card is frozen:

```
z gate "Add a CSV export button to the orders table"

◆ ambiguity=0.46  (goal 0.6 / constraint 0.3 / success 0.3)  → next: define the constraints
...
◆ gate PASSED (ambiguity=0.16) → next: implement against .z/spec-cards/add-csv-export-20260730T142210Z.json
```

Trigger phrases like "clarity gate", "게이트", or "run the gate" also work.
