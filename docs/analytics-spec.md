# LatencyLedger — Analytics Specification

**Product:** LatencyLedger (Continuous API latency regression tracking with CI gates)
**Stack constraints:** SQLite-only storage, first-party events only, no third-party analytics at launch. Python stdlib backend, static frontend, single-process + optional split worker.
**Scope:** This spec defines how LatencyLedger measures itself. It does not change product behavior in `docs/product-spec.md` — it instruments it.

---

## 1. Event Taxonomy & Principles

- **Naming:** `snake_case`, past-tense verbs for completed actions (`check_created`), present-tense nouns for views (`page_view`). Format: `{object}_{action}` (e.g. `check_added`, `alert_delivered`, `gate_evaluated`).
- **Event envelope (every event):** `event_id` (UUIDv4), `event_name`, `event_ts` (ms epoch, client-clock), `received_ts` (ms epoch, server), `user_id` (nullable, anonymous UUID before signup), `session_id`, `anonymous_id`, `source` (`web` | `api` | `worker` | `ci`), `properties` (JSON object, flat keys only), `sdk_version`, `app_version`.
- **Cardinality control:** All property values that are free-text (URLs, check names, error messages) are hashed or truncated before storage (see §8). High-cardinality fields are never event properties.
- **Absolute rule:** Never log PII in `properties` beyond `user_id` / `anonymous_id`. Email, password, API key, check URL, git SHA (beyond 7-char prefix), and raw IP are never stored in the raw event payload.

### 1.1 Event catalogue (38 events)

