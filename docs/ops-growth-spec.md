# httpping — Ops + Growth Spec

> **Owner:** Desk-5, Ops + Growth Lead · **Status:** Spec only — do not build features yet
> **Product:** `httpping` — measure HTTP request latency. Today a TypeScript CLI
> (`httpping <url> [count]` → per-request ms + min/max/avg, see `src/index.ts`).
> This spec defines the hosted SaaS around that core: **latency & uptime monitoring
> for HTTP endpoints**, with the CLI as the free acquisition wedge.
> **Companion docs:** `docs/product-spec.md` (PM, desk-1), `docs/architecture.md`, `docs/roadmap.md`.
>
> **Constraints (hard):** GDPR/LGPD-aware · no paid tools required at launch ·
> everything actionable for the build team (each item names an owner + a done-condition).

---

## 1. Go-to-market plan

### 1.1 Positioning (one line)
> "Know when your API got slower before your users do." LatencyLedger watches
> p95 against a rolling 7-day baseline and alerts on a 20%+ regression — even
> while status is still 200 OK. The CLI + GitHub Actions gate is the free wedge;
> CI-native regression evidence is the paid reason to stay.

### 1.2 Target segments (ranked)

| # | Segment | Who | Pain | Why they convert |
|---|---------|-----|------|------------------|
| S1 | **Indie hackers / solo devs** | 1-person SaaS, side projects, API builders | Their API is their product; they ship fast, monitor never. Current tooling (Pingdom/StatusCake) feels enterprise/heavy. | CLI is familiar; free tier covers them forever; latency p95 is a number they already care about. |
| S2 | **Small dev teams (2–15)** | Startup eng teams, agencies | Need "is it us or the region?" answers; on-call for public APIs, webhooks, status pages. | Shared monitors, Slack/email alerts, region breakdown, status page link. |
| S3 | **Ops / SRE / platform engineers** | DevOps at mid-size cos, MSPs | Need synthetic checks + SLO evidence for clients; want API/CLI parity for IaC. | API + CLI + webhooks, exportable data, multi-region, retention. |
| S4 | **Open-source maintainers** | OSS projects with public endpoints/pages | Need credibility ("we're up") + community visibility; zero budget. | Free tier + public status badge; CLI in CI. |

**Primary ICP at launch: S1 + S2.** S3 is the expansion motion; S4 is the
top-of-funnel flywheel.

### 1.3 Channels (ranked, all $0 at launch)

| Rank | Channel | Motion | Cost | Expectation |
|------|---------|--------|------|-------------|
| **1** | **GitHub / OSS flywheel** (README, npm, GitHub README badge, Discussions) | `npm i -g httpping` → README demo GIF → link to hosted monitors → badge on the monitored site | $0 | Highest volume, lowest CAC; devs trust CLI in CI. |
| 2 | **SEO / programmatic pages** | Free tools: "HTTP latency checker for <url>", region latency pages, glossary (p95, TTFB). Each page = working checker + CTA. | $0 (build time) | Slow burn, compounds; target long-tail "check latency", "is <service> up". |
| 3 | **Dev communities** | Hacker News "Show HN", r/webdev, r/selfhosted, Indie Hackers, Dev.to, Lobsters. Launch post + weekly build-in-public. | $0 | Spiky; one good HN thread > months of ads budget we don't have. |
| 4 | **Content / docs** | "How to measure p95 latency", "latency budgets for APIs", CI latency-gate tutorial using the CLI. | $0 | Feeds SEO + newsletter. |
| 5 | **Partnerships / integrations** | GitHub Actions marketplace listing, webhook receivers, status-page embeds. | $0 | Distribution via platforms users already live in. |
| 6 | Paid (later, not at launch) | Developer-targeted search/social | — | Only after free-channel CAC + LTV are measured. Explicitly **out** of 90-day OKRs. |

**Top channel: GitHub/OSS flywheel.** All launch messaging routes through the CLI.

