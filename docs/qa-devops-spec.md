# LatencyLedger — QA + DevOps Specification

> Spec only. Covers test strategy, CI, Docker, deployment, monitoring, security
> scanning, release/versioning, and developer onboarding for LatencyLedger
> (see `docs/product-spec.md` and `docs/architecture.md`).
> **Hard constraint:** everything works with no paid services — Python 3.11+
> stdlib + SQLite only; GitHub Actions free tier; no third-party APM, email,
> or billing keys required to build, test, or boot.

---

## 1. Test Strategy

**Tools:** `unittest` (stdlib) as the canonical runner — zero install, runs on
any Python 3.11+ host. `pyproject.toml` may optionally list `pytest` as a
dev-only convenience, but CI must pass with stdlib alone so a bare
`python -m unittest discover` is the source of truth. A thin runner script
`scripts/test.sh` wraps the suite for one-command local/CI invocation:

```sh
#!/bin/sh
# scripts/test.sh — run all tests, with coverage if available
set -e
python -m unittest discover -s tests -v
# coverage (stdlib only, no plugin needed):
python -m coverage run -m unittest discover -s tests 2>/dev/null || true
```

`coverage` is an optional dev dependency (`pip install coverage`); if absent,
tests still run and coverage is simply skipped. No paid coverage service
(Codecov etc.) — coverage reports are local artifacts / CI logs only.

### 1.1 Test layers and planned counts

| Layer | Scope | Tool | Planned tests | Notes |
|---|---|---|---|---|
| **Unit** | `stats.py` (percentile, baseline, bucketing), `detector.py` (20% rule, cooldown, min-sample) | `unittest.TestCase` | **~30** | Pure functions, no I/O. Fixed cases + property-style loops (seeded random). |
| **API / integration** | `router.py`, `auth.py`, `checks.py`, `gate.py`, `handlers/*` | `unittest` + `http.client` against ephemeral server | **~40** | Temp-DB SQLite (`tempfile`, `:memory:` or tmp file), server on port `0`. Auth flows, gate 200/422, public-report isolation, error shapes. |
| **Sampler** | `sampler.py` vs local stub HTTP server | `unittest` + `http.server` stub thread | **~12** | Injected latency, timeout, redirect-off, non-2xx, connection-refused, oversized body. No external network. |
| **Scheduler / alerts** | `scheduler.py`, `alerts.py` | `unittest`, fake clock / stub SMTP+webhook | **~10** | Due-check loop, cooldown, retry/backoff, delivery logging. |
| **E2E smoke** (manual + scripted) | Full path: register → add check → ping-now → chart data → gate → public link | `scripts/e2e.sh` (curl against `docker compose up` or local server) | **~6 scripted scenarios** | Runs in CI as a smoke job after unit/integration pass; not part of `unittest` gate. |
| **SSRF / security** | `checks.py` URL validation, `auth.py` hashing | `unittest` | **~10** | Private/loopback/link-local rejection, DNS-rebind shape, oversized URL, password-hash round-trip, API-key compare. |

**Total planned: ~100 automated tests** (≈92 `unittest` + ≈6 scripted e2e scenarios + 2 gate checks). Sprint-1 minimum viable set is the unit + API layers (~70 tests); sampler/scheduler added before public launch (M2).

### 1.2 Coverage targets

- **Gate: ≥70% line coverage on `app/stats.py`, `app/detector.py`, `app/auth.py`** (matches roadmap/M1 target and product-spec KPI). Enforced in CI by a small stdlib check: run `trace`-based or `coverage` report, fail if a gated module drops below 70%. If neither tool is available in CI, the gate degrades to "tests pass" with a warning (never silently green without the check running).
- Overall `app/` target: ≥60% by M1, ≥75% by M2.
- Excluded from coverage: `app/main.py` (composition root — covered by e2e smoke), `app/static/*` (no Python).

### 1.3 Test layout and fixtures

