# LatencyLedger — Backend Specification

> Source docs: `docs/product-spec.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/design-system.md` (main branch).
> Stack: **Python 3.11+ stdlib only** (`http.server`/`wsgiref`, `sqlite3`, `urllib.request`, `hashlib`, `secrets`, `smtplib`, `logging`, `threading`). **No pip dependencies required to boot** (`requirements.txt` is empty / declares `python>=3.11`). No external service required to boot; SMTP, OAuth, and Stripe are all disabled without env vars. SQLite via stdlib `sqlite3` (WAL mode). This spec is the backend contract for sprint 1 (P0) + sprint 2 (P1) + later (P2) — P2 items are marked and stubbed.

---

## 0. Terminology & conventions

- **Base URLs:** session-cookie API under `/api/*`; API-key API under `/api/v1/*`; public (no-auth) under `/r/{slug}` and `/s/{slug}`.
- **IDs:** opaque URL-safe strings (`secrets.token_urlsafe` / `uuid4().hex`) for `checks.id`, `api_keys.id`, `alert_channels.id`, `projects.id`; integer autoincrement for high-volume append-only tables (`samples`, `alerts`, `deliveries`, `jobs`).
- **Timestamps:** UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`), second precision. All `*_at` / `ts` columns are `TEXT`.
- **IDs in paths** are percent-decoded and validated; unknown IDs return `404` (never leak existence cross-user — see §3 RBAC).
- **Pagination:** `?limit=` (default 50, max 200) + `?offset=` (default 0); list responses return `{ "data": [...], "limit": N, "offset": N, "total": N }` where applicable.
- **Errors (all endpoints):** `{"error": "<machine_code>", "detail": "<human message>", "request_id": "<id>"}`. Codes: `400` validation, `401` unauthenticated, `403` forbidden/over-plan, `404` not found / not owned, `409` conflict (e.g. duplicate email/slug), `422` business rule failed (CI gate over budget), `429` rate limited, `500` internal. `402` reserved for over-plan hard block (see §4.9). `405` method not allowed, `413` body too large.
- **Content types:** request/response `application/json; charset=utf-8`; export streams `text/csv` or `application/json`. Max request body `64 KiB` (JSON) enforced → `413`.
- **Headers on every response:** `X-Request-Id`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy` (strict, see §10), `Referrer-Policy: no-referrer`, `X-Frame-Options: SAMEORIGIN`. JSON responses also `Cache-Control: no-store` for authenticated endpoints.

---

## 1. API contract

### 1.1 Conventions

| Aspect | Rule |
|---|---|
| Auth (browser) | `HttpOnly; SameSite=Lax; Path=/` session cookie `ll_session` (see §3). `Authorization` header not used for `/api/*`. |
| Auth (CI/API) | `Authorization: Bearer ll_<32 chars>` on `/api/v1/*`. Also accepts `X-API-Key` as fallback. Session cookie alone does **not** authorize `/api/v1/*` gate/ingest (key required except where noted). |
| Public | `/r/{slug}`, `/s/{slug}`, `/healthz`, `/metrics`, static assets — no auth. Public report must never leak owner email, API keys, thresholds, or channel targets. |
| RBAC | Roles: `admin`, `user`, `anon` (anon = public endpoints only). Team roles (`owner`/`member`) are P2 and live on `workspaces`/`workspace_members` (§2). Every authenticated route resolves the user from session or key, then checks ownership (`resource.user_id = actor.id`) or `admin`. Cross-user access → `404` (not `403`) to avoid enumeration. |

### 1.2 Auth & user endpoints

| # | Method & path | Auth | Request | Response (200/201) | Errors |
|---|---|---|---|---|---|
| A1 | `POST /api/auth/register` | anon | `{ "email": string, "password": string }` | `201 { "user": { "id": str, "email": str, "plan": str, "created_at": ts } }` + sets session cookie | `400` bad email / short password (<10 chars) / >2048 total body; `409` email exists |
| A2 | `POST /api/auth/login` | anon | `{ "email": string, "password": string }` | `200 { "user": {...} }` + sets session cookie | `400` malformed; `401` bad credentials (generic message, constant-time); `429` rate limited (5/min/IP) |
| A3 | `POST /api/auth/logout` | user | — | `204` (clears cookie, deletes session row) | `401` if no session |
| A4 | `GET /api/auth/me` | user | — | `200 { "user": {...} }` | `401` |
| A5 | `PATCH /api/auth/me` | user | `{ "email"?: str, "password"?: str }` (email change requires re-auth: `current_password`) | `200 { "user": {...} }` | `400` validation; `401` re-auth failed / no session; `409` email taken |
| A6 | `POST /api/auth/oauth/start` (P2 stub) | anon | `{ "provider": "github"\|"google" }` | `501 { "error": "oauth_disabled" }` unless `OAUTH_ENABLED=1` + provider keys set; when enabled `302` to provider | `501` when disabled; `400` unknown provider |
| A7 | `GET /api/auth/oauth/callback` (P2 stub) | anon | `?code=&state=` | `501` unless enabled; when enabled `302` to `/` + sets session cookie | `400` bad state; `501` disabled |
| A8 | `POST /api/admin/plan-toggle` | admin | `{ "email": str, "plan": "free"\|"pro"\|"team" }` | `200 { "user": {...} }` (manual plan toggle until Stripe P1) | `401/403/404` |
| A9 | `POST /api/admin/users/{id}/plan` | admin | `{ "plan": str }` | `200 { "user": {...} }` | `401/403/404/400` |

### 1.3 API keys (P0)

| # | Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|---|
| K1 | `POST /api/keys` | user (session) | `{ "name"?: string ≤64 }` | `201 { "id": str, "prefix": str, "key": "ll_…" (shown once), "created_at": ts }` | `400` name too long; `401`; `403` plan limit (free ≤2 keys) |
| K2 | `GET /api/keys` | user | — | `200 { "data": [{ "id","prefix","name","created_at","revoked_at" }] }` (never returns raw key or hash) | `401` |
| K3 | `DELETE /api/keys/{id}` | user (owner) / admin | — | `204` (soft revoke: sets `revoked_at`; immediate effect) | `401/404` |

### 1.4 Checks CRUD (P0)

| # | Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|---|
| C1 | `GET /api/checks` | user | `?limit=&offset=&project_id=` | `200 { "data": [Check], "total": N }` where `Check = { id, name, url, interval_sec, threshold_pct, is_public, slug, project_id, last_checked_at, created_at, last_p95_ms?, status? }` | `401` |
| C2 | `POST /api/checks` | user | `{ "name": str(1..64), "url": str(1..2048), "interval_sec": int, "threshold_pct"?: float, "project_id"?: str (P1) }` | `201 Check` | `400` non-http(s), bad URL, SSRF-blocked host pattern, interval not in {60,300,900,3600} or below plan min; `403` over plan check count; `404` project not owned (P1) |
| C3 | `GET /api/checks/{id}` | user (owner) | — | `200 Check` | `401/404` |
| C4 | `PATCH /api/checks/{id}` | user (owner) | any subset of `{ name, url, interval_sec, threshold_pct, is_public }` | `200 Check` | `400` validation; `401/404`; `403` plan min-interval violation |
| C5 | `DELETE /api/checks/{id}` | user (owner) | — | `204` (cascades samples/alerts/channels) | `401/404` |
| C6 | `POST /api/checks/{id}/ping-now` | user (owner) | `{ "count"?: int =10 (1..50) }` | `200 { "samples": [{ "ms": float|null, "status": int|null, "error"?: str }], "stats": Stats, "checked_at": ts }` (persists samples, see §4.2) | `400` bad count; `401/404` |

### 1.5 History, stats, alerts (P0)

| # | Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|---|
| X1 | `GET /api/checks/{id}/series` | user (owner) | `?range=24h\|7d\|30d (default 24h)&bucket=tight` | `200 { "check_id": str, "range": str, "points": [{ "ts": ts, "avg_ms": float, "p95_ms": float, "count": int }], "baseline_p95_ms": float|null }` — bucketed avg+p95 (see §4.3) | `400` bad range; `401/404` |
| X2 | `GET /api/checks/{id}/stats` | user (owner) | `?window=24h\|7d\|30d (default 24h)` | `200 Stats = { "window", "count", "error_count", "min_ms", "max_ms", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "baseline_p95_ms": float|null, "uptime_pct": float }` | `401/404` |
| X3 | `GET /api/checks/{id}/alerts` | user (owner) | `?kind=&limit=&offset=` | `200 { "data": [{ "id", "kind", "observed_p95_ms", "baseline_p95_ms", "created_at", "acked_at" }] }` | `401/404` |
| X4 | `PATCH /api/alerts/{id}/ack` | user (owner of check) | — | `200 Alert` (sets `acked_at`) | `401/404` |
| X5 | `GET /api/checks/{id}/export` (P1) | user (owner) | `?format=json\|csv (default json)&from=&to=` | `200` streamed JSON or CSV (`Content-Disposition: attachment`) | `400` bad format/range; `401/404` |

### 1.6 CI / v1 API (API-key auth)

| # | Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|---|
| V1 | `POST /api/v1/checks/{id}/samples` | API key (owner of check) | `{ "ms": float ≥0, "status": int 100..599, "size_bytes"?: int, "sha"?: str ≤40, "note"?: str ≤500 }` | `201 { "sample_id": int, "ts": ts }` (also triggers detector §4.4) | `400` validation; `401` bad/revoked key; `404` check not owned by key's user; `429` rate limited (100/min/key) |
| V2 | `POST /api/v1/checks/{id}/gate` | API key (owner) | `{ "p95_ms": float >0, "window"?: "24h"\|"7d"\|"30d" }` | `200 { "pass": true, "observed_p95_ms": float, "budget_p95_ms": float }` when observed ≤ budget | `422 { "error":"gate_failed", "pass": false, "observed_p95_ms", "budget_p95_ms" }` when over; `400/401/404/429` |
| V3 | `GET /api/v1/checks/{id}/stats` | API key (owner) | same as X2 | same as X2 | `400/401/404` |
| V4 | `GET /api/v1/checks` | API key | `?limit=&offset=` | `200` list (same shape as C1, no `project` filter needed) | `401/429` |

### 1.7 Projects (P1)

| # | Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|---|
| P1-1 | `GET /api/projects` | user | `?limit=&offset=` | `200 { "data": [{ "id","name","created_at","check_count" }] }` | `401` |
| P1-2 | `POST /api/projects` | user | `{ "name": str(1..64) }` | `201 Project` | `400/401` |
| P1-3 | `GET /api/projects/{id}` | user (owner) | — | `200 Project` | `401/404` |
| P1-4 | `PATCH /api/projects/{id}` | user (owner) | `{ "name": str }` | `200 Project` | `400/401/404` |
| P1-5 | `DELETE /api/projects/{id}` | user (owner) | `?detach=true\|false` | `204` (refuse if checks exist and `detach=false` → `409`) | `401/404/409` |
| P1-6 | `POST /api/projects/{id}/checks/{check_id}` | user (owner of both) | — | `200 Check` (reassign) | `401/404` |

### 1.8 Alert channels & deliveries (P0 webhook/email + P1 chat)

| # | Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|---|
| H1 | `GET /api/checks/{id}/channels` | user (owner) | — | `200 { "data": [{ "id","kind","target","created_at" }] }` (target masked to host only for email) | `401/404` |
| H2 | `POST /api/checks/{id}/channels` | user (owner) | `{ "kind": "email"\|"webhook"\|"slack"\|"discord", "target": str }` | `201 Channel` (validates email format / https webhook URL, blocks SSRF targets) | `400` bad kind/target/SSRF; `401/404`; `403` plan limit |
| H3 | `DELETE /api/channels/{id}` | user (owner) | — | `204` | `401/404` |
| H4 | `POST /api/channels/{id}/test` | user (owner) | — | `200 { "delivery_id": int, "status": int, "attempts": int }` (sends test message, logs delivery) | `401/404`; delivery failure still `200` with status code field (see §6) |
| H5 | `GET /api/checks/{id}/deliveries` | user (owner) | `?limit=&offset=` | `200 { "data": [{ "id","alert_id","channel_id","status","attempts","ts" }] }` | `401/404` |

### 1.9 Public endpoints (no auth)

| # | Method & path | Auth | Response | Errors |
|---|---|---|---|---|
| R1 | `GET /r/{slug}` | anon | `200` HTML public report (chart + stats; no keys/settings/email) | `404` if slug missing or `is_public=0` |
| R2 | `GET /r/{slug}/series` | anon | `200` JSON (same shape as X1, but only when public; rate limited 60/min/IP) | `404` if not public; `429` rate limited |
| R3 | `GET /s/{slug}` (P1 status page) | anon | `200` HTML aggregate (component list, 90d uptime, incidents from down/regression events) | `404` |

### 1.10 Ops endpoints

| # | Method & path | Auth | Response | Errors |
|---|---|---|---|---|
| O1 | `GET /healthz` | anon | `200 { "ok": true, "db": "ok", "scheduler": "ok"\|"disabled"\|"stalled", "uptime_sec": int, "version": str }` | `503` if DB unreachable (body still JSON with `ok:false`) |
| O2 | `GET /metrics` | anon (P0; recommend IP allowlist behind proxy) | `200 text/plain` Prometheus exposition (see §9) | — |
| O3 | `GET /` + `GET /static/*` | anon | Static HTML/JS/CSS (no build step) | `404` unknown static path |

**Endpoint count:** 37 (A1–A9: 9, K1–K3: 3, C1–C6: 6, X1–X5: 5, V1–V4: 4, P1-1–P1-6: 6, H1–H5: 5, R1–R3: 3, O1–O3: 3 — minus A6/A7 counted once; total distinct method+path pairs = **37**).

---

## 2. Data model (SQLite)

Global conventions: `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=5000`. All `TEXT` timestamps UTC ISO-8601. `id` for `checks`/`api_keys`/`alert_channels`/`projects`/`status_pages` is `TEXT` (opaque); all other PKs `INTEGER`. Boolean flags are `INTEGER 0/1`. Every table has `created_at` unless noted. No `NULL` for non-nullable-by-design columns (`CHECK`/`NOT NULL` enforced).

### 2.1 Entity list (16 tables; 9 in P0)

| # | Table | Pri | Purpose |
|---|---|---|---|
| 1 | `users` | P0 | Accounts |
| 2 | `sessions` | P0 | Browser sessions (revocable) |
| 3 | `api_keys` | P0 | CI API keys (hash only) |
| 4 | `checks` | P0 | URL checks users watch |
| 5 | `samples` | P0 | Latency samples (append-only, high volume) |
| 6 | `alerts` | P0 | Regression/down alerts (deduped by cooldown) |
| 7 | `alert_channels` | P0 | Email/webhook targets per check |
| 8 | `deliveries` | P0 | Delivery attempts per alert×channel |
| 9 | `plan_limits` | P0 | Seed data: per-plan caps |
| 10 | `projects` | P1 | Groups of checks |
| 11 | `status_pages` | P1 | Public status page per user/project |
| 12 | `schema_migrations` | P0 | Applied migration versions |
| 13 | `jobs` | P0 | Background job queue (webhook retry, digest) |
| 14 | `rate_buckets` *(optional, in-memory preferred — see §3.5)* | — | Not persisted P0; in-process token bucket. Table reserved for multi-process P2. |
| 15 | `workspaces` + `workspace_members` (P2 teams) | P2 | Teams/roles stub |
| 16 | `oauth_identities` (P2) | P2 | OAuth provider ↔ user link stub |

