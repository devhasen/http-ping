# LatencyLedger — Legal / Compliance Spec (SPEC ONLY — Research & Draft)

> **⚠️ DISCLAIMER — THIS DOCUMENT IS NOT LEGAL ADVICE.**
> Everything marked **TEMPLATE** in §1–§2 is an AI-drafted starting point to take to a
> qualified lawyer in the relevant jurisdiction(s). Do **not** publish it as-is.
> Items flagged **🚩 HOW TO VERIFY / NEEDS LAWYER** must be reviewed before any
> public launch (M2 in `docs/roadmap.md`), before handling paying customers / EU-BR
> users, and before Stripe (Sprint 2) or OAuth (P2) go live. Replace every
> `[BRACKETED PLACEHOLDER]` with real entity details before legal review.
>
> Single-operator / self-host friendly: this spec distinguishes (a) **hosted
> LatencyLedger** (what these documents govern) between Hosted Operator and Hosted
> Users, from (b) **self-hosted** instances (operator = you; you are solely
> responsible for your instance's compliance — see §7 + ToS §14).
>
> Cross-references: `docs/product-spec.md` (auth, alerts, public links, pricing),
> `docs/architecture.md` (schema, auth, SSRF, stack), `LICENSE`, `SECURITY.md`.

---

## 1. Legal document list

Every document below lives (once finalised) at `/legal/<name>` on the hosted
instance and in the upstream repo at `docs/legal/<name>.md`. Pre-launch /
SPEC phase: they live **only in this file** as templates.

| # | Document | Route | Priority | Status |
|---|---|---|---|---|
| 1 | Terms of Service (ToS) | `/legal/terms` | MUST before sign-up | **TEMPLATE draft §2** |
| 2 | Privacy Policy | `/legal/privacy` | MUST before sign-up | **TEMPLATE draft §3** |
| 3 | Cookie Policy | `/legal/cookies` | MUST before first cookie | Summary §4, full TBD |
| 4 | Data Processing Addendum (DPA) | `/legal/dpa` | MUST before taking EU-BR customers if we act as processor (§5) | Outline §5 + drafting notes |
| 5 | Acceptable Use Policy (AUP) | `/legal/aup` | MUST before sign-up (SSRF wording) | Outline §6 |
| 6 | SLA | `/legal/sla` | Only when selling Pro/Team + in `Free` if promised | Outline §7 — **do not promise an uptime you don't keep** |
| 7 | Refund Policy | `/legal/refunds` | SHOULD before Stripe (Sprint 2) | Outline §8 |

Rule for all seven: **version-stamp every document** (`Last updated: YYYY-MM-DD`,
`Version: 1.0`) + archive superseded versions (keep them retrievable; GDPR/ToS
disputes turn on which version a user saw). Material changes → email all account
holders + bump `Last updated`; never silently rewrite history.

---

## 2. Terms of Service — TEMPLATE / NOT LEGAL ADVICE

> **TEMPLATE — FOR LAWYER REVIEW ONLY. NOT LEGAL ADVICE.**
> Replace all `[…]` before review. Have a lawyer in the operator's state/country
> confirm consumers vs business users, liability caps, and arbitration/[class-waiver]
> enforceability. This draft is written for a **solo/small operator** — see §7
> "Single-operator legal floor".

**LatencyLedger Terms of Service — Last updated: [YYYY-MM-DD] · Version: [___]**

1. **Who you are.** These Terms between **[LEGAL ENTITY NAME, e.g. "___ LLC",
   registration no. ___]** ("LatencyLedger", "we", "us") and **you**, the
   LatencyLedger account holder ("you", "Customer").
   🚩 HOW TO VERIFY: entity form, registered agent, principal place of business
   and notice address — a terms violation then becomes personal; verify before launch.
2. **The Service.** Hosted HTTP latency monitoring: URL checks on a schedule,
   `p50/p95/p99` and trend analytics, regression alerts, CI latency gates, API
   keys, and opt-in public report links / status pages. Optional self-hosted
   software is governed by §14 + the MIT License.
3. **Eligibility.** You must be **18+** (see §9 below) and competent to contract.
   LatencyLedger is a tool for adult developers/teams, not a consumer service.
4. **Accounts, sign-up, credentials.**
   - Sign up with an email address and a password. You are responsible for keeping
     credentials secret and for everything done under your account/API keys.
   - API keys (shown once, stored hashed) authenticate your CI. Never publish
     them. Revoke any key you suspect is compromised; revocation is immediate.
   - You agree to give accurate contact details and to update them.
5. **Your data & URLs.**
   - You grant us a non-exclusive, worldwide, royalty-free licence to store and
     process URLs, check configuration, samples, git SHAs/notes, and alert
     configuration **solely to provide the Service**.
   - Checks may only target URLs that are (a) **publicly reachable over http(s)**,
     (b) **not** on private/loopback/link-local addresses, and (c) **lawfully
     yours or held with the target owner's permission**. Our sampler blocks
     internal destinations; attempts to use LatencyLedger as a proxy, port scanner,
     or SSRF tool are a material breach (see AUP §6).
   - You are responsible for what you point the Service at. Do not submit
     personal data of third parties into check URLs, notes or SHAs (that makes
     **you** the controller — see Privacy Policy §[controller]).
6. **Plans, limits, fees.** Free/Pro/Team plan limits (check count, minimum
   interval, history length) are enforced server-side. Paid plans are billed
   monthly/yearly via a payment processor **[Stripe]**; prices exclude tax.
   🚩 NEEDS LAWYER: sales tax/VAT, auto-renewal + cancellation disclosures vary by
   jurisdiction (esp. EU consumer rules / Brazil CDC); verify per-market billing
   copy before Stripe goes live.
7. **Public report links.** A check you mark public is **world-readable, no login**
   required, at `/r/[slug]` (and `/s/[slug]` status pages). It shows chart +
   stats only — never API keys. **Do not put secrets in URLs or check names.**
   Toggling public off returns 404. Anyone can copy/scrape a public link.
8. **Alerts.** Email/webhook/chat deliveries are best-effort. A missed, delayed
   or false-positive/negative alert is **not** a guarantee of detection and does
   not make us liable for your downtime, lost revenue, or CI outcomes.
9. **Age & content restrictions.** No minimum product content restriction applies
   to latency monitoring itself, but accounts are **18+**, and the AUP prohibits
   unlawful content/uses. *We do not knowingly collect data from children*
   (see Privacy §[children] + GDPR/LGPD §5).
10. **Acceptable Use.** You agree to follow the AUP (§6 below): no abuse of the
    scheduler, no SSRF/proxy use, no aggressive scraping/DoS-by-checking, no
    interference with the Service or other users, no unlawful activity.
11. **Availability & warranties.** The Service is provided **"AS IS" / "AS
    AVAILABLE"** to the extent permitted by law. We do not warrant that monitoring
    is uninterrupted, timely, or error-free. **Any advertised SLA (§7) is only a
    service credit commitment, not a guarantee of 100% uptime.**
12. **Limitation of liability.**
    - To the maximum extent permitted by law, we are **not liable for indirect,
      incidental, consequential, special, or punitive damages**, including loss of
      profits, revenue, data (beyond what we can restore from backups), or goodwill.
    - Our total liability for any 12-month period is capped at the **greater of
      (i) USD [___] or (ii) amounts you paid us in that period**.
    - Nothing limits liability that cannot legally be limited (e.g. wilful
      misconduct, fraud).
    🚩 NEEDS LAWYER: enforceability differs by jurisdiction (e.g. EU consumer law
    disallows such caps against consumers; some US states limit liability waivers).
    Confirm before launch.
13. **Termination / suspension.** Either party may terminate. We may suspend or
    terminate your account for breach of the AUP/Terms (incl. SSRF/abuse), legal
    requirement, or non-payment, with notice where legally required and **except**
    for egregious/clearly unlawful use (e.g. using a check against internal systems).
    On termination, your data is deleted per §10 / Privacy §[deletion].
14. **Self-hosted deployments.** Anyone may self-host the open-source LatencyLedger
    under the MIT License. Self-host operators are **not** our customers: they
    operate under their own law, with their own users, and are solely responsible
    for their instance's ToS, Privacy Policy and security. LatencyLedger (the
    upstream project) provides **no warranty or support** for self-hosted instances.
