# LatencyLedger — Test Plan (QA Lead, desk-8)

> Spec-only document for `devhasen/http-ping` (main). It does **not** implement
> tests — it plans them. When code lands, every ID below
> (`U-*`, `I-*`, `E-*`, `P-*`, `R-*`) becomes a `tests/test_*.py` function
> whose docstring starts with the ID, so traceability is greppable:
> `grep -r "U-STAT" tests/`.
>
> Product under test: **LatencyLedger** — Python 3.11+ stdlib-only backend
> (`http.server` + `sqlite3` + `urllib.request`), static HTML/CSS/JS frontend,
> SQLite storage, Docker deploy. Source of truth for scope:
> `docs/product-spec.md` (§2 P0 stories 1–8, §5 metrics) and
> `docs/architecture.md` (module layout, schema, API list).
>
> **Tooling constraint (non-negotiable):** stdlib + `pip` deps declared in
> `requirements.txt` / `pyproject.toml`; **no paid test SaaS**, no external
> services in the default suite. Network access in tests = loopback only.

---

## 1. Pyramid, levels & tools

### 1.1 Pyramid shape (target volume)

```
                    ┌──────────────────────────┐
                    │  E2E / smoke  (~8%)      │  full boot, real HTTP round-trips
                    ├──────────────────────────┤
                    │  Integration (~27%)      │  API vs live server + real SQLite file
                    ├──────────────────────────┤
                    │  Unit (~65%)             │  pure fns, injected fakes, no I/O
                    └──────────────────────────┘
```
Rationale: `stats.py` / `detector.py` / `gate.py` are pure and cheap to test
exhaustively; the hand-rolled `router.py`/`auth.py`/`sampler.py` need real
socket/SQLite integration because their bugs are wiring bugs; e2e is kept
tiny (boot → register → check → ping → alert → gate → public page) because
it is slow and flaky-prone.

### 1.2 Levels

| Level | What it covers | Runs from | Typical count |
|---|---|---|---|
| **Unit** | pure logic, validation, SSRF guard, percentile math, detector rule, hashing, URL parsing, rate-limit bucket | `python -m unittest discover -s tests` or `pytest -q` | 64 |
| **Integration** | HTTP API against ephemeral `http.server` on an OS-assigned port, temp-file SQLite DB, stub `urllib` target server, fake SMTP/webhook sinks | same, slower | 38 |
| **E2E / smoke** | full process boot (`python -m app.main`), scripted happy-path through the public UI/API surface, Docker image build check | CI `e2e` job, `scripts/smoke.sh` | 18 |
| **Performance** | §4 benchmark scripts (not correctness gates) | manual / nightly | 5 scenarios |
| **Beta / UAT** | §5 — human acceptance on the Docker deploy | manual | checklist |

### 1.3 Tools (stdlib-first, declared deps only)

| Need | Tool | Why |
|---|---|---|
| Test framework | Python stdlib **`unittest`** (`discover`, `subTest`, `mock`) — canonical runner. **`pytest`** is *optional*: `pyproject.toml` already declares `[tool.pytest.ini_options]`; if `pip install pytest` is available it runs the same `unittest.TestCase` classes. Default suite must pass under stdlib alone, so tests are written as `unittest.TestCase` (pytest-compatible) and never import pytest-only APIs. | `requirements.txt` stays stdlib-only; zero install needed to test. Declaring `pytest` as a *test* extra later is allowed but never required. |
| Custom runner | `scripts/run_tests.py` (stdlib): runs `unittest` with timing, prints per-test ms, writes `test-report.json` (pass/fail/skip counts) for CI artifact upload. | No extra dep; gives CI a machine-readable result without a SaaS. |
| HTTP client in tests | stdlib **`http.client`** + **`urllib.request`** (for GET-with-headers/cookie handling in e2e). No `requests`/`httpx`. | matches §2/user constraint "http client tests with urllib". |
| Stub target server | stdlib `http.server.ThreadingHTTPServer` on `127.0.0.1:0` with injected latency (`time.sleep`), status codes, and hang modes. Used for `sampler.py` and e2e. | Loopback-only; never hits the public internet in CI. |
| DB fixture | stdlib `sqlite3` `:memory:` per test for unit; temp file (`tempfile.TemporaryDirectory`) for integration (WAL + concurrency need a real file). | §3. |
| Coverage | stdlib **`trace`** (`trace.Trace(count=1,trace=0)`) — see §7. `coverage.py` is allowed *only* if added to `requirements-dev.txt` and never required for the gate. | keeps runtime at zero deps. |
| Benchmarks | stdlib `time.perf_counter`, `threading`, `concurrent.futures`, `http.client` pools — `scripts/bench.py`, §4. | no `locust`/`k6`. |
| CI | GitHub Actions (`.github/workflows/ci.yml`, example already in `examples/github-actions.yml`) running `python -m unittest discover` + `python scripts/run_tests.py`. | free for public repo; no paid test CI. |

### 1.4 Layout

```
tests/
  __init__.py
  helpers.py            # ephemeral server, seeded DB, http client wrappers, fake SMTP/webhook sinks
  test_stats.py         # U-STAT-*
  test_detector.py      # U-DET-*
  test_gate.py          # U-GATE-*
  test_auth.py          # U-AUTH-* + I-AUTH-*
  test_checks.py        # U-CHK-*  + I-CHK-*  (incl. SSRF)
  test_sampler.py       # I-SAMP-* (stub server)
  test_api.py           # I-API-*  (endpoints, gate, public report)
  test_scheduler.py     # I-SCHED-* (due-loop, cooldown, ingest queue)
  test_alerts.py        # I-ALERT-* (fake SMTP / webhook sink)
  e2e/__init__.py
  e2e/test_smoke.py     # E-*
scripts/
  run_tests.py          # custom stdlib runner + JSON report
  bench.py              # §4 benchmarks
  smoke.sh              # §1.2 e2e shell smoke (curl + python urllib)
```

