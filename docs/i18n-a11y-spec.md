# LatencyLedger — i18n + Accessibility Specification

> Version 1.0 · 2026-11-08 · Status: Spec (not yet implemented)
> Product: LatencyLedger — continuous API latency regression tracking with CI gates (see `docs/product-spec.md`, `docs/architecture.md`, `docs/design-system.md`)
> Constraints: JSON locale files shipped statically; **no external services** (no CDN, no TMS, no hosted translation API, no analytics). Python 3.11+ stdlib-only backend + vanilla JS frontend with no build step.

---

## 1. i18n Architecture

### 1.1 Principles

1. **Static JSON only.** All strings live in JSON files served as static assets from the same origin. No runtime fetch to third-party i18n services.
2. **No string literals in markup or code.** Every user-facing string is a locale key resolved through `t()`. Hard-coded English in HTML/JS/Python is a lint error (see §3.3).
3. **Keys are semantic, not English-derived.** Key names describe *where/what*, never the English text: `checks.empty.title`, not `noChecksYetString`.
4. **English (`en`) is the source locale.** It ships complete first; `pt-BR` is translated from it. Missing keys fall back to English (never blank, never a raw key) — see §2.3.
5. **Numbers, dates, units, and plurals are never concatenated or hand-formatted.** They go through `Intl.*` (JS) / `locale`-aware stdlib formatting (Python) — see §1.5–§1.6.
6. **One locale per page load.** No mixed-language chrome. `<html lang>` always reflects the active locale.

### 1.2 File Layout

```
app/static/locales/
├── en.json          # source locale, complete
├── pt-BR.json       # Brazilian Portuguese
└── manifest.json    # { "default": "en", "supported": ["en", "pt-BR"], "fallbacks": {...} }
```

- Files are plain UTF-8 JSON, served with `Content-Type: application/json; charset=utf-8`.
- Files are loaded once per page load (script tag or `fetch` of the two JSON files); cached by the browser. No per-key network calls.
- Server-side (Python, for emails/alerts/CI messages) reads the same files from disk; no duplication. A single `locales/` directory is the source of truth for both tiers.
- CI validates every locale file: valid JSON, identical key sets to `en.json`, no empty strings, valid ICU-style placeholders (see §1.4).

### 1.3 `t()` Helper

#### Vanilla JS (frontend)

```js
// app/static/i18n.js — no dependencies
const I18n = (() => {
  let dict = {}, fallback = {}, locale = "en";
  async function init(loc) {
    locale = normalize(loc);
    dict = await (await fetch(`/static/locales/${locale}.json`)).json().catch(() => ({}));
    fallback = locale === "en" ? {} : await (await fetch(`/static/locales/en.json`)).json();
    document.documentElement.lang = locale;
  }
  const pluralRule = (n) => new Intl.PluralRules(locale).select(n);
  function t(key, vars = {}, count) {          // t(key, vars), t(key, vars, count)
    let node = dict, fb = fallback;
    for (const part of key.split(".")) { node = node?.[part]; fb = fb?.[part]; }
    if (count !== undefined && node && typeof node === "object") node = node[pluralRule(count)] ?? node.other;
    if (count !== undefined && fb && typeof fb === "object") fb = fb[pluralRule(count)] ?? fb.other;
    let s = typeof node === "string" ? node : (typeof fb === "string" ? fb : key);
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
    return s;
  }
  return { init, t, get locale() { return locale; } };
})();
```

Usage in markup: `data-i18n="checks.empty.title"` attributes are hydrated on load; dynamic strings call `t()` directly. Interpolation uses `{name}` placeholders only — never string concatenation (`"p95 rose " + x + "ms"` is forbidden; use `t("alert.regression.body", { from, to })`).

#### Python stdlib (backend: emails, webhook/Slack payloads, API error details)

```python
# app/i18n.py — stdlib only (json, pathlib, re)
import json
from pathlib import Path

_LOCALES = Path(__file__).parent / "static" / "locales"
_cache: dict[str, dict] = {}

def _load(locale: str) -> dict:
    if locale not in _cache:
        _cache[locale] = json.loads((_LOCALES / f"{locale}.json").read_text("utf-8"))
    return _cache[locale]

def _get(d: dict, key: str):
    for part in key.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d

def t(key: str, locale: str = "en", **vars) -> str:
    """Resolve key in locale, fall back to en, final fallback = key itself."""
    s = _get(_load(locale), key) or _get(_load("en"), key) or key
    if isinstance(s, dict):  # plural node reached without a count — last resort
        s = s.get("other", key)
    for k, v in vars.items():
        s = s.replace("{" + k + "}", str(v))
    return s

def user_locale(user) -> str:
    """User preference → Accept-Language → 'en'. See §2.2."""
```

