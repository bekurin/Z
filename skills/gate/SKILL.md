---
name: gate
description: "Run the Clarity Gate before building. Socratic interview + ambiguity scoring; blocks until ambiguity <= 0.2, then freezes an immutable spec card to .z/spec-cards/. Use when the user says 'z gate', 'clarity gate', 'run the gate', '게이트', or is about to implement a feature from a vague request."
---

# /z:gate

Turn a fuzzy request into a measurably-clear, frozen **spec card** before any code is
written. The gate opens only when `ambiguity <= 0.20`.

## Constants

```
WEIGHTS (greenfield) : goal 0.40 | constraint 0.30 | success 0.30
WEIGHTS (brownfield) : goal 0.35 | constraint 0.26 | success 0.26 | context 0.13   (renormalized, Σ = 1.00)
THRESHOLD            : 0.20
MAX_ROUNDS           : 8
ambiguity = 1 − Σ(weightᵢ × clarityᵢ)
```

> These numbers are mirrored from `${CLAUDE_PLUGIN_ROOT}/scripts/card_lib.py`, the single
> source of truth. If you change one, change it there and in `agents/clarity-interviewer.md`
> and `README.md` — `tests/test_contract_sync.py` fails the build if they drift.

## Instructions

### Step 1 — Get the goal and detect mode

- Take the goal from the skill argument. If none was given, ask the user for it in one
  sentence.
- Decide **mode**: if the request touches an existing codebase (files exist, the user
  references current behavior, or you can see relevant source), use `brownfield` and the
  four-dimension weights; otherwise `greenfield` with three.

### Context reuse (brownfield only)

To score the `context` dimension you may need to read target source files. **Reuse the
per-project context cache so you don't re-read files that have not changed.** Before reading
a source file, consult the cache:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_cache.py" get <path>
```

- **HIT (exit 0):** it prints a short summary you captured on an earlier run — use that and
  do **not** re-read the whole file.
- **MISS (exit 3, prints `MISS`):** read the file, then store a concise summary (the class's
  responsibility, key methods, collaborators, notable gaps) for next time:

  ```bash
  printf '%s' "<summary>" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_cache.py" put <path>
  ```

The cache lives at `.z/context/index.json` in the project and is keyed by each file's content
hash, so a changed file MISSes automatically and gets re-read. It is **advisory** — if a
cached summary lacks a detail you need, read the file anyway. A cached summary is only valid
because you read that exact file content before; it never invents clarity. To reset the cache
manually: `context_cache.py clear` (or `prune` to drop only stale entries).

### Design knowledge (background)

Durable design decisions/conventions (e.g. `api-design`, `cache-key-design`) resolve in two
layers: shared **org** knowledge (a company directory set per repo in `.z/config.json`) and
**project** knowledge under `.z/knowledge/`, where a project note overrides the org note of
the same topic. **Read the relevant ones as background before interviewing** — an already
decided convention is a real constraint you should not re-ask about, and it keeps specs
consistent across tasks and repos.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/knowledge.py" list          # topics + origin + status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/knowledge.py" path <topic>  # resolved file to read
```

Read the file `path` prints (project wins over org). A note with `status: accepted` supplies
`constraint`/`context` clarity (fold it into the card's `constraints`/`assumptions`, e.g.
"follows cache-key-design"). A `check <topic>` reporting `review` means the note's
`related_files` drifted — treat that convention as uncertain and, if it bears on the goal,
raise it rather than assuming it still holds. Do not edit knowledge here: org notes are
read-only in the consuming repo (change them in the company knowledge repo), and project
notes are human-owned — scaffold with `knowledge.py new`, and override an org note by
creating a project note of the same topic.

### Step 2 — Adopt the interviewer role

Read `${CLAUDE_PLUGIN_ROOT}/agents/clarity-interviewer.md` and follow its rubric, score
anchors, questioning strategy, and stop conditions **exactly**. That file is the source of
truth for how to score and what to ask. Do not invent your own scoring.

### Step 3 — Interview loop (≤ MAX_ROUNDS)

Repeat until a stop condition is met:

1. Score every dimension in `[0,1]` against the agent's anchors, from what you know so far.
2. Compute `ambiguity` with the mode's weights.
3. If `ambiguity <= THRESHOLD` → go to Step 4 (PASS).
4. Otherwise pick the dimension contributing the most residual ambiguity and ask a small,
   focused batch (1–3 questions) about **only** that dimension. Use `AskUserQuestion` so
   the user can pick concrete options; always leave room for a free-text answer.
5. Emit the one-line progress breadcrumb before the next round:

   ```
   ◆ ambiguity=0.34  (goal 0.9 / constraint 0.6 / success 0.4)  → next: pin down success criteria
   ```

**Never invent answers to lower the score.** An unanswered question keeps its dimension
low. If the user explicitly says to stop and proceed anyway, treat it as a **forced pass**
(Step 4 with `forced: true`) and record the real failing score.

### Step 4 — Synthesize and freeze the spec card

Build a card object conforming to `${CLAUDE_PLUGIN_ROOT}/schemas/spec-card.schema.json`:

- `id`: `<kebab-slug-of-goal>-<UTC compact timestamp>` (e.g. `add-csv-export-20260730T142210Z`).
- `parent_id`: if `z card` / `.z/spec-cards/` shows a prior card for the same goal that
  this supersedes, set its id; else `null`.
- `mode`, `goal`, `constraints[]`, `success_criteria[]` (each with a concrete `verify`),
  `non_goals[]`, `assumptions[]` (only user-confirmed), `open_questions[]` (empty for a
  clean pass; non-blocking only for a forced pass).
- `ambiguity`: final `score`, `threshold` 0.20, `forced` boolean, and per-dimension
  `{weight, clarity}`.
- `created_at`: current UTC ISO-8601. `frozen`: `true`.
- `content_hash`: compute it with the shared helper so it always matches the validator:

  ```bash
  # after writing the card WITH content_hash set to "" (blank):
  python3 - "$CARD_PATH" <<'PY'
  import json, sys
  sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
  import card_lib
  p = sys.argv[1]
  card = json.load(open(p, encoding="utf-8"))
  card["content_hash"] = card_lib.content_hash(card)
  json.dump(card, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
  PY
  ```
  If no shell is available, still fill every other field and note the hash was not computed.

Write the file to the **project** (not the plugin dir) at `.z/spec-cards/<id>.json` using
the Write tool. Create `.z/spec-cards/` if needed. Cards are append-only — never overwrite
an existing card; a change means a new card with `parent_id` set.

### Step 5 — Report

Print a compact human summary: final ambiguity, the dimension scores, the goal, the
numbered success criteria, non-goals, and the saved card path. If this was a forced pass,
say so plainly and name what remains ambiguous.

End your response with the state breadcrumb:

```
◆ gate PASSED (ambiguity=0.16) → next: implement against .z/spec-cards/<id>.json
```
or, if not passed:
```
◆ gate OPEN (ambiguity=0.38, weakest: success) → next: answer the success-criteria questions, or force a pass
```

## Notes

- This skill is **chat-driven** and needs no MCP server, network, or database — the harness
  (you) performs the scoring against the agent's rubric.
- Keep the interview tight: attack the weakest dimension, stop refining a dimension once it
  clears ~0.9, and don't exceed MAX_ROUNDS.
- Verify any card you freeze with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-card.py <path>`.
