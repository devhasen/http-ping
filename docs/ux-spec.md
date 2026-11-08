# HttpPing — UX Specification

> Version: 1.0 — 2026-11-08 — Tandem with (pending) `product-spec.md`
> Product: web frontend for the `httpping` latency tool — measure HTTP request
> latency (per-request ms, min/max/avg) against any URL, visualise it, and
> compare targets over time.
> Frontend constraints: **static HTML/CSS/JS, no build step.** No framework,
> no bundler, no server-side rendering. All UX patterns below must be
> implementable with vanilla JS + CSS, a single `fetch` call shape, and no
> client-side router dependency.

---

## 1. Personas

### P1 — The Side-Project Builder ("Maya")
- **Role:** solo dev / indie hacker shipping a small API or landing page.
- **Tech level:** High. Comfortable with CLI, curl, logs. Distrusts magic.
- **Goals:** Quick answer to "is my endpoint slow, or is it just me?"; check
  latency after a deploy; share one link that proves it.
- **Pains:** Existing dashboards bury one number under charts and upsells;
  doesn't want to create an account to ping one URL; wants raw numbers, not
  a score out of 100.
- **Success looks like:** pastes a URL, gets min/max/avg in <5s, no sign-up.

### P2 — The On-Call / SRE ("Ravi")
- **Role:** ops engineer responsible for uptime, paged at 3am.
- **Tech level:** Expert. Thinks in percentiles, regions, and error budgets.
- **Goals:** Confirm whether latency spike is real, regional, or one bad node;
  compare "before vs after" a change; keep a watch running on a critical URL.
- **Pains:** Tools that average away the tail; alert fatigue; no way to see
  which request failed. Needs failed requests shown, not dropped.
- **Success looks like:** sees p50/p95 (or at minimum min/max/avg + per-request
  list), failed pings counted explicitly, history comparable at a glance.

### P3 — The Product Manager / Founder ("Elena")
- **Role:** non-technical stakeholder, cares about user-facing speed.
- **Tech level:** Low-medium. Uses browser, spreadsheets; no terminal.
- **Goals:** Understand "how fast is our site for visitors?" in plain language;
  screenshot a result for a stakeholder; track a competitor URL.
- **Pains:** Jargon (TTFB, p95, jitter) without explanation; charts that need
  a tutorial; doesn't know what a "count" or "region" means.
- **Success looks like:** one headline number + a plain-English sentence
  ("Addresses load in about 210 ms — fast"), with detail one click away.

### P4 — The QA / Evaluator ("Tom")
- **Role:** tester verifying a CDN, a staging deploy, or a partner API.
- **Tech level:** Medium-high. Precise, repetitive, checklist-driven.
- **Goals:** Run the same URL N times identically, record results, re-run and
  diff; check a URL in multiple regions/countries.
- **Pains:** Non-deterministic defaults (count silently changes), results not
  copyable/importable, no way to note what config produced a result.
- **Success looks like:** fixed, visible config (URL, count, method, region),
  one-click copy of the full run as text/CSV/JSON, reproducible re-run.

---

## 2. User Journey Maps (Top 3 Flows)

### Journey A — "Quick Check" (P1 / P3, primary flow)
*First time, no account, in <10 seconds.*

| Step | Touchpoint | Emotion (1–5) | Note / UX lever |
|------|-----------|---------------|-----------------|
| 1 | Lands on homepage | 3 | Hero shows the tool immediately: one big URL field above the fold, no marketing wall |
| 2 | Types/pastes URL | 3 | Field accepts `example.com` (auto-prefixes `https://`); validation is forgiving, not pedantic |
| 3 | Taps **Measure** | 4 | Single primary action; Enter submits; button label is a verb, not "Submit" |
| 4 | Loading | 3 → 4 | Live counter "3 of 10…" + progress bar; cancel available (see §6 loading) |
| 5 | Results | 5 | Headline trio **min / avg / max** + sparkline + per-request list; plain sentence for P3 |
| 6 | Share / re-run | 4 | "Copy link" encodes config in URL; "Run again" is one click, config preserved |

**Emotion curve:** flat-neutral → small dip at load → **peak at results**.
Design priority: the peak must be *instant and legible* — the three numbers
are the largest text on the results view, not the chart.

### Journey B — "Investigate a Spike" (P2)
*Returning user with saved targets.*

