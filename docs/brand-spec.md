# LatencyLedger — Brand / Marketing Specification

> **Source:** `docs/product-spec.md` (Idea/Concept §1), `docs/design-system.md`, `docs/architecture.md`, `README.md`
> **Product name:** LatencyLedger
> **One-line pitch:** Continuous API latency regression tracking with CI gates — know when your API got slower before your users do.
> **Constraints:** Organic + content only. No paid tools, no paid ads, no paid distribution. Self-hostable / stdlib-only positioning must be preserved. No uptime-only or status-page-only positioning (explicit non-goal / crowded-market risk).
> **Status:** SPEC ONLY — no code changes in this document.

---

## 1. Brand Identity

### 1.1 Name

**LatencyLedger** (from product spec §1)

- Wordmark: `LatencyLedger` — CamelCase in prose and headlines. Lowercase `latencyledger` only in URLs, repo paths, and code identifiers (`ll_` API-key prefix, `latencyledger` Docker image).
- Short form: "Ledger" is acceptable in internal copy after first mention (`LatencyLedger — the Ledger for your API's latency`). Never use bare "Ledger" as the product name in public launch copy; it collides with accounting/finance tools.
- Pronunciation: `lat-en-see-LED-jer` (two stresses hidden; guides voiceover).
- Domain / handles (to claim): `latencyledger.com` preferred; fallbacks `latencyledger.dev`, `latencyledger.io`. GitHub org/repo: `latencyledger/*`. X/Twitter, GitHub, HN, Product Hunt, dev.to, hashnode: `@latencyledger`.
- Never rename to a generic "API monitor / uptime monitor" — that is the crowded category LatencyLedger explicitly avoids (product spec §6–§7).

### 1.2 Tagline Options (3)

| # | Tagline | Angle | Best use |
|---|---|---|---|
| **A (recommended primary)** | **"Know when your API got slower — before your users do."** | Directly from product-spec pitch; loss-avoidance + empathy | Hero, HN/PH title, SEO title |
| **B** | **"Uptime says 'up.' LatencyLedger says 'how fast.'"** | Challenger vs. UptimeRobot/Better Stack; category split | Landing section header, social, conference talk title |
| **C** | **"The ledger your p95 can't hide in." / "Every millisecond, on the record."** | Ledger metaphor; evidence/accountability | Blog, public-report link footer, status-page footer |

**Selection rule:** Ship A as primary. Keep B as the challenger / comparison-page headline. Keep C for shareable-evidence surfaces (public reports, PR comments, postmortems). Do not A/B test paid variants — organic only; choose by qualitative feedback from first 100 users (§8).

### 1.3 Voice & Tone Guide

**Core feeling:** A calm on-call engineer who brought receipts. Evidence over decoration (design-system Principle 1). Quiet until it matters (Principle 2).

| Dimension | Voice (always) | Tone (adjust by context) |
|---|---|---|
| **Personality** | Precise, plain-spoken, slightly dry, trustworthy | Warm with users, blunt with abstractions ("green" ≠ "fast") |
| **Sentence length** | Short. One idea per sentence. Numbers get their own line. | — |
| **Vocabulary** | Latency vocabulary: `p50/p95/p99`, `baseline`, `drift`, `regression`, `budget`, `budget gate`, `sample`, `SHA`. Avoid: `synthetic`, `APM`, `observability platform` (APM is a non-goal). | — |
| **Evidence** | Always show the delta: `p95 212ms → 389ms (+84%) on abc123` — never "latency increased." | — |
| **Humor** | Dry, sparing, never at the user's expense. One joke per launch post max. | — |
| **Formatting** | Monospace for numbers/hashes/URLs. Bold for the verdict only (`**FAIL**`, `**PASS**`). | — |
| **Accessibility** | Status is never color-alone; always icon + text label (design-system requirement). Mirror this in copy: pair every status word with its number. | — |

**Tone ladder by surface:**
- **Marketing/landing:** Confident, benefit-led, second-person ("your users"). Tagline A register.
- **Product/alerts:** Terse, factual, no adjectives. Alert banner register: "p95 rose 212ms → 389ms" (design-system Alert banner).
- **Docs/errors:** Helpful, imperative ("Add a URL check", "Paste a URL"). Error copy names the fix ("non-https URL — use https://…").
- **Community/social:** Peer-to-peer, first-person plural ("we shipped", "what we learned"). Replies within 24h on HN/GitHub.

### 1.4 Do / Don't Phrasing

