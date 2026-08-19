# Z — Development Guide

> This CLAUDE.md is for **local development of the Z plugin**. End users install via the
> plugin marketplace (see [README.md](README.md)); once installed, the skills/agents load
> natively and this file is not needed.

## What Z is

Z is a **lightweight, markdown-first Claude Code plugin** implementing a single idea: a
**Clarity Gate** that scores request ambiguity and blocks implementation until
`ambiguity <= 0.20`, then freezes an immutable spec card. There is **no backend** — no MCP
server, no database, no network. The harness
(Claude) does the scoring by following the agent's rubric; only genuinely deterministic
work (hashing, validation) lives in `scripts/*.py`.

## `z` commands (dev mode)

When the user types one of these, read the matching `SKILL.md` and follow it exactly —
do **not** use the Skill tool, use the Read tool and execute the instructions:

| Input | Action |
|-------|--------|
| `z gate ...` / "clarity gate" / "게이트" | Read `skills/gate/SKILL.md` and follow it |
| `z score ...` | Read `skills/score/SKILL.md` and follow it |
| `z card ...` | Read `skills/card/SKILL.md` and follow it |

The scoring rubric, weights, score anchors, and questioning strategy live in
`agents/clarity-interviewer.md` — that agent file is the source of truth for *how to score*.
The gate skill reads it at Step 2.

## Layout

```
.claude-plugin/plugin.json    # plugin manifest (name "z", skills path)
agents/clarity-interviewer.md # the rubric + scoring + questioning contract
schemas/spec-card.schema.json # frozen spec-card contract (draft-07)
skills/gate/SKILL.md          # interview → score → gate → freeze card
skills/score/SKILL.md         # one-shot score, no card
skills/card/SKILL.md          # show latest card + lineage
hooks/hooks.json              # (optional) build-intent nudge
install.sh                    # install into Claude Code and/or Codex ([claude|codex|all], default auto)
scripts/card_lib.py           # deterministic core: weights, math, hashing (stdlib)
scripts/validate-card.py      # verify a card's structure, math, and hash
scripts/gate-nudge.py         # UserPromptSubmit nudge hook
scripts/context_cache.py      # per-project context cache (get/put/list/prune/clear)
scripts/knowledge.py          # durable design-knowledge store (list/check/touch/new)
templates/knowledge/          # starter design-knowledge notes (cache-key-design, _template)
tests/                        # pytest verification harness (dev-only)
```

Runtime artifacts are written to the **target project** at `.z/spec-cards/<id>.json`,
never into this plugin repo.

## Key invariants (keep these true when editing)

- **The formula is the contract.** `ambiguity = 1 − Σ(weightᵢ × clarityᵢ)`, threshold
  `0.20`. Greenfield weights `0.40/0.30/0.30`; brownfield adds `context` and renormalizes to
  `0.35/0.26/0.26/0.13` (Σ = 1.00).
- **One source of truth.** The weights and threshold live in `scripts/card_lib.py`. The
  markdown files (`agents/clarity-interviewer.md`, `skills/gate/SKILL.md`, `README.md`)
  mirror them for the human/harness. `tests/test_contract_sync.py` fails the build if the
  numbers drift out of sync — so change them in `card_lib.py` and the docs together.
- **Cards are immutable.** Never edit or overwrite a card. A spec change = a new card with
  `parent_id` set to the one it supersedes.
- **No invented clarity.** Scoring must reflect what the human actually stated. Unanswered
  questions keep a dimension low — that is the whole point of the gate.
- **The context cache is advisory and honest.** `scripts/context_cache.py` stores per-file
  summaries under the project's `.z/context/index.json`, keyed by the file's content sha256.
  It exists only to avoid re-reading unchanged code; it must never let a stale or unread file
  raise the `context` score. A changed file's hash MISSes and is re-read. Reset with
  `context_cache.py clear` / `prune`.