### 1.4 Landing page messaging (copy — hand straight to build)

- **H1 (hero):** "Is your endpoint fast? Prove it in 10 seconds."
- **Sub:** "`httpping` measures real HTTP latency — min, max, avg, p95 — from your
  terminal or from 12 regions in the cloud. No card. No agent. No dashboard-hunting."
- **Primary CTA:** `npx httpping https://your-api.com` (copy-paste, with copy button)
  → secondary: "Start free monitoring" (no card).
- **Three proof points (above fold):**
  1. p95, not averages — "Averages lie. We show the tail your users feel."
  2. Multi-region — "One slow region is an outage you haven't found yet."
  3. CLI = API = UI — "Same check everywhere: terminal, CI, and dashboard."
- **Trust/use-case block:** "For APIs, webhooks, status pages, and that one endpoint
  a client keeps asking about."
- **Pricing teaser:** "Free for 3 monitors forever. Pro when you outgrow it."
- **Status-page social proof slot (launch with own monitors):** live badge showing
  httpping's own uptime/latency — dogfooding as marketing.

### 1.5 Launch checklist (build-team actionable)

- [ ] Landing page live: hero message above, `npx` one-liner with copy button, pricing
      teaser, legal footer links (§6), cookie notice (§6.3).
- [ ] CLI published: npm `httpping` + GitHub repo public, README with demo GIF,
      install/usage, "Monitor this in the cloud →" CTA link.
- [ ] Free-tier signup live: email magic-link (no password), 3 monitors, no card (§2).
- [ ] First-run email sequence wired to **local outbox stub** (§4) — never fire-and-forget.
- [ ] Analytics events shipped (§3) + dashboard (Metabase/ClickHouse OSS or Postgres
      materialized views — no paid tool) showing signup→monitor→alert funnel.
- [ ] Own-infrastructure monitors live (landing page + API) with public status badge.
- [ ] Support: FAQ + feedback form + status page live (§5); support inbox monitored.
- [ ] Legal: ToS, Privacy Policy, Cookie notice published, DPA-on-request (§6).
- [ ] Launch posts drafted: Show HN, r/webdev, Indie Hackers, Dev.to — each with
      distinct angle (CLI-first for HN, "free forever" for indie, latency-budget
      tutorial for Dev.to). Post within same week; stagger, don't blast.
- [ ] GitHub Actions marketplace: publish CLI action ("fail CI if p95 > X").
- [ ] Backup/restore + incident runbook tested for the SaaS itself (§5.4).

---

## 2. Pricing & packaging detail

> Currency: USD. Prices are starting hypotheses for the 90-day test, not final.
> Price must be ignorable on every page except the pricing page; all tiers
> self-serve. Annual = 2 months free (≈17% off).

### 2.1 Tiers

| | **Free** | **Pro** | **Team** |
|---|---|---|---|
| Price | $0 forever | **$9/mo** per workspace | **$29/mo** per workspace |
| Checks | 3 | 25 | 100 |
| Check interval | 5 min min | 1 min min | 1 min min (multi-region P2) |
| Regions | 1 (single-region P0) | 1 (P0) | Multi-region (P2) |
| History | 7 days | 90 days | 1 year |
| Latency percentiles | p50/p95 | p50/p95/p99 + histograms | + SLO burn-rate views |
| Regression alerts | 1 channel (email) | email + webhook + chat | all + status pages |
| Users | 1 | 3 seats | Unlimited seats |
| API + CI gates | CI gate, 1 project | CI gates unlimited | unlimited + audit log |
| Public report links | yes | yes | yes + custom domain |
| Support | Community (GitHub) | Email, 48h | Email, 24h + priority |
| Self-host (Docker) | yes (community) | - | yes |

**Annual:** Pro $90/yr, Team $290/yr. **Grandfather:** anyone on a launch promo
keeps their rate while continuously subscribed.