`rate_buckets` is excluded from P0 persistence; in-memory bucket (§3.5) is sufficient single-process. Counted as entities in §2.2 for completeness; **P0 persisted entity count = 12 tables** (`users`, `sessions`, `api_keys`, `checks`, `samples`, `alerts`, `alert_channels`, `deliveries`, `plan_limits`, `schema_migrations`, `jobs`, + `projects` shipped as empty P0-ready table? — no: `projects` is P1. **P0 = 11 persisted tables**; P1 adds 2; P2 adds 3).

### 2.2 Table definitions

#### `users` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK, `secrets.token_urlsafe(16)`-ish (`uuid4 hex`) |
| `email` | `TEXT` | `UNIQUE NOT NULL`, normalized lowercase+trimmed, ≤254 chars, regex-validated |
| `pw_hash` | `TEXT` | `NOT NULL`, format `pbkdf2-sha256$<iters>$<salt_b64>$<hash_b64>` (§3.3) |
| `plan` | `TEXT` | `NOT NULL DEFAULT 'free'`, `CHECK IN ('free','pro','team')` |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

Indexes: `UNIQUE users.email`. No other indexes.

#### `sessions` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK, `secrets.token_urlsafe(32)` (opaque) |
| `user_id` | `TEXT` | FK → `users(id) ON DELETE CASCADE`, `NOT NULL` |
| `expires_at` | `TEXT` | `NOT NULL` (now + 30d; sliding refresh on use if <15d left) |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

Indexes: `sessions(user_id)`, `sessions(expires_at)`. Cleanup: delete expired on boot + nightly via `jobs` (§5).

#### `api_keys` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK |
| `user_id` | `TEXT` | FK → `users(id) ON DELETE CASCADE`, `NOT NULL` |
| `prefix` | `TEXT` | `NOT NULL` (first 6 chars after `ll_`, e.g. `ll_a1b2c3…` prefix `a1b2c3` for display) |
| `hash` | `TEXT` | `NOT NULL UNIQUE`, SHA-256 hex of full key (`hashlib.sha256`) |
| `name` | `TEXT` | `NOT NULL DEFAULT ''`, ≤64 chars |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |
| `revoked_at` | `TEXT` | `NULL` (set on revoke; `WHERE revoked_at IS NULL` required on all auth queries) |
| `last_used_at` | `TEXT` | `NULL` (updated on successful auth, throttled to 1/min) |

Indexes: `UNIQUE api_keys(hash)`, `api_keys(user_id)`, `api_keys(user_id, revoked_at)`.

#### `checks` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK |
| `user_id` | `TEXT` | FK → `users(id) ON DELETE CASCADE`, `NOT NULL` |
| `name` | `TEXT` | `NOT NULL CHECK (length(name) BETWEEN 1 AND 64)` |
| `url` | `TEXT` | `NOT NULL CHECK (length(url) BETWEEN 1 AND 2048)`; `http(s)` only, SSRF-validated at write time (§3.6) |
| `interval_sec` | `INTEGER` | `NOT NULL CHECK IN (60,300,900,3600)` + plan min-interval enforced in app layer (§4.9) |
| `threshold_pct` | `REAL` | `NOT NULL DEFAULT 20.0`, `CHECK (threshold_pct >= 5 AND threshold_pct <= 200)` |
| `is_public` | `INTEGER` | `NOT NULL DEFAULT 0 CHECK IN (0,1)` |
| `slug` | `TEXT` | `UNIQUE`, `NULL` unless `is_public=1`; format `[a-z0-9-]{4,64}`; generated on first publish |
| `project_id` | `TEXT` | FK → `projects(id) ON DELETE SET NULL`, `NULL` (P1; column present P0 as nullable for forward-compat) |
| `region` | `TEXT` | `NOT NULL DEFAULT 'single'`, `CHECK IN ('single','us','eu','ap')` (P2 multi-region stub; `single` only P0) |
| `last_checked_at` | `TEXT` | `NULL` |
| `baseline_p95_ms` | `REAL` | `NULL` (cached rolling baseline for fast detector reads; recomputed nightly + on ingest) |
| `cooldown_until` | `TEXT` | `NULL` (detector 6h cooldown per check, §4.4) |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

Indexes: `checks(user_id)`, `checks(user_id, created_at)`, `UNIQUE checks(slug) WHERE slug IS NOT NULL`, `checks(project_id)`, `checks(last_checked_at)`.

#### `samples` (P0, append-only)
| Field | Type | Constraints |
|---|---|---|
| `id` | `INTEGER` | PK autoincrement |
| `check_id` | `TEXT` | FK → `checks(id) ON DELETE CASCADE`, `NOT NULL` |
| `ts` | `TEXT` | `NOT NULL` (ingest time, UTC) |
| `ms` | `REAL` | `NULL` (null on network error/timeout; `ms >= 0` when present) |
| `status` | `INTEGER` | `NULL`, `CHECK (status BETWEEN 100 AND 599)` |
| `size_bytes` | `INTEGER` | `NULL`, `CHECK (size_bytes >= 0)` |
| `git_sha` | `TEXT` | `NULL CHECK (length(git_sha) <= 40)` |
| `note` | `TEXT` | `NULL CHECK (length(note) <= 500)` |
| `error` | `TEXT` | `NULL CHECK (length(error) <= 200)` (e.g. `timeout`, `dns`, `connect`, `http`) |

Indexes: `samples(check_id, ts)`, `samples(check_id, ts DESC)`, `samples(ts)` (retention purge), `samples(git_sha)` (commit annotation lookups). Retention: rows older than plan `history_days` purged nightly (§5); `samples` never updated, only inserted + purged.

#### `alerts` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `INTEGER` | PK autoincrement |
| `check_id` | `TEXT` | FK → `checks(id) ON DELETE CASCADE`, `NOT NULL` |
| `kind` | `TEXT` | `NOT NULL CHECK IN ('regression','down','recovered','gate')` |
| `observed_p95_ms` | `REAL` | `NULL` (null for `down` when no successful sample) |
| `baseline_p95_ms` | `REAL` | `NULL` |
| `detail` | `TEXT` | `NOT NULL DEFAULT ''` ≤1000 (plain-language summary, e.g. `p95 rose 212ms → 389ms`) |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |
| `acked_at` | `TEXT` | `NULL` |

Indexes: `alerts(check_id, created_at DESC)`, `alerts(created_at)`.

#### `alert_channels` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK |
| `check_id` | `TEXT` | FK → `checks(id) ON DELETE CASCADE`, `NOT NULL` |
| `kind` | `TEXT` | `NOT NULL CHECK IN ('email','webhook','slack','discord')` |
| `target` | `TEXT` | `NOT NULL` (email addr or https URL; SSRF-validated for webhook-like kinds; stored as given, masked only in list responses) |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

Indexes: `alert_channels(check_id)`. Unique: `UNIQUE(alert_channels(check_id, kind, target))`.

#### `deliveries` (P0)
| Field | Type | Constraints |
|---|---|---|
| `id` | `INTEGER` | PK autoincrement |
| `alert_id` | `INTEGER` | FK → `alerts(id) ON DELETE CASCADE`, `NOT NULL` |
| `channel_id` | `TEXT` | FK → `alert_channels(id) ON DELETE CASCADE`, `NOT NULL` |
| `status` | `INTEGER` | `NULL` (HTTP status or SMTP code; null on network failure) |
| `attempts` | `INTEGER` | `NOT NULL DEFAULT 0 CHECK (0<=attempts<=3)` |
| `ts` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |
| `last_error` | `TEXT` | `NULL` ≤500 |

Indexes: `deliveries(alert_id)`, `deliveries(channel_id, ts DESC)`.

