# LatencyLedger — API Specification

> Version: **v1** (`/api/v1/*` for API-key surface, `/api/*` for session surface).
> Status: **Draft — sprint 1 (P0) + planned P1 surface marked as such.**
> Stack constraint: implementable with Python stdlib only (`http.server`,
> `sqlite3`, `urllib.request`, `hashlib`, `hmac`, `secrets`, `json`).
> No external API gateway, no paid third party required to boot.
> Machine-readable contract: [`api.yaml`](./api.yaml) (OpenAPI 3.1).
> Product context: [`product-spec.md`](./product-spec.md) ·
> Backend context: [`architecture.md`](./architecture.md) (`app/router.py`,
> `app/handlers/*.py`, `app/auth.py`, `app/gate.py`, `app/alerts.py`).

## 0. At a glance

| Item | Value |
|---|---|
| Base URL | `https://<host>/` — API under `/api` and `/api/v1` |
| Also: | `GET /healthz`, public HTML at `/r/{slug}` and `/s/{slug}` |
| Format | JSON only for `/api*`; `text/csv` only for `GET …/export?format=csv` |
| Auth | Session cookie (browser) **or** `Authorization: Bearer ll_…` (CI/API) |
| Versioning | URL prefix (`/api/v1`); additive changes only within v1 (§7) |
| Pagination | Cursor (`?cursor=&limit=`) for all list endpoints (§1.4) |
| Error shape | `{"error": "<code>", "detail": "<human>", "request_id": "…"}` (§1.6) |
| Rate limit | Token bucket per tier, `429` + `Retry-After` + `X-RateLimit-*` (§4) |
| Webhooks (outbound) | HMAC-SHA256 signed POSTs, exp. backoff retry, stdlib only (§5) |

Endpoint count (P0): **20 operations**. With P1 surface: **33 operations**.
Full reference in §2; OpenAPI skeleton in `docs/api.yaml`.

---

## 1. REST/JSON conventions

### 1.1 Versioning

- The **URL prefix is the version**: `/api/v1/*` is the public, API-key
  surface and is versioned. `/api/*` (session surface) is unversioned in
  sprint 1 but follows the same conventions, so it can be promoted to
  `/api/v1/*` without a shape change.
- **Within a version, changes are additive only**: new optional fields,
  new endpoints, new enum values. Clients must ignore unknown fields.
- Breaking changes (removed/renamed fields, changed semantics, stricter
  validation that rejects previously-valid requests) require a new prefix
  (`/api/v2/*`) and a 12-month overlap. See §7 for the full policy.
- `Accept` header negotiation of versions (e.g. `Accept: application/vnd.latencyledger.v2+json`)
  is **not** used — no gateway, no content-negotiation machinery in stdlib
  `http.server` beyond reading the header if ever needed.

### 1.2 Resource naming

- **Plural nouns, kebab-case, no verbs in paths** (verbs only as RPC-style
  action suffixes where the action is not a CRUD operation):
  `/api/checks`, `/api/keys`, `/api/projects`, `/api/checks/{id}/ping-now`.
- **IDs**: opaque, URL-safe, `secrets.token_urlsafe(12)` (checks, keys,
  projects, channels) or integer PK (samples, alerts, deliveries) rendered
  as a JSON number. Never sequential user-enumerating IDs for checks.
- **Nested resources are addressed through their parent** when ownership
  matters: `/api/checks/{id}/channels/{channelId}` — a `channelId` that
  belongs to a different check returns `404` (not `403`, to avoid leaking
  existence).
- **Timestamps**: ISO-8601 UTC with `Z`, second precision, e.g.
  `2026-11-08T03:22:00Z`. Stored as `TEXT` via `datetime('now')` in SQLite.
- **Units are in field names**: `ms`, `*_ms`, `*_sec`, `*_bytes`, `*_pct`.
  Latency is always **milliseconds** (`ms`, `p95_ms`), never seconds.

### 1.3 Methods & semantics

| Method | Use | Idempotency |
|---|---|---|
| `GET` | Read. Safe, cacheable only where `Cache-Control` says so. | n/a |
| `POST` | Create a resource, or perform an action (`ping-now`, `gate`, `test`). | Creates are **not** idempotent unless an `Idempotency-Key` is sent (§1.7). |
| `PATCH` | Partial update (only provided fields change). | Idempotent on a fixed body. |
| `DELETE` | Remove. Returns `204` with empty body on success. | Idempotent (second call → `404`). |

No `PUT` in v1 — all updates are partial (`PATCH`), which keeps handlers
in stdlib routing to one code path per resource.

### 1.4 Pagination

All list endpoints use **cursor pagination**:

```
GET /api/checks?cursor=<opaque>&limit=50&sort=-created_at&status=active
```

