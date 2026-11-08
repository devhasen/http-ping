# Frontend / Design Spec — HTTP Ping

**Product:** HTTP Ping — an HTTP latency & uptime monitoring SaaS built around the
`httpping` CLI (measure HTTP request latency: min / max / avg).
**Author:** Frontend/Design lead (desk-3, Agent Office)
**Status:** SPEC ONLY — do not build pages yet. Implementation to follow.
**Source material:** Repo `devhasen/http-ping` (main). `docs/product-spec.md` and
`docs/architecture.md` had not landed when this spec was written; where the backend
contract is unknown, this spec notes the assumption and the API shape the frontend
expects (`/api/v1/...`, JSON, bearer token). If the product/architecture specs
later contradict, those specs win and this document should be revised.

**Hard constraints (apply to every page):**

- Zero build tooling: no bundler, no transpiler, no npm build step.
- No external CDN. No third-party scripts, fonts, or stylesheets. Inlined or
  locally-served assets only (`/static/...`).
- No paid services: no analytics SDKs, no SaaS error trackers, no hosted font services.
- One static HTML/CSS/JS app served by the backend; all data via `fetch`.
- Runs from `file://`-insensitive, relative-safe paths where possible; prefers
  absolute `/static/...` asset paths.

---

## 1. Site Map & Every Page

Base path: `/`. Public marketing pages at the top level; app pages under `/app/…`;
auth pages under `/auth/…`. All routes are served as static HTML by the backend
(history-mode routing with a server-side fallback to `index.html` for app routes).
One `index.html` shell per page file, each loading its own JS module — no SPA
bundle (keeps zero-build constraint trivially satisfiable).

| # | Route | Purpose | Key components | Auth |
|---|-------|---------|----------------|------|
| 1 | `/` (landing) | Explain HTTP Ping; CLI → hosted monitoring story; CTA to signup. | Hero, latency live-demo strip, feature cards, pricing teaser, footer | public |
| 2 | `/auth/signup` | Create account (email + password). | Form (email, password, confirm), validation messages, link to login | public |
| 3 | `/auth/login` | Sign in. | Form (email, password), "forgot?" link, error toast | public |
| 4 | `/auth/reset-request` | Request password reset. | Form (email), success state | public |
| 5 | `/auth/reset` | Set new password (token in query). | Form (new password, confirm), token-expired state | public |
| 6 | `/app` (dashboard) | Home of the app: monitor overview, aggregate health, quick stats. | Stat cards (monitors up/down, avg latency, incidents), monitor summary table, recent events | protected |
| 7 | `/app/monitors` | List every monitor. | Filter/sort toolbar, monitors table, "New monitor" button, empty state | protected |
| 8 | `/app/monitors/new` | Create a monitor. | Multi-step form: target URL, check interval, alert thresholds, notification channels | protected |
| 9 | `/app/monitors/:id` | Monitor detail: latency chart, uptime, raw ping history. | Latency line chart (canvas), stats row (min/max/avg/p95/p99), uptime %, recent results table, pause/resume/delete actions | protected |
| 10 | `/app/incidents` | Alerts / incidents list. | Incidents table, status filter (active/resolved), severity badges | protected |
| 11 | `/app/settings` | Account + workspace settings. | Profile form, API token display/revoke, notification prefs, danger zone | protected |
| 12 | `/app/billing` | Billing STUB (no real payments). | Plan card (free tier), usage meters, "Upgrade" stub button → toast "Billing is not enabled" | protected |
| 13 | `/app/docs` | Developer docs: API base URL, auth header example, endpoint table. | Code blocks (inline `<pre>`), endpoint table, copy-button | protected |
| 14 | `404` (fallback) | Not found. | Message + link home | public |

**Page count: 14** (9 protected app pages, 4 public auth pages, 1 landing, + 404).

Key structural components reused across pages:

- `AppShell` — sidebar nav (Dashboard, Monitors, Incidents, Settings, Billing, Docs),
  top bar (account menu, logout), main content region.
- `PageHeader` — title + primary action button.
- `StatCard` — KPI tile (label, value, delta).
- `DataTable` — sortable/filterable table with empty/loading/error states.
- `LatencyChart` — canvas line/area chart with hover crosshair + tooltip.
- `StatusBadge` / `SeverityBadge` — pill chips (up/down/degraded; info/warn/critical).
- `Toasts` — stacked notifications (see §6.5).
- `Modal` — confirm dialogs, create/edit forms, API token reveal.

