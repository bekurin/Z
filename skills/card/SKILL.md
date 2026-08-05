---
name: card
description: "Show the latest frozen Clarity Gate spec card and its lineage. Use when the user says 'z card', wants to review the current frozen spec, or asks what the last gate produced."
---

# /z:card

Render the most recent spec card in the current project and trace its lineage.

## Instructions

1. Look in `.z/spec-cards/` in the current project. If it is missing or empty, tell the
   user no card exists yet and suggest `z gate "<goal>"`.
2. Select the latest card — the newest by the timestamp segment of the filename/`id`
   (they sort lexicographically because the timestamp is `YYYYMMDDThhmmssZ`).
3. Render it as a compact human summary:
   - goal, mode, and final `ambiguity.score` (mark **forced** if `forced: true`)
   - constraints
   - numbered success criteria with their `verify`
   - non-goals and assumptions
   - the per-dimension `{weight, clarity}` breakdown
   - the card's `id` and file path
4. **Lineage:** if `parent_id` is set, follow the chain backward and print it oldest→newest:

   ```
   add-csv-export-20260730T142210Z
     └─ add-csv-export-20260731T090000Z   (superseded above)
        └─ add-csv-export-20260731T142210Z  ← current
   ```

5. Offer next steps: implement against this card, or run `z gate` again to mint a new card
   (whose `parent_id` will point at this one).

## Notes

- Cards are immutable — never edit one here. To change a spec, run `z gate` again.
- Optionally verify integrity:
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-card.py .z/spec-cards/<id>.json`.