- `limit`: integer, default `50`, min `1`, max `200`. Out-of-range → `400`.
- `cursor`: opaque value returned as `next_cursor`. The server encodes
  `(last_sort_value, last_id)`; clients must treat it as opaque and not
  construct it. An invalid/foreign cursor → `400 invalid_cursor`.
- Response:

```json
{
  "data": [ /* …items… */ ],
  "next_cursor": "eyJ2IjoiMjAyNi0xMS0wOFQwMzoyMjowMFoiLCJpZCI6ImNoaz…",
  "has_more": true
}
```

- `next_cursor` is `null` and `has_more` is `false` on the last page.
- Offset pagination (`?page=&offset=`) is **not** offered: it drifts under
  concurrent inserts and encodes position in the URL. Cursor over
  `(created_at DESC, id DESC)` is stable in SQLite with one index.

### 1.5 Filtering & sorting

- Filters are **exact-match query params** named after the field:
  `?status=active`, `?project_id=…`, `?kind=regression`, `?sha=abc1234`.
  Unknown filter params are ignored (forward-compat), known filters with
  invalid values → `400`.
- Sorting: `?sort=<field>` or `?sort=-<field>` (leading `-` = descending).
  Default `-created_at` on lists. Allowed fields are listed per endpoint
  in §2 and whitelisted in the handler — **never interpolate `sort` into
  SQL**; map to a fixed `ORDER BY` clause.
- Range filters use explicit params, not operators in names:
  `?from=2026-11-01T00:00:00Z&to=2026-11-08T00:00:00Z`.
- String matching is exact; there are no `*`/`%` wildcard filters in v1
  (avoids `LIKE` escaping bugs and index blowups on SQLite).

### 1.6 Error envelope & status codes

Every error response, on every endpoint, has exactly this shape:

```json
{
  "error": "plan_limit_exceeded",
  "detail": "Free plan allows 3 checks. Upgrade to Pro for 25.",
  "request_id": "req_01JABCDEF1234567890",
  "upgrade_url": "https://latencyledger.example/pricing"
}
```

| Field | Rule |
|---|---|
| `error` | Short `snake_case` machine code. Stable across versions; clients may switch on it. |
| `detail` | Human-readable. May change wording; never parse it. |
| `request_id` | Always present. Echoed as `X-Request-Id` response header. Quote it in support reports. |
| `upgrade_url`, `retry_after_sec`, `fields` | Optional, only when relevant (`fields` on `422 validation_failed`). |

Standard status codes and `error` codes:

| HTTP | `error` | When |
|---|---|---|
| `400` | `invalid_request` / `invalid_cursor` | Malformed JSON, bad param, bad cursor. |
| `401` | `unauthenticated` | Missing/expired session or API key. |
| `402` | `plan_limit_exceeded` | Tier quota hit; body carries `upgrade_url`. |
| `403` | `forbidden` | Authenticated but not owner / not admin. |
| `404` | `not_found` | Resource does not exist **or is not owned by caller** (no existence leak). |
| `405` | `method_not_allowed` | Right path, wrong verb. |
| `409` | `conflict` | e.g. duplicate email on register, duplicate check `slug`. |
| `415` | `unsupported_media_type` | Body is not `application/json` where JSON is required. |
| `422` | `validation_failed` | Syntactically valid JSON, semantically invalid (bad URL, `p95_ms` ≤ 0). Carries `fields`. |
| `429` | `rate_limited` | Token bucket empty; `Retry-After` + `X-RateLimit-*`. |
| `500` | `internal` | Unexpected; `request_id` is the only diagnostic surfaced. |

Success codes: `200` (read/action), `201` (created, with `Location`
header), `204` (deleted / logout), `422` **only** for the CI gate
"budget missed" result (§2.9) — there `422` is a *successful evaluation*,
not a client error, and the body is a gate result, not an error envelope.

### 1.7 Headers, body limits, idempotency

- Requests: `Content-Type: application/json` on all `POST`/`PATCH` with a
  body; `Accept: application/json` preferred (default when omitted).
- **Max body size: 64 KiB** for JSON endpoints (samples ingest included).
  Larger → `413 payload_too_large` (`error: payload_too_large`). Enforced
  while reading the body in `http.server` (`Content-Length` check before
  `read()`), so a huge body never reaches the router.
- `Idempotency-Key: <uuid>` is accepted on `POST /api/v1/checks/{id}/samples`
  and `POST /api/checks`. First execution stores `(key, response)` for
  24 h; a replay returns the stored response with `Idempotent-Replayed: true`.
- Every response carries `X-Request-Id`, `X-Content-Type-Options: nosniff`,
  and `Content-Security-Policy` on HTML pages. API JSON responses carry
  `Cache-Control: no-store` (session/API data must never be cached).

---

## 2. Endpoint reference

Conventions for the tables below: **Auth** = `S` session cookie,
`K` API key (`Bearer ll_…`), `P` public, `A` admin session.
`req`/`res` are JSON unless noted. All error responses use §1.6.

