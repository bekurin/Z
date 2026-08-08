---
topic: cache-key-design
status: accepted
updated_at: 2026-08-06
---

# Cache key design (Redis / local KV)

> Design rules for cache keys written to a shared KV store such as Redis. Copy this into your
> project's `.z/knowledge/` and fill in the `TODO`s. `z gate` reads this note as background so
> cache work does not re-ask what is already decided here.

## Key format

```
{app}:{domain}:{purpose}:{identifier}:v{schema}:{attitude}
```

| Segment | Required | Meaning |
|---------|:--------:|---------|
| `app` | yes | Identifies the server (the writer) that sets the key |
| `domain` | yes | Business domain |
| `purpose` | yes | What the key is for (e.g. daily auth limit, sign-up) |
| `identifier` | yes | The identifier |
| `v{schema}` | optional | Value schema version; bump only when the value's shape changes |
| `attitude` | optional | Extra discriminator when one `purpose` cannot be expressed by a single key |

`v{schema}` is recognized by its `v` prefix, so an `attitude` may appear without a `schema`
without making the position ambiguous.

## Examples

| Use | Key |
|-----|-----|
| Daily auth count | `authn:identify:daily:111222` |
| Sign-up progress | `member:join:progress:2223333` |
| After a value-shape change (v2) | `member:join:progress:2223333:v2` |
| Same purpose split by channel via attitude | `member:join:progress:2223333:app` / `member:join:progress:2223333:web` |

## Rules

- Lowercase only. The exception is an `identifier` whose real value contains uppercase.
- A segment made of several joined words uses kebab-case (e.g. `daily-limit`, `email-verify`).
- Data with no TTL (nothing to expire) belongs in the DB, not the cache. A key that lives
  forever in a shared cache is effectively a memory leak.
- For a look-aside key whose reload cost is high, add about ±3% jitter to the fixed TTL so
  many keys do not expire at the same moment and reload together (a stampede).
- Bump `v{schema}` only when the value's shape changes. Old entries are then never misread by
  new code and fall out via TTL.
- Use `attitude` only when one `purpose` cannot be distinguished by a single key. Do not
  attach it when no disambiguation is needed.

## Project specifics

- `app` identifiers in use: TODO
- Current schema version: TODO (`v1`)