### API surface the frontend assumes

```
POST /api/v1/auth/login        {email, password}            -> {token}
POST /api/v1/auth/signup       {email, password}            -> {token}
POST /api/v1/auth/logout
GET  /api/v1/monitors                                      -> Monitor[]
GET  /api/v1/monitors/:id                                  -> Monitor
POST /api/v1/monitors          {name, url, intervalSec, …} -> Monitor
PATCH /api/v1/monitors/:id
DELETE /api/v1/monitors/:id
GET  /api/v1/monitors/:id/results?from=&to=&limit=         -> PingResult[] | {points}
GET  /api/v1/incidents?status=                             -> Incident[]
GET  /api/v1/me                                              -> {email, plan, apiToken?}
PATCH /api/v1/me
```

`Monitor = {id, name, url, intervalSec, status: 'up'|'down'|'degraded'|'paused',
lastLatencyMs, avgLatencyMs, uptimePct24h, createdAt}`.
`PingResult = {ts, latencyMs|null, statusCode|null, error|null}`.

---

## 2. User Flows

### 2.1 Signup

1. Landing → **Sign up** → `/auth/signup`.
2. Enter email + password (≥ 10 chars, shown meter optional, inline validity).
3. Submit → `POST /api/v1/auth/signup`.
   - Success → store token in `sessionStorage` (key `hp.token`), redirect `/app`.
   - 409 (email taken) → inline field error + toast. 422 → inline field errors.
   - Network error → error toast, form stays populated.
4. First-run state on `/app`: empty monitors → dashboard empty state with
   **Create your first monitor** CTA.

### 2.2 Login / logout / session

1. `/auth/login` → `POST /api/v1/auth/login` → token → `/app`.
2. All `/app/**` routes guard on token presence; missing token → redirect to
   `/auth/login?next=<original-path>`.
3. 401 from any API call → clear token, toast "Your session expired. Please sign in
   again.", redirect login.
4. **Logout** (top-bar menu) → `POST /api/v1/auth/logout` → clear token → `/`.

Password reset stub: request → always shows "If an account exists…" (no account
enumeration); `/auth/reset?token=…` validates token on load; expired token shows
error state with link back to request page.

### 2.3 Main app flow (monitor lifecycle)

1. **Dashboard** → stat cards + compact monitors table + recent incidents.
2. **Monitors** → browse/filter (by status, by name search) → row click → detail.
3. **New monitor**: form (name, URL with live validation, interval select
   30s/1m/5m/10m, latency alert threshold ms, notify checkbox) → create →
   redirect to detail. URL validation client-side (`new URL()`) + server errors
   mapped per-field.
4. **Monitor detail**: range selector (1h/24h/7d) → fetch results → chart +
   min/max/avg/p95/p99 + uptime %; results table (latest 50, newest first).
   Actions: Pause/Resume toggle, Delete (confirm modal).
5. **Incidents**: filter active/resolved → row → (stub) links to monitor detail.

Auto-refresh: dashboard + detail poll every 30s while visible (`document.hidden`
pauses polling). Poll failures back off silently, show staleness indicator.

### 2.4 Settings

- Profile: display name, email (read-only), change password (current/new).
- API token: masked field, **Reveal** → modal with full token + copy; **Revoke**
  → confirm modal → new token generated.
- Notifications: email alerts toggle, digest toggle. Save → toast.
- Danger zone: delete account → type-to-confirm modal → stub (disabled, tooltip
  "Not available yet").

### 2.5 Billing stub

- `/app/billing`: current plan card ("Free — 10 monitors, 5-min checks"),
  usage meters (monitors used/limit, checks this month/limit), single **Upgrade**
  button → toast "**Billing isn't enabled yet.** You're on the free plan — no action needed."
  No payment fields, no processor. Footer note: "Billing coming soon."

---

## 3. Design System

### 3.1 Color palette

Light theme is the default and the primary design target; dark theme is a
`prefers-color-scheme` re-skin using the same semantic tokens (see §3.5).

