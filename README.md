# Z — Clarity Gate

> Before you ask an AI to build something, prove the spec is clear.

**Z** is a lightweight [Claude Code](https://claude.com/claude-code) plugin that puts a
**measurable clarity gate** in front of implementation work. It runs a short Socratic
interview, scores the *ambiguity* of your request across weighted dimensions, and refuses
to hand off to coding until ambiguity drops to **≤ 0.2**. When it passes, it freezes an
immutable **spec card** you can build against.

---

## The idea in one formula

Z scores three dimensions of your request, each in `[0, 1]`:

| Dimension | Weight | Question it answers |
|-----------|:------:|---------------------|
| **Goal** | 0.40 | Is *what* you want specific and unambiguous? |
| **Constraint** | 0.30 | Are the limits (stack, scope, budget, deadlines) defined? |
| **Success criteria** | 0.30 | Are "done" and "correct" *measurable*? |

> Brownfield work adds a fourth dimension, **Context** (0.15, weights renormalized) —
> "is the existing codebase understood?"

```
ambiguity = 1 − Σ(clarityᵢ × weightᵢ)
PASS  ⇔  ambiguity ≤ 0.20        (i.e. ≥ 80% weighted clarity)
```

If you score poorly, you are still guessing at the architecture — so Z keeps interviewing
(up to 8 rounds), always attacking the *weakest* dimension first.

---

## Commands

| Command | What it does |
|---------|--------------|
| `z gate "<goal>"` | Run the full gate: interview → score → gate → emit a frozen spec card. |
| `z score "<draft spec or goal>"` | One-shot score of existing text. No interview, no card — just a breakdown and what to tighten. |
| `z card` | Show the latest spec card (and its lineage). |

Trigger phrases like "clarity gate", "게이트", or "run the gate" also work.

---

## Usage

### 1. Run the gate before building

```
z gate "Add a CSV export button to the orders table"
```

Z detects that this is too vague to build (the *what* is directional but constraints and
"done" are unstated), so it interviews you — attacking the weakest dimension first:

```
◆ ambiguity=0.46  (goal 0.6 / constraint 0.3 / success 0.3)  → next: define the constraints

  Which of these are hard constraints?
   1) Server-side generation, admins only, max 50k rows
   2) Client-side, any signed-in user
   3) Other…
```

After a couple of focused rounds it clears the bar and freezes a card:

```
◆ gate PASSED (ambiguity=0.16) → next: implement against .z/spec-cards/add-csv-export-20260730T142210Z.json
```

### 2. Quick-check without an interview

```
z score "a dashboard for users"
```

```
dimension    weight  clarity  contribution
goal          0.40    0.3       0.12
constraint    0.30    0.1       0.03
success       0.30    0.1       0.03
──────────────────────────────────────────
ambiguity = 0.82   → OPEN (needs ≤ 0.20)
◆ next: run `z gate` — which users? which data? what actions?
```

### 3. Review the frozen spec

```
z card
```

Renders the latest card (goal, constraints, numbered success criteria, non-goals,
ambiguity breakdown) and its lineage. To change a passed spec, run `z gate` again — Z mints
a **new** card whose `parent_id` points at the old one.

### 4. (Optional) verify a card's integrity

```
python3 scripts/validate-card.py .z/spec-cards/<id>.json
```

Checks the structure, recomputes the ambiguity arithmetic, and re-derives the
`content_hash` to prove the frozen card was not tampered with.

---

## The spec card

On pass, Z writes an **immutable** JSON artifact to your project at
`.z/spec-cards/<slug>-<timestamp>.json` (schema: [`schemas/spec-card.schema.json`](schemas/spec-card.schema.json)):

```jsonc
{
  "id": "add-csv-export-20260730T142210Z",
  "parent_id": null,                 // set when a card supersedes an earlier one
  "mode": "greenfield",
  "goal": "…",
  "constraints": ["…"],
  "success_criteria": [
    { "id": "AC1", "statement": "…", "verify": "how to check it" }
  ],
  "non_goals": ["…"],
  "assumptions": ["…"],
  "open_questions": [],              // must be empty (or non-blocking) to pass
  "ambiguity": {
    "score": 0.16,
    "threshold": 0.2,
    "dimensions": {
      "goal":       { "weight": 0.40, "clarity": 0.9 },
      "constraint": { "weight": 0.30, "clarity": 0.8 },
      "success":    { "weight": 0.30, "clarity": 0.8 }
    }
  },
  "created_at": "2026-07-30T14:22:10Z",
  "content_hash": "sha256:…",
  "frozen": true
}
```

---

## Install (local dev)

Z is a standard Claude Code plugin. For local development, register this directory as a
plugin marketplace and install it — see [CLAUDE.md](CLAUDE.md) for the exact steps.

Once published:

```
claude plugin marketplace add bekurin/Z
claude plugin install z@z
```

---

## Why "soft" gating

Z is deliberately advisory rather than a hard blocker: the `gate` skill declines to move
on to implementation while ambiguity is high, and (optionally) a `UserPromptSubmit` hook
nudges you toward `z gate` when it sees build-intent prompts with no recent card. You can
always force a pass — Z records the forced score honestly on the card.

---

MIT licensed.