15. **Changes.** We may update these Terms. Material changes to paid plans will
    take effect on the next renewal with **[30] days'** notice by email + in-app.
    Continued use after the effective date accepts the new Terms.
16. **Governing law & disputes.** These Terms are governed by the law of
    **[STATE/COUNTRY]** 🚩 NEEDS LAWYER. Disputes: **[binding arbitration /
    courts of ✓]** 🚩 NEEDS LAWYER — arbitration + class-action waiver enforceability
    varies (e.g. EU consumers; LGPD/GDPR cannot be arbitrated away).
17. **Contact notice.** Which address for legal notices, and how we may notify you
    (email on file + in-app banner).
18. **Version archive.** Superseded versions are archived at `/legal/terms/archive`.

---

## 3. Privacy Policy — TEMPLATE / NOT LEGAL ADVICE

> **TEMPLATE — FOR LAWYER REVIEW ONLY. NOT LEGAL ADVICE.**
> Have counsel confirm controller/processor roles, lawful bases, and retention
> periods for the operator's jurisdiction and for GDPR (EU/EEA) + LGPD (Brazil).
> Align 1:1 with the GDPR/LGPD mapping in §5 below — any mismatch is a finding.

**LatencyLedger Privacy Policy — Last updated: [YYYY-MM-DD] · Version: [___]**

