# LatencyLedger — Security Specification

Version 1.0 · 2026-11-08 · Security Lead (desk-7)
Scope: LatencyLedger SaaS (Python 3.11+ stdlib-only backend, SQLite, static frontend, Docker deployment) as defined in `docs/product-spec.md` and `docs/architecture.md`.
Constraints: **stdlib-only runtime, no paid security SaaS required.** All controls below are implementable with the Python standard library (`hashlib`, `secrets`, `hmac`, `sqlite3`, `urllib`, `logging`, `http.server`) plus host/OS tooling.

---

## 1. Threat Model (STRIDE)

### 1.1 Assets

| ID | Asset | Sensitivity | Notes |
|----|-------|-------------|-------|
| A1 | User credentials (password hashes, session tokens) | Critical | Confidentiality + integrity; breach = account takeover |
| A2 | API keys (`ll_…`) for CI ingestion/gate | High | Full `/api/v1/*` access for the owning user |
| A3 | User check configuration (URLs, intervals, thresholds, webhook targets) | High | URLs may point at internal/non-public endpoints; webhook URLs contain secrets |
| A4 | Latency samples + derived stats (p50/p95/p99, baselines) | Medium | May reveal neighbours' traffic patterns; business-sensitive |
| A5 | Alert history + delivery logs | Medium | Reveals incident timing/status of user's API |
| A6 | Public report content (`/r/{slug}`) | Low (intentionally public) | Must not leak A2/A3-internal fields |
| A7 | SQLite database file (`/data/*.db`) | Critical | Contains A1–A5; backup copies inherit classification |
| A8 | Server host + scheduler process (env, logs) | High | Holds session-signing/session material, SMTP creds, env secrets |
| A9 | Audit logs | High | Integrity-critical for forensics; see §7 |
| A10 | Docker image + CI pipeline (GitHub Actions workflow, `examples/github-actions.yml`) | High | Supply-chain entry point; holds production secrets |

### 1.2 Actors

| Actor | Capability | Motivation |
|-------|-----------|------------|
| Anonymous internet attacker | Unauthenticated HTTP access | Credential stuffing, SSRF abuse, scanning |
| Authenticated malicious user | Own account + API key | Abuse checker as SSRF/proxy, probe other users' data (IDOR), spam |
| Compromised user account / leaked API key | Victim's privileges | Data exfiltration, gate manipulation, alert-channel abuse |
| Malicious/compromised dependency or CI action | Build/deploy-time code exec | Token theft, backdoor, image poisoning |
| Insider (developer/operator) | Source + infra access | Accidental or deliberate secret/database exposure |
| Network-adjacent attacker | Traffic between user↔app, app↔target URL, app↔webhook | Sniffing session cookies/keys, MITM on non-TLS deployments |

### 1.3 Attack Surfaces

1. **Web app** (`http.server` routes in `app/router.py`, static frontend) — auth endpoints, check CRUD, ping-now, export, public report.
2. **Sampler/scheduler** (`app/sampler.py`, `app/scheduler.py`) — the server fetches *attacker-chosen URLs* (highest-risk surface: SSRF).
3. **Outbound channels** — webhook POSTs, SMTP email (`app/alerts.py`) — attacker-controlled URLs/addresses.
4. **CI gate API** (`/api/v1/*`) — API-key auth, no session; CI secrets in GitHub Actions.
5. **Data layer** — SQLite via `app/db.py`; SQL injection via any unsanitised input.
6. **Deployment** — Docker image, `docker-compose.yml`, volume `/data`, host env vars.
7. **Frontend** — vanilla JS + canvas; DOM XSS via check names, URLs, notes, git SHAs.
8. **Logs/observability** — structured logs to stdout; may inadvertently contain secrets/PII.

### 1.4 Risks (STRIDE)

Rating: Likelihood (L) × Impact (I) → Overall (H > M > L). Residual = rating after mitigation.