---

## 2. Test catalog — every P0 feature

P0 features (product-spec §2/§3): **F1 Auth** (story 1), **F2 Check CRUD +
validation** (story 2), **F3 Manual ping-now** (story 3), **F4 History
chart/series** (story 4), **F5 Regression alert** (story 5), **F6 API keys**
(story 6), **F7 CI gate endpoint** (story 7), **F8 Public report link**
(story 8), plus cross-cutting **F9 Scheduler & ingest**, **F10 Health /
Docker / observability**.

ID prefixes: `U-` unit, `I-` integration, `E-` e2e. Each row = one test
function. Parentheses after the ID name the module under test.

### F1 — Sign up / log in (story 1) · `app/auth.py`, `handlers/api.py`

**Unit**
- `U-AUTH-01` register valid email+password → user row created, `pw_hash` is a
  `pbkdf2_hmac` digest (never plaintext), salt present, iterations ≥ 100k.
- `U-AUTH-02` password verify: correct pw → True; wrong pw → False;
  `secrets.compare_digest` used (timing-safe).
- `U-AUTH-03` duplicate email → raises/returns 409 conflict (not 500).
- `U-AUTH-04` invalid email (no `@`, empty, >254 chars), empty pw, pw < 8
  chars → 422-style validation error with field shown.
- `U-AUTH-05` session token: 32-byte `token_urlsafe`, unique per login,
  stored server-side with `expires_at` in the future.
- `U-AUTH-06` logout deletes the session row; subsequent use → 401.
- `U-AUTH-07` expired session → 401 even if token otherwise valid.
- `U-AUTH-08` session cookie attributes: `HttpOnly`, `SameSite=Lax`, `Path=/`.
- `U-AUTH-09` API-key hashing: stored value is SHA-256 hex of the key;
  raw `ll_…` key never persisted; prefix (first 8 chars) stored separately.
- `U-AUTH-10` login rate limit: 5 failures/min per IP → 429; success resets
  the bucket; bucket refills after 60s (injected clock).

**Integration**
- `I-AUTH-01` `POST /api/auth/register` → 201 + sets session cookie;
  `GET /api/auth/me` returns the user (same cookie).
- `I-AUTH-02` register → login → logout → `me` is 401 (full cycle over HTTP).
- `I-AUTH-03` SQL-injection probes in email/pw (`' OR 1=1--`, `"; DROP TABLE`)
  → 4xx, `users` table intact, no auth bypass.
- `I-AUTH-04` two users with same email raced (sequential double-register)
  → second is 409.

**E2E**
- `E-AUTH-01` (happy) register → login → me → logout → me-401, via
  `urllib` with a cookie jar against the booted server.
- `E-AUTH-02` (error) wrong password ×6 → 429 on the 6th; correct password
  still blocked until window passes (or returns 429 with `Retry-After`).

### F2 — Add a URL check (story 2) · `app/checks.py`, `app/db.py`

**Unit**
- `U-CHK-01` valid `https://api.example.com/users` + allowed interval
  (60/300/900/3600) → accepted, row persisted.
- `U-CHK-02` scheme rejection: `ftp://`, `javascript:`, `file:///etc/passwd`,
  schemeless string → 422.
- `U-CHK-03` URL length > 2048 → 422; exactly 2048 → accepted.
- `U-CHK-04` interval validation: 0, negative, 30 (below 1m), 999999 → 422;
  only the four allowed values pass.
- `U-CHK-05` SSRF guard: hostnames resolving to `127.0.0.1`, `10/8`,
  `172.16/12`, `192.168/16`, `169.254/16`, `::1` → rejected (mocked DNS).
- `U-CHK-06` SSRF guard: DNS rebinding shape — hostname resolves public at
  validation, private at connect → connect-time check rejects (re-resolve).
- `U-CHK-07` redirect target: `302 → http://169.254.1.1/` → rejected
  (redirects disabled / re-guarded, per architecture).
- `U-CHK-08` plan limit: free plan 3rd check OK, 4th → 402 (plan_limits
  lookup); Pro 25 OK.
- `U-CHK-09` check name: empty → default derived from hostname; >120 chars
  → 422.

**Integration**
- `I-CHK-01` `POST /api/checks` (session) → 201; `GET /api/checks` lists it
  within 1s and it appears on the dashboard payload.
- `I-CHK-02` `POST /api/checks` unauthenticated → 401.
- `I-CHK-03` `GET/PATCH/DELETE /api/checks/{id}`: other user's id → 404
  (not 403 — no existence leak); owner can patch name/interval and delete;
  after delete, `GET` → 404 and samples are gone/cascade.
- `I-CHK-04` `PATCH` to a private-IP URL → 422 (guard enforced on update too,
  not only create).
- `I-CHK-05` invalid JSON body / missing fields → 400 with `{"error":…}`
  shape, no stack trace in response.

**E2E**
- `E-CHK-01` (happy) register → create check on the stub server URL →
  dashboard HTML contains the check name → delete → gone.
- `E-CHK-02` (edge) create with `http://127.0.0.1:<port>` (the stub itself)
  → 422 SSRF; proves the guard works end-to-end (stub is loopback).

> Note 1: `E-CHK-02` needs the guard to allow an *explicit test allowlist*
> seam (env `ALLOW_PRIVATE_URLS=1` in tests only) or the stub must be
> reached via a public-looking name. The plan: tests set
> `ALLOW_PRIVATE_URLS=1` so the loopback stub is reachable, **and** a
> negative test without the flag asserts SSRF rejection. The flag must
> never be set in production config.

### F3 — Manual ping now, N=10 (story 3) · `app/sampler.py`, `app/stats.py`

**Unit**
- `U-SAMP-01` `ping()` against stub with fixed 20ms delay → returns ms in
  `[15, 500]`, status 200, size_bytes > 0 (port of `httpping` timing:
  `Date.now()`-equivalent via `time.perf_counter`).