| Step | Touchpoint | Emotion | Note / UX lever |
|------|-----------|---------|-----------------|
| 1 | Opens dashboard, sees target list | 4 | Last-run summary per target (avg + status dot) — no blank screen |
| 2 | Selects the degraded target | 3 | Detail view opens on history, not on empty state |
| 3 | Compares runs | 3 | Run list with timestamp, count, min/avg/max; delta vs previous run shown |
| 4 | Drills into one run | 4 | Per-request table flags failures and outliers (>2× median) |
| 5 | Acts (re-run, adjust count, watch) | 4 | "Run again with 20" and "Add to watch" without re-typing URL |

**Emotion curve:** anxious (spike) → relief when data is findable →
confidence from the failure detail. **Key risk:** hiding failed requests —
they must be first-class, counted in a visible "2 of 12 failed" banner.

### Journey C — "Compare / Re-produce a Result" (P4 / P2)
*Needs an auditable, reproducible measurement.*

| Step | Touchpoint | Emotion | Note / UX lever |
|------|-----------|---------|-----------------|
| 1 | Sets URL + count + region | 3 | Config panel is explicit: every parameter visible, no hidden defaults |
| 2 | Runs | 3 | Deterministic count; "10 requested, 8 succeeded" stated, never silent |
| 3 | Exports | 4 | Copy as text / CSV / JSON — includes config + timestamp + per-request rows |
| 4 | Shares link | 4 | URL hash encodes full config; opening it reproduces the exact form |
| 5 | Watches over time | 4 | Saved target with history; scheduled re-run (if product offers it) |

**Emotion curve:** cautious → control → satisfaction. Any ambiguity about
"what exactly was measured" is a trust-killer; the config stamp on every
result is the fix.

---

## 3. Jobs-to-be-Done (per core feature)

| Feature | Job (When / I want / So I can) | Priority |
|---|---|---|
| **Single URL measurement** (core) | When I suspect a URL is slow, I want to enter it and get latency in seconds, so I can decide whether to dig deeper. | P0 |
| **Count selector** | When I need more confidence, I want to choose how many requests (5/10/20/50), so the average isn't one lucky sample. | P0 |
| **Results: min / avg / max + per-request list** | When a run finishes, I want the spread, not just the mean, so I can see consistency and outliers. | P0 |
| **Error surfacing** | When some pings fail, I want failures counted and listed, so I don't mistake "avg of 3" for "avg of 10". | P0 |
| **History / saved targets** | When I measured before, I want past runs one click away, so I can tell if things got better or worse. | P1 |
| **Copy / export (text, CSV, JSON)** | When I need to report a result, I want it in a format I can paste anywhere, so I don't retype numbers. | P1 |
| **Shareable link (config in URL)** | When I want a teammate to see the same thing, I want a link that reproduces my exact run, so there's no "which settings did you use?" thread. | P1 |
| **Multi-region / multi-target compare** | When latency varies by geography, I want to compare regions side by side, so I can tell if it's my server or the network path. | P2 |
| **Watch / scheduled checks + alerts** | When a URL is critical, I want it re-measured on a schedule, so I find degradation before users do. | P2 |
| **Plain-language summary** | When I'm not technical, I want "fast / okay / slow" in words, so I can act without learning jargon. | P1 |

**Out of scope for v1 UX:** accounts, billing, team workspaces (must not gate
Journey A), browser-execution proxies beyond the shipped measurement path.

---

## 4. Information Architecture

### 4.1 Navigation structure (single-level, flat — 4 destinations)

```
HttpPing
├── Measure          (default, /)          ← the tool itself, above the fold
├── History          (/history)            ← saved targets + past runs
├── Compare          (/compare)            ← multi-target / multi-region  [P2]
└── About / Help     (/about)              ← what the number means, method, FAQ
```

- No nested menus, no dropdown nav. A static site with no build step does not
  need a SPA router: plain anchor links, full-page or fragment navigation.
- The wordmark links home → `/`.
- Nav is a horizontal bar on desktop; on mobile it collapses to the same four
  links in a single row (see §7) — **no hamburger** for only 4 items.

### 4.2 Page hierarchy

```
/                         Measure (URL field, count, run, live results)
/   ├── result panel      (inline on same page — no page change on Run)
/   ├── per-request table (inline, collapsible)
/history
   ├── targets list
   └── /history/:target  run list → run detail (per-request rows)
/compare
   └── side-by-side table + overlaid sparkline (no new page level)
/about
   ├── method (how latency is measured, what min/avg/max mean)
/   └── FAQ
```