| # | Threat (STRIDE) | Description | L | I | Overall | Mitigation (owner) | Residual |
|---|-----------------|-------------|---|---|---------|--------------------|----------|
| T1 | **Spoofing / SSRF** | Attacker registers a check pointing at `169.254.169.254`, `localhost`, or RFC1918 hosts; sampler fetches cloud metadata/internal services and returns timing/status, or exfiltrates via alert webhook | H | H | **H** | SSRF guard (§4): scheme allowlist, DNS resolve + IP-range blocklist (private/loopback/link-local/reserved/unspecified), re-resolve per request, redirects disabled, 10s timeout, 1MB body cap; block DNS-rebinding by resolving once and connecting to the validated IP with original Host/SNI where feasible | M |
| T2 | **Spoofing / Credential attacks** | Credential stuffing, brute-force, and password-spraying against `/api/auth/login`; session fixation/hijack | H | H | **H** | PBKDF2-HMAC-SHA256 ≥200k (or scrypt) with per-user salt (§3), per-IP + per-account throttling, exponential backoff, account lockout, generic error messages, HttpOnly+SameSite session cookies, session rotation on login, constant-time comparisons | M |
| T3 | **Information disclosure / IDOR** | Authenticated user A guesses/reads user B's checks, samples, alerts, or API keys via predictable IDs (sequential ints) or missing ownership checks | M | H | **H** | Every query scoped by `user_id` (`WHERE id=? AND user_id=?`); unguessable IDs (`secrets.token_urlsafe` / UUID4) for checks/keys/slugs; 404 (not 403) for foreign objects; API keys never returned after creation; public reports strip private fields | L |
| T4 | **Tampering / Injection** | SQL injection via name/url/note/sha fields; DOM XSS via stored check names/notes rendered with `innerHTML`; header/log injection | H | M | **H** | Parameterised queries everywhere (no string formatting into SQL); output encoding per context (§4); CSP `default-src 'self'`; `X-Content-Type-Options: nosniff`; validate+cap length of all text fields; CR/LF stripping in log fields | L |
| T5 | **Repudiation** | User denies creating a check/key or triggering a gate; no evidence of who did what | M | M | **M** | Audit log (§7) with user_id, action, target, IP, timestamp; alert-delivery log; gate-call log; tamper-evident hash chain | L |
| T6 | **Information disclosure / Secret leakage** | Secrets (`.env`, SMTP creds, session material, API keys) committed to git, baked into Docker image, printed to logs, or sent in plaintext email/webhook | M | H | **H** | §5 secrets policy: env-only, `.gitignore`, Docker `COPY` excludes, log redaction, TLS-only in production, keys hashed at rest (SHA-256), shown-once plaintext | L |
| T7 | **Denial of service** | Attacker floods login (attrition), creates thousands of 1-minute checks, or points sampler at slow/large endpoints to exhaust threads/disk (SQLite growth) | M | M | **M** | Per-user plan limits (`plan_limits`), min interval 1m, account-level check quota; per-IP/per-key rate limits (login 5/min, ingest 100/min); request size caps, body cap 1MB, sampler concurrency cap, sample retention/pruning per plan history window | M |
| T8 | **Elevation of privilege / Plan bypass** | User forges plan/quota by tampering requests; free user enables Pro features (e.g. manual plan toggle abuse) | L | M | **M** | Plan is server-side column only, never accepted from client; admin plan-toggle endpoint requires separate admin credential + audit entry; enforce limits server-side on every create/ingest | L |
| T9 | **Tampering / Supply chain** | Compromised `python:3.11-slim` base, GitHub Action, or transitive dev dependency (pytest) injects code; typosquatted package added later | L | H | **M** | §6 policy: stdlib-only runtime (zero runtime deps = near-zero surface), pinned base-image digest, pinned Action SHAs, lockfile for dev deps, CI `pip-audit`-style review, image scan in CI | L |
| T10 | **Spoofing / Public-report enumeration** | Attacker enumerates `/r/{slug}` or `/s/{slug}` to harvest users' latency data; slug predictable | M | L | **M** | Slugs are `secrets.token_urlsafe(16)` (≥128-bit); toggling public off returns 404 immediately; no links/IDs to private resources in public HTML/JSON | L |
| T11 | **Information disclosure / Timing side-channel** | Login/gate responses leak whether an email exists or whether a key is valid via timing or error text | M | L | **M** | Always run a full PBKDF2 verify (dummy hash for unknown email); uniform login error `invalid credentials`; constant-time `hmac.compare_digest` for hashes/tokens; gate returns generic fail without distinguishing "no data" vs "over budget" where feasible | L |
| T12 | **Tampering / Scheduler & data integrity** | Clock skew, duplicate/replayed sample ingestion, or forged `{ms,sha}` samples corrupt baselines and gate results | L | M | **M** | Ingestion authenticated by API key, per-key rate limit, server stamps `ts` (ignore client ts), validate `ms` range (0–60000) and `sha` format (`[0-9a-f]{7,40}`), idempotency key or duplicate-window dedupe | L |

**Top 3 threats (highest priority):** T1 SSRF via the sampler, T2 credential/session attacks, T3 IDOR/cross-account data exposure. These are covered first in the pre-launch checklist (§10).

---

## 2. OWASP Top 10 (2021) Mapping

| # | OWASP 2021 | Where it applies in LatencyLedger | Controls |
|---|------------|-----------------------------------|----------|
| A01 | Broken Access Control | Check/sample/alert/key CRUD; plan limits; public report toggle; admin plan endpoint | Ownership-scoped queries on every route (T3); 404 for foreign objects; server-side plan enforcement (T8); role check on admin endpoint; deny-by-default router |
| A02 | Cryptographic Failures | Password storage, session tokens, API keys, SQLite at rest, TLS, public slugs | PBKDF2/scrypt (§3); SHA-256 hashed API keys; `secrets` module for all tokens; TLS via reverse proxy in production; file permissions `0600` on `/data/*.db`; random 128-bit+ slugs/IDs |
| A03 | Injection | All user inputs (email, name, URL, note, sha, gate `p95_ms`); frontend DOM | Parameterised SQL; strict allowlist validation per input type (§4); context output encoding; no `innerHTML` with user data; JSON body size caps |
| A04 | Insecure Design | Rate limits, quotas, cooldowns, SSRF guard, alert anti-spam | Threat model (§1); plan limits + min intervals; 6h alert cooldown; SSRF guard; state-machine for key revoke (immediate); abuse-case tests |
| A05 | Security Misconfiguration | Debug mangling, error verbosity, headers, Docker, default creds | No debug mode in prod; generic error bodies; security headers (CSP, HSTS where TLS, XFO, nosniff, Referrer-Policy); non-root Docker user; no default accounts; `Server` header suppressed |
| A06 | Vulnerable & Outdated Components | Zero runtime deps; `python:3.11-slim` base; pytest dev dep; GitHub Actions | §6 supply-chain policy: pinned digests/SHAs, dev lockfile, monthly review, Dependabot-equivalent (GitHub native) |
| A07 | Identification & Authentication Failures | Register/login/logout, sessions, API keys, OAuth stub | §3 in full: strong password policy, throttling+lockout, session rotation/expiry, shown-once keys, MFA-ready (P2) |
| A08 | Software & Data Integrity Failures | Docker image, CI workflows, sample ingestion, migrations | Signed/pinned Actions, digest-pinned base image, checksum-verified installs in CI, server-stamped ingestion, idempotent migrations, integrity checks on boot |
| A09 | Security Logging & Monitoring Failures | Audit log, alert deliveries, auth events, scheduler health | §7 audit logging, tamper-evident chain, `/healthz` + scheduler heartbeat, alert on repeated auth failures |
| A10 | Server-Side Request Forgery | Sampler (user URLs), webhook alerts, SMTP | SSRF guard (§4/T1): scheme+IP blocklist, DNS re-check, no redirects, timeouts, response caps; webhook targets validated the same way; SMTP host from config only, never user input |