#### `plan_limits` (P0, seed)
| Field | Type | Constraints |
|---|---|---|
| `plan` | `TEXT` | PK, `CHECK IN ('free','pro','team')` |
| `max_checks` | `INTEGER` | Seed: free 3 / pro 25 / team 100 |
| `min_interval_sec` | `INTEGER` | Seed: free 300 / pro 60 / team 60 |
| `history_days` | `INTEGER` | Seed: free 7 / pro 90 / team 365 |

One row per plan, seeded by migration v1. Read at check-create/patch + purge job.

#### `projects` (P1)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK |
| `user_id` | `TEXT` | FK → `users(id) ON DELETE CASCADE`, `NOT NULL` |
| `name` | `TEXT` | `NOT NULL CHECK (1..64)` |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

Indexes: `projects(user_id)`.

#### `status_pages` (P1)
| Field | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PK |
| `user_id` | `TEXT` | FK → `users(id) ON DELETE CASCADE`, `NOT NULL`, `UNIQUE` (one page per user P1) |
| `slug` | `TEXT` | `UNIQUE NOT NULL [a-z0-9-]{4,64}` |
| `project_id` | `TEXT` | FK → `projects(id) ON DELETE SET NULL`, `NULL` (null = all user's checks) |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

Indexes: `UNIQUE status_pages(slug)`, `status_pages(user_id)`.

#### `schema_migrations` (P0)
| Field | Type | Constraints |
|---|---|---|
| `version` | `INTEGER` | PK |
| `name` | `TEXT` | `NOT NULL` |
| `applied_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |

#### `jobs` (P0, see §5)
| Field | Type | Constraints |
|---|---|---|
| `id` | `INTEGER` | PK autoincrement |
| `kind` | `TEXT` | `NOT NULL CHECK IN ('webhook_retry','email_send','purge_samples','purge_sessions','baseline_recompute','digest')` |
| `payload` | `TEXT` | `NOT NULL` (JSON) |
| `run_at` | `TEXT` | `NOT NULL` (`DEFAULT datetime('now')`) |
| `attempts` | `INTEGER` | `NOT NULL DEFAULT 0` |
| `last_error` | `TEXT` | `NULL` |
| `status` | `TEXT` | `NOT NULL DEFAULT 'pending' CHECK IN ('pending','running','done','failed')` |
| `created_at` | `TEXT` | `NOT NULL DEFAULT datetime('now')` |
| `finished_at` | `TEXT` | `NULL` |

Indexes: `jobs(status, run_at)`, `jobs(kind, run_at)`, `jobs(created_at)`.

#### P2 stubs (not shipped sprint 1)

`workspaces(id, name, owner_user_id, created_at)`, `workspace_members(id, workspace_id FK, user_id FK, role CHECK IN ('owner','member'), UNIQUE(workspace_id,user_id))`, `oauth_identities(id, user_id FK, provider CHECK IN ('github','google'), provider_user_id TEXT, UNIQUE(provider,provider_user_id))`.

### 2.3 Relationships

```
users 1──* sessions
users 1──* api_keys
users 1──* checks 1──* samples
checks 1──* alerts 1──* deliveries *──1 alert_channels
checks *──0..1 projects (FK SET NULL)
users 1──0..1 status_pages
*──* jobs (no FK; payload JSON references alert/delivery/check IDs)
```

Deleting a user cascades to sessions, api_keys, checks (→ samples, alerts, channels, deliveries). Deleting a check cascades samples/alerts/channels/deliveries. No `ON DELETE CASCADE` from `samples` upward (samples are leaf).

### 2.4 Storage & performance notes

- Single-writer: all writes go through one `sqlite3` connection guarded by `threading.RLock`; scheduler thread and HTTP threads serialize writes. Reads may use same connection (short transactions) — WAL still gives concurrent readers when using `check_same_thread=False` with lock discipline. Documented migration path to Postgres: replace `db.py` adapter; schema is portable (no SQLite-only types beyond `AUTOINCREMENT`).
- `samples` growth: 25 checks × 1/min = 36k rows/day/user worst case; `(check_id, ts)` index keeps series queries <50ms. Retention purge nightly keeps table bounded.

---

## 3. Auth & RBAC

### 3.1 Approach chosen

**Opaque server-side sessions for the browser + API keys for CI/integrations. No JWT.** Rationale: instant revocation (logout / password change / admin action must take effect immediately), no secret-management for signing keys, trivially testable with stdlib, matches product spec AC ("logout invalidates session", "revoke takes effect immediately"). JWT adds key rotation + revocation-list complexity with no benefit single-process.

### 3.2 Sessions

- Cookie: `ll_session=<token>; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000` (30 days). `Secure` flag set when `COOKIE_SECURE=1` or `BASE_URL` is https (default `1` in production, `0` in local dev).
- Token: `secrets.token_urlsafe(32)` (~43 chars, 256-bit); stored as PK in `sessions` (not hashed — server-side lookup is the point; table is not readable without DB access).
- Expiry: `expires_at = now + 30d`; sliding refresh: if last use >15d ago, extend +30d on next authenticated request (update row + re-set cookie).
- Logout: `DELETE FROM sessions WHERE id=?` + `Set-Cookie: ll_session=; Max-Age=0`.
- Password change (A5): invalidate all other sessions for the user, keep current (or force re-login — simpler: invalidate all, require re-login; document choice).
- Session fixation: rotate session id on login/register (never accept a client-supplied session id that isn't in the table).

### 3.3 Password hashing (stdlib)

```python
import hashlib, secrets, base64
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    iters = 200_000
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, iters)
    return f"pbkdf2-sha256${iters}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
def verify(pw: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split('$')
        salt = base64.b64decode(salt_b64); expected = base64.b64decode(dk_b64)
        actual = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, int(iters_s))
        return algo == 'pbkdf2-sha256' and secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