- `U-SAMP-02` stub returns 500 → sample recorded with status 500, ms valid,
  no exception raised.
- `U-SAMP-03` stub hangs >10s → timeout error sample, function returns
  within ~10s (±1s), no thread hang.
- `U-SAMP-04` body > 1MB → read capped at 1MB, size recorded as 1MB,
  function completes.
- `U-SAMP-05` connection refused (closed port) → error sample, no crash.
- `U-SAMP-06` TLS to a non-TLS stub → error sample, no crash.
- `U-STATS-01` empty list → all stats `None`/zero-safe (no `ZeroDivisionError`,
  no `ValueError` from `min()`).
- `U-STATS-02` single sample → min=max=avg=p50=p95=p99=that value.
- `U-STATS-03` known set `[10,20,30,40,50]` → p50=30, p95≈49 (linear
  interpolation), p99≈49.6, avg=30 (assert within 0.5).
- `U-STATS-04` unsorted input → same result as sorted (function sorts/dedups
  internally).
- `U-STATS-05` errors excluded from percentiles but counted: input with
  8 ok + 2 error markers → percentiles over 8, `error_count=2`.
- `U-STATS-06` large N (10k samples) → correct p95, completes < 100ms
  (guards against O(n²) percentile code).

**Integration**
- `I-PING-01` `POST /api/checks/{id}/ping-now` → 200, `results` array of 10
  `{ms,status}` sorted by time, aggregate block present
  (min/max/avg/p50/p95/p99), errors counted separately.
- `I-PING-02` ping-now on another user's check → 404.
- `I-PING-03` ping-now with stub failing 3 of 10 → 7 ok + 3 errors,
  response is still 200, percentiles computed over the 7.

**E2E**
- `E-PING-01` (happy) ping-now against stub (20ms) → UI renders 10 rows,
  summary line matches `min/max/avg` within rounding (±1ms).
- `E-PING-02` (edge) ping-now against a dead port → all 10 error, page
  shows "all requests failed", no 500.

### F4 — History chart, 24h/7d (story 4) · `app/stats.py` bucketing, `app/static/app.js`

**Unit**
- `U-SER-01` bucketing: samples spanning 25h → 24h range yields ≤ 24 buckets,
  each `{t, avg, p95, n}`; 7d yields ≤ 42 buckets (4h each) — exact bucket
  math asserted.
- `U-SER-02` < 2 points → empty-state signal (empty list + `points: 0`),
  API returns 200 (not 404).
- `U-SER-03` gaps (no samples in a bucket) → bucket omitted or null, never
  interpolated silently.
- `U-SER-04` out-of-range samples (before/after window) excluded.
- `U-SER-05` baseline: rolling median of daily p95 over 7d (min 50 samples
  rule) — known series → expected baseline value.

**Integration**
- `I-SER-01` seed 200 samples across 24h → `GET …/series?range=24h` returns
  bucketed points with `avg` and `p95`, monotonic `t`.
- `I-SER-02` `range=30d` and `range=bogus` → 30d works; bogus → 400.
- `I-SER-03` series for another user's check → 404; unauthenticated → 401.

**E2E**
- `E-SER-01` (happy) seed samples → load check detail page → canvas element
  present, chart draws without JS error (checked via returned HTML/JS smoke:
  `node --check app/static/app.js` in CI, plus page contains the series
  JSON / data attribute).
- `E-SER-02` (edge) fresh check (0 samples) → page shows empty state text,
  no JS exception, no broken canvas.

### F5 — Regression alert (story 5) · `app/detector.py`, `app/alerts.py`, `app/scheduler.py`

**Unit**
- `U-DET-01` baseline 200ms, observed p95 200ms → no alert.
- `U-DET-02` observed 239ms (+19.5%) → no alert (below threshold).
- `U-DET-03` observed 240.1ms (+20.05%) → alert fires (custom threshold
  via `threshold_pct` respected: e.g. 10% threshold fires at +10.05%).
- `U-DET-04` < 50 baseline samples → no alert regardless of observed
  (insufficient-history guard).
- `U-DET-05` cooldown: alert fired, second regression 10 min later → no
  second alert; 6h+ later → alert allowed again.
- `U-DET-06` recovery: p95 drops back under baseline → no alert, cooldown
  state cleared.
- `U-DET-07` negative/zero baseline (empty or all-zero series) → no crash,
  no alert (division-by-zero guard).
- `U-DET-08` sustained drift: +5% per ingest for 10 ingests crossing +20%
  cumulatively → fires exactly once (not per-ingest spam).
- `U-DET-09` detector is deterministic/idempotent: same input series twice
  → same decision (no randomness, no wall-clock dependence beyond injected
  `now`).

**Integration**
- `I-ALERT-01` inject samples via `POST /api/v1/checks/{id}/samples` pushing
  p95 +25% over baseline → one row in `alerts`, alert visible via
  `GET /api/checks/{id}/alerts`; second inject within cooldown → still one.
- `I-ALERT-02` SMTP disabled (no `SMTP_*` env) → alert row still created,
  no exception, delivery skipped/logged.
- `I-ALERT-03` SMTP enabled with fake sink (`smtpd`-style stdlib server or
  monkeypatched `smtplib.SMTP` in-process) → 1 message sent, subject/body
  contain observed + baseline ms and check name.
- `I-ALERT-04` webhook configured, sink returns 500 → ingest still succeeds
  (alert delivery failure never blocks sample ingest); failure logged.
- `I-ALERT-05` `acked_at` set via UI action → alert no longer "unacked" in
  list; re-regression after ack still respects cooldown from `created_at`.

**E2E**
- `E-ALERT-01` (happy) seed baseline → inject regression → alert banner on
  dashboard ("p95 rose 212ms → 389ms" shape, per design-system) → alert
  log lists it.