**1. Who is responsible.** Data controller (hosted Service): **[LEGAL ENTITY NAME,
   address, contact DPO/privacy email privacy@[DOMAIN]]**. Self-hosted instances:
   the operator is the controller (§7).

**2. What we collect, and why.** "Personal data" = information identifying or
   relating to an identifiable person.

| Category | Example fields | Source | Lawful basis (GDPR/LGPD analogue) |
|---|---|---|---|
| Account | email, password hash (PBKDF2 ≥100k, arm: `hashlib.pbkdf2_hmac`), `created_at`, plan | You, at sign-up | Contract (performance of ToS) |
| Session | session token (opaque, server-side), `expires_at`, login timestamps | App on login | Legitimate interests — security/fraud prevention; strictly necessary cookie |
| API keys | `prefix` + hash, `revoked_at` — **raw key never stored** | You generate | Contract |
| Checks/samples | check name, `url`, interval, `threshold_pct`, `is_public`/`slug`, `ms`/`status`/`size_bytes`, `git_sha`/`note` | You / your CI | Contract |
| Alerts/deliveries | channel target (email/webhook URL), alert observations, delivery status | You / system | Contract + legitimate interests (service delivery) |
| Network/security logs | IP address, user-agent, request timestamps, rate-limit records | Automatic | Legitimate interests — security, abuse (SSRF) prevention |
| Billing (P1) | what the payment processor holds — **card data never touches our servers** | Stripe `[PROCESSOR]+` | Contract / legal obligation (tax) |
| Support | emails/tickets you send us | You | Contract / legitimate interests |

Sample data is **latency measurements, not user content** — but a user could put
personal data in a URL/query-string, note, or SHA. That user is then the
controller for that input (§5).

**3. What we do NOT collect.** No trackers/ads, no third-party analytics on the
default deployment, no sale of personal data, no cardholder data on our servers,
and **no data from children** (18+ only; see §9 below).

**4. Sharing.** Personal data is shared only with:
- **Sub-processors** that host/support the Service: email delivery (SMTP/SendGrid-type
  provider), object storage/backups, payment processor — listed in `/legal/subprocessors`
  (name, purpose, location, LGPD/GDPR transfer mechanism). 🚩 Verify actual
  sub-processors before launch; a stale list is a GDPR Art. 28 failure.
- **Recipients you direct**: your public report link (world-readable — your
  choice), your webhook/chat endpoints, your email inbox.
- **Authorities** where legally required; acquirers if LatencyLedger is sold
  (with notice).
We never sell personal data. International transfers rely on adequacy / SCCs (GDPR)
and LGPD Art. 33 mechanisms. 🚩 NEEDS LAWYER: pick the correct mechanism for the
actual host region.

