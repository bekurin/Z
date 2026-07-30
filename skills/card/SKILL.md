---
name: card
description: "Show the latest Clarity Gate spec card and its lineage. Use when the user says 'z card', 'show the spec card', 'what did the gate produce', or wants to review the frozen spec before building."
---

# /z:card

Display a frozen spec card produced by `z gate`.

## Instructions

### Step 1 — Locate cards

List `.z/spec-cards/*.json` in the current project (use Glob). If the directory is missing
or empty, tell the user no gate has been run yet and suggest `z gate "<goal>"`. Stop.

### Step 2 — Pick the card

- If the user passed an `id` or partial slug, select the matching card.
- Otherwise select the most recent by the timestamp in the `id` (they sort
  lexicographically, so the greatest string is newest).

Read the chosen card with the Read tool.

### Step 3 — Render

Show a readable summary, not raw JSON:

- **Goal**, **mode**, and **ambiguity** (score vs 0.2 threshold; note if `forced: true`).
- **Dimensions** table: `dimension | weight | clarity`.
- **Constraints**, numbered **success criteria** (`AC1: statement — verify: …`),
  **non-goals**, **assumptions**, and any **open questions**.
- **Provenance**: `created_at`, `content_hash`, and the file path.

### Step 4 — Lineage

If `parent_id` is set, walk the chain (each parent's card by id) and print the generations
oldest→newest as `id → id → id`, so the user can see how the spec evolved. Note how many
generations exist.

End with:

```
◆ showing card <id> (gen N) → next: implement against it, or `z gate` to evolve the spec
```

## Notes

- Cards are immutable. If the user wants to change the spec, do **not** edit the card —
  direct them to `z gate`, which mints a new card with `parent_id` pointing here.
- If `z:validate` / the card validator script exists, mention the user can verify integrity
  with it; otherwise skip.
