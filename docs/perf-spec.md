# LatencyLedger — Performance Specification

> **Owner:** Performance Engineer · **Status:** Spec only — no implementation yet
> **Product:** `LatencyLedger` — continuous API latency-regression tracking + CI gates (see `docs/product-spec.md`, `docs/architecture.md`)
> **Constraints (hard):** Python 3.11+ **stdlib only**, single-host friendly, **no build step**, no Redis/CDN/paid services required to boot.
> **Companion docs:** `docs/product-spec.md`, `docs/architecture.md`, `docs/design-system.md`, `docs/ops-growth-spec.md`
>
> All budgets are **p95 on a 1 vCPU / 512 MB single host** (the documented Docker self-host target), measured locally unless stated. Budgets are SLOs, not aspirations: a PR that regresses them without justification + backlog entry fails CI (§8).

---

## 1. Performance budgets

### 1.1 Web Vitals (dashboard, check detail, public report — desktop + Moto G4 emulation)

| Metric | Target (p75, field/lab) | Stretch | Why |
|---|---|---|---|
| **LCP** | **≤ 1.8 s** | ≤ 1.2 s | First meaningful paint = stat tiles + chart. Static HTML, no render-blocking JS. |
| **INP** | **≤ 200 ms** | ≤ 100 ms | Ping-now, filter, tooltip interactions. |
| **CLS** | **≤ 0.05** | ≤ 0.01 | Canvas + tiles reserve fixed height; no late font/layout swaps (system fonts only). |
| TTI | ≤ 2.5 s | ≤ 1.8 s | Full interactivity on Fast 3G. |
| FCP | ≤ 1.0 s | — | Server-rendered shell, no JS required for first paint. |

Measurement: Lighthouse (lab, CI smoke) + RUM beacons (`POST /api/v1/rum`, best-effort, sampled 10%) aggregated weekly. If LCP/INP/CLS breach for 7d, file P0 backlog item (§9) — do not silently raise the budget.

### 1.2 API latency — server-side p95 (excluding upstream target latency for `ping-now`)

| Endpoint class | p50 | **p95 budget** | p99 (alert only) | Notes |
|---|---|---|---|---|
| `GET /healthz` | <5 ms | **≤ 25 ms** | ≤ 50 ms | DB ping + scheduler heartbeat. Must never queue behind ingest. |
| Auth (`register`/`login`/`logout`/`me`) | ≤60 ms | **≤ 150 ms** | ≤ 300 ms | Dominated by `pbkdf2_hmac` 200k iters (~60–90 ms). Budget assumes 1 vCPU; see §3.5 for tuning. |
| Checks CRUD (`GET/POST /api/checks`, `PATCH/DELETE /{id}`) | ≤30 ms | **≤ 100 ms** | ≤ 200 ms | Includes SSRF DNS resolve on create. |
| `GET /api/checks/{id}/stats` | ≤50 ms | **≤ 200 ms** | ≤ 400 ms | Percentiles + rolling baseline; cached (§6). |
| `GET /api/checks/{id}/series?range=24h\|7d\|30d` | ≤60 ms | **≤ 200 ms** | ≤ 400 ms | Server-side bucketing (§3.3); ≤500 points returned. |
| `GET /api/checks/{id}/alerts`, `GET /api/keys` | ≤30 ms | **≤ 100 ms** | ≤ 200 ms | Paginated lists. |
| `POST /api/checks/{id}/ping-now` | — | **≤ 12 s wall** (10 × 10 s timeout + slack) | — | Budget is *wall time*, not server CPU; server must stream/admit ≤4 concurrent ping-nows (§7). Returns partial results on timeout, never hangs. |
| `POST /api/v1/checks/{id}/samples` (CI ingest) | ≤30 ms | **≤ 100 ms** | ≤ 200 ms | Single-row insert + detector enqueue (detector is async, §3.4). |
| `POST /api/v1/checks/{id}/gate` | ≤50 ms | **≤ 150 ms** | ≤ 300 ms | Reads cached stats; no full percentile recompute on hot path. |
| `GET /r/{slug}` (public report, HTML) | ≤80 ms | **≤ 250 ms** | ≤ 500 ms | Includes chart data fetch; no auth lookup. |
| Static assets (`/static/*`) | ≤5 ms | **≤ 25 ms** (disk/gzip) | ≤ 50 ms | Served from memory cache after first hit (§2.3). |

