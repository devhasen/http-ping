# LatencyLedger — Support Specification

> **Scope:** Customer support for LatencyLedger (latency regression tracking + CI gates) at public launch (Milestone M2). **Sprint 1 scope is this document only — spec, no implementation.**
> **Hard constraint:** No paid support SaaS (no Zendesk / Intercom / Freshdesk / Help Scout). Everything below is implementable with the existing stack: Python 3.11 **stdlib only** (`sqlite3`, `smtplib`, `http.server`), SQLite (WAL), static HTML/CSS/JS, no build step, no CDN. Every channel, table, and endpoint in this spec reuses `app/db.py`, `app/router.py`, `app/alerts.py` (SMTP/webhook), and `app/auth.py` (session + admin check).
> **Companion docs:** `docs/product-spec.md` (features, plans, metrics), `docs/architecture.md` (schema, API, security), `docs/roadmap.md` (P0/P1/P2), `docs/design-system.md` (quiet-until-it-matters, status color + icon + label).

---

## 1. Support Channels at Launch: Email-Only + In-App Feedback Form (DB-Backed Admin Inbox)

### 1.1 Channel decision

| Channel | Launch? | Rationale |
|---|---|---|
| **Email** (`support@latencyledger.example` — replace with real domain at launch; alias to founder/lead inbox) | ✅ Primary | Zero new infra: reuse `smtplib` in `app/alerts.py`. Works for self-hosters who will never log into hosted UI. |
| **In-app feedback form** | ✅ Primary | DB-backed, no third party. Captures authenticated context (user id, plan, check id) automatically — the fastest path to a reproducible ticket. |
| **Knowledge base / docs in-app** (`/help`) | ✅ Deflection (§10) | Static pages + SQLite search; no SaaS docs platform. |
| **Public status page** (`/status`) | ✅ Trust channel (§8) | Self-hosted endpoint; doubles as the answer to "is it us or you?" |
| Live chat / chat widget | ❌ Deferred | Requires a persistent session + polling infra + staffing promise we cannot keep at M1/M2. Revisit only if ticket volume > 30/week sustained. |
| Phone / Slack community / Discord | ❌ Deferred | No headcount. Public GitHub Issues remains the de-facto community channel for self-hosters (link it, don't staff it as SLA). |
| Paid support SaaS (Zendesk etc.) | ❌ Forbidden by constraint | Replaced in full by §1.3 admin inbox. |

**Staffing assumption (launch):** 1 support lead (author of this spec), founder as escalation. Business-hours response per §5 SLA; no 24/7 promise at M1/M2. Self-hosted (community) users get best-effort support via email/GitHub Issues, explicitly *not* under SLA (see §1.4).

### 1.2 Email channel — how it works

```
User ──email──▶ support@latencyledger.example (mailbox / alias)
                    │
                    ▼  (manual triage in Sprint 1; ingest script in P1)
             Admin inbox (/admin/support) — ticket created by hand or by ingest
                    │
                    ▼  reply via same SMTP config as alerts (alerts.py)
             User ◀──email── support@latencyledger.example
```

- **Inbound:** Sprint 1 — support lead triages the mailbox manually and creates a ticket in the admin inbox (§1.3) with `source='email'`, pasting the sender address into the ticket's `contact_email`. P1 — add `scripts/ingest_support_email.py` (IMAP poll every 5 min, stdlib `imaplib`) that parses subject/body into `support_tickets` and threads replies by `Ticket #LL-####` in the subject line. No new dependency.
- **Outbound:** All replies sent through the existing SMTP path (`app/alerts.py`, env `SMTP_HOST/PORT/USER/PASS/FROM`). If SMTP is not configured (self-host default), the admin inbox shows the reply as a ready-to-copy draft and logs the ticket as "answered off-system" — support must still work for a no-SMTP deploy.
- **Auto-reply (in-app, no SaaS):** On ticket creation, send one acknowledgement email (template = Macro #1, §2) with ticket reference + expected first-response time from §5. If SMTP absent, acknowledgement is skipped and the in-app form shows the reference inline instead. Auto-reply must **never** be sent more than once per ticket (flag `ack_sent_at`).
- **Address hygiene:** `support@` for tickets, `noreply@` for alerts/system mail (never mixed — users must be able to filter alerts; alerts already go from the configured `SMTP_FROM`). Bounce handling: log bounces to the ticket timeline; if the contact address bounces, mark ticket `contact_bounced=1` and stop auto-mail.

### 1.3 In-app feedback form + DB-backed admin inbox (the Zendesk replacement)

#### User-facing form

- Location: header link **Help** → `/help/feedback`, and a "Send feedback" button on the dashboard footer. Also reachable unauthenticated at `/help/feedback` (for signup-blocked users) — unauthenticated submissions require a contact email, authenticated ones prefill it.
- Fields (mirrors `docs/design-system.md` a11y: labels, ≥40px targets, keyboard reachable, focus-visible):

| Field | Type | Required | Notes |
|---|---|---|---|
| Category | select | ✅ | `Bug`, `Question`, `Feature request`, `Billing`, `Abuse/security`, `Other` |
| Subject | text (≤120 chars) | ✅ | Becomes ticket title |
| Message | textarea (≤8000 chars) | ✅ | Plain text; escaped on render |
| Check (optional) | select of user's checks | — | Sends `check_id` so the agent sees URL, interval, stats without asking |
| Attach context | checkbox, default on | — | Attaches plan, app version, last 5 samples' aggregate (no payload bodies) |
| Contact email | email | if logged out | Prefilled if logged in |
| Severity (self-rated) | select | — | `Blocking / Degraded / Minor / Just a question` — agent re-grades per §5 |

- Client validation + server validation (lengths, category allowlist). Rate limit: 5 submissions/hour/IP (reuse the token-bucket approach from `architecture.md` Security) to prevent spam/abuse of the inbox.
- On submit: `POST /api/support/tickets` → `201 {id, ref: "LL-####", status:"open"}`; confirmation screen shows the reference, expected first-response window, and a link to `/help` (deflection — user may find the answer while waiting).

#### Data model (SQLite additions — same migration style as `architecture.md`)

```sql
support_tickets(
  id TEXT PK,                 -- LL- + zero-padded sequence, e.g. LL-0042
  user_id INT NULL FK users,  -- NULL for logged-out / email-only
  contact_email TEXT,
  source TEXT,                -- 'inapp' | 'email' | 'admin'
  category TEXT, severity TEXT, status TEXT,   -- status per §5 lifecycle
  subject TEXT, body TEXT,
  check_id TEXT NULL FK checks,
  plan TEXT,                  -- snapshot of user's plan at submission
  app_version TEXT,           -- from /healthz version field
  assignee TEXT NULL,         -- support lead username
  ack_sent_at TEXT NULL, first_response_at TEXT NULL, resolved_at TEXT NULL,
  csat_stars INT NULL,        -- filled by §7 survey
  created_at TEXT, updated_at TEXT
);
support_replies(
  id INTEGER PK, ticket_id TEXT FK, author TEXT,  -- 'agent' | 'user' | 'system'
  body TEXT, sent_via TEXT,   -- 'email' | 'inapp' | 'note' (internal note)
  created_at TEXT
);
feedback_votes(               -- §6 roadmap loop
  id INTEGER PK, user_id INT NULL, ticket_id TEXT FK NULL,
  topic TEXT, kind TEXT,      -- 'feature' | 'bug' | 'praise'
  created_at TEXT
);
surveys(                      -- §7 NPS/CSAT
  id INTEGER PK, user_id INT NULL, kind TEXT,  -- 'nps' | 'csat'
  score INT, context TEXT, shown_at TEXT, answered_at TEXT NULL
);
```

Indexes: `support_tickets(status, created_at)`, `support_tickets(user_id)`, `support_replies(ticket_id, created_at)`. All SQL parameterized (per `architecture.md`).

#### Admin inbox (the support console)

- URL: `/admin/support` — gated by an admin flag, **not** a new auth system: reuse session auth (`app/auth.py`) + an `is_admin` column/flag on `users` (or env `ADMIN_EMAILS` allowlist — prefer env allowlist for Sprint 1, zero migration for roles; full teams/roles are P2 per product spec). Non-admin → 403.
- List view: queue filtered by `status` (Open / Pending / Resolved / Closed), sorted by severity then age. Each row: ref, subject, category, severity, age, plan, source. Design-system: status dot + text label, never color alone.
- Detail view: original message, check context (link to the user's check detail if the agent has access — for hosted users yes; for self-hosters, context comes only from the submitted snapshot), reply composer (send via SMTP or save-as-note), internal-notes tab (`sent_via='note'`, never emailed), lifecycle actions (§5: assign, change severity, resolve, close, reopen), and the §7 CSAT prompt trigger on resolve.
- No JS framework: server-rendered HTML + vanilla JS, same pattern as the rest of the app. Works offline/self-hosted.

### 1.4 What support does *not* cover

- **SLA does not apply to self-hosted/community installs** (free, "yes (community)" in product spec pricing). Best-effort email/GitHub Issues; the docs and `/status` self-diagnosis path are the contract.
- **No data-recovery promise** beyond SQLite backup guidance (see Troubleshooting §4.12). We never ask for passwords, API keys, or session cookies — if a "support" email asks, it's phishing (Macro #9).
- **GDPR/privacy:** ticket bodies are stored in the same SQLite DB as user data, retained 12 months after close, exportable/deletable on request via the admin inbox (delete = hard-delete row + replies, logged in a `support_audit` note). Self-hosters own their copy.

---

## 2. Support Macros — 10 Canned Responses

Macros are stored as plain-text templates in a `support_macros` table (`id, name, subject_template, body_template, category`) seeded at migration — editable by the admin inbox without a deploy, no SaaS. Placeholders: `{name}`, `{ref}`, `{check_name}`, `{url}`, `{p95}`, `{baseline}`, `{plan}`, `{sla_window}`. Always plain-language, always end with the single next step. Tone follows design-system: evidence first, quiet until it matters.

**Macro 1 — Ticket acknowledgement (auto-sent on creation)**
> Subject: Your LatencyLedger ticket {ref} is in the queue
>
> Hi {name},
>
> Thanks for writing — your ticket is **{ref}** (category: {category}). We've logged it and a human will reply within {sla_window} (see the severity/SLA table in Help).
>
> While you wait, these solve most cases in under 2 minutes: [link to /help troubleshooting]. If your issue is "is LatencyLedger down?", check /status first.
>
> No need to reply to this email — just reply in the app or to this thread with anything to add.
>
> — LatencyLedger Support

**Macro 2 — Regression alert explained ("why did I get this alert?")**
> Subject: Why {check_name} triggered a regression alert
>
> Hi {name},
>
> Your alert fired because {check_name}'s p95 rose more than 20% above its rolling 7-day baseline (50+ samples required). At alert time: p95 was **{p95}** vs a baseline of **{baseline}** — the endpoint is slower, not necessarily down.
>
> To check: open the check, look at the 24h chart, and look for the commit marker (SHA) just before the rise — that's your prime suspect (see "Commit annotation" in Help).
>
> If this is a false positive, you can raise the threshold on the check (Settings → alert threshold) or mute it for 6h after the next alert. Full tuning guide: [link].
>
> — LatencyLedger Support

**Macro 3 — Cannot reproduce / need more info (asking for the one thing that matters)**
> Subject: Re: {ref} — one detail will let me reproduce this
>
> Hi {name},
>
> Thanks for the report. I couldn't reproduce it yet, and one detail will change that: **{specific_ask}** (e.g. "the check URL + interval, or a screenshot of the chart with the time range").
>
> Please don't send API keys or passwords — the check URL, its interval, and the time range are enough. Reply to this thread or in the app and I'll pick it up immediately.
>
> — LatencyLedger Support

**Macro 4 — Bug confirmed, fix scheduled**
> Subject: {ref} confirmed — fix is scheduled
>
> Hi {name},
>
> Good news: I reproduced {ref} and it's a bug on our side, not your setup. The fix is scheduled for the next release (target: {release_window}); your check data is not affected.
>
> I'll update this ticket the moment the fix ships and you can re-verify with "Ping now". No action needed from you.
>
> — LatencyLedger Support

**Macro 5 — Bug fixed, please re-verify**
> Subject: {ref} is fixed in {version} — please re-verify
>
> Hi {name},
>
> The fix for {ref} shipped in version **{version}**. Could you re-run the steps from your original report (or click "Ping now" on {check_name}) and confirm it's gone? Just reply "fixed" or reopen the ticket if it persists.
>
> Thanks for the sharp report — this one helped other users too.
>
> — LatencyLedger Support

**Macro 6 — Works as designed (expected behavior, with the knob)**
> Subject: Re: {ref} — this is expected, here's the control
>
> Hi {name},
>
> That behavior is by design: {explain_the_behavior_in_one_sentence}. It exists because {reason}.
>
> The knob for it is {setting_path} — {what changing it does}. If you'd like it changed as a default for everyone, reply "feature request" and I'll file it to the roadmap loop (Help → Feedback).
>
> — LatencyLedger Support

**Macro 7 — Feature request received (roadmap loop entry)**
> Subject: Re: {ref} — request logged for the roadmap
>
> Hi {name},
>
> Logged! Your request ({one_line_summary}) is now in our feedback queue and counted toward roadmap prioritization (we rank by how many users ask and how much it unblocks). There's no date I can promise today.
>
> If it helps, the closest workaround right now is {workaround_or_none}. I'll update this ticket when it ships or when the roadmap decision changes. Thanks for shaping the product.
>
> — LatencyLedger Support

**Macro 8 — Plan limit hit (402 / upgrade path)**
> Subject: Re: {ref} — your {plan} plan limit
>
> Hi {name},
>
> You've hit your {plan} plan limit ({limit_detail}, e.g. "3 checks on Free"). Your existing checks keep running — we never delete or pause data for hitting a limit — but new checks are blocked until you upgrade or remove one.
>
> Upgrade is at Settings → Billing ({upgrade_link}); self-hosting is free and unlimited on your own box. Dropping a check you no longer need also frees the slot instantly.
>
> — LatencyLedger Support

**Macro 9 — Security / phishing warning ("we will never ask for…")**
> Subject: Security: LatencyLedger will never ask for your password or API key
>
> Hi {name},
>
> If anyone claiming to be LatencyLedger support asks for your password, API key (`ll_…`), or session cookie — it's not us. We can fix almost everything from the check URL, interval, and time range alone.
>
> If you received such a request, forward it to support@latencyledger.example, revoke any key you shared (Settings → API keys → Revoke, takes effect immediately), and change your password. If you're unsure whether an email is really from us, check that it came from our domain and that any link it contains points to latencyledger.example.
>
> — LatencyLedger Support

**Macro 10 — Resolution / closing (with CSAT trigger)**
> Subject: {ref} resolved — let us know if it's really gone
>
> Hi {name},
>
> Closing this as resolved: {one_line_resolution}. If the problem comes back, reply and it reopens at the same severity — no need to re-explain.
>
> Quick favor: how did we do? [1–5 stars link, one tap, no login] — it takes 5 seconds and genuinely sets our support priorities.
>
> — LatencyLedger Support

---

## 3. FAQ — 15 Q&A (grounded in `docs/product-spec.md` features)

1. **What is LatencyLedger?** Continuous API latency regression tracking with CI gates. It watches your endpoints' p50/p95/p99, learns a rolling baseline, and alerts when p95 rises >20% — even while the API still returns "200 OK" — so you know your API got slower before your users do.
2. **How is this different from an uptime monitor (UptimeRobot, Better Stack)?** Uptime tools alert on downtime. LatencyLedger's first-class alert is *latency drift vs baseline*, plus a CI gate that can fail a PR on a latency budget. Your endpoint can be "up" and still regressing — that's the gap we close.
3. **What do I need to create my first check?** A public `https://` URL and 60 seconds. Paste it, pick an interval (1m/5m/15m/1h), and you get min/max/avg/p50/p95/p99 plus a history sparkline. No agent, no instrumentation, no code changes.
4. **What does "Ping now" do?** Fires N=10 requests at the URL immediately and shows each `{ms, status}` sorted, with p50/p95/p99/min/max/avg computed server-side. Error requests are counted separately, not crashed. Use it to verify a fix without waiting for the scheduler.
5. **How does the regression alert work, exactly?** On every ingest, the detector compares recent p95 to the rolling 7-day baseline (needs ≥50 samples before it can fire). Alert fires once, then cools down for 6 hours per check. Threshold is per-check and tunable (default 20%).
6. **Why did I get an alert when my API is still returning 200?** Because the alert is about *slowness*, not downtime. A p95 rise of >20% over baseline with all-200 responses is exactly the silent regression uptime tools miss. Check the chart for the commit (SHA) marker before the rise.
7. **What is the CI gate and how do I use it?** `POST /api/v1/checks/{id}/gate` with a budget like `{p95_ms: 400}`. Returns `200 {pass:true}` under budget or `422 {pass:false, observed_p95}` over. The repo ships a GitHub Actions example YAML — one step, API key in secrets, PR blocked if p95 is over budget.
8. **What is an API key, and is it safe?** A key starting `ll_` generated in Settings, shown **once** at creation (only its hash is stored). It authenticates `/api/v1/*` without a session. Revoking takes effect immediately. Never paste it into chat/support tickets.
9. **What is a public report link?** Toggle a check public to get `/r/{slug}` — a read-only page with chart + stats, no login, no API keys or settings leaked. Toggle it off and the link returns 404 immediately. Use it for postmortems and PR comments.
10. **Can I see which commit made my API slower?** Yes (P1). Tag samples with a git SHA via `POST /api/v1/checks/{id}/samples {sha, note}` (or the CI example). The chart marks the SHA, and regression alerts include the last SHA before the drift — your prime suspect.
11. **What are the plans and limits?** Free: 3 checks, 5-min minimum interval, 7-day history, 1 alert channel. Pro $9/mo: 25 checks, 1-min interval, 90-day history, email + webhook + chat alerts. Team $29/mo: 100 checks, multi-region, 1-year history, status pages. Flat pricing — no per-seat, no per-incident fees. Hitting a limit never deletes data (Macro #8).
12. **Can I self-host?** Yes — one Docker command (`docker compose up`, port 8000), SQLite on a volume, no external API keys needed to boot. SMTP is optional (alerts are silently email-disabled without it). Self-host is free/community; hosted Pro is for those who don't want to run the box.
13. **Do you support Slack/Discord/webhook alerts?** Webhooks + email in P0; Slack/Discord incoming-webhook channels in P1 (test-send button, delivery logged, exponential backoff, 3 attempts). A failing webhook never blocks ingest.
14. **How accurate are the latency numbers?** We measure real HTTP request timing from the checker (10s timeout, redirects not followed by default). Single-region in P0 — treat absolute ms as "our vantage point," and use *relative change vs baseline* for decisions. Multi-region comparison is P2.
15. **How do I contact support, and how fast will I hear back?** Email `support@…` or the in-app feedback form (Help → Send feedback). First-response targets by severity are in §5 (e.g. blocking = within 1 business day). Check `/status` first for platform incidents, and the Knowledge Base (`/help`) — most answers are already there.

---

## 4. Troubleshooting Guides (per feature)

Format per guide: **Symptoms → Likely causes (ordered) → Fix → Escalate when**. All checks assume hosted (M2) unless marked self-host.

### 4.1 Sign up / login / sessions
- **Symptoms:** `409` on register; login loops; "session expired" immediately.
- **Causes/fixes:** `409` = email already registered → use password reset or log in. Login loop = cookie blocked (private mode, third-party cookie settings) or `SameSite` conflict behind a proxy → allow cookies for the domain. Instant expiry = server clock skew or DB not persisting sessions (self-host: check `/data` volume is writable).
- **Escalate when:** valid credentials rejected repeatedly with 401 → S3 (§5); never ask the user for their password (Macro #9).

### 4.2 Adding a check / URL validation
- **Symptoms:** "invalid URL" on a URL that looks fine; check saved but never pings.
- **Causes/fixes:** Non-`http(s)` scheme, >2048 chars → rejected by design. A URL that only resolves on your LAN / VPN → our checker can't reach it (SSRF guard blocks private IPs) → host it publicly or self-host. Saved-but-silent → scheduler not running (see §4.3).
- **Escalate when:** a public `https://` URL is rejected → S3, include the URL verbatim.

### 4.3 Scheduler not sampling / stale last_checked_at
- **Symptoms:** chart flatlines; `last_checked_at` frozen; "Ping now" works but nothing scheduled.
- **Causes/fixes (hosted):** Check `/healthz` (scheduler heartbeat); if the heartbeat is stale it's a platform incident → check `/status` and file S2. **(Self-host)** `RUN_SCHEDULER=0` means web-only by design → set `RUN_SCHEDULER=1` or run a separate worker container. SQLite locked/contended → check disk + WAL; restart the container (ingest is idempotent).
- **Escalate when:** heartbeat stale on hosted >10 min → S2, link the user to the status-page entry.

### 4.4 Stats look wrong (p50/p95/p99, baseline)
- **Symptoms:** "p95 doesn't match my APM"; baseline seems too high/low; sudden jump in stats with no real slowdown.
- **Causes/fixes:** Different vantage point (single region, network path) — compare *change*, not absolute ms vs APM. Baseline needs ≥50 samples / 7 days rolling — new checks have no baseline yet (alerts can't fire, by design). A few huge outliers (cold starts) inflate p95 → look at the per-request "Ping now" list; consider raising the threshold.
- **Escalate when:** percentiles are mathematically inconsistent (p50 > p95) on the same series → S2 (data bug, Macro #4).

### 4.5 Regression alerts: no alert / too many alerts
- **Symptoms:** Expected alert never fired; alert storm; alert for a deploy that was fine.
- **Causes/fixes:** No alert → check sample count (<50 = detector asleep), cooldown active (6h), threshold set > actual rise, or the check was <7 days old. Too many → threshold too tight for a noisy endpoint → raise to 30–40% or accept the drift (Macro #6). Alert for a known deploy → annotate the SHA so the next baseline learns it; adjust per-check threshold.
- **Escalate when:** p95 rose >50% for >7 days with zero alerts → S3 detector bug; include check id + time range.

### 4.6 Email alerts not arriving
- **Symptoms:** Alerts in the UI log (or expected) but no inbox mail.
- **Causes/fixes:** (Self-host) SMTP env vars unset → email disabled by design; set `SMTP_HOST/PORT/USER/PASS/FROM` and restart. Spam folder / SPF-DKIM on the sending domain. Per-check alert channel points to a stale address → fix in Settings → Alert channels, use test-send. Rate limits from the mailbox provider.
- **Escalate when:** test-send fails with a 5xx from our SMTP relay on hosted → S3; include the delivery-log status code (admin inbox shows it).

### 4.7 Webhook / Slack / Discord alerts failing
- **Symptoms:** Delivery log shows non-2xx; retries exhausted.
- **Causes/fixes:** Incoming-webhook URL revoked/rotated in Slack/Discord → re-add the channel, hit test-send. Non-HTTPS or private-IP target → blocked. Payload rejected (Slack needs `{"text": …}`) → re-create the channel (don't hand-edit). Remember: a failing webhook never blocks ingest — your data is safe.
- **Escalate when:** test-send succeeds but real deliveries 422 → S3, include the delivery response body.

### 4.8 API keys: 401s, lost key, CI can't authenticate
- **Symptoms:** `/api/v1/*` returns 401; "I lost my key"; gate works manually but not in CI.
- **Causes/fixes:** Key revoked (check Settings → API keys list, revoke is instant). Key copied with trailing whitespace / wrong env var in CI secrets. Using the session cookie path against `/api/v1/*` (keys only) or vice versa. Lost key = generate a new one (old one can't be recovered — only the hash is stored) and revoke the old.
- **Escalate when:** a freshly generated, never-revoked key 401s → S3 (auth bug); never ask for the full key (Macro #9).

### 4.9 CI gate: always failing / always passing / 422 confusion
- **Symptoms:** PR blocked despite fast API; gate passes during a real regression; `422` in CI logs.
- **Causes/fixes:** Budget too tight for the endpoint's real p95 → measure first (`GET /api/checks/{id}/stats`), set budget with headroom (e.g. real p95 + 20%). Gate sampling a cold/stale baseline → run "Ping now" or wait a full interval before gating. `422` is *expected* on failure — it's `{pass:false, observed_p95}`; the GitHub Actions example treats non-200 as fail. Gate endpoint needs an API key, not a session.
- **Escalate when:** `observed_p95` in the gate response contradicts the chart for the same window → S2.

### 4.10 Public report links: 404, stale, or leaking
- **Symptoms:** Shared `/r/{slug}` 404s; report shows old data; user worried a link leaks settings.
- **Causes/fixes:** 404 = toggle was switched off (by design — instant revoke) or slug mistyped. Stale = scheduler gap (§4.3). Leak concern: reassure — the public page renders chart + stats only; no API keys, email, or settings are in the response (verify in View Source). If a slug was shared publicly and the user wants it burned, toggle off/on to mint a new slug.
- **Escalate when:** a toggled-off link still renders → S1 privacy bug, treat as security (§5), Macro #9 pattern.

### 4.11 Projects, status pages, exports, commit annotations (P1)
- **Projects:** check not visible under a project → it belongs to exactly one project; move it in the check settings. **Status page:** `/s/{slug}` 404 = not published; incidents auto-generate from down/regression events — if none appear, check that the underlying checks are in the page's project. **Export:** `GET /api/checks/{id}/export?format=csv` needs auth + a date range; 402 = history beyond your plan window. **SHA annotation:** `POST …/samples` needs an API key; 422 = missing `ms`/`status` fields.

### 4.12 Docker / self-hosting (community)
- **Symptoms:** container won't boot; DB locked; scheduler silent; port conflict.
- **Causes/fixes:** Python <3.11, `/data` volume not mounted/writable, `PORT` taken, `RUN_SCHEDULER=0` (web-only). Back up by copying the SQLite file (WAL: copy after a clean shutdown or use `.backup`). No SMTP env = no email alerts (not an error). Upgrades: pull the new image, `docker compose up -d` — migrations apply idempotently on boot.
- **Escalate when:** a clean `docker compose up` on a supported host still fails to boot → S4 best-effort with `docker compose logs` output (redact secrets).

### 4.13 Billing, plans, and hitting limits (402)
- **Symptoms:** `402` on check-create; can't set 1-min interval on Free; Stripe toggle confusion.
- **Causes/fixes:** Plan limits are enforced in `plan_limits` (checks, min interval, history days) — see FAQ #11. Sprint-1 billing is a **manual plan toggle** (admin endpoint) until Stripe lands behind its env flag (P1) — if a user was promised Pro and isn't seeing it, the toggle may not have been applied; escalate to admin. Never delete checks on limit-hit.
- **Escalate when:** a paying user's plan shows `free` in the admin inbox snapshot → S2 (billing), Macro #8.

---

## 5. Ticket Lifecycle + Severity / SLA

### 5.1 Lifecycle (state machine — enforced in the admin inbox)

```
            ┌──────────────┐
            ▼              │
  [open] ──► [acknowledged] ──► [in_progress] ──► [pending_user]
   ▲                                │  ▲                │
   │                                ▼  │                ▼
   │                             [resolved] ◄────── (user replies)
   │                                │
   └────────── [reopened] ◄─────────┘
                    │
  [resolved] ──► [closed]  (auto after 7 days of no reply; user can reopen)
```

| State | Meaning | Entry action | Exit |
|---|---|---|---|
| `open` | Created, not yet acked | Auto-ack (Macro #1) | Agent picks up |
| `acknowledged` | Human has seen it | Agent sets SLA clock start | Agent starts work |
| `in_progress` | Actively being worked | — | Waiting on user, or resolved |
| `pending_user` | Ball is in the user's court (Macro #3) | Agent sends the ask | User replies → `in_progress` |
| `resolved` | Fix/answer delivered (Macros #5/#10) | CSAT prompt fires (§7) | 7 days auto-close, or reopen |
| `reopened` | Problem returned | — | Back to `in_progress`, severity preserved |
| `closed` | Terminal | Retained 12 months (§1.4) | Reopen only |

Rules: every state change writes a `support_replies` row (`author='system'`) so the timeline is the audit trail. Internal notes (`sent_via='note'`) are visible only in the admin inbox. A ticket may not skip `acknowledged` → `resolved` without at least one agent reply (prevents silent closes).

### 5.2 Severity and SLA

Severity is set by the agent (user self-rating is a hint). **SLA = first human response** (ack doesn't count). "Business hours" = Mon–Fri, 09:00–18:00 CET (launch assumption, stated in the auto-ack).

| Severity | Definition (LatencyLedger examples) | First response | Resolution target | Channel |
|---|---|---|---|---|
| **S1 Critical** | Platform down; data loss; public-link privacy leak (§4.10); auth bypass; billing charging wrongly with money moved | **≤ 4 business hours** | Workaround or fix ≤ 2 business days | Email + in-app, both |
| **S2 Major** | A core feature is broken for a user: scheduler not sampling (§4.3), gate contradicting the chart (§4.9), paid plan shows Free (§4.13), alerts firing >50% rise ignored (§4.5) | **≤ 1 business day** | Fix or workaround ≤ 5 business days | Email + in-app |
| **S3 Minor** | Degraded or confusing, workaround exists: export range bug, webhook delivery 422, key 401 on fresh key, single-check stats oddity | **≤ 3 business days** | Next release | In-app preferred |
| **S4 Question / request** | How-to, feature request (Macro #7), docs gap, self-host best-effort | **≤ 5 business days** | Answer / roadmap entry | In-app preferred |

- **Breach handling:** if an SLA will be missed, the agent sends an honest update before the deadline (new ETA + what's happening) — a missed-but-communicated SLA beats a silent one. Breaches are logged (`support_tickets` breached flag via `first_response_at` vs `created_at`) and reviewed monthly.
- **Self-hosted/community:** S4 best-effort only; S1–S3 on a self-hosted install are fixed in code and shipped, not paged.
- **Anti-gaming:** severity can't be downgraded silently — changing it writes a timeline note with the reason.

---

## 6. Feedback → Roadmap Loop Design

Goal: every support interaction makes `docs/roadmap.md` smarter, with zero new tooling.

```
Ticket / survey / in-app feedback
        │
        ▼
 Categorize (admin inbox, one click): bug | feature | praise | docs-gap | wont-fix
        │
        ├── bug ──► fix (Macros #4/#5) ──► changelog line
        ├── feature ──► feedback_votes (topic + count) ──► roadmap scoring ──► roadmap.md
        ├── docs-gap ──► Knowledge Base article (§10) ──► ticket resolved by link
        └── praise ──► testimonial pool (with permission) + NPS §7
```

1. **Capture:** the feedback form's Category field (§1.3) + admin re-categorization. Feature requests create/update a `feedback_votes` row per topic string (normalized: lowercase, trimmed, de-duped by the agent — e.g. "slack alerts" / "Slack notifications" merge).
2. **Score:** monthly, the support lead ranks feature topics by `votes × plan_weight` (Pro/Team votes count 2× — they represent the revenue we need for M3's 50 paying users) + strategic fit against `docs/roadmap.md` P1/P2. Top items get promoted into `roadmap.md` with a "requested by N users" annotation.
3. **Close the loop (the part most tools skip):** when a roadmap item ships, every open `feedback_votes` ticket on that topic gets Macro #7's update variant ("shipped in {version}") if the user's ticket is still open, or a one-off email if closed but ≤12 months old. This is the cheapest retention lever we have.
4. **Quarterly digest:** a short section (added to `roadmap.md` or a `docs/changelog.md` if one is created) listing: top 5 requested features, what shipped from user feedback, and what we explicitly won't do (with the Macro #6 reasoning). Publish it in-app (`/help/changelog`) — transparency is a feature for indie devs.
5. **Guardrails:** feedback never auto-changes the roadmap (human decides); no vote-buying; personal data in feedback follows §1.4 retention.

---

## 7. NPS / CSAT In-App Survey Design

Both surveys live in `surveys` (§1.3), render in vanilla JS, store in SQLite, and respect design-system (quiet, one question, dismissible, never a modal that blocks the dashboard).

### 7.1 CSAT (per-ticket, the operational one)

- **Trigger:** on `resolved` (§5.1) only — Macro #10 carries the link. One tap: `GET /support/survey/csat?ticket=LL-####` → 5 stars (1 = very unhappy … 5 = very happy) + optional 140-char comment. No login required (ticket ref is the capability), one response per ticket (idempotent — repeat taps ignored).
- **Storage:** `surveys(kind='csat', score=1–5, context=ticket_ref)` + mirror into `support_tickets.csat_stars` for queue reporting.
- **Use:** weekly CSAT = mean stars; target ≥ 4.2. Any ≤2 response triggers a follow-up: agent reopens the conversation personally within 1 business day (this is where churn is actually prevented). CSAT is per-agent too (assignee), reviewed monthly, never tied to automation.
- **Anti-bias:** asked only on resolved tickets (not on every reply), results shown to the whole team, no incentives.

### 7.2 NPS (relationship, quarterly)

- **Trigger:** user has been active ≥ 30 days AND has ≥ 1 check with ≥ 7 days of history (i.e. they've actually gotten value), then at most **once per quarter per user**, shown as a dismissible inline banner on the dashboard (not a modal) on the first weekly-active day of the quarter.
- **Question:** "How likely are you to recommend LatencyLedger to another developer?" 0–10. Score: promoters 9–10, passives 7–8, detractors 0–6. **NPS = %promoters − %detractors.** Optional follow-up: "What one thing would make this a 10?" (feeds §6 as a `feedback_votes` topic).
- **Cooldowns (hard rules):** never show within 7 days of a CSAT prompt, never during an open S1/S2 ticket, never more than quarterly, dismiss = snooze 90 days, no re-prompt after a detractor score for 6 months (they get a personal follow-up instead).
- **Targets (M3):** NPS ≥ 30, response rate ≥ 10% of eligible (report raw counts alongside — small-n NPS is noise; don't over-read it).
- **Detractor handling:** any 0–6 score creates an S3 ticket assigned to the support lead with context — NPS here is a churn-detection system, not a vanity metric.

---

## 8. Status Page Design (`/status` Endpoint)

Two distinct things — don't conflate them (product spec keeps them separate too):

| | **Platform status** (this section) | **User status pages** (P1, product spec #11) |
|---|---|---|
| URL | `GET /status` (hosted) | `GET /s/{slug}` |
| Audience | Everyone, no auth | The user's customers |
| Purpose | "Is LatencyLedger broken?" | "Is *their* API broken?" |
| Source | Self-monitoring (below) | Their checks' down/regression events |

### 8.1 Platform `/status` design

**Data (no new infra):** derive from the existing `GET /healthz` (DB ping + scheduler heartbeat, `architecture.md` Observability) plus a tiny `status_events` table:

```sql
status_events(id INTEGER PK, component TEXT, state TEXT,  -- 'operational'|'degraded'|'outage'|'maintenance'
              message TEXT NULL, started_at TEXT, ended_at TEXT NULL, created_by TEXT);
```

- **Components (fixed list):** Web app, API (`/api/v1`), Scheduler/ingest, Alert delivery (email/webhook), Public reports.
- **Auto-detection:** a watchdog (same scheduler thread) flips a component to `degraded`/`outage` when its self-check fails N consecutive times (e.g. scheduler heartbeat stale > 5 min, healthz DB ping fails), and back to `operational` on recovery — then auto-creates the `status_events` row. Manual incidents (deploys, bugs) are posted from the admin inbox ("Post status update" on `/admin/support` reuses the same table).
- **Pages:**
  - `GET /status` (HTML, first-class, design-system): overall banner (green/neutral "All systems operational" or red "Degraded: Scheduler" — icon + text, never color alone), per-component dots with **90-day uptime %** computed from `status_events`, active incident list with plain-language summaries and timestamps, past-incidents list (auto-generated from the same table — same pattern as the user's `/s/{slug}`), and a subscribe line ("get incidents by email" → creates an alert channel, §4.7).
  - `GET /status.json` (machine-readable): `{overall, components:[{name,state,uptime_90d}], active_incidents:[...], updated_at}` — this is what sophisticated users poll; also powers the dashboard footer status link on every page.
  - `GET /status/feed.xml` (RSS, optional P1): incidents as feed items — trivial with string templating, no dependency.
- **Caching/privacy:** `/status` is public, cacheable (ETag on `updated_at`), and must expose **no** user data — component states only. The self-monitor's raw probe results stay server-side.
- **Support tie-in:** every S1/S2 ticket that is platform-caused must link a `status_events` row (or create one) — the status page is the single source of truth, and Macro #1's "check /status first" stays honest.

---

## 9. Churn Playbook + Win-Back Email Draft

Churn here means: a hosted user stops getting value (checks deleted, no logins, plan lapses) — the silent kind, since indie devs rarely cancel loudly. All signals are computable from existing tables (`users`, `checks`, `samples`, `alerts`, `sessions`); no new tracking.

### 9.1 Churn risk signals (checked weekly by a script, or by the lead's Monday review)

| Signal | Threshold | Likely cause | Play |
|---|---|---|---|
| **Dormant** | No login in 14 days, but checks still sampling | Forgot / never got value | In-app banner + email (Play A) |
| **Value-never** | Signup → 0 checks after 7 days | Activation failure (KPI: 40% add a check in 24h) | Onboarding nudge (Play B) |
| **Alert-fatigued** | ≥ 3 alerts in 7 days, 0 chart views after alerts | False positives eroding trust (§4.5) | Threshold-tuning email (Play C) |
| **Silent churn** | All checks deleted, or plan lapses to Free with no login 30d | Moved to competitor / API decommissioned | Win-back (Play D, §9.3) |
| **Power-then-gone** | Was Pro/Team, downgraded, still has checks | Price or limit pain | Limit-aware offer (Play D variant) |

### 9.2 Plays (all manual-send from the admin inbox in Sprint 1 — no automation SaaS)

- **Play A — Dormant:** subject "Your checks are still running — here's what they saw". Body: their own data (last p95, any regression since they left — evidence first). One CTA: "View my checks". No discount, no guilt.
- **Play B — Value-never:** subject "Add your first check in 60 seconds". Body: the 3-step path + the GitHub Actions example link + offer of a manual reply ("reply and I'll add it with you" — concierge for the first 100 signups).
- **Play C — Alert-fatigued:** subject "Let's tune {check_name}'s alerts". Body: show their alert count + precision ("3 alerts, 0 opened"), one-click link to raise threshold to 30% and a 6h mute. Fixing false positives *is* the retention play (product spec risk #2).
- **Play D — Silent churn / win-back:** §9.3.
- **Rules:** max 1 churn email per user per 30 days; every send logged as a `support_replies` note (`sent_via='email'`) against a `kind='churn'` marker; honor unsubscribes instantly (one `churn_opt_out` flag on `users`); never email a user with an open S1/S2 ticket; never use dark patterns (no "your data will be deleted in 48h" — it's not true, we retain per §1.4).

### 9.3 Win-back email draft (Play D)

> **Subject:** We fixed what was probably annoying — plus your old data is still here
>
> Hi {name},
>
> It's been a while since you checked on {check_name} ({url}). Two things since you left:
>
> 1. **{fix_line}** — the thing most likely to have frustrated you ({e.g. "alerts now learn your deploy rhythm — a SHA-tagged deploy no longer re-alerts every 6 hours"}).
> 2. **Your history is intact.** {check_name} has {sample_count} samples waiting, including the baseline from before you left — pick up exactly where you stopped.
>
> If the API itself went away, no worries — delete the check and you're done, no hard feelings. If it just got noisy or you moved for a week, one click is back in:
>
> **[View my checks]** ({dashboard_link})
>
> And if neither is true, reply to this email and tell me what would bring you back. I'm the support lead and I read every reply.
>
> — {support_lead_name}, LatencyLedger
>
> P.S. Not interested in these emails? [Unsubscribe] — one click, no login, and it's done.

**Success metric:** win-back rate = reactivated (any login + check view within 30d of send) ÷ sent; target ≥ 5% for Play D, reviewed monthly. A win-back that only gets an unsubscribe is still a successful interaction — it means the address list stays clean.

---

## 10. Knowledge Base Structure

Served **in-app** at `/help` (static HTML, same no-build pattern as the rest of the app — no ReadMe.com/Instantly, no GitBook). One source of truth: articles are Markdown files in `docs/kb/` rendered by the existing handler, so docs live in the repo next to `product-spec.md` and version with the code. Self-hosters get the same KB from their own install.

### 10.1 Information architecture (tree)

```
/help/                                    ← landing: search box + top-5 answers + category cards
├── getting-started/
│   ├── add-your-first-check.md          ← the 60-second path (FAQ #3)
│   ├── understand-your-chart.md         ← p50/p95/p99, baselines, SHA markers
│   └── your-first-regression-alert.md   ← what just fired and what to do
├── guides/
│   ├── ci-gate-github-actions.md        ← the YAML walkthrough (product spec #7)
│   ├── tune-your-alerts.md              ← thresholds, cooldowns, false positives (§4.5)
│   ├── public-reports.md                ← sharing evidence safely (§4.10)
│   └── commit-annotations.md            ← finding the guilty SHA (P1)
├── reference/
│   ├── api.md                           ← endpoints, error codes, gate 200/422
│   ├── plans-and-limits.md              ← the pricing table, 402 behavior
│   └── self-hosting.md                  ← Docker, env vars, backups (§4.12)
├── troubleshooting/                     ← the §4 guides, one file per feature
│   ├── login-and-sessions.md
│   ├── scheduler-not-sampling.md
│   ├── email-alerts-not-arriving.md
│   ├── api-keys-and-401s.md
│   └── ci-gate-always-failing.md  … (mirrors §4)
├── feedback/                            ← the §1.3 form + §6 changelog link
└── status/                              ← link out to /status (§8)
```

### 10.2 Article format (every `.md` file)

```markdown
---
title: <plain-language, searchable>
category: getting-started | guides | reference | troubleshooting
keywords: <comma list for search>
updated: <YYYY-MM-DD>
plan: free | pro | team | all          ← badge shown on the article
---

# <Title>
<One-paragraph answer first — the KB is skimmed, not read.>
## Steps / Causes & fixes   (numbered, evidence-first, as in §4)
## If this doesn't work     (the escalation path: file a ticket with {ref} context + link to the form)
```

### 10.3 Search (stdlib-only, no SaaS search)

SQLite `LIKE` over `title + keywords + body` on a `kb_articles` index table built at boot from `docs/kb/*.md` (title/keywords only — body via the file read on open). Rank: title match > keyword match > body match; show top 8 with category badges. No FTS5 dependency for Sprint 1 (it ships with SQLite but `LIKE` is honest at this corpus size); upgrade to FTS5 only if the KB passes ~200 articles. Also: the feedback form (§1.3) shows the top 3 matching articles *before* submit — deflection at the moment of need.

### 10.4 Maintenance rules (owned by the support lead)

- Every S3/S4 ticket whose answer is reusable becomes a KB article or an update within the same week (the ticket links the article; the article links back to the ticket category).
- `updated:` bumped on every edit; articles stale > 6 months get a "reviewed" pass at the quarterly digest (§6.4).
- KB coverage target: ≥ 80% of ticket volume answerable from `/help` by M3 (measured by the admin inbox's "resolved by article link" tag).
- The KB is the marketing site's help section too — same files, linked from the landing page. No separate docs system, ever (constraint).

---

## Appendix — Implementation Checklist (for the build sprint — NOT this sprint)

- [ ] Migrations: `support_tickets`, `support_replies`, `feedback_votes`, `surveys`, `support_macros`, `status_events`, `users.is_admin`/env `ADMIN_EMAILS`, `users.churn_opt_out`
- [ ] `POST /api/support/tickets`, `GET /support/survey/csat`, `GET /status`, `GET /status.json`, `/help/*` + search
- [ ] `/admin/support` inbox (list/detail/composer/lifecycle) behind admin gate
- [ ] Seed `support_macros` with the 10 templates above (editable, no deploy)
- [ ] Auto-ack on create (Sprint 1: in-app confirmation; email ack when SMTP configured)
- [ ] `/healthz` already exists → wire the §8 watchdog to it
- [ ] KB: create `docs/kb/` with the §10.1 tree, seed the 5 highest-deflection articles first
- [ ] Privacy: 12-month retention job, hard-delete path, no secrets in ticket bodies (Macro #9)

## Counts (verification)

- **Support macros: 10** (Macro #1–#10, §2)
- **FAQ Q&A: 15** (FAQ #1–#15, §3)
- **Troubleshooting guides: 13** (§4.1–§4.13)
- **Severity levels: 4** (S1–S4, §5.2)