| Token | Hex | Rationale |
|-------|-----|-----------|
| `--bg` | `#FAFAF8` | Warm off-white; less clinical than pure white, pairs with the "ping" terminal heritage. |
| `--surface` | `#FFFFFF` | Cards/tables/modals sit a step above bg. |
| `--surface-alt` | `#F1EFE9` | Subtle warm grey for hover/pressed and code blocks. |
| `--border` | `#E3E0D6` | Warm light border, visible but quiet. |
| `--text` | `#1C1B17` | Near-black warm; high contrast on bg/surface. |
| `--text-muted` | `#5C574D` | Secondary text; still ≥ 4.5:1 on bg. |
| `--accent` | `#14666B` | Deep teal — "signal/acoustic" reading of *ping*; credible for infra tooling, distinct from generic blue. Buttons, links, focus rings, chart line. |
| `--accent-strong` | `#0E4C50` | Hover/active state of accent; darker for ≥ 4.5:1 on white text pairing. |
| `--accent-soft` | `#DFEEEC` | Tinted surface for selected rows, info banners. |
| `--ok` | `#1E7A46` | Up/healthy. ≥ 4.5:1 on white. |
| `--ok-soft` | `#E2F2E7` | Badge bg. |
| `--warn` | `#9A6A00` | Degraded. Dark amber text for contrast; never rely on hue alone (see badges). |
| `--warn-soft` | `#FBF0D3` | Badge bg. |
| `--danger` | `#B3261E` | Down/error/destructive. ≥ 4.5:1 on white. |
| `--danger-soft` | `#FBE9E7` | Badge bg. |
| `--chart-line` | `#14666B` | Matches accent; area fill `--accent-soft` at low opacity, drawn as rgba in canvas. |
| `--focus-ring` | `#14666B` | 2px outline + 2px offset; see §5. |
| `--code-bg` | `#1C1B17` | Dark terminal block for code samples (matches CLI heritage of `httpping`). |
| `--code-text` | `#F4F2EA` | Light text on dark code block. |

Dark theme (`prefers-color-scheme: dark` or `data-theme="dark"`):

| Token | Hex |
|-------|-----|
| `--bg` | `#141412` |
| `--surface` | `#1C1C19` |
| `--surface-alt` | `#26261F` |
| `--border` | `#33322B` |
| `--text` | `#F2F0E8` |
| `--text-muted` | `#B8B2A4` |
| `--accent` | `#5EBEC3` |
| `--accent-strong` | `#8FD3D6` |
| `--accent-soft` | `#1E3A3C` |
| `--ok` | `#6BCB8D` |
| `--warn` | `#E3B341` |
| `--danger` | `#F2837A` |
| `--code-bg` | `#0E0D0B` |

All semantic pairings were chosen to meet WCAG AA (§5). Status colors are never
the sole indicator — every status also carries a text label/icon shape.

### 3.2 Typography

System font stack only — no webfonts (zero-CDN constraint):

```
font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, sans-serif;
mono: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
```

Scale (1.25 ratio, rem-based so user font-size prefs apply):

| Style | Size | Weight | Line-height | Use |
|-------|------|--------|-------------|-----|
| `display` | 2.25rem (36px) | 700 | 1.15 | Landing hero |
| `h1` | 1.75rem (28px) | 700 | 1.2 | Page titles |
| `h2` | 1.375rem (22px) | 600 | 1.25 | Section heads |
| `h3` | 1.125rem (18px) | 600 | 1.3 | Card titles |
| `body` | 1rem (16px) | 400 | 1.5 | Default text |
| `small` | 0.875rem (14px) | 400 | 1.45 | Table cells, captions |
| `micro` | 0.75rem (12px) | 600 | 1.35 | Badges, labels (uppercase, letter-spacing 0.04em) |
| `mono` | 0.875rem (14px) | 400 | 1.5 | URLs, numbers, code |

Latency values always render in `mono` with tabular figures (`font-variant-numeric:
tabular-nums`) so digits stop jittering.

### 3.3 Spacing & layout

- 8px base grid; spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 (px).
- App shell: 240px sidebar + fluid content (max-width 1200px, 24px gutters).
- Cards: 16px padding, 1px border, 8px radius (`--radius`), no shadows except
  modal/toast (0 8px 24px rgba(28,27,23,0.12)).
- Tables: 12px vertical cell padding, header `micro` uppercase, row divider 1px.
- Forms: 16px between fields; labels `small` semibold; inputs 40px height.

### 3.4 Components