### 2.1 Health

#### `GET /healthz` — P (no auth)

Liveness + readiness for Docker/`docker compose` healthchecks.

```
200 OK
{"status": "ok", "db": "ok", "scheduler": "ok", "time": "2026-11-08T03:22:00Z"}
```

`503` with `{"status": "degraded", "db": "down", …}` if the DB ping fails.
Never includes version-internal details. `Cache-Control: no-store`.

### 2.2 Auth (session surface)

#### `POST /api/auth/register` — P

```http
POST /api/auth/register
{"email": "dev@example.com", "password": "correct horse battery staple"}
201 Created
Set-Cookie: ll_session=<opaque>; HttpOnly; SameSite=Lax; Path=/
{"id": "usr_…", "email": "dev@example.com", "plan": "free", "created_at": "…"}
```

- Password policy: min 12 chars. Hash: `hashlib.pbkdf2_hmac('sha256', …)`
  with a per-user salt, ≥ 200 000 iterations (see `architecture.md`).
- `409 {"error":"conflict",…}` on duplicate email (compare case-insensitively).
- `422 validation_failed` with `fields: {"email": "…", "password": "…"}`.
- Rate-limited per IP: 5 attempts / min (§4).

#### `POST /api/auth/login` — P

Body as register. On success: `200` + `Set-Cookie` as above, body = `me`
object. On bad credentials: `401` with a **generic** message (no
"user not found" vs "wrong password" distinction — anti-enumeration).
Sequence diagram: §3.1.

#### `POST /api/auth/logout` — S

Deletes the session row server-side (instant revocation) and clears the
cookie (`Set-Cookie: ll_session=; Max-Age=0`). Returns `204`.
Idempotent: logging out with an already-invalid cookie still returns `204`.

#### `GET /api/auth/me` — S

`200 {"id","email","plan","created_at"}`. `401` if no/expired session.
Used by the frontend on load to decide "show login vs dashboard".

### 2.3 Checks (URL monitors)

Model (`Check`):

```json
{
  "id": "chk_…", "project_id": null, "name": "Checkout API",
  "url": "https://api.example.com/checkout", "interval_sec": 300,
  "threshold_pct": 20.0, "is_public": false, "slug": null,
  "last_checked_at": "2026-11-08T03:20:00Z", "created_at": "2026-11-08T03:00:00Z"
}
```

#### `GET /api/checks` — S

`?cursor=&limit=&sort=&project_id=&is_public=`. Returns cursor page of
`Check` (§1.4). Only the caller's own checks.

#### `POST /api/checks` — S · `201`

```http
POST /api/checks
{"name": "Checkout API", "url": "https://api.example.com/checkout",
 "interval_sec": 300, "threshold_pct": 20, "project_id": null}
201 Created
Location: /api/checks/chk_…
{ "id": "chk_…", … }
```

Validation: `url` must be `http(s)`, ≤ 2048 chars, and pass the SSRF
guard (hostname must not resolve to private/loopback/link-local —
checked again at sample time). `interval_sec` ∈ {60, 300, 900, 3600} in
sprint 1 (free tier: ≥ 300, §4). Over plan limit → `402`.

#### `GET /api/checks/{id}` — S · `200` — one `Check` or `404`.

#### `PATCH /api/checks/{id}` — S · `200`

Any subset of `name`, `url`, `interval_sec`, `threshold_pct`,
`is_public`, `project_id`. Setting `is_public: true` mints a `slug`
(`secrets.token_urlsafe(8)`) if none exists; setting `false` keeps the
slug but disables the route (returns `404`). Same validation as create.

#### `DELETE /api/checks/{id}` — S · `204`

Deletes the check and (cascade) its samples, alerts, channels, deliveries.
Second call → `404`.

### 2.4 Sampling, series & stats

#### `POST /api/checks/{id}/ping-now` — S · `200`

Runs `N=10` fetches immediately (same `urllib` path as the scheduler,
10 s timeout, redirects off, 1 MB body cap) and returns:

```json
{
  "results": [{"ms": 182, "status": 200}, {"ms": 190, "status": 200}],
  "stats": {"count": 10, "errors": 1, "min_ms": 170, "max_ms": 240,
            "avg_ms": 195, "p50_ms": 188, "p95_ms": 231, "p99_ms": 238}
}
```

Samples are persisted (so the chart updates immediately) and counted
against the ingest rate limit. Errors are counted, not raised.

#### `GET /api/checks/{id}/series` — S · `200`

`?range=24h|7d|30d` (default `24h`), `?bucket=auto`. Returns bucketed
points for the canvas chart:

```json
{"check_id": "chk_…", "range": "24h", "bucket_sec": 900,
 "points": [{"ts": "2026-11-08T03:00:00Z", "avg_ms": 191.2, "p95_ms": 233.0, "samples": 3}]}
```