```

- ≥100k iterations required by spec; use 200k (tunable via env `PBKDF2_ITERS`, floor 100k enforced).
- Compare with `secrets.compare_digest`; login returns generic `401 { "error": "invalid_credentials" }` on both unknown email and bad password (run a dummy PBKDF2 against a fixed salt when user not found to normalize timing).
- Password policy: 10–128 chars, no length-2048 confusion (body cap separate). No composition rules sprint 1 (breach-corpus check is P2).

### 3.4 API keys

- Format: `ll_` + 32 chars from `secrets` alphabet (`token_urlsafe` trimmed to 32 chars or `secrets.choice(string.ascii_letters+digits)` ×32). Show full key **once** in K1 response; never return again.
- Storage: `SHA-256(full_key)` hex in `api_keys.hash`; `prefix` = first 6 chars after `ll_` for list UI. Verify: `SHA-256(presented) == hash` via `compare_digest` + `revoked_at IS NULL`.
- Revocation: `revoked_at = now`; auth query `WHERE hash=? AND revoked_at IS NULL` → takes effect on next request (immediate).
- Scopes: P0 keys are full-access within the owner's data (ingest + gate + read). Read-only keys are P2. Key auth **does not** satisfy browser-session-only routes (`POST /api/keys`, `PATCH /api/auth/me`).

### 3.5 Roles & RBAC

| Role | Meaning | Access |
|---|---|---|
| `anon` | No session / no key | Public endpoints only: `/r/{slug}`, `/r/{slug}/series`, `/s/{slug}`, `/healthz`, `/metrics`, static, `POST /api/auth/register|login`, OAuth stub |
| `user` | Authenticated account | Full CRUD on own `checks`, `samples` (ingest via key), `alerts`, `channels`, `keys`, `projects` (P1), `status_pages` (P1) |
| `admin` | `user` with `is_admin=1` (P0: `users.is_admin INTEGER DEFAULT 0` — add column in v1 migration, managed via env `ADMIN_EMAILS` bootstrap or direct DB) | Plan toggle (A8/A9), user list (P2), everything `user` can do |
| `owner`/`member` (P2 teams) | Workspace roles in `workspaces`/`workspace_members` | `member` cannot delete project/workspace or manage members; enforced per-route via `require_role(workspace, 'owner')` helper. Not shipped sprint 1. |

Route-level enforcement: every handler calls `actor = resolve_actor(request)` → `{ user_id, via: 'session'|'key' }` or `None`; then `require_user(actor)` / `require_owner(check, actor)` / `require_admin(actor)`. Ownership checks use `AND user_id=?` in SQL and return `404` on miss. Never trust client-supplied `user_id`.

### 3.6 Rate limiting

In-memory token bucket (stdlib `threading.Lock` + `dict`), single-process; `rate_buckets` table reserved for multi-process P2:

| Scope | Limit | Key | Window | Response |
|---|---|---|---|---|
| Login attempts | 5/min | client IP (+ email, to stop distributed spray, the tighter of the two) | sliding 60s | `429` + `Retry-After` |
| Register | 5/hour | client IP | 1h | `429` |
| API-key ingest (`POST /api/v1/.../samples`) | 100/min | API key ID | sliding 60s | `429` |
| Gate (`POST /api/v1/.../gate`) | 60/min | API key ID | 60s | `429` |
| Public report (`GET /r/{slug}/series`) | 60/min | client IP + slug | 60s | `429` |
| Ping-now | 10/hour | user ID | 1h | `429` (prevents checker-as-proxy abuse) |
| Scheduler-triggered fetches | natural (check interval) | check ID | — | n/a |

Client IP: `X-Forwarded-For` first hop **only** when `TRUST_PROXY=1` (default 0; direct `REMOTE_ADDR` otherwise — prevents header spoofing when self-hosted without proxy).

### 3.7 CSRF

- Session auth is cookie-only, so CSRF matters. Defense: `SameSite=Lax` (default) + explicit check on all state-changing `/api/*` requests: if `Origin` header present, it must match `BASE_URL` origin (or be absent for curl/CI — absent is allowed only for `/api/v1/*` key-auth, never for cookie routes with `Content-Type: application/json`). JSON content-type means classic form-encoded CSRF cannot send valid bodies, but `fetch` from evil origin with `credentials:include` is still blocked by CORS absence (no `Access-Control-Allow-Origin` header is ever sent) + Origin check. No CSRF tokens sprint 1 (stdlib SPA without cross-site forms); reassess if cross-site embedding is ever needed (then add double-submit token cookie).

### 3.8 Input validation

- Central `validate.py` helpers: `email()`, `url()` (scheme http/https, length, SSRF), `interval()`, `sha()`, `json_body()` (parse + body cap + content-type check). All handlers validate **before** any DB write; invalid → `400` with `detail` naming the field. Unknown JSON fields ignored (forward-compat) except strict mode on gate/ingest.
- Output encoding: static frontend escapes all user data via `textContent` (never `innerHTML`); server JSON always `json.dumps` with `Content-Type: application/json`.

### 3.9 SSRF guard (critical — the product *is* an HTTP checker)

For both check-creation validation and every sampler fetch (§4.1):
1. Parse URL with `urllib.parse.urlparse`; reject unless `scheme in ('http','https')`, `hostname` present, `port` in {80,443} or explicit port 1–65535 with host public.
2. Resolve hostname with `socket.getaddrinfo`; reject if **any** resolved IP is in: loopback (`127.0.0.0/8`, `::1`), private (`10/8`, `172.16/12`, `192.168/16`, `fc00::/7`), link-local (`169.254/16`, `fe80::/10`), unspecified (`0.0.0.0/8`), multicast, reserved, or documentation ranges. Use `ipaddress.ip_address(...).is_private / is_loopback / is_link_local / is_reserved / is_multicast / is_unspecified`.
3. Fetch with redirects **disabled** (never follow — prevents redirect-to-internal bypass); `urllib.request` with a custom opener that raises on 3xx. Timeout 10s. Read at most 1 MiB (abort beyond).
4. Re-resolve + re-check **at fetch time** (DNS may change between create and fetch; TOCTOU accepted sprint 1 with recheck at connect — document as known limitation).
5. Webhook/channel targets use the same guard (https only, same IP denylist).

This runs on every scheduler tick; creation-time check gives fast feedback, fetch-time check is authoritative.

---

## 4. Core business logic per feature

### 4.1 Sampler (port of `httpping` fetch+timing, `app/sampler.py`)

```
def sample(check) -> Sample:
    url = check.url
    ssrf_guard(url)                      # §3.9, raises SSRFBlocked
    t0 = time.monotonic()
    try:
        req = Request(url, method='GET', headers={'User-Agent': 'LatencyLedger/1.0'})
        with urlopen(req, timeout=10, opener=no_redirect_opener) as resp:  # §3.9: no redirects
            status = resp.status
            body = resp.read(1 << 20)    # 1 MiB cap
            size = len(body)
        ms = (monotonic() - t0) * 1000.0
        return Sample(ms=ms, status=status, size_bytes=size, error=None)
    except TimeoutError / socket.timeout:
        return Sample(ms=None, status=None, error='timeout')
    except socket.gaierror:
        return Sample(ms=None, status=None, error='dns')
    except ConnectionRefusedError / ConnectionResetError:
        return Sample(ms=None, status=None, error='connect')
    except HTTPError as e:               # 4xx/5xx still a valid latency sample
        return Sample(ms=(now-t0)*1000, status=e.code, error=None)
    except Exception as e:
        return Sample(ms=None, status=None, error='http' if type(e).__name__=='URLError' else 'error:<class>')
```

Notes: `ms` includes full body read (matches `httpping` CLI semantics: `fetch` + `res.text()`). Do **not** retry within a sample tick (retries inflate latency). Concurrent samples per check: 1 at a time (scheduler holds a per-check lock; overlapping tick skips if previous still running).

### 4.2 Ping-now (C6)

```
POST /api/checks/{id}/ping-now { count=10 }
1. Auth + ownership + ping-now rate limit (§3.6).
2. Validate count ∈ [1,50].
3. Run min(count, plan allowance) sequential samples via sampler (sequential to avoid self-inflicted contention; P2 may parallelize).
4. Persist each sample (ms/status/size/error, ts=now, git_sha=null).
5. Compute Stats over the N results (§4.3); error requests counted separately (error_count, excluded from percentiles).
6. Return { samples: [{ms,status,error}], stats, checked_at }.
7. Run detector once on the persisted batch (§4.4) — ping-now can trigger regression alerts.
Edge: storage error mid-batch → still return results + log; partial persist acceptable (samples are append-only, detector tolerates gaps). Never crash on a single failing request (product AC).
```

### 4.3 Stats & percentiles (`app/stats.py`, pure functions, test-gated ≥70%)

```
def percentile(sorted_vals, p) -> float | None:
    if not sorted_vals: return None
    # linear interpolation, "type 7" (numpy default / Excel PERCENTILE.INC)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = floor(k); c = ceil(k)
    if f == c: return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

def compute_stats(samples) -> Stats:
    ok = sorted([s.ms for s in samples if s.ms is not None])
    errors = count of s.ms is None
    if not ok: return Stats(count=0, error_count=errors, min=None, max=None, avg=None, p50=None, p95=None, p99=None, uptime=0)
    avg = sum(ok)/len(ok); uptime = 100 * len(ok) / (len(ok)+errors)
    return Stats(count=len(ok), error_count=errors, min=ok[0], max=ok[-1], avg=avg,
                 p50=percentile(ok,50), p95=percentile(ok,95), p99=percentile(ok,99), uptime=uptime)
```

**Baseline (rolling):** daily p95 series over the last 7d (one p95 per UTC day, only days with ≥1 sample); baseline = **median** of daily p95 (robust to spikes, matches "rolling median of daily p95"). Requires ≥50 samples total **and** ≥3 days of history; otherwise `baseline_p95_ms = null` and detector is dormant (no false alerts on new checks). Recomputed: cached on `checks.baseline_p95_ms` by nightly `baseline_recompute` job + on-demand when null and detector fires.

**Series bucketing (X1):** window `range` → bucket size: `24h→5m` (288 pts), `7d→1h` (168), `30d→4h` (180). For each bucket: `avg_ms` = mean of ok samples, `p95_ms` = percentile(bucket, 95), `count` = n. Buckets with 0 samples are **omitted** (frontend draws gaps; do not fabricate zeros). `<2 points` total → frontend empty state (API returns `points: []` + `baseline_p95_ms`).

### 4.4 Regression detector (`app/detector.py`) — the product's core

Fires on: scheduler ingest (per sample), ping-now batch (once), CI ingest (V1, per sample). Algorithm, per check:

```
def maybe_alert(check) -> Alert | None:
    now = utcnow()
    # 1. Cooldown
    if check.cooldown_until and now < check.cooldown_until: return None
    # 2. Baseline + sample floor
    baseline = check.baseline_p95_ms (recompute if null)
    window = last 24h samples (ok only)
    if baseline is None or baseline <= 0: return None
    if len(window) < 50: return None                     # min-sample floor (product spec §6)
    observed_p95 = percentile(sorted(window_ms), 95)
    # 3. Threshold (+ hysteresis): regression while observed > baseline * (1 + threshold_pct/100)
    if observed_p95 <= baseline * (1 + check.threshold_pct/100.0): return None
    # 4. Anti-flap hysteresis: only fire if previous window was NOT already alerting,
    #    OR if observed exceeds previous alert's observed by 10% (escalation). Track via
    #    "last alert within 24h for this check": if exists and observed within 10% of that
    #    alert's observed, suppress (still in regression, already notified).
    prev = last unacked alert for check within 24h
    if prev and observed_p95 < prev.observed_p95_ms * 1.10: return None
    # 5. Persist + cooldown + fan-out
    alert = insert alerts(kind='regression', observed, baseline,
                          detail=f"p95 rose {baseline:.0f}ms → {observed:.0f}ms")
    check.cooldown_until = now + 6h
    fan_out(alert, channels)   # §4.6; delivery failures never block ingest
    return alert
```

**`down` alerts:** ≥3 consecutive error samples (ms null) OR ≥3 consecutive `status >= 500` → `kind='down'` (same cooldown + fan-out). **Recovery:** after a `down` alert, first run with ≥5 ok samples → `kind='recovered'`. **Gate alerts** (`kind='gate'`) are not enqueued by detector — gate is synchronous (§4.5); kind reserved for P1 audit log.

**Edge cases:** baseline=0 (instant local fetch) — guard division; all-error window — observed null → no regression alert (down path handles it); clock skew — all timestamps server UTC; detector is idempotent under retry (cooldown + prev-window hysteresis make double-fire impossible within 6h).

### 4.5 CI gate (V2, `app/gate.py`)

```
POST /api/v1/checks/{id}/gate { p95_ms, window=24h }
1. API-key auth + ownership (key's user must own check; else 404).
2. Fetch window samples (ok only). If count < 5: 400 { error: "insufficient_samples", observed_count } — gate cannot pass on thin data.
3. observed = percentile(sorted(ms), 95)
4. if observed <= p95_ms: 200 { pass: true, observed_p95_ms, budget_p95_ms }
5. else: 422 { error: "gate_failed", pass: false, observed_p95_ms, budget_p95_ms }
```

Gate never mutates state. GHA example (ships in `examples/github-actions.yml`): step calls gate, `continue-on-error: false`, reads `observed_p95_ms` from JSON for PR comment. GitHub Actions YAML must be validated against this contract in tests (fit-check, not live call).

### 4.6 Alert fan-out (`app/alerts.py`)

On alert creation: for each `alert_channels` row for the check, create `deliveries(alert_id, channel_id, attempts=0)` and enqueue a `webhook_retry`/`email_send` job (or send synchronously if no channel retry needed — spec: **always async via `jobs`**, so ingest path never blocks on SMTP/HTTP). Job handler:

```
attempts loop (max 3):
  try send(channel, alert)   # email via smtplib (if SMTP env set), webhook/slack/discord via urllib POST JSON
  except -> record status/last_error, attempts+=1, if attempts<3 schedule retry at +1m, +5m (exponential-ish 1m/5m/25m)
  on success: status=HTTP code, done
```

- Email: only when `SMTP_HOST`, `SMTP_FROM` set; otherwise email delivery rows are created with `last_error='smtp_disabled'` and `status=null` (visible in UI as "not configured", never an error to the user). Default sprint-1: **webhook is the dependable channel; email is opportunistic.**
- Webhook payload: `{ "text": "...", "alert": {…}, "check": {…} }` (Slack-compatible `text` field; Discord uses `content`). SSRF guard on channel target (§3.9). Timeout 5s, 256 KiB response cap.
- Failure of one channel never blocks another or the ingest loop. All outcomes in `deliveries`.
- Test-send (H4): synthesizes an alert-like payload, delivers through the same code path, returns delivery status.

### 4.7 Public report (R1/R2)

`GET /r/{slug}`: lookup `checks WHERE slug=? AND is_public=1`; if miss → HTML 404 page (no existence oracle beyond the slug itself, which is unguessable `[a-z0-9-]{4,64}`). Renders: check name, url, stats (24h), sparkline (canvas, same bucketing as X1), baseline. **Never** includes: owner email, `user_id`, thresholds, channels, API keys, `threshold_pct`. R2 serves the same bucketed series as JSON with public rate limit. Toggling `is_public=0` → subsequent R1/R2 → 404 immediately (no cache — `Cache-Control: no-store` on public JSON; HTML may `max-age=60` keyed by any content change).

### 4.8 Scheduling (`app/scheduler.py`, §5)

Due-loop: every 5s, `SELECT * FROM checks WHERE last_checked_at IS NULL OR last_checked_at <= datetime('now', '-' || interval_sec || ' seconds')` ordered by `last_checked_at`. Per-check: acquire per-check lock, re-read `last_checked_at` (avoid double-fire under clock jumps), run sampler, insert sample with `ts=now`, update `last_checked_at=now`, call detector. Lock per check held only for the fetch (≤10s). Heartbeat: update in-memory `scheduler.last_tick` + `scheduler.heartbeat` row (or `jobs` row with `kind='heartbeat'`) — `/healthz` reports `stalled` if no tick >60s with `RUN_SCHEDULER=1`.

### 4.9 Plan limits & billing (sprint 1)

Checked on `POST /api/checks` and `PATCH` (min interval): `plan_limits[users.plan]` vs `COUNT(checks WHERE user_id=?)` and `interval_sec < min_interval_sec`. Over count → `403 { error: "plan_limit", detail: "upgrade link" }` (402 reserved for Stripe P1; use `402` only when `STRIPE_ENABLED=1` and payment required — define both, default `403/plan_limit` sprint 1). History retention uses `history_days` (§5 purge). Manual plan toggle via A8/A9 until Stripe (env-gated) ships. `plan_limits` is seeded data, not user-editable.

### 4.10 Export (P1, X5)

`GET /api/checks/{id}/export?format=csv|json&from&to` (auth owner): stream rows via generator (fetch 5k at a time, `yield`), `Content-Disposition: attachment; filename=<check>-export.<ext>`. CSV header: `ts,ms,status,size_bytes,git_sha,note,error`. Respect plan `history_days` (clamp `from`).

---

## 5. Background jobs / scheduling

**Design:** `jobs` table + a single polling thread in the scheduler process (no Celery/Redis — stdlib only, constraint). The job thread is the same thread as the due-check loop; jobs and checks interleave fairly (jobs first each cycle, then due checks — jobs are fast).

| Job kind | Payload | Trigger | Handler |
|---|---|---|---|
| `webhook_retry` | `{ delivery_id }` | alert fan-out; retry backoff +1m/+5m/+25m | §4.6 send; mark `done`/`failed` after 3 attempts |
| `email_send` | `{ delivery_id }` | alert fan-out (email channels) | §4.6 smtplib; `done`/`failed` |
| `purge_samples` | `{}` (nightly) | 02:00 UTC timer | `DELETE FROM samples WHERE ts < datetime('now', '-' || history_days || ' days')` per-plan (join `checks`→`users`→`plan_limits`); log row count |
| `purge_sessions` | `{}` (nightly) | 02:30 UTC | `DELETE FROM sessions WHERE expires_at <= datetime('now')`; vacuum check |
| `baseline_recompute` | `{ check_id? }` | nightly 02:15 UTC (all checks) + on-demand when detector needs it | recompute & store `checks.baseline_p95_ms` (§4.3); log |
| `digest` (P2) | `{ user_id, date }` | weekly timer | email digest of regressions; stub sprint 1 |

**Worker loop (pseudo):**

```
def worker_loop(stop):
    while not stop:
        job = claim_one_job()   # UPDATE jobs SET status='running' WHERE id=(SELECT id ... WHERE status='pending' AND run_at<=now LIMIT 1) RETURNING *
        if job: handle(job)     # update attempts/status/finished_at; on exception: attempts+=1; if attempts<3 reschedule run_at=now+backoff else status='failed'
        check_due_checks()      # §4.8
        stop.wait(1.0)          # 1s poll; wake immediately on new job insert via threading.Event + notify from writers
```

**Atomicity & idempotency:** `claim_one_job` is a single `UPDATE … RETURNING` inside a transaction (SQLite serializes writers — safe single-process; for split web/worker P2, keep WAL + this single statement, or add `FOR UPDATE SKIP LOCKED` Postgres equivalent later). Handlers must be idempotent: re-sending a webhook on crash is acceptable (deliveries record attempts); purge/recompute are naturally idempotent. **Scalability flag:** `RUN_SCHEDULER=1` (default) runs the worker thread in-process; `RUN_SCHEDULER=0` = web-only (jobs/checks handled by a second container instance with `RUN_SCHEDULER=1`). Scheduler is stateless so horizontal worker scaling is safe (per-check lock is best-effort in-process; cross-process double-fetch is a bounded, acceptable degradation — ingest is append-only).

---

## 6. Error handling & logging conventions

**Error handling:**
- Handlers raise `ApiError(status, code, detail)`; central dispatcher maps to the §0 JSON shape with `request_id`. Unhandled exceptions → `500 { "error": "internal" }` + full traceback in logs (never in response). `sqlite3.Error` subclasses are caught at the DB layer and logged with SQL params redacted.
- Validation always returns `400` (never `500`) for client errors, including malformed JSON (`json.JSONDecodeError` → `400 malformed_json`), wrong content-type (`400`), and oversized body (`413`).
- Downstream failures (SMTP/webhook) never surface as request errors on ingest paths; they are `deliveries` rows (§4.6). Gate over-budget is `422`, not `500`.
- Idempotency: `POST /api/v1/checks/{id}/samples` accepts an optional `Idempotency-Key` header (P1); sprint 1 tolerates duplicates (append-only).

**Logging:**
- Python `logging` to stdout, JSON formatter: `{"ts": "...", "level": "INFO", "msg": "...", "request_id": "...", "user_id": "…", "method": "GET", "path": "/api/checks", "status": 200, "duration_ms": 12}`. One line per request + one per job execution + one per scheduler stall.
- Levels: `INFO` normal, `WARNING` detector suppressions/rate limits/delivery retries, `ERROR` unhandled exceptions/purge failures/SQLite errors. Never log passwords, API keys, session tokens, or `pw_hash` (redaction helper for `Authorization` / `ll_session` headers).
- `request_id` = `secrets.token_urlsafe(8)` per request, echoed in `X-Request-Id` and error bodies.
- Sampling: log 100% of errors, sample 10% of successful sampler fetches (avoid log flood at 1-min intervals × 100 checks).

---

## 7. Migrations strategy

- Versioned SQL files `app/migrations/0001_init.sql`, `0002_…sql`, …; applied **on boot** by `db.py` before the server starts.
- Tracking: `schema_migrations(version, name, applied_at)` + `PRAGMA user_version` kept in sync (user_version is the fast path; table is the audit trail). `db.py` reads `PRAGMA user_version`, applies each migration with `version > user_version` in order inside a transaction, then sets `user_version`. Idempotent: safe to re-run (boot with `user_version == max` is a no-op).
- Migrations must be **forward-only**, transactional (SQLite DDL is transactional), and must not require downtime beyond the boot window. Each migration file is plain SQL + optional `PRAGMA` statements; no Python hooks sprint 1 (data backfills are separate `000N_..._backfill.sql` with idempotent `UPDATE … WHERE` clauses).
- Seed data (plan_limits, admin bootstrap) lives in `0001_init.sql` as `INSERT OR IGNORE`.
- Downgrades: not supported (documented; restore from `/data` volume backup). Backup note: user is encouraged to snapshot the SQLite file volume.
- Tests apply migrations to a **temp file** DB (`:memory:` where possible, else `tmp_path / "test.db"`), never to the dev DB.

---

## 8. Caching strategy

**In-process only (stdlib `functools.lru_cache` / dict + `TTLCache`-style class). No Redis/Memcached sprint 1.**

| What | Cache | TTL | Invalidation |
|---|---|---|---|
| `checks.baseline_p95_ms` reads | instance attr on `Check` object per request (no shared cache needed) | per-request | recompute nightly + on demand |
| `plan_limits` | module dict loaded at boot | process lifetime | reload on admin plan change (or restart) |
| Series/stats results (X1/X2) | `{ (check_id, range, window): (expires_at, Stats) }` | 60s | TTL + explicit bust on ping-now/ingest for that check |
| Public report HTML (R1) | file-free render cached in memory | 60s | bust on `is_public`/any-sample write for that check (TTL is the fallback; correctness over freshness) |
| Session auth | direct PK lookup (`sessions` ~µs) | — | none (DB is the cache) |
| Rate-limit buckets | in-memory dict | window itself | n/a |

Bounded size: series/stats cache capped at 512 entries (evict oldest). No distributed cache — noted as P2 when splitting web/worker (then series cache moves to a shared store or is dropped to 0s TTL).

---

## 9. Observability: `/health`, `/metrics`, structured logs

### 9.1 `GET /healthz` (O1)

```json
{ "ok": true, "db": "ok", "scheduler": "ok", "uptime_sec": 1234, "version": "1.0.0", "request_id": "…" }
```

- `db`: `SELECT 1` (timeout 1s). Fail → `503` + `ok:false`.
- `scheduler`: `ok` if `RUN_SCHEDULER=0` ("disabled") or last tick <60s; else `stalled` (still `200` if DB ok, but callers should alert — log a `WARNING`).
- No auth (enables Docker/K8s probes), no user data.

### 9.2 `GET /metrics` (O2) — Prometheus text

```
# HELP http_requests_total Total HTTP requests by method/path/status
# TYPE http_requests_total counter
ll_http_requests_total{method="GET",path="/api/checks",status="200"} 123
# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
ll_http_request_duration_seconds_bucket{le="0.05"} …
ll_http_request_duration_seconds_bucket{le="0.1"} …
ll_http_request_duration_seconds_count …
ll_http_request_duration_seconds_sum …
# HELP samples_ingested_total Samples ingested
ll_samples_ingested_total{source="scheduler"} 456
ll_samples_ingested_total{source="ping-now"} …   ll_samples_ingested_total{source="ci"} …
# HELP alerts_fired_total Alerts fired
ll_alerts_fired_total{kind="regression"} …
ll_alerts_fired_total{kind="down"} …
# HELP deliveries_total Deliveries by channel/status
ll_deliveries_total{kind="webhook",status="200"} …
# HELP scheduler_heartbeat_seconds Seconds since last scheduler tick
ll_scheduler_heartbeat_seconds 3
# HELP samples_p95_ms Rolling ingest p95 (gauge, computed every scrape from last 5m window)
ll_ingest_p95_ms 42.5
```

Counters implemented as in-memory dicts incremented at the same call sites as the JSON logs (§6) — one source of truth, two renderings. No OpenTelemetry sprint 1 (hook point: logging formatter emits W3C traceparent-compatible `request_id`; OTel export is P2).

### 9.3 Self-monitoring

- Ingest p95 & detector counters logged per §9.2. Scheduler stall webhook (optional env `ALERT_WEBHOOK_URL`, reuse §4.6) fires when heartbeat >120s. This matches product `KPI: scheduler uptime ≥99.9%, p95 ingest <2s`.

---

## 10. Security checklist (OWASP Top 10:2021 → LatencyLedger mapping)

| OWASP | Risk | Control in this spec |
|---|---|---|
| **A01 Broken Access Control** | IDOR on checks/samples/alerts; anon reading private reports | Ownership predicates in SQL (`AND user_id=?`); cross-user → `404`; public slug ung​uessable + rate limited; per-route `require_user/owner/admin` (§3.5) |
| **A02 Cryptographic Failures** | Weak hashing; key/hash leakage; no TLS | PBKDF2-HMAC-SHA256 200k + compare_digest (§3.3); API keys stored as SHA-256 hash only; session opaque 256-bit; `Secure` cookie under https; TLS terminated at reverse proxy (documented in Docker/README) |
| **A03 Injection** | SQLi, XSS, log injection | 100% parameterized SQL (no f-strings in queries); frontend `textContent` only; JSON error `detail` escaped by `json.dumps`; log formatter escapes newlines |
| **A04 Insecure Design** | Checker-as-SSRF/proxy; false-positive trust loss | SSRF denylist + no-redirect + timeout + 1 MiB cap at **create and fetch** (§3.9); ping-now rate limited; detector hysteresis/cooldown/min-samples (§4.4) |
| **A05 Security Misconfiguration** | Debug endpoints; secrets in code; default creds | No debug/pprof routes; secrets via env only (`SECURITY.md`); `admin` via env bootstrap, no default password; Docker runs non-root in `python:3.11-slim` |
| **A06 Vulnerable Components** | Supply-chain | Zero pip deps sprint 1 (stdlib only) → no dependency CVEs to track; Python pinned to `>=3.11` in `pyproject.toml`; SBOM trivial |
| **A07 Auth Failures** | Credential stuffing; session hijack | Rate-limited login (§3.6); generic 401; constant-time verify; session rotation on login; 30d expiry + revocation; API-key revocation immediate |
| **A08 Software/Data Integrity** | Tampered migrations/payloads | Migrations are versioned files in git (signed via commit history); webhook payloads are JSON built server-side (no user templating); `Idempotency-Key` (P1) |
| **A09 Logging/Monitoring Failures** | Missed attacks; PII in logs | Structured JSON logs with request_id (§6); redaction helper; `/healthz` + `/metrics` alerting; delivery log is product-visible audit trail |
| **A10 SSRF** | **Primary product risk** (fetches user URLs) | §3.9 in full: scheme allowlist, DNS-resolution denylist (private/loopback/link-local/reserved), no redirects, 10s timeout, 1 MiB cap, same guard on webhook targets; residual risk (DNS rebinding TOCTOU) documented with mitigation (fetch-time recheck) |

Additional hardening sprint 1: security headers on every response (§0); body cap 64 KiB; `Cache-Control: no-store` on authenticated JSON; `SECURITY.md` with disclosure address; `docker-compose` volume for `/data` with restrictive perms noted in deployment docs.

---

## 11. Backend file map (what implementers build from this spec)

```
app/
  main.py        entry: HTTP server (http.server ThreadingHTTPServer or wsgiref) + scheduler/worker threads; RUN_SCHEDULER flag
  config.py      env: PORT, DATABASE_URL (path), COOKIE_SECURE, TRUST_PROXY, SMTP_*, OAUTH_ENABLED, STRIPE_ENABLED, ADMIN_EMAILS, ALERT_WEBHOOK_URL, PBKDF2_ITERS
  db.py          sqlite3 conn factory, WAL pragma, migration runner, single-writer RLock
  router.py      tiny method+path router -> handlers; ApiError dispatcher; request_id middleware; security headers
  auth.py        hash/verify, sessions, API keys, resolve_actor, require_*, rate limiter, CSRF Origin check
  validate.py    email/url/interval/sha/json_body helpers; SSRF guard (resolve+denylist)
  checks.py      check CRUD handlers + plan-limit checks
  sampler.py     §4.1 sample(); no-redirect opener
  scheduler.py   §4.8 due-check loop + §5 worker loop + heartbeat
  stats.py       §4.3 percentile/stats/baseline/bucketing (pure, unit-tested)
  detector.py    §4.4 regression/down/recovery
  alerts.py      §4.6 fan-out + email/webhook/slack/discord senders + backoff
  gate.py        §4.5 CI gate
  handlers/api.py  A/K/C/X/V/H route handlers; handlers/pages.py static; handlers/public.py R1/R2/R3
  static/        index.html, app.js (canvas chart), style.css, check.html, r.html, s.html (P1)
  migrations/    0001_init.sql … (seed plan_limits, users.is_admin column)
tests/           pytest: test_stats.py, test_detector.py, test_auth.py, test_api.py (ephemeral server + temp DB), test_sampler.py (local stub server)
examples/github-actions.yml   GHA step calling §4.5 V2
```

---

## 12. Acceptance mapping (product-spec P0 → backend surface)

| Product story | Backend surface | Spec section |
|---|---|---|
| Sign up / log in | `POST /api/auth/register|login|logout`, `GET /api/auth/me` | §1.2, §3 |
| Add URL check | `POST /api/checks` + validation | §1.4, §3.9 |
| Manual ping now | `POST /api/checks/{id}/ping-now` | §1.4, §4.2 |
| History chart | `GET /api/checks/{id}/series` (bucketed) | §1.5, §4.3 |
| Regression alert | detector + alert log + channels | §4.4, §4.6, §1.5 |
| API key for CI | `POST/GET/DELETE /api/keys` | §1.3, §3.4 |
| CI gate endpoint | `POST /api/v1/checks/{id}/gate` (+ `examples/github-actions.yml`) | §1.6, §4.5 |
| Public report link | `GET /r/{slug}`, `GET /r/{slug}/series`, toggle via `PATCH /api/checks/{id}` | §1.9, §4.7 |
| Docker + `/healthz` | `http.server` on PORT, `/healthz`, `/metrics` | §9, architecture.md deployment |

P1 surfaces (projects §1.7, channels §1.8, export X5, status page R3) and P2 stubs (multi-region `region` column, OAuth A6/A7, teams tables, anomaly/z-score detector extension point in `detector.py`) are included above so sprint-2 implementers don't need a schema break.

---

*Counts (for the build report): API endpoints = 37 method+path routes (§1). Data-model entities = 11 P0 persisted tables, 13 with P1, 16 with P2 stubs (§2). Auth approach = opaque server-side sessions (HttpOnly `ll_session` cookie) + hashed API keys (`ll_…`, SHA-256 at rest), PBKDF2-HMAC-SHA256 password hashing, no JWT.*

## Appendix A — Auth delivery note (see §3.4)

- **Auth approach in one line:** opaque, server-side **sessions** for browsers (HttpOnly `ll_session` cookie + `sessions` table, revocable) and
  **API keys** (`ll_…`, SHA-256 hash stored only) for CI `/api/v1/*`.
- **No JWT** — chosen for immediate revocation (logout / password change / key revoke take effect on next request) and zero secret-management.
- **Password hashing:** `hashlib.pbkdf2_hmac('sha256', …, 200_000)` with per-user 16-byte salt, `secrets.compare_digest`, generic 401, dummy-hash timing normalization (§3.3).