---

## 3. AuthN/AuthZ Design

### 3.1 Password policy
- Minimum **12 characters** (allow up to 128; truncate policy via explicit reject, not silent truncation), maximum 128.
- No composition rules beyond length (NIST SP 800-63B); reject passwords in a small built-in common-password list (top ~1k corpus embedded, or at minimum: reject if `pw.lower()` in {`password`, `123456`, `qwerty`, …} — must be stdlib-only, so embed a compact list, no network fetch).
- Reject passwords equal to the email local-part.
- Email: valid format, ≤254 chars, normalised to lowercase, unique (case-insensitive) → `409` on duplicate.
- Registration / password-reset emails must not reveal whether an account exists (uniform response).

### 3.2 Hashing (stdlib only)
- **Primary: `hashlib.scrypt`** if available (OpenSSL ≥1.1): `scrypt(pw, salt=16B random, n=2**14, r=8, p=1, dklen=32)`. Store `scrypt$16384$8$1$<b64-salt>$<b64-hash>`.
- **Fallback (portable): `hashlib.pbkdf2_hmac('sha256', pw, salt, 200_000, dklen=32)`** — must meet ≥200k iterations; store `pbkdf2-sha256$200000$<b64-salt>$<b64-hash>`.
- Algorithm field stored with the hash so parameters can be upgraded over time (re-hash on next successful login when params are stale).
- Verify with `hmac.compare_digest` (constant-time). Always run a full verify against a dummy hash for unknown accounts (T11).
- Never log, return, or store plaintext passwords. Never use MD5/SHA-1/unsalted hashes.

### 3.3 Session management
- Opaque server-side sessions: `id = secrets.token_urlsafe(32)` (256-bit), stored in `sessions` table with `user_id`, `created_at`, `expires_at`.
- Cookie: `HttpOnly; SameSite=Lax; Path=/` (+ `Secure` when behind TLS — required in production; set via `COOKIE_SECURE=1` / auto-detect `X-Forwarded-Proto`). No `Domain` attribute (host-only).
- Lifetime: idle timeout **12h**, absolute timeout **30 days**. Expired sessions purged on boot + lazily on access.
- **Rotate session ID on login** (defeats fixation) and on password change; **invalidate all sessions on password change**.
- Logout: server-side row deleted + cookie cleared (instant revocation — the reason sessions are server-side).
- Sessions are per-device independent rows; no client-side JWT (avoids signing-key management and revocation problems at this scale).

### 3.4 Token storage
| Material | At rest | In transit | Shown to user |
|----------|---------|-----------|---------------|
| Password | scrypt/PBKDF2 hash + salt (above) | TLS only (prod) | never |
| Session ID | plaintext row in `sessions` (it *is* the credential; DB file perms + TLS protect it) — alternatively store SHA-256 of the ID; **preferred: store SHA-256(id)**, raw ID only in cookie | HttpOnly cookie, `Secure` in prod | never (cookie only) |
| API key | SHA-256 hash + 8-char display prefix only | `Authorization: Bearer ll_…` header over TLS | **once at creation** (full key); list shows prefix + created date; revoke → `revoked_at` set, immediate effect |
| Public slug / report ID | plaintext in DB (not a secret, but unguessable: `secrets.token_urlsafe(16)`) | URL path | shared by user |
| SMTP / OAuth secrets | env only (§5), never in DB or logs | — | never |

### 3.5 Brute-force protection & lockout
- Per-IP login throttle: **5 failed attempts / minute / IP** (in-memory token bucket in `router.py`/`auth.py`); `429` + `Retry-After` beyond.
- Per-account: after **5 consecutive failures**, exponential lockout: 1m → 2m → 4m … capped at 60m; reset on success. Lockout state in DB (`users.failed_attempts`, `users.locked_until`) so it survives restart and is per-account, not just per-IP.
- Per-key ingest throttle: **100 requests / minute / API key** → `429`.
- Per-IP global request throttle for unauthenticated endpoints (e.g. 60/min/IP on `/r/{slug}` and `/healthz` exempt rate-limited by proxy).
- All throttles return generic messages; never reveal lockout reason vs bad password in a way that enumerates accounts (uniform `401 invalid credentials`, with `429` only for rate state).
- Optional CAPTCHA/human-proof challenge after repeated failures is P2 (stdlib-only constraint keeps this out of sprint 1 — rate limits must suffice).
- Alert/log on: ≥10 failed logins for one account in 10 min → audit event + (P1) email to account owner.

### 3.6 Authorisation (every route)
- Session routes (`/api/*`): require valid session; resolve `user_id`; **every** data query includes `AND user_id = ?`.
- API-key routes (`/api/v1/*`): `Authorization: Bearer <key>`; resolve key hash → `user_id`; same scoping; keys cannot access session-only routes (e.g. key management, password change) and vice versa.
- Public routes (`/r/{slug}`): only rows with `is_public=1`; response built from an explicit allowlist of fields (no ORM-style dump of the `checks` row).
- Admin (plan toggle): separate `ADMIN_TOKEN` env secret compared with `compare_digest`; audited; never exposed in UI.

