# LatencyLedger — Developer Docs Spec

> **SaaS:** LatencyLedger — Continuous API latency regression tracking with CI gates. Know when your API got slower before your users do.
> **Audience:** Contributors and integrators. This is a *spec* for the developer docs: run it, extend it, and keep it in sync with `docs/product-spec.md` and `docs/architecture.md`.
> **Stack (per `docs/architecture.md`):** Python 3.10+ stdlib-only backend (`http.server` + `sqlite3` + `urllib.request`), static HTML/CSS/JS frontend (no build step), SQLite (WAL). No `pip install` required to boot. Existing `httpping` TypeScript CLI in the repo root is retained for latency-measurement parity; the SaaS backend lives in `app/`.
> **Status:** All commands below are copy-paste ready against the repo layout in `docs/architecture.md`. Where a file does not exist yet, the command is the contract it must satisfy (see §10).

---

## 1. Developer Quickstart

### 1.1 Prerequisites

- Python **3.10 or newer** (architecture targets 3.11+; 3.10 is the supported floor for this spec):
  ```bash
  python3 --version   # expect Python 3.10+ / 3.11+
  ```
- Optional: Docker + Docker Compose (for §7). No other tools needed — `curl`, git, and (for tests) `pytest`.

### 1.2 One-command run

From the repo root (Python backend):

```bash
git clone https://github.com/devhasen/http-ping.git && cd http-ping
python3 -m app.main
# -> LatencyLedger listening on http://127.0.0.1:8000  (DB auto-created on first boot)
```

Open <http://localhost:8000> — you should see the dashboard. First boot creates the SQLite database (`data/latencyledger.db` by default, mode WAL) and applies `app/schema.sql` migrations idempotently. **No API keys, no `pip install`, no env vars required.**

Existing CLI core (works today, no build step):

```bash
node dist/index.js https://example.com 5
# 1 42ms / 2 38ms / ... / min .. max .. avg ..
npm run build   # only if you edit src/index.ts (tsc)
```

Run via Docker instead (see §7):

```bash
docker compose up
# -> http://localhost:8000
```

### 1.3 Setup (from scratch)

```bash
# 1. Clone
git clone https://github.com/devhasen/http-ping.git
cd http-ping

# 2. (Optional) virtualenv — not required, stdlib only
python3 -m venv .venv && . .venv/bin/activate

# 3. Start
python3 -m app.main

# 4. In a second terminal, verify health
curl -i http://localhost:8000/healthz
# HTTP/1.1 200 OK  {"status":"ok","db":"ok","scheduler":"running"}
```

No `requirements.txt` installs: `requirements.txt` is intentionally empty. If you add a dependency, justify it in the PR (stdlib-first rule, see §9).

### 1.4 First API call (copy-paste)

Register, create a check, and ping it — all without leaving the terminal:

```bash
export BASE=http://localhost:8000

# 1. Register (creates user, sets HttpOnly session cookie in the jar)
curl -s -c /tmp/ll.jar -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"correct-horse-123"}' \
  $BASE/api/auth/register

# 2. Create a URL check (stored in SQLite, shows on dashboard within 1s)
curl -s -b /tmp/ll.jar -H 'Content-Type: application/json' \
  -d '{"name":"example","url":"https://example.com","interval_sec":300}' \
  $BASE/api/checks

# 3. Manual ping now (10 requests -> {ms,status} + min/max/avg/p50/p95/p99)
curl -s -b /tmp/ll.jar -X POST $BASE/api/checks/<CHECK_ID>/ping-now

# 4. Stats + history
curl -s -b /tmp/ll.jar "$BASE/api/checks/<CHECK_ID>/stats"
curl -s -b /tmp/ll.jar "$BASE/api/checks/<CHECK_ID>/series?range=24h"
```

Replace `<CHECK_ID>` with the `id` returned by step 2. Error shape on any call: `{"error":"<code>","detail":"..."}` (see §10).

---

## 2. Architecture Deep-Dive Outline (for contributors)

Read in order; each module is a plain function set — no framework magic (see `docs/architecture.md`).