**5. Retention.** Shorter of: account lifetime, plan history limit (7d Free / 90d Pro
/ 1yr Team), or a period we technically need for security (network logs **30 days**,
anti-abuse records **12 months**), billing/tax records **as required by law
(generally 5–10 yrs)**. Deleted or anonymised on account termination (§10).
🚩 NEEDS LAWYER: confirm jurisdiction-specific tax retention with an accountant.

**6. Security.** Salted PBKDF2 password hashing, HTTPS, HttpOnly `SameSite=Lax`
session cookies, least-privilege server access, encrypted backups, SQLite/Postgres
with access controls, secrets via env only. This is a reasonable-efforts statement,
**not** a guarantee.

**7. Your rights.** See §5 (GDPR/LGPD mapping) — access/export, rectification,
erasure, restriction, portability, objection, automated-decision opt-out, and how
to exercise each in-app/API. Response target **1 month (GDPR)** / **15 days (LGPD)**.
🚩 Verify deadlines with counsel for each jurisdiction you serve.

**8. Cookies & tracking.** LatencyLedger is **cookieless-first**: only strictly
necessary storage is used (session cookie). See §4 — no consent banner needed
today; a banner becomes required only if non-essential cookies are added.

**9. Children.** 18+ only. If you believe a child has an account, contact us and
we will delete it.

**10. Changes to this policy.** Material changes via email + in-app; a version
archive is kept.

**11. Contact.** `privacy@[DOMAIN]` for privacy requests; response within the
timeframes in §5.

---

## 4. Cookie consent design — minimal, cookieless-first

### 4.1 Current state (default, Sprint 1 — nothing to consent to)

Only **strictly necessary** storage is used:

| Storage | Name / pattern | Purpose | Essential? | Consent needed? |
|---|---|---|---|---|
| Session cookie | `session` (opaque `secrets.token_urlsafe(32)`) | keep logged in | **Yes** | **No** — strictly necessary (GDPR ePrivacy Art. 5(3) exemption / LGPD `legítimo interesse`+fraude) |
| Anti-CSRF | `csrf_token` if added | CSRF defence | Yes | No (same exemption) |
| Preference cookie (if any) e.g. `ll_theme` | UI pref | Yes (user-selected) | No (user-chosen, first-party) |

- Cookie attributes on every necessary cookie: `HttpOnly` (session), `Secure`,
  `SameSite=Lax`, minimal `Max-Age`, no cross-site embedding (no third-party
  cookies at all), no fingerprinting, no analytics SDK.
- **Result: NO consent banner in the privacy-respecting default.** Do not add a
  rejected-consent banner project-wide; it would itself be a dark pattern and
  would confuse EU users ("why is it asking if it doesn't track me?").
