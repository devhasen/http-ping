# LatencyLedger — Monetization Spec

> **Owner:** Desk-14, Financial Analyst / Monetization Lead · **Status:** Spec only — do not build features yet
> **Product:** LatencyLedger (repo `devhasen/http-ping`) — continuous API latency-regression tracking + CI gates. Note: `httpping` CLI is the free acquisition wedge.
> **Companions:** `docs/product-spec.md` (PM, desk-1) · `docs/architecture.md` · `docs/ops-growth-spec.md` (desk-5) · `docs/roadmap.md`
> **Hard constraint:** launch must boot and run with **$0 billing infrastructure and no Stripe keys**. Paid plans are a manual/stub toggle until a provider is wired in (see §4).
> **Currency:** USD. Prices are launch hypotheses for the 90-day window, stated so they can be tested (§6), not final.

---

## 1. Pricing model

### 1.1 Recommended tiers (launch)

Reconciled from `product-spec.md` §4 (Free / Pro $9 / Team $29) and `ops-growth-spec.md` §2 (same prices, richer limit detail — interval/regions/seats). Where the two docs differ on chip size, this spec adopts the ops doc's fuller matrix and flags the delta.

| | **Free** | **Pro** | **Team** |
|---|---|---|---|
| Price | $0 forever | **$9/mo** per workspace (monthly) · **$90/yr** annual | **$29/mo** per workspace (monthly) · **$290/yr** annual |
| URL checks (monitors) | 3 | 25 | 100 |
| Min check interval | 5 min | 30 s *(product-spec: 1 min — see Note A)* | 10 s *(product-spec: 1 min + multi-region)* |
| Regions | 3 (US/EU/Asia) | 8 | 12 + custom |
| History / retention | 7 days | 90 days | 13 months (1 year) |
| Percentiles | p50/p95 | p50/p95/p99 + histograms | + SLO burn-rate views |
| Regression alerts (core wedge) | 1 channel (email) | email + webhook + Slack/Discord | all + PagerDuty/Opsgenie, on-call rotations |
| CI gates | 1 project | unlimited | unlimited |
| Public report links (`/r/{slug}`) | yes | yes | yes + custom domain |
| Status page | basic public URL | custom domain + branding | multi-product, SLA reports |
| Projects | 1 | unlimited | unlimited |
| Seats | 1 | 3 | unlimited |
| API rate limit | 60/min | 300/min | 1,000/min |
| API access | read-only | full | full + audit log |
| Export (CSV/JSON) | — | yes | yes |
| Support | community (GitHub) | email, 48h | email, 24h + priority |
| Self-host (Docker) | yes (community) | — | yes |

**Note A — interval delta to resolve with PM:** `product-spec.md` says Pro/Team are both "1 min min"; `ops-growth-spec.md` says 30 s / 10 s. This spec **adopts 30 s Pro / 10 s Team** because interval is the single most felt upgrade trigger (§3) and matches competitors (Better Stack 30 s, UptimeRobot 30 s on Team, StatusCake 30 s on top tier). If build ships 1-min-only in sprint 1, Pro's price justification rests on monitors + retention + alert channels instead — acceptable, but re-test in §6 Exp. 2. Do not ship 10 s until the scheduler can sustain it (ingest + SQLite headroom — see §2.4).

**Annual discount:** 2 months free (Pro $90 vs $108, Team $290 vs $348) ≈ 17% off. This is deliberate: annual billing materially cuts churn (see §2.2) and pulls cash forward. **Grandfather:** launch-promo users keep their rate while continuously subscribed (ops §2.1).

### 1.2 Feature matrix (paywall lines)

| Feature | Free | Pro | Team |
|---|:---:|:---:|:---:|
| CLI `httpping` + GitHub Action | ✅ | ✅ | ✅ |
| Hosted HTTP(S) checks, p50/p95 | ✅ | ✅ | ✅ |
| Regression detector (+20% p95 vs 7-day baseline) | ✅* | ✅ | ✅ |
| Public report link, status badge | ✅ | ✅ | ✅ |
| Check interval < 5 min | — | ✅ | ✅ |
| More than 3 monitors / 3+ regions | — | ✅ | ✅ |
| p99 + histograms, 90-day history | — | ✅ | ✅ |
| Webhook / Slack / Discord alert channels | — | ✅ | ✅ |
| Keyword/body validation, TLS/cert-expiry alerts | — | ✅ | ✅ |
| P95-threshold alerts, CSV/JSON export | — | ✅ | ✅ |
| Multi-step / transaction checks | — | — | ✅ |
| PagerDuty/Opsgenie, on-call rotations, SLO views | — | — | ✅ |
| Teams/workspaces + roles (P2) | — | — | ✅ |