### 2.2 Feature matrix (ship order matters)

| Feature | Free | Pro | Team |
|---|:---:|:---:|:---:|
| CLI (`httpping`) | ✅ | ✅ | ✅ |
| Hosted checks (WAS/HTTPS, status codes) | ✅ | ✅ | ✅ |
| Body/keyword validation | — | ✅ | ✅ |
| TLS/cert expiry alerts | — | ✅ | ✅ |
| Threshold alerts (p95 > X) | — | ✅ | ✅ |
| Multi-step / transaction checks | — | — | ✅ |
| RUM tie-in / browser checks | — | — | Later (§7) |
| CI gate (GitHub Action) | ✅ | ✅ | ✅ |
| Public status badges | ✅ | ✅ | ✅ |

### 2.3 Limits (enforced server-side, surfaced in UI at 80%)

- Monitors, checks/day (interval × monitors), seats, team members, API rate
  (Free 60/min · Pro 300/min · Team 1000/min), data retention (above), regions.
- **Free-tier abuse guard:** no-card accounts capped by checks/day; monitors to
  private/internal URLs rejected on Free (prevents SSRF abuse of the checker grid).

### 2.4 Upgrade triggers (product events → in-app nudge, max 1 per 7 days)

| Trigger event | Suggested upgrade |
|---|---|
| Created 3rd monitor (Free cap hit) | Pro — more monitors |
| Checks at 80% of quota | Pro — higher checks/day |
| Tries interval < 5 min | Pro — 30 s checks |
| Tries region > 3 or a 4th region | Pro — 8 regions |
| Tries webhook/Slack alert | Pro — integrations |
| Tries team invite | Team — unlimited seats |
| Retention view requested > 7 days | Pro — 90 days |
| Status page custom domain | Pro |

Nudge must show the **usage number that triggered it** ("You've used 3/3 monitors"),
never a bare "Upgrade now".

---

## 3. Analytics plan

### 3.1 Principles
- **$0 stack:** event table in Postgres → Metabase (OSS, self-hosted) or a
  `metrics_daily` rollup + Grafana. No Mixpanel/Amplitude at launch.
- **Privacy/GDPR:** no third-party trackers at launch; first-party events only,
  pseudonymous `user_id`, no raw URLs/PII in event payloads (hash target host for
  internal analytics). Opt-in needed before any future third-party analytics.
- **One source of truth:** every event lands in `events(event_name, user_id,
  workspace_id, properties jsonb, created_at)`; funnels are SQL views, not
  client-side SDK magic.

### 3.2 Events to track (snake_case, ship with first build)

| Event | When | Key properties |
|---|---|---|
| `landing_viewed` | Landing page view | `source` (utm/referrer), `page` |
| `cli_installed` | First CLI run (anonymous pinghome, opt-in) | `version`, `platform` |
| `signup_started` / `signup_completed` | Magic-link flow | `method`, `source` |
| `monitor_created` | First + subsequent monitors | `interval`, `region_count`, `is_first` |
| `check_executed` | (internal, sampled) one monitor-day | `monitor_id`, `regions` |
| `alert_configured` | Alert channel added | `channel` (email/slack/webhook) |
| `alert_fired` | Outage/threshold alert sent | `monitor_id`, `type`, `region` |
| `status_page_viewed` / `badge_embedded` | Public status surfaces | `monitor_id` |
| `upgrade_viewed` / `checkout_started` / `subscription_activated` | Paywall flow | `plan`, `trigger` (§2.4) |
| `downgrade_requested` / `cancelled` | Churn | `plan`, `reason` (survey) |
| `feedback_submitted` | In-app feedback (§5.3) | `category`, `sentiment` |
| `email_sent` / `email_clicked` | Lifecycle emails (§4) | `template`, `variant` |
| `weekly_active_workspace` | Weekly heartbeat (derived) | — |

### 3.3 Funnel stages (SQL views + Metabase questions)