| Component | Variants / behavior |
|-----------|---------------------|
| **Button** | `primary` (accent bg, white text), `secondary` (surface, border), `ghost` (text only), `danger` (danger bg). Sizes: sm 32px / md 40px. Focus: 2px `--focus-ring` outline offset 2px. Disabled: 50% opacity, `aria-disabled`. |
| **Input / select / textarea** | 40px, 1px border, 6px radius; focus border = accent + ring; invalid = danger border + error message (`aria-invalid`, `aria-describedby`). |
| **Checkbox / switch** | Native input (unstyled except `accent-color: var(--accent)`) — free keyboard + screen-reader support. |
| **Badges** | Pill, `micro` uppercase, colored dot + text label (dot has shape difference: ● up, ▲ degraded, ✕ down). |
| **Tables** | `<table>` semantic; sortable headers are `<button>`s with `aria-sort`; zebra off — hover tint only; horizontal scroll container on small widths. |
| **Cards** | Surface bg, border, radius; `StatCard` = label (`micro`) + value (h2 mono) + delta chip. |
| **Latency chart** | Canvas 2D (no library). Axis labels `small` mono; hover crosshair + tooltip (time, ms, status code); keyboard-accessible summary (`aria-label` on canvas + visually-hidden data table toggle). |
| **Modal** | `<div role="dialog" aria-modal="true">`, focus trap, Esc closes, restores focus to trigger; scrim rgba(0,0,0,0.4). |
| **Toasts** | Bottom-right stack, `role="status"` (info/success) / `role="alert"` (error), auto-dismiss 5s, manual close, pause on hover/focus. |
| **Empty states** | Centered icon (inline SVG) + headline + body + primary CTA. |
| **Loading states** | Skeleton blocks (pulse on `--surface-alt`) for tables/cards; button spinner (CSS) with `aria-busy` on region. |
| **Inline alert** | Banner (info/warn/danger tinted bg + icon + text) for page-level messages, e.g. session expiry, stale data. |
| **Pagination** | Simple prev/next + "Showing X–Y of Z". |
| **Tabs** (monitor detail) | Native buttons, `role="tablist"`, arrow-key navigation. |

### 3.5 Dark/light mode decision

- **Shipped: both, via semantic CSS custom properties.** All component CSS uses
  tokens only — zero hardcoded hex outside the token definitions.
- **Default: respect `prefers-color-scheme`** (zero JS). An explicit toggle in the
  top-bar menu stores `hp.theme` in `localStorage` (`light`/`dark`/`system`);
  a tiny inline script in `<head>` sets `data-theme` before paint to avoid flash.
- Rationale: infra/ops users work late and stare at charts; dark mode is expected.
  Maintaining one token set costs nothing at this scale; shipping themes that
  disagree on contrast would.

---

## 4. Responsive / Mobile Behavior (per page)

Breakpoints: `≥1024px` desktop · `768–1023px` tablet · `<768px` mobile.

| Page | Tablet | Mobile |
|------|--------|--------|
| Landing | Hero stacks to 1 col at 768 | Single column; hero CTA full-width; feature grid 1 col |
| Auth pages | Card centered, max 400px | Card full-width with 16px page padding |
| Dashboard | Stat cards 2×2 grid | Stat cards 1 col; summary table horizontally scrollable |
| Monitors list | Table keeps URL column, drops created | Table collapses: name + status + latency only (others hidden via `hidden` class at <768); row tap → detail |
| New monitor | Form max-width 560px | Full-width, single column, sticky bottom submit bar |
| Monitor detail | Chart full-width; stats row 2×2 | Stats 2-col grid; results table scrollable; action buttons wrap |
| Incidents | Same as monitors list | Same collapse pattern as monitors list |
| Settings | Two-column fields where sensible | Single column; danger zone last, full-width |
| Billing | Plan card + meters side by side | Stacked; meters full-width |
| Docs | Code blocks scroll horizontally | Same; endpoint table scrolls |

Global rules: minimum touch target 40×40px (44px preferred); sidebar → top-bar
with hamburger (off-canvas drawer) under 1024px; no horizontal page scroll —
table/code overflow is contained in scrollable wrappers with `tabindex="0"` and
visible focus rings so it stays keyboard-reachable. Charts re-render on resize
(`ResizeObserver`) and on theme change.

---

## 5. Accessibility (WCAG 2.2 AA)

### 5.1 Contrast ratios (key pairings, computed)