1. **Boot & config** — `app/main.py` (HTTP server + scheduler thread, flag-gated) → `app/config.py` (reads §5 env vars, no secrets in code).
2. **Routing** — `app/router.py`: tiny method+path router → handlers. Add routes here; handlers are plain functions `(ctx) -> (status, json)`.
3. **Database** — `app/db.py` + `app/schema.sql`: `sqlite3` connection, WAL mode, `PRAGMA user_version` migrations, parameterized queries only. Tables: `users, sessions, api_keys, checks, samples, alerts, alert_channels, deliveries, plan_limits`.
4. **Auth** — `app/auth.py`: `hashlib.pbkdf2_hmac('sha256', pw, salt, 200_000)`, opaque session tokens (`secrets.token_urlsafe(32)`, HttpOnly `SameSite=Lax` cookie), API keys `ll_…` stored as SHA-256 hash + prefix, `secrets.compare_digest`.
5. **Checks & SSRF guard** — `app/checks.py`: validation (non-`http(s)` and `>2048` chars rejected), private/loopback/link-local IP rejection at DNS+connect, redirects disabled, 10s timeout, 1MB body cap.
6. **Sampler** — `app/sampler.py`: `urllib.request` fetch+timing (Python port of the `httpping` TS logic in `src/index.ts`); per-request `{ms,status,size}`, errors counted, never crash ingest.
7. **Scheduler** — `app/scheduler.py`: in-process thread, due-check loop, single-writer ingest queue; kill switch `RUN_SCHEDULER=0` for web-only workers.
8. **Stats** — `app/stats.py` (pure, heavily tested): min/max/avg/p50/p95/p99, rolling baseline (median of daily p95), bucketed series (avg + p95 per bucket).
9. **Detector** — `app/detector.py`: regression rule = p95 rises >20% over rolling 7d baseline (min 50 samples), 6h cooldown per check, fires once per cooldown window.
10. **Alerts** — `app/alerts.py`: `smtplib` email (disabled without SMTP env) + webhook delivery, exponential backoff (3 attempts), every delivery logged in `deliveries`.
11. **CI gate** — `app/gate.py`: `POST /api/v1/checks/{id}/gate {p95_ms}` → `200 {pass:true}` or `422 {pass:false, observed_p95}`; API-key auth only.
12. **Handlers** — `app/handlers/api.py` (`/api/*` session), `app/handlers/pages.py` (static), `app/handlers/public.py` (`/r/{slug}` read-only, no keys leaked).
13. **Frontend** — `app/static/` (vanilla JS + canvas, no CDN/build step): dashboard, check detail, public report. Follow `docs/design-system.md` tokens (`--bg #0f1115`, `--accent #4f8cff`, `--p95 #b083f0`, `--bad #e5534b`).
14. **Scaling path** — split web/worker via `RUN_SCHEDULER=0` + second container; SQLite → Postgres by replacing the `db.py` adapter (portable schema).

---

## 3. API Cookbook

Conventions for every example: `$BASE=http://localhost:8000`, JSON bodies, errors are `{"error":code,"detail":...}`. Each example shows **curl** and **Python `urllib`** (stdlib only — no `requests`). Python snippets assume a live server; swap IDs from real responses.

### Example 1 — Register & login (session cookie)

```bash
curl -s -c /tmp/ll.jar -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"correct-horse-123"}' \
  $BASE/api/auth/register
curl -s -b /tmp/ll.jar $BASE/api/auth/me
```

```python
import json, urllib.request, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def call(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        "http://localhost:8000" + path, data=data, method=method,
        headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read())

print(call("POST", "/api/auth/register",
           {"email": "dev@example.com", "password": "correct-horse-123"}))
print(call("GET", "/api/auth/me"))
```

### Example 2 — Create a check (CRUD: create)

```bash
curl -s -b /tmp/ll.jar -H 'Content-Type: application/json' \
  -d '{"name":"api-users","url":"https://api.example.com/users","interval_sec":300}' \
  $BASE/api/checks
```

```python
check = call("POST", "/api/checks",
             {"name": "api-users",
              "url": "https://api.example.com/users", "interval_sec": 300})
print(check["id"])  # save for examples 3-5, 8
```

### Example 3 — List, read, update, delete a check (CRUD)

```bash
curl -s -b /tmp/ll.jar $BASE/api/checks
curl -s -b /tmp/ll.jar $BASE/api/checks/<CHECK_ID>
curl -s -b /tmp/ll.jar -X PATCH -H 'Content-Type: application/json' \
  -d '{"interval_sec":60}' $BASE/api/checks/<CHECK_ID>
curl -s -b /tmp/ll.jar -X DELETE $BASE/api/checks/<CHECK_ID>
```

