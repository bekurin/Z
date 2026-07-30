# Z — Development Guide

> This CLAUDE.md is for **local development of the Z plugin**. End users install via the
> plugin marketplace (see [README.md](README.md)); once installed, the skills/agents load
> natively and this file is not needed.

## What Z is

Z is a **lightweight, markdown-first Claude Code plugin** implementing a single idea from
[ouroboros](https://github.com/Q00/ouroboros): a **Clarity Gate** that scores request
ambiguity and blocks implementation until `ambiguity <= 0.2`, then freezes an immutable
spec card. There is **no backend** — no MCP server, no database, no network. The harness
(Claude) does the scoring by following the agent's rubric.

## `z` commands (dev mode)

When the user types one of these, read the matching `SKILL.md` and follow it exactly —
do **not** use the Skill tool, use the Read tool and execute the instructions:

| Input | Action |
|-------|--------|
| `z gate ...` / "clarity gate" / "게이트" | Read `skills/gate/SKILL.md` and follow it |
| `z score ...` | Read `skills/score/SKILL.md` and follow it |
| `z card ...` | Read `skills/card/SKILL.md` and follow it |

The scoring rubric, weights, score anchors, and questioning strategy live in
`agents/clarity-interviewer.md` — that agent file is the source of truth. The gate skill
reads it at Step 2.

## Layout

```
.claude-plugin/plugin.json   # plugin manifest (name "z", skills path)
agents/clarity-interviewer.md# the rubric + scoring + questioning contract
schemas/spec-card.schema.json# frozen spec-card contract (draft-07)
skills/gate/SKILL.md         # interview → score → gate → freeze card
skills/score/SKILL.md        # one-shot score, no card
skills/card/SKILL.md         # show latest card + lineage
hooks/hooks.json             # (optional) build-intent nudge
scripts/                     # (optional) zero-dep Node helpers
```

Runtime artifacts are written to the **target project** at `.z/spec-cards/<id>.json`,
never into this plugin repo.

## Key invariants (keep these true when editing)

- **The formula is the contract.** `ambiguity = 1 − Σ(weightᵢ × clarityᵢ)`, threshold
  `0.20`. Greenfield weights `0.40/0.30/0.30`; brownfield adds `context` and renormalizes.
  If you change weights or threshold, change them in **all three** of: this file,
  `agents/clarity-interviewer.md`, and each `skills/*/SKILL.md`, and the README.
- **Cards are immutable.** Never edit or overwrite a card. A spec change = a new card with
  `parent_id` set to the one it supersedes.
- **No invented clarity.** Scoring must reflect what the human actually stated. Unanswered
  questions keep a dimension low — that is the whole point of the gate.
- **Markdown-first.** Prefer instructions the harness executes over new runtime code. Only
  add scripts under `scripts/` for genuinely deterministic work (hashing, schema checks).

## Testing locally

There is no build step. To exercise the plugin inside Claude Code:

1. Register this directory as a local plugin marketplace and install it:
   ```
   claude plugin marketplace add ./            # from inside Z/
   claude plugin install z@z
   ```
   (Or point the marketplace at the absolute path to this `Z/` directory.)
2. In a scratch project, run the flows and check behavior:
   - **Vague goal** — `z gate "make the app better"` → must NOT pass in round 1; must ask
     about the weakest dimension first.
   - **Sharp goal** — a goal with explicit constraints and a measurable success criterion →
     should pass in a few rounds and write `.z/spec-cards/<id>.json`.
   - **Math check** — recompute `1 − Σ(wᵢcᵢ)` by hand from the card's `ambiguity.dimensions`
     and confirm it equals `ambiguity.score`.
   - **Card + lineage** — `z card` renders the latest card; run `z gate` again on the same
     goal and confirm the new card's `parent_id` points at the previous one.
3. Validate a card's structure, ambiguity math, and content hash:
   ```
   python3 scripts/validate-card.py .z/spec-cards/<id>.json
   ```

## Notes

- The neighboring projects `../ouroboros` (Python) and `../ECC` (Node) are **references
  only** — do not modify them. Z borrows ouroboros' ambiguity gate and immutable-Seed
  ideas but shares no code.
- Directory listings in this workspace can be filtered by the user's `rtk` shell hook
  (plain `ls` may print `(empty)`); use `rtk proxy ls`, `find`, Glob, or the Read tool.