---

## 4. Input Validation & Output Encoding

General rules: **deny-by-default** (unknown fields → `400`); validate **server-side** (client validation is UX only); cap every string/number/body; reject NUL bytes and CR/LF in fields that end up in headers/logs; use `{"error": code, "detail": …}` with no stack traces, SQL text, or file paths in any error response.

### 4.1 Per-input-type rules

| Input | Type / constraints | Validation | On failure | Output encoding |
|-------|--------------------|-----------|------------|-----------------|
| Email (`register`, `login`) | string ≤254 | RFC-ish regex `^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$` after lowercase+strip; reject controls | `400 validation` | `html.escape` in UI; never interpolated into SQL/logs unescaped |
| Password | string 12–128 chars (§3.1) | length + blocklist + ≠ email local-part | `400` (generic, no hint which rule beyond length) | never rendered/logged |
| Check `name` | string 1–80 chars | strip; reject control chars/CR/LF | `400` | `html.escape` (text context); `textContent` in JS (never `innerHTML`) |
| Check `url` **(SSRF-critical)** | string 1–2048 chars | scheme ∈ {`https`, `http`} only; parse with `urllib.parse.urlsplit`; reject username/password in URL (`user:pass@host`); reject fragment; host required; port ∈ {80,443} or explicit 1–65535 non-privileged; **resolve hostname → reject if any A/AAAA in {127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fe80::/10, fc00::/7, 0.0.0.0/8, 100.64/10, documentation/reserved ranges}**; re-resolve+re-check at fetch time; redirects **disabled** (3xx with Location → recorded as status, not followed) or, if followed, max 3 with full re-validation each hop; timeout 10s; read cap 1MB; `User-Agent: LatencyLedger/1.0` | `400 ssrf_blocked` / `400 validation` | `html.escape` in HTML; `textContent` in JS; never in SQL unparameterised |
| Check `interval_sec` | enum {60, 300, 900, 3600} | allowlist (from plan: free min 300) | `400` | JSON number only |
| `threshold_pct` | number 5–100 | `float`, range check | `400` | JSON number |
| `note`, git `sha` (sample ingest) | `sha`: `^[0-9a-f]{7,40}$`; `note`: string ≤280, strip controls | regex; reject otherwise | `400` (ingest rejected, not partially stored) | `html.escape`; sha rendered as plain text (never as link href without validation) |
| Sample `ms` | number 0–60000 | range; `status` int 100–599; else reject | `422` (gate) / `400` (ingest) | JSON number |
| Gate `p95_ms` budget | number 1–60000 | range; check must exist + owned | `404` / `422 {pass:false, observed_p95}` | JSON number |
| Webhook `target` (alert channel) | URL ≤2048 | same SSRF rules as check URL, **plus** scheme must be `https` for production delivery; validate on save **and** on each send | `400 ssrf_blocked` | never rendered as clickable link without `rel="noopener noreferrer nofollow"` + scheme check |
| Email alert target | string ≤254 | same email validation | `400` | `html.escape` |
| `range` query param | enum {`24h`,`7d`,`30d`} | allowlist; bucket size derived server-side | `400` | JSON |
| Export `format` | enum {`csv`,`json`} | allowlist; filename generated server-side (`latencyledger-{check_id}-{date}.csv`), never from user input | `400` | `Content-Disposition: attachment` + `Content-Type` set server-side |
| Public `slug` (path) | `^[A-Za-z0-9_-]{16,64}$` | strict regex before any DB lookup | `404` | `html.escape` |
| API key (header) | `^ll_[A-Za-z0-9_-]{32}$` | format check, then SHA-256 + `compare_digest` | `401` (generic) | never logged (log only prefix/fingerprint) |
| JSON bodies (all POST) | ≤64KB total (ingest ≤16KB) | `Content-Type: application/json` required; strict `json.loads` with object-at-top-level; unknown keys rejected | `400` / `413` | — |
| `Cookie` / `Authorization` headers | size-capped (≤8KB) | parse defensively; malformed → ignore header (treat as unauthenticated) | `401` | — |

### 4.2 Output rules
- HTML: all user data via a single `esc()` helper (`html.escape(..., quote=True)`) at render time; **no `innerHTML`/`document.write` with user data**; inline SVG/canvas text drawn via `fillText` (canvas is not HTML — still escape nothing needed, but never inject into DOM as HTML).
- JSON API: `json.dumps` with `Content-Type: application/json; charset=utf-8`; never reflect raw input in error messages (use fixed error codes + safe `detail` strings).
- CSV export: fields quoted per RFC 4180 by hand (`csv` module); values starting with `=`, `+`, `-`, `@` prefixed with `'` to prevent spreadsheet formula injection.
- HTTP response headers: `Content-Security-Policy: default-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` (belt-and-braces alongside CSP), `Strict-Transport-Security` when `COOKIE_SECURE`/TLS enabled, `Cache-Control: no-store` on all `/api/*` responses.
- Redirects: only to same-origin paths; `Location` never built from user input.

---

## 5. Secrets Management