```python
print(call("GET", "/api/checks"))
print(call("GET", f"/api/checks/{check['id']}"))
print(call("PATCH", f"/api/checks/{check['id']}", {"interval_sec": 60}))
# DELETE has no JSON body of interest:
req = urllib.request.Request(f"http://localhost:8000/api/checks/{check['id']}",
                             method="DELETE")
opener.addheaders = [("Cookie", "; ".join(f"{c.name}={c.value}" for c in jar))]
print(opener.open(req).status)
```

### Example 4 — Manual ping + stats (the core value)

```bash
curl -s -b /tmp/ll.jar -X POST $BASE/api/checks/<CHECK_ID>/ping-now
curl -s -b /tmp/ll.jar $BASE/api/checks/<CHECK_ID>/stats
```

```python
ping = call("POST", f"/api/checks/{check['id']}/ping-now")
print("p95:", ping["p95"], "ms  | samples:", len(ping["samples"]))
print(call("GET", f"/api/checks/{check['id']}/stats"))
```

### Example 5 — History with pagination + range

```bash
# Cursor pagination: limit + cursor query params (see §10 contract)
curl -s -b /tmp/ll.jar "$BASE/api/checks/<CHECK_ID>/series?range=7d&limit=100&cursor=<CURSOR>"
curl -s -b /tmp/ll.jar "$BASE/api/checks/<CHECK_ID>/alerts?limit=20&cursor=<CURSOR>"
```

```python
page = call("GET", f"/api/checks/{check['id']}/series?range=7d&limit=100")
for point in page["data"]:
    print(point["ts"], point["p95"])
while page.get("next_cursor"):
    page = call("GET", f"/api/checks/{check['id']}/series"
                          f"?range=7d&limit=100&cursor={page['next_cursor']}")
```

### Example 6 — API key for CI (auth: create, use, revoke)

```bash
# Create (plaintext key shown ONCE — save it)
curl -s -b /tmp/ll.jar -X POST $BASE/api/keys
# Use it (no cookie needed)
curl -s -H "Authorization: Bearer ll_<YOUR_KEY>" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"p95_ms":400}' $BASE/api/v1/checks/<CHECK_ID>/gate
# Revoke (takes effect immediately)
curl -s -b /tmp/ll.jar -X DELETE $BASE/api/keys/<KEY_ID>
```

```python
key = call("POST", "/api/keys")          # {"key": "ll_...", "prefix": "ll_ab12..."}
api_key = key["key"]                      # store CI secret, never commit

req = urllib.request.Request(
    f"http://localhost:8000/api/v1/checks/{check['id']}/gate",
    data=json.dumps({"p95_ms": 400}).encode(), method="POST",
    headers={"Authorization": f"Bearer {api_key}",
             "Content-Type": "application/json"})
try:
    print(json.loads(urllib.request.urlopen(req).read()))
except urllib.error.HTTPError as e:
    print(e.code, json.loads(e.read()))   # 422 when over budget
```

### Example 7 — CI gate pass/fail + sample ingestion

```bash
# Ingest a CI sample tagged with the commit SHA
curl -s -H "Authorization: Bearer ll_<YOUR_KEY>" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"ms":212,"status":200,"sha":"abc1234","note":"post-deploy"}' \
  $BASE/api/v1/checks/<CHECK_ID>/samples

# Gate: 200 {pass:true} under budget, 422 {pass:false,observed_p95} over
curl -s -H "Authorization: Bearer ll_<YOUR_KEY>" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"p95_ms":400}' $BASE/api/v1/checks/<CHECK_ID>/gate; echo
# -> {"pass":true,...}   or   HTTP 422 {"pass":false,"observed_p95":389}
```

```python
ingest = urllib.request.Request(
    f"http://localhost:8000/api/v1/checks/{check['id']}/samples",
    data=json.dumps({"ms": 212, "status": 200, "sha": "abc1234",
                     "note": "post-deploy"}).encode(), method="POST",
    headers={"Authorization": f"Bearer {api_key}",
             "Content-Type": "application/json"})
print(urllib.request.urlopen(ingest).status)
```

See `examples/github-actions.yml` for the full Actions step (gate fails the build on 422).

### Example 8 — Regression alerts (list + verify cooldown)

