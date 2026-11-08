# LatencyLedger — Architecture

## Stack Choice (justified)

**Python 3.11+ stdlib-only backend** (`http.server` + `sqlite3` + `urllib.request` + `hashlib`/`secrets`/`smtplib`) serving **static HTML/CSS/JS** (vanilla JS, canvas charts). No pip dependencies required to boot.

| Option | Verdict |
|---|---|
| **Python stdlib (chosen)** | Zero `pip install` to run; `sqlite3` built-in; scheduler = thread; portable to any host; smallest attack surface. Trade-off: hand-rolled routing — acceptable at this scale, isolated in `router.py`. |
| FastAPI/Flask | Nicer routing/OpenAPI, but adds pip deps + version churn for marginal gain in sprint 1; can be adopted later by swapping the WSGI layer (routes are plain functions). |
| Node (existing repo is TS) | Repo's `httpping` CLI is Node/TS, but Node hosting + SQLite needs `better-sqlite3` native build; Python stdlib avoids native deps entirely. CLI parity kept via a small Python port of the same timing logic. |

Frontend: no build step (`npm run build` not required). Charts: hand-rolled canvas (no CDN dependency — works offline/self-hosted). Optional CDN enhancement is progressive, never required.

## Repo Layout

```
.
├── README.md, LICENSE, CONTRIBUTING.md, SECURITY.md
├── requirements.txt          # empty (stdlib-only); documents Python >=3.11
├── pyproject.toml            # metadata + pytest config
├── Dockerfile, docker-compose.yml
├── app/
│   ├── __init__.py
│   ├── main.py               # entry: HTTP server + scheduler thread (flag-gated)
│   ├── config.py             # env vars (DATABASE_URL, PORT, SMTP_*, RUN_SCHEDULER)
│   ├── db.py                 # sqlite3 connection, WAL, migrations (schema.sql)
│   ├── schema.sql
│   ├── router.py             # tiny method+path router -> handlers
│   ├── auth.py               # hashing, sessions, API keys
│   ├── checks.py             # check CRUD + validation (SSRF guard)
│   ├── sampler.py            # urllib fetch+timing (port of httpping logic)
│   ├── scheduler.py          # due-check loop, ingest queue
│   ├── stats.py              # percentiles, baseline, bucketing (pure, tested)
│   ├── detector.py           # regression rule (+20% p95 vs baseline, cooldown)
│   ├── alerts.py             # email (smtplib) + webhook delivery, retry/backoff
│   ├── gate.py               # CI budget gate logic
│   ├── handlers/             # api.py, pages.py (serve static), public.py
│   └── static/               # index.html, app.js, style.css, check.html, r.html
├── tests/                    # pytest: test_stats.py, test_detector.py, test_api.py, test_auth.py
├── docs/                     # product-spec.md, architecture.md, roadmap.md, design-system.md
└── examples/github-actions.yml
```

## Database Schema (SQLite)

```sql
users(id INTEGER PK, email TEXT UNIQUE, pw_hash TEXT, plan TEXT DEFAULT 'free',
      created_at TEXT DEFAULT datetime('now'));
sessions(id TEXT PK, user_id INT FK, expires_at TEXT, created_at TEXT);
api_keys(id TEXT PK, user_id INT FK, prefix TEXT, hash TEXT, created_at TEXT, revoked_at TEXT);
checks(id TEXT PK, user_id INT FK, name TEXT, url TEXT, interval_sec INT,
       threshold_pct REAL DEFAULT 20, is_public INT DEFAULT 0, slug TEXT UNIQUE,
       last_checked_at TEXT, created_at TEXT);
samples(id INTEGER PK, check_id TEXT FK, ts TEXT, ms REAL, status INT,
        size_bytes INT, git_sha TEXT, note TEXT);   -- index (check_id, ts)
alerts(id INTEGER PK, check_id TEXT FK, kind TEXT, observed_p95 REAL,
       baseline_p95 REAL, created_at TEXT, acked_at TEXT);
alert_channels(id TEXT PK, check_id TEXT FK, kind TEXT, target TEXT, created_at TEXT);
deliveries(id INTEGER PK, alert_id INT FK, channel_id TEXT FK, status INT, attempts INT, ts TEXT);
plan_limits(plan TEXT PK, max_checks INT, min_interval_sec INT, history_days INT);
```

Migrations: ordered `schema.sql` + `PRAGMA user_version`; applied idempotently on boot.

## API Design

REST, JSON, `/api/*` (session cookie) + `/api/v1/*` (API key). Errors: `{"error": "code", "detail": "..."}` with 400/401/403/404/409/422/429.

- `POST /api/auth/register|login|logout`, `GET /api/auth/me`
- `GET/POST /api/checks`, `GET/PATCH/DELETE /api/checks/{id}`
- `POST /api/checks/{id}/ping-now`, `GET /api/checks/{id}/series?range=24h|7d|30d`
- `GET /api/checks/{id}/stats`, `GET /api/checks/{id}/alerts`
- `POST /api/v1/checks/{id}/samples` {ms,status,sha} — CI ingestion
- `POST /api/v1/checks/{id}/gate` {p95_ms} → 200/422 pass/fail
- `POST/GET /api/keys`, `DELETE /api/keys/{id}`
- `GET /r/{slug}` public report (no auth), `GET /healthz`

## Auth Approach

- Passwords: `hashlib.pbkdf2_hmac('sha256', pw, salt, 200_000)`; `secrets.compare_digest`.
- Sessions: opaque `secrets.token_urlsafe(32)` in HttpOnly, SameSite=Lax cookie; server-side table for instant revocation.
- API keys: `ll_` + 32 random chars; store SHA-256 hash + prefix only; constant-time compare.
- OAuth (GitHub/Google) is a **stub behind env flag** (`OAUTH_ENABLED=0` default) — app boots with no provider keys.

## Security

- **SSRF guard:** resolve hostname, reject private/loopback/link-local IPs; re-check on redirect (redirects disabled); 10s timeout; max 1MB body read.
- Rate limiting: per-IP login attempts (5/min) and per-key ingest (100/min) via in-memory token bucket.
- All SQL parameterized; output escaped in templates (no `innerHTML` with user data); security headers (CSP, X-Content-Type-Options, frame-ancestors).
- Secrets only via env; `SECURITY.md` for disclosure.

## Testing Strategy

- Unit: `stats.py` percentiles/baseline, `detector.py` regression rule — property + fixed cases, no network.
- API: `pytest` + `http.client` against ephemeral server on random port + temp SQLite DB; auth, gate 200/422, public-report isolation.
- Sampler: against a local stub HTTP server (latency injected, failure modes).
- CI: `pytest -q` in GitHub Actions; coverage gate 70% on `stats/detector/auth`.

## Deployment (Docker)

- `Dockerfile`: `python:3.11-slim`, copy `app/`, `EXPOSE 8000`, `CMD ["python","-m","app.main"]`; volume `/data` for SQLite.
- `docker-compose.yml`: app + named volume; `RUN_SCHEDULER=1`.
- Run: `docker compose up` → http://localhost:8000. No external keys needed.
- Scaling path: scheduler is stateless; split web/worker via `RUN_SCHEDULER=0` + second container; SQLite → Postgres by replacing `db.py` adapter (schema is portable).

## Observability

- `GET /healthz` (DB ping + scheduler heartbeat), structured JSON logs to stdout (`logging`, request id per call).
- Self-monitoring: ingest p95 + detector counters logged; optional webhook on scheduler stall.
- No third-party APM required (constraint); OpenTelemetry hook point noted for P2.