```
tests/
├── __init__.py
├── helpers.py          # shared: temp DB, ephemeral server, auth client, fake clock
├── test_stats.py       # unit: percentiles/baseline/bucketing
├── test_detector.py    # unit: regression rule/cooldown/min-sample
├── test_auth.py        # unit+API: register/login/session/API-key
├── test_api.py         # integration: checks CRUD, gate, series, public report
├── test_sampler.py     # sampler vs stub server
├── test_scheduler.py   # due-loop, ingest queue, alert retry
└── test_security.py    # SSRF guard, rate-limit shape, header checks
scripts/
├── test.sh             # unittest discover + optional coverage
└── e2e.sh              # curl smoke against a running instance
```

**Fixtures (stdlib only):**

- `TempDB` — context manager creating a temp SQLite file, applying `app/schema.sql`, exposing `DATABASE_URL=file:...`. Never touches a real DB file.
- `TestServer` — starts `http.server` on an ephemeral port in a thread, yields `http.client` base URL, tears down on exit (`setUp`/`tearDown`).
- `StubUpstream` — `http.server` handler with programmable latency/status/body for sampler tests.
- `FakeClock` / `FakeSMTP` / `FakeWebhook` — injected via env or constructor seam; no network, no real email.
- Seeded sample-data factory in `helpers.py`: `make_samples(n, p95=..., drift=...)` so detector tests are deterministic.

**Rules:** no test may hit the external network; no test may use a fixed port; every test must clean up its temp DB/server; tests must pass on a clean checkout with only `python3.11+` (no `pip install`).

---

## 2. CI Pipeline (GitHub Actions)

Workflow: `.github/workflows/ci.yml`. Triggers: `push` to `main` and `pull_request`. **Must pass on push to `main`** — `main` is protected: merge only when all required checks are green.

### 2.1 Stages (jobs)

| Job | Runs | Steps |
|---|---|---|
| `lint` | `python -m py_compile` on all `app/**/*.py` + `python -m unittest discover` compile check; `ruff` *if already vendored*, else skip (stdlib-only). No network. | checkout → setup-python 3.11 → py_compile → (optional ruff) |
| `test` | `scripts/test.sh` (unit + integration + sampler + security). Matrix: Python 3.11, 3.12. | checkout → setup-python → `sh scripts/test.sh` → coverage gate check on `stats/detector/auth` |
| `e2e-smoke` | Build image, `docker compose up -d`, run `scripts/e2e.sh`, tear down. Depends on `test`. | docker build → compose up → curl smoke (6 scenarios) → compose down |
| `security` | `pip-audit` if deps exist (empty `requirements.txt` → no-op pass) + `bandit` if available, else stdlib grep checks (§6). Non-blocking in sprint 1, blocking from M2. | audit/scan → fail on high severity |
| `docker` | `docker build -t latencyledger:<sha> .` Depends on `test`. Push to GHCR **only** on tag/release (never on plain push to `main`). | docker build → (tag push if release) |

Pipeline order: `lint` + `test` in parallel → `e2e-smoke` + `docker` → `security` (parallel). Total target: <5 min on free-tier runners.

### 2.2 Minimal workflow sketch

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:   { runs-on: ubuntu-latest, steps: [...] }   # py_compile
  test:   { runs-on: ubuntu-latest, strategy: { matrix: { python: ["3.11","3.12"] } },
            steps: [...] }                            # sh scripts/test.sh
  security: { runs-on: ubuntu-latest, steps: [...] }  # pip-audit / bandit / stdlib checks
  e2e:    { needs: test, runs-on: ubuntu-latest, steps: [...] }  # docker compose + e2e.sh
  docker: { needs: test, runs-on: ubuntu-latest, steps: [...] }  # docker build only on push