- Python pluralization: implement CLDR plural categories for supported locales (`en`, `pt-BR` — both one/other in practice) in `plural(locale, n)` mirroring `Intl.PluralRules`; do not use `gettext` (adds tooling) — the JSON + small helper covers the launch scope.
- API error bodies keep machine-readable `error` codes (`"invalid_url"`); the human `detail` field is localized via `t()` using the request locale. Error codes are **never translated**.

### 1.4 Message Format, Plurals, Variables

- **Interpolation:** `{var}` placeholders. Variable names are ASCII, lower_snake. Translators must preserve them exactly.
- **Plurals:** JSON nodes are objects keyed by CLDR category:

  ```json
  "checks": { "count": { "one": "{count} check", "other": "{count} checks" } }
  ```

  `en`: `one` for 1, `other` otherwise. `pt-BR`: `one` for 0–1 (CLDR: 0 and 1 use `one` in Portuguese), `other` otherwise — handled by `Intl.PluralRules("pt-BR")` in JS and the matching Python helper. Never hard-code "add 's'".
- **Gender / word order:** If a future locale needs it, add `gender`/`case` variants as object keys; the launch locales do not need them.
- **Markup in strings:** Avoid HTML inside JSON strings. Where a string needs emphasis, use `{0}` placeholder for a wrapped element or two separate keys. No `innerHTML` with locale strings.
- **Length budget:** Strings should be ≤30% longer than English (pt-BR typically ~15–25%). UI layouts must tolerate +40% text expansion (see §5).

### 1.5 Date / Time Formatting