- The Cookie Policy (§1 #3) still ships as a transparent *informative* page at
  `/legal/cookies` listing exactly the table above, explaining the exemption, and
  stating that anyone who adds a non-essential cookie must update the policy and
  ship a banner.

### 4.2 If non-essential cookies are ever added (marketing, analytics)

Default-deny: no JS/pixel fires until a positive opt-in. Design requirements a
lawyer-adjacent reviewer must sign off:

- Prior consent **before** any non-essential cookie is set (GDPR ePrivacy Art. 5(3)
  + LGPD Art. 7, I). No pre-ticked boxes, equal-weight Accept/Reject. Reject-all
  must be as easy as Accept.
- Consent state stored as a first-party cookie (`consent` id, timestamp, category
  choices) + server-side log; must survive and be refreshable; must be revocable
  at any time (a one-click "Cookie settings" link in the footer + banner).
- Separate consent per purpose (analytics / marketing / functional-preference)
  — bundling purposes is invalid consent.
- After this change, the Cookie Policy must enumerate every cookie (name, owner,
  lifetime, purpose) and the ToS/Privacy Policy promoted cookies from
  "strictly necessary" to "consent-based". 🚩 NEEDS LAWYER: verify banner wording
  per target market before shipping any non-essential cookie.

---

## 5. Data privacy: GDPR + LGPD mapping

> **⚠ NOT LEGAL ADVICE.** This is a design mapping to implement, then have a lawyer
> verify for the operator's own jurisdiction and chosen hosting region. "Confirm"
> rows are the hooks where the lawyer must replace a placeholder decision.

### 5.1 Roles

- **Hosted LatencyLedger = controller** for account, check, and usage data it
  decides how to process.
- **Customer = controller** for personal data they put in check URLs / notes / SHAs
  / webhooks (e.g. a URL with `?user_id=…`).
- **LatencyLedger = processor** when acting on a customer's behalf to store samples
  / check config → **DPA + GDPR Art. 28 / LGPD Art. 42** contract is required before
  EU/BR customers. DPA draft outline: subject matter+duration, parties, instructions
  (docs-only), confidentiality, sub-processor list + change notice, security Art. 32,
  breach notification **without undue delay (target ≤72h)**, assistance with
  data-subject requests, deletion/return at termination, audit rights.
  🚩 NEEDS LAWYER: add jurisdiction of interpretation; DPA text is the most
  commonly failed diligence item.
- **Self-hosted = operator is solely controller** (see §7).

### 5.2 Lawful bases / hipóteses legais

| Processing | GDPR basis | LGPD hypothesis (Art. 7) | Where recorded |
|---|---|---|---|
| Account creation / check execution / alerts | (b) Contract | Art. 7, V (execução de contrato) | ToS §2 |
| Session/security/anti-abuse logs, rate-limiting, SSRF blocking | (f) Legitimate interests | Art. 7, IX / Art. 10 | Privacy §[logs] |
| Email delivery of alerts | (b) Contract | Art. 7, V | alerts pipeline |
| Public report links (opt-in by user) | (b) Contract | Art. 7, V | `/r/[slug]` toggle |
| Email back-ups / hosting | (f) Legitimate interests | Art. 7, IX | sub-processor list |
| (Future) marketing / product analytics | **(a) Consent — opt-in only** | **Art. 7, I — consentimento** | not active in Sprint 1 |
| (Future) billing/tax | (c) Legal obligation | Art. 7, II | Stripe/tax records |

LGPD Art. 10 legitimate-interest balancing test must be documented (LIA) before
relying on (f)/Art. 7, IX. 🚩 NEEDS LAWYER: have counsel bless the LIA summary.

### 5.3 Data-subject rights — implementation design

Rights below are exercised **in-app (self-service where possible) + email fallback**
(`privacy@[DOMAIN]`). Response SLO: **1 month GDPR / 15 calendar days LGPD**,
extendable once for complex requests. Identity verification: authenticated session
or an emailed account-recovery link — never extra ID documents.

| Right | GDPR Art | LGPD Art | How offered (endpoint / UI) | Implementation notes |
|---|---|---|---|---|
| **Access / confirmation** | 15 | 18, I–II | `GET /privacy/export` (self-service) + email request | Authenticated; see Export below |
| **Rectify** | 16 | 18, IV | `PATCH /api/auth/me` (email), check edits in UI | validate email; confirm by email link |
| **Erase / delete** | 17 | 18, VI | `DELETE /api/auth/me` + self-service "Delete my account" in settings | full cascade (see §10); backups purged in ≤30d |
| **Restrict** | 18 | 18, VII | Email request + (future) in-app pause | mark `restricted` flag on user; stop scheduler for their checks |
| **Portability / export** | 20 | 18, V | `GET /privacy/export` (JSON) | structured, machine-readable; ≥70% format reuse of check-history export |
| **Object** (legitimate-interest processing) | 21 | 18, §3 (oposição) | Email request | suppress objected processing (e.g. security-marketing follow-ups) |
| **Automated decision / profile opt-out** | 22 | 20 (revisão) | N/A today; disclose if regression-scoring ever ranks users | no such decision in Sprint 1 |

**DSR endpoints needed (engineering backlog — all NEW, none exist today):**

| Endpoint | Method · Route | Auth | Returns / does | Notes |
|---|---|---|---|---|
| **Export** | `GET /privacy/export` | session | ZIP/JSON of `users` row, checks, samples, alerts, api-key metadata (never raw keys), alert channels, audit log | Generate async if sample volume is large; email a signed download link; **P1** build on top of existing history CSV export (`GET /api/checks/{id}/export`) |
| **Rectify** | `PATCH /api/auth/me` `{email}` | session | updates + email-confirmation link | reuse existing `GET /api/auth/me` shape |
| **Erase** | `DELETE /api/auth/me` | session (re-auth: password confirm) | cascades delete of sessions, api_keys, checks, samples, alerts, alert_channels, deliveries, `private` audit rows; revokes public slugs | see §10 checklist; backups purge ≤30d; irreversible-warn UX + 14-day soft-delete grace? — 🚩 undecided, NEEDS LAWYER (LGPD/GDPR erasure vs breach grace) |
| **Restrict** | `POST /privacy/restrict` | session | sets `users.restricted_at` | scheduler skips restricted users' checks |
| **Object** | `POST /privacy/object` | session/email | records `users.objection_flags` (json) | consumed by alert/marketing suppression |
| **Rectify (contact)** | email | `privacy@[DOMAIN]` | manual handling | when self-service can't cover it |

All DSR code paths must be **tested with pytest** (export completeness, delete
cascade completeness, tombstoned-read 404, public-slug revocation timing) — see
§9 for the test matrix. Add a `dsr_requests` audit table (`user_id, kind,
requested_at, fulfilled_at, status`) so the operator can *prove* they honoured it.

### 5.4 Breach response (GDPR Art. 33/34; LGPD Art. 48)

- **Triage (≤24h):** confirm scope, who was affected, what categories. Evidence:
  security logs, container / DB access logs.
- **Notify the regulator** where required: GDPR **≤72h** from awareness; LGPD
  **"reasonable time"** (ANPD guides: short — treat as ≤72h). Notify **data
  subjects** without undue delay where risk is high.
- **Record** in a breach register (date, findings, actions) even if not notifiable —
  and have a pre-written template letter (lawyer-approved) before launch.
- 🚩 NEEDS LAWYER: the ANPD has been tightening its breach guidance; diary any
  guidance change as a "material privacy notice" trigger.

### 5.5 Records of processing (GDPR Art. 30 / LGPD Art. 37)

Maintain a RoPA in the repo at `docs/legal/ropa.md` (controller, purposes, Lawful
bases, categories of data subjects, recipients) — one table per activity (account,
checks, alerts, back-ups, support). A single SQLite `privacy_events` audit table
in-app is the *operational* log; the RoPA is the *legal* document. Keep both.

---

## 6. Age / content restrictions

- **18+ only.** LatencyLedger is a paid/pro tool for adult developers and teams.
  There is no children's content, no social features, and we do not knowingly
  process data from anyone under 18 (GDPR Art. 8 / LGPD Art. 14 informed-parental
  consent is unusable for this product).
- **Gate at sign-up:** date-of-birth or an explicit "I am 18 or older" representation.
  🚩 NEEDS LAWYER: age-verification method; a checkbox is weak evidence vs an IDV
  check. Keep the checkbox + `users.age_attested_at` timestamp until counsel advises otherwise.
- **Content restrictions:** no illegal content may be stored/linked through checks,
  public links or notes. The AUP prohibits unlawful content and any content
  facilitating abuse of the scheduler. We reserve the right to remove public
  slugs that violate the AUP and to suspend the account.

---

## 7. Open-source license compliance

### 7.1 This repo: MIT

- `LICENSE` (MIT, © 2026 LatencyLedger contributors) covers **LatencyLedger's own
  source** (`app/`, `app/static/`, `examples/`, local docs) — the permissive MIT
  terms (use/copy/modify/merge/publish/distribute/sublicense/sell) are already
  present. Verify `LICENSE` is included in every distribution (Docker image,
  tarball, PyPI if ever published).
- The npm/TypeScript CLI skeleton in `src/` + `dist/` is also intended MIT but
  ships inside the same `LICENSE`. Keep one LICENSE file; don't create dual-license
  confusion without a lawyer's reading.
- **Attribution & warranties:** MIT requires keeping the copyright+permission
  notice in copies. The "AS IS" warranty disclaimer mirrors the ToS §11 — keep
  them aligned. 🚩 Clarify with counsel whether self-host ToS (§2 item 14) is
  needed given "AS IS"; MIT disclaimers cover software, the ToS covers the person.

### 7.2 Third-party dependency audit policy

LatencyLedger's design goal (stdlib-only, `requirements.txt` empty) keeps audit
surface tiny. Policy that keeps it that way:

| Rule | Action before merging |
|---|---|
| **Runtime dep** added (any `requirements.txt` entry) | PR must link its license. **MIT/Apache-2.0/BSD** = green. **GPL/AGPL** = NO without license review (network-use) 🚩 NEEDS LAWYER for any copyleft. |
| **`pytest`-only dev dep** | disclose in `pyproject.toml`; no distribution obligation |
| **Transitive dep drift** | pin + `pip freeze` baseline; regenerate lockfile on every bump |
| **Legal gate** | a lawyer or maintainer verifies each new runtime dep's license **and** ToS (licenses sit beside ToS surprises, e.g. a permissive-license lib that phones home) |
| **Cadence** | pre-release audit: list every dep + license into `docs/legal/THIRD-PARTY-NOTICES.md` (a copy ships in the Docker image) |
| **Dev deps observed today** | `typescript@^5.0.0` + `@types/node@^20.0.0` (MIT/Apache-2.0 family; via `package-lock.json`) — verify each bump keeps it so |

**Hosts-only deps:** never plan around "the Dockerfile bundles X" without checking
X's license (e.g. `python:3.11-slim` ships OpenSSL which has its own permissive
license; Docker Compose is MIT). 🚩 Verifying distro/OAuth/Stripe terms at integration time.