```bash
curl -s -b /tmp/ll.jar "$BASE/api/checks/<CHECK_ID>/alerts?limit=20"
# -> {"data":[{"kind":"regression","observed_p95":389,"baseline_p95":212,...}], ...}
```

```python
alerts = call("GET", f"/api/checks/{check['id']}/alerts?limit=20")
for a in alerts["data"]:
    print(a["created_at"], a["observed_p95"], "vs baseline", a["baseline_p95"])
```

### Example 9 — Webhook alert channel (create, test-send, delivery log)

```bash
curl -s -b /tmp/ll.jar -H 'Content-Type: application/json' \
  -d '{"kind":"webhook","target":"https://hooks.example.com/ll"}' \
  $BASE/api/checks/<CHECK_ID>/alert-channels
curl -s -b /tmp/ll.jar -X POST $BASE/api/checks/<CHECK_ID>/alert-channels/<CHANNEL_ID>/test
```

```python
channel = call("POST", f"/api/checks/{check['id']}/alert-channels",
               {"kind": "webhook", "target": "https://hooks.example.com/ll"})
print(call("POST", f"/api/checks/{check['id']}/alert-channels/{channel['id']}/test"))
```

### Example 10 — Public report link (unauthenticated, read-only)

```bash
# Toggle public (owner only, session cookie)
curl -s -b /tmp/ll.jar -X PATCH -H 'Content-Type: application/json' \
  -d '{"is_public":true}' $BASE/api/checks/<CHECK_ID>
# Anyone can view — no auth header, no keys/settings leaked
curl -s $BASE/r/<SLUG>
```

```python
import urllib.request
# Slug comes from the check object returned by Example 3
html = urllib.request.urlopen(f"http://localhost:8000/r/{check['slug']}").read()
print(len(html), "bytes of read-only report")
```

---

## 4. Seeding & Demo Mode

### 4.1 Demo mode (fastest path to a chart)

```bash
# Seed a demo user + 3 checks + 7 days of synthetic samples, then open the UI
python3 -m app.seed --demo
# -> seeded: dev@latencyledger.demo (login: demo / demo) + 3 checks, ~2,500 samples
curl -s -c /tmp/ll.jar -H 'Content-Type: application/json' \
  -d '{"email":"dev@latencyledger.demo","password":"demo"}' \
  $BASE/api/auth/login
```

Demo mode ships with `DEMO_MODE=1` (see §5): it runs the seeder on boot if the DB is empty, disables email sending, and uses a synthetic slow endpoint (`http://127.0.0.1:9`-style local stub — never a real external host). Demo data is *entirely* synthetic and regenerable: `python3 -m app.seed --reset --demo`.

### 4.2 Seeding (dev / CI / perf)

```bash
python3 -m app.seed --demo              # demo user + 3 checks + 7d samples
python3 -m app.seed --users 20 --checks 5 --days 30   # scale test
python3 -m app.seed --reset             # wipe + reseed (dev only, refuses in prod)
python3 -m app.seed --check <CHECK_ID> --inject-regression \
    --from-p95 200 --to-p95 400         # force a >20% drift to test detector/alerts
```

Seeding contract: deterministic with `--seed <int>` (default `42`) so CI fixtures are reproducible; never contacts the network (synthetic samples are generated in-process); `--reset` requires `ALLOW_PRIVATE_IPS=1` or `ENV=dev` and is a no-op in production.

### 4.3 Demo-mode behaviour checklist

- UI shows a "Demo data" banner; all demo accounts are clearly labeled.
- Regression alert fires within one scheduler tick after `--inject-regression` (verifies detector + cooldown).
- Public report link for the demo check works logged-out (Example 10).
- Nothing in demo mode sends real email/webhooks (`SMTP_ENABLED` forced off, webhook targets are stubbed).

---

## 5. Configuration Reference

Every env var. Defaults are safe for local dev — the app boots with **zero** env vars set. Secrets must come from the environment only (never committed).

