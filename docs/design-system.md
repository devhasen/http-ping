# LatencyLedger Design System

## Principles
1. **Evidence over decoration** — numbers first, charts second, chrome last.
2. **Quiet until it matters** — green/neutral normally; red only on regression/down.
3. **Works offline** — no CDN, no web fonts required; system font stack.

## Color
| Token | Value | Use |
|---|---|---|
| `--bg` | `#0f1115` | app background (dark default, light theme mirrors) |
| `--panel` | `#171b22` | cards/panels |
| `--text` | `#e6e9ee` | primary text |
| `--muted` | `#9aa3af` | secondary text, axes |
| `--accent` | `#4f8cff` | links, primary buttons, p50 line |
| `--ok` | `#34c07c` | pass / healthy |
| `--warn` | `#e8b23a` | near-budget |
| `--bad` | `#e5534b` | regression / down / fail |
| `--p95` | `#b083f0` | p95 line (distinct from p50) |

Contrast: text on bg ≥ 7:1; status colors always paired with icon + text label (never color alone).

## Typography
System stack: `-apple-system, "Segoe UI", Roboto, sans-serif`; monospace: `ui-monospace, "SF Mono", Menlo, monospace` for ms values/hashes. Scale: 12/14/16/20/28.

## Components
- **Stat tile:** label + big mono value + delta chip (▲/▼ with % and text).
- **Check row:** name, url (truncated, mono), last p95, mini sparkline, status dot.
- **Chart:** canvas, p50 (accent) + p95 (purple) lines, baseline dashed, SHA markers as ticks; tooltip with time + values.
- **Alert banner:** red left border, plain-language summary ("p95 rose 212ms → 389ms"), link to chart.

## Layout
Max width 1080px, single column on mobile; header (logo, nav, account), main (dashboard grid → detail), footer (status + docs links). Touch targets ≥40px.

## Motion & a11y
Reduced-motion respected (`prefers-reduced-motion`); charts have `role="img"` + text summary; all actions keyboard reachable; focus visible outline 2px accent.