\* Free gets the detector on its 3 checks/1 channel — *the wedge must be felt on Free*, or nobody converts. What Free withholds is **scale and channels**, not the core insight. This matches the ops §2.2 matrix.

### 1.3 Per-unit / overage pricing

**No per-unit overage at launch.** Limits are hard caps enforced server-side (product-spec §4: `plan_limits` table checked on check-create + ingest; over-limit → `402` + upgrade link; architecture.md schema already includes `plan_limits(plan, max_checks, min_interval_sec, history_days)`). Rationale:

- Overage billing without a real provider (§4) means manual reconciliation from day one — pure toil for < $100 MRR.
- Hard caps are the upgrade trigger (§3): "You've used 3/3 monitors" converts better than a metered surprise bill.
- **Post-Stripe candidate (test in §6):** a "check credit" add-on (e.g. $1 per 10k checks) for users who burst past 25 monitors — only if support tickets show demand. Do not build before then.

### 1.4 Competitive positioning (researched, Oct–Nov 2026)

| Competitor | Entry paid | Free tier | Where LatencyLedger sits |
|---|---|---|---|
| UptimeRobot | ~$13/mo (10 monitors) / $39 (100) | 50 monitors, 5-min | Below on price, narrower (latency-first, not uptime breadth) |
| Better Stack | $34/seat/mo incl. 10 monitors; +$25 per 50-monitor block | 10 monitors, 3-min | **Well below** ($9 vs $34 floor) — the "too small for Better Stack" gap |
| StatusCake | ~$24/mo (100 monitors) | 10 monitors, 5-min | Below; StatusCake wins on raw monitor count, loses on CI gate + CLI |
| Pingdom (SolarWinds) | ~$10–18/mo (10 checks, no free tier) | none | Far below; Pingdom sells depth/brand to enterprise |

LatencyLedger's wedge is **price + p95/CI**, not monitor volume. Pro at $9 undercuts every paid competitor's floor while covering the indie/SMB pain (regression before users notice). Team at $29 undercuts UptimeRobot Team ($39) and StatusCake Business ($80) at 100 monitors.

Sources: competitor pricing as published on vendor pricing pages and corroborated by 2026 third-party comparisons (UptimeRobot/Better Stack/StatusCake/Pingdom — see Sources at end).

---

## 2. Unit economics

### 2.1 Definitions & stated assumptions

| Metric | Assumption / value | Basis |
|---|---|---|
| ARPU (gross, blended) | **$12.00/mo** = 85% Pro ($9) + 15% Team ($29) | Mix hypothesis: most payers are solo/indie on Pro; Team is expansion. Revisit after 30 payers. |
| ARPU after payment fees | **≈ $11.35/mo** | Stripe US 2.9% + 30¢: Pro nets $9 − $0.56 = $8.44; Team nets $29 − $1.14 = $27.86; blended fee $0.65. Fees sourced from Stripe's published pricing. |
| ARPU (annual-blended) | ≈ **$10.10/mo net** if 30% of payers bill annually (2 months free) | Annual discount reduces gross ARPU ~17% on that cohort. Model conservatively at $11 gross until mix is known. |
| Gross margin | **~80%** (subscription-only) | Hosting is one small VPS + SQLite (architecture: stdlib + SQLite, single container). COGS = VPS ($6–20/mo) + email (FileTransport at launch, $0) + bandwidth. Benchmark: 2025 B2B SaaS subscription gross margin median ≈ 81% (Drivetrain), 74–80% by ARR band (2025 SaaS Benchmarks). At our scale, fixed COGS spread over few users pushes margin down initially, then up — model 75% in year 1, 82% by month 12. |
| Avg. paying lifetime | **~17 months** (1 / 6% monthly churn) | SMB SaaS median monthly churn ≈ 5.8% (RevMine, 500+ SaaS cos, 2024 data); Stripe/Churnkey: 4.0% overall SaaS. We model 6% conservative → 5% base → 4% optimistic (annual billing skews lower). |
| LTV (gross-margin-adjusted) | $12 × 17 mo × 80% ≈ **$163** (mid case) | LTV = ARPU × lifetime × gross margin. Range $130–$220 across scenarios. |
| CAC | **~$0–$5 blended at launch** (organic-only) | All launch channels are $0 (ops §1.3: GitHub/OSS, SEO, communities). CAC = founder time, not cash. Fully-loaded CAC (valuing founder time at even $25/h, ~2h per payer) ≈ $50 — still pays back in < 5 months. Paid CAC is explicitly post-launch (ops §1.3 rank 6). |
| CAC payback | **< 1 month cash / ~4–5 months fully-loaded** | Payback = CAC ÷ (ARPU × gross margin). Cash: ~$0. Fully-loaded: $50 ÷ ($12 × 80%) ≈ 5.2 mo. Benchmark: healthy SMB payback is 6–12 mo (2025 benchmarks median 5 mo at <$1M ARR). We clear it at both definitions. |
| LTV:CAC | **> 3:1 fully-loaded (~3.3:1); effectively infinite on cash CAC** | ≥ 3:1 is the standard healthy benchmark (GrowthTera/Drivetrain 2025). |