| # | Name | Default | Description |
|---|------|---------|-------------|
| 1 | `HOST` | `127.0.0.1` | Bind address for `http.server`. Set `0.0.0.0` in Docker/bare-metal prod. |
| 2 | `PORT` | `8000` | HTTP listen port. |
| 3 | `DATABASE_URL` | `sqlite:///data/latencyledger.db` | SQLite DSN. Relative paths resolve from repo root; absolute path recommended in prod. |
| 4 | `RUN_SCHEDULER` | `1` | `1` = run in-process scheduler thread; `0` = web-only (split worker setup). |
| 5 | `SCHEDULER_INTERVAL_SEC` | `30` | How often the scheduler scans for due checks. |
| 6 | `CHECK_TIMEOUT_SEC` | `10` | Per-request fetch timeout in the sampler. |
| 7 | `ALLOW_PRIVATE_IPS` | `0` | `1` disables the SSRF guard (dev/testing only, never prod). |
| 8 | `SESSION_TTL_DAYS` | `30` | Session cookie lifetime; sessions table enforces expiry server-side. |
| 9 | `REGRESSION_THRESHOLD_PCT` | `20` | p95 rise (%) vs rolling baseline that triggers an alert. |
| 10 | `REGRESSION_MIN_SAMPLES` | `50` | Minimum samples before the detector can fire (false-positive guard). |
| 11 | `ALERT_COOLDOWN_HOURS` | `6` | Per-check alert cooldown after a regression fires. |
| 12 | `RATE_LIMIT_LOGIN_PER_MIN` | `5` | Per-IP login attempt budget (in-memory token bucket). |
| 13 | `RATE_LIMIT_INGEST_PER_MIN` | `100` | Per-API-key sample/gate request budget. |
| 14 | `PLAN_DEFAULT` | `free` | Plan assigned to new signups (`free`/`pro`/`team`); manual toggle until Stripe lands. |
| 15 | `PUBLIC_BASE_URL` | `http://localhost:8000` | Public origin used in report links and alert emails. |
| 16 | `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`; structured JSON logs to stdout. |
| 17 | `SMTP_ENABLED` | auto | `1` forces email on, `0` forces off; unset = on only when `SMTP_HOST` is set. |
| 18 | `SMTP_HOST` | *(empty)* | SMTP server for regression alert email. Empty disables email. |
| 19 | `SMTP_PORT` | `587` | SMTP submission port. |
| 20 | `SMTP_TLS` | `1` | STARTTLS upgrade. |
| 21 | `SMTP_USER` | *(empty)* | SMTP auth user. |
| 22 | `SMTP_PASS` | *(empty)* | SMTP auth password (env only). |
| 23 | `SMTP_FROM` | `noreply@localhost` | From address for alert email. |
| 24 | `OAUTH_ENABLED` | `0` | `1` enables GitHub/Google login stubs; app must boot with `0` and no keys. |
| 25 | `OAUTH_GITHUB_CLIENT_ID` | *(empty)* | GitHub OAuth client id (only used when `OAUTH_ENABLED=1`). |
| 26 | `OAUTH_GITHUB_CLIENT_SECRET` | *(empty)* | GitHub OAuth client secret (only used when `OAUTH_ENABLED=1`). |
| 27 | `OAUTH_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client id (only used when `OAUTH_ENABLED=1`). |
| 28 | `OAUTH_GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth client secret (only used when `OAUTH_ENABLED=1`). |
| 29 | `DEMO_MODE` | `0` | `1` = seed demo data on empty DB, stub email/webhooks, show demo banner. |
| 30 | `ENV` | `dev` | `dev`/`test`/`prod`. `prod` refuses demo/reset and requires `ALLOW_PRIVATE_IPS=0`. |

**Env var count: 30.**

Example `.env` for local dev (optional — copy to a file *outside* git):

```bash
HOST=127.0.0.1
PORT=8000
DATABASE_URL=sqlite:///data/dev.db
RUN_SCHEDULER=1
ALLOW_PRIVATE_IPS=1
LOG_LEVEL=DEBUG
```

Load explicitly (the app does not auto-load `.env`):

```bash
set -a; . ./.env; set +a; python3 -m app.main
```

---

## 6. Testing Guide

### 6.1 Run the tests

```bash
python3 -m pytest -q                      # full suite (unit + API)
python3 -m pytest tests/test_stats.py -q  # stats only (fast, no server)
python3 -m pytest tests/test_detector.py tests/test_auth.py -q
python3 -m pytest --cov=app --cov-report=term-missing -q   # coverage
```

Coverage bar: **≥70% on `stats.py`, `detector.py`, `auth.py`** (enforced in CI). If `pytest` is missing: `python3 -m pip install pytest pytest-cov` (test-only dependency; runtime stays stdlib-only).

