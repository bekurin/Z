---
topic: api-design
status: proposed
updated_at: 2026-08-06
---

# API design (HTTP / REST)

> Conventions for HTTP APIs we expose. Copy this into your project's `.z/knowledge/`, adapt
> the rules to your stack, fill in the `TODO`s, and change `status` to `accepted` once agreed.
> `z gate` reads this note as background so API work does not re-decide what is settled here.

## Resource naming

- Nouns, not verbs, in paths. Plural collection names: `/orders`, `/orders/{orderId}`.
- kebab-case for multi-word path segments: `/order-items`.
- Nesting shows ownership one level deep: `/orders/{orderId}/items`. Deeper than that, prefer
  a top-level resource with a filter.
- An action that is not a CRUD operation is a sub-resource with a verb: `POST
  /orders/{orderId}/cancel`, not `POST /cancelOrder`.

| Good | Avoid |
|------|-------|
| `GET /orders` | `GET /getOrders` |
| `GET /orders/8042` | `GET /orders?id=8042` (single by id) |
| `GET /orders/8042/items` | `GET /orderItems?orderId=8042` |
| `POST /orders/8042/cancel` | `POST /cancelOrder` |
| `/order-items` | `/orderItems`, `/order_items` |

## Methods and status codes

- `GET` read (no side effects), `POST` create, `PUT` full replace, `PATCH` partial update,
  `DELETE` remove.
- Success: `200` read/update, `201` create (with a `Location` header), `202` accepted async,
  `204` no body.
- Client error: `400` malformed, `401` unauthenticated, `403` authenticated-but-forbidden,
  `404` not found, `409` conflict, `422` semantic validation failure, `429` rate limited.
- Do not return `200` with an error body. The status code is the contract.

| Request | Result |
|---------|--------|
| `POST /v1/orders` | `201`, `Location: /v1/orders/8042` |
| `GET /v1/orders/8042` | `200` |
| `PATCH /v1/orders/8042` | `200` |
| `DELETE /v1/orders/8042` | `204` |
| `GET /v1/orders/9999` | `404` |
| `POST /v1/orders` (missing `items`) | `422` |
| `POST /v1/orders/8042/cancel` (already shipped) | `409` |

## Versioning

- Version in the path: `/v1/orders`. Bump the major only on a breaking change.
- Additive changes (new optional field, new endpoint) do not bump the version.
- Example: adding an optional `note` field to the order body stays `v1`; removing `items` or
  renaming it to `lineItems` is breaking and becomes `/v2/orders`.
- TODO: current version = `v1`.

## Response shape

- One consistent envelope across endpoints. TODO: pick and record the exact shape, e.g.

  ```json
  { "data": { ... }, "meta": { ... } }
  ```

- Errors follow Problem Details for HTTP APIs (RFC 7807), served as
  `application/problem+json`:

  ```json
  {
    "type": "https://api.example.com/problems/order-not-found",
    "title": "Order not found",
    "status": 404,
    "detail": "Human-readable explanation of this occurrence.",
    "instance": "/v1/orders/9999"
  }
  ```

- `type` is the stable, machine-readable discriminator clients switch on (a URI, not the HTTP
  status). `title` is stable per `type`; `detail` and `instance` are specific to the
  occurrence. Field-level validation errors go in an `errors` extension member.

Example — `GET /v1/orders/8042` → `200`:

```json
{
  "data": {
    "id": "ord_8042",
    "status": "PAID",
    "totalAmount": 15900,
    "currency": "KRW",
    "createdAt": "2026-08-06T02:08:20Z",
    "items": [
      { "id": "itm_1", "name": "Keyboard", "quantity": 1, "unitAmount": 15900 }
    ]
  },
  "meta": {}
}
```

Example — `GET /v1/orders/9999` → `404` (`Content-Type: application/problem+json`):

```json
{
  "type": "https://api.example.com/problems/order-not-found",
  "title": "Order not found",
  "status": 404,
  "detail": "No order with id ord_9999.",
  "instance": "/v1/orders/9999"
}
```

Example — `POST /v1/orders` with an invalid body → `422`:

```json
{
  "type": "https://api.example.com/problems/validation-failed",
  "title": "Request failed validation",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "instance": "/v1/orders",
  "errors": [
    { "field": "items[0].quantity", "code": "MIN", "message": "must be >= 1" }
  ]
}
```

## Collections: pagination, filtering, sorting

- Pagination is mandatory on every collection; never return an unbounded list.
- TODO: pick one style and use it everywhere — cursor (preferred for large or live data) or
  offset.
- Filtering by explicit query params. No free-form query DSL in the URL.
- Sorting: `?sort=-createdAt,name` (leading `-` = descending).

Example — filter + sort:

```
GET /v1/orders?status=paid&created-after=2026-08-01&sort=-createdAt,id
```

Example — cursor pagination, `GET /v1/orders?status=PAID&limit=2`:

```json
{
  "data": [
    { "id": "ord_8042", "status": "PAID" },
    { "id": "ord_8041", "status": "PAID" }
  ],
  "meta": { "nextCursor": "eyJpZCI6Im9yZF84MDQwIn0", "hasMore": true }
}
```

Follow the cursor: `GET /v1/orders?status=PAID&limit=2&cursor=eyJpZCI6Im9yZF84MDQwIn0`.

Example — offset alternative, `GET /v1/orders?page=2&size=20`:

```json
{ "data": [ ... ], "meta": { "page": 2, "size": 20, "total": 137 } }
```

## Field conventions

- JSON field names are camelCase; keep the same casing in requests and responses.
- Timestamps are UTC ISO-8601 strings (`2026-08-06T02:08:20Z`), field names suffixed `At`
  (`createdAt`).
- IDs are opaque strings, never a raw auto-increment integer exposed as a number.
- Money is an integer minor unit plus a currency code, never a float.
- Enums are UPPER_SNAKE_CASE strings, not magic numbers.
- Omit unknown/absent fields rather than sending `null`, unless `null` is a meaningful value.

Example — a member resource showing every convention:

```json
{
  "id": "mbr_2223333",
  "status": "ACTIVE",
  "grade": "GOLD",
  "balance": 15900,
  "currency": "KRW",
  "joinedAt": "2026-08-06T02:08:20Z",
  "deletedAt": null
}
```

## Idempotency and safety

- `GET`, `PUT`, `DELETE` are idempotent; repeating them must not change the result.
- Non-idempotent `POST` that creates money-affecting or duplicate-sensitive resources accepts
  an `Idempotency-Key` header and returns the original result on retry.

Example — a retried payment must not double-charge:

```
POST /v1/payments
Idempotency-Key: 3f8a1c2e-... (client-generated, stable across retries)

{ "orderId": "ord_8042", "amount": 15900, "currency": "KRW" }
```

The first call returns `201` with `payment.id = pay_5501`. A retry with the same
`Idempotency-Key` returns that same `201` / `pay_5501` instead of creating a second payment.

## Project specifics

- Base path / current version: TODO (`/v1`)
- Success response envelope: TODO
- Problem `type` base URI: TODO (`https://api.example.com/problems/`)
- Pagination style: TODO (cursor vs offset)
- Auth scheme: TODO