| # | Event | Trigger | Key properties | PII rule |
|---|---|---|---|---|
| 1 | `page_view` | Route change / initial load (client beacon) | `path`, `route_name`, `referrer`, `viewport` | Path normalized: check IDs → `:id`; no query strings stored |
| 2 | `signup_started` | Click on Sign up / register CTA | `entry_point` (`nav`/`landing`/`public_report`/`ci_docs`), `plan_intent` | No email stored |
| 3 | `signup_completed` | `POST /api/auth/register` → 201 | `method` (`email`), `time_to_signup_ms`, `plan` | `user_id` only; email never stored |
| 4 | `signup_failed` | Register → 4xx | `error_code` (`duplicate_email`/`validation`/`rate_limited`), `attempt` (1-based) | No email, no password |
| 5 | `login_started` | Submit login form | `method` (`email`) | No email |
| 6 | `login_completed` | `POST /api/auth/login` → 200 | `auth_type` (`session`/`oauth`), `session_age_days` | `user_id` only |
| 7 | `login_failed` | Login → 401/429 | `error_code` (`bad_credentials`/`locked`/`rate_limited`) | No email |
| 8 | `logout_completed` | `POST /api/auth/logout` | `session_duration_ms` | `user_id` only |
| 9 | `check_added` | `POST /api/checks` → 201 | `interval_sec`, `threshold_pct`, `plan`, `source` (`manual`/`api`/`import`) | URL stored as hashed `url_hash` + `url_host` only |
| 10 | `check_add_failed` | Check create → 4xx/402 | `error_code` (`validation`/`plan_limit`/`ssrf_blocked`), `plan` | No URL, no error detail verbatim |
| 11 | `check_edited` | `PATCH /api/checks/{id}` → 200 | `changed_fields` (array), `interval_sec` | Check ID only |
| 12 | `check_deleted` | `DELETE /api/checks/{id}` → 200 | `check_age_days`, `sample_count_bucket` | No URL |
| 13 | `check_duplicated` | Duplicate action | `source_check_age_days` | IDs only |
| 14 | `ping_now_run` | `POST /api/checks/{id}/ping-now` | `sample_count`, `error_count`, `p95_ms`, `status_code` | `check_id` only |
| 15 | `chart_viewed` | History chart rendered (≥2 points) | `range` (`24h`/`7d`/`30d`), `check_id` | Check ID only |
| 16 | `chart_range_changed` | User switches 24h/7d/30d | `from_range`, `to_range` | — |
| 17 | `sample_ingested` | Worker/CI sample written | `source` (`scheduler`/`ci`/`manual`), `status_code`, `ms_bucket` (`<100`/`100-400`/`400-1000`/`>1000`) | Sampled 1% (see §7) |
| 18 | `regression_alert_raised` | Detector fires (+20% rule) | `check_id`, `observed_p95`, `baseline_p95`, `pct_over`, `cooldown_active` | No URL |
| 19 | `alert_viewed` | Alert row expanded / chart opened from alert | `alert_id`, `kind` (`regression`/`down`), `age_hours_bucket` | `user_id` only |
| 20 | `alert_acknowledged` | User marks alert acked/useful | `alert_id`, `verdict` (`useful`/`false_positive`/`ignored`), `time_to_ack_ms` | — |
| 21 | `alert_delivered` | Email/webhook/chat send attempted | `channel` (`email`/`webhook`/`slack`/`discord`), `attempt`, `status_code` | No target address stored — `channel_id` hash only |
| 22 | `alert_delivery_failed` | Delivery after 3 attempts | `channel`, `error_class` (`timeout`/`auth`/`5xx`/`other`) | No target |
| 23 | `alert_channel_added` | `POST /api/checks/{id}/alert-channels` | `channel` | Target stored as opaque hash |
| 24 | `api_key_created` | `POST /api/keys` → 201 | `key_prefix` (first 6 chars), `plan` | Key value never stored |
| 25 | `api_key_revoked` | `DELETE /api/keys/{id}` | `key_age_days` | Prefix only |
| 26 | `gate_evaluated` | `POST /api/v1/checks/{id}/gate` | `passed` (bool), `budget_p95_ms`, `observed_p95_ms`, `source` (`github_actions`/`other_ci`/`manual`) | Check ID only |
| 27 | `gate_failed` | Gate → 422 | `observed_p95_ms`, `budget_p95_ms`, `overage_pct` | — |
| 28 | `public_report_toggled` | Toggle `is_public` | `now_public` (bool), `has_slug` | Slug hashed |
| 29 | `public_report_viewed` | Anonymous `GET /r/{slug}` | `referrer`, `range` | Anonymous session only |
| 30 | `export_requested` | `GET /api/checks/{id}/export` | `format` (`csv`/`json`), `range`, `row_count_bucket` | Check ID only |
| 31 | `project_created` / `project_deleted` | Projects CRUD (P1) | `check_count` | IDs only |
| 32 | `status_page_viewed` | `GET /s/{slug}` | `component_count` | Anonymous |
| 33 | `plan_upgraded` | Admin/manual toggle or Stripe (P1) | `from_plan`, `to_plan`, `source` (`admin`/`stripe`/`trial_expired`), `mrr_delta` | `user_id` only |
| 34 | `plan_downgraded` | Downgrade / cancel | `from_plan`, `to_plan`, `reason` | — |
| 35 | `onboarding_step_completed` | Wizard step done | `step` (`check_added`/`first_chart`/`alert_tested`/`ci_connected`) | `user_id` only |
| 36 | `experiment_assigned` | User enters experiment | `experiment_id`, `variant`, `assignment_hash` | `user_id` only |
| 37 | `experiment_exposed` | User sees treatment UI | `experiment_id`, `variant` | — |
| 38 | `feature_disabled` | Flag off / power user opts out | `feature`, `source` | — |

Sampled events (not 100%): `sample_ingested` (1%), `page_view` on `/r/{slug}` (100% — low volume, key funnel).

---

## 2. Pageview Tracking Design

### 2.1 Endpoint

```
POST /api/events
Content-Type: application/json
Authorization: session cookie OR x-api-key (for CI-attributed events)
Rate limit: 100 events/min per user, 1000/min per IP (anonymous)
```

Request body:

```json
{
  "events": [
    {
      "event_name": "page_view",
      "event_ts": 1731456000123,
      "properties": { "path": "/dashboard", "route_name": "dashboard" }
    }
  ],
  "anonymous_id": "a3f9c1e2-…"
}
```

Response: `202 Accepted, { "accepted": 1, "rejected": 0 }`. Validation failures are rejected per-event with the first error; the batch is never partially applied silently.

### 2.2 Client beacon

- Vanilla JS module `app/static/analytics.js` (~80 lines, no build step, no third-party). Loaded async on every page except `404`.
- Uses `navigator.sendBeacon` (fallback: `fetch` with `keepalive: true` on `pagehide`).
- Respects `DNT=1` / `Sec-GPC=1` → queues nothing, returns early (see §8).
- Anonymous ID: `crypto.randomUUID()` persisted in `localStorage` under `ll_anon_id`; merged into `user_id` on first login (`identity_merge` event, fired once).
- Route tagging: `data-route` attribute on `<body>`; SPA-less MPA so one beacon per page load + one per in-page range change (`chart_range_changed`).