**Honesty note:** early-stage payback medians in benchmarks "may be understated due to unallocated founder/CS/onboarding costs" (2025 SaaS Benchmarks). The fully-loaded column above is our correction — quote that one externally.

### 2.2 Churn & retention assumptions

| Scenario | Monthly gross churn | Implied lifetime | Rationale |
|---|---|---|---|
| Conservative | 7% | ~14 mo | SMB bottom-quartile; mostly monthly billing |
| Base | 5% | ~20 mo | SMB median (5.8%) improved by annual-billing mix + alert loop |
| Optimistic | 4% | ~25 mo | Stripe/Churnkey SaaS median; annual-heavy mix |

Monthly billing churns ~3× annual (6.2% vs 2.1%, RevMine). **Every annual conversion is worth ~3× the lifetime** — annual plans are a retention feature, not just a discount. Push annual in the paywall (§3), never discount monthly.

### 2.3 Cost structure at launch ($0 billing infra)

| Cost | Launch | At $1k MRR |
|---|---|---|
| Hosting (1 VPS, Docker + SQLite) | $6–20/mo | $20–50/mo (2nd worker) |
| Email | $0 (FileTransport → VPS MTA) | $0–10/mo (free SMTP tier) |
| Payments | $0 (manual toggle) | Stripe 2.9% + 30¢ only |
| Analytics | $0 (Postgres events + Metabase OSS) | $0 |
| Domains/TLS | ~$15/yr | same |

Contribution margin per Pro payer at launch: $9 − $0.56 (Stripe, once live) − ~$0.30 hosting ⇒ **~$8.10 (90%)** at marginal scale; blended reported margin 75–82% per §2.1 once fixed costs are counted. Infra is effectively free until ~100 payers, which is why the $9 price works.

### 2.4 Capacity cost guardrail

Checks are the cost driver: 100 Team monitors at 10 s = 864k checks/day. Fine for one worker at low concurrency, but **do not enable 10 s intervals until ingest p95 < 2 s is proven in prod** (product-spec KPI). If scheduler load threatens margin, the lever is interval floor, not price — e.g. Team 10 s → 15 s — before any price rise.

---

## 3. Freemium conversion strategy

### 3.1 Free-tier limits rationale

| Limit | Why it's the line |
|---|---|
| **3 monitors** | Covers "my API + my landing page + one more" — real indie value, zero false promise. The 4th monitor is the natural first upgrade moment. UptimeRobot's free 50 proves volume alone doesn't convert; scarcity on monitors is what creates the paywall event. |
| **5-min interval** | At 5 min, latency drift is visible but not actionable for CI. 30 s is *felt* as a different product. |
| **7-day history** | Enough to see a regression alert fire; not enough for baseline confidence or postmortems. 90 days is the "evidence" tier. |
| **1 alert channel (email)** | Email is where alerts go to die. Slack/webhook is where teams live. The channel boundary is the Team/Pro wedge. |
| **1 CI project** | One gated repo is the demo; the second repo is the habit. |

Every Free limit maps to exactly one Pro feature (§1.2). No "gotcha" limits (no check-count meters, no watermarked reports) — Free users must be able to succeed, because Free→paid word-of-mouth is the channel (§2.1 CAC).

### 3.2 Upgrade triggers (ship these events first)

Reuse `ops-growth-spec.md` §2.4 triggers, ranked by expected conversion value:

| # | Trigger event (analytics event) | Paywall copy anchor |
|---|---|---|
| 1 | Creates 4th monitor (`monitor_created`, count = 4) | "You've used 3/3 free monitors." |
| 2 | Tries interval < 5 min (`interval_changed` rejected) | "5-min checks can't catch drift fast enough. 30 s checks can." |
| 3 | Tries to add webhook/Slack channel | "Alert where your team already is." |
| 4 | Views history > 7 days | "Your baseline needs 90 days to be believable." |
| 5 | Tries a 4th region | "One slow region is an outage you haven't found." |
| 6 | Creates 2nd CI-gated project | "Gate every repo, not just one." |
| 7 | Tries team invite / 4th seat | "Bring the on-call with you." |

**Trigger rule:** the nudge must always show the usage number that triggered it, never a bare "Upgrade now" (ops §2.4). Max 1 nudge per 7 days per workspace.

### 3.3 Paywall UX rules