| Tier | API | Notes |
|---|---|---|
| JS | `Intl.DateTimeFormat(locale, { dateStyle, timeStyle, timeZone })` | Always pass explicit `timeZone` (user's, from profile or UTC with label). Never `toLocaleString()` without locale. |
| Python | `datetime.strftime` is **locale-unaware by default** — format ISO 8601 (`2026-11-08T03:22:00Z`) for storage/API; format for humans in the browser via `Intl`. Email bodies: hand-format `"%Y-%m-%d %H:%M UTC"` (unambiguous) rather than pretending locale-correct output. | Storage is always UTC ISO 8601. Display is always localized. |

- Relative times ("5 min ago") use `Intl.RelativeTimeFormat(locale)` in JS; Python emails use absolute UTC timestamps to avoid wrong relative math.
- Durations: `Intl.NumberFormat(locale, { style: "unit", unit: "millisecond" })` for ms values where a unit label is needed; API payloads carry raw numbers (`ms: 389`), never pre-formatted strings.

### 1.6 Number Formatting

- JS: `Intl.NumberFormat(locale)` for counts, thousands separators (en-US `1,234` vs pt-BR `1.234`), and decimals. Percentiles in ms are rounded via `Intl.NumberFormat(locale, { maximumFractionDigits: 0 })`.
- Python: values in JSON APIs are raw numbers. Human-readable email numbers use `f"{n:,}"` only for English; for pt-BR, format with the small helper `fmt_num(n, locale)` (stdlib, no `locale` module dependency on server locale settings — implement grouping manually: `,` en, `.` pt-BR).
- Never format a number server-side and re-parse it client-side.

---

## 2. Launch Locales & Locale Selection

### 2.1 Launch Locales (2)

| Locale | Code | Status at launch | Notes |
|---|---|---|---|
| English | `en` (UI strings written against `en-US` conventions) | Source, complete | Default and fallback. |
| Brazilian Portuguese | `pt-BR` | Translated from `en`, reviewed before launch | `pt-BR` only — not European Portuguese. Use the glossary in §4.3. |

**Locale count at launch: 2.** No other locale ships in sprint 1. The manifest lists `supported: ["en", "pt-BR"]`; unknown locales degrade gracefully (§2.3) rather than 404ing.

### 2.2 Route / Query / Preference Strategy (in priority order)

```
1. Explicit user preference  (account setting, persisted server-side: users.locale)
2. URL query parameter        (?lang=pt-BR)  — shareable, overrides for that visit, does not persist
3. Accept-Language header     — first supported match (en, pt-BR, pt→pt-BR, en-*→en)
4. Default: en
```

- **No locale-prefixed routes** (`/pt-BR/checks`) in sprint 1. The app is a single-page dashboard; a path prefix would break public report links (`/r/{slug}`), CI endpoints, and shared URLs. Locale is runtime state, not URL state.
- `?lang=` is validated against the manifest; unknown values are ignored (fall through to the next priority), never an error page.
- The resolved locale is set three places on every response: `<html lang>`, `Content-Language` response header, and the `t()` context for server-generated strings (emails use the recipient's `users.locale`).
- Switching language is a `<select>` in the header (same control as in §7), applies immediately without reload (re-hydrates `data-i18n` nodes + re-renders dynamic strings), and persists to the account. Public report pages (`/r/{slug}`) respect `?lang=` / `Accept-Language` but never persist anything (no account).

### 2.3 Fallbacks

| Situation | Behavior |
|---|---|
| Key missing in `pt-BR` | Use English string. Log a CI warning (key-set diff check, §3.3) so it is caught before merge, not at runtime. |
| Key missing in both | Render the key itself (visible failure > silent blank). |
| Locale file fails to load (network) | Fall back to English dict already bundled as last resort; page still renders. |
| Unsupported `Accept-Language` (e.g. `fr`) | `en`. Never 406. |
| Malformed JSON | CI rejects the PR; runtime: treat as empty dict → English fallback. |

---

## 3. Translation Workflow (No Paid TMS)

### 3.1 Process

1. **Write English first.** New strings are added to `en.json` only, in the same PR as the feature. Keys are namespaced by feature (`checks.*`, `alerts.*`, `auth.*`, `gate.*`, `email.*`, `public.*`).
2. **Extract & diff.** A stdlib-only script (`python tools/check_locales.py`) compares every locale against `en.json`: missing keys, extra keys, empty values, placeholder mismatches (`{count}` present in en but not pt-BR), and plural-category mismatches. It runs in CI and fails the build on any diff. Output is a plain-text report — no service.
3. **Translate.** Maintainer (or contributor) edits `pt-BR.json` directly in a PR. No web console, no TMS. Git *is* the TMS: diffs are reviewable, history is blameable, rollbacks are `git revert`.
4. **Review.** A second reader (ideally a native pt-BR speaker; see §4) reviews the JSON diff in the PR. Machine translation may produce a first draft but must be human-edited before merge — raw MT of technical strings produces the exact errors §4 warns about.
5. **Ship.** Locale JSON files deploy with the app (same Docker image, same static serve). No separate deploy step.

### 3.2 Cadence & Ownership

- Translation is part of the feature PR, not a later batch. A PR that adds UI strings without `en.json` entries fails CI (§3.3).
- `pt-BR` lag is acceptable: fallback (§2.3) covers gaps. A "translation debt" issue is filed automatically when the diff script reports missing keys, and it blocks release only if the string is on a P0 user path (auth, check create, alert, gate result).
- No paid TMS, no per-word billing, no vendor accounts. Total i18n tooling budget: two stdlib Python scripts + one JS file.

### 3.3 Guardrails (CI)

| Check | Tool | Fails build? |
|---|---|---|
| All locale files valid JSON, UTF-8 | `check_locales.py` (stdlib `json`) | Yes |
| Key sets identical to `en.json` | same | Yes (missing key) / warning (extra key) |
| No empty or whitespace-only values | same | Yes |
| Placeholders match `en.json` exactly | same | Yes |
| Plural categories match `Intl.PluralRules` for the locale | same (hard-coded CLDR categories for en/pt-BR) | Yes |
| No hard-coded user-facing strings in JS/HTML/Python | `grep` lint for banned patterns in CI (`console.log` strings are exempt; `innerText = "` / `>England<` style patterns flagged) | Warning → review |
| `pt-BR` strings not byte-identical to English (except glossary terms) | same | Warning (catches untranslated copy-paste) |

---

## 4. Translator Guide

### 4.1 Style Rules

1. **Translate meaning, not words.** LatencyLedger copy is plain, evidence-first (design-system principle #1). Short sentences. Active voice. Second person ("your check"), never impersonal constructions.
2. **Keep numbers and units separate.** Never write the number as a word ("twenty percent" → use `{pct}` variable). Units: `ms` stays `ms` in both locales (see glossary).
3. **Do not translate placeholders.** `{count}`, `{url}`, `{p95}` pass through byte-identical.
4. **Do not add or remove markup, line breaks, or emphasis** that isn't in the English source.
5. **pt-BR conventions:** formal-but-friendly "você"; avoid "o senhor/a senhora". Use Brazilian terminology (e.g. *latência*, not *latência* from PT-PT tiptoeing — see glossary). Date/number formats are handled by code (§1.5–§1.6) — write "{date}" variables, never a formatted date inside a sentence.
6. **Length:** Aim ≤ +30% over English. If a pt-BR string needs much more space, flag it — the UI must not clip (see §5).
7. **Tone for alerts:** Bad news is stated plainly with numbers ("p95 subiu de 212ms para 389ms"), never euphemized, never with exclamation marks.

### 4.2 What Not To Do

- Do not translate product/technical terms in §4.3.
- Do not translate URLs, API paths (`/api/v1/checks`), HTTP status text ("OK", "Not Found"), CSS class names, or JSON keys.
- Do not "improve" the English source while translating — file a separate issue instead.

### 4.3 Glossary — Untranslatable / Do-Not-Translate Terms

| Term | pt-BR | Rule |
|---|---|---|
| LatencyLedger, p50, p95, p99 | LatencyLedger, p50, p95, p99 | Product name and percentile notation are identical in both locales. |
| `ms` (millisecond) | `ms` | Unit abbreviation never changes, never indented with a space in code-generated strings. |
| API, CI, URL, JSON, CSV, HTTP, status code | API, CI, URL, JSON, CSV, HTTP, código de status | Acronyms stay; expand on first use in long-form copy only. |
| "Ping", "ping now" | "Ping", "Ping agora" | Keep "ping" as the product verb (it matches the repo CLI `httpping`). |
| "Check" (a monitored URL) | "verificação" | Use *verificação* consistently; never *cheque* (wrong sense) or *check*. |
| "Alert" | "alerta" |  |
| "Baseline" | "linha de base" | Rolling 7-day baseline; first use may add "(baseline)" in English copy. |
| "Regression" | "regressão" | Latency regression, not software regression testing. |
| "Budget" (CI latency budget) | "orçamento" | e.g. *orçamento de latência*; never *budget* in pt-BR prose. |
| "Gate" (CI gate) | "portão" (CI) / "gate" in code contexts | Verb use: "bloquear o PR". UI label: prefer *gate de CI* with English in parentheses on first occurrence. |
| API key, slug, webhook | chave de API, slug, webhook | *webhook* stays English; *slug* stays (public report slug). |
| SHA / git SHA / commit | SHA / commit | Hashes themselves are never localized. |
| "Report" (public report link) | "relatório" |  |

New terms discovered during translation are added to this glossary in the same PR.

---

## 5. RTL Readiness Notes

- **Launch locales (en, pt-BR) are both LTR.** Full RTL support is explicitly out of scope for sprint 1. These notes exist so sprint-1 code doesn't paint itself into a corner.
- **Use logical CSS properties** (`margin-inline-start`, `padding-inline-end`, `inset-inline-start`) instead of physical (`margin-left`). New CSS must pass a lint review for physical properties on directional rules.
- **Do not use left/right in icon design** for directional meaning (back/forward arrows). Use `transform: scaleX(-1)` under `[dir="rtl"]` for chevrons and progress arrows.
- **Charts:** canvas axes are data-driven, not text-driven; keep the time axis flowing in the locale's reading direction by using `Intl` numbers for tick labels. Numbers themselves (ms values, percentages) stay LTR-wrapped (`dir="ltr"` on `<code>`/mono values) per WCAG 1.3.2/3.1.2.
- **Set `dir` on `<html>`** from the locale table in `manifest.json` (`"dir": "ltr"` now; a future `ar`/`he` entry flips it). All layout must key off `[dir]` selectors, not JS-detected language.
- **No RTL bugs are blocking at launch** (no RTL locales ship), but the checklist (§8) includes the logical-property rule so it stays true.

---

## 6. Accessibility — WCAG 2.2 AA Targets

### 6.1 Conformance Target

**WCAG 2.2 Level AA** for all public and authenticated pages (dashboard, check detail, public report `/r/{slug}`, status page P1, auth pages, emails are best-effort — see §6.7). Conformance is claimed per-page, not per-site, until every P0 route passes §7. Level AAA is not a target (exceptions noted in §6.8).

Success criteria explicitly in scope beyond WCAG 2.1 AA: **2.4.11 Focus Not Obscured (Minimum)**, **2.5.8 Target Size (Minimum) — 24×24 CSS px min (we ship ≥40px, exceeding AA)**, **3.3.7 Redundant Entry**, **3.3.8 Accessible Authentication (Minimum)** — no password-manager-hostile auth (no paste-blocking, no cognitive tests).

### 6.2 Semantic HTML Rules

- One `<h1>` per page; heading order never skips a level (`<h2>` after `<h1>`, etc.). Page title (`<title>`) names the page and product: `Check name · LatencyLedger`.
- Landmarks: `<header>`, `<nav aria-label="Primary">`, `<main id="main">`, `<footer>`. One `<main>` per page.
- Lists are lists: checks dashboard uses `<ul>`/`<li>`; stats use `<dl>` or a real `<table>` with `<th scope>`. Never a `<div>` grid pretending to be a table for tabular data (chart data table alternative: §6.5).
- Interactive elements are native where possible: `<button>`, `<a>`, `<input>`, `<select>`. Custom controls (chart tooltip, language switcher) use the correct `role` + keyboard behavior (§6.4).
- Statuses are text, not color: every status dot/color chip is paired with an icon **and** a text label ("Regressão", "OK") per design-system token rule. `aria-hidden` on the decorative icon; the label carries the meaning.
- Images/canvas: `role="img"` + `aria-label` summary + adjacent text summary (§6.5). No information conveyed by image alone.
- Form inputs: every `<input>`/`<select>` has a `<label for>`; errors use `aria-describedby` + `role="alert"` on the summary (§6.6). Placeholders are never labels.
- Language: `<html lang="en">` / `lang="pt-BR"` always set; inline foreign-language content (a user's check name in another language) gets `lang` on the element. `lang` changes trigger a full re-render.

### 6.3 Focus Management

- **Visible focus:** `:focus-visible` outline `2px solid var(--accent)` with `2px` offset on every interactive element; never `outline: none` without a replacement. Over dark/light themes the accent passes 3:1 against both backgrounds (verified in design tokens).
- **Focus order = reading/DOM order.** No positive `tabindex`. (`tabindex="-1"` only for programmatic focus targets: `<main>` skip target, alert region, dialog.)
- **Focus Not Obscured (2.4.11):** Sticky headers/footers never cover the focused element — scroll padding (`scroll-padding-top`) equals header height; focused elements get `scroll-margin` where they can land under overlays.
- **Route changes:** SPA-style re-renders and full page loads move focus to `<main tabindex="-1">` (or the page `<h1 tabindex="-1">` pattern). Focus is never left on a removed element (focus falls to `<body>` is a failure).
- **Dialogs/menus** (API key reveal, check delete confirm, language menu): trap focus while open, `Esc` closes, focus returns to the triggering control on close. `aria-modal="true"`, `role="dialog"`, labelled by heading. The "key shown once" dialog moves focus to its heading on open; closing returns focus to the keys list.
- **Focus never lost on live updates:** Background data refresh (new samples, chart tick) never moves focus or re-renders the focused node in place. Refresh updates text/`aria-live` regions only.

### 6.4 Skip Links

- First focusable element on every page: **"Skip to main content"** (`<a href="#main" class="skip-link">`), visually hidden until focused, then visible at top with accent outline. Target: `<main id="main" tabindex="-1">`.
- Second skip link (dashboard + check detail): **"Skip to check list"** / **"Skip to chart data"** where the page is long. Public report pages: skip to chart summary.
- Skip links are first in DOM order on every page including auth and public-report pages (no exceptions for "simple" pages).

### 6.5 Live Regions, Charts, and Non-Text Content

- **Latency chart:** `<canvas role="img" aria-label="…">` with a plain-language summary in text immediately following (in §2, `aria-describedby` points there): "p95 rose from 212 to 389 milliseconds between 02:10 and 04:00 UTC, crossing the 400 millisecond budget." The summary is regenerated from the same data, in the active locale, via `Intl.NumberFormat`.
- **Data table alternative:** A visually-hidden (or toggleable) `<table>` of the bucketed series (time, p50, p95) mirrors the chart per WCAG 1.1.1/1.2.5. Toggle is a real `<button aria-expanded>`, not hover.
- **Live regions:**
  - `aria-live="polite"` status region for non-urgent updates ("Check updated — p95 212ms"), announced at most once per refresh cycle, auto-cleared.
  - `role="alert"` for regression/down events and form errors (assertive, interruptive — used sparingly, only for genuine alerts).
  - "Ping now" results: `aria-live="polite"` summary after completion; per-request results are in the results table (not announced one by one).
  - Alert banners (`design-system.md` Alert banner component): `role="alert"` once on injection, then static text (no re-announcing on re-render).
- **Motion:** Honor `prefers-reduced-motion` — chart draws render statically (no animated transitions, no drawing animation), toasts appear without slide, spinners become static "Loading…" text. Media query in CSS **and** a JS check for canvas animation. No auto-playing content anywhere.
- **Flashing:** No content flashes >3 times/second (no exceptions; no flashing content exists by design).

### 6.6 Forms & Errors

- Errors are identified in text (not color alone), described per field via `aria-describedby`, and summarized at the top of the form with anchor links to each field (focus moves to the summary on submit-with-errors).
- Required fields: `required` + visible "(required)" text (never `*` alone). Autocomplete tokens on auth forms (`email`, `new-password`, `current-password`), `type="email"` for email, `inputmode` where relevant.
- Paste is never blocked (3.3.8); the API key "shown once" view offers a copy button **and** selectable text fallback.
- The check-URL validation error (non-http, too long, private IP) is a text message naming the problem, linked to the field, localized via `t("checks.errors.*")`.

### 6.7 Color, Contrast, and Zoom

- Text contrast ≥4.5:1 (AA); large text ≥3:1. Design tokens promise ≥7:1 for primary text on `--bg` — verified in §7; `--muted #9aa3af` on `#0f1115` is ≥4.5:1 (checked; do not use `--muted` for small text below 12px).
- Status colors (`--ok`, `--warn`, `--bad`) always paired with icon + text (§6.2) — contrast of the color itself is not the sole conveyor (1.4.1).
- Layout holds at 200% zoom / 320 CSS px width without horizontal scroll (1.4.10 Reflow at AA: 320px). No fixed-height text containers; text wraps, it doesn't clip.
- Touch targets ≥40×40px per design system (exceeds WCAG 2.2 AA 24px minimum, 2.5.8). Adjacent targets have ≥8px spacing.

### 6.8 Keyboard Map

| Key | Action | Scope |
|---|---|---|
| `Tab` / `Shift+Tab` | Move forward / backward through all interactive elements | Everywhere |
| `Enter` / `Space` | Activate focused button/link; toggle checkboxes/switches | Native on `<button>`, `<a>`, `<input>` |
| `Esc` | Close open dialog, menu, or tooltip | Dialogs, menus, language switcher |
| `↑` `↓` ← `→` | Move within composite widgets (tabs, menu, table rows nav if implemented as grid) | Composite widgets only |
| `Home` / `End` | First/last item in a composite widget | Tabs, menus |
| `/` | Focus main search/filter input (dashboard check filter) | Dashboard only; `Esc` returns focus |
| `?` | Open keyboard-shortcut help dialog | Authenticated app only |
| `g d` (two-key) | Go to Dashboard | Authenticated app only (roving, never while typing in a field) |
| `g c` | Go to Checks list | Authenticated app only |
| `Shift+?` | Same as `?` | Authenticated app only |

Rules: single-key shortcuts never fire while focus is in a text field, `<select>`, `<textarea>`, or content-editable. Every shortcut has a visible equivalent (a button/link doing the same thing) — shortcuts are accelerators, never the only path. Shortcut help (`?`) lists every binding; bindings are documented in the help dialog itself (self-describing).

### 6.9 Emails (best-effort AA)

Regression and alert emails use semantic HTML (real heading/p structure, table-based layout only where email clients require it, alt/role text on any image). They are plain-language text-first: the HTML email includes a `text/plain` part with the same content. Email clients can't guarantee focus/ARIA behavior; the web alert log is the canonical accessible record.

---

## 7. A11y Testing Plan

### 7.1 Automated Checks (CI + pre-merge)

| Check | Tool (no external service) | Scope | Gate |
|---|---|---|---|
| axe-core rule violations | `axe-core` vendored locally (no CDN), run via a small Node script or python `playwright` if available; otherwise vendored JS in a test page | Every P0 route, both locales, both themes | 0 critical/serious violations |
| HTML validity (landmarks, heading order, label association) | `axe-core` rules + a stdlib HTML parser lint in CI | All static pages | 0 errors |
| Contrast ratios (tokens + computed styles) | Token contrast script (stdlib, computes WCAG ratios from `design-system.md` hex values) | All token pairs used for text | ≥4.5:1, fails build |
| Locale file integrity | `tools/check_locales.py` (§3.3) | `en.json`, `pt-BR.json` | Fails build on diff |
| Keyboard-only smoke test (scripted) | Playwright/selenium tab-through asserting focus lands on expected landmarks and every interactive element is reachable | Dashboard, check detail, auth, public report | Every focusable element reachable; focus visible |

- axe checks run against **both locales** — pt-BR's longer strings expose overflow/overlap bugs English hides.
- axe runs at 320px and 1280px widths, and with reduced-motion forced on.

### 7.2 Manual Keyboard Walkthrough (per release)

Tester performs this script with keyboard only, screen reader off first, then with one screen reader (NVDA+Firefox or VoiceOver+Safari):

1. **Tab from top of page** on dashboard → lands on skip link → activates → focus reaches `<main>`. Continue tabbing: header nav → language switcher → account → check list → every row action reachable in DOM order.
2. **Create a check** by keyboard only: fill name, URL, interval `<select>`, submit with an invalid URL → error summary receives focus → follow anchor link to field → fix → submit succeeds → focus moves to the new check's row (or status region announces it).
3. **Ping now** by keyboard → wait for results → results table reachable; summary announced via live region (verify with screen reader).
4. **Open API-key dialog** → focus trapped inside → `Esc` closes → focus returns to the "Generate key" button. Key text is selectable/copyable.
5. **Chart:** canvas has `role="img"` + label; toggle the data table → table is fully keyboard-navigable; chart summary text matches data.
6. **Language switch to pt-BR** → `<html lang>` updates, all chrome re-renders in pt-BR, focus stays on the switcher, no text clips or overflows at 320px and 200% zoom.
7. **Public report page** (logged out) → same walkthrough: skip link, chart summary, data table, no login wall traps focus.
8. **Reduced motion** on (OS setting) → reload → no animations; chart renders statically; toasts appear instantly.
9. **Screen reader pass:** NVDA/VoiceOver reads dashboard landmarks, check rows (name, URL, status as text), stats, and the regression alert banner (`role="alert"` fires once). No "image" with no label, no unlabeled buttons.

### 7.3 Test Matrix

| Dimension | Values tested |
|---|---|
| Locale | `en`, `pt-BR` |
| Theme | dark (default), light |
| Width | 320px, 768px, 1280px; 200% zoom at 1280px |
| Input | keyboard only, mouse, touch (≥40px targets spot-check) |
| Motion | `prefers-reduced-motion: reduce` on/off |
| Screen reader | NVDA + Firefox, VoiceOver + Safari (one per release, §7.2) |
| Browser | latest Chrome/Firefox/Safari (spot-check, not exhaustive) |

Bugs found in manual passes are filed with: route, locale, viewport, steps, expected vs actual, and tagged `a11y`. A P0-route WCAG AA failure blocks the release milestone (M2).

---

## 8. A11y Audit Checklist (Build-Team Sign-Off)

> Sign-off requires every item checked on **each P0 route** (dashboard, check detail, auth, public report) in **both locales**. Initial and date each section. Any unchecked item blocks the release milestone.

**A. Language & i18n**
- [ ] A1. `<html lang>` matches active locale on every page (`en` / `pt-BR`).
- [ ] A2. `Content-Language` header matches active locale on every response.
- [ ] A3. No hard-coded user-facing strings in HTML/JS/Python (all via `t()`).
- [ ] A4. `check_locales.py` passes — identical key sets, no empty values, placeholders intact.
- [ ] A5. No mixed-language chrome (no untranslated English strings in pt-BR UI, except §4.3 glossary terms).
- [ ] A6. Numbers/dates/units formatted via `Intl`/locale helpers — no hand-formatted or concatenated numbers.
- [ ] A7. Plurals use CLDR categories (`one`/`other`) via `Intl.PluralRules` — no manual "s" logic.
- [ ] A8. Language switcher works without reload, persists to account, focus stays on switcher, `?lang=` respected on public pages.
- [ ] A9. Missing-key fallback renders English (not blank, not raw key) in pt-BR.
- [ ] A10. Long strings (+40%) do not clip/overlap at 320px or 200% zoom in either locale.

**B. Semantic Structure**
- [ ] B1. Exactly one `<h1>` per page; heading levels never skipped; `<title>` names page + product.
- [ ] B2. Landmarks present: `<header>`, `<nav aria-label>`, `<main id="main">`, `<footer>` — one `<main>` per page.
- [ ] B3. Data presented as real lists/tables (`<ul>`/`<table>` with `<th scope>`); no div-grids for tabular data.
- [ ] B4. Interactive elements are native (`<button>`, `<a>`, `<input>`, `<select>`) or have correct roles.
- [ ] B5. Status conveyed by icon **and** text label — never color alone (dots/chips pass this).

**C. Keyboard & Focus**
- [ ] C1. Every interactive element reachable and operable by keyboard alone (§7.2 walkthrough passes).
- [ ] C2. Visible focus indicator (2px accent) on every interactive element, both themes; `outline: none` never appears without replacement.
- [ ] C3. Focus order matches DOM/reading order; no positive `tabindex`.
- [ ] C4. Focus is moved to `<main>`/`<h1>` on route change; never left on a removed element.
- [ ] C5. Dialogs trap focus, close on `Esc`, return focus to trigger (API key dialog verified).
- [ ] C6. Background refresh/live updates never move focus or steal it.
- [ ] C7. Focus Not Obscured (2.4.11): sticky header/footer + `scroll-padding` never hide the focused element.
- [ ] C8. Skip link is first focusable element, visible on focus, lands on `<main tabindex="-1">` (all pages).
- [ ] C9. Single-key shortcuts (`/`, `?`, `g d`, `g c`) never fire inside form fields; every shortcut has a visible equivalent; `?` help lists all bindings.

**D. Live Regions, Charts & Motion**
- [ ] D1. Chart canvas has `role="img"`, localized `aria-label` summary, and `aria-describedby` to adjacent text summary.
- [ ] D2. Chart data-table alternative exists, toggled by a real `<button aria-expanded>`, mirrors the data.
- [ ] D3. Non-urgent updates use `aria-live="polite"` (announced once per cycle); alerts/errors use `role="alert"` (fires once).
- [ ] D4. "Ping now" completion announced via live region; per-request results are in a reachable table.
- [ ] D5. `prefers-reduced-motion` honored: no chart/toast/spinner animation; static alternatives shown.
- [ ] D6. No content flashes ≥3×/second (no flashing content by design).

**E. Forms, Color & Targets**
- [ ] E1. Every input has a programmatic `<label for>`; placeholders are not labels.
- [ ] E2. Errors are text + `aria-describedby` per field, summarized at top with anchor links; focus moves to summary on failed submit.
- [ ] E3. Required fields marked with `required` + visible "(required)" text; autocomplete tokens correct on auth forms.
- [ ] E4. Paste never blocked; API key shown once is both copyable and selectable.
- [ ] E5. Text contrast ≥4.5:1 (large text ≥3:1) for all token pairs in both themes — token script passes.
- [ ] E6. Layout reflows at 320px / 200% zoom without horizontal scroll or clipping.
- [ ] E7. Touch targets ≥40×40px with ≥8px spacing between adjacent targets.
- [ ] E8. Long locale strings (+40%) do not overflow containers in either locale (pt-BR verified).

**F. Automated & Manual Testing**
- [ ] F1. axe-core: 0 critical/serious violations on all P0 routes, both locales, both themes, 320px + 1280px.
- [ ] F2. axe-core run with reduced-motion forced on: 0 critical/serious violations.
- [ ] F3. HTML validity / landmark / heading-order lint passes in CI.
- [ ] F4. Scripted keyboard-only tab-through passes (every interactive element reachable).
- [ ] F5. Manual keyboard walkthrough (§7.2, steps 1–9) completed on current build.
- [ ] F6. Screen-reader pass completed (NVDA+Firefox or VoiceOver+Safari): landmarks, rows, stats, alert banner all announced correctly.
- [ ] F7. Reduced-motion manual pass completed (OS setting on, no animations).
- [ ] F8. pt-BR manual pass completed: all chrome translated, no overflow, dates/numbers correctly localized.

**G. Sign-Off**

| Role | Name | Date | Pass / Fail |
|---|---|---|---|
| i18n engineer |  |  |  |
| Frontend / build engineer |  |  |  |
| Product Manager |  |  |  |
| QA / accessibility reviewer |  |  |  |

*Total checklist items: 46 (A1–A10, B1–B5, C1–C9, D1–D6, E1–E8, F1–F8). All must be checked for milestone sign-off.*

---

## Appendix: Open Questions for Build Team

1. Should server-side email timestamps be localized (Python `fmt_num`/date helpers) or kept UTC-absolute (§1.5)? Proposal: UTC-absolute until a second locale demands it.
2. Should `?lang=` persist via cookie for logged-out public-report viewers? Proposal: no (keep stateless); `Accept-Language` covers it.
3. Chart `aria-label` verbosity: one-line summary vs. full bucket list? Proposal: one-line summary + data-table alternative (§6.5) — full list would be unusable via screen reader.