Empty (`points: []`) when < 2 samples — frontend renders the empty state.

#### `GET /api/checks/{id}/stats` — S · `200`

Lifetime + window stats, computed server-side in `stats.py`:

```json
{"window": "24h", "count": 288, "errors": 0, "min_ms": 165, "max_ms": 312,
 "avg_ms": 201, "p50_ms": 196, "p95_ms": 266, "p99_ms": 301,
 "baseline_p95_ms": 244, "drift_pct": 9.0}
```

`baseline_p95_ms` = rolling median of daily p95 over the last 7 days;
`drift_pct = (p95 - baseline) / baseline * 100`. `null` baseline when
fewer than 50 samples in history (detector is armed only at ≥ 50).

#### `GET /api/checks/{id}/alerts` — S · `200` (cursor list)

`?kind=regression|down&cursor=&limit=`. Items:

```json
{"id": 7, "kind": "regression", "observed_p95_ms": 389, "baseline_p95_ms": 212,
 "created_at": "…", "acked_at": null}
```

#### `GET /api/checks/{id}/export` — S · `200`

`?format=json` (default) or `?format=csv`, `?from=&to=`. JSON returns the
series shape; CSV streams `text/csv` with header
`ts,ms,status,size_bytes,git_sha,note`. Auth required; respects the
caller's history retention (§4).

### 2.5 API keys (CI credentials)

Model (`ApiKey`): `{ "id", "prefix": "ll_ab12", "created_at", "revoked_at" }` —
the secret is shown **once** at creation and never stored (SHA-256 hash only).

#### `POST /api/keys` — S · `201`

```http
POST /api/keys
{}
201 Created
{"id": "key_…", "prefix": "ll_ab12", "created_at": "…",
 "secret": "ll_ab12…rest-shown-once"}
```

#### `GET /api/keys` — S · `200` — cursor list of `ApiKey` (no secrets).

#### `DELETE /api/keys/{id}` — S · `204` — sets `revoked_at`; takes effect
on the next request (no caching of key validity).

### 2.6 CI surface (`/api/v1/*`, API-key auth)

#### `POST /api/v1/checks/{id}/samples` — K · `201`

Ingest one externally-measured sample (from CI, a load harness, or a
custom probe). This is the write path the GitHub Actions example uses.

```http
POST /api/v1/checks/{id}/samples
Authorization: Bearer ll_…
{"ms": 212, "status": 200, "size_bytes": 4312, "git_sha": "abc1234", "note": "ci-nightly"}
201 Created
{"id": 1042, "check_id": "chk_…", "ts": "…"}
```

- `ms ≥ 0` required; `status` 100–599; `git_sha` ≤ 40 chars hex-ish
  (validated loosely — any string ≤ 64 chars, stored as-is).
- Triggers the regression detector synchronously (or enqueues, if the
  ingest queue is backlogged — same `detector.py` entry point).
- `Idempotency-Key` supported (§1.7). Rate limit: 100/min/key (§4).

#### `POST /api/v1/checks/{id}/gate` — K · `200` / `422`

The CI gate. Body: `{"p95_ms": 400}` and optionally `{"window": "24h"}`.

```http
POST /api/v1/checks/{id}/gate
Authorization: Bearer ll_…
{"p95_ms": 400}
200 OK
{"pass": true, "observed_p95_ms": 266, "budget_p95_ms": 400, "window": "24h", "samples": 288}
```

Under budget → `200 {"pass": true, …}` (exit 0 in CI). Over budget →
`422 {"pass": false, "observed_p95_ms": 512, …}` — a *successful
evaluation*, not an error envelope; CI scripts `jq -e .pass` or checks
the status code. Fewer than 5 samples in window → `422` with
`{"pass": false, "reason": "insufficient_samples", "samples": 2}`.
The GitHub Actions step treats `200` as green and anything else as red.

### 2.7 Public report

#### `GET /api/public/r/{slug}` — P · `200`

JSON twin of the HTML report at `/r/{slug}` (same slug, same data, no
auth). Body = `{check name, url, stats, series}` — **no** user id, email,
API keys, thresholds, or alert channels. `is_public: false` or unknown
slug → `404` (identical response either way). HTML is served at
`/r/{slug}` by `handlers/public.py` with the same data and a strict CSP.

### 2.8 Projects (P1)

`GET /api/projects`, `POST /api/projects` (`{"name"}` → `201`),
`GET|PATCH|DELETE /api/projects/{id}`. `Check.project_id` filters the
check list. Team/workspaces (P2) extend this with roles; not in v1 wire
format.

### 2.9 Alert channels & deliveries (P1, webhook P0 for regression)