### 6.2 How the tests work (no network, no flakiness)

- **Unit** (`test_stats.py`, `test_detector.py`): pure functions, fixed + property cases, injected sample arrays — e.g. p95 of `[100..500]` is `450`, a 212→389 drift must fire, 212→240 must not.
- **API** (`test_api.py`, `test_auth.py`): ephemeral server on a random port + temp SQLite DB (`tmp_path`), driven with `http.client`. Covers register/login/logout, check CRUD, gate `200`/`422`, public-report isolation (logged-out `/r/{slug}` leaks no keys).
- **Sampler**: local stub HTTP server with injected latency/failures — asserts timing math and error counting, never a real external host.

### 6.3 Add a test (copy-paste template)

New percentile/statistic? Add to `tests/test_stats.py`:

```python
def test_p99_of_fixed_series():
    from app.stats import percentile
    assert percentile([100, 200, 300, 400, 500], 99) == 496  # nearest-rank
```

New API route? Add to `tests/test_api.py` using the existing fixtures:

```python
def test_gate_rejects_over_budget(client, auth_headers, check):
    res = client.post(f"/api/v1/checks/{check['id']}/gate",
                      {"p95_ms": 1}, headers=auth_headers)
    assert res.status == 422
    assert res.json()["pass"] is False
```

New detector rule? Add a fixed case + an injected-samples case to `tests/test_detector.py`, asserting both fire and no-fire branches and the 6h cooldown.

### 6.4 CI

GitHub Actions runs `python3 -m pytest -q` on every PR (see `.github/workflows/`). A red coverage gate on `stats/detector/auth` blocks merge.

---

## 7. Deployment Guide

### 7.1 Docker (recommended)

```bash
docker compose up -d            # app + named volume for SQLite
docker compose logs -f app      # structured JSON logs
curl -s http://localhost:8000/healthz
```

`Dockerfile`: `python:3.11-slim`, copies `app/`, `EXPOSE 8000`, `CMD ["python","-m","app.main"]`; SQLite lives on the `/data` volume so restarts keep data. `docker-compose.yml` sets `RUN_SCHEDULER=1` and mounts the volume. No external keys needed to boot.

Scale-out (web/worker split):

```bash
# Web-only instance
RUN_SCHEDULER=0 docker compose up -d --scale app=2
# Dedicated worker (same image, scheduler on)
RUN_SCHEDULER=1 docker compose -f docker-compose.worker.yml up -d
```

### 7.2 Bare metal

```bash
# 1. Python 3.11+ on the host
python3 --version
# 2. Fetch + run under your process manager (systemd example)
sudo useradd --system --home /opt/latencyledger latencyledger
sudo git clone https://github.com/devhasen/http-ping.git /opt/latencyledger
cd /opt/latencyledger
sudo -u latencyledger env HOST=0.0.0.0 PORT=8000 \
  DATABASE_URL=sqlite:///data/latencyledger.db \
  RUN_SCHEDULER=1 python3 -m app.main
# 3. Put a reverse proxy (nginx/caddy) in front for TLS; app serves plain HTTP.
# 4. Back up /data/latencyledger.db (SQLite file copy is a valid backup).
```

Postgres migration path: replace the `db.py` adapter — schema is portable, no app-level rewrites needed (P2).

### 7.3 Health & rollout

- `GET /healthz` → DB ping + scheduler heartbeat (wire this to your load balancer / uptime monitor).
- Rollout: `docker compose pull && docker compose up -d`; migrations apply idempotently on boot (`PRAGMA user_version`).
- Rollback: pin the previous image tag; SQLite schema is backward-compatible within a sprint.

---

## 8. Troubleshooting: 10 Common Dev Problems