---

## 8. Record-keeping: what to store, retention, legal hold

| Category | Store | Retention target | Notes |
|---|---|---|---|
| **Account & service records** | `users`, `api_keys` (hash only), `checks`, `samples`, `alerts`, deliveries, `audit_log` flags | While account active + **30d** after deletion | Enforce plan history limits (7d/90d/1yr) |
| **Security logs** | HTTP access logs (ip, ua, path), auth attempts, SSRF blocks | **30 days** rolling | Legitimate interest; minimise IP (truncate `/24`) |
| **Anti-abuse records** | rate-limit events, abuse flags | **12 months** | Needed to act on repeat abusers |
| **DSR records** | `dsr_requests` audit table | **Until request fulfilled + 3 yrs** | Prove compliance |
| **Billing/tax** | invoices, processor reports | **5–10 yrs** per jurisdiction | 🚩 NEEDS LAWYER/accountant |
| **Backups** | nightly encrypted DB snapshots | **30 days** | Deletion from backups on the next rotation |
| **Version archive** | every ToS/Privacy version ever published | **Indefinite** | For disputes |

**Legal hold:** when a request, litigation, or regulatory inquiry arrives, **suspend
deletion jobs for that user/data set** (legal-hold flag on `users`) until counsel
releases it. A hold overrides all §8 retentions and §10 deletions. Document the
hold in the same `audit_log`.