### 5.1 Policy
1. **No secrets in git, ever.** `.env` is gitignored (already in `.gitignore`); commit only `.env.example` with placeholder values. Pre-commit check: `grep -rE '(sk_|ll_[A-Za-z0-9_-]{20,}|password\s*=\s*["'\''][^"'\'']{4,})'` over staged files should return nothing; CI runs the same scan.
2. **Env-only at runtime.** All secrets via environment variables read in `app/config.py` (single choke point; no `os.environ` scattered elsewhere): `SESSION_SECRET` (if used for signing — sessions are opaque, so this is reserved), `SMTP_HOST/PORT/USER/PASS`, `ADMIN_TOKEN`, `OAUTH_*` (stub, P2). `DATABASE_URL`/`PORT`/`RUN_SCHEDULER` are config, not secrets, but still env-only.
3. **No hardcoded secrets** — including fallback defaults. If a required secret is missing, the app **fails to boot** with a clear error naming the variable (never silently use a default like `dev-secret` in production; a dev-only default is allowed only when `ENV=dev` is explicit and logs a loud warning).
4. **Never in Docker image layers.** `Dockerfile` must not `COPY .env`; `.dockerignore` excludes `.env`, `*.db`, `data/`, `.git/`. Run-time config via `docker-compose.yml` `environment:` / `env_file:` (host-side only) or orchestrator secrets.
5. **Minimal scope:** SMTP credentials have send-only scope; GitHub Actions secrets scoped per-repo; API keys per-user and revocable.

### 5.2 Rotation
- **Session material:** rotate on any suspected compromise by deleting all rows in `sessions` (global logout) — no key to rotate since sessions are opaque server-side.
- **API keys:** user-rotatable at any time (revoke + create); system **must support immediate revocation** (already required by spec) and bulk-revoke by user on abuse.
- **SMTP/OAuth/ADMIN_TOKEN:** rotate at least **every 12 months**, and **immediately** on: staff departure with access, suspected exposure/leak, or any incident touching env/host. Rotation runbook: set new value in env → restart/redeploy → verify `/healthz` + test alert → remove old value from host env + any secret store.
- **On suspected leak:** treat the secret as burned — rotate first, investigate second; assume anything ever committed to git is public even if later removed (rotation is mandatory after any `.env`/key commit).

### 5.3 Handling
- Secrets never written to logs, error pages, client responses, analytics, or support bundles. Log redaction: `auth.py`/`alerts.py` redact `Authorization`, `Cookie`, `SMTP_PASS`, and API-key full values (prefix only).
- DB backups (containing A7) are classified Critical: encrypt at rest where the host supports it, restrict to operator-only access, never upload to shared/public storage.
- Local dev: `.env` file with `chmod 600`; never paste real secrets into issues, PRs, or chat.

---

## 6. Dependency & Supply-Chain Policy

**Runtime: zero third-party dependencies** (`requirements.txt` is intentionally empty). This is the strongest supply-chain control available at this scale and must be preserved: any proposal to add a runtime dependency requires a security review + PR justification (per `CONTRIBUTING.md`).

| Surface | Policy |
|---------|--------|
| Python runtime | Pin Docker base image by **digest** (`python:3.11-slim@sha256:…`, updated monthly); non-root `USER`; `pip` not installed/used at runtime. Host Python ≥3.11; track CPython security releases on the python.org security mailing list / GitHub security advisories, patch within 14 days of a CVE rated ≥ medium. |
| Dev dependencies (pytest) | Only dev dep; pinned with exact version in a lockfile; reviewed monthly; `pip download --require-hashes` style hash pinning where feasible; never run `pip install` from an unpinned spec in CI. |
| GitHub Actions | Pin every action by **full commit SHA** (not tag/branch), with a comment noting the tag; review workflow diffs on every PR (workflows are a top supply-chain attack vector); minimal `permissions:` per workflow; no `pull_request_target` with checkout of untrusted code. |
| `examples/github-actions.yml` | Uses `actions/checkout@v4` → must be SHA-pinned in the shipped example; user secrets (`LL_URL`, `LL_API_KEY`) via GitHub Secrets only, never echoed (steps must not `echo`/`printenv` secrets). |
| New dependencies | PR must state: purpose, why stdlib can't do it, maintenance status, known CVEs (`pip-audit` / GitHub Dependabot), and license. Default answer is **no**. |
| Vulnerability tracking | Enable GitHub Dependabot (config + lockfile) — free, no SaaS; review alerts weekly; critical CVEs patched ≤7 days, high ≤14 days. `pip-audit` run in CI on dev deps (free, pip-installable). Docker image scanned in CI with `trivy` or `docker scout` (free tiers) — findings triaged weekly. |
| Typosquatting / integrity | Installs only from PyPI with TLS + hash verification; no `pip install` from VCS URLs or local wheels without review; `package-lock.json`/`node_modules` (legacy `httpping` CLI) must not be introduced into the Python app path — the shipped product is Python; if the TS CLI is kept, its lockfile is reviewed the same way. |
| Build reproducibility | Docker build from clean context; no fetching code at container runtime; app boots with network fully disabled (self-test in CI: run with `--network none`). |

---

## 7. Audit Logging

### 7.1 What to log
Structured JSON lines to stdout (`logging`, same pipeline as app logs). Every event: `ts` (UTC ISO-8601), `event`, `user_id` (or `null`), `actor` (`session`|`api_key`|`anonymous`|`admin`|`scheduler`), `ip`, `target_type`, `target_id`, `result` (`success`|`failure`), `request_id` (per-call correlation ID), and event-specific fields below. **Never log**: passwords, full API keys, session IDs, SMTP creds, full `Authorization`/`Cookie` headers, or check URLs in full for auth events (log host only, or a check ID).