| # | Symptom | Cause | Fix |
|---|---------|-------|-----|
| 1 | `ModuleNotFoundError: No module named 'app'` | Ran from wrong directory / old checkout | `cd` to repo root, then `python3 -m app.main`. Confirm `ls app/main.py`. |
| 2 | `Address already in use` on `:8000` | Another process or a stale server | Change `PORT=8001 python3 -m app.main`, or `lsof -i :8000` and stop the old process. |
| 3 | `curl: (7) Failed to connect` after start | Server bound to `127.0.0.1` but you curled a different host/port | Curl `http://127.0.0.1:$PORT/healthz` with the `PORT` you set; check `LOG_LEVEL=DEBUG` output. |
| 4 | `401 {"error":"unauthorized"}` on `/api/*` | Missing/expired session cookie | Re-register/login with `-c /tmp/ll.jar`, then always pass `-b /tmp/ll.jar` (Example 1). |
| 5 | `403`/`422` on check create: `private_ip_blocked` | URL resolves to private/loopback (SSRF guard) | Use a public URL, or in dev only set `ALLOW_PRIVATE_IPS=1`. Never enable in prod. |
| 6 | `409 {"error":"email_exists"}` on register | That email already registered | Log in instead, or use a fresh email / reset the dev DB (`python3 -m app.seed --reset`). |
| 7 | Gate returns `422 {pass:false}` unexpectedly | Observed p95 is over budget (real regression!) | View `GET /api/checks/{id}/series?range=24h` + `stats`; if real, it's the product working — fix the endpoint or raise `p95_ms`. |
| 8 | No regression alert after injecting drift | Below min samples, inside cooldown, or email disabled | Seed ≥`REGRESSION_MIN_SAMPLES` (50), wait out `ALERT_COOLDOWN_HOURS` (6), check `GET .../alerts`; email needs `SMTP_HOST` set. |
| 9 | `429 rate_limited` | Login (5/min/IP) or ingest (100/min/key) budget hit | Slow down; in tests set `RATE_LIMIT_LOGIN_PER_MIN=100 RATE_LIMIT_INGEST_PER_MIN=1000`. |
| 10 | Dashboard is empty / public link `404` | Fresh DB (no checks yet) or public toggle off / wrong slug | Create a check (Example 2); for `/r/{slug}` confirm `is_public:true` and copy the `slug` from the check object. |

General debugging: `LOG_LEVEL=DEBUG python3 -m app.main`; `GET /healthz` separates "app down" from "app up, data missing". Nuking local state: `rm data/latencyledger.db && python3 -m app.main` (DB recreates on boot).

---

## 9. Contribution Workflow

1. **Fork** `devhasen/http-ping` on GitHub; clone your fork locally.
2. **Branch** from `main` with a short, typed name:
   ```bash
   git checkout main && git pull origin main
   git checkout -b feat/percentile-p99        # or fix/, docs/, chore/
   ```
3. **Build** stdlib-first (no new runtime deps without justification). Keep routes in `app/router.py`, logic in its module, and new env vars documented in §5 of this file.
4. **Test**: `python3 -m pytest -q` — add/extend tests (§6.3); keep ≥70% coverage on `stats`/`detector`/`auth`.
5. **Lint/format**: Python stdlib tooling only in sprint 1; match surrounding style (type hints on new public functions, docstrings on modules).
6. **Commit** — one logical change per commit, imperative mood, typed prefix:
   ```
   feat: add p99 to check stats endpoint

   The gate needs p99 for SLO-style budgets; stats already computes
   p50/p95 so this is a one-line addition + test.
   ```
7. **Push & open a PR** against `main`:
   ```bash
   git push -u origin feat/percentile-p99
   ```
   PR checklist: description of *why*, test output (`pytest -q`), docs updated (`docs/api.yaml` per §10 if the API changed), no secrets.
8. **Review & merge** — CI must be green; a maintainer reviews; merge with a squash or rebase per repo settings. Delete the branch after merge. Never commit directly to `main` except docs-spec updates owned by the docs role.

Commit style quick reference: `feat:` new capability · `fix:` bug · `docs:` documentation only · `test:` tests · `refactor:` no behaviour change · `chore:` tooling/deps. Keep the subject ≤72 chars.

---

## 10. Format Contract for `docs/api.yaml`

`docs/api.yaml` is the OpenAPI 3.1 source of truth for the REST API. It must satisfy this contract — the backend, the cookbook (§3), and client generators all derive from it.

### 10.1 Global requirements

- `openapi: 3.1.0`, `info.title: LatencyLedger API`, `servers: [{url: /}]` (relative — works behind any reverse proxy).
- Every operation has a unique `operationId`, a `summary`, `security` (see §10.3), and documented request/response bodies with `application/json`.
- All errors use the shared `Error` schema: `{"error":"<machine_code>","detail":"<human message>"}`. Every operation documents at least its `4xx`/`5xx` responses using shared components — no inline error shapes.

### 10.2 Error examples (required on every operation)