Error budget: 5xx < 0.1% of requests (excl. 4xx). Any endpoint breaching p95 for 3 consecutive load-test runs (§4) is a release blocker.

### 1.3 Query time budgets (SQLite, warmed page cache)

| Query class | Budget | Mandatory index |
|---|---|---|
| Point lookup (`checks` by id, `sessions` by id, `api_keys` by hash) | ≤ 5 ms | PK / `UNIQUE` |
| Dashboard list (user's checks + latest sample per check) | ≤ 50 ms | `(user_id, created_at)`, `(check_id, ts DESC)` |
| Series bucketing (≤ 30d, ≤ 10k raw rows → ≤500 buckets) | ≤ 50 ms | `(check_id, ts)` |
| Percentile / baseline over ≤ 10k rows | ≤ 100 ms | `(check_id, ts)`; computed in Python over fetched `ms` column only |
| Ingest insert (1 sample + detector counters) | ≤ 10 ms | — |
| Alert/delivery listing (paginated) | ≤ 30 ms | `(check_id, created_at DESC)` |

Rule: **no query may do a full table scan** (`EXPLAIN QUERY PLAN` shows `SCAN` without `USING INDEX`) on `samples`, `checks`, or `alerts` in production code paths. See §5.3.

---

## 2. Frontend performance (no build step)

### 2.1 Asset budget (gzipped, initial load per page)

| Asset | Budget | Notes |
|---|---|---|
| `index.html` / `check.html` / `r.html` (each) | **≤ 15 KB** | Inline critical CSS only (§2.4); no inline JS except 1-line config. |
| `style.css` (all pages) | **≤ 12 KB** | Single file, no `@import`, no web fonts. |
| `app.js` (all pages) | **≤ 35 KB** | Vanilla JS, no framework, no chart lib (hand-rolled canvas). |
| **Total initial (HTML+CSS+JS, gzipped)** | **≤ 70 KB** | **Hard CI gate (§8).** Raw (ungzipped) ≤ 150 KB. |
| Per additional page chunk | ≤ 10 KB | Lazy-loaded via `<script defer>` + dynamic import-free `fetch` of page JS only. |
| Images / fonts / third-party | **0** | No CDN, no web fonts, no tracking pixels. System font stack per design-system. Icons = inline SVG ≤ 2 KB total. |

If a feature needs more, it must remove something else or move the code behind `defer` + on-demand load and document the trade-off in the PR.

### 2.2 Caching headers (stdlib `http.server` handler sets these)

```
Cache-Control: public, max-age=31536000, immutable   # /static/*.{css,js,svg} — versioned by content hash in filename (?v=sha or -<hash> suffix)
Cache-Control: no-cache                               # HTML pages (index/check/r) — revalidate, allow conditional GET
ETag: "<sha256-of-body>"                              # all static + HTML; 304 on match (stdlib: manual If-None-Match check)
Vary: Accept-Encoding
```

No `Cache-Control` on `/api/*` (except `no-store` on auth responses). HTML never `immutable` — invalidation is by revalidation.

### 2.3 Gzip via stdlib

- `gzip` module only (no `zlib` pre-compression files, no external compressor). Pre-compress at first request, cache bytes in memory keyed by `(path, mtime)` (§6).
- Serve `Content-Encoding: gzip` only when client sends `Accept-Encoding: gzip` **and** asset is ≥ 1 KB (smaller files cost more to compress than they save).
- Compression level **6** (stdlib default balance); do not use 9 — CPU cost on 1 vCPU outweighs ~2% size gain.
- `Content-Length` must be the compressed length; `ETag` computed on the *uncompressed* body so it is stable across encodings.

### 2.4 Critical CSS (no build step)

- Critical CSS (above-the-fold layout: header, stat tiles, chart container) inlined in a single `<style>` block ≤ **4 KB** in each HTML file. It must render the shell correctly with **`style.css` and `app.js` blocked** (progressive enhancement).
- Full `style.css` loaded with `<link rel="stylesheet">` (not `@import`, not JS-injected) — with the budget above it is not render-blocking beyond one RTT on same host.
- No framework CSS, no unused selectors: CI greps for selectors with no matching HTML class/id and fails on >10% dead rules.

### 2.5 Rendering budget

- Chart: canvas only (no SVG/DOM nodes per point); redraw ≤ 16 ms/frame; use `requestAnimationFrame` + dirty-flag, throttle tooltip to rAF.
- Data: fetch ≤ 500 bucket points (§3.3); render from cached JSON — no per-point DOM creation.
- No `innerHTML` with untrusted data (XSS + perf); build nodes via `createElement`/`textContent` or escape.

---

## 3. Backend performance

### 3.1 SQLite tuning (single file, WAL)

Set on **every** connection (in `db.py`, enforced by a `PRAGMA` check on boot):

```sql
PRAGMA journal_mode=WAL;          -- concurrent readers + 1 writer
PRAGMA busy_timeout=5000;         -- 5s; scheduler retries, never crashes on SQLITE_BUSY
PRAGMA cache_size=-64000;         -- 64 MB page cache (negative = KiB)
PRAGMA synchronous=NORMAL;        -- safe with WAL; FULL only for auth writes if needed
PRAGMA temp_store=MEMORY;
PRAGMA mmap_size=268435456;       -- 256 MB mmap (read-mostly series queries)
PRAGMA page_size=4096;            -- set at DB creation, not per-connection
PRAGMA foreign_keys=ON;
PRAGMA wal_autocheckpoint=1000;   -- checkpoint at ~4 MB, keeps WAL bounded
```

- **Single-writer discipline:** all writes go through one queue (scheduler ingest queue, §3.4). Readers use separate read-only connections (`mode=ro` URI) so a long stats query never blocks ingest.
- **Transactions:** short, `BEGIN IMMEDIATE` only for writes; batch ingest (up to 100 samples/tx) — never hold a write tx during network I/O (webhook/email).
- **Vacuum/analyze:** `ANALYZE` weekly (cron via scheduler, off-peak); `PRAGMA optimize` on boot. `VACUUM` only manually — it locks the DB.
- **Auth writes:** `synchronous=FULL` is acceptable for `register`/`login` (low QPS) if durability matters more than the ~5 ms cost; document the choice in `db.py`.
- File location: `/data/latencyledger.db` on a mounted volume (never tmpfs — SQLite + WAL needs real fsync semantics). CI uses a temp dir.

### 3.2 Pagination discipline

- **Cursor pagination everywhere** (no `OFFSET` beyond page 1 — O(n) skip cost). Cursor = `(created_at, id)` tuple, opaque-base64 in the response.
- Defaults: `limit=50`, `max_limit=200` for list APIs; `series` returns ≤ 500 buckets (§3.3).
- Every list response returns `{items, next_cursor, total_estimate}` — `total_estimate` from `COUNT(*)` only if the table is < 100k rows for that user, else omit (no expensive count on hot path).
- Hard cap: no endpoint may return > 200 rows or > 256 KB JSON in one response.

### 3.3 N+1 avoidance

- Dashboard list: **1 query** for checks + **1 query** for latest samples via `ROW_NUMBER() OVER (PARTITION BY check_id ORDER BY ts DESC)` or a `MAX(ts)` join — never a query per check.
- Stats/series: **1 query** fetching `(ts, ms, status)` for the range; percentile + bucketing in Python (stdlib `statistics` / manual sort). Never fetch-then-query-per-bucket.
- Alerts/deliveries: single `JOIN` to `alert_channels`; no per-alert delivery lookup.
- Code-review rule: any loop containing a SQL call is a **P0 defect** unless the loop is over a fixed ≤5-item constant and documented. CI has a `grep` gate for `for .*:` + `execute(` proximity (§8).

### 3.4 In-process caching policy (backend)

See §6 for the full architecture. Principles here:

- Cache **reads**, never writes. Every cache entry has a TTL and an explicit invalidation trigger — no `cache forever`.
- In-memory only (`functools.lru_cache` or a small `dict`+`TTLCache`-style class hand-rolled in `cache.py` — stdlib only). Bounded size (max 5,000 entries / 64 MB; evict LRU). No cross-process coherence needed (single host; split web/worker in P2 reintroduces a shared-cache decision — see backlog).
- **Never cache:** auth session validation result across requests without re-checking revocation (revoke must be immediate — check `sessions.revoked_at` on every request, cheap indexed lookup). Cache password-hash verification result for ≤ 5 s to absorb login bursts, keyed by `(email, pw_hash)` — safe because hash is the identity.
- Scheduler ingest and detector must bypass the cache and write through to SQLite, then invalidate affected keys (§6).

### 3.5 The `pbkdf2_hmac` cost (auth budget driver)

200k iterations ≈ 60–90 ms on 1 vCPU — this dominates the auth p95 (§1.2). Rules:

- Never run PBKDF2 in the request thread for more than one user at a time under load: a semaphore (max 2 concurrent PBKDF2, stdlib `threading.Semaphore`) + 429 with `Retry-After` beyond that. Prevents a login burst from starving ingest.
- Do not lower iterations below 200k without a security review. If auth p95 breaches, scale CPU before touching iterations.

### 3.6 Scheduler / sampler

- One thread per due check, bounded by a semaphore (**max 8 concurrent fetches**). Each fetch: 10 s timeout, 1 MB body cap, redirects off.
- Ingest is **async**: sampler writes to an in-memory queue; a single writer drains it in batches (§3.1). Detector runs on the writer thread, never blocks the sampler.
- If the queue exceeds 1,000 pending samples, drop oldest + log (shed load, don't OOM) — monitored via `/healthz` (`ingest_queue_depth`).

---

## 4. Load test plan (urllib-based, stdlib only)

### 4.1 Harness: `tools/loadtest.py`

- Pure stdlib: `urllib.request` + `concurrent.futures.ThreadPoolExecutor` (no `requests`, `locust`, or k6). Runs against a local Docker instance (`docker compose up -d` + temp DB).
- CLI: `python tools/loadtest.py --scenario <name> --rps <n> --duration <s> --base-url http://localhost:8000`
- Output: JSON summary to stdout (`{scenario, rps_achieved, p50, p95, p99, error_rate, max_rss_mb}`) + human table. Exit code 0/1 against thresholds (§4.3).
- Seeding: creates 1 test user + 10 checks via the real API (not direct DB writes), so the test exercises auth + validation.

### 4.2 Scenarios

| # | Scenario | Load | Exercises |
|---|---|---|---|
| S1 | **Baseline read** | 20 req/s, 60 s: `GET /api/checks`, `GET /{id}/series?range=7d`, `GET /{id}/stats` | Dashboard + chart hot path |
| S2 | **CI gate burst** | 50 req/s, 30 s: `POST /api/v1/checks/{id}/gate` + `POST .../samples` | API-key auth, ingest, gate cache |
| S3 | **Auth burst** | 10 logins/s, 30 s (correct + wrong passwords) | PBKDF2 semaphore, rate limit |
| S4 | **Scheduler soak** | 60 s, 20 checks @ 5 s interval against a local stub target with injected 50–200 ms latency | Sampler concurrency, ingest queue, detector |
| S5 | **Public report** | 30 req/s, 30 s: `GET /r/{slug}` (uncached + cached mix) | Public path, static gzip |
| S6 | **Ping-now fan-out** | 5 concurrent `POST /api/checks/{id}/ping-now` (N=10) repeatedly for 60 s | Sampler semaphore, partial-failure handling |

### 4.3 Success thresholds (must pass on 1 vCPU / 512 MB)

| Scenario | p95 | Error rate | Max RSS | Notes |
|---|---|---|---|---|
| S1 | ≤ 200 ms (series/stats), ≤ 100 ms (list) | < 0.5% | ≤ 512 MB | No 5xx. |
| S2 | ≤ 150 ms (gate), ≤ 100 ms (ingest) | < 0.5% | ≤ 512 MB | No `SQLITE_BUSY` 5xx (busy_timeout absorbs). |
| S3 | ≤ 150 ms (login) | < 1% (429 allowed, not 5xx) | ≤ 512 MB | Semaphore holds; ingest (S4 concurrent) not starved. |
| S4 | ingest p95 ≤ 2 s (§product KPI) | < 1% sample loss | ≤ 512 MB | Queue depth < 500 at end; no deadlock. |
| S5 | ≤ 250 ms | < 0.5% | ≤ 512 MB | Gzip cache hit rate > 90% after warmup. |
| S6 | wall ≤ 12 s per ping-now | 0 hung requests (all return ≤ 12 s) | ≤ 512 MB | Partial results acceptable; hang = fail. |

Runs: S1–S6 on every release candidate; S4 (soak) nightly for 10 min. Results archived as `loadtest-<date>-<scenario>.json` in CI artifacts; a >20% p95 regression vs the previous archived run fails the build (§8).

---

## 5. Profiling guide

### 5.1 CPU hot paths (`cProfile`, stdlib)

```bash
# Unit-level (stats/detector hot path)
python -m cProfile -s cumulative -m pytest tests/test_stats.py tests/test_detector.py -q

# End-to-end (ephemeral server + loadtest S1)
python -m cProfile -o /tmp/prof.out -m app.main          # then drive traffic
python -c "import pstats; pstats.Stats('/tmp/prof.out').sort_stats('cumulative').print_stats(30)"
```

Rules:

- Profile **before** optimizing. A change without a before/after `cProfile` diff (top-10 cumulative) is rejected in review.
- `stats.py` percentile/baseline and `detector.py` are the expected hot paths; if `router.py`/`auth.py` (non-PBKDF2) appears in the top 5, that's a bug, not a tuning opportunity.
- For line-level detail use `line_profiler` only if available — **never require it** (stdlib-only constraint); `cProfile` + manual timers (`time.perf_counter()` around suspect blocks, logged at DEBUG) are sufficient.

### 5.2 Memory

```bash
python -X tracemalloc -m app.main     # or: tracemalloc.start() in tests
```

- Watch for: unbounded `dict`/`list` growth in sampler queue, cache (§6) exceeding its 64 MB cap, and `samples` row materialization (fetch `ms` only, never `SELECT *` on wide rows).
- CI: `tracemalloc` snapshot in `tests/test_stats.py` for a 10k-row series — assert peak < 20 MB.

### 5.3 Query discipline (`EXPLAIN QUERY PLAN`)

- Every new query ships with its `EXPLAIN QUERY PLAN` output in the PR description. Acceptable: `SEARCH ... USING INDEX`. **Reject:** `SCAN` on `samples`/`checks`/`alerts`/`deliveries`, or `USE TEMP B-TREE FOR ORDER BY` on a hot path without a backlog entry.
- Helper for devs:

  ```python
  # tools/explain.py — paste a query, get the plan
  import sqlite3
  con = sqlite3.connect("file:latencyledger.db?mode=ro", uri=True)
  for row in con.execute("EXPLAIN QUERY PLAN " + QUERY, PARAMS):
      print(row)
  ```

- New index requires: (a) plan before/after, (b) write-amplification note (each index slows ingest), (c) drop-candidate if unused (check `dbstat`).

---

## 6. Caching architecture — without Redis

Single host, single process (P0). All caching is **in-process, TTL-bounded, LRU-evicted**. If the app ever splits web/worker (P2), this layer is replaced by a shared SQLite-backed cache table — the TTL/invalidation contract below does not change.

| What | TTL | Invalidation | Size cap |
|---|---|---|---|
| Gzipped static assets (`{path: (bytes, etag, mtime)}`) | ∞ (until file mtime changes — stat on request) | mtime check per request (cheap `os.stat`) | 5 MB total |
| `plan_limits` by plan | 60 s | TTL expiry only (admin plan change is rare; 60 s staleness acceptable) | < 100 entries |
| Series buckets + stats per `(check_id, range)` | 30 s | TTL **or** ingest of a new sample for that check (writer invalidates) | 1,000 entries / 32 MB |
| Public report payload per `slug` | 30 s | TTL **or** `is_public` toggle / new sample | 500 entries |
| Baseline (rolling median of daily p95) per check | 5 min | TTL or ingest | 1,000 entries |
| DNS / SSRF-guard resolve result per hostname | 60 s | TTL (short — IP can change; never cache > 60 s for SSRF) | 500 entries |
| Session existence (revoked?) | **0 — never cached** | — (see §3.4) | — |

Implementation (`app/cache.py`):

- One class: `TTLCache(max_entries, default_ttl)` backed by `dict` + `OrderedDict` for LRU; `threading.RLock` (stdlib). No `functools.lru_cache` for mutable/invalidatable entries (no TTL control).
- Every `get` records hit/miss; `/healthz` (or a debug endpoint, auth-gated) exposes hit rate. **Target: ≥ 80% hit rate** on `series`/`stats` under S1; below that, the cache is mis-tuned, not the DB.
- Cache stampede guard: on miss, one thread computes, others wait on a per-key `threading.Event` (no thundering-herd on TTL expiry after a deploy).
- Negative caching: 404 for `/r/{slug}` cached 10 s (prevents slug-enumeration load).

---

## 7. Resource budgets (single-host Docker target)

| Resource | Budget | Enforcement / alert |
|---|---|---|
| **RAM** | **≤ 512 MB** RSS (app process) | `docker compose` `mem_limit: 512m`; `/healthz` reports RSS; alert if > 450 MB for 5 min. Cache caps (§6) + queue cap (§3.6) keep this bounded. |
| **CPU** | **≤ 1 vCPU** sustained; burst to host max for < 30 s | `cpus: 1.0`; PBKDF2 semaphore (§3.5) + sampler semaphore (8) prevent CPU meltdown. |
| **Disk** | DB ≤ 2 GB at 1k checks × 1m interval × 90d (≈ 130M rows worst case — see note) | Nightly `ANALYZE`; WAL checkpoint (§3.1); retention job deletes samples older than plan `history_days` (runs in scheduler, batched 1k/tx). Note: the 2 GB cap assumes bucketed retention (raw samples → daily rollups after 30d, P1). |
| **DB connections** | 1 writer + ≤ 4 readers (pool via `sqlite3` connections, `check_same_thread=False` + lock) | Never open a connection per request; reuse via a small pool in `db.py`. |
| **HTTP connections** | `ThreadingHTTPServer` with `daemon_threads=True`, max **64** worker threads | Semaphores above this: ping-now 4, sampler 8, PBKDF2 2. Excess → 429 `Retry-After: 1`, never queue unboundedly. |
| **Open file descriptors** | ≤ 256 (DB + sockets + static) | Static served from memory cache after first read — no fd per request. |
| **Scheduler** | 1 thread, wakes every 1 s, checks due list (indexed query) | Heartbeat in `/healthz`; stall > 10 s → log + optional webhook (§product-spec). |

If a deployment needs more, the documented scaling path is: raise `cpus`/`mem_limit`, then split web/worker via `RUN_SCHEDULER=0` (§architecture). The budgets above do not change — they are per-process.

---

## 8. CI performance gates

All gates run in GitHub Actions on `python:3.11-slim`, stdlib-only (no `pip install` beyond `pytest` for tests). A gate failure **blocks merge** unless a maintainer adds a `perf-waiver` label + backlog entry (§9) explaining the regression.

| Gate | Command / check | Threshold | Blocks |
|---|---|---|---|
| **Static asset size** | `python tools/check_assets.py` — sums `app/static/*`, gzips, asserts budget | Gzipped initial ≤ **70 KB**, no single file > 40 KB, no file outside `app/static/` is web-served | Merge |
| **Dead CSS** | part of `check_assets.py` | ≤ 10% unused selectors | Merge |
| **API smoke latency** | `pytest tests/test_api.py` with per-test timing wrapper; ephemeral server, seeded DB | Each endpoint class within §1.2 p95 (asserted on the *test* p95 of ≥ 20 calls) | Merge |
| **Query plan** | `pytest tests/test_query_plans.py` — runs `EXPLAIN QUERY PLAN` on every query in `db.py`'s registry | No `SCAN` on hot tables (§5.3) | Merge |
| **N+1 grep** | `python tools/check_n_plus_one.py` — flags SQL-in-loop patterns | 0 flagged sites outside the allowlist | Merge |
| **Load test (S1+S2)** | `python tools/loadtest.py --scenario S1/S2` on release candidates (not every PR — 60 s cost) | §4.3 thresholds | Release |
| **Load test archive diff** | compare JSON vs last archived run | p95 regression > 20% | Release |
| **Coverage (perf-relevant)** | `pytest --cov=app.stats --cov=app.detector --cov=app.auth` | ≥ 70% (product-spec KPI) | Merge |
| **tracemalloc peak** | `tests/test_stats.py::test_series_memory` | < 20 MB for 10k rows | Merge |

CI also runs a **Lighthouse smoke** on `index.html` (via `lighthouse` if available, else a `curl` + size check — never required, per stdlib constraint) and records LCP/INP/CLS as artifacts. A lab LCP > 2.5 s files an automatic backlog P1.

---

## 9. Optimization backlog

### P0 — before public launch (blockers)

| # | Item | Expected gain | Owner |
|---|---|---|---|
| P0-1 | Bucketed series query (`strftime`/`floor` bucketing in SQL, not Python) for `series?range=30d` | 30d series 300 ms → < 50 ms | Backend |
| P0-2 | Dashboard `ROW_NUMBER()` latest-sample query (kill the per-check loop) | Dashboard N+1 → 2 queries total | Backend |
| P0-3 | In-process `TTLCache` for series/stats + stampede guard (§6) | Series p95 200 ms → < 50 ms at 80% hit rate | Backend |
| P0-4 | Pre-gzipped static cache + `ETag`/`immutable` headers (§2.2–2.3) | Static p95 25 ms, repeat-visit LCP −40% | Backend/Frontend |
| P0-5 | PBKDF2 semaphore + 429 (§3.5) | Prevents auth-burst starvation of ingest | Backend |
| P0-6 | `tools/loadtest.py` (S1–S6) + CI gates (§8) | Makes every other item measurable | Perf |
| P0-7 | Retention job (batched delete past `history_days`) + `ANALYZE` cron | Bounds disk + keeps query plans stable | Backend |

### P1 — first sprint after launch

| # | Item | Expected gain | Owner |
|---|---|---|---|
| P1-1 | Daily rollup table (raw samples → `daily_p95` after 30d) | 90d history query without scanning 130M rows | Backend |
| P1-2 | RUM beacon (`/api/v1/rum`) + weekly Web Vitals report | Field LCP/INP/CLS visibility | Frontend |
| P1-3 | Chart `OffscreenCanvas` / adaptive bucket count on resize | INP on large series < 100 ms | Frontend |
| P1-4 | `mmap_size` + read-only connection tuning based on S1 profile | Series p95 −30% on warm cache | Backend |
| P1-5 | Skeleton loading for dashboard tiles (CLS → ~0) | CLS 0.05 → < 0.01 | Frontend |
| P1-6 | Index audit via `dbstat` (drop unused indexes) | Ingest write amplification −10–20% | Backend |

### P2 — later / when scaling

| # | Item | Expected gain | Owner |
|---|---|---|---|
| P2-1 | Shared cache (SQLite-backed table) for split web/worker | Coherent cache across processes | Backend |
| P2-2 | Postgres adapter (`db.py` swap) if write contention breaches §1.3 | Removes single-writer ceiling | Backend |
| P2-3 | `asyncio` sampler (replace thread-per-fetch) | 8 → 100s concurrent checks on 1 vCPU | Backend |
| P2-4 | OpenTelemetry export (hook point in §architecture) | APM without breaking stdlib-only boot | Backend |
| P2-5 | HTTP/2 or keep-alive tuning on `ThreadingHTTPServer` | Fewer TCP handshakes for CI gate bursts | Backend |
| P2-6 | Edge/static CDN (optional, never required) | Static p95 → < 10 ms globally | Ops |

---

## Appendix — how to use this spec

1. **New endpoint?** Look up its class in §1.2, add a query-plan test (§5.3) + smoke timing (§8), ship.
2. **New query?** Paste `EXPLAIN QUERY PLAN` in the PR; no `SCAN` on hot tables.
3. **New static asset?** Run `tools/check_assets.py`; stay under 70 KB gzipped total.
4. **Something feels slow?** Profile first (§5), then check the backlog (§9) — don't invent a new cache or index without a profile.
5. **Budget breach?** File a P0/P1 backlog item with the load-test JSON attached. Do not raise the budget silently.