### 2.3 Batching & buffering

- Client: max 20 events / batch, flush every 5 s, flush on `visibilitychange=hidden` and `pagehide`. Failed batch retried once, then dropped (no localStorage queue — leads are acceptable loss for product analytics).
- Server: validates against a per-event allowlist schema (unknown `event_name` → 400 with `unknown_event`; unknown properties → stripped, not an error). Ingest writes to `events` table in a single SQLite transaction per batch; `WAL` mode; no fsync per event.
- Schema:

```sql
CREATE TABLE IF NOT EXISTS events (
  event_id      TEXT PRIMARY KEY,
  event_name    TEXT NOT NULL,
  user_id       TEXT,
  anonymous_id  TEXT,
  session_id    TEXT,
  source        TEXT DEFAULT 'web',
  event_ts      INTEGER NOT NULL,   -- ms epoch, client
  received_ts   INTEGER NOT NULL,   -- ms epoch, server
  properties    TEXT NOT NULL DEFAULT '{}'  -- JSON, flat
);
CREATE INDEX idx_events_name_ts ON events(event_name, event_ts);
CREATE INDEX idx_events_user_ts ON events(user_id, event_ts);
CREATE INDEX idx_events_anon_ts ON events(anonymous_id, event_ts);
```

---

## 3. Funnel Definitions

Each funnel is a step table: step, event, optional filter, conversion window. Funnels are computed in SQL (see §5 for the admin dashboard versions).

### 3.1 Signup funnel

Goal: landing → activated account. Window: 7 days from first `page_view` on `/` or `/r/{slug}`.

| Step | Event | Filter | Notes |
|---|---|---|---|
| 1 | `page_view` | `path IN ('/', '/r/:slug', '/docs')` | Entry, anonymous OK |
| 2 | `signup_started` | `entry_point` in (above) | CTA click |
| 3 | `signup_completed` | `method='email'` | 201 from register |
| 4 | `check_added` | — | **Activation** — first value moment |
| 5 | `chart_viewed` | within 1 h of step 4 | Value proof |

Primary KPI: step 3 → 4 conversion (signup → first check within 24 h), target ≥40% per product-spec.

### 3.2 Activation funnel

Goal: prove time-to-first-value. Window: 24 h from `signup_completed`.

| Step | Event | Filter | Notes |
|---|---|---|---|
| 1 | `signup_completed` | — | Cohort anchor |
| 2 | `check_added` | — | median time-to-first-chart <5 min (step 3) |
| 3 | `chart_viewed` | `range='24h'` | First sparkline rendered |
| 4 | `ping_now_run` | optional | Manual validation |
| 5 | `regression_alert_raised` OR `alert_delivered` | within 7 d | North-star precursor: alert acted on = `alert_viewed` within 1 h |

North Star (product-spec §5): checks with a regression alert delivered that was acted on (`alert_viewed` within 1 h of `alert_delivered`).

### 3.3 Core-action funnel (CI gate adoption)

Goal: Pro conversion driver — gate evaluated in CI, not just dashboard curiosity. Window: 30 d from first `api_key_created`.

| Step | Event | Filter | Notes |
|---|---|---|---|
| 1 | `api_key_created` | — | CI intent |
| 2 | `gate_evaluated` | `source='github_actions'` | First CI run |
| 3 | `gate_evaluated` | `passed=false` (i.e. `gate_failed`) | Gate actually blocked something — value proof |
| 4 | `alert_acknowledged` | `verdict='useful'` | User confirms alert quality |
| 5 | `plan_upgraded` | `to_plan IN ('pro','team')` | Monetization |

Secondary core-action funnel (alert trust): `regression_alert_raised` → `alert_delivered` → `alert_viewed` → `alert_acknowledged(useful)`. Precision target ≥70%.

---

## 4. Cohort & Retention SQL Sketches (SQLite)

All sketches assume the `events` table from §2.3 and product tables from `architecture.md` (`users`, `checks`, `alerts`). Timestamps are ms epoch in `events`, text in product tables — convert with `strftime('%Y-%m-%d', event_ts/1000, 'unixepoch')`.

### 4.1 Weekly cohort retention (W0–W12)

A user is "retained" in week *n* if they fire `chart_viewed` (proxy for "weekly active check viewed", product-spec §5) or `check_added` in that week.