- **Depth ≤ 2** from home. Every page reachable in ≤2 clicks from anywhere.
- Results render **inline** on `/` (no route change) — keeps scroll position,
  shareable state lives in the URL hash (§4.4).

### 4.3 Breadcrumb rules

- Breadcrumbs appear **only at depth ≥ 2** (run detail, target detail).
- Format: `Home / History / <target> / <run>` — every crumb is a link except
  the last (current page, `aria-current="page"`).
- No breadcrumbs on `/`, `/compare`, `/about` — redundant on flat pages.
- Crumbs must not truncate the target name; wrap to two lines max on mobile.

### 4.4 URL / state rules (no router build step)

- Config (URL, count, region, method) encodes into the URL hash
  (`/#url=…&count=10`) so links are shareable and back-button safe.
- Hash is the single source of truth for form state on load — opening a
  shared link pre-fills the form exactly (Journey C).
- 404: static `404.html` with a link home and a re-measure box (not a dead end).

---

## 5. Usability Heuristics (Nielsen) → specific decisions

| # | Heuristic | Decision for HttpPing |
|---|---|---|
| 1 | **Visibility of system status** | During a run: live `n of N` counter + determinate progress bar + per-request dot filling in. Always show "10 requested · 8 succeeded · 2 failed" — never a silent partial. |
| 2 | **Match with real world** | Label the headline numbers *fastest / typical / slowest* alongside min/avg/max. The summary sentence uses words ("about 210 ms — fast"), not just statistics. |
| 3 | **User control & freedom** | Runs are cancellable mid-flight; "Run again" and "Reset" always available; editing the URL mid-run cancels cleanly, no stuck spinner. |
| 4 | **Consistency & standards** | One primary button per view, always bottom-of-form on mobile; units always `ms`; errors always "what + fix". The CLI (`httpping <url> [count]`) and web form order fields identically: URL, then count. |
| 5 | **Error prevention** | URL field auto-prefixes `https://`, strips trailing spaces/copy artifacts, confirms count changes before a long run (>50) with "this takes ~30s". `.example`/localhost allowed with a warning, not an error. |
| 6 | **Recognition over recall** | History shows last-run summary per target; form remembers last URL/count (localStorage); placeholder text shows a real example (`https://example.com`), not "Enter URL". |
| 7 | **Flexibility & efficiency** | Keyboard: Enter = Run, `/` focuses URL field (with visible hint), Esc cancels. Power path: shared hash links and copy/export. No forced onboarding tour. |
| 8 | **Aesthetic & minimalist** | One task per screen. Results = 3 big numbers + sparkline + table; nothing else competes. Settings beyond URL+count live behind a collapsed "Advanced" disclosure. |
| 9 | **Help users with errors** | Errors name the failure + next action: "Couldn't reach example.com (network error). Check the address, or try https://." Failed pings are listed per-request, each with its reason — never a lone "error". |
| 10 | **Help & documentation** | `/about` explains the method in 3 plain sentences + a glossary (latency, average, max). Contextual "?" next to min/avg/max with one-line definitions — no need to leave the page. |

---

## 6. State Patterns

### 6.1 Onboarding
- **No gate, no tour, no account.** First visit = the tool, with the URL field
  focused and placeholder = `https://example.com`.
- One 3-step inline hint under the field on first load only (dismissible, stored
  in localStorage, never shown again): *1 · Paste a URL · 2 · Choose how many
  times · 3 · Press Measure.*
- If the visitor arrives with a shared hash link, skip hints — the form is
  already explained by its pre-filled values.

### 6.2 Empty states
- **First run, no results:** results panel shows an illustration-free empty
  state — a dashed outline box: "No measurements yet. Enter a URL and press
  **Measure**." The field stays focused. Never a blank white panel.
- **History empty:** "Nothing saved yet — runs you revisit with 'Save target'
  appear here." CTA back to Measure.
- **Compare with <2 targets:** prompt to add a target; compare table disabled
  with explanation, not an empty grid.

### 6.3 Error states
- **Form errors (inline, next to field):** invalid URL → "That doesn't look like
  a URL — did you mean https://…?" Count out of range → clamp + note.
- **Run failures (per-request):** each failed row shows reason (timeout / DNS /
  refused / HTTP 5xx) in plain words; summary banner: "2 of 10 failed".
- **All-failed run:** full panel error with retry button + "check the URL" help
  link; headline numbers hidden (not zeros — fake numbers are worse than none).