| Event | Fields | Purpose |
|-------|--------|---------|
| `auth.register`, `auth.login` (success + failure), `auth.logout`, `auth.password_change` | `email_hash` (SHA-256 of email, for correlation without storing PII in logs), `ip`, `user_agent` | T2/T5 forensics |
| `auth.lockout`, `auth.rate_limited` | `email_hash`, `ip`, `fail_count`, `locked_until` | Brute-force detection |
| `key.created`, `key.revoked`, `key.used` (sampled: log on first use per hour per key, not per request) | `key_prefix`, `key_id` | A2 lifecycle, T12 |
| `check.created/updated/deleted`, `check.ping_now`, `check.public_toggled` | `check_id`, `url_host` only, `interval_sec`, `is_public` | T1/T3/T5 |
| `ssrf_blocked` | `url_host`, `resolved_ips` (truncated), `reason` | T1 — alert if >5/hour from one account |
| `gate.called` | `check_id`, `p95_ms`, `observed_p95`, `pass` | T12 gate integrity |
| `alert.fired`, `alert.delivered` (per channel), `alert.failed` | `alert_id`, `channel_kind`, `target_host`, `http_status`, `attempts` | A5, delivery disputes (T5) |
| `admin.plan_changed` | `user_id`, `from_plan`, `to_plan`, `admin_actor` | T8 |
| `export.generated` | `check_id`, `format`, `range`, `row_count` | A4 bulk-read tracking |
| `session.revoked_all`, `security.global_logout` | `reason` | Incident response (§8) |
| `scheduler.stall`, `health.degraded` | — | Availability + A09 |
| `http.4xx/5xx` (error rate aggregates) | `route`, `status`, `count` (5-min buckets) | Anomaly detection |

### 7.2 Retention
- Audit events: **13 months** online (queryable), then archive; alert/delivery logs: **13 months** (matches Pro 1-year history plan); auth events: **13 months**.
- Sample data retention follows plan (`plan_limits.history_days`: free 7d, Pro 90d, Team 1y) — enforced by a daily prune job, logged as `retention.pruned` with row counts.
- Docker/host log rotation: `json-file` with `max-size=10m, max-files=10` per container (or host journald equivalent) — never unbounded growth (T7).

### 7.3 Tamper-evidence
- **Hash chain:** each audit row written to SQLite includes `prev_hash` and `hash = SHA256(prev_hash || canonical_json(event))`; a daily (or on-boot) verification job recomputes the chain and alerts on mismatch (`audit.chain_broken`). Local, stdlib-only, no external service required.
- Audit table is **append-only**: no UPDATE/DELETE code paths anywhere in the app; DB user (service account) is granted no DELETE on `audit_log` by convention + code review; the prune job must never touch audit rows.
- Forward a daily copy (or the daily chain head hash) to an off-host location the operator controls (e.g. email digest to operator, or append to a separate file on different storage) — free, no SaaS. This bounds the value of host-level log tampering.
- Clock: use `datetime.now(timezone.utc)` server-side everywhere; never trust client timestamps; log both wall-clock and a monotonic sequence number per process.

---

## 8. Incident Response Plan

### 8.1 Roles (small-team reality: one person may hold several)
| Role | Responsibilities | Contact |
|------|------------------|---------|
| **Incident Commander (IC)** | Owns the incident, timeline, decisions, comms | Maintainer / on-call operator (name + email in `SECURITY.md` contact; private runbook holds phone) |
| **Security Lead** | Threat assessment, containment, eradication, disclosure decision | This spec's owner |
| **Comms Lead** | User notifications, status page, public disclosure | IC if team <3 |
| **Platform/Ops** | Host, Docker, DB, backups, env/secret rotation | Operator |

### 8.2 Severity levels
| Sev | Definition | Examples | Response target | User notification |
|-----|-----------|----------|-----------------|-------------------|
| **S1 Critical** | Active/exploited breach, data loss, full compromise | DB exfiltrated; session-signing material leaked; SSRF yielding internal data | Respond ≤1h, contain ≤4h | ≤24h + public disclosure per §9 |
| **S2 High** | Exploitable vuln, mass credential attack, major DoS | Auth bypass; credential stuffing at scale; scheduler down >1h | ≤4h, fix ≤72h | Affected users ≤72h |
| **S3 Medium** | Limited-impact issue, workaround exists | IDOR on non-sensitive fields; alert spam bug | ≤1 business day, fix ≤14d | In release notes |
| **S4 Low** | Hardening, informational | Header missing; verbose error text | Backlog | Release notes |

### 8.3 Steps
1. **Detect** — audit-log alerts (§7), `/healthz` failures, user reports via `security@…`, GitHub Dependabot/advisory, anomaly in ingest/gate volume.
2. **Triage & declare** — IC assigns severity, opens an incident record (private issue or `docs/incidents/<date>-<slug>.md` tracked file), starts a UTC timeline. Freeze non-emergency deploys.
3. **Contain** — smallest effective blast-radius action, in order of preference: rate-limit/block offending IP or key; revoke affected API keys/sessions (`security.global_logout`); disable the vulnerable feature by env flag (e.g. `OAUTH_ENABLED=0`, `RUN_SCHEDULER=0`, public reports off); block SSRF target pattern. Do **not** wipe the host/DB before forensic capture (step 5) unless S1 active exfiltration demands it.
4. **Eradicate** — patch, rotate all secrets that could be exposed (assume A1/A2/A8 burned until proven otherwise: new `ADMIN_TOKEN`, SMTP creds, force password reset for affected accounts), rebuild Docker image from pinned digest, redeploy.
5. **Preserve & investigate** — snapshot DB + audit chain head + container logs *before* remediation where feasible; verify audit hash chain (§7.3); identify scope (which users/keys/data, what time window) from audit events + `ssrf_blocked`/`gate.called` logs.
6. **Recover** — restore service incrementally; monitor auth/sampler/gate error rates for 24h; keep heightened logging for 7 days.
7. **Notify** — affected users by email (what, what data, what they must do: rotate keys/reset password), public disclosure per §9 coordinated with any reporter.
8. **Postmortem** — within 5 business days: root cause, timeline, what detection missed, action items with owners; update this spec + add regression tests (e.g. new SSRF/IDOR test). Blameless.