```sql
WITH cohort AS (
  SELECT user_id,
         strftime('%Y-%m-%d', MIN(event_ts)/1000, 'unixepoch', 'weekday 0', '-6 days') AS cohort_week_start
  FROM events
  WHERE event_name = 'signup_completed' AND user_id IS NOT NULL
  GROUP BY user_id
),
active AS (
  SELECT DISTINCT user_id,
         strftime('%Y-%m-%d', event_ts/1000, 'unixepoch', 'weekday 0', '-6 days') AS active_week_start
  FROM events
  WHERE event_name IN ('chart_viewed', 'check_added', 'gate_evaluated')
    AND user_id IS NOT NULL
)
SELECT c.cohort_week_start,
       COUNT(DISTINCT c.user_id) AS cohort_size,
       COUNT(DISTINCT CASE WHEN a.active_week_start = c.cohort_week_start THEN c.user_id END) AS w0,
       COUNT(DISTINCT CASE WHEN a.active_week_start = date(c.cohort_week_start, '+7 days')  THEN c.user_id END) AS w1,
       COUNT(DISTINCT CASE WHEN a.active_week_start = date(c.cohort_week_start, '+14 days') THEN c.user_id END) AS w2,
       COUNT(DISTINCT CASE WHEN a.active_week_start = date(c.cohort_week_start, '+28 days') THEN c.user_id END) AS w4
FROM cohort c
LEFT JOIN active a ON a.user_id = c.user_id
GROUP BY c.cohort_week_start
ORDER BY c.cohort_week_start;
```

W4 retention = `w4 * 100.0 / cohort_size`, target ≥25%.

### 4.2 Signup-cohort activation (first check within 24 h)

```sql
WITH signups AS (
  SELECT user_id, MIN(event_ts) AS signup_ts
  FROM events WHERE event_name = 'signup_completed' AND user_id IS NOT NULL
  GROUP BY user_id
),
first_check AS (
  SELECT user_id, MIN(event_ts) AS check_ts
  FROM events WHERE event_name = 'check_added' AND user_id IS NOT NULL
  GROUP BY user_id
)
SELECT strftime('%Y-%W', s.signup_ts/1000, 'unixepoch') AS signup_week,
       COUNT(*)                                            AS signups,
       SUM(CASE WHEN f.check_ts IS NOT NULL
                 AND f.check_ts - s.signup_ts <= 24*3600*1000 THEN 1 ELSE 0 END) AS activated_24h,
       ROUND(100.0 * SUM(CASE WHEN f.check_ts IS NOT NULL
                              AND f.check_ts - s.signup_ts <= 24*3600*1000 THEN 1 ELSE 0 END)
             / COUNT(*), 1) AS activation_pct
FROM signups s LEFT JOIN first_check f ON f.user_id = s.user_id
GROUP BY signup_week ORDER BY signup_week;
```

### 4.3 Alert precision (30 d rolling)

```sql
SELECT date(e.event_ts/1000, 'unixepoch') AS day,
       SUM(e.event_name = 'alert_acknowledged'
           AND json_extract(e.properties, '$.verdict') = 'useful')          AS useful,
       SUM(e.event_name = 'alert_acknowledged'
           AND json_extract(e.properties, '$.verdict') = 'false_positive')   AS false_positive,
       ROUND(100.0 * SUM(json_extract(e.properties,'$.verdict')='useful')
             / NULLIF(SUM(e.event_name='alert_acknowledged'), 0), 1) AS precision_pct
FROM events e
WHERE e.event_name IN ('alert_acknowledged')
  AND e.event_ts >= (strftime('%s','now') - 30*86400) * 1000
GROUP BY day ORDER BY day;
```

---

## 5. Admin Analytics Dashboards

Served at `/admin/analytics` (session cookie, `is_admin=1` only — add the flag to `users` in the admin migration). Static HTML + canvas, no build step. Five dashboards, all SQLite queries server-side, response cached 60 s in-memory.

| # | Dashboard | Chart | Key queries (sketch) |
|---|---|---|---|
| D1 | Growth | Line: signups/day + activated/day (7 d EMA) | §4.2 grouped by day; `signup_completed` vs `check_added` |
| D2 | Funnels | Horizontal bar: signup / activation / CI-gate step conversion | Step counts via `COUNT(DISTINCT user_id)` per event pair with 7 d window |
| D3 | Retention | Cohort heatmap table (cohort_week × W0–W12) | §4.1 matrix rendered as table |
| D4 | Alert quality | Bar: alerts raised/delivered/viewed/acked per day; precision % line | `regression_alert_raised`, `alert_delivered`, `alert_viewed`, `alert_acknowledged`; §4.3 |
| D5 | Revenue & CI | Stacked bar: plan mix; line: `gate_evaluated` pass/fail per day | `users.plan` counts; `gate_evaluated` by `json_extract(properties,'$.passed')` |