#### `GET /api/checks/{id}/channels` — S · cursor list of
`{"id","kind":"email|webhook|chat","target","created_at"}`.
#### `POST /api/checks/{id}/channels` — S · `201`
`{"kind": "webhook", "target": "https://hooks.example.com/x"}`.
Webhook targets must be `https` (http allowed only for loopback in dev).
#### `POST /api/checks/{id}/channels/{channelId}/test` — S · `200`
Sends a signed test event (§5) and returns the delivery record.
#### `DELETE /api/checks/{id}/channels/{channelId}` — S · `204`.
#### `GET /api/checks/{id}/deliveries` — S · cursor list of
`{"id","alert_id","channel_id","status","attempts","ts"}`.

### 2.10 Status pages (P1)

`POST /api/status-pages` (`{"name","slug"}`), `GET /api/status-pages`,
`GET|DELETE /api/status-pages/{id}`, `POST …/status-pages/{id}/checks`
(`{"check_id"}`), public HTML at `/s/{slug}`. 90-day uptime % is computed
from samples; incidents are auto-generated from `down`/`regression` alerts.

### 2.11 Admin (plan management, sprint-1 manual billing)

#### `PATCH /api/admin/users/{userId}/plan` — A · `200`
`{"plan": "pro"}` → returns the user. Requires an admin flag on the
session user; everyone else gets `403`. This is the no-Stripe billing
path from the product spec (Stripe stays behind an env flag in P1).

### 2.12 Endpoint summary

| # | Method | Path | Auth | Since |
|---|---|---|---|---|
| 1 | GET | `/healthz` | P | P0 |
| 2 | POST | `/api/auth/register` | P | P0 |
| 3 | POST | `/api/auth/login` | P | P0 |
| 4 | POST | `/api/auth/logout` | S | P0 |
| 5 | GET | `/api/auth/me` | S | P0 |
| 6 | GET | `/api/checks` | S | P0 |
| 7 | POST | `/api/checks` | S | P0 |
| 8 | GET | `/api/checks/{id}` | S | P0 |
| 9 | PATCH | `/api/checks/{id}` | S | P0 |
| 10 | DELETE | `/api/checks/{id}` | S | P0 |
| 11 | POST | `/api/checks/{id}/ping-now` | S | P0 |
| 12 | GET | `/api/checks/{id}/series` | S | P0 |
| 13 | GET | `/api/checks/{id}/stats` | S | P0 |
| 14 | GET | `/api/checks/{id}/alerts` | S | P0 |
| 15 | GET | `/api/checks/{id}/export` | S | P1 |
| 16 | POST | `/api/keys` | S | P0 |
| 17 | GET | `/api/keys` | S | P0 |
| 18 | DELETE | `/api/keys/{id}` | S | P0 |
| 19 | POST | `/api/v1/checks/{id}/samples` | K | P0 |
| 20 | POST | `/api/v1/checks/{id}/gate` | K | P0 |
| 21 | GET | `/api/public/r/{slug}` | P | P0 |
| 22 | GET | `/api/projects` | S | P1 |
| 23 | POST | `/api/projects` | S | P1 |
| 24 | GET | `/api/projects/{id}` | S | P1 |
| 25 | PATCH | `/api/projects/{id}` | S | P1 |
| 26 | DELETE | `/api/projects/{id}` | S | P1 |
| 27 | GET | `/api/checks/{id}/channels` | S | P1 |
| 28 | POST | `/api/checks/{id}/channels` | S | P1 |
| 29 | POST | `/api/checks/{id}/channels/{channelId}/test` | S | P1 |
| 30 | DELETE | `/api/checks/{id}/channels/{channelId}` | S | P1 |
| 31 | GET | `/api/checks/{id}/deliveries` | S | P1 |
| 32 | GET | `/api/status-pages` | S | P1 |
| 33 | POST | `/api/status-pages` | S | P1 |
| 34 | GET | `/api/status-pages/{id}` | S | P1 |
| 35 | DELETE | `/api/status-pages/{id}` | S | P1 |
| 36 | POST | `/api/status-pages/{id}/checks` | S | P1 |
| 37 | PATCH | `/api/admin/users/{userId}/plan` | A | P1 (admin stub P0) |

---

## 3. Authentication flows

### 3.1 Login (session cookie)

```
Browser                LatencyLedger (http.server)        SQLite
-------                ----------------------------        ------
POST /api/auth/login
{email, password}
      |----------------->|  lookup user by email
      |                  |--------------->| SELECT … WHERE email=?
      |                  |<---------------| row (pw_hash, salt)
      |                  |  pbkdf2_hmac(pw, salt, 200k)
      |                  |  compare_digest(candidate, stored)
      |                  |  -- on mismatch: 401 generic (no detail)
      |                  |  token = secrets.token_urlsafe(32)
      |                  |--------------->| INSERT INTO sessions
      |  200 + Set-Cookie: ll_session=…; HttpOnly; SameSite=Lax
      |<-----------------|  {"id","email","plan"}
```