### 8.4 Contact / escalation
- Public: `security@latencyleledger.example` (see §9 / `SECURITY.md`). Private runbook (operator-held, not committed with secrets): IC phone, host provider console URL, DB backup location, secret-rotation checklist. Escalate to host provider if infra-level compromise is suspected. Law-enforcement/regulator notification is IC + Security Lead decision per jurisdiction and data involved (GDPR 72h breach rule where applicable).

---

## 9. Responsible Disclosure Policy (`SECURITY.md` content draft)

The repo already ships a `SECURITY.md`; the following is the full replacement draft (keep the file name at repo root so GitHub surfaces it):

```markdown
# Security Policy

## Reporting a vulnerability

LatencyLedger welcomes responsible security research. If you believe you have
found a security vulnerability, please report it privately:

- **Email:** security@latencyleledger.example
- **Include:** affected version/branch, reproduction steps, impact assessment,
  and any proof-of-concept. Do not attach real user data or test against
  other users' accounts.

We will:

- Acknowledge your report within **3 business days**.
- Confirm and assess the issue, and provide a target fix date within **14 days**.
- Release a fix, then publish a coordinated disclosure (with credit, unless you
  prefer to remain anonymous) at a time agreed with you — please do not
  disclose publicly before then.

### Safe harbour & good-faith rules

Good-faith research that follows this policy will not be treated as an attack
and we will not pursue legal action. Please:

- Test only against your own account and instances you own.
- Avoid automated scanning that could degrade the service for others
  (no high-volume fuzzing, no DoS, no social engineering).
- Do not access, retain, or disclose other users' data beyond the minimum
  needed to demonstrate the issue; stop and report promptly if you encounter it.
- Do not use findings to extort, defraud, or spam.

Out of scope: social engineering/phishing of staff, physical attacks, and
vulnerabilities in third-party services (report those to the operator).

## Supported versions

`main` (pre-1.0, rolling release). Only the latest release receives security
fixes; self-hosters should redeploy image digests promptly when a fix ships.

## Security notes for self-hosters

- The sampler blocks private/loopback destinations to prevent SSRF; do not
  disable or weaken the guard in `app/checks.py` / `app/sampler.py`.
- Serve over TLS (reverse proxy) in production so session cookies and API
  keys are encrypted in transit; set `COOKIE_SECURE=1` behind TLS.
- Never commit `.env` or API keys; session and API-key material is hashed at
  rest (see `docs/security-spec.md` §3/§5).
- Keep the Docker base image digest and GitHub Actions pins updated
  (see `docs/security-spec.md` §6).
```

---

## 10. Pre-Launch Security Checklist

**How to use:** every box must be checked (or explicitly waived with a written rationale + owner in the launch ticket) before the first public deploy. IDs are stable for referencing in tickets. 38 items.