1. **Awareness → signup:** `landing_viewed → signup_started → signup_completed`
   (target ≥ 8% landing→signup; the CLI one-liner is the conversion device).
2. **Activation:** `signup_completed → monitor_created (first)` — *the* aha moment.
   Target: ≥ 60% of signups create a monitor within 24h. **North-star-adjacent metric.**
3. **Value:** `monitor_created → alert_configured → alert_fired` (they've felt the
   product do its job). Target ≥ 35% of activated workspaces see a real alert in 30d.
4. **Monetization:** `alert_fired → upgrade_viewed → subscription_activated`.
5. **CLI funnel (parallel):** npm downloads (npm registry API, weekly) → `cli_installed`
   → hosted signup (match via optional `httpping login` linking CLI run to account).

### 3.4 Retention cohorts

- **Cohort by signup week** (`cohort_week`), track W1/W4/W12 retention =
  workspace ran ≥ 1 check in the week. Report **weekly-active-workspaces (WAW)**,
  **monitor-weeks** (monitors alive that week), and **alert-delivered workspaces**.
- **Segment cohorts:** by plan, by monitor count bucket, by first-alert latency
  (workspaces that got an alert in week 1 vs. never) — the single strongest
  retention predictor to validate.
- **Churn cohort:** `cancelled` + reason taxonomy (price / missing feature /
  never-activated / competitor). Review monthly; feed §7 roadmap.

### 3.5 Instrumentation checklist for build
- [ ] `events` table + insert-on-action in every mutation (signup, monitor, alert,
      subscription); sampling only for `check_executed`.
- [ ] Metabase dashboards: Acquisition, Activation funnel, Retention cohorts, Revenue.
- [ ] Weekly metrics job: npm downloads, WAW, churn; posted to team channel (self-hosted
      webhook or email digest from the local outbox).

---

## 4. Retention / engagement loops

### 4.1 Loops (in priority order)

1. **The alert loop (core):** monitor trips → email/Slack alert → user opens
   dashboard → sees region breakdown → adds a threshold/team member → deeper
   in the product. Every alert email must link to the *specific* incident view,
   not the home page.
2. **Weekly latency digest:** "Your API's p95 this week: 212ms (↓18%) — slowest
   region: eu-west. You spent 4h 12m above your 500ms budget." Value without
   action required; builds the habit of opening httpping weekly.
3. **Badge loop:** free users embed the public status badge → their README/site
   recruits the next user. Badge links to a public status page (SEO + acquisition).
4. **CI loop:** GitHub Action fails a deploy when p95 regresses → dev sees httpping
   in their pipeline → adds continuous monitors.
5. **Win-back:** dormant 30d → "your monitors went quiet — resume checks?" + one-click
   resume (monitors paused, not deleted, for 90 days).

### 4.2 Email design — local outbox at launch (no mail service required)

**Architecture (build this first, swap provider later):**

- `email_outbox(id, workspace_id, template, payload jsonb, status, attempts,
  next_attempt_at, created_at, sent_at)` — every email is inserted here first;
  a worker drains it. This gives us transactional retry + an audit trail for
  GDPR deletion requests.
- **Transport abstraction:** `MailTransport` interface with two implementations:
  1. `FileTransport` (launch default): writes RFC-822 `.eml` files to
     `var/outbox/` (+ logs the recipient) — zero external dependency, testable in CI.
     In production-at-launch, `FileTransport` writes to a maildir that the host's
     existing MTA (Postfix/dovecot on the VPS) can pick up, or mail is simply queued.
  2. `SmtpTransport` (drop-in later, e.g. any free-tier SMTP): same interface,
     env-configured. Swapping in a paid provider (SES/Mailgun) is a config change,
     not a code change.