Components (all responses `$ref` these — never duplicate inline):

```yaml
components:
  schemas:
    Error:
      type: object
      required: [error, detail]
      properties:
        error:  { type: string, example: validation_failed }
        detail: { type: string, example: url must be http(s) and <= 2048 chars }
    GateResult:
      type: object
      properties:
        pass: { type: boolean, example: false }
        observed_p95: { type: number, example: 389 }
  responses:
    BadRequest:      # 400
      description: Validation failed
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: validation_failed, detail: 'url must be http(s) and <= 2048 chars' }
    Unauthorized:    # 401
      description: Missing or invalid session cookie / API key
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: unauthorized, detail: 'authentication required' }
    Forbidden:       # 403
      description: Authenticated but not allowed (e.g. private_ip_blocked)
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: private_ip_blocked, detail: 'target resolves to a private IP' }
    NotFound:        # 404
      description: Resource not found
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: not_found, detail: 'check not found' }
    Conflict:        # 409
      description: Email already registered
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: email_exists, detail: 'an account with this email already exists' }
    Unprocessable:   # 422 — CI gate over budget (also used for domain validation)
      description: Gate failed — observed p95 exceeds budget
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: gate_failed, detail: 'observed p95 389ms exceeds budget 400ms' }
    TooManyRequests: # 429
      description: Rate limited
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example: { error: rate_limited, detail: 'too many requests, retry after 60s' }
```

The gate operation documents **two** success shapes: `200` with `GateResult(pass:true)` and `422` with `GateResult(pass:false, observed_p95)` (the `422` body is the `GateResult`, not `Error` — an explicit, documented exception to the rule above).

### 10.3 Auth header & security schemes

```yaml
components:
  securitySchemes:
    sessionCookie:        # browser / UI / user-facing /api/*
      type: apiKey
      in: cookie
      name: ll_session    # HttpOnly, SameSite=Lax; set by /api/auth/login|register
    apiKey:               # CI / machine /api/v1/*
      type: http
      scheme: bearer
      bearerFormat: ll_…
      description: 'API key (ll_ + 32 chars). Plaintext shown once at creation; server stores SHA-256 hash + prefix only.'
```

Rules: (a) `/api/*` operations use `security: [{sessionCookie: []}]`; (b) `/api/v1/*` operations use `security: [{apiKey: []}]` — **never both, never none** (except `GET /healthz` and `GET /r/{slug}`, which are explicitly `security: []` and documented as public); (c) the `Authorization: Bearer ll_…` header format must be stated in the scheme description exactly as in §3 Example 6; (d) `401 Unauthorized` is documented on every secured operation.

### 10.4 Pagination params (required on every list endpoint)

List endpoints: `GET /api/checks`, `GET /api/checks/{id}/alerts`, `GET /api/checks/{id}/series`, `GET /api/keys`. All use **cursor pagination** — no offset, no page numbers:

```yaml
components:
  parameters:
    Limit:
      name: limit
      in: query
      description: Max items per page (1-200).
      schema: { type: integer, minimum: 1, maximum: 200, default: 50 }
    Cursor:
      name: cursor
      in: query
      description: Opaque cursor from a previous response's next_cursor. Omit for the first page.
      schema: { type: string }
    Range:
      name: range
      in: query
      description: Time window for series/alerts.
      schema: { type: string, enum: [24h, 7d, 30d], default: 24h }
  schemas:
    Page:  # envelope returned by every list endpoint
      type: object
      required: [data]
      properties:
        data: { type: array, items: {} }      # items typed per-endpoint
        next_cursor: { type: string, nullable: true,
                       description: Pass as ?cursor= for the next page; null when exhausted. }
```

Required list-response shape: `{"data":[...],"next_cursor":"<opaque>"|null}` — `next_cursor` is present on **every** list response, `null` at the end, and the client contract is "follow `next_cursor` until `null`" (as in §3 Example 5). `limit`/`cursor`/`range` are `$ref`'d from the components above, never redefined inline.

### 10.5 CI checks for the contract

- `yamllint docs/api.yaml` passes; `python3 -c "import yaml,sys; yaml.safe_load(open('docs/api.yaml'))"` parses (PyYAML is test-only, not a runtime dep).
- A doc-test in CI extracts every §3 cookbook example's endpoint and asserts it exists as a path+method in `docs/api.yaml` (drift detection between docs and spec).