1. **Feature-block, never data-block.** Hitting a limit never hides existing data or stops existing checks. Over-limit actions are *new* creates only. Downgraded/expired users keep their 3 monitors running (see §4.4).
2. **402 + upgrade link** on API (product-spec §4), friendly inline panel in UI — no modal ambush, no content lock mid-task.
3. **Show the trigger number** in the paywall ("3/3 monitors used", "10 s requested, Free minimum is 5 min").
4. **Annual default-selected** in the paywall (2 months free, lower churn) with monthly one click away. Never pre-select the more expensive option silently.
5. **Sticky-after-activation:** once a workspace has received a regression alert, paywall copy shifts from features to *evidence* ("Last month this check caught a +34% p95 drift on your `/users` endpoint") — sell the save, not the tier.
6. **Self-serve, no sales calls** at any tier at launch (ops §2). No "Contact us" for Team until S3 (platform/ops segment) exists.
7. **Cancel in ≤ 3 clicks, no dark patterns.** Cancel → downgrade at period end, data export offered first (ops §5.2 FAQ #7). Retention offers are limited to one honest annual-discount offer — no guilt screens.
8. **Status badge & public reports stay free forever** — they are the acquisition loop (§4.1 of ops spec). Paywalling them would kill the flywheel.

### 3.4 Conversion benchmarks to plan against

- Industry freemium → paid: **2–5%** typical (B2B SaaS; developer tools 1–3%, but hard usage limits push well above — Rework/GetMonetizely 2025).
- First Page Sage (86 SaaS cos): **2.6%** organic freemium→paid.
- Newer ChartMogul/ProductLed 2026 cohort (200 B2B products): **median 8%**, 3–5% "good", 8–12% "great" for self-serve freemium.
- **Our planning numbers:** 3% (conservative) / 5% (base) / 7% (optimistic) of *activated* workspaces (those that created ≥ 1 monitor — ops §3.3), i.e. above the 2.6% organic benchmark because our limits are hard-usage limits on the exact value axis (monitors, interval, channels). If we land under 3% by day 90, the fix is trigger tuning (§6), not a price cut.

---

## 4. Billing implementation design ($0 provider at launch)

### 4.1 Principle

**Billing is a `plan` field + an audit log, not a payment system.** The app must boot, register, enforce limits, and "charge" with zero external calls and zero secrets. Stripe is an optional adapter plugged in later behind an env flag (roadmap: "Stripe behind env flag; manual plan toggle until then"; product-spec §4).

### 4.2 Launch design (what to build in sprint 2, P1)

**Schema additions** (extend architecture.md `users.plan`, `plan_limits`):

```sql
-- Extend users, add billing tables
ALTER TABLE users ADD COLUMN plan_status TEXT DEFAULT 'active';   -- active|past_due|canceled
ALTER TABLE users ADD COLUMN billing_cycle TEXT DEFAULT 'monthly';-- monthly|annual
ALTER TABLE users ADD COLUMN plan_expires_at TEXT;                -- null = manual/no expiry
ALTER TABLE users ADD COLUMN stripe_customer_id TEXT;             -- null until Stripe live
ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT;

CREATE TABLE subscriptions(
  id TEXT PK, user_id INT FK, plan TEXT, cycle TEXT,
  status TEXT,            -- active|past_due|canceled|trialing
  current_period_end TEXT, created_at TEXT,
  provider TEXT DEFAULT 'manual',   -- manual|stripe
  provider_ref TEXT                 -- invoice id / stripe sub id
);
CREATE TABLE invoices(
  id TEXT PK, user_id INT FK, subscription_id TEXT FK NULL,
  amount_cents INT, currency TEXT DEFAULT 'USD', status TEXT,
  -- manual flows: issued|paid|void|refunded ; stripe flows mirror payment_intent status
  provider TEXT DEFAULT 'manual', period_start TEXT, period_end TEXT,
  created_at TEXT, paid_at TEXT
);
CREATE TABLE plan_changes(           -- audit trail for every toggle
  id INTEGER PK, user_id INT FK, from_plan TEXT, to_plan TEXT,
  actor TEXT,                       -- 'admin'|'user'|'stripe-webhook'|'system'
  reason TEXT, created_at TEXT
);
```

**Enforcement stays exactly as product-spec §4 designed:** `plan_limits` checked on check-create + ingest; over-limit → 402. Plan changes only write `users.plan` + `plan_changes` + a `subscriptions` row. Nothing else in the app knows what "payment" means.

**Manual-activation flow (launch):**

1. User clicks Upgrade → paywall → "Pay by invoice / contact us" → creates an `invoices` row (`issued`, provider `manual`) and emails the owner the invoice details + a payment link placeholder (bank/Wise/PayPal instructions, or "reply to this email").
2. Admin (owner) marks `paid` via an admin endpoint (`POST /api/admin/users/{id}/set-plan {plan, cycle, expires_at}` — token-guarded by `ADMIN_TOKEN` env, absent ⇒ disabled) after the transfer lands. Expiry-based: `plan_expires_at` set to +1 month / +1 year; the scheduler downgrades expired subs daily (system actor, `reason: 'manual-expiry'`).
3. While manual: all §4.4 dunning/refund rules apply with `provider='manual'`; the customer-facing copy says "manual billing in beta — your plan is active, we'll email you before it expires."

This gives a real, auditable path to charge the first 10–50 payers with zero integration — which is exactly the M3 milestone (50 payers, $450 MRR).

### 4.3 Plugging in Stripe later (adapter contract)

```
BILLING_PROVIDER=manual            # launch default; app boots with no keys
# later:
BILLING_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...
STRIPE_PRICE_TEAM_MONTHLY=price_...
STRIPE_PRICE_TEAM_ANNUAL=price_...
```

- `BillingProvider` interface in a new `app/billing.py`: `create_checkout(user, plan, cycle)`, `handle_webhook(event)`, `cancel(user)`, `refund(invoice)`. `ManualProvider` implements the §4.2 flow; `StripeProvider` implements checkout + webhooks (`checkout.session.completed` → activate; `customer.subscription.deleted` → cancel; `invoice.payment_failed` → past_due). The rest of the app calls only the interface + `users.plan`.
- **Boot rule:** if `BILLING_PROVIDER=stripe` but keys are missing, log a loud warning and fall back to `manual` — the app always boots. Never crash on missing billing config (mirrors the OAuth-stub pattern in architecture.md).
- **Webhook security:** verify `Stripe-Signature` with `STRIPE_WEBHOOK_SECRET`; reject unsigned events. Idempotent handling via `provider_ref` unique constraint.
- Stripe fees reminder (§2.1): 2.9% + 30¢ US cards; +1.5% international; 0.8% ACH (cap $5) — ACH is worth offering for annual Team ($290 ⇒ $5 vs $8.71 card fee).

### 4.4 Dunning, grace, downgrade

| Event | Timeline | UX |
|---|---|---|
| Payment fails (Stripe) / manual expiry-7d reminder | Day 0, 3, 7 | `dunning` email sequence (ops §4.2 template #6): friendly, shows what stays free, one-click update payment method |
| Past due | Day 0–14 grace | Pre-existing checks keep running at current interval (no data loss, no silent stop — a stopped checker the user doesn't know about is a trust-destroyer); new creates blocked |
| Grace ends unpaid | Day 14 | Auto-downgrade to Free: limits clamp to 3 monitors / 5 min / 7 days; extra monitors **paused, not deleted** (ops §4.1 loop 5: resume in one click); retention beyond 7 days hidden but recoverable on re-upgrade |
| Manual invoice overdue | Same as above | Same flow; `status: 'past_due'`, emails at 0/7/14 days |
| Involuntary churn watch | Ongoing | Stripe/Churnkey benchmark: ~22% of SaaS churn is involuntary (failed payments) — recovering half of it is "free" retention. Track `past_due` recovery rate as a KPI |

### 4.5 Refunds & cancellations

- **Monthly:** no refunds after the period starts (standard); cancel anytime, service runs to period end. In practice at launch: manual goodwill refunds via `invoices.status='refunded'` + `plan_changes` audit row.
- **Annual:** pro-rated refund within the first **30 days** (ops §5.2 FAQ #7); after 30 days, service credit only. Stripe: full/partial refund via the provider adapter; manual: transfer back.
- **Cancel flow:** Settings → Billing → Cancel (≤ 3 clicks, §3.3 rule 7) → optional 1-question reason survey (`cancelled` event, churn taxonomy per ops §3.4) → export-data prompt → `plan_status='canceled'`, downgrade at period end.
- **Chargebacks:** accept the loss on first occurrence (cost of a $9 chargeback > $9); dispute evidence is the `plan_changes` + `deliveries` audit trail. Disable the account's future card payments after 2 chargebacks.

---

## 5. Financial projections (12 months)

### 5.1 Model mechanics (auditable)

```
new_signups (per month, channel growth)
  × activation 60% (created ≥1 monitor in 24h — ops KR1.2 target)
  × conversion (of activated) 3% / 5% / 7%
  = new paying workspaces
paying_t = paying_{t-1} × (1 − churn) + new_paying_t        churn 7% / 5% / 4%
MRR_t = paying_t × $12 blended ARPU  (85% Pro $9, 15% Team $29)
```

Annual-billing discount (~17% on ~30% of payers) is excluded from the tables for clarity — subtract ~5% from MRR for a net figure. No paid acquisition spend in any scenario (organic only, §2.1). Signup growth assumptions: conservative ~+15%/mo linear-ish from 30; base ~+20%/mo compounding from 120 (GitHub flywheel + SEO compounding); optimistic ~+25%/mo from 250 (one viral moment, e.g. Show HN). All are testable against ops §8 OKRs (500 signups by day 90 ⇒ base starts at 120/mo).

### 5.2 Conservative — 3% conversion, 7% churn, slow growth

| Month | New signups | New paying | Paying (EOM) | MRR |
|---|---|---|---|---|
| 1 | 30 | 0.5 | 1 | $6 |
| 2 | 40 | 0.7 | 1 | $15 |
| 3 | 50 | 0.9 | 2 | $24 |
| 4 | 60 | 1.1 | 3 | $36 |
| 5 | 70 | 1.3 | 4 | $48 |
| 6 | 85 | 1.5 | 5 | $63 |
| 7 | 100 | 1.8 | 7 | $80 |
| 8 | 115 | 2.1 | 8 | $100 |
| 9 | 130 | 2.3 | 10 | $121 |
| 10 | 150 | 2.7 | 12 | $145 |
| 11 | 170 | 3.1 | 14 | $171 |
| 12 | 190 | 3.4 | **17** | **$200** |

### 5.3 Base — 5% conversion, 5% churn, 60% activation

| Month | New signups | New paying | Paying (EOM) | MRR |
|---|---|---|---|---|
| 1 | 120 | 3.6 | 4 | $43 |
| 2 | 170 | 5.1 | 9 | $102 |
| 3 | 240 | 7.2 | 15 | $184 |
| 4 | 320 | 9.6 | 24 | $290 |
| 5 | 420 | 12.6 | 36 | $426 |
| 6 | 540 | 16.2 | 50 | $599 |
| 7 | 680 | 20.4 | 68 | $814 |
| 8 | 850 | 25.5 | 90 | $1,079 |
| 9 | 1,050 | 31.5 | 117 | $1,404 |
| 10 | 1,280 | 38.4 | 150 | $1,794 |
| 11 | 1,550 | 46.5 | 189 | $2,262 |
| 12 | 1,850 | 55.5 | **235** | **$2,815** |

Base-case coherence checks: 25 payers by day 90 is the ops KR3.1 target — base lands at ~15 by day 90, so the 90-day OKR is *harder* than base unless month 1–3 signups beat 120/mo; 50 payers / $450 MRR (roadmap M3) lands ~month 5–6 in base. Treat KR3.1 as a stretch goal, M3 as the base commitment.

### 5.4 Optimistic — 7% conversion, 4% churn, viral channel

| Month | New signups | New paying | Paying (EOM) | MRR |
|---|---|---|---|---|
| 1 | 250 | 10.5 | 11 | $126 |
| 2 | 380 | 16.0 | 26 | $312 |
| 3 | 560 | 23.5 | 49 | $582 |
| 4 | 800 | 33.6 | 80 | $962 |
| 5 | 1,100 | 46.2 | 123 | $1,478 |
| 6 | 1,500 | 63.0 | 181 | $2,175 |
| 7 | 2,000 | 84.0 | 258 | $3,096 |
| 8 | 2,600 | 109.2 | 357 | $4,282 |
| 9 | 3,400 | 142.8 | 485 | $5,825 |
| 10 | 4,400 | 184.8 | 651 | $7,809 |
| 11 | 5,600 | 235.2 | 860 | $10,319 |
| 12 | 7,000 | 294.0 | **1,120** | **$13,435** |

### 5.5 Reading the scenarios

- **Year-1 revenue:** conservative ≈ $1.0k cumulative · base ≈ $9.8k cumulative · optimistic ≈ $46k cumulative. Base is a side-project-scale business in year 1; it becomes real at month 12 ($2.8k MRR ⇒ ~$34k ARR run-rate).
- **The lever that matters most is signups, not price.** Base→optimistic is driven by channel (signups 9,070 vs 29,590 cumulative) more than conversion. Protect the $0 flywheel (§3.3 badge/CLI rules) before optimizing price.
- **Churn dominates by month 12:** at 5% churn you must add ~12 payers/mo just to stand still at 235. Annual-billing push (§2.2) is the highest-ROI retention work after the alert loop.
- **Re-forecast trigger:** re-run this table at day 45 with actual activation/conversion (ops review cadence) and replace assumptions, not just numbers.

---

## 6. Experiments to run post-launch (first 90 days)

Owner: desk-14 with desk-5 (analytics). All experiments pre-registered in the `events` table (ops §3) before launch; one variable at a time; minimum 2 weeks or 100 exposed workspaces per arm.

| # | Experiment | Hypothesis | Primary metric | Guardrail |
|---|---|---|---|---|
| 1 | **Price anchor: $9 vs $12 Pro** (50/50 on pricing page) | $12 loses < 20% conversion ⇒ +33% ARPU; indie price sensitivity is lower than feared below $15 | `subscription_activated` / `upgrade_viewed` | Support/complaint rate; cancellation in first 30d |
| 2 | **Interval wedge: Pro 30 s vs 1 min** | 30 s is the Probe trigger; 1-min Pro converts measurably worse | `upgrade_viewed` after `interval_changed` rejection | Scheduler ingest p95 < 2s (§2.4) |
| 3 | **Annual-default vs monthly-default** on paywall | Annual default lifts annual mix 30% → 50%+ with < 10% total conversion loss ⇒ lower churn | Annual share of new payers; 90-day survival | Refund requests; "bait" complaints |
| 4 | **Free monitors: 3 vs 5** | 5 monitors grows activation but dilutes the paywall event; net conversion flat/down | Free→paid of activated; activation rate | Total signups (flywheel must not shrink) |
| 5 | **Paywall copy: feature vs evidence** (§3.3 rule 5) for workspaces that received an alert | Evidence copy ("caught a +34% drift") out-converts feature copy | `upgrade_viewed` → `subscription_activated` post-alert | Alert unsubscribe rate |
| 6 | **Team anchor: $29 vs $39** (match UptimeRobot Team) | $29 has no measurable conversion gain over $39 at low volume; $39 raises ARPU | Team share of new payers; ARPU | Team upgrade_viewed abandonment |
| 7 | **CI-gate-first onboarding** (template repo + Action on signup) vs dashboard-first | CI-first users convert to Pro at 2× (gate = habit) | Pro conversion of CI-activated cohort | Time-to-first-monitor |
| 8 | **Overage add-on** (post-Stripe only): $1/10k extra checks vs hard cap | High-volume users prefer metered over forced upgrade | Add-on attach rate; ARPU | Bill-shock tickets |

**Pricing-page experiments (do after 1–4):** highlight Pro vs Team (middle-tier bias); "per workspace" vs "per user" framing (we are per-workspace/flat — test that wording makes Team feel cheaper to teams); publish the live status badge + real numbers on the pricing page (dogfooding as proof).

---

## 7. Legal / tax notes (high-level — not tax advice)

> ⚠️ Read with `docs/ops-growth-spec.md` §6 (ToS/Privacy drafts, GDPR+LGPD). **This section is not legal or tax advice.** Do not charge money until the §6.4 legal checklist is signed off by counsel (ops hard gate).

### 7.1 Invoicing
- Every manual payment (§4.2) issues an invoice record (`invoices` table) with sequential number, date, seller identity, buyer email, plan, period, and amount — keep these exportable (CSV) from day one; they are the skeleton of tax compliance.
- Once Stripe is live, Stripe Invoices are the source of truth; still **mirror** them into `invoices` so manual + Stripe eras have one ledger.
- Invoice wording must not claim VAT/GST registration until actually registered (see §7.2). Until then: "Prices in USD. Taxes may apply depending on your location; any applicable taxes will be shown before payment."

### 7.2 VAT / GST readiness
- **Design for it now, collect it later:** store `country` (ISO) on the user at signup/checkout and a `tax_rate` + `tax_id` field on invoices from the start — backfilling tax data later is painful.
- **Thresholds (directional, verify with counsel/accountant):** EU VAT MOSS/OSS registration above €10k in cross-border B2C digital sales; UK VAT registration at £90k turnover; Brazil (LGPD market — ops §6.2) has its own NFSe/CNPJ regime for digital services. Below thresholds, selling cross-border as a small non-EU seller is generally manageable, but the *obligation follows the seller's location*, not the customer's — get advice based on where the operator actually is.
- **Stripe Tax** is the pragmatic plug-in when crossing a threshold: it calculates/collects/remits VAT/GST/GST-PI, and integrates with the §4.3 adapter (add `STRIPE_TAX_ENABLED` flag; tax collection is a Stripe customer setting, not an app change). Budget ~0.5% + per-transaction fee on top of 2.9% when enabled.
- **B2B reverse charge:** Team-tier buyers may supply a VAT ID — collect it at checkout, validate format (VIES for EU), and put "Reverse charge — VAT to be accounted for by recipient" on their invoices. Do not self-assess EU B2B VAT.

### 7.3 Other launch-legal money notes
- **Refund policy in ToS** must match §4.5 exactly (30-day pro-rated annual) — publish before first charge.
- **DPA on request for Team** before any B2B sale (ops §6.4); sub-processor list must name the payment processor once Stripe is live (§6.2 living page).
- **No card storage, ever** — card data touches only the processor (PCI scope stays SAQ-A via Stripe/PayPal). Manual-era payments (bank transfer/PayPal) keep card data out of our systems entirely.
- **Records retention:** keep invoices + `plan_changes` for the statutory period in the operator's jurisdiction (commonly 5–10 years) even after account deletion — privacy deletion (§6.2) must carve out legally-required financial records.
- **Pricing changes:** 30 days' notice for material price changes (ops §6.1 term 9); grandfather clause §1.1 applies to anyone mid-subscription.

---

## 8. Decisions & open items

| # | Decision needed | Default in this spec | Owner |
|---|---|---|---|
| D1 | Pro/Team interval: 30 s/10 s (ops) vs 1 min (product-spec) | 30 s / 10 s, gated by scheduler headroom | PM (desk-1) |
| D2 | Month-1 signup assumption (120/mo) vs ops KR1.1 (500 by day 90) | Base assumes KR1.1 is stretch; M3 ($450 MRR) is the commitment | Desk-14 + desk-5 |
| D3 | Manual-era payment methods (bank / PayPal / Wise) | Any one; invoice-first, admin-activate | Operator |
| D4 | When to enable Stripe: at 25 payers or M3 (50)? | At 25 payers — manual friction costs more than Stripe fees by then | Desk-14 |
| D5 | Annual discount 17% (2 months free) — keep if Exp. 3 shows monthly default wins? | Keep; churn math favors annual | Desk-14 |

---

## Sources

- Competitor pricing (published pricing pages + 2026 third-party corroboration): [UptimeRobot pricing](https://uptimerobot.com/pricing) (Free 50 monitors; Solo ~$13, Team ~$39, Scale ~$83/mo) · [Better Stack pricing](https://betterstack.com/pricing) ($34/seat incl. 10 monitors; +$25 per 50-monitor block) · [StatusCake pricing](https://www.statuscake.com/pricing/) (Free 10; Superior ~$24.49/100; Business ~$79.99/300) · [Pingdom pricing](https://www.pingdom.com/pricing/) (no free tier; synthetic from ~$10–18/mo for 10 checks) — comparisons via [AlertPing 2026 uptime-monitor comparison](https://alertping.com/blog/uptime-monitor-comparison-2026) and vendor review roundups.
- Freemium conversion: [GetMonetizely, freemium unit economics (Nov 2025)](https://www.getmonetizely.com/articles/can-you-maintain-profitability-with-generous-free-tiers-a-deep-dive-into-freemium-economics) (B2B SaaS 2–5%, dev tools 1–3%) · [Rework Playbook, free-to-paid conversion (Jan 2025)](https://resources.rework.com/libraries/saas-growth/free-to-paid-conversion) · [First Page Sage, SaaS conversion benchmarks (Sep 2025)](https://firstpagesage.com/seo-blog/saas-free-trial-conversion-rate-benchmarks/) (2.6% organic) · [ChartMogul/ProductLed SaaS Conversion Report (Jan 2026)](https://chartmogul.com/reports/saas-conversion-report/) (median 8%, 3–5% good, 8–12% great).
- Unit economics: [2025 SaaS Benchmarks Report](https://www.saasbenchmarks.com/) (gross margin 74–80% by ARR; CAC payback median 5 mo <$1M ARR) · [SaaSCan/Benchmarkit 2025](https://www.benchmarkit.ai/) (top-quartile subscription gross margin >85%) · [Drivetrain 2025 SaaS benchmarks](https://www.drivetrain.ai/) (subscription gross margin 81% median; ~12 mo payback "good") · [GrowthTera 2025 guide](https://www.growthtera.com/blog/saas-benchmarks) (LTV:CAC ≥ 3:1; SMB payback 6–12 mo).
- Churn & fees: [RevMine churn benchmarks (2024 data, 500+ cos)](https://revmine.ai/blog/churn-benchmarks/) (SMB median 5.8%/mo; annual 2.1% vs monthly 6.2%) · [Stripe + Churnkey churn benchmarks](https://stripe.com/lp/churn-benchmarks) ($1.4T processed data: SaaS 4.0%/mo, 22% involuntary) · [Stripe pricing](https://stripe.com/pricing) (2.9% + 30¢ US cards; 0.8% ACH cap $5; +1.5% international).
- Internal specs: `docs/product-spec.md` §4–§5, `docs/architecture.md` (schema, `plan_limits`), `docs/ops-growth-spec.md` §2/§5/§6, `docs/roadmap.md` (milestones M1–M3).

*End of spec. Next step: PM resolves D1; build implements §4.2 schema + manual toggle in sprint 2 (P1).*