| Pairing | Ratio | Verdict |
|---------|-------|---------|
| `--text` #1C1B17 on `--bg` #FAFAF8 | ~15.4:1 | AAA |
| `--text-muted` #5C574D on `--bg` | ~7.0:1 | AA |
| White on `--accent` #14666B | ~6.1:1 | AA |
| White on `--accent-strong` #0E4C50 | ~8.8:1 | AA |
| `--ok` #1E7A46 on white | ~5.2:1 | AA |
| `--warn` #9A6A00 on white | ~5.0:1 | AA |
| `--danger` #B3261E on white | ~5.9:1 | AA |
| `--code-text` #F4F2EA on `--code-bg` #1C1B17 | ~14.9:1 | AAA |
| Dark: `--accent` #5EBEC3 on `--bg` #141412 | ~8.6:1 | AA |

Body text ≥ 4.5:1; large text (≥24px / 18.66px bold) ≥ 3:1; non-text UI
(borders that carry meaning, chart lines, focus indicators) ≥ 3:1.

### 5.2 Focus states

- Every interactive element: visible 2px `--focus-ring` outline, 2px offset.
  Never `outline: none` without a replacement.
- Focus is trapped inside open modal; on close, focus returns to the trigger.
- Skip link ("Skip to main content") as first focusable element on every page.
- `:focus-visible` preferred so mouse users don't get ring noise.

### 5.3 ARIA & semantics

- Landmarks: `<header>`, `<nav aria-label>`, `<main id="main">`, `<footer>`.
- Forms: real `<label for>`; errors via `aria-invalid` + `aria-describedby` pointing
  at the error text; required fields `aria-required="true"`.
- Live regions: toasts `role="status"`/`role="alert"`; chart data changes announced
  via `aria-live="polite"` summary; polling regions `aria-live="off"` with a
  manually accessible "refresh" and a visually-hidden "last updated …" text.
- Status badges: text label always present (color + shape + text, never color only).
- Tables: `<th scope>`, `aria-sort` on sorted column, caption or `aria-label`.
- Canvas chart: `role="img"` + `aria-label` describing trend, plus a toggleable
  text/table alternative ("View data as table").

### 5.4 Keyboard nav