- `E-ALERT-02` (edge) inject regression with only 20 baseline samples →
  no banner, no alert (min-sample guard visible in product).

### F6 — API key for CI (story 6) · `app/auth.py`, `handlers/api.py`

**Unit**
- `U-KEY-01` generate → key matches `^ll_[A-Za-z0-9]{32}$`-shape; DB stores
  only hash + prefix; raw key returned exactly once (create response).
- `U-KEY-02` authenticate: correct key → user resolved; wrong key → None;
  revoked key → None; tampered key (one char flipped) → None.
- `U-KEY-03` constant-time compare (`secrets.compare_digest`) on hashes.
- `U-KEY-04` two keys for the same user are independent (revoking one
  leaves the other valid); key for user A never resolves to user B.

**Integration**
- `I-KEY-01` `POST /api/keys` → 201 with raw key once; `GET /api/keys`
  lists prefix + created date only (no hash, no raw key).
- `I-KEY-02` `DELETE /api/keys/{id}` → subsequent `/api/v1/*` call with
  that key → 401 immediately (no caching window).
- `I-KEY-03` `/api/v1/*` without key → 401; with session cookie but no key
  → 401 (key required on v1); with key but no cookie → works (proves
  cookie-free CI path).
- `I-KEY-04` another user's key cannot ingest into my check → 404.

**E2E**
- `E-KEY-01` generate key in UI → copy → `curl`-equivalent (`urllib`) gate
  call with `Authorization: Bearer ll_…` → 200; revoke in UI → same call
  → 401.

### F7 — CI gate endpoint (story 7) · `app/gate.py`, `handlers/api.py`

**Unit**
- `U-GATE-01` observed p95 under budget → `{pass: true}`.
- `U-GATE-02` observed over budget → `{pass: false, observed_p95}` and the
  HTTP layer maps it to 422 (not 200/500).
- `U-GATE-03` exactly at budget (`p95 == budget`) → pass (≤ semantics,
  asserted and documented).
- `U-GATE-04` missing/zero/negative `p95_ms` → 422 validation error.
- `U-GATE-05` no samples yet → pass with `observed_p95: null`? or 422?
  **Decision needed from PM (desk-1) before implementation** — plan
  assumes *fail-closed*: 422 `{pass:false, reason:"no_data"}`; this test
  encodes whichever decision is recorded in the spec.
- `U-GATE-06` gate uses the same percentile function as stats (one
  implementation: gate of seeded known set == `stats.p95`).

**Integration**
- `I-GATE-01` seed samples with p95 350ms → `POST …/gate {p95_ms:400}` →
  200 `{pass:true}`; `{p95_ms:300}` → 422 `{pass:false, observed_p95:350}`.
- `I-GATE-02` gate with API key, no session cookie → works; without key
  → 401 (reuses F6 auth).
- `I-GATE-03` gate on another user's check → 404.
- `I-GATE-04` sample ingest `POST /api/v1/checks/{id}/samples {ms,status,sha}`
  → 202/201 and the sample appears in stats/series (ingest round-trip that
  the gate depends on).

**E2E**
- `E-GATE-01` (happy) the `examples/github-actions.yml` flow as a shell
  smoke: create key → ingest 10 samples → gate under budget → exit 0.
- `E-GATE-02` (error) gate over budget → HTTP 422 → smoke script exits
  non-zero (proves CI can fail a PR).

### F8 — Public report link (story 8) · `app/handlers/public.py`

**Unit**
- `U-PUB-01` slug generation: URL-safe, unique per check, stable across
  toggles (toggling off/on reuses the same slug).
- `U-PUB-02` slug collision on create (forced) → regenerated, not 500.

**Integration**
- `I-PUB-01` toggle `is_public=1` → `GET /r/{slug}` unauthenticated → 200
  with chart + stats, and the payload contains **no** `api_keys`,
  `sessions`, `pw_hash`, email, or any other user's data (field audit test:
  response keys ⊆ allowlist).
- `I-PUB-02` toggle off → `GET /r/{slug}` → 404 (same shape as nonexistent
  slug — no existence oracle: body identical for "off" vs "never existed").
- `I-PUB-03` write endpoints (`PATCH`, `POST …/ping-now`, `DELETE`) on a
  public slug's check without session → 401/404 (read-only).
- `I-PUB-04` unknown slug → 404; slug with path traversal (`../`, `%2e%2e`)
  → 404, no file read.
- `I-PUB-05` XSS probe in check name (`<script>alert(1)</script>`) →
  rendered escaped in HTML (`&lt;script&gt;`), not raw.

**E2E**
- `E-PUB-01` (happy) make check public → open `/r/{slug}` in a fresh
  `urllib` opener with **no cookies** → 200, stats + chart present.
- `E-PUB-02` (error) unpublish → same URL → 404.

### F9 — Scheduler & ingest (cross-cutting) · `app/scheduler.py`, `app/db.py`

**Unit**
- `U-SCHED-01` due-check selection: `last_checked_at + interval <= now` →
  selected; not-yet-due → skipped; exact-boundary → selected.
- `U-SCHED-02` clock skew / `last_checked_at` in the future → not due,
  no crash.
- `U-SCHED-03` ingest queue: enqueue 100 samples → all persisted, order
  preserved per check, single-writer (no partial writes on exception).
- `U-SCHED-04` DB migration idempotency: apply `schema.sql` twice →
  `PRAGMA user_version` correct, no duplicate-table error.
- `U-SCHED-05` WAL mode enabled on the connection (`PRAGMA journal_mode`).

**Integration**
- `I-SCHED-01` scheduler thread with `interval=1s` fixture against stub →
  ≥2 samples appear in DB within 3s; `last_checked_at` advances.
- `I-SCHED-02` `RUN_SCHEDULER=0` boot → no samples taken, web still serves
  (flag-gated behaviour).
- `I-SCHED-03` 20 checks all due at once → all sampled, no lost samples,
  no `sqlite3.OperationalError: database is locked` surfaced to users.