Data access pattern: each dashboard is one `GET /api/admin/analytics/{dashboard}` handler that runs the query and returns JSON. No full-table scans past 90 d without an index hit (`idx_events_name_ts` covers all dashboard queries).

---

## 6. A/B Experimentation Framework

Lightweight, SQLite-backed, no third-party flag service.

**Assignment:** deterministic hash of `user_id` (fallback `anonymous_id`) + `experiment_id` → bucket 0–99. `bucket < treatment_pct` → treatment. Stored once in:

```sql
CREATE TABLE IF NOT EXISTS experiment_assignments (
  experiment_id TEXT NOT NULL,
  user_id       TEXT NOT NULL,
  variant       TEXT NOT NULL,          -- 'control' | 'treatment'
  assigned_ts   INTEGER NOT NULL,
  PRIMARY KEY (experiment_id, user_id)
);
```

**Lifecycle:** `experiment_assigned` (at first exposure) and `experiment_exposed` (when treatment UI actually renders) are separate events — analysis uses *exposed* as the denominator to avoid dilution. Experiment config lives in code (`app/experiments.py`: name, description, variants, `treatment_pct`, primary metric event, min sample, start/end dates), not in a remote service, so config is reviewable in git.

**Guardrails:**
- One active experiment per surface (landing, dashboard, check-create) to avoid interaction effects.
- Minimum sample per variant: max(100 signups, 2 weeks) before reading results; no peeking — decisions only at the pre-registered end date.
- Primary metric per experiment is declared in config before launch (e.g. `signup_started → signup_completed` rate). Secondary metrics are reported but not used for ship/no-ship.
- Rollback: flipping `treatment_pct` to 0 in code + redeploy; assignments already stored stay for post-hoc analysis.

**Analysis (SQLite):** compare primary-metric rate by variant, with a simple z-test computed in Python over the two proportions (no stats library needed). Report confidence interval; ship only if CI excludes 0 and effect ≥ pre-declared `min_effect`.

---

## 7. Data Governance

### 7.1 Naming & versioning

- Events are immutable once shipped. New semantics = new event name (`alert_sent` → `alert_delivered_v2` if payload meaning changes; preferred: new name, deprecate old).
- Property names are `snake_case`; units are in the name (`_ms`, `_sec`, `_pct`, `_count`). Boolean properties use `is_`/`has_` prefix and real JSON booleans.
- Every event in §1.1 has an owner (the engineer who shipped the trigger) recorded in a `docs/analytics-events.md` registry generated from the client/server allowlist.

### 7.2 Deprecation

1. Mark deprecated in the registry with a `deprecated_since` date.
2. Stop emitting (code removal in the same release that adds the replacement).
3. Keep querying for 90 d for backfill/comparison, then drop from dashboards.
4. Deprecation PR must link the replacement event and migration note.

### 7.3 Quality checks (run nightly in-process, logged)

| Check | SQL / rule | Fail action |
|---|---|---|
| Unknown event names | `SELECT event_name, COUNT(*) FROM events WHERE event_name NOT IN (<allowlist>) GROUP BY 1` | Alert admin (email), investigate within 24 h |
| Volume anomaly | Daily count per event vs 7 d median; flag if ±50% | Non-blocking: log + dashboard badge |
| Schema drift | New property keys not in allowlist for that event | Stripped at ingest; count reported daily |
| Late events | `received_ts - event_ts > 24h` | Counted; >1% triggers ingest bug investigation |
| PII leak scan | Regex over `properties` for email / `ll_` key / `sk_` patterns | Quarantine batch, page admin immediately |
| Broken identity | `user_id IS NULL AND` event is post-signup (e.g. `check_added`) | Flag; indicates cookie merge failure |

Quality results render on D1 of the admin dashboard as a status row (green/red per check).

---

## 8. Privacy-Preserving Defaults

These are defaults, not options. Self-hosters get the same behavior with no config.