**Verify-able controls:** retention jobs run on a scheduler tick and log their
deletions to `audit_log`; a test asserts no record past retention survives a
tick (see §9).

---

## 9. Account termination & data deletion

### 9.1 User-facing flow (product copy + UX requirements)

1. **Settings → Account → "Delete my account"** (danger zone, red button). Only
   visible to the account owner; re-authentication (password prompt) required.
2. Pre-delete **warning sheet**: lists what is deleted (account, checks, samples,
   alert history, public links, API keys), what is retained by law (billing/tax
   for 5–10 yrs), and the **irreversibility** of the act. Export-first button
   ("Download my data") is offered before confirm.
3. **Confirm** → account enters `pending_deletion` for a **14-day grace period**
   (recoverable via login link) 🚩 NEEDS LAWYER — settle erasure-vs-grace policy:
   GDPR/law says erase "without undue delay", a grace period can still be OK if
   disclosed, but a consent-checker must bless it.
   - Publish the grace period in the ToS/Privacy — do not hide it.
4. After grace: hard delete (DB rows), revoke public slugs (404), revoke API keys,
   cancel scheduled checks + deliveries, then honour the **backup rotation** window
   (backups containing the user are overwritten within 30 days — disclose that this
   is the last copy).
5. Confirmation email ("your account was deleted on …; tax records retained until …")
   + audit log entry.