**E2E**
- `E-SCHED-01` boot with scheduler on, stub check, wait ≤3s → dashboard
  shows a first data point without any manual ping.

### F10 — Health, Docker, observability (cross-cutting) · `app/main.py`, `Dockerfile`

**Unit**
- `U-OPS-01` `/healthz` handler: DB ping OK → 200 `{"ok": true}` shape;
  DB closed (simulate) → 503 (not 500 stack trace).
- `U-OPS-02` unknown route → 404 JSON `{"error": …}`; wrong method on a
  known route → 405.

**Integration**
- `I-OPS-01` security headers on every response: `Content-Security-Policy`,
  `X-Content-Type-Options: nosniff`, `frame-ancestors` present.
- `I-OPS-02` malformed JSON to a POST → 400, server keeps serving the next
  request (no handler-thread death).

**E2E**
- `E-OPS-01` `docker build` succeeds; `docker run` (or compose) boots with
  no env keys; `GET /healthz` → 200 within 5s of start.
- `E-OPS-02` structured log line emitted for a request and contains a
  request-id (grep stdout, stdlib only).

### 2.1 Scenario count

| | Count |
|---|---|
| F1 Auth | 10 + 4 + 2 = 16 |
| F2 Check CRUD | 9 + 5 + 2 = 16 |
| F3 Ping-now & stats | 12 + 3 + 2 = 17 |
| F4 History/series | 5 + 3 + 2 = 10 |
| F5 Regression alert | 9 + 5 + 2 = 16 |
| F6 API keys | 4 + 4 + 1 = 9 |
| F7 CI gate + ingest | 6 + 4 + 2 = 12 |
| F8 Public report | 2 + 5 + 2 = 9 |
| F9 Scheduler/ingest | 5 + 3 + 1 = 9 |
| F10 Health/Docker/ops | 2 + 2 + 2 = 6 |
| **Total planned scenarios** | **120** |

That is 120 concrete test functions: **64 unit (53%) / 38 integration
(32%) / 18 e2e (15%)** — deliberately heavier on integration/e2e than the
ideal §1.1 pyramid in sprint 1, because the routing, SSRF, public-page
isolation, and scheduler wiring are new and their bugs are wiring bugs;
the split should drift toward 65/27/8 as pure modules grow.
Every scenario is happy-path, edge, or error as labelled; P1 features
(projects, channels, status page, export, Slack) are **out of scope** for
this catalog and get their own addendum when scoped.

---

## 3. Test data & fixtures strategy

### 3.1 Principles

1. **Isolation by default:** no test touches another test's data. Every
   test gets a fresh DB, fresh server port, fresh stub server. Order
   independence is a requirement, not a nicety — `unittest` runs
   alphabetically, and the suite must also pass under `pytest --random-order`
   if that plugin is ever present (no shared mutable module state).
2. **No shared global seed data** in the repo beyond code: fixtures are
   built in `tests/helpers.py` by functions, not by importing a dump file.
3. **Determinism:** wall-clock is injected (`now` parameter / fake clock)
   for detector, cooldown, session-expiry, and rate-limit tests. Network
   latency in stubs is *injected and bounded*, never asserted exactly
   (assert ranges, e.g. `[15ms, 2000ms]`).

### 3.2 DB per test

- **Unit tests** that touch the DB (`auth`, `checks`, `keys`): `sqlite3` with
  `":memory:"` + `db.init_schema(conn)` in `setUp`, closed in `tearDown`.
  Fresh per test method — SQLite `:memory:` is the fastest isolation
  available and the schema is small (9 tables).
- **Integration tests**: a real temp file via
  `tempfile.TemporaryDirectory` + `DATABASE_URL=file://…` (or env pointing
  at the temp path), because WAL behaviour, multi-connection reads, and the
  scheduler thread cannot be tested meaningfully on `:memory:`.
- **E2E**: one temp DB per *module* (class), seeded per test.
- Never use the dev/prod `sqlite` file; an `assert "test" in os.environ`
  style guard in helpers prevents accidentally pointing tests at real
  data.

### 3.3 Seed data (factory functions in `tests/helpers.py`)

| Factory | Returns | Notes |
|---|---|---|
| `make_user(email=None, plan="free")` | user dict + session cookie | unique email via `uuid4` hex; pw = `"correct-horse-9"` (then hashed normally — pbkdf2 at 200k iters is ~50ms, acceptable; helpers may use a low-iteration override *only* behind an env flag, with one test asserting prod iterations ≥ 100k). |
| `make_check(user, url=STUB_URL, interval=60, **kw)` | check dict + id + slug | defaults to the loopback stub URL; `is_public=0`. |
| `seed_samples(check, n, base_ms, spread_ms, start_ts, status=200)` | list of sample rows | deterministic pseudo-random via `random.Random(42)` — same seed every run, so percentile expectations are stable. |
| `make_regression_series(check)` | baseline 7d at ~200ms p95, then +25% | shared by detector integration + e2e alert tests. |
| `make_api_key(user)` | `(raw_key, prefix)` | raw key held only in the test's memory. |
| `public_check(user)` | check with `is_public=1` + slug | for F8 tests. |

**Seed users:** exactly two canonical users — `alice@example.com`
(owner of most fixtures) and `bob@example.com` (the "other user" for all
404/isolation tests). Plus a `pro` user for plan-limit tests. No other
identities; everything else is generated per-test with `uuid`.

### 3.4 HTTP fixtures

- `EphemeralServer` (context manager): starts `ThreadingHTTPServer` on
  `127.0.0.1:0`, yields `base_url`, shuts down cleanly. One per test class
  where possible, one per test where scheduler/concurrency is involved.
- `StubTarget`: loopback HTTP server with routes `/ok` (20ms), `/slow`
  (300ms), `/fail` (500), `/hang` (sleeps 30s), `/big` (2MB body),
  `/redirect-private` (302 → `169.254.1.1`). Threading, so concurrent
  pings don't serialize.