- **Templates as code:** versioned templates (`templates/welcome.html`,
  `alert.html`, `digest.html`, `winback.html`, `dunning.html`) with
  `{{variables}}`, plain-text fallbacks, and a `List-Unsubscribe` header +
  one-click unsubscribe link (GDPR/LGPD: consent + opt-out on every non-transactional
  email; transactional vs. marketing clearly separated).
- **Suppression list:** `email_suppressions(address_hash)` — bounces/unsubscribes/
  GDPR erasure requests; checked before every enqueue.
- **Sending rules:** max 1 marketing email / 7 days per workspace; transactional
  (alerts) exempt but rate-limited per monitor; all timestamps UTC; emails
  render inlined-CSS + plain text (no tracking pixels — privacy-first; measure
  clicks via redirect links instead).

**Email sequence (launch):**
1. `welcome` (transactional, immediate) — monitor-creation deep link + CLI command.
2. `first-alert-hero` (triggered by first real alert) — "It worked. Here's your
   incident." (only send if an alert actually fired).
3. `weekly-digest` (opt-in at monitor creation, default on for Pro/Team).
4. `upgrade-nudge` (triggered by §2.4, shows usage number).
5. `winback-30d` — resume in one click.
6. `dunning` (failed payment) — 3 attempts over 7 days, then graceful downgrade
   to Free (no data loss during grace).

---

## 5. Support playbook

### 5.1 Tiers & SLAs

| Tier | Channel | First response | Resolution target |
|---|---|---|---|
| Free | GitHub Discussions, FAQ | Best effort (48h) | Best effort |
| Pro | Email (`support@`) | **48h** business days | 5 business days |
| Team | Email, priority tag | **24h** business days | 3 business days |
| Outage (all tiers) | Status page + alert to owner | Acknowledge ≤ 1h business hours; public status update ≤ 2h | Postmortem within 5 days |

Solo-team reality: SLAs are targets, not contractual guarantees until we charge
meaningfully; publish them as targets ("aim for") to avoid legal exposure.

### 5.2 FAQ draft (ship as docs FAQ + support macro library)

1. **How is httpping different from Pingdom/UptimeRobot?** — CLI-first, p95 latency
   (not just up/down), API parity, free tier that covers real indie use.
2. **What counts as a check / how are checks billed?** — 1 check = 1 region probe of
   1 monitor; see Pricing for quotas; paused monitors don't consume checks.
3. **Can I monitor an internal/private endpoint?** — Paid tiers via our checker grid
   only for public HTTPS endpoints (SSRF policy); internal needs a self-hosted
   runner (roadmap, §7 Later).
4. **Why did I get alerted when the site was up?** — Region-specific failures,
   status-code vs. latency thresholds; how to tune per-region vs. global rules.
5. **What regions do you check from?** — List (§2.1); how regions affect false positives.
6. **How long is my data kept?** — Per plan (§2.1); export anytime via API/CSV.
7. **Can I cancel / get a refund?** — Self-serve cancel; annual refunds pro-rated
   within 30 days; data export before cancellation.
8. **Is my data used to train AI models?** — No. Never. (publish + honor).
9. **Where is data hosted / who is the sub-processor?** — Link to Privacy Policy.
10. **How do I add the status badge?** — Markdown snippet (`![status](...)`).

### 5.3 Feedback loop

- **In-app:** every alert email + dashboard has "Was this alert right? 👍/👎" →
  `feedback_submitted` event (§3.2) + stored verbatim.