- **Three memory layers, distinct lifecycles.** Do not conflate them:
  | Layer | Location | Keyed by | Lifecycle |
  |-------|----------|----------|-----------|
  | file summaries | `.z/context/index.json` | file content sha256 | machine-written, **auto-invalidates** |
  | task specs | `.z/spec-cards/` | card id | **immutable** snapshot per gate |
  | design knowledge | `.z/knowledge/*.md` | topic slug | **human-curated**, advisory staleness |
- **Design knowledge is human-owned + advisory.** `scripts/knowledge.py` never deletes or
  auto-writes a note's body — it only flags `review` when a note's `related_files` drift, and
  re-baselines on `touch`. Cross-task decisions (`api-design`, `cache-key-design`) outlive any
  single code edit, so a changed file flags review rather than invalidating the decision.
  `templates/knowledge/` ships starters to copy into a project's `.z/knowledge/`.
- **Markdown-first.** Prefer instructions the harness executes over new runtime code. Only
  add scripts under `scripts/` for genuinely deterministic work (hashing, schema checks),
  and keep them standard-library-only so the plugin ships zero runtime dependencies.

## The verification harness

The plugin has no build step, but the deterministic surface (the two scripts, the schema,
and the ambiguity/hash math) is covered by a pytest suite under `tests/`.

```bash
python3 -m pip install -r requirements-dev.txt   # pytest + jsonschema (dev only)
python3 -m pytest                                 # run the whole harness
```

What it pins:

- `tests/test_card_lib.py` — the pure math and hashing in `card_lib.py`.
- `tests/test_validate_card.py` — the CLI's exit codes and failure messages, run as a
  subprocess over the fixtures in `tests/fixtures/`.
- `tests/test_schema.py` — valid cards conform to the JSON schema; broken ones are rejected.
- `tests/test_gate_nudge.py` — the hook nudges only on build-intent with no card, and never
  blocks.
- `tests/test_contract_sync.py` — the weights/threshold in the docs match `card_lib.py`.
- `tests/test_context_cache.py` — the cache's HIT/MISS freshness by content hash, plus
  list/prune/clear and malformed-index tolerance, run as a subprocess in a temp project.
- `tests/test_knowledge.py` — the design-knowledge store's advisory staleness (related-file
  drift flags `review`, never deletes), `touch`/`new`/`list`, and the frontmatter parser.

The harness does **not** test Claude's judgment of clarity scores (that is the human-in-the
loop part); it tests everything deterministic around it.

## Testing the plugin inside Claude Code (manual smoke)

1. Register this directory as a local plugin marketplace and install it:
   ```
   ./install.sh            # from inside Z/ — auto-detects Claude Code and/or Codex
   ```
   `install.sh` takes an optional target: `claude` (marketplace + `z` plugin), `codex`
   (renders the skills into `~/.codex/prompts/z-*.md` and a managed block in
   `~/.codex/AGENTS.md`), or `all`. With no argument it installs into every supported CLI on
   `PATH`. The Codex path resolves `${CLAUDE_PLUGIN_ROOT}` to this checkout since Codex has no
   plugin root — re-run after editing a skill to refresh the generated prompts.
2. In a scratch project, run the flows and check behavior:
   - **Vague goal** — `z gate "make the app better"` → must NOT pass in round 1; must ask
     about the weakest dimension first.
   - **Sharp goal** — a goal with explicit constraints and a measurable success criterion →
     should pass in a few rounds and write `.z/spec-cards/<id>.json`.
   - **Math check** — `python3 scripts/validate-card.py .z/spec-cards/<id>.json` → exit 0.
   - **Card + lineage** — `z card` renders the latest card; run `z gate` again on the same
     goal and confirm the new card's `parent_id` points at the previous one.

## Notes

- Any neighboring projects in this workspace (e.g. `../ECC`) are **references only** — do
  not modify them. Z shares no code with them.
- Directory listings in this workspace can be filtered by the user's `rtk` shell hook
  (plain `ls` may print `(empty)`); use `rtk proxy ls`, `find`, Glob, or the Read tool.
