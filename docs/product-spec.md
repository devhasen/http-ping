# LatencyLedger — Product Specification

## 1. Idea / Chosen SaaS Concept

- **Name:** LatencyLedger
- **One-line pitch:** Continuous API latency regression tracking with CI gates — know when your API got slower before your users do.
- **Target users:** Solo developers and small teams (2–20 devs) building REST APIs / SaaS backends; indie hackers shipping on GitHub; platform/devops-lite engineers who care about p95 but can't justify Datadog/New Relic.
- **Core value props:**
  1. **Regression alerts, not just uptime:** Flags a 15%+ p95 rise vs rolling baseline even when status is still "200 OK" — the gap uptime tools miss.
  2. **CI-native:** GitHub Actions step + API key; gate PRs on latency budgets (e.g. p95 < 400ms) with one YAML block.
  3. **Zero-setup checks:** Paste a URL, get min/max/p50/p95/p99, sparkline history, and per-region-ish breakdown in <60 seconds.
  4. **Shareable evidence:** Public read-only report links for postmortems / PR comments ("p95 regressed 212ms→389ms on commit abc123").
  5. **Cheap & self-hostable:** Flat pricing, no per-seat/per-incident billing; Docker self-host for teams that can't send traffic data to a third party.
- **Competitors / substitutes:**
  | Competitor | What they do | Gap LatencyLedger exploits |
  |---|---|---|
  | UptimeRobot / Better Stack | Uptime + status pages, latency as secondary stat | No baseline regression detection, no CI gate, latency is an afterthought |
  | Bencher / Gatling Cloud | Benchmark tracking in CI | Heavy harness setup, benchmark-centric not live-API-centric, pricier/complex for indie APIs |
  | Datadog APM / New Relic | Full APM, infra + traces | Overkill + expensive for small teams; requires agent instrumentation |
  | Pingdom / Statuscake | Synthetic monitoring | Alert on downtime, not gradual latency drift; weak percentile history |
- **Differentiation:** Only tool that (a) treats *latency trend vs baseline* as first-class alert, (b) works on a plain public URL with no agent, (c) gates CI on percentile budgets, and (d) can self-host in one Docker command.
- **Why now (2026):** API latency regressions are a top cause of silent churn; AI-generated code volume has exploded, making accidental N+1 queries / missing indexes more common; CI performance gating (Gatling, Bencher patterns) is proven but tools target enterprise load-testers, not live endpoint drift for small teams. Uptime market is crowded/saturated ($8.5B, 9% CAGR) while *latency-drift* tooling for indies is thin.

## 2. User Stories