| ✅ Do | ❌ Don't |
|---|---|
| "Know when your API got slower — before your users do." | "Best API monitoring platform." (unverifiable superlative; also wrong category) |
| "p95 rose 212ms → 389ms vs the 7-day baseline (+20% threshold)." | "Latency increased." (no number, no baseline) |
| "Gate your PR on p95 < 400ms." | "Performance monitoring for enterprises." (wrong persona; APM is a non-goal) |
| "Paste a URL. Get p50/p95/p99 in <60 seconds." | "Zero-setup AI-powered observability." (no AI in P0; "zero-setup" is already strong and true) |
| "Self-host in one Docker command. No pip install." | "Cloud-native scalable solution." (vague; contradicts stdlib/self-host story) |
| "Your uptime is green. Your p95 just drifted +84%." | "Uptime monitoring with status pages." (that is the competitor's pitch and P1 only) |
| "Share the report: p95 regressed on commit abc123." | "Shareable analytics dashboard." (commodity phrasing) |
| "Flat $9/mo. No per-seat, per-incident billing." | "Affordable pricing." (weasel word — name the number) |

**Compliance note:** Never claim paid features exist (multi-region, ML anomaly, SSO/OAuth are P2; status pages P1). Launch copy must only promise P0: auth, URL checks, ping-now, history chart, regression alerts (email/webhook), API keys, CI gate, public reports, Docker self-host.

---

## 2. Visual Identity

Aligned to `docs/design-system.md`. No new palette; the design tokens *are* the brand.

### 2.1 Logo Concept (SVG-first)

**Concept: "The Ledger Line"** — a p95 line that draws itself into a ruled ledger entry, ending in a hard tick (the gate verdict).

- **Mark:** A minimal sparkline (p50 faint, p95 solid) rising left→right, underscored by two thin rules (ledger lines). The final segment terminates in a vertical tick — read as `|`, a gate/bar line, and a ledger entry mark. Left segment flat (baseline), right segment bends up (regression) — the story in one glyph.
- **Wordmark:** `LatencyLedger` in system stack semibold (matches design-system type; no custom font file — works offline, Principle 3). The `L` in Ledger can be heavier weight as a ligature with the mark's tick.
- **Hero/inverse:** Mark in `--accent #4f8cff` on `--bg #0f1115`; p95 line in `--p95 #b083f0` (true to the chart — the logo *is* the chart).
- **Favicon:** The tick + sparkline alone, 16×16 legible; no text.
- **SVG spec (designer brief):** Single-path sparkline on a 48×48 viewBox, stroke-width 3, round caps, two 1px horizontal rules at 25%/75%, final tick 6px tall. Provide: `logo.svg` (mark), `logo-word.svg`, `logo-mono.svg` (single-color #e6e9ee for docs/README), `favicon.svg`. All inline SVG, no raster required. Must remain legible at 16px and in monochrome.
- **Clear space:** Height of the tick on all sides. **Minimum size:** 24px digital (mark-only below that). **Never:** recolor p95 to green, add gradients, stretch the sparkline, place on busy imagery, or use the mark in red except in an actual regression context.
- **Public-report watermark:** Faint horizontal rules + tick (the logo at 8% opacity) beneath every public report chart — reinforces "on the record" without cluttering data.

### 2.2 Color Usage

Brand palette = design-system tokens. Do not introduce marketing-only colors.

| Token | Value | Brand use | Share of marketing surfaces |
|---|---|---|---|
| `--bg` `#0f1115` | App + landing background (dark default) | 60% |
| `--panel` `#171b22` | Cards, code blocks, feature tiles | 20% |
| `--text` `#e6e9ee` | Headlines, body | — |
| `--muted` `#9aa3af` | Captions, axes, secondary copy | — |
| `--accent` `#4f8cff` | Primary CTA, links, p50 line | 8% |
| `--ok` `#34c07c` | "Healthy / PASS" only — sparingly | 4% |
| `--p95` `#b083f0` | p95 line, "the number that matters" callouts | 4% |
| `--warn` `#e8b23a` | Near-budget only | 2% |
| `--bad` `#e5534b` | Regression / FAIL only — never decorative | 2% |

**Rules:** Dark-first marketing pages (matches product). Every status color paired with icon + label. Green is earned (only beside a real p95 number). Red appears only on genuine regression examples — never as a CTA color. Contrast: text-on-bg ≥7:1 (design-system standard) applies to landing copy too.

### 2.3 Imagery Guidelines

1. **Screenshots are the imagery.** Real dashboard, real chart, real numbers. No stock photos of servers, rockets, or "teams collaborating." If it isn't a chart, a terminal, or a GitHub Actions YAML block, it doesn't ship.
2. **Show the bend.** Hero/OG image: p50 flat, p95 bending up, SHA tick at the bend, baseline dashed. Annotated with three mono labels only: `212ms`, `389ms`, `abc123`.
3. **Terminal-first secondary imagery:** `$ python3 -m app.main` and the one-block GitHub Actions YAML are brand icons. Screenshot them on `--panel` with mono font.
4. **People (sparse):** If people appear at all, they are the user's own users being protected ("before your users do") — abstract, never fake testimonial faces. No illustrated mascots (off-voice; "quiet until it matters").
5. **Charts have text summaries** (`role="img"` + caption) on every marketing page image — a11y is a brand signal, not an afterthought.
6. **No CDN-dependent visuals.** All images inline SVG or self-hosted PNG/WebP; the product works offline and the marketing should not contradict that.

---

## 3. Messaging

### 3.1 Positioning Statement

> **For** solo developers and small teams (2–20 devs) building REST APIs and SaaS backends who care about p95 but can't justify Datadog/New Relic,
> **LatencyLedger is a** continuous API latency-regression tracker with CI gates
> **that** alerts you when p95 drifts +20% above its rolling baseline — even while uptime still says "200 OK" —
> **unlike** UptimeRobot/Better Stack (uptime-first, latency as an afterthought) and Bencher/Gatling Cloud (benchmark harness, not live-endpoint drift),
> **our product** treats latency trend vs. baseline as the first-class alert, gates PRs on percentile budgets, needs no agent, and self-hosts in one Docker command.

**Category:** "Latency regression tracking" — *not* "uptime monitoring," *not* "APM," *not* "synthetic monitoring." Category discipline is the moat (product spec §6–§7).

### 3.2 Value Props per Persona

| Persona | Pain (their words) | LatencyLedger value prop | Proof point |
|---|---|---|---|
| **Indie hacker / solo dev** (primary) | "I found out my API was slow from a user complaint, 3 days late." | Paste-URL checks; regression alert before users notice; flat $9, no per-seat math | p95 `212→389ms` alert example; <60s to first chart |
| **Small-team founder / tech lead** (2–20) | "Someone shipped an N+1 and we didn't notice for a sprint." | CI gate: fail the PR when p95 > budget; SHA annotation on every drift | `POST /gate {p95_ms:400} → 422` on the offending commit |
| **Platform / DevOps-lite** | "We need perf budgets but our APM bill is absurd for this." | Percentile budgets without an agent; self-host for data that can't leave the building | `docker compose up`, stdlib-only, no pip install |
| **CI-conscious contributor / OSS maintainer** | "Benchmarks in CI are heavy; I just want live endpoints watched." | One YAML block gates the build; public report links for PR comments | GitHub Actions example YAML; `/r/{slug}` shareable evidence |

Non-personas (do not target): enterprises needing APM/traces, mobile/browser perf teams (Lighthouse), load testers (k6/Gatling) — all explicit non-goals.

### 3.3 Elevator Pitches

**30-second (HN comment / meetup / intro DM):**

> "LatencyLedger watches your API's p95 continuously. Uptime tools tell you it's 'up' — we tell you it quietly got 84% slower last Tuesday, on commit abc123, and we can fail the CI build that did it. Paste a URL, get p50/p95/p99 and a baseline in under a minute, self-host with one Docker command. Flat nine bucks, no per-seat billing."

**3-minute (demo / podcast / blog walkthrough):**

> **(0:00–0:30) Problem.** "Your uptime dashboard is green. Your API is still 200 OK. But p95 drifted from 212 to 389 milliseconds after a deploy nobody benchmarked — classic N+1, missing index, or a chatty AI-generated query. Users feel it before any uptime tool fires, and churn follows. The gap isn't more uptime checks; it's a tool that treats *latency trend vs. baseline* as the alert."
>
> **(0:30–1:30) Product.** "LatencyLedger polls your URL on a schedule — one minute to an hour — stores every sample, computes p50, p95, p99, and compares against a rolling seven-day baseline. When p95 rises more than twenty percent, you get one alert, not a pager storm: a 6-hour cooldown means you hear it once. Every chart is annotated with the git SHA, so the drift points at the commit. And because it's running in your CI, you can gate a pull request on a latency budget — post a target p95, get a pass or fail back, in one YAML block."
>
> **(1:30–2:15) Differentiation.** "Three things the big tools don't do for small teams: one, the regression alert *is* the product, not a secondary stat; two, it works on a plain public URL with no agent to install; three, it self-hosts in one Docker command — no pip install, no third-party keys — because latency data is often data you can't ship to a vendor."
>
> **(2:15–3:00) Close + ask.** "Free tier is three checks, hosted or self-hosted. Pro is nine dollars a month flat — no per-seat, no per-incident billing. Try it on your slowest endpoint first; the first regression alert is the demo. If it catches anything, share the public report link — that's how the next person finds us."

---

## 4. Landing Page — Full Copy Draft

*Single-page, dark-first, max width 1080px (design-system layout). All numbers are illustrative examples; ship with a live `/r/{slug}` demo report embedded, not a fake screenshot.*

---

**Header nav:** Logo `LatencyLedger` · Features · Pricing · Docs · GitHub · `[ Start free ]`

**Hero**
- **Eyebrow (mono):** `CONTINUOUS API LATENCY REGRESSION TRACKING`
- **H1 (Tagline A):** Know when your API got slower — **before your users do.**
- **Sub:** Uptime says "up." LatencyLedger tells you how fast — p50/p95/p99 vs. a rolling baseline, with a CI gate so the PR that slowed you down fails the build.
- **CTAs:** `[ Start free — 3 checks ]` `[ Self-host the Docker image ]`
- **Micro-proof (mono):** `$ python3 -m app.main  →  http://localhost:8000` · No pip install · No API keys
- **Hero visual:** The bend chart — p50 flat `#4f8cff`, p95 bending `#b083f0`, baseline dashed, SHA tick `abc123`; labels `212ms` → `389ms`. Caption: "A regression your uptime tool called 'green.'"

**Section — The gap (Tagline B)**
- **H2:** Uptime says "up." LatencyLedger says "how fast."
- **Body:** A 200 OK response can take 40ms or 4 seconds. UptimeRobot and Better Stack check the first; accidental N+1 queries live in the second. LatencyLedger watches the trend — not just the status — and alerts when p95 drifts +20% above its 7-day baseline while everything still looks green.

**Section — How it works (3 steps)**
- **H2:** Paste a URL. Get the ledger.
- **1. Add a check.** `https://api.yourapp.com/users` — interval from 1 minute to 1 hour. <60 seconds to your first p50/p95/p99 + sparkline.
- **2. Watch the baseline.** Every sample is stored. The chart draws p50 and p95 against a rolling baseline; each deploy's SHA is a tick on the line.
- **3. Get alerted on drift — or gate the build.** p95 > +20% vs. baseline (min 50 samples, 6h cooldown) → email/webhook with the delta. In CI, `POST /gate {p95_ms: 400}` returns pass/fail for your budget.

**Section — Code (CI-native)**
- **H2:** Gate the PR, not just the page.
- **Body:** One YAML block. The commit that blows the latency budget fails the build — with the observed p95 in the log.
- **Code block:**
```yaml
- uses: latencyledger/gate@v1
  with:
    check: ${{ vars.LL_CHECK_ID }}
    budget-p95-ms: 400
    api-key: ${{ secrets.LL_API_KEY }}
```
- **Link:** `See the full GitHub Actions example →`

**Section — Evidence (shareable)**
- **H2:** Every slowdown, on the record.
- **Body:** Toggle a check public and share a read-only report for postmortems and PR comments. No login, no leaked settings — just the chart, the numbers, and the commit.
- **Visual:** Public report card: `p95 regressed 212ms → 389ms on commit abc123` with mini-chart. `[ View a live public report → ]`

**Section — Pricing (flat, honest)**
- **H2:** Flat pricing. No per-seat math.
- **Free ($0):** 3 checks · 5-min intervals · 7-day history · 1 email alert channel · public reports · self-host
- **Pro ($9/mo):** 25 checks · 1-min intervals · 90-day history · email + webhook + chat alerts · unlimited CI gates
- **Team ($29/mo):** 100 checks · multi-region (P2, coming) · status pages (P1) · self-host
- **Microcopy:** "Self-host is free forever. Hosted pricing is flat — never per-seat, never per-incident."

**Section — FAQ**
- **How is this different from UptimeRobot / Better Stack?** They alert on downtime and treat latency as a secondary stat. LatencyLedger's first-class alert is latency *drift vs. baseline* — plus a CI gate. Uptime alone is the gap we fill.
- **Do I need to install an agent?** No. LatencyLedger checks a plain public URL. No instrumentation, no SDK.
- **What counts as a regression?** p95 rises >20% above a rolling 7-day baseline with ≥50 samples. Alert fires once per 6 hours (cooldown) — no pager storms. Threshold is tunable per check.
- **Can it fail my CI build?** Yes — `POST /api/v1/checks/{id}/gate` with `{p95_ms: N}` returns 200 (pass) or 422 (fail with observed p95), using an `ll_…` API key.
- **Can I self-host?** Yes — `docker compose up`, Python stdlib only, no pip install, no third-party keys to boot. SQLite included; Postgres path documented.
- **Is my data private?** Checks are private by default. Public report links are opt-in, read-only, and leak no keys or settings. SSRF guard blocks private/loopback targets.
- **What does it not do?** Browser/Lighthouse perf, load testing (k6/Gatling), full APM/tracing. Deliberately — those are different tools with different bills.

**Final CTA**
- **H2:** Your next slowdown is already deployed. Watch it.
- **Sub:** Add your slowest endpoint first. The first drift alert is the demo.
- **CTAs:** `[ Add your first check — free ]` `[ Read the docs ]`

**Footer**
- Logo + Tagline C: "Every millisecond, on the record."
- Columns: **Product** (Features, Pricing, Changelog, Roadmap) · **Docs** (Quickstart, CI gate guide, API reference, Self-host) · **Community** (GitHub, HN launch thread, Discord/Slack, dev.to) · **Legal** (Privacy, Security disclosure, MIT License)
- Bottom line (mono): `© 2026 LatencyLedger · MIT · Built stdlib-only — works offline` + `GET /healthz` status dot with `operational` text label.

**SEO skeleton (see §6):** Title `LatencyLedger — API Latency Regression Tracking with CI Gates` · Meta description uses Tagline A + "p95 alerts & CI latency budgets; self-hostable." · H1 = Tagline A (never two H1s).

---

## 5. Launch Content

### 5.1 Announcement Blog Post Draft

**Title:** Your uptime is green. Your p95 just drifted +84%. I'm launching LatencyLedger.

**URL:** `/blog/latencyledger-launch`

---

Your uptime dashboard is green. Status: 200 OK. Everyone is calm.

Meanwhile, p95 went from 212ms to 389ms after Tuesday's deploy. Nobody noticed for three days — until a user did, in a support ticket, with the word "slow" in it.

That gap — between *up* and *fast* — is the entire reason LatencyLedger exists.

## The problem nobody dashboards

Every API team I've talked to has the same story: an accidental N+1 query, a missing index, a chatty ORM call from AI-generated code that "worked" in review. The endpoint never went down. It just got slower, gradually, and every uptime tool called it healthy because latency is a secondary stat in their model.

UptimeRobot and Better Stack are good at what they are. But they will never page you for drift, because drift isn't downtime — it's a trend. And Datadog APM will happily show you the trend for a per-host price that makes no sense for a two-person team.

## What LatencyLedger does

LatencyLedger polls your URL on a schedule (1 minute to 1 hour), stores every sample, and computes the percentiles that matter — p50, p95, p99 — against a rolling 7-day baseline. When p95 rises more than 20% above that baseline, you get **one** alert: email or webhook, with the delta, the baseline, and the git SHA that preceded the drift. A 6-hour cooldown means you hear it once, not forty times.

Three details matter:

**No agent.** It checks a plain public URL. Paste it, get percentiles in under a minute.

**CI-native.** You can gate a pull request on a latency budget. `POST /gate` with `{p95_ms: 400}` returns pass or fail, so the commit that blows the budget fails the build — in one YAML block.

**Shareable evidence.** Toggle a check public and get a read-only report link for postmortems and PR comments: "p95 regressed 212ms → 389ms on commit abc123." No login, no leaked settings.

## Why it's self-hostable

Latency data is often data you can't ship to a vendor. So LatencyLedger runs on Python's standard library alone — no pip install, no third-party keys to boot, `docker compose up` and you're on `localhost:8000`. SQLite included. If you outgrow it, the Postgres path is documented, and the scheduler splits into a separate worker with one env flag.

## Pricing, stated plainly

Free: 3 checks, 7-day history, an email alert, self-host. Pro: $9/month flat — 25 checks, 1-minute intervals, 90 days, webhooks, unlimited CI gates. No per-seat, no per-incident billing. The bill should never be the reason you skip a check.

## Try it on your slowest endpoint

That's my honest suggestion: don't add your homepage. Add the endpoint you're already nervous about. If LatencyLedger catches a drift in the first month, share the public report — that's how the next person finds it.

Repo, docs, and the GitHub Actions example are linked below. I'm hanging around the launch thread today answering everything — especially "how is this different from X," which is fair, because latency-drift tooling for small teams is genuinely thin right now.

Every millisecond, on the record.

— *LatencyLedger*

**Links:** [Start free](/) · [Self-host (Docker)](docs) · [CI gate guide](docs) · [GitHub repo](https://github.com/devhasen/http-ping)
**Tags:** `api-latency`, `p95`, `ci-gates`, `uptime`, `indie-hacker`, `devops`, `self-host`, `launch`

---

### 5.2 Five Social Posts

1. **X / Bluesky (launch, Tagline A):**
   > Your uptime is green. Your p95 just drifted +84%. I launched LatencyLedger — continuous API latency regression tracking with a CI gate, so the commit that slowed you down fails the build. Paste a URL, get p95 vs. baseline in <60s. Self-host in one Docker command. [link] #buildinpublic
2. **Hacker News (Show HN title + first comment):**
   > Title: `Show HN: LatencyLedger — Know when your API got slower, before your users do`
   > First comment: "LatencyLedger is a latency-*drift* tracker, not another uptime checker. Uptime tools treat latency as a secondary stat; we make p95-vs-baseline the alert (+20% rule, 6h cooldown), annotate every chart with the git SHA, and gate CI on p95 budgets. Stdlib-only Python, `docker compose up`, no agent. Free 3 checks, $9 flat. Happy to answer architecture or false-positive questions — the detector is the interesting part."
3. **Mastodon / dev.to (story, Tagline B):**
   > "Uptime says 'up.' Let me tell you how fast. ▸ I watched an endpoint sit at 200 OK for a week while p95 went 212ms → 389ms. No uptime tool fired — nothing was *down*. So I built the tool I wanted: baseline drift alerts + a CI gate on p95. Launch post + demo inside. Every millisecond, on the record."
4. **LinkedIn (professional, persona-led):**
   > Small-team APIs have a blind spot: gradual latency drift. It isn't downtime, so uptime tools miss it; APM is priced for enterprises, so small teams skip it. LatencyLedger fills the gap — continuous p95-vs-baseline tracking, commit-annotated charts, and a CI gate that fails the PR blowing the latency budget. Flat $9/mo, self-hostable with one Docker command. Launching today — would love feedback from platform and backend engineers.
5. **GitHub (repo description + discussion, community):**
   > Repo tagline: "Continuous API latency regression tracking with CI gates — know when your API got slower before your users do." Discussion starter: "What's your latency budget? We're collecting real-world p95 budgets for common endpoints (auth, search, CRUD) to publish a benchmark table. If you self-host LatencyLedger, drop your budget + p95 here — most useful answer gets added to the docs."

### 5.3 Launch-Kit Outline (Product Hunt / Hacker News)

**Product Hunt**
- Name: LatencyLedger
- Tagline (60 chars): "Know when your API got slower — before your users do." (Tagline A, verbatim)
- Description: Positioning statement (§3.1), compressed to 260 chars + 3-bullet "first regression alert is the demo" hook.
- Gallery (5): (1) Hero bend chart, (2) Dashboard stat tiles, (3) CI YAML + FAIL log, (4) Public report link, (5) `docker compose up` terminal. Alt text = text summary for each (a11y).
- Topics: Developer Tools, API, Monitoring, Open Source, SaaS.
- First comment (maker): 30s pitch (§3.3) + "try it on your slowest endpoint" ask + live demo `/r/` link.
- Maker reply banking: pre-draft 6 replies (vs. UptimeRobot, vs. Datadog, pricing, self-host, false positives, "is this just a cron job?").

**Hacker News (Show HN)**
- Title: `Show HN: LatencyLedger — API latency regression tracking with CI gates`
- Body: 3-min pitch (§3.3) + technical note (stdlib-only, detector rule `+20% p95 vs 7-day baseline, ≥50 samples, 6h cooldown`, SSRF guard, SQLite/WAL) + explicit non-goals (not APM, not load testing) to pre-empt "another monitor?" + ask (budgets + false-positive feedback).
- Timing: Tue–Thu, 8–10am US ET (HN peak). Author present for 4h. No vote-begging, no sock-puppets.
- Follow-up: "One month later" HN post + dev.to post with real drift stories (with permission) — the retention loop.

**Shared assets checklist (no paid tools):** OG image (1200×630, bend chart), logo SVG set (§2.1), 30s GIF of "paste URL → first chart" (self-hosted, <5MB), README badge row, `llms.txt` for AI crawlers (see §6), press kit as a single Markdown page (`/press`) — no PDF required.

---

## 6. SEO

### 6.1 Keywords (12 — primary + long-tail)

| # | Keyword | Intent | Page to rank |
|---|---|---|---|
| 1 | `api latency monitoring` | Commercial/informational | `/` (home) |
| 2 | `p95 latency regression detection` | Informational (niche, ownable) | `/` + blog |
| 3 | `ci gate latency budget` | Transactional (developer) | `/blog/ci-latency-gate` |
| 4 | `api latency monitoring for small teams` | Commercial | `/` + `/pricing` |
| 5 | `uptime vs latency monitoring difference` | Comparison (Tagline B) | `/blog/uptime-vs-latency` |
| 6 | `how to monitor API response time p95` | How-to | `/docs` + blog |
| 7 | `detect slow api endpoint before users` | Problem | `/` hero + blog |
| 8 | `self hosted api monitoring docker` | Transactional (self-host) | `/docs/self-host` |
| 9 | `github actions api latency check` | How-to | `/docs/ci-gate` |
| 10 | `latency drift alert baseline` | Informational (niche) | `/blog/latency-drift-alerts` |
| 11 | `api performance regression in ci` | Informational | `/blog/perf-regression-ci` |
| 12 | `cheap alternative to datadog APM small team` | Comparison (careful, factual) | `/blog/datadog-alternative` |

**Keyword discipline:** Never rank for bare `uptime monitoring` (saturated, wrong category). Own the *drift + CI gate* intersection. Each keyword maps to exactly one canonical page — no cannibalization.

### 6.2 Metadata Templates

**Home `/`**
```html
<title>LatencyLedger — API Latency Regression Tracking with CI Gates</title>
<meta name="description" content="Know when your API got slower — before your users do. LatencyLedger alerts on p95 drift vs. baseline and gates CI on latency budgets. Free, self-hostable.">
<meta property="og:title" content="Know when your API got slower — before your users do.">
<meta property="og:description" content="Continuous p95 tracking, commit-annotated charts, CI latency gates. No agent. One Docker command.">
<meta property="og:image" content="/og/hero-bend.png">
<meta name="twitter:card" content="summary_large_image">
```
**Docs `/docs`:** `<title>{Page} | LatencyLedger Docs</title>` + `<meta name="description" content="{one-sentence imperative summary} — LatencyLedger {category}.">`
**Blog `/blog/{slug}`:** `<title>{H1} — LatencyLedger Blog</title>` + `article:published_time`, `author`, `og:type=article`.
**Public report `/r/{slug}`:** `noindex` on the *list*, `index` on individual opt-in reports with title `p95 report: {check-name} — LatencyLedger` (shareable evidence = backlinks).
**Global:** Canonical to trailing-slash-free URL, `robots` allow `/`, disallow `/api/*`, `llms.txt` at root summarizing product, pricing, and docs links for AI crawlers.

### 6.3 Sitemap

```
/                          → home (Tagline A)
  /pricing
  /docs
    /docs/quickstart
    /docs/ci-gate
    /docs/self-host
    /docs/api-reference
    /docs/security
  /blog
    /blog/latencyledger-launch
    /blog/uptime-vs-latency
    /blog/ci-latency-gate
    /blog/latency-drift-alerts
    /blog/perf-regression-ci
    /blog/datadog-alternative
  /press                   → launch kit (Markdown → HTML)
  /r/{slug}                → public reports (indexed only when opted public)
  /sitemap.xml  /robots.txt  /llms.txt  /rss.xml (blog feed)
```
Priorities: `/` (1.0), `/pricing` + `/docs` (0.8), `/blog/*` (0.6), `/r/*` (0.4). Changefreq: home weekly, blog monthly, docs on release. Generate `sitemap.xml` from the docs/blog file list at build — never hand-maintain.

---

## 7. Launch Checklist (Organic + Content Only)

### Pre-launch (T-14 to T-1)
- [ ] Landing page (§4) live; H1 = Tagline A; OG/hero-bend image set; `sitemap.xml`, `robots.txt`, `llms.txt`, RSS live.
- [ ] Demo public report `/r/demo` seeded with a visible bend + SHA tick (the screenshot is a live link).
- [ ] `/docs/quickstart` + `/docs/ci-gate` + `/docs/self-host` complete; GitHub Actions YAML tested end-to-end (pass + 422 fail).
- [ ] Blog launch post (§5.1) scheduled; 3 follow-up drafts (`uptime-vs-latency`, `ci-latency-gate`, `latency-drift-alerts`) outlined so launch isn't a one-day spike.
- [ ] Social kit (§5.2 ×5) + PH/HN kits (§5.3) drafted; maker replies banked (6).
- [ ] Logo SVG set + favicon (§2.1) exported; README badge row; GitHub repo topics: `api-latency`, `p95`, `uptime`, `ci`, `self-hosted`, `monitoring`.
- [ ] Analytics: privacy-friendly, no cross-site tracking (Plausible/Umami self-hosted or Fathom) — do not add Google Analytics to a "data you can't ship" product.
- [ ] `GET /healthz` + self-monitoring verified; status dot in footer shows real state.
- [ ] Soft-launch: 5–10 target users (indie hackers, OSS maintainers) get early access + feedback form. Fix the top 3 frictions before public.

### During launch (Day 0–1)
- [ ] 08:00 ET: Publish blog post → post to dev.to + hashnode (canonical to own blog) → X/Bluesky post #1.
- [ ] 09:00 ET: Show HN live; author present 4h; reply to every comment; never upvote own post.
- [ ] 00:01 PT: Product Hunt live (schedule in PH); first comment = 30s pitch + demo link; reply cadence <30min for 6h.
- [ ] 12:00 ET: Mastodon/dev.to story (#3); LinkedIn (#4); GitHub discussion #5 with budget-collection prompt.
- [ ] Track in real time: signups, first-check activation (target ≥40% in 24h), time-to-first-chart (target <5min median), HN/PH rank, referral source.
- [ ] Log every question verbatim — these become FAQ + follow-up blog titles.

### Post-launch (Day 2–30)
- [ ] Day 2: Thank-you post (HN "one month later" teaser + X) with what was learned; reply to all PH/HN threads.
- [ ] Day 7: Publish follow-up #1 (`uptime-vs-latency`, Tagline B) — the comparison keyword page.
- [ ] Day 14: Publish follow-up #2 (`ci-latency-gate`) with real CI YAML walkthrough + GIF.
- [ ] Weekly: 1 blog/dev.to post, 3 social posts (one real drift story with permission, one how-to, one peer reply spree in r/selfhosted, r/devops, Indie Hackers, Lobsters).
- [ ] Day 30: Retro against product-spec KPIs — activation ≥40%, W4 retention ≥25%, free→paid ≥3%, ≥30% Pro users with ≥1 true alert. Publish the retro publicly (transparency is the brand).
- [ ] SEO: submit sitemap to Search Console; check keyword pages indexing (§6.1); request manual review only if a page is dropped — never buy links.

---

## 8. Community Playbook — First 100 Users

**Goal:** 100 *activated* users (added ≥1 check), not 100 signups. Activation ≥40% in 24h is the product-spec target — the playbook serves that number.

### 8.1 Where the first 100 come from (organic only)

| Channel | Tactic | Expected yield |
|---|---|---|
| **Hacker News** | Show HN launch (§5.3) + "1 month later" follow-up | 30–40 |
| **Product Hunt** | Launch day + maker engagement | 10–20 |
| **GitHub / OSS** | Repo stars → self-hosters → hosted Pro conversion (product-spec CAC assumption) | 15–25 |
| **Indie Hackers / Lobsters / r/selfhosted / r/webdev** | Launch post + genuinely helpful replies (never link-drops) | 10–15 |
| **Word of mouth** | Public report links shared in PRs/postmortems ("on the record") | 5–10 (compounds) |
| **dev.to / hashnode** | 4 launch-post syndication + weekly how-tos | 5–10 |

No paid tools, no ads, no bought lists, no upvote brigades. Every post must earn its link.

### 8.2 The first-100 operating cadence

- **Every new user gets a human reply within 24h** (email or in-app). Ask one question: *"What's the slowest endpoint you'll point this at first?"* That answer is onboarding, research, and copy at once.
- **First-check concierge:** If a signup hasn't added a check in 24h, send one email with the exact click path + the GitHub Actions YAML. Not a drip sequence — one helpful email.
- **First-alert follow-up:** When a user's first regression alert fires, email once: "Did it match what you suspected? Reply here." Target: alert precision ≥70% (product-spec KPI). Every "false positive" reply is a detector-tuning ticket.
- **Weekly "100 users" digest to the team (solo):** new signups, activated %, first-check median time, alert count + precision, top verbatim question. Post the public version monthly (the retro in §7).

### 8.3 Community assets (build once, reuse)

- **GitHub Discussions:** `Show and tell` (public reports), `Budgets` (real p95 budgets — feeds the keyword pages), `False positives` (detector tuning, public).
- **Budget benchmark table:** A living docs page of real-world p95 budgets by endpoint type (auth/search/CRUD), seeded from the discussion. This is the SEO + community flywheel: users contribute budgets → page ranks → more users.
- **Contrib path:** `CONTRIBUTING.md` already exists — add "first alert precision report" as a Good First Issue category (stats/detector tests).
- **Swag-free recognition:** Public "drift catchers" board (opt-in): handles + the p95 delta caught. No merch, no discounts — recognition only (paid tools are out; so is pay-to-win positioning).
- **Anti-patterns (never):** DM spam, HN/PH vote manipulation, review-gating, buying newsletter placements, comparing against Datadog with unverifiable claims. The brand is receipts; the community is the proof.

### 8.4 Exit criteria for "first 100"

- 100 activated users (≥1 check) with ≥25% W4 retention among the first cohort.
- ≥30% of Pro users received ≥1 true regression alert in their first 30 days.
- Every §6 keyword page indexed; at least one blog post in top-3 for a long-tail keyword (§6.1 #2/#10).
- Retro published; next cohort's onboarding updated from verbatim feedback.

---

## Appendix — Cross-References & Open Items

- **Upstream truth:** Name, pitch, personas, pricing, KPIs, non-goals, differentiation — all from `docs/product-spec.md` §§1–7. This spec invents no features and promises no P1/P2 features (status pages, multi-region, ML anomaly, SSO) in launch copy.
- **Visual truth:** All color/type/motion values are `docs/design-system.md` tokens verbatim (§2). The logo concept (§2.1) is a new brief for a designer — it must be delivered as inline SVG consistent with the chart's p50/p95 encoding.
- **Stack truth:** "Stdlib-only, no pip install, one Docker command" (README + `docs/architecture.md`) is a marketing pillar — verify any future copy change against the actual boot command.
- **Open items for the team:** (1) Confirm final Tagline A vs. B via first-100 feedback (§1.2). (2) Claim domains/handles (§1.1) before launch. (3) Seed `/r/demo` with a realistic bend (not synthetic-perfect). (4) Decide blog platform (self-hosted static vs. dev.to-primary with canonical) — must support `sitemap.xml` + RSS + `llms.txt`.

---

*SPEC ONLY — no product code changed. Next step: land the landing page and demo report per §4, then execute §7.*