- **Network down (whole app):** global offline banner (`navigator.onLine` +
  error event), Run button disabled with reason.

### 6.4 Loading states
- **Run in progress:** determinate progress bar + `n of N` + live per-request
  rows appearing one by one (streaming feel, no spinner-only void).
- **Cancel:** "Stop" button; partial results kept and labelled "stopped after 4 of 10".
- **Slow single request:** per-request timeout (e.g. 30s) with a visible
  "still waiting…" state — the UI never looks frozen.
- **Static site rule:** no skeleton screens for pages (they're instant); only
  the run has a loading state, and it is determinate.

---

## 7. Mobile / Responsive UX Rules (beyond layout)

- **Touch targets:** ≥44×44px for all interactive elements (WCAG 2.5.8 target
  size); Run button ≥56px tall, full-width on ≤480px. Per-request "details"
  toggles get 44px hit areas even if the visual row is shorter.
- **Form patterns:** `inputmode="url"` on the URL field (URL keyboard), `inputmode="numeric"`
  on count; `autocomplete="off"`, `autocapitalize="off"`, `spellcheck="false"` on the
  URL field; `type="url"` semantics. Count is a segmented control (5/10/20/50)
  + custom number input — native radio/segmented inputs, not divs.
- **No hover-only interactions:** sparkline data points, tooltips, and glossary
  "?" must work on tap — tap toggles a panel, tap-away dismisses. Long-press
  is never required.
- **Thumb zone:** primary actions (Run, Stop, Copy) in the bottom half on
  portrait; results trio stacks vertically, numbers ≥32px, never in a
  horizontally scrolling row.
- **Tables on mobile:** per-request table becomes a card list (one card per
  request: `#3 · 212 ms · ok`), not a sideways scroll. Compare table likewise.
- **Nav on mobile:** 4 links fit one row at 360px (short labels: Measure /
  History / Compare / About); no hamburger, no overflow menu.
- **Performance budget (mobile-first):** single static page ≤150KB transfer,
  zero JS frameworks, results paint incrementally so a slow connection still
  shows the finished rows. No `backdrop-filter` or heavy shadows on low-end
  hardware paths.

---

## 8. Accessibility Audit Plan — WCAG 2.2 AA, product-specific

Audit method: keyboard-only pass + screen reader pass (NVDA/VoiceOver) +
axe-core run + manual contrast check, on `/`, `/history`, run detail,
`/compare`, `/about`, in both success and all-failed states.

| WCAG 2.2 criterion | Product-specific check |
|---|---|
| 1.1.1 Non-text content | Sparkline has `role="img"` + text alternative (the trio numbers); status dots have text labels ("ok / failed"), never colour alone |
| 1.3.1 Info & relationships | Per-request rows are a real `<table>` (or list) with headers; min/avg/max labelled with `<dl>`/headings, not styled divs |
| 1.4.1 Use of colour | Status is text + icon + colour (redundant encoding); failed rows not identifiable by red alone |
| 1.4.3 Contrast (AA 4.5:1) | Numbers, body text, placeholder text all ≥4.5:1; the "fast/okay/slow" sentence ≥4.5:1 in both themes |
| 1.4.10 Reflow | 320px width: no horizontal scroll; results trio stacks; tables become cards (§7) |
| 1.4.12 Text spacing | Survives 200% text spacing without clipping the trio or table cards |
| 2.1.1 Keyboard | All actions reachable by keyboard: Run, Stop, copy, segment control, disclosures, crumbs, cards — no div-buttons |
| 2.4.3 Focus order | Focus order = visual order: URL → count → Run → results; live rows don't steal focus |
| 2.4.7 Focus visible | Visible focus ring (≥2px, 3:1 against adjacent colours) on every interactive element |
| 2.5.3 Label in name | Accessible name contains the visible label ("Run measurement", not "▶") |
| 2.5.8 Target size (AA) | ≥24×24px minimum, 44px per §7, no exceptions for the "?" glossaries |
| 3.2.3 Consistent navigation | Nav order + labels identical on every page; Run stays primary on every form |
| 3.3.1 Error identification | Failed pings and invalid URL described in text and linked to the field (`aria-describedby`), not colour alone |
| 3.3.3 Error suggestion | URL error suggests the fix ("did you mean https://…?"), all-failed run offers retry |
| 4.1.2 Name/role/value | Segmented count = `radiogroup`/`radio`; progress = `progressbar` with `aria-valuenow`; live counter = `aria-live="polite"` throttled |
| 4.1.3 Status messages | Run completion and "2 of 10 failed" announced via `aria-live` region; per-row updates NOT announced (no SR spam) — counter only |
| 2.2.1 Timing adjustable | No auto-playing anything; the run is user-initiated and stoppable; no session timeouts |
| 1.4.4 Resize text | 200% zoom: layout holds, trio numbers wrap, no clipped controls |

Additional product rules:
- Reduced-motion: `prefers-reduced-motion` disables the counting animation and
  sparkline draw-in; rows appear instantly.
- Colour-blind + monochrome check: the whole flow works in greyscale (labels carry the meaning).
- All-failed and offline states get the same audit pass as the happy path.

**Release gate:** zero WCAG 2.2 AA failures above; any failure = fix before merge.

---

## 9. Usability Test Plan — 5-User Protocol

### 9.1 Recruitment
- **5 participants**, 2 per persona where possible (P1, P2, P3, P4 mixed), screened
  by the persona questions in §1. Must include ≥1 non-technical (P3) and ≥1
  keyboard-only or screen-reader user if feasible; otherwise note the gap.
- 45 minutes each, moderated think-aloud, in-person or screen-share.
- Incentive + consent recorded; no account needed, tested as a fresh visitor.

### 9.2 Tasks (mapped to Journeys A/B/C)

| # | Task | Journey | Success criteria |
|---|---|---|---|
| T1 | "Measure how long `https://example.com` takes, 10 times." | A | Completes unassisted; reads min/avg/max correctly in own words; <60s |
| T2 | "Run it again with 20 and copy the result to share with a teammate." | A/C | Uses re-run or shared link; export produced; config matches request |
| T3 | "One of the pings fails — find out which one and why."* | B | Locates the failed row and states its reason; notes the "n of N failed" count |
| T4 | "Is this URL fast or slow? Explain it to a non-technical colleague." | A | Uses the plain-language summary; answer is correct in substance |
| T5 | "Compare this URL against another, and tell me which is slower." | B/C | Completes compare; picks the slower correctly; notices spread (max), not just avg |
| T6 | "You arrive from a shared link — set up the same test and run it." | C | Recognises the hash link pre-fills the form; re-runs without re-typing |

\* T3 uses a seeded failing URL (e.g. a closed port) — the only "rigged" task.

### 9.3 Metrics & pass thresholds
- **Task completion:** ≥4/5 on each task unassisted; T1 must be 5/5.
- **Time:** T1 median <60s; T2 <90s; others recorded, no hard gate.
- **Errors:** ≤1 critical error per task across 5 users (wrong answer counts —
  e.g. reading avg as "the" latency while ignoring a big max, or missing failures).
- **SUS (post-test):** mean ≥80 (top-quartile). Below 68 = redesign gate.
- **Qualitative:** every confusion point logged with the Nielsen heuristic
  violated (§5); ≥85% of findings fixed or scheduled before release.

### 9.4 Procedure
1. Intro + consent (2 min). 2. Tasks T1–T6, think-aloud, no hints; moderator
   only asks "what are you thinking?" (20 min). 3. Follow-ups: "What did
   min/avg/max mean to you?" / "Was anything missing?" (5 min). 4. SUS +
   debrief (5 min). 5. Findings synthesis within 48h → severity-ranked
   fix list mapped to §5 heuristics, tagged by persona.

### 9.5 Risks / notes
- 5 users finds ~85% of *discoverable* issues per Nielsen; treat results as
  directional, re-test after fixes with a second round of 5.
- Do not recruit only engineers — P3's jargon confusion won't appear otherwise.
- Test the all-failed state at least once (T3 covers the mixed case).

---

## Appendix — Traceability

| UX spec section | Consumed by |
|---|---|
| §1 Personas | Product spec scope calls; test recruitment (§9) |
| §2 Journeys | Page/feature priority; acceptance criteria per flow |
| §4 IA | Frontend routes, nav markup, breadcrumb component |
| §5 Heuristics | Code-review checklist: each heuristic = a review question |
| §6 States | Component states: empty / error / loading implementations |
| §7 Mobile | CSS breakpoints, form markup, touch-target audit |
| §8 A11y | CI: axe-core + manual gate; release checklist |
| §9 Test plan | Pre-release validation round (5 users, SUS ≥80) |

*If `docs/product-spec.md` changes scope (features, audience, regions),
revisit §1, §3, and §9 first — the rest is largely scope-independent.*