```

### 2.3 Badges (README.md)

```md
![CI](https://github.com/devhasen/http-ping/actions/workflows/ci.yml/badge.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![Coverage gated](https://img.shields.io/badge/coverage-70%25%2B-orange)
```

Badges are static Shields.io / GitHub-native — no paid badge/coverage service.

---

## 3. Docker

### 3.1 Approach summary

Single-container, stdlib-only image. **Multi-stage build** (builder stage
installs nothing — stdlib only — so its job is bytecode compilation and
sanity checks; runtime stage is a minimal `python:3.11-slim` copy with only
`app/` + entrypoint). No pip layer is needed; if a future dependency appears,
it is installed only in the builder stage and copied into the runtime stage.
Runs as a non-root user; SQLite data lives on a mounted volume, never in the
image.

### 3.2 `Dockerfile` (design)

```dockerfile
# --- builder (compile check, no deps) ---
FROM python:3.11-slim AS builder
WORKDIR /src
COPY app/ ./app/
RUN python -m compileall -q app/

# --- runtime ---
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd -m -u 10001 appuser
WORKDIR /app
COPY --from=builder /src/app/ ./app/
USER appuser
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["python", "-m", "app.main"]
```

### 3.3 `docker-compose.yml` (design)

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: "file:/data/latencyledger.db"
      RUN_SCHEDULER: "1"
      PORT: "8000"
    volumes: [data:/data]
    restart: unless-stopped
    healthcheck: { test: [...], interval: 30s, timeout: 5s, retries: 3 }
    deploy:
      resources: { limits: { cpus: "0.5", memory: 256M } }   # single-host caps
volumes: { data: {} }
```

- **Healthcheck:** `GET /healthz` (DB ping + scheduler heartbeat from architecture.md); compose + Docker `HEALTHCHECK` both use it; unhealthy containers are restarted by `restart: unless-stopped`.
- **Resource limits:** `cpus: 0.5`, `memory: 256M` on a single host (prevents a runaway sampler from starving the host; tune up for larger fleets).
- **Scaling path (documented, not sprint-1):** split web/worker with `RUN_SCHEDULER=0` on the web container and a second container with `RUN_SCHEDULER=1` sharing the volume.

---

## 4. Deployment (single-host / VPS)

Target: one $5–10 VPS (or any Docker host) running `docker compose up`.
No paid services, no external keys required to boot. Reverse proxy (Caddy or
nginx) is recommended for TLS — both are free; Caddy is preferred for
automatic HTTPS with zero config.

### 4.1 Steps

1. Provision VPS (Ubuntu 24.04, 1 vCPU / 1 GB RAM), install Docker + Compose.
2. Clone repo; `cp .env.example .env` (see §4.2); set `SECRET_KEY`.
3. `docker compose up -d --build`.
4. Point reverse proxy at `localhost:8000`; issue TLS cert (Caddy automatic).
5. Verify: `curl https://<host>/healthz` → `200 {"ok": true, ...}`.
6. First run: register, add a check, confirm a chart appears within 5 minutes.

### 4.2 Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `PORT` | No | `8000` | HTTP listen port |
| `DATABASE_URL` | No | `file:/data/latencyledger.db` | SQLite path (WAL mode) |
| `SECRET_KEY` | **Yes (prod)** | — | Session signing; generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `RUN_SCHEDULER` | No | `1` | `0` = web-only (worker split) |
| `APP_BASE_URL` | No | `http://localhost:8000` | Public URL for email links / report links |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | No | — | Email alerts; **disabled entirely when unset** (app boots without it) |
| `OAUTH_ENABLED` | No | `0` | OAuth stub flag; do not enable without provider keys |
| `CHECK_INTERVAL_MIN_SEC` | No | `60` | Floor for check intervals |
| `LOG_LEVEL` | No | `INFO` | JSON log verbosity |

Secrets live only in `.env` (git-ignored). `.env.example` documents every
variable with safe placeholder values.

### 4.3 Backups (SQLite)

- **Manual:** `sqlite3 /data/latencyledger.db ".backup '/backups/latencyledger-$(date +%F).db'"` or `cp` the file while the app is stopped.
- **Scheduled (free, cron):** daily at 02:00, keep last 7:
  ```sh
  0 2 * * * docker exec <app> python -c "..."  # or host-side cp of the volume file
  find /backups -name 'latencyledger-*.db' -mtime +7 -delete
  ```
- Backups are plain SQLite files — restore is `cp backup.db /data/latencyledger.db && docker compose restart app`.
- Test a restore at least once before public launch (M2).

### 4.4 Rollback

1. Keep the previous image: tag every build `latencyledger:<git-sha>` and retain the last known-good tag.
2. Rollback = `docker compose stop app && docker tag latencyledger:<last-good> latencyledger:latest && docker compose up -d app`.
3. DB migrations are idempotent (`PRAGMA user_version`); never ship a migration that is not reversible by restoring the pre-deploy backup (§4.3). If a bad migration shipped: stop app → restore pre-deploy backup → roll back image.

---

## 5. Monitoring & Alerting

Constraint: **no paid APM**. Self-hosted and free tooling only.

### 5.1 Signals

- **Uptime:** `GET /healthz` polled every 30s by Docker healthcheck (§3) and by an external free check (e.g. a cron `curl` + alert, or the app self-checking another instance). Healthz reports DB ping + scheduler heartbeat, so a stalled scheduler is visible, not just a dead process.
- **App metrics:** `GET /metrics` (plain-text, Prometheus-compatible exposition, stdlib-generated) with counters: `ingest_total`, `ingest_p95_ms`, `detector_alerts_total`, `scheduler_stall_total`, `http_requests_total{status}`. Scraped by a local Prometheus if desired, or simply curled in cron — no agent required.
- **Logs:** structured JSON to stdout (`logging`, one `request_id` per call). Viewed via `docker compose logs -f`; optionally shipped to a file with log rotation (`json-file` driver, `max-size: 10m`, `max-file: 3`). No log service needed.
- **Self-monitoring (dogfooding):** LatencyLedger monitors its own `/healthz` as a check — the product's regression alerts double as infra alerts.

### 5.2 Alerting plan

- **Down / unhealthy:** Docker `restart: unless-stopped` + a cron watchdog: if `/healthz` fails 3 consecutive polls, send a webhook (free: any chat incoming webhook, or `mailto` via a local SMTP). Alert within 2 minutes.
- **Scheduler stall:** `scheduler_stall_total` increments on missed heartbeat; watchdog alerts on any increment.
- **Latency regression on the app itself:** self-check with a 20% p95 rule (same detector) → email/webhook to operator.
- **Disk / DB growth:** weekly cron checking volume size; alert at >80% disk or DB >1 GB.

### 5.3 Incident runbook outline

1. **Detect** — watchdog / healthcheck alert, or user report.
2. **Triage (5 min)** — `docker compose ps`; `curl localhost:8000/healthz`; `docker compose logs --tail=100`. Classify: process down / DB error / scheduler stall / bad deploy.
3. **Mitigate** — restart (`docker compose restart app`); if bad deploy, rollback per §4.4; if DB corrupt, restore latest backup per §4.3.
4. **Verify** — `/healthz` 200, scheduler heartbeat advancing, a test check ingests a sample.
5. **Postmortem** — write `docs/postmortems/YYYY-MM-DD-<slug>.md` (what happened, timeline, root cause, follow-up); share the public report link (`/r/{slug}`) as evidence. Keep postmortems in-repo — no paid tooling.

---

## 6. Security Scanning & Dependency Policy

### 6.1 Scanning (in CI, §2 `security` job)

- **`pip-audit`** on `requirements.txt` + `pyproject.toml`. Because the app is stdlib-only, `requirements.txt` is empty in sprint 1 — the job runs and passes trivially; it becomes meaningful the moment any dependency is added. Free, runs in CI.
- **`bandit`** (if available in the CI environment) for Python-specific issues (weak hashes, `eval`, unsafe temp files). Free.
- **Stdlib fallback checks** (always run, no install): grep-based checks for `eval(`, `exec(`, `pickle.loads`, `subprocess` with `shell=True`, `hashlib.md5`/`sha1` for security use, `random.` used for tokens (must be `secrets.`), and SQL string-interpolation patterns. These catch the same high-severity classes bandit flags, with zero dependencies.
- Fail CI on any **high** severity finding; mediums file an issue, don't block (until M2, then block on mediums too).

### 6.2 Dependency policy

- **Default: no dependencies.** Any new pip dependency requires a one-line justification in the PR (stdlib alternative considered, license, maintenance status). Target: `requirements.txt` stays empty.
- **Allowed categories if justified:** pinned exact versions (`==`), updated at least monthly via Dependabot/Renovate free tier; no pre-1.0 deps in production paths; no native-extension deps (keeps the Docker image portable).
- **Licenses:** MIT / Apache-2.0 / BSD / ISC only. Copyleft (GPL/AGPL) deps are rejected without maintainer sign-off.
- **`python:3.11-slim` base image** patched monthly (`docker pull` in CI on a schedule); pin by digest in release tags.

### 6.3 App-level security (from architecture.md — tested per §1)

SSRF guard (private/loopback/link-local rejection, DNS + redirect re-check, 10s timeout, 1 MB cap), per-IP login rate limit (5/min), per-key ingest limit (100/min), parameterized SQL, HttpOnly `SameSite=Lax` sessions, PBKDF2 ≥100k iterations, API keys stored as SHA-256 hashes only, security headers (CSP, `X-Content-Type-Options`, `frame-ancestors`). Each control has a corresponding test in `tests/test_security.py`.

---

## 7. Release & Versioning

- **SemVer** (`MAJOR.MINOR.PATCH`): MAJOR = breaking API/DB changes; MINOR = new features (backward-compatible); PATCH = bug fixes. Tagged `vX.Y.Z` on `main`, signed annotated tag preferred.
- **`CHANGELOG.md`** (Keep a Changelog format): `## [Unreleased]`, then `## [1.0.0] - YYYY-MM-DD` with `Added / Changed / Fixed / Security` sections. Every release PR updates it; the changelog entry is part of the release checklist, not an afterthought.
- **Release flow:** merge to `main` (CI green) → bump version in `pyproject.toml` → update `CHANGELOG.md` → tag `vX.Y.Z` → CI builds and pushes `latencyledger:vX.Y.Z` to GHCR → GitHub Release from the tag with changelog notes.
- **Pre-releases:** `vX.Y.Z-rc.N` for beta channels; never tag a commit that isn't green on `main`.
- **Hotfixes:** branch from the last release tag, cherry-pick the fix, patch-release `vX.Y.Z+1`, backport the changelog entry.

---

## 8. Onboarding Dev Environment

One-command run from a clean checkout. Prerequisites: Python 3.11+, Docker (optional alternative).

```sh
git clone https://github.com/devhasen/http-ping.git
cd http-ping
cp .env.example .env        # optional — defaults work with nothing set
docker compose up --build   # → http://localhost:8000
```

Without Docker:

```sh
python3 -m app.main         # stdlib-only, no pip install needed
```

Then:

```sh
sh scripts/test.sh          # run the full test suite (unit + integration)
sh scripts/e2e.sh           # smoke-test a running instance
```

- **First 5 minutes:** register → add `https://example.com` as a check → "Ping now" → see the chart. No keys, no accounts anywhere else.
- **Project conventions:** `CONTRIBUTING.md` covers branch naming (`feat/…`, `fix/…`), PR checklist (tests + changelog), and the stdlib-first dependency policy (§6.2). `SECURITY.md` covers vulnerability disclosure.
- **Local DB:** defaults to `./latencyledger.db` (file) or set `DATABASE_URL=:memory:` for throwaway runs. Migrations apply automatically on boot.


---

## 9. Appendix: Planned Test Counts (Summary)

| Layer | Planned |
|---|---|
| Unit (stats, detector) | ~30 |
| API / integration | ~40 |
| Sampler vs stub | ~12 |
| Scheduler / alerts | ~10 |
| SSRF / security | ~10 |
| **Total `unittest`** | **~102** |
| Scripted e2e smoke scenarios | ~6 |

CI stages: `lint → test (3.11/3.12) → {e2e-smoke, docker} → security`. Must pass on push to `main`.
Docker: multi-stage `python:3.11-slim` (builder compile-check → slim runtime, non-root),
`HEALTHCHECK` on `/healthz`, compose with `/data` volume, `0.5 CPU / 256M` limits.