| Concern | Default | Mechanism |
|---|---|---|
| IP address | **Never stored.** Not in `events`, not in product tables. Rate limiting uses an in-memory token bucket keyed by a salted hash of IP, discarded after 5 min. | `hashlib.sha256((ip + daily_salt).encode()).hexdigest()[:16]`; daily salt rotated, never persisted |
| Do Not Track / GPC | `DNT: 1` or `Sec-GPC: 1` → client sends nothing; server returns 204 for any beacon from that header | Early return in `analytics.js` and in `POST /api/events` handler |
| Fingerprinting | No canvas/WebGL/font fingerprinting, no UA parsing beyond coarse `browser_family` + `os_family` buckets | Only `navigator.userAgent` substring match for 2 coarse fields |
| URL / check-name PII | `url_host` only (e.g. `api.example.com`); full URL hashed with SHA-256 for dedup, never stored raw in events | `url_hash` property; raw URL stays in product DB under normal auth |
| Git SHA | 7-char prefix only, stored as `git_sha_prefix` | Truncated at emit time |
| Email | Never in `properties`; `user_id` is the join key | Ingest allowlist rejects `email`/`target`/`url` keys |
| Retention | Raw events kept 12 months, then aggregated to daily rollups and raw deleted. Product samples keep plan-based history (Free 7 d / Pro 90 d / Team 1 yr) per product-spec. | Nightly retention job (`app/retention.py`), idempotent, logged |
| Third parties | **None at launch.** No Google Analytics, Mixpanel, Segment, PostHog, Sentry, or CDN scripts on tracked pages. Charts are hand-rolled canvas. | `analytics.js` is the only script; CSP blocks inline third-party origins |
| Consent | Logged-in users: account creation implies product analytics (disclosed in Privacy page). Anonymous public-report viewers: beacon only fires if DNT/GPC is absent and is limited to `public_report_viewed` + `page_view`. | Privacy page at `/privacy` describes this in plain language |
| Self-hosting | `ANALYTICS_DISABLED=1` env var disables all beaconing and ingest; admin dashboard still shows product-table metrics | Checked at boot; client receives a `data-analytics="off"` flag and sends nothing |

---

## 9. Weekly Metrics Report Template

Generated Monday 09:00 (in-process cron thread) and emailed to admins + posted to `/admin/analytics/weekly`. Plain-text/markdown; numbers pulled from the §4 queries over the trailing 7 d vs prior 7 d.

```markdown
# LatencyLedger — Weekly Metrics (2026-11-02 → 2026-11-08)

## North Star
- Alerts acted on (delivered → viewed ≤1h): 42 (+18% WoW)

## Growth
- Signups: 128 (+12%)   |  Activation (first check ≤24h): 51 (39.8%, target ≥40%)
- Median time-to-first-chart: 3m 41s

## Retention
- W4 retention (4-week-old cohort): 27% (target ≥25%)
- DAU (chart_viewed): 96 | WAU: 402

## Alert quality
- Raised: 58 | Delivered: 55 (94.8%) | Viewed: 41 | Acked useful: 31
- Precision: 77% (target ≥70%) | False-positive rate: 9%

## CI gate
- Evaluated: 214 (pass 168 / fail 46) | Fail rate: 21.5%
- GitHub Actions share: 81%

## Revenue
- Free: 1,240 | Pro: 38 (+3) | Team: 5 (+0) | MRR: $342
- Free→paid conversion: 3.4% (target ≥3%)

## Data quality
- Unknown events: 0 | PII scans: clean | Late events: 0.3%
- Ingest p95: 180ms | Scheduler uptime: 99.97%

## Experiments
- exp/latency-budget-preset: treatment +6.2pp on signup (CI [-1.1, +13.5]) — inconclusive, continue

## Notes
- <free-text: ships, incidents, decisions>
```

Column formatting: `Δ%` vs prior week in parentheses; every KPI from product-spec §5 appears at least once. Missed targets are flagged with `⚠` and a one-line owner note.

---

## Appendix: Implementation Order

1. `POST /api/events` + `events` table + allowlist validation (§2).
2. `analytics.js` client beacon + DNT handling (§2.2, §8).
3. Client- and server-side emission for the 38 events in §1.1 (server-side first for product events; client only for `page_view`/`signup_started`/`chart_*`).
4. Admin dashboards D1–D5 (§5) + nightly quality checks (§7.3).
5. Experiment framework (§6) — only when first experiment is planned.
6. Weekly report generator (§9).