- Full operability with keyboard only: all actions reachable, modals/traps/drawers
  Esc-close, tables rows selectable via Enter on the row link (rows themselves
  aren't focusable — links inside are).
- Tab order follows visual order; no positive `tabindex`.
- Charts: data table alternative is fully keyboard operable; chart canvas itself
  does not need to be focusable when the alternative exists.
- Arrow keys in tab lists and radio-like segmented controls (range selector).

---

## 6. Tech Approach

### 6.1 Static serving, no build step

- Backend serves files from `/static/` (or `./public/`): `index.html` per page,
  `css/app.css`, `js/*.js` as ES modules (`<script type="module">`). No bundling —
  each page loads its own small module graph (4–8 files) that imports shared
  modules by relative path. Module imports make shared code safe without a bundler.
- Asset references are relative to the page (`../static/...` from `/app/`, etc.)
  or root-absolute (`/static/...`). No `?v=` hashing pipeline; cache-busting via
  immutable headers only if the backend supports it. No sourcemaps, no minification.
- Icons: inline SVG sprite defined once per page (`<symbol>` defs in each HTML file
  — acceptable duplication at this scale vs. a build-time sprite step).
- Fonts: system stacks only (§3.2).

### 6.2 File layout (target)

```
/static/
  css/tokens.css      /* custom properties: light + dark (§3.1) */
  css/components.css  /* buttons, forms, badges, tables, modal, toast … */
  css/layout.css      /* shell, page layouts, responsive rules */
  js/api.js           /* fetch client (§6.3) */
  js/store.js         /* tiny state store (§6.4) */
  js/toast.js         /* toast system (§6.5) */
  js/modal.js         /* focus-trapped modal */
  js/chart.js         /* canvas latency chart */
  js/shell.js         /* sidebar, theme toggle, route guard */
  js/pages/*.js       /* one module per page route */
```

### 6.3 Vanilla JS fetch client (`api.js`)

- `api(path, {method, body, auth=true})` wraps `fetch`, sets
  `Content-Type: application/json`, attaches `Authorization: Bearer <token>`.
- Typed error: `ApiError {status, code, message, fields?}` — callers catch and
  map `fields` onto form inputs, `status` onto toasts (§8).
- Timeout via `AbortController` (15s); retry once on 5xx/network for GETs only.
- 401 → dispatch `auth:expired` event → global handler clears token, toasts,
  redirects to login. Never retry a 401.
- Base URL from `window.HP_CONFIG.apiBase` (inline `<script>` in each HTML head,
  defaults to same origin `/api/v1`).

### 6.4 State management (`store.js`)

- Minimal pub/sub store: `store.get(key)`, `store.set(key, value)` (notifies
  subscribers), `store.subscribe(key, fn)`. No framework, no global mutable
  spaghetti: page modules own their data, store holds only cross-cutting state —
  `session` (token, user), `theme`, `toasts`, `me`.
- Server data is always re-fetched per page load (no cache invalidation problem).
  Polling writes into page-local state and re-renders.
- Render strategy: template-string → `innerHTML` for list regions, then explicit
  event delegation (`data-action` attributes). No virtual DOM. Rows keyed by `id`
  to preserve DOM nodes when polling updates only changed rows.
- Escaping: every server-supplied string interpolated with a `esc()` helper
  (`textContent`-based) — monitoring URLs/monitors names are user-controlled XSS
  surface; treat all API strings as untrusted.

### 6.5 Error toast system

- `toast.show({kind: 'success'|'error'|'info', title, body?, action?})` renders
  into a single `#toasts` container (`aria-live` managed by kind).
- One toast per unique error code at a time (dedupe by `code` within 10s) — polling
  failures must not stack.
- Errors never fire-and-forget into console only: every API failure surfaces as
  toast *or* inline field error *or* page-level empty/error state (§8).
- Toast action buttons supported ("Retry", "View monitor") and focusable.

---

## 7. Wireframes (per page)

Conventions: `[brackets]` = dynamic data; `▶` primary button; `…` collapses detail.
Widths in px for desktop (≥1024).

### 7.1 `/` — Landing (public)

```
┌────────────────────────────────────────────────────────┐
│ [logo HTTP Ping]        Features  Docs  Pricing  [Sign in] [▶ Sign up] │
├────────────────────────────────────────────────────────┤
│  Know exactly how fast your HTTP endpoints are.        │
│  Hosted latency monitoring for every URL you care      │
│  about — min, max, avg, and uptime, checked every      │
│  minute. Built on the httpping CLI.                    │
│  [▶ Start monitoring — free]   [View docs]             │
│                                                        │
│  ┌─ live demo strip ────────────────────────────────┐  │
│  │ https://api.example.com   84ms  ▲ chart (canvas) │  │
│  └──────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────┤
│ [card: Min/Max/Avg] [card: Uptime %] [card: Alerts]    │
│ [card: CLI parity]    [card: No agents] [card: API-first]│
├────────────────────────────────────────────────────────┤
│  "We found the slow endpoint in 5 minutes." — beta user│
├────────────────────────────────────────────────────────┤
│  Free: 10 monitors · Pro (soon): unlimited, 30s checks  │
│  [▶ Create free account]                               │
├────────────────────────────────────────────────────────┤
│  footer: © 2026 HTTP Ping · Docs · Status · GitHub     │
└────────────────────────────────────────────────────────┘
```

### 7.2 `/auth/signup` & `/auth/login` (card pattern)

```
┌────────────────── 400px centered ──────────────────┐
│  HTTP Ping — Create your account                   │
│  ┌────────────────────────────────────────────┐    │
│  │ Email        [________________________]    │    │
│  │ Password     [________________________]    │    │
│  │ Confirm      [________________________]    │    │
│  │              [▶ Create account]          │    │
│  │ Already have an account? Sign in          │    │
│  └────────────────────────────────────────────┘    │
│  error state: inline red text under field + toast  │
└────────────────────────────────────────────────────┘
```

### 7.3 `/app` — Dashboard

```
┌────────┬────────────────────────────────────────────────────────┐
│ side   │  Dashboard                     [▶ New monitor]        │
│ bar    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│ 240px  │  │Monitors│ │Up now  │ │Avg lat │ │Incidents│         │
│        │  │  24    │ │  22    │ │ 132ms  │ │   2     │         │
│        │  └────────┘ └────────┘ └────────┘ └────────┘          │
│        │  Monitors (compact)               View all →           │
│        │  ┌───────────────────────────────────────────────┐    │
│        │  │ name      url          status   last   24h%   │    │
│        │  │ API      api.ex…      ● Up     84ms  99.98% │    │
│        │  │ Site     www.ex…      ▲ Degraded 412ms 97%  │    │
│        │  └───────────────────────────────────────────────┘    │
│        │  Recent incidents                                      │
│        │  ▲ api.example.com — latency > 500ms · 12m ago        │
└────────┴────────────────────────────────────────────────────────┘
```

### 7.4 `/app/monitors` — List

```
┌─────────────────────────────────────────────────────────────────┐
│  Monitors                    [search______] [status ▾] [▶ New]   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Name ▲ │ URL             │ Status    │ Last   │ Avg   │ 24h% │  │
│  │ API  ▼ │ https://api…    │ ● Up      │ 84ms   │ 96ms  │ 99.9%│  │
│  │ Site   │ https://www…    │ ✕ Down    │ —      │ —     │ 91.2%│  │
│  │ Cron   │ https://cron…   │ ⏸ Paused  │ 12ms   │ 15ms  │ 100% │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Showing 1–25 of 42        [‹ Prev] [Next ›]                    │
│  empty state: "No monitors yet." [▶ Create your first monitor]  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.5 `/app/monitors/new` — Create form

```
┌─────────────────────────────────────────────────────────────────┐
│  New monitor                        [Cancel] [▶ Create monitor] │
│  Name      [________________________]  (suggested from URL)      │
│  Target URL[https://___________________]  ✓ valid, reachable   │
│  Check every [5 minutes ▾]                                     │
│  Alert if latency > [500____] ms                               │
│  Alert if status code ≥ [500]                                  │
│  Notify me by [✓] Email  [ ] Webhook (Pro)                     │
│  POST /api/v1/monitors → 201 → redirect to /app/monitors/:id   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.6 `/app/monitors/:id` — Detail

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Monitors   API — api.example.com            [⏸ Pause] [🗑]   │
│  ● Up · checked 2m ago · every 5 min         Updated 12s ago ↻  │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │Last    │ │Avg     │ │Min     │ │Max     │ │Uptime  │        │
│  │84ms    │ │102ms   │ │41ms    │ │890ms   │ │99.98%  │        │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘        │
│  Latency — [1h|24h|7d|30d]        [View data as table]          │
│  ┌─ canvas chart: line + area, threshold line at 500ms -------┐ │
│  │        ▲ spike (hover: 14:32 · 890ms · 200)               │ │
│  └────────────────────────────────────────────────────────────┘ │
│  Recent results (latest 50)                                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Time (UTC) │ Latency │ Status │ Error                     │  │
│  │ 14:32:05   │ 890ms   │ 200    │ —                         │  │
│  │ 14:27:05   │ 96ms    │ 200    │ —                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.7 `/app/incidents`

```
┌─────────────────────────────────────────────────────────────────┐
│  Incidents    [All|Active|Resolved ▾ segmented]                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Started (UTC) │ Monitor │ Severity │ Reason        │Status  │  │
│  │ 14:10         │ API     │ ▲ Warn   │ p95 > 500ms   │Active  │  │
│  │ 09:02         │ Site    │ ✕ Crit   │ 3 failed checks│Resolved│ │
│  └───────────────────────────────────────────────────────────┘  │
│  Row → monitor detail. Empty: "No incidents. Nicely quiet."    │
└─────────────────────────────────────────────────────────────────┘
```

### 7.8 `/app/settings`

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings                                                       │
│  Profile              [Display name ______] [Email (locked)]    │
│  Password             [Current ___] [New ___] [▶ Change]        │
│  API token            [hp_••••••••••••] [Reveal] [Revoke]       │
│  Notifications        [✓] Email alerts  [ ] Weekly digest       │
│  Danger zone          Delete account… (disabled, stub)         │
│                       [▶ Save settings]                         │
└─────────────────────────────────────────────────────────────────┘
```

### 7.9 `/app/billing` (stub)

```
┌─────────────────────────────────────────────────────────────────┐
│  Billing                                                        │
│  ┌─ Current plan ──────────────┐ ┌─ Usage ──────────────────┐  │
│  │ Free · $0/mo                │ │ Monitors  7 / 10  [███░░]│  │
│  │ [▶ Upgrade to Pro] (toast)  │ │ Checks/mo 41.2k / 100k   │  │
│  └─────────────────────────────┘ └──────────────────────────┘  │
│  Billing is not enabled yet. Everything is on the free plan.    │
└─────────────────────────────────────────────────────────────────┘
```

### 7.10 `/app/docs`

```
┌─────────────────────────────────────────────────────────────────┐
│  API docs                                                       │
│  Base URL: https://…/api/v1    [Copy]                           │
│  Auth: header  Authorization: Bearer <token>                    │
│  ┌─ example ────────────────────────────────────────────────┐  │
│  │ $ curl -H "Authorization: Bearer $HP_TOKEN" \             │  │
│  │     https://…/api/v1/monitors                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│  Endpoints table: Method │ Path │ Description                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Copy / UX Tone + State Copy

### 8.1 Tone

- **Plain, technical, unhurried.** Write like good CLI help text: short sentences,
  real nouns, exact numbers. No marketing puffery inside the app; landing may be
  warmer but stays factual ("Know exactly how fast…", never "supercharge").
- **Numbers first.** Latency in whole ms, percentages to 2 decimals, times in UTC
  on data surfaces (local time only where unambiguous, labeled).
- **Second person, active voice.** "Create your first monitor." not "A monitor
  can be created."
- **Errors name the thing and the next step.** Never "Something went wrong."
- No exclamation marks in-app. One on the landing hero max.

### 8.2 State copy (canonical strings)

**Empty states**

| Where | Copy |
|-------|------|
| Dashboard, no monitors | "No monitors yet. Add a URL and we'll check it every few minutes." + [Create your first monitor] |
| Monitors, filtered to none | "No monitors match this filter." + [Clear filters] |
| Incidents, none | "No incidents. Nicely quiet." |
| Monitor detail, no results yet | "No checks yet — the first check runs within a minute." |
| Results table (range empty) | "No results in this range. Try a wider window." |

**Loading states**

- Tables/cards: skeleton rows (3–5), `aria-busy="true"`, off-screen live text
  "Loading…". No spinners blocking whole page except first paint of auth pages.
- Button submit: label swaps to "Saving…" and disables; `aria-busy` on the form.

**Error / toast copy**

| Situation | Title | Body |
|-----------|-------|------|
| Network down | "Can't reach HTTP Ping" | "Check your connection and try again." + [Retry] |
| 401 / expired | "Your session expired" | "Please sign in again." |
| 403 | "Not allowed" | "This action needs a different plan or role." |
| 404 monitor | "Monitor not found" | "It may have been deleted." + [Back to monitors] |
| 409 email taken | field error | "An account with this email already exists. Try signing in." |
| 422 validation | field errors | (per-field, no toast) |
| 429 rate limit | "Too many requests" | "Wait a minute and try again." |
| Create monitor fail | "Couldn't create monitor" | server message or "Check the URL and try again." |
| Delete monitor success | "Monitor deleted" | (name) removed. |
| Token revoked | "API token revoked" | "Create a new one in Settings." |
| Billing upgrade click | "Billing isn't enabled yet" | "You're on the free plan — no action needed." |
| Poll stale (>2 min) | inline banner | "Data may be stale — last updated 3m ago." + [Retry] |

**Success toasts**

- "Monitor created — first check in under a minute."
- "Settings saved."
- "Password changed. Sign in with your new password elsewhere."

### 8.3 Microcopy rules

- Buttons use verb + object: "Create monitor", "Delete monitor", "Revoke token".
- Destructive actions: button labeled "Delete monitor", confirm modal title
  "Delete this monitor?", body "Checks for {name} will stop and history will be
  removed. This can't be undone.", actions [Cancel] [Delete monitor].
- Time strings: relative ("2m ago") with absolute UTC in `title` attribute.
- Never expose raw stack traces or HTTP internals to users; log them to console
  (`console.error`) for developers.

---

## Appendix — Open Questions for Product/Architecture Specs

1. Confirm the `/api/v1` contract in §1 (auth method, monitor/result shapes) —
   frontend selectors/fields depend on it.
2. Is there a plan gate on monitors/checks (free tier limits in §7.9 are placeholders)?
3. Notification channels at launch: email only?
4. Does the backend serve static files (and from what root)? This spec assumes
   `/static/...` + per-page HTML with history fallback.

*End of spec. Next step: backend serves `/static/`; frontend builds pages per
this document in route order: auth → shell → monitors list → detail → incidents →
settings → billing/docs stubs.*