- **Monthly:** 1-question survey to active workspaces ("What would you miss most if
  we shut down?") — open-ended, reviewed manually; top answers feed §7.
- **Public:** GitHub Discussions "Feedback" category; link from every support reply.
- **Triage:** feedback → labeled GitHub issues weekly; churn reasons (§3.4) reviewed
  monthly against roadmap.

### 5.4 Internal ops (for the SaaS itself)
- **Status page** (our own, dogfooded) + incident runbook: detect (our own monitors)
  → acknowledge → status page → fix → postmortem.
- **Backups:** daily Postgres dumps, 30-day retention, restore tested monthly.
- **On-call (launch):** single maintainer + documented escalation; alert to maintainer
  via the same httpping alerting (dogfooding) + a second channel (email).

---

## 6. Legal / compliance (GDPR + LGPD)

> ⚠️ **These are drafts for build to publish, not legal advice.** Have counsel review
> before charging money. Templates below are placeholders to be replaced with reviewed
> text; every draft must be published before paid launch.

### 6.1 Terms of Service — draft outline (publish at `/terms`)
1. Service description; 2. Accounts (accuracy, security, 13+/16+ per GDPR
   age rules); 3. Acceptable use — **no** scanning/probing behind paywalls,
   no SSRF/internal-network abuse, no reselling checks; 4. Availability (target,
   not guaranteed, until SLA contracts exist); 5. Pricing, taxes, cancellation,
   refunds (prorated 30d annual); 6. Intellectual property; 7. Limitation of
   liability; 8. Termination; 9. Changes (30d notice for material changes); 10. Governing law.

### 6.2 Privacy Policy — draft outline (publish at `/privacy`)

- **Controller / contact** + DPO contact (required by GDPR Art. 37 where applicable;
  name a contact even if DPO not mandatory).
- **What we collect:** account email, monitor configs (URLs you monitor — *note: URLs
  can contain PII; warn users not to put tokens/PII in URLs*), check results,
  payment data (via payment processor — **we never store card numbers**),
  support correspondence, product analytics (§3).
- **Purposes & lawful bases (GDPR Art. 6):** contract (service delivery), legitimate
  interests (security/fraud, analytics), consent (marketing email — opt-in only),
  legal obligation (invoicing/tax).
- **LGPD specifics:** rights of access/correction/portability/deletion (Art. 18),
  encarregado (DPO) contact, international-transfer mechanism (SCCs if data leaves
  BR/EEA), ANPD considerations for the Brazilian user base.
- **Sub-processors list** (living page): hosting, payment processor, email
  transport (when swapped in), analytics store — each with location + purpose.
- **Retention:** account data while active; check data per plan; backups 30d;
  deletion within 30 days of request (GDPR Art. 17) including outbox + backups aging out.
- **Cookies:** link to cookie notice (§6.3). **Data export:** self-serve CSV/API export
  (right to portability) before deletion.
- **No sale of data. No ad-tech. No AI training on customer data.**

### 6.3 Cookie notice — draft (publish at `/cookies`, banner at first visit)
- **Strictly necessary** (auth session, security) — always on.
- **Functional** (preferences, e.g. theme, region pinning) — on by default, disclosed.
- **Analytics** — **off by default**, opt-in only (ePrivacy/GDPR consent; LGPD consent).
  No third-party analytics cookies at launch (§3.1), so this stays "none" until
  a tool is added — then this notice + banner must change first.
- Banner: equal Accept/Reject prominence, "Customize" opens granular toggles, choice
  persisted 12 months, withdrawable from footer link anytime.

### 6.4 Checklists for build
- [ ] Cookie banner + Preferences modal (granular, equal-weight buttons).
- [ ] Consent records stored (`consent(user_id, type, granted_at, version)`).
- [ ] Self-serve: export my data · delete my account (30d purge incl. outbox rows).
- [ ] Sub-processor page + Privacy/Terms versioned in git (`docs/legal/`).
- [ ] **DPA** available on request for Team tier (data-processing addendum) before B2B sales.
- [ ] Monitor-creation warning: "Don't put secrets/PII in monitored URLs."

---

## 7. Roadmap (quarters, relative to launch)

### Now — Launch quarter (Q0)
- Hosted checks (WAS/HTTPS), 3→8 regions, p50/p95, email + Slack alerts.
- CLI parity (same check, `httpping check --region`), GitHub Action.
- Public status pages + badges, free tier (3 monitors), outbox email system (§4.2).
- Billing: MANUAL PLAN TOGGLE (admin endpoint) in sprint 1; Stripe optional
  behind env flag (PM 4). Pricing page, legal pages, cookie banner ship at
  launch; charging only after 6.4 sign-off.
- First-run experience: signup → monitor → first alert in < 10 min.

### Next — +1 quarter
- Webhooks + PagerDuty/Opsgenie, keyword/body validation, cert-expiry alerts.
- p99 + latency histograms + budget/alerting on p95 thresholds.
- Team seats + roles, API tokens, audit log; CSV export.
- Multi-step (transaction) checks for Team.
- Self-hosted runner (beta) for internal endpoints (S3 expansion).

### Later — +2 quarters and beyond
- Browser/RUM synthetic checks; SLO burn-rate reporting (Team).
- Status-page multi-product, SLA reports, white-label.
- Anomaly detection (baseline-aware alerts vs. static thresholds).
- Public API v2 + Terraform provider (S3: IaC parity).
- i18n (pt-BR first — LGPD market, §6.2), additional regions (LATAM, Africa).
- Marketplace/integrations: Slack Marketplace, Datadog/Grafana exporters.

---

## 8. OKRs — first 90 days

**Objective 1: Prove the CLI→SaaS flywheel works.**
- KR1.1: 500 hosted signups (email-verified) from all channels.
- KR1.2: ≥ 40% of signups create a first check within 24h (activation, PM 5).
- KR1.3: 5,000 CLI installs (npm/python downloads, weekly trend rising WoW).
- KR1.4: Median time-to-first-chart < 5 min (PM 5).

**Objective 2: Deliver the "first alert" aha moment.**
- KR2.1: ≥ 30% of activated workspaces receive ≥1 true regression alert in
  first 30d; alert precision (marked useful) ≥ 70% (PM 5).
- KR2.2: Median time signup → first monitor < 10 min; signup → first alert < 7 days.
- KR2.3: Weekly digest open rate ≥ 40% (click-tracked, no pixels).

**Objective 3: Validate willingness to pay (no paid tools, no paid ads).**
- KR3.1: ≥ 25 paying workspaces by day 90 (path to PM 50 payers / $450 MRR @ 6mo).
- KR3.2: Free→paid conversion ≥ 3% (PM 5); stretch 5%.
- KR3.3: Monthly gross churn < 8% among payers; ≥ 20 exit-survey responses.

**Objective 4: Be trustworthy enough to keep.**
- KR4.1: W4 cohort retention ≥ 25% of activated workspaces (PM 5); stretch 50%.
- KR4.2: Support first-response SLA met ≥ 90% (§5.1); FAQ deflection: ≥ 30% of
  "support" questions answered by FAQ (tracked via Discussions→FAQ links).
- KR4.3: 100% of signups pass consent/cookie compliance (audit §6.4 checklist).

**Objective 5: Ship launch (build-team gate).**
- KR5.1: All §1.5 launch-checklist items done; §6.4 legal checklist ✅ before any charge.
- KR5.2: Own-infrastructure status page live with 99.9%+ measured uptime over the 90d.

*Review cadence:* weekly metrics check (Metabase), day-45 mid-point review (adjust
pricing/channel mix), day-90 OKR scoring + churn-reason review → roadmap re-plan.

---

## 9. Competitor & market sizing notes

### 9.1 Competitive landscape

| Competitor | Strength | Weakness we exploit |
|---|---|---|
| **UptimeRobot** (free tier) | Cheap, established, huge free tier | Up/down only — no latency percentiles; dated UX; free limits now tight. |
| **Pingdom** (SolarWinds) | Synthetic depth, brand, enterprise | Expensive, heavy, overkill for indie/small teams. |
| **Better Stack (Better Uptime)** | Modern UX, status pages, incident tooling | Focused on uptime+incidents; latency percentile depth + CLI/CI wedge unowned. |
| **StatusCake / Uptrends** | Broad checks (DNS, SSL, real-browser) | Feature-bloated; hard to find the latency story; pricier than our Pro entry. |
| **Cronitor / Hyperping / OhDear** | Developer-friendly, modern, affordable | OhDear is Laravel-centric; Cronitor is cron-focused; Hyperping is closest direct rival — **differentiator: CLI + CI gate + p95-first.** |
| **Cloudflare / AWS health checks** | Free-ish if already on platform | Locked to their infra; not a neutral third party. |
| DIY `curl` + cron | $0, full control | No baseline, no regression alerts, no history — the gap LatencyLedger closes. |
| Bencher / Gatling Cloud | Benchmark tracking in CI | Harness, not live-API drift; pricier/heavier for indies. |

**Our wedge, stated plainly:** nobody owns "latency percentiles + CLI + CI gate +
startup pricing" together. Incumbents sell *uptime*; we sell *speed*, and the CLI
makes speed measurable in the exact place developers already work.

### 9.2 Market sizing (directional, order-of-magnitude)

- **Bottom-up (SAM):** millions of small web businesses/APIs worldwide run public
  HTTP endpoints; a conservative slice — indie SaaS + small dev teams actively
  concerned with API latency in English/PT/ES markets — is **hundreds of thousands
  of potential workspaces**. At $9–29/mo, even 0.01% penetration is a meaningful
  five-figure MRR — the 90-day target (25 payers, §8) needs only a sliver of this.
- **Top-down sanity:** the uptime-monitoring category is a mature, multi-hundred-
  million-dollar market dominated by the incumbents above; we don't need category
  share, we need the "too small / too latency-focused for Pingdom, too serious
  for a cron script" gap — which is precisely S1+S2.
- **Adjacency (future TAM):** SLO/latency-budget tooling for platform teams (S3),
  CI performance gates, public status pages as marketing. Roadmap §7 captures these
  without distracting from the launch wedge.

### 9.3 Risks & watch-outs
- **Incumbent bundling** (cloud + monitoring freebies) → neutrality is our moat;
  publish region coverage honestly.
- **Checker-grid abuse** (SSRF, scraping) → Free-tier public-HTTPS-only policy (§2.3)
  + rate limits + abuse review of signup cohorts.
- **Commodity pricing pressure** → the CLI/CI integration and p95 depth are the
  non-commodity assets; protect them ahead of raw check volume.
- **Legal exposure** (selling before §6 counsel review; processing PII without
  consent records) → hard gate: no charges until §6.4 is ✅.

---

### 2.5 Reconciliation deltas vs PM spec (PM wins)

| Item | PM spec (authoritative) | This ops spec |
|---|---|---|
| SaaS name | LatencyLedger; httpping = CLI/core | Renamed throughout |
| Pricing | Free / Pro $9 / Team $29; 3/25/100 checks; 7d/90d/1yr history | Aligned (2.1/2.3) |
| Regions/intervals | Single-region P0; Free 5min min, paid 1min min; multi-region P2 | Aligned |
| CI gates | 1 project Free; unlimited paid | Aligned |
| Billing | Manual toggle; Stripe P1 behind env flag | 1.5/7 updated; no charge before 6.4 |
| North star | Regression alert delivered + acted on (open alert, view chart <1h) | Adopted (3.3/8) |
| Targets | 50 payers/$450 MRR @ 6mo; free-paid ≥3%; W4 ≥25%; first-chart <5min | Day-90 OKRs = path milestones (8) |
| Stack | Python stdlib + SQLite, plan_limits table | events/outbox must be SQLite-compatible |

*End of spec. Build next: SQLite events/email_outbox tables (3/4) before payments; gate charging on 6.4 counsel review. Original next step: PM confirms
`docs/product-spec.md` + `docs/architecture.md`; build team implements §3/§4
instrumentation + outbox before payments.*