Subsequent requests send `Cookie: ll_session=…`; the handler resolves it
to a `user_id` via the `sessions` table (a DB hit per request, which is
what makes logout instant). Expired/unknown cookie → `401 unauthenticated`.

### 3.2 Registration

Same as login, plus: validate → `INSERT INTO users` (unique email;
race → `409`) → create session → `201` + cookie. The user lands logged
in; no separate "confirm email" step in sprint 1 (documented risk).

### 3.3 Refresh (session)

There is **no refresh token** in v1: the session cookie *is* the
credential, with a server-side `expires_at` (30 days, sliding — each
authenticated request extends it, capped at 90 days from creation).
Sliding expiry is implemented as one `UPDATE sessions SET expires_at=…`
per request; no client-visible refresh call exists. If the team later
wants a hard refresh model, it is a new `/api/auth/refresh` endpoint and
is backward-compatible (additive, §7).

### 3.4 Logout & revocation

```
Browser                LatencyLedger
-------                -------------
POST /api/auth/logout
Cookie: ll_session=…
      |----------------->|  DELETE FROM sessions WHERE id=?
      |  204 + Set-Cookie: ll_session=; Max-Age=0
      |<-----------------|  (old cookie is now a 401 everywhere)
```

### 3.5 API key (CI) flow

```
CI (GitHub Actions)    LatencyLedger
-------------------    -------------
POST /api/v1/checks/{id}/gate
Authorization: Bearer ll_<secret>
{"p95_ms": 400}
      |----------------->|  sha256(secret) -> lookup api_keys.hash
      |                  |  revoked_at IS NULL? compare_digest
      |  200 {"pass": true, …}   (or 422 {"pass": false, …})
      |<-----------------|
```

Keys are generated in the browser UI (`POST /api/keys`, secret shown
once), stored as hashes only, and revoked by `DELETE /api/keys/{id}`
(`revoked_at` set; checked on every request — no validity cache).

### 3.6 OAuth (P2 stub)

`OAUTH_ENABLED=0` by default; when `0`, no OAuth routes are registered
and the app boots with no provider keys. Enabling it adds
`GET /api/auth/oauth/{provider}/start` + `…/callback` behind the same
session issuance as §3.1. Not part of the v1 wire contract.

---

## 4. Rate limiting & quota design per tier

Two distinct mechanisms: **rate limits** (requests per minute — abuse
control) and **plan quotas** (checks/history — billing). Both are
enforced in-process with a token bucket / table lookup — no gateway.

### 4.1 Rate limits (token bucket, in-memory)

Keyed by `(bucket, identity)` where identity is IP for unauthenticated
routes and user/key id otherwise. Refill continuously at
`limit/60` tokens/sec; burst = `limit`. On exhaustion: `429` with

```
Retry-After: 12
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 2026-11-08T03:23:00Z
```

| Bucket | Limit | Applies to |
|---|---|---|
| `login` | 5/min/IP | `POST /api/auth/login`, `/api/auth/register` |
| `read` | 300/min/user | all `GET /api/*` |
| `write` | 60/min/user | `POST`/`PATCH`/`DELETE /api/*` (session) |
| `ingest` | 100/min/key | `POST /api/v1/…/samples` |
| `gate` | 60/min/key | `POST /api/v1/…/gate` |
| `ping-now` | 10/min/check | `POST /api/checks/{id}/ping-now` (protects the sampler) |
| `public` | 60/min/IP | `GET /api/public/r/{slug}`, `/r/{slug}`, `/s/{slug}` |
| `webhook-out` | 30/min/channel | outbound alert deliveries (§5) |

In-memory buckets are per-process; with the split web/worker deployment
(`architecture.md`) the web process is the only one that needs them, and
a restart merely resets bursts — acceptable for sprint 1, documented as
a known limitation (a SQLite-backed bucket table is the migration path).

### 4.2 Plan quotas

Enforced on check-create and on history reads via `plan_limits`:

| | Free | Pro ($9/mo) | Team ($29/mo) |
|---|---|---|---|
| Max checks | 3 | 25 | 100 |
| Min interval | 300 s (5 min) | 60 s (1 min) | 60 s + multi-region (P2) |
| History retention | 7 days | 90 days | 1 year |
| Alert channels | 1 (email) | email + webhook + chat | all + status pages |
| CI gate projects | 1 | unlimited | unlimited |
| API keys | 1 | 5 | 20 |
| Public report links | yes | yes | yes + custom domain (P2) |

- Over-quota create → `402 {"error":"plan_limit_exceeded","upgrade_url":…}`.
- History older than retention is pruned by a daily job and is excluded
  from `series`/`stats`/`export` responses (no error — the window just
  shrinks).
- `min_interval` is validated at check-create/`PATCH` → `422` with
  `fields: {"interval_sec": "Free plan minimum is 300s"}`.

---

## 5. Webhook design (outbound alert deliveries)