### AuthN/AuthZ
- [ ] S-01 Password policy enforced server-side: 12–128 chars, common-password blocklist, ≠ email local-part; over-length rejected (not truncated).
- [ ] S-02 Hashing is scrypt (n=2^14,r=8,p=1) or PBKDF2-HMAC-SHA256 ≥200,000 iterations, 16-byte `secrets` salt, algorithm+params stored with hash; `hmac.compare_digest` used.
- [ ] S-03 Password change re-hashes, rotates the current session, and invalidates all other sessions.
- [ ] S-04 Sessions: opaque `secrets.token_urlsafe(32)`, stored as SHA-256 hash server-side, HttpOnly + SameSite=Lax (+ Secure in prod), idle 12h / absolute 30d, rotated on login, instant revocation on logout.
- [ ] S-05 Login throttling live: per-IP 5/min, per-account lockout with exponential backoff (1m→60m cap), generic `401` for unknown email vs wrong password, dummy-hash verify path tested.
- [ ] S-06 API keys: `ll_` + 32 `secrets` chars, SHA-256 hash + prefix only at rest, shown once, per-key 100/min throttle, revoke effective immediately (verified by test).
- [ ] S-07 Every `/api/*` and `/api/v1/*` handler scopes queries by `user_id`; cross-account IDOR tests pass (user B gets 404 for user A's check/key/alert IDs, including sequential-ID guessing).
- [ ] S-08 Public report `/r/{slug}` returns only allowlisted fields; disabling `is_public` makes the URL 404 immediately; no private IDs/URLs/keys in HTML or JSON.
- [ ] S-09 Admin plan-toggle endpoint requires `ADMIN_TOKEN` via `compare_digest`, is not reachable from the UI, and writes an `admin.plan_changed` audit event.
- [ ] S-10 OAuth paths are disabled by default (`OAUTH_ENABLED=0`) and the app boots cleanly with no provider keys set.

### SSRF & Input Handling
- [ ] S-11 SSRF guard passes bypass tests: `169.254.169.254`, `127.0.0.1`, `10/8`, `172.16/12`, `192.168/16`, `::1`, `0.0.0.0`, `100.64/10`, DNS-rebinding (TOCTOU re-check), redirect-to-internal, `user:pass@` URLs, `file://`/`gopher://` schemes — all blocked, `ssrf_blocked` logged.
- [ ] S-12 Sampler: redirects disabled (or ≤3 hops each re-validated), 10s timeout enforced, 1MB response cap enforced, no shell/`os.system` anywhere near URL handling.
- [ ] S-13 Webhook targets validated with the same SSRF rules on save *and* on send; production webhook delivery requires `https`.
- [ ] S-14 All SQL is parameterised (grep audit for `%`/`+`/`f-string`/`format` in SQL strings = zero hits); no dynamic table/column names from user input.
- [ ] S-15 All form/body fields validated per §4.1 table (length caps, allowlists, numeric ranges, regexes); unknown JSON fields rejected; bodies size-capped; error responses contain no SQL/stack traces/file paths.
- [ ] S-16 Frontend: no `innerHTML`/`document.write` with user data (grep-verified); check names, notes, SHAs rendered via `textContent`/`esc()`; CSV export formula-injection prefixing (`'`) applied.

### Secrets, Transport & Platform
- [ ] S-17 `.env` gitignored + `.dockerignore` excludes `.env`/`*.db`/`data/`; CI secret-scan passes; `.env.example` contains placeholders only.
- [ ] S-18 App fails to boot with a clear error if a required secret is missing (no silent `dev-secret` default outside explicit `ENV=dev`).
- [ ] S-19 TLS plan documented and staged: reverse-proxy termination, `COOKIE_SECURE=1`, HSTS header present when TLS enabled; plain-HTTP prod deploy is explicitly blocked or warned.
- [ ] S-20 Security headers present on all responses (spot-checked with `curl -I`): CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on `/api/*`.
- [ ] S-21 Docker: pinned base-image digest, non-root `USER`, no runtime network needed to boot (verified with `--network none`), `/data` volume permissions `0600`/`0700`, log rotation configured.
- [ ] S-22 No default/demo accounts or debug endpoints in the shipped image; `debug`/`trace` routes return 404; `Server` header suppressed or generic.

### Supply Chain & CI
- [ ] S-23 `requirements.txt` empty and verified at runtime; any new runtime dep has a merged security-review PR (default: none).
- [ ] S-24 All GitHub Actions pinned by full commit SHA with the tag noted in a comment; workflow `permissions:` minimised; workflow diffs reviewed.
- [ ] S-25 Dev dependencies locked + hashed; `pip-audit` (or equivalent) clean in CI; Dependabot enabled and first scan reviewed.
- [ ] S-26 Container image scan (trivy/scout) run on the release candidate; critical/high findings fixed or waived in writing.

### Logging, Monitoring & Response Readiness
- [ ] S-27 Audit events (§7.1) emitted for all listed actions; no secrets/PII in log lines (grep + sample review of one day of logs).
- [ ] S-28 Tamper-evident hash chain writing + verification job running; chain-head forwarded off-host daily; audit table has no UPDATE/DELETE code paths.
- [ ] S-29 Alerting live: repeated auth failures, `ssrf_blocked` spike, scheduler-stall webhook, chain-break event — each tested end-to-end (forced event → alert received).
- [ ] S-30 `/healthz` returns DB + scheduler heartbeat; uptime check (self or free external pinger) confirming it.
- [ ] S-31 Retention/prune job running per plan history windows; `retention.pruned` logged; disk-usage alarm threshold set (T7).

### Abuse & Resilience
- [ ] S-32 Rate limits verified by load test: login 5/min/IP, ingest 100/min/key, unauthenticated 60/min/IP — `429` + `Retry-After` observed.
- [ ] S-33 Quotas enforced server-side: free-plan check cap + min interval; over-limit create returns `402`; plan value cannot be set from any client request (negative test).
- [ ] S-34 Regression-alert anti-spam: 6h cooldown per check verified; alert delivery retries (3, exponential backoff) logged without blocking ingest.
- [ ] S-35 Gate endpoint: unauthenticated → `401`; wrong budget type → `400`; over budget → `422 {pass:false, observed_p95}`; forged/`ms`-out-of-range samples rejected.

### Disclosure & Launch
- [ ] S-36 `SECURITY.md` (repo root) matches §9, GitHub Security tab shows it, `security@…` mailbox is monitored with an auto-reply + 3-business-day acknowledgement tested.
- [ ] S-37 Incident runbook (§8) printed/stored off-host with named IC + Security Lead + contacts; one tabletop exercise completed and logged.
- [ ] S-38 Full test suite green in CI (`pytest -q`, coverage ≥70% on stats/detector/auth), including the new security regression tests (SSRF bypasses, IDOR, key revoke, lockout, header presence).

---

## Appendix: Traceability

| Spec section | Architecture / Product refs |
|--------------|------------------------------|
| §1 Threat model | `docs/product-spec.md` §6 risks (SSRF abuse, scheduler, false positives); `docs/architecture.md` Security |
| §2 OWASP mapping | All routes in `docs/architecture.md` API Design |
| §3 Auth design | Product-spec story 1 (PBKDF2 ≥100k → tightened to ≥200k/scrypt here); architecture Auth Approach |
| §4 Validation | Product-spec story 2 (URL validation); architecture SSRF guard |
| §5–§6 Secrets/supply chain | architecture Deployment (env vars, Docker); `examples/github-actions.yml` secrets |
| §7–§8 Logging/IR | architecture Observability (`/healthz`, structured logs, self-monitoring) |
| §9 Disclosure | existing `SECURITY.md` (superseded by §9 draft) |

*This spec supersedes the brief Security notes in `docs/architecture.md` and the draft `SECURITY.md` where they conflict. Implementation tickets should reference item IDs (§10: S-01…S-38) and threat IDs (§1.4: T1…T12).*