- Client wrappers: `http_get/post/patch/delete(base, path, cookie=…,
  api_key=…) -> (status, headers, json)`, built on `http.client` /
  `urllib.request`. They must **not** follow redirects silently (assert the
  redirect behaviour explicitly where relevant).

### 3.5 Fake external sinks

- **SMTP:** monkeypatched `smtplib.SMTP` (in-process fake recording
  `(from, to, subject, body)`) — no socket, no creds. One integration test
  may use a real stdlib `smtpd` debug server on loopback if desired, but
  the fake is the default.
- **Webhook:** `StubTarget` route that records method/headers/body and
  returns a configurable status (200/500). Never a real external URL.
- **Clock:** a `FakeClock` (`now()`, `advance(seconds)`) injected into
  detector/scheduler/auth; tests call `advance(6*3600+1)` instead of sleeping.

---

## 4. Performance / load test plan

Goals come from product-spec §5: **scheduler uptime ≥ 99.9%, p95 ingest
latency < 2s**. Load testing the *checked endpoints* is a non-goal
(spec §6); this section loads **LatencyLedger itself**.

### 4.1 Benchmark script design — `scripts/bench.py` (stdlib only)

```
python scripts/bench.py --scenario ingest      # concurrent sample POSTs
python scripts/bench.py --scenario read        # dashboard/series GETs
python scripts/bench.py --scenario ping        # concurrent ping-now
python scripts/bench.py --scenario mixed       # ingest + read + gate + public
python scripts/bench.py --scenario scheduler   # N due checks, 1 scheduler tick
```

Common design (all scenarios):
- Spawns the real server in-process (or as a subprocess with a temp DB) on
  an ephemeral port; seeds a fixed dataset (deterministic `Random(42)`).
- Uses `concurrent.futures.ThreadPoolExecutor` + `http.client`
  connections; ramps 1 → 10 → 50 → 100 → 200 concurrent workers in steps,
  holding each step 10s.
- Records per-request latency with `time.perf_counter`; reports
  p50/p95/p99/max + error rate + throughput (req/s) per step as JSON to
  stdout and `bench-report.json`.
- Hard guardrail: **loopback target only** — the script refuses to run
  against a non-`127.0.0.1` URL (SSRF-style self-protection), so it can
  never be pointed at a third-party site.
- Not part of the merge gate (§8); run manually and nightly in CI
  (artifact only).

### 4.2 Targets

| Scenario | Load | Pass bar |
|---|---|---|
| **P-INGEST** | 50 concurrent CI clients POSTing samples to distinct checks | p95 < 2s (spec), error rate 0, no `database is locked` visible to clients |
| **P-READ** | 100 concurrent dashboard + series GETs (logged-in) | p95 < 500ms, error rate 0 |
| **P-PING** | 20 concurrent `ping-now` (N=10 each vs stub) | all 200 responses complete, p95 < 15s (10 sequential × ~50ms + overhead), no thread starvation |
| **P-MIXED** | 30 ingest + 30 read + 10 gate + 20 public-page GETs | p95 overall < 2s, error rate < 0.1%, SQLite WAL shows no writer deadlock |
| **P-SCHED** | 200 checks due in the same tick | all 200 sampled within 60s, zero lost samples, scheduler heartbeat logged |

Baseline hardware note: targets are for a modest CI/dev VM (2 vCPU,
SQLite on SSD/tmpfs). On slower hardware, the *relative* shape matters
(no cliff, no error-rate knee) rather than the absolute numbers; record
machine specs in the bench report.

### 4.3 Out of scope

Load-testing user endpoints through the checker, browser rendering
performance, k6/Gatling-style distributed load — all non-goals per spec §6.

---

## 5. Beta / UAT plan

### 5.1 Phases

| Phase | Audience | Entry criteria | Exit criteria |
|---|---|---|---|
| **Alpha (M1)** | The team + 5 friendly devs, internal Docker deploy | §8 merge gates green; `E-*` suite green on the release candidate | All P0 stories walked through ( §5.2 checklist); zero Sev-1/Sev-2 open |
| **Beta (M2)** | ~20 invited small-team devs (GitHub invite → `docker compose up` or hosted trial) | Alpha exit signed; README quickstart verified on a clean machine | §5.2 sign-off; activation metric instrumented; ≥1 true regression alert delivered to a beta user |
| **Launch (M3)** | Public | Beta exit signed; CI-gate example (`examples/github-actions.yml`) proven in a real PR | — |

### 5.2 Acceptance sign-off process

1. **Candidate freeze:** QA lead tags `rc-<date>`; no code changes except
   Sev-1 fixes (re-tag) after freeze.
2. **PM walkthrough (desk-1):** PM runs the 8 P0 stories against the
   candidate using the AC in product-spec §2, checking each off in the
   sign-off table below. **A story is accepted only with a recorded
   pass/fail per acceptance criterion** — "looked fine" is not a pass.
3. **QA lead verification:** QA re-runs the automated suite (§1) on the
   exact tagged commit and attaches `test-report.json`; spot-checks the
   two highest-risk behaviours: SSRF guard (F2) and public-report isolation
   (F8, field audit).
4. **Beta feedback loop:** beta users get a bug-report template (§5.4) and
   a "was this alert useful?" affordance on every alert (feeds the ≥70%
   alert-precision KPI in spec §5). Feedback is triaged weekly by PM + QA.
5. **Sign-off record:** the table below is filled in the release notes;
   launch requires PM signature + QA signature. No signature → no launch.

| P0 story | PM pass/fail | QA pass/fail | Notes / bug IDs |
|---|---|---|---|
| 1 Sign up / log in | | | |
| 2 Add a URL check | | | |
| 3 Manual ping now | | | |
| 4 History chart | | | |
| 5 Regression alert | | | |
| 6 API key for CI | | | |
| 7 CI gate endpoint | | | |
| 8 Public report link | | | |