Applicable: regression alerts (P0) and P1 alert channels (email, webhook,
chat). This section specifies the **webhook** kind; email/chat reuse the
same event payload and retry machinery.

### 5.1 Events

| Event `type` | Fired when |
|---|---|
| `alert.regression` | p95 rises > `threshold_pct` (default 20%) over the 7-day rolling baseline, ≥ 50 samples, once per 6 h cooldown per check. |
| `alert.down` | A sample has a network error or `status ≥ 500` (P1; P0 ships regression). |
| `alert.resolved` | First subsequent window back under baseline + hysteresis (P1). |
| `ping.test` | Manual "send test" from the UI (`…/channels/{id}/test`). |

### 5.2 Payload

```json
{
  "id": "evt_01JABC…", "type": "alert.regression",
  "created_at": "2026-11-08T03:22:00Z",
  "check": {"id": "chk_…", "name": "Checkout API", "url": "https://…"},
  "observed_p95_ms": 389, "baseline_p95_ms": 212, "drift_pct": 83.5,
  "last_git_sha": "abc1234"
}
```

`POST` to the channel `target` with `Content-Type: application/json`.

### 5.3 Signature scheme (HMAC, stdlib)

Each webhook channel has a per-channel secret (generated at channel
creation, shown once, stored as a SHA-256 hash like API keys).
Every delivery sends:

```
X-LatencyLedger-Event: alert.regression
X-LatencyLedger-Delivery: del_01JABC…
X-LatencyLedger-Timestamp: 2026-11-08T03:22:00Z
X-LatencyLedger-Signature: v1=<hex hmac-sha256>
```

where `signature = HMAC_SHA256(secret, "<timestamp>.<raw_body>")`
using `hmac.new(secret, msg, hashlib.sha256).hexdigest()` — stdlib only.
Receivers verify with `hmac.compare_digest` and reject timestamps older
than 5 minutes (replay window). The secret never travels in the request.

Receiver verification sketch (Python stdlib):

```python
import hashlib, hmac
expected = hmac.new(secret, f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
assert hmac.compare_digest("v1=" + expected, header)
```

### 5.4 Retry policy

- Success = any `2xx` within 10 s. `4xx` (except `429`) = permanent
  failure, no retry. `429`, `5xx`, timeouts, DNS/TCP errors = retryable.
- Backoff (per delivery): attempts at `t+0`, `+30 s`, `+5 min`,
  `+30 min` (4 attempts), with ±20% jitter. `Retry-After` from a `429`
  overrides the schedule when larger.
- Every attempt is recorded in `deliveries` (`status`, `attempts`, `ts`);
  after the final attempt the alert is marked `delivery_failed` and
  surfaced in `GET …/deliveries` — a failed webhook never blocks ingest.
- Delivery runs on the scheduler thread pool; a backlogged queue sheds
  load by dropping `ping.test` first, never `alert.regression`.

### 5.5 Chat channels (P1)

Slack/Discord incoming webhooks receive the same JSON payload wrapped
as `{"text": "…"}` (Slack) or `{"content": "…"}` (Discord) — the signed
raw body is still the §5.2 payload for the `X-LatencyLedger-*` headers,
so verification is identical.

---

## 6. Implementation notes (stdlib `http.server`)

- One `BaseHTTPRequestHandler` subclass; routing is a list of
  `(method, regex, handler)` in `app/router.py` — exactly the table in
  §2.12. No framework, no gateway: auth, rate limiting, and CORS are
  handler-level concerns.
- **CORS**: the frontend is same-origin (static files served by the same
  server), so no CORS is needed in the default deployment. If the API is
  ever split from the frontend, `Access-Control-Allow-Origin` must be an
  explicit allowlist with `Allow-Credentials: true` — never `*` with
  credentials. Preflight (`OPTIONS`) is handled by the router.
- **Concurrency**: `ThreadingHTTPServer` + a single-writer SQLite queue
  (WAL mode). Handlers are plain functions `(req) -> (status, body, headers)`;
  JSON parsing/dumping is `json` stdlib; body cap enforced before `read()`.
- **IDs & secrets**: `secrets.token_urlsafe` everywhere; password hashing
  `hashlib.pbkdf2_hmac`; key/secret storage `hashlib.sha256(...).hexdigest()`
  with `hmac.compare_digest` on lookup.

---

## 7. API changelog / versioning policy

| Version | Date | Change |
|---|---|---|
| v1.0 (this spec) | 2026-11-08 | Initial contract: auth, checks, sampling, gate, public report (P0). Projects/channels/status-pages designed, ship in P1 under the same v1 prefix. |
| v1.1 (planned, P1) | — | Projects, alert channels, deliveries, status pages, CSV export. **Additive only** — no v1.0 client breaks. |
| v2 (future, if ever) | — | Only for breaking changes: 12-month overlap with v1, `Deprecation` + `Sunset` headers on v1 (≥ 6 months notice), migration guide in `docs/`. |