### 9.2 Internal checklist (operator-run)

- [ ] Verify identity (session + password re-auth, or email recovery link)
- [ ] Check not under **legal hold** — if held, do not delete; notify counsel
- [ ] Check for open **DSR/billing disputes** — surface, don't destroy, evidence
- [ ] Export on demand: `GET /privacy/export` generated and emailed (if requested)
- [ ] **Cascade delete** in one transaction: `samples WHERE check_id IN (SELECT …)`,
  `alerts`, `deliveries`, `alert_channels`, `checks`, `api_keys`, `sessions`,
  `users`; `VACUUM`; row-count assertion in tests
- [ ] Revoke **all public slugs** (`is_public=0`, slug tombstoned → 404)
- [ ] Disable scheduler for the user's checks
- [ ] Delete from **backups** on next rotation; log sweep completion in `audit_log`
- [ ] Confirmation email logged; `dsr_requests` audit row created with `fulfilled_at`
- [ ] Record any **retained-by-law** data (billing/tax) and its retention deadline
- [ ] Note: LGPD/GDPR erasure applies to controllers; per-user data in **third-party
  systems** (SMTP provider, payment processor) is handled by their own deletion API
  or PO-side clearing; log whichever happened.

### 9.3 What doesn't get deleted

- Anonymised/aggregated metrics that cannot identify a person (e.g. "check count").
- Tax and billing records for as long as the law demands (state it plainly).
- Audit-log *fact* that an account existed and was deleted (with `user_id`
  pseudonymised, not raw personal data) to prove compliance.

---

## 10. Self-hosted deployments (operational note)

- Self-host operators are **not** LatencyLedger's customers: every instance
  collects its own account data and therefore needs **its own ToS, Privacy Policy
  and cookie policy**. Ship a `docs/legal/self-host-checklist.md` template:
  replace every `[DOMAIN]`, set retention, list sub-processors (even if none),
  wire the DSR endpoints (§5.3), block private-target checks (already enforced by
  the SSRF guard), and meter data collection (no telemetry by default).
- The upstream repo's **legac/legal docs in this file are the canonical
  templates**; self-hosts should adapt, not adopt blindly. 🚩 NEEDS LAWYER for
  every production self-host bigger than a side project.

---

## 11. 🚩 "Needs a real lawyer review" checklist (before launch)

Do **not** treat this spec as clearance. Have counsel sign off on:

1. **Entity & jurisdiction** — legal form, governing law, court/arbitration venue,
   class-action waiver enforceability (esp. EU consumers).
2. **Liability cap** — max-amount clause and consequential-damages waiver lawful
   given your jurisdictions.
3. **Tax & billing** — VAT/sales tax, auto-renewal/disclosure, refund-rule fines for
   non-compliance, subscription-refund timelines (Stripe dispute window).
4. **DPA** — sub-processor list accuracy, SCCs/Art. 33 transfer mechanism for the
   host region, breach-notification SLA (72h), LGPD Art. 42 processor contract.
5. **RoPA + LIA** — GDPR Art. 30 record and the LGPD Art. 10 legitimate-interest
   balancing test documented.
6. **Erasure grace period** (14 days) — confirmable vs GDPR "without undue delay"
   and LGPD Art. 16.
7. **Age gate** — checkbox vs robust age verification.
8. **Copyleft deps** — no GPL/AGPL in any runtime dep; any OAuth/Stripe SDK/license
   checked at integration time.
9. **Trademark & domain** — "LatencyLedger" availability; USPTO/BR trademark search.
10. **Account deletion in consumers' sight** — EU "right to cancel in 2 clicks"
    and consumer contract rules apply if any consumer (non-business) users exist;
    decide whether you serve consumers at all or restrict ToS to business accounts.