### P0 — must ship in sprint 1
1. **Sign up / log in** — As a developer, I can create an account with email+password so my checks stay private. *AC: POST /api/auth/register creates user with salted hash (hashlib.pbkdf2_hmac, ≥100k iters); duplicate email → 409; login returns HttpOnly session cookie; logout invalidates session.*
2. **Add a URL check** — As a user, I can add `https://api.myapp.com/users` with interval (1m/5m/15m/1h) so I can watch it. *AC: validation rejects non-http(s), >2048 chars; stored in SQLite; appears in dashboard list within 1s.*
3. **Manual ping now** — As a user, I can click "Ping now" to run N=10 requests and see per-request ms. *AC: returns array of {ms,status} sorted; p50/p95/p99/min/max/avg computed server-side; error requests counted separately, not crashed.*
4. **History chart** — As a user, I can see last 24h/7d latency sparkline per check. *AC: API returns bucketed points (avg + p95 per bucket); frontend renders canvas chart with no build step; empty state when <2 points.*
5. **Regression alert** — As a user, I get an email/webhook alert when p95 rises >20% over rolling 7d baseline (min 50 samples). *AC: detector runs on each ingest; alert fires once per 6h cooldown per check; alert log visible in UI; testable via injected samples.*
6. **API key for CI** — As a user, I can generate/revoke an API key (ll_…) shown once. *AC: only hash stored; key authenticates /api/v1/*; revoke takes effect immediately; list shows prefix + created date.*
7. **CI gate endpoint** — As a CI user, I can `POST /api/v1/checks/{id}/gate` with budget `{p95_ms:400}` and get pass/fail. *AC: 200 {pass:true} when under budget, 422 {pass:false, observed_p95} when over; works with API key, no session needed.*
8. **Public report link** — As a user, I can toggle a check public and share a read-only link. *AC: /r/{slug} works without login, shows chart + stats, no API keys/settings leaked; toggle off → 404.*

### P1 — next sprint
9. **Multiple endpoints per project** — As a user, I can group checks into projects. *AC: projects CRUD, checks belong to one project, dashboard filters by project.*
10. **Alert channels** — As a user, I can add webhook URL or email per check. *AC: test-send button; delivery logged with status code; exponential backoff retry (3 attempts).*
11. **Status page** — As a user, I can publish a status page aggregating my checks. *AC: /s/{slug} shows component list with 90d uptime %, incident list auto-generated from down/regression events.*
12. **Commit annotation** — As a CI user, I can tag samples with git SHA (`POST .../samples {sha, note}`). *AC: chart marks SHA; regression alert includes last SHA before drift.*
13. **Export CSV/JSON** — As a user, I can export check history. *AC: GET /api/checks/{id}/export?format=csv streams file; respects date range; auth required.*
14. **Slack/Discord notifications** — As a user, I can post alerts to chat. *AC: incoming-webhook POST with formatted text; failure logged, doesn't block ingest.*

### P2 — later
15. **Multi-region checks** — As a user, I can check from 3 regions and compare. *AC: region field on check; scheduler fans out; UI compares p95 per region. Requires paid workers — stubbed as single-region in P0.*
16. **Anomaly detection (ML-lite)** — As a user, I get alerts on unusual variance, not just mean shift. *AC: z-score on p95 series; threshold configurable; false-positive rate measured in tests.*
17. **Teams / workspaces** — As a team, we can share checks and roles (owner/member). *AC: invite by email, role check on every route, member cannot delete project.*
18. **SSO / OAuth** — As a user, I can log in with GitHub/Google. *AC: OAuth stub behind flag; no provider keys required to boot (disabled without env vars).*

## 3. Feature List (buildable in one sprint, no paid third parties)

| Priority | Feature | Notes |
|---|---|---|
| P0 | Auth (session cookie + API key), user CRUD | stdlib only |
| P0 | Check CRUD + scheduler (in-process thread, urllib) | interval 1m–1h, timeout 10s, follow redirects off |
| P0 | Sample ingest (ms, status, size, sha) into SQLite | WAL mode |
| P0 | Stats: min/max/avg/p50/p95/p99 + baseline (rolling median of daily p95) | pure Python |
| P0 | Regression detector (+20% rule) + alert log + email (smtplib, optional) + webhook | email disabled without SMTP env |
| P0 | CI gate API + GitHub Actions example YAML in docs | |
| P0 | Dashboard + check detail + public report (static HTML/CSS/JS, canvas chart) | no build step |
| P0 | Docker + docker-compose, health endpoint | |
| P1 | Projects, status page, CSV export, chat webhooks | |
| P2 | Multi-region, ML anomaly, teams, OAuth stub | architecture-ready, not sprint-1 |

All P0 features use only Python stdlib + SQLite. No external API keys needed to boot.

## 4. Business / Pricing Model Sketch

| | Free | Pro ($9/mo) | Team ($29/mo) |
|---|---|---|---|
| URL checks | 3 | 25 | 100 |
| Check interval | 5 min min | 1 min min | 1 min + multi-region |
| History | 7 days | 90 days | 1 year |
| Regression alerts | 1 channel (email) | email + webhook + chat | all + status pages |
| CI gates | 1 project | unlimited | unlimited |
| Public report links | yes | yes | yes + custom domain |
| Self-host | yes (community) | — | yes |

- Usage limits enforced in `plan_limits` table checked on check-create + ingest; over-limit → 402 with upgrade link.
- Billing P1: Stripe *optional* behind env flag; sprint-1 ships with manual plan toggle (admin endpoint) so no payment keys needed to run.
- CAC assumption: GitHub/OSS distribution (self-host → convert to hosted Pro). LTV target: 8 mo × $9 = $72.

## 5. Success Metrics / KPIs

- **Activation:** ≥40% of signups add first check within 24h; median time-to-first-chart <5 min.
- **Retention:** W4 cohort retention ≥25% (weekly active check viewed).
- **Value proof:** ≥30% of Pro users receive ≥1 true regression alert in first 30d; alert precision (user marks useful) ≥70%.
- **Revenue:** 50 paying users in 6 months ($450 MRR) as first milestone; free→paid conversion ≥3%.
- **Reliability:** Scheduler uptime ≥99.9% (self-monitored); p95 ingest latency <2s; test coverage ≥70% on stats/detector modules.
- **North Star:** Number of checks with a regression alert delivered that was acted on (proxy: user opens alert → views chart within 1h).

## 6. Non-goals and Risks

**Non-goals (sprint 1):** Browser/JS performance testing (Lighthouse-style), load testing (k6/Gatling territory), full APM/tracing, mobile SDK, native apps, multi-region (P2).

**Risks:**
- *Scheduler reliability in single-process* — Mitigate: separate worker via env flag (`RUN_SCHEDULER=0` for web-only), WAL SQLite, idempotent ingest.
- *False-positive alerts erode trust* — Mitigate: min-sample threshold, 20%+ hysteresis, 6h cooldown, user-tunable threshold.
- *Abuse (using checker as SSRF/proxy)* — Mitigate: block private/loopback IPs at DNS+connect, timeout, rate limits (see architecture.md Security).
- *Crowded uptime market* — Mitigate: position strictly on latency-drift + CI gate, not uptime/status alone.
- *SQLite write contention* — Mitigate: single-writer queue, WAL, short transactions; Postgres migration path documented.

## 7. Candidate Evaluation

Scored 1–5 (5 best). Weights: Value 35%, Feasibility 30%, Novelty 20%, Effort 15% (effort 5 = least effort).

| Criterion | A. LatencyLedger (latency regression + CI gate) | B. StatusPage for indies | C. Webhook debugger |
|---|---|---|---|
| Novelty | 5 — drift detection + CI gate niche, thin competition | 3 — Statuspage.me/StillOnline/Upty crowded | 2 — webhook.site/Svix Play saturated |
| Feasibility (stdlib, 1 sprint) | 5 — extends existing httpping fetch loop; percentiles + SQLite trivial | 4 — same stack, but incident workflow adds scope | 4 — capture endpoint easy, replay/forward adds scope |
| Value | 5 — silent slowdowns cause churn; devs lack cheap tool | 4 — trust/communication value, proven demand | 3 — dev convenience, low willingness to pay |
| Effort | 5 — smallest delta from existing repo | 3 — status page + subscribers + incidents | 4 — simple capture, but retention/privacy issues |
| **Weighted score** | **5.0** | 3.55 | 3.15 |

**Research reasoning:** Uptime monitoring is a $8.5B market growing ~9%/yr but dominated by UptimeRobot/Better Stack on uptime, leaving latency *drift* underserved; CI performance-gating literature (Gatling/Bencher) confirms demand but targets load-testers, not live endpoints. Status-page-for-indies has validated indie demand (StillOnline $9/$29, Upty) but is now crowded with near-identical entrants. Webhook tooling (webhook.site, Svix Play) is free/commodity with weak monetization. LatencyLedger reuses the repo's existing `fetch`+timing core, is the most differentiated, and has a clear paid wedge (CI gates + alert channels).

**Verdict:** Build LatencyLedger. Status-page features are retained as P1 inside it (not as standalone product) to capture that demand without competing head-on.