### 5.3 Bug severity definitions

| Severity | Definition | Examples | Response |
|---|---|---|---|
| **Sev-1 (blocker)** | Data loss, security hole, or core P0 flow broken on the happy path | SSRF bypass; public page leaks API keys; register/login broken; gate returns wrong pass/fail; samples lost | Fix before any release; re-run full §6 checklist |
| **Sev-2 (major)** | P0 feature broken in an edge/error path, or alert false-negative/positive at threshold | ping-now crashes on all-error stub; detector fires with <50 samples; revoke doesn't take effect immediately | Must fix for launch; fix for beta→public |
| **Sev-3 (minor)** | Working but wrong/awkward; workaround exists | chart bucket off-by-one at 24h boundary; cookie missing SameSite; flaky 429 message | Fix in next sprint; track in backlog |
| **Sev-4 (cosmetic)** | Visual/copy/polish only | label truncation, spacing, wording | Backlog; batch with design fixes |

Severity is assigned by the QA lead at triage, disputes resolved by PM.
False-positive alerts (Sev-2 when systematic) and false-negative alerts
(Sev-1 because the product's core promise is detection) — the severity
asymmetry is deliberate.

### 5.4 Bug report template

```markdown
**Severity:** Sev-1 / Sev-2 / Sev-3 / Sev-4   (QA lead confirms at triage)
**Title:** [short imperative summary]

**Environment:** docker/hosted · version or commit · OS · Python version
**P0 story affected:** 1–8 (spec §2) or "none"

**Steps to reproduce:**
1.
2.
3.

**Expected:** …
**Actual:** …

**Evidence:** request/response (headers+body, keys redacted), alert log
excerpt, screenshot/video, or `test-report.json` / bench report attached.
Note whether the alert was useful (yes/no) if alert-related.

**Frequency:** always / often / once · first seen: <date>
```

---

## 6. Regression checklist per release

Run in full on every release candidate; every item must pass or be
explicitly waived by PM + QA with a recorded reason. Items map to the
catalog so a failure points at the tests to re-run.

- [ ] **R-01 Full suite green:** `python scripts/run_tests.py` → 100% pass
      (or only documented skips) on the tagged commit.
- [ ] **R-02 Auth smoke:** register → login → me → logout (E-AUTH-01);
      wrong-password rate limit (E-AUTH-02).
- [ ] **R-03 Check CRUD + SSRF:** E-CHK-01, E-CHK-02; private-IP create → 422.
- [ ] **R-04 Ping-now:** E-PING-01 (summary matches), E-PING-02 (all-error).
- [ ] **R-05 History:** E-SER-01 (chart renders), E-SER-02 (empty state).
- [ ] **R-06 Regression alert:** E-ALERT-01 fires at +25% with banner;
      E-ALERT-02 silent below 50 samples; cooldown holds (I-ALERT-01).
- [ ] **R-07 API keys:** E-KEY-01; revoke → 401 on next v1 call (I-KEY-02).
- [ ] **R-08 CI gate:** E-GATE-01 exit 0 under budget; E-GATE-02 non-zero
      over budget; `examples/github-actions.yml` still valid YAML and
      references real endpoints.
- [ ] **R-09 Public report:** E-PUB-01 no-cookie 200; E-PUB-02 → 404 after
      unpublish; field audit (I-PUB-01) re-run — no keys/hashes/emails.
- [ ] **R-10 Scheduler:** E-SCHED-01 first sample without manual ping;
      `RUN_SCHEDULER=0` boot still serves web (I-SCHED-02).
- [ ] **R-11 Ops:** E-OPS-01 Docker build + `/healthz` 200; security
      headers present (I-OPS-01); unknown route → JSON 404.
- [ ] **R-12 Migration:** fresh boot + boot over an existing DB both
      succeed (schema idempotency, U-SCHED-04); `PRAGMA user_version`
      unchanged if no new migration.
- [ ] **R-13 Perf spot-check:** `bench.py --scenario mixed` at 50 workers
      → p95 < 2s (or within 20% of the previous release's recorded p95).
- [ ] **R-14 Docs parity:** README quickstart commands copy-paste-run on a
      clean machine; product-spec AC and this plan agree on the
      U-GATE-05 no-data decision.

---

## 7. Coverage targets & measurement

### 7.1 Targets (line coverage, per module)

Overall floor mirrors spec §5 (≥70% on core). Sprint-1 targets:

| Module | Target | Why |
|---|---|---|
| `app/stats.py` | **≥ 90%** | pure, cheap to cover; the product's credibility lives here |
| `app/detector.py` | **≥ 90%** | the core promise (alert accuracy) |
| `app/gate.py` | **≥ 90%** | one wrong boolean fails a user's CI |
| `app/auth.py` | **≥ 85%** | security-sensitive; every branch matters |
| `app/checks.py` (incl. SSRF guard) | **≥ 85%** | the abuse-resistance surface |
| `app/sampler.py` | **≥ 80%** | network edge cases dominate; stub covers most |
| `app/router.py`, `handlers/*` | **≥ 70%** | wiring; integration tests cover the routes |
| `app/scheduler.py`, `app/alerts.py`, `app/db.py` | **≥ 60%** | threading/timing code — cover the logic, not every sleep path |
| `app/main.py`, `app/config.py` | **≥ 40%** | boot/config paths, covered by e2e smoke rather than unit |
| `app/static/*.js` | n/a (syntax-checked) | `node --check` in CI; no JS coverage harness in stdlib |
| **Whole `app/`** | **≥ 75%** | floor; spec §5's 70% is the minimum, this plan holds 75% |

Branch coverage is aspirational for `stats`/`detector`/`gate` (≥ 85%
branch); line coverage is the enforced gate.

### 7.2 How to measure (stdlib-first)

1. **Preferred — `coverage.py` if present:** if it is declared in
   `requirements-dev.txt` (allowed as a *dev* dep, never a runtime dep),
   CI runs `coverage run -m unittest discover` + `coverage report` and
   the gate in §8 reads the per-module numbers from `coverage json`.
2. **Default — stdlib `trace`:** `scripts/run_tests.py` supports
   `--coverage` which wraps the suite in `trace.Trace(count=1, trace=0)`:
   ```python
   tracer = trace.Trace(count=1, trace=0)
   tracer.run("unittest.main(module=None, exit=False)")
   counts = tracer.results().counts   # (filename, lineno) -> hits
   ```
   then intersects counted lines with executable lines per module
   (`trace`-style `coverdir` output, or a small linecount helper that
   skips blanks/comments/imports) to produce a per-module percentage.
   `trace` requires running the suite under the tracer, so it is slower
   (~5–10× in-process) — acceptable for the nightly/coverage job, not the
   per-push gate if it slows CI badly.
3. **Fallback — line counting ratio:** if neither is wired, QA manually
   reports `covered test functions / planned test functions` per module
   from the catalog (§2) as a proxy, and flags any module below its
   target. This fallback expires once `trace` support ships in
   `scripts/run_tests.py` (sprint 1 deliverable).

Coverage is reported per PR as an artifact (`coverage.json`); drops
below the module target fail CI per §8 — with one exception: a *new*
module may land at ≥ 50% in its first PR if the author files a follow-up
issue and the QA lead approves the waiver in the PR.

---

## 8. CI gating rules (what must pass to merge)

CI: GitHub Actions, `.github/workflows/ci.yml` (stdlib-only steps;
`actions/checkout` + `actions/setup-python` only — no paid test services).
Every PR and every direct push to `main` runs the same jobs; `main` is
branch-protected with "require status checks" once the workflow exists.

| Job | Command | Gate |
|---|---|---|
| **unit+integration** | `python -m unittest discover -s tests -v` (or `pytest -q` if installed) | **Must pass 100%.** Any failure blocks merge. No `xfail`/skip without a linked issue + QA approval. |
| **report** | `python scripts/run_tests.py --json test-report.json` | Artifact uploaded; counts must match catalog totals (120 planned; skips explicitly listed). |
| **coverage** | `python scripts/run_tests.py --coverage` (stdlib `trace`) | **Must meet §7.1 per-module targets** and ≥75% overall. Waiver only as in §7.2. |
| **syntax/static** | `python -m compileall app tests`, `node --check app/static/app.js` (if Node present) | Must pass. |
| **smoke (e2e)** | `bash scripts/smoke.sh` (boots server, runs E-* happy paths) | **Must pass** on PRs touching `app/`, `app/static/`, `Dockerfile`, or `docs/` examples. |
| **docker** | `docker build -t latency-ledger:ci .` + boot + `curl /healthz` | Must pass on PRs touching `Dockerfile`/`app/`; may be `continue-on-error` only until the Docker image is in the merge path — then it becomes required. |
| **bench (nightly/manual)** | `python scripts/bench.py --scenario mixed` | **Not a merge gate.** Artifact only; regressions discussed, not blocked. |
| **docs** | Markdown link check is manual; `examples/github-actions.yml` YAML-parsed by the smoke job | Must parse; broken links filed as Sev-3. |

### Merge rules

1. **Green CI required:** all required jobs above pass on the exact commit
   being merged. Reruns must be on the same commit (no "push a fix, merge
   the old run").
2. **No test deletion to make CI green.** Deleting or skipping a test
   requires the QA lead's approval in the PR and, if the behaviour is
   still required, a replacement test in the same PR.
3. **New P0 behaviour = new tests in the same PR.** A PR that adds or
   changes a P0 feature without tests for it (catalog IDs) is not mergeable.
4. **Coverage may not drop** below prior `main` for touched modules.
5. **No secrets in CI logs/artifacts:** test-report and bench-report are
   checked for accidental `ll_…` keys / pw hashes before upload (a grep
   step in the workflow; the fixtures use obviously-fake values anyway).
6. **Releases:** merging to `main` does not auto-release; releases follow
   §5.2 sign-off and §6 checklist on a tag.

---

## 9. Risks, assumptions & open decisions

- **Pytest vs stdlib runner:** the brief asks for stdlib `unittest` + a
  custom runner; `architecture.md` mentions `pytest`. This plan resolves
  the overlap by writing tests as `unittest.TestCase` (both runners work)
  and keeping the *default* gate stdlib-only. If the team prefers pytest,
  it is added as a dev-only pip dep — the catalog is unchanged.
- **U-GATE-05 (no-data gate verdict)** needs a PM decision (desk-1):
  fail-closed (422) vs pass-with-null. Test encodes the recorded decision.
- **SSRF test seam:** `ALLOW_PRIVATE_URLS=1` env for tests (F2 note 1)
  must be confirmed by the implementer and must default to `0` in prod.
- **pbkdf2 cost in tests:** 200k iterations × ~120 tests is fine, but
  helpers should use a single shared precomputed hash for fixture users,
  with exactly one test asserting real iteration counts.
- **Flakiness budget:** integration/e2e tests use bounded waits (poll with
  deadline, e.g. 3s) instead of fixed `sleep`s; any test that flakes twice
  is quarantined (skipped with issue link) within one sprint, never
  silently re-run-and-ignored.
- **Frontend JS:** no automated browser tests in sprint 1 (no paid tools,
  no Playwright in stdlib). Coverage is `node --check` + HTML/JSON contract
  assertions + the UAT walkthrough (§5.2). This is an accepted risk;
  revisit if the chart JS grows.

---

*Owner: QA lead (desk-8). Reviewers: Product Manager (desk-1) for §5/§9
decisions, implementing engineers for §3/§4 feasibility. Update this
document in the same PR as any change to P0 scope, coverage targets, or
CI gates.*