Rules:

1. Additive changes ship under the current prefix with a minor bump and
   a changelog entry here + in `api.yaml` (`info.version`).
2. No field is ever removed or re-typed within a version; deprecated
   fields are marked `deprecated: true` in OpenAPI for **two** minor
   versions before removal (which itself requires a major version).
3. Error `error` codes are part of the contract: new codes may be added,
   existing codes are never reused for a different meaning.
4. `docs/api.yaml` is the source of truth for shapes; this document is
   the source of truth for behaviour. If they disagree, the YAML wins
   for types and this document wins for semantics, and the discrepancy
   is fixed in the next commit.

---

## 8. SDK-less client guide (browser JS, `fetch`)

No SDK is shipped. The frontend (`app/static/app.js`) and any external
page use plain `fetch` with `credentials: "include"` (same-origin
session cookie). Everything below is copy-pasteable.

### 8.1 Small helpers

```js
const API = ""; // same origin; use "https://ledger.example.com" cross-origin

async function api(path, { method = "GET", body, key } = {}) {
  const res = await fetch(API + path, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { Authorization: `Bearer ${key}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok && data?.error) {
    const err = new Error(data.detail || data.error);
    err.code = data.error; err.status = res.status;
    err.requestId = data.request_id; err.data = data;
    throw err;
  }
  return { status: res.status, data, headers: res.headers };
}
```

### 8.2 Login, then load checks

```js
await api("/api/auth/login", {
  method: "POST",
  body: { email: "dev@example.com", password: "…" },
}); // sets the ll_session cookie automatically

const { data } = await api("/api/checks?limit=50");
for (const check of data.data) renderRow(check);
const next = data.next_cursor; // pass back as ?cursor=… for page 2
```

### 8.3 Create a check, ping it now, draw the chart

```js
const { data: check } = await api("/api/checks", {
  method: "POST",
  body: { name: "Checkout API", url: "https://api.example.com/checkout", interval_sec: 300 },
});

const { data: ping } = await api(`/api/checks/${check.id}/ping-now`, { method: "POST" });
console.log(ping.stats.p95_ms); // 231

const { data: series } = await api(`/api/checks/${check.id}/series?range=24h`);
drawSparkline(canvasEl, series.points.map(p => p.p95_ms)); // hand-rolled canvas, app.js
```

### 8.4 CI usage from GitHub Actions (no browser needed)

```yaml
- name: Latency gate
  run: |
    curl -fsS -X POST "https://ledger.example.com/api/v1/checks/${{ vars.CHECK_ID }}/gate" \
      -H "Authorization: Bearer ${{ secrets.LL_API_KEY }}" \
      -H "Content-Type: application/json" \
      -d '{"p95_ms": 400}'
  # exit 0 on 200 {"pass":true}; non-zero on 422 {"pass":false}
```

And to record a CI-measured sample before gating:

```bash
curl -fsS -X POST "https://ledger.example.com/api/v1/checks/$CHECK_ID/samples" \
  -H "Authorization: Bearer $LL_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $GITHUB_SHA-$GITHUB_RUN_ID" \
  -d "{\"ms\": 212, \"status\": 200, \"git_sha\": \"$GITHUB_SHA\"}"
```

### 8.5 Error handling & rate limits in the client

```js
try {
  await api("/api/checks");
} catch (e) {
  if (e.code === "rate_limited") {
    const retryAfter = +e.data.retry_after_sec || 10;
    await new Promise(r => setTimeout(r, retryAfter * 1000));
  } else if (e.code === "plan_limit_exceeded") {
    location.href = e.data.upgrade_url;
  } else if (e.code === "unauthenticated") {
    location.href = "/login";
  } else {
    toast(`Something went wrong (${e.requestId})`);
  }
}
```

### 8.6 Verifying a webhook signature (receiver side, JS)

```js
import { createHmac, timingSafeEqual } from "node:crypto";

function verify(rawBody, ts, header, secret) {
  const expected = "v1=" + createHmac("sha256", secret).update(`${ts}.`).update(rawBody).digest("hex");
  return timingSafeEqual(Buffer.from(expected), Buffer.from(header));
}
```

(The Python stdlib equivalent is in §5.3.)

---

## 9. OpenAPI

[`docs/api.yaml`](./api.yaml) contains the OpenAPI 3.1 skeleton for the
whole API: all 37 operations from §2.12, shared `Error`, `Check`,
`ApiKey`, `Stats`, `Series`, `Alert`, `GateResult`, and `WebhookEvent`
schemas, and the `ll_session` cookie + `Bearer ll_…` security schemes.
It is generated from this document and must be kept in sync (§7 rule 4).
Validate with any OpenAPI 3.1 tooling; the file is plain YAML with no
build step.
