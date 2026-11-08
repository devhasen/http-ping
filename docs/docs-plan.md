# Documentation Plan — http-ping

> **Owner:** Docs/Technical Writing (desk-9) — lead · Support (review) · Engineering (review)
> **Status:** SPEC ONLY (this plan). No user-facing docs are written yet.
> **Product:** `http-ping` — CLI that measures HTTP request latency (`httpping <url> [count]`, TypeScript / Node, bin `dist/index.js`).
> **Constraints:** Docs ship as Markdown in-repo. No paid docs SaaS (no ReadMe, GitBook, Notion, HelpDocs, etc.). Rendering is GitHub Markdown + npm/GitHub Pages-free static build only if ever needed.

Docs live under `docs/` in the `main` branch alongside code. Every doc below maps to a file path that will be created in a later PR — this plan authorizes the map, structure, and standards, not the prose.

---

## 1. Full documentation map

| # | Doc | Path | Audience (primary / secondary) | Owner (team) | Priority |
|---|-----|------|-------------------------------|--------------|----------|
| 1 | README (entry point) | `README.md` | First-time evaluators / all | Docs/Tech Writing (lead), Eng (verify) | P0 — exists, needs expansion |
| 2 | User Guide | `docs/user-guide.md` | CLI end users (devs, SREs, support) | Docs/Tech Writing | P0 |
| 3 | Admin Guide | `docs/admin-guide.md` | Ops / platform / IT admins deploying in ci/corp | Docs/Tech Writing + Platform/DevOps | P1 |
| 4 | Developer Guide | `docs/developer-guide.md` | Contributors / integrators embedding the library | Docs/Tech Writing + Core Engineering | P0 |
| 5 | API Reference | `docs/api-reference.md` | Programmatic users (library) + CLI flag reference | Docs/Tech Writing + Core Engineering | P0 |
| 6 | FAQ | `docs/faq.md` | All users with a specific question | Docs/Tech Writing + Support | P1 |
| 7 | Changelog | `CHANGELOG.md` | All users, upgraders | Docs/Tech Writing (format), Release Eng (entries) | P0 |
| 8 | Glossary (reference) | `docs/glossary.md` | All — linked from every other doc | Docs/Tech Writing | P1 |
| 9 | Migration / Upgrade notes | `CHANGELOG.md` § Unreleased + `docs/upgrading.md` (when breaking) | Upgraders | Docs/Tech Writing + Release Eng | P2 (create on first breaking change) |

**Doc count: 9 planned docs** (8 in the initial ship set, #9 on-demand). README + CHANGELOG sit at repo root; the rest under `docs/`.

---

## 2. Per-doc detail

### 2.1 README (`README.md`)
- **Audience:** Anyone deciding whether to use http-ping in the first 30 seconds.
- **Outline:** What it does (one sentence) → Install (`npm i -g http-ping` / `npx`) → 30-second quickstart (`httpping https://example.com 10` + sample output) → Options table → Output explained → Links to User Guide / API Reference / FAQ → License.
- **Estimated size:** ~80–120 lines (~3 KB).
- **Owner:** Docs/Tech Writing (lead), Core Eng (accuracy).

### 2.2 User Guide (`docs/user-guide.md`)
- **Audience:** End users running the CLI day-to-day (devs, QA, SREs). Secondary: Support answering tickets.
- **Outline:**
  1. What http-ping measures (and doesn't — latency, not throughput/content)
  2. Installing & updating
  3. Quickstart (first run — see §5)
  4. Measuring a URL: count, timeouts, output reading
  5. Interpreting results: min / max / avg, per-request lines, error lines
  6. Common scenarios: smoke-test an endpoint, compare before/after a deploy, CI sanity check
  7. Troubleshooting (link to FAQ)
- **Estimated size:** ~250–350 lines (~10–15 KB).
- **Owner:** Docs/Tech Writing.

### 2.3 Admin Guide (`docs/admin-guide.md`)
- **Audience:** Platform/DevOps/SRE and enterprise IT who roll http-ping out fleet-wide, in CI, or behind proxies. (Even though http-ping is a standalone CLI, "admin" = the person responsible for where/how it runs.)
- **Outline:**
  1. Deployment models: global npm, npx/ephemeral, vendored tarball, CI runner
  2. Runtime requirements: Node ≥ 20, network egress, proxy env vars, DNS
  3. CI integration (GitHub Actions example step, exit-code contract)
  4. Security: no secrets stored, URL handling, allowed hosts/allowlist patterns via wrapper scripts
  5. Upgrades & rollback (pin version, verify checksum)
  6. Support & escalation (what logs to collect before filing a bug)
- **Estimated size:** ~200–280 lines (~8–12 KB).
- **Owner:** Docs/Tech Writing (lead), Platform/DevOps (review).

### 2.4 Developer Guide (`docs/developer-guide.md`)
- **Audience:** Contributors and anyone importing http-ping as a library or forking it.
- **Outline:**
  1. Repo layout (`src/`, `dist/`, `docs/`, build `tsc` → `dist/index.js`)
  2. Building & running locally (`npm install`, `npm run build`, `npm start`)
  3. Architecture: CLI arg parsing → sequential `fetch` loop → per-request timing → summary stats (include the current 22-line `src/index.ts` flow as a diagram-in-words)
  4. How a latency sample is taken (performance.now vs Date.now — current impl uses `Date.now()`; note the limitation)
  5. Contribution workflow: branch, PR, docs requirement (any behavior change lands with doc update)
  6. Testing & releasing (manual smoke + `tsc` typecheck today; note gap — no test suite yet)
  7. Extending: adding CLI flags, output formats (JSON), error taxonomy
- **Estimated size:** ~300–400 lines (~12–16 KB).
- **Owner:** Docs/Tech Writing + Core Engineering.

### 2.5 API Reference (`docs/api-reference.md`)
- **Audience:** Programmatic users and script authors. Covers both the CLI surface (flags/exit codes) and the library surface (once exported).
- **Outline:** See §3 for the mandatory format. Sections: CLI invocation, Arguments, Exit codes, Output schema, Library API (future `ping(url, opts)`), Error codes, Versioning.
- **Estimated size:** ~200–300 lines (~8–12 KB), grows with the library API.
- **Owner:** Docs/Tech Writing (lead), Core Eng (signatures).

### 2.6 FAQ (`docs/faq.md`)
- **Audience:** All users hitting a specific problem.
- **Outline:** Grouped Q&As — Installation, Usage, Output, Errors, Performance/accuracy, CI, Security. Each answer ≤ 5 lines, links to the doc that goes deeper. Seeded questions in §8 of this plan.
- **Estimated size:** ~150–220 lines (~6–9 KB).
- **Owner:** Docs/Tech Writing + Support (source of real questions).

### 2.7 Changelog (`CHANGELOG.md`)
- **Audience:** Upgraders and evaluators.
- **Format:** Keep a Changelog (keepachangelog.com) + Semantic Versioning. See §2.7.1.
- **Estimated size:** Template ~40 lines; grows per release. Entry per release ~10–30 lines.
- **Owner:** Docs/Tech Writing (format), Release Eng (entries per PR).

**Changelog format:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [1.0.0] - 2026-01-01
### Added
- Initial release: `httpping <url> [count]` latency measurement.
```

### 2.8 Glossary (`docs/glossary.md`)
- **Audience:** All — linked inline from every other doc.
- **Outline:** Alphabetical term → one-sentence definition → "see also". Terms in §8.
- **Estimated size:** ~60–100 lines (~3–4 KB).
- **Owner:** Docs/Tech Writing.

### 2.9 Upgrading (`docs/upgrading.md`, on-demand)
- Created only when a breaking change ships. Audience: upgraders. Outline: what breaks → old → new → rollback. Owner: Docs/Tech Writing + Release Eng.

---

## 3. API reference format

Every endpoint / command / function entry follows this fixed structure. No free-form API prose.

**Rules:**
1. One entry per command/function. Heading = signature.
2. **OpenAPI-style annotation block** (as a fenced `yaml` block) directly under the heading — this is the single source of truth for parameter types, required/optional, defaults.
3. `curl`/shell example (CLI) or `ts` example (library).
4. Response JSON with a field table (name, type, description).
5. Error table (code/message → cause → fix).
6. "See also" links to User Guide / FAQ.

**Template:**

````markdown
### `httpping <url> [count]`

Measure HTTP request latency for a URL.

```yaml
# OpenAPI-style annotation
command: httpping
parameters:
  - name: url
    in: argument
    required: true
    type: string
    format: uri
    description: Target URL (http/https).
  - name: count
    in: argument
    required: false
    type: integer
    default: 5
    minimum: 1
    description: Number of sequential requests.
responses:
  "200":
    description: Completed measurement; summary on stdout.
  "1":   # exit code
    description: Usage error or unreachable target.
```

#### Example

```bash
httpping https://example.com 10
```

```
1 12ms
2 15ms
...
10 11ms
min 9 max 18 avg 13
```

#### Output fields

| Field | Type | Description |
|-------|------|-------------|
| per-request line | `"<n> <ms>ms"` | Latency of request *n*, integer ms |
| `min`/`max`/`avg` | integer (ms) | Summary over successful requests only |

#### Errors

| Exit code | Message | Cause | Fix |
|-----------|---------|-------|-----|
| 1 | `usage: httpping <url> [count]` | Missing URL argument | Pass a URL: `httpping https://example.com` |
| — | `<n> error` | Request failed (DNS, refused, timeout) | Check connectivity; see FAQ |

#### See also
- User Guide § Measuring a URL · FAQ "Why do I see `error`?"
````

**Example curl/JSON (for the future HTTP-service form, if http-ping ever grows one):**

```bash
curl -s http://localhost:3000/ping?url=https://example.com\&count=10
```

```json
{
  "url": "https://example.com",
  "count": 10,
  "samples": [12, 15, 11],
  "min": 11,
  "max": 15,
  "avg": 13,
  "unit": "ms"
}
```

> Note: today http-ping is CLI-only. The `curl`/JSON block above is the *format precedent* for a future service mode; do not document a server that doesn't exist as if it shipped. The CLI annotation is the normative reference for v1.

---

## 4. Error message & UX copy catalog

Every user-facing string category, with the tone and the exact current string. **Tone rules:** plain, lowercase-friendly, no blame, action-oriented, no exclamation marks, no emoji, no jargon without a glossary link.

| # | Category | Current string (verbatim) | Location | Tone / rule | Gap / action |
|---|----------|---------------------------|----------|-------------|--------------|
| 1 | Usage / help | `usage: httpping <url> [count]` | `src/index.ts:3` | Lowercase, terse, mirrors the command | Add `--help` printing full usage (cmd, args, examples, exit codes) — see User Guide |
| 2 | Per-request success | `<n> <ms>ms` e.g. `1 12ms` | `src/index.ts:15` | Bare numbers, no decoration | Keep stable — scripts may parse it; document as a format contract |
| 3 | Per-request failure | `<n> error` | `src/index.ts:16` | Lowercase, no errno detail | Too vague — needs the error reason (e.g. `1 error: ECONNREFUSED`) — file as product issue; catalog the target string now |
| 4 | Summary | `min <n> max <n> avg <n>` | `src/index.ts:20` | Lowercase labels, integer ms | Document that failures are excluded from the summary and that no summary prints when all fail |
| 5 | Empty/quiet case | *(nothing printed)* when all requests fail | `src/index.ts:18` | — | Add explicit line, e.g. `no successful requests` + non-zero exit code |
| 6 | No-argument exit | exit code `1` with usage on stdout | `src/index.ts:3` | — | Usage should go to **stderr**; exit code stays `1`. Document the contract |
| 7 | Invalid count | *(silently defaults to 5)* | `src/index.ts:2` | — | Warn on `NaN`/out-of-range: `warning: invalid count, using 5` |
| 8 | Invalid URL | *(uncaught throw → stack trace)* | `src/index.ts` (fetch) | — | Catch and print `error: invalid URL` + usage; exit `1` |
| 9 | Network errors | *(caught → `error` only)* | `src/index.ts:16` | — | Map to: DNS / refused / timeout / TLS — one human line each (see FAQ) |
| 10 | Future: help / version | `--help`, `--version` | — | Full sentence case, aligned columns | Spec the exact output in API Reference before implementing |
| 11 | Future: JSON output | `--json` mode | — | Machine format, schema in §3 | Not shipped — placeholder only |

**Copy principles (apply to all rows):**
- Say what happened, then what to do. One line per error.
- Never print a raw stack trace to users.
- Keep machine-parseable lines (rows 2–4) byte-stable; evolution goes through a flag (`--json`), never by silently changing the format.

---

## 5. Onboarding tutorial script (first-run flow)

**Goal:** a new user goes from `npm i -g` to interpreting their first measurement in under 2 minutes. **Steps: 8.**

| Step | Action | Exact command / copy | Expected result | Time |
|------|--------|----------------------|-----------------|------|
| 1 | Install | `npm i -g http-ping` (or `npx http-ping …` with no install) | `httpping` on `$PATH` | ~20s |
| 2 | Verify | `httpping --help` | Usage + examples print; exit `0` | ~5s |
| 3 | First measurement | `httpping https://example.com` (default count 5) | 5 lines `1 12ms`… then `min … max … avg …` | ~10s |
| 4 | Read the output | (no command) — walk through: each line = one request's latency; summary = min/max/avg over successes | User can say what `avg 13` means | ~20s |
| 5 | Choose a count | `httpping https://example.com 10` | 10 sample lines + summary | ~10s |
| 6 | Try a failure on purpose | `httpping http://localhost:9 3` (nothing listening) | `error` lines; learn that failures don't enter the average | ~10s |
| 7 | Measure *their* endpoint | `httpping https://<their-service> 10` | Real numbers for their URL | ~15s |
| 8 | Next steps | Print the three links: User Guide (scenarios), API Reference (flags/exit codes), FAQ (errors) | User knows where to go next | ~5s |

**Success criterion:** after step 8, the user can answer: "What did http-ping measure, and what does avg mean?" If not, the tutorial failed — fix the docs, not the user.

---

## 6. Docs style guide

- **Voice:** Second person, present tense, active voice ("Run…", "You get…"). Short sentences. One idea per sentence.
- **Tone:** Friendly, precise, no marketing adjectives ("blazing-fast" is banned; say the number).
- **Formatting:** GitHub Markdown only. ATX headings (`#`/`##`/`###`), no heading skipped levels. One H1 per file. Lists: `-` for bullets, `1.` for ordered steps. Line length ≤ 100 chars (soft).
- **Code examples:** Always fenced with a language tag (`bash`, `json`, `yaml`, `ts`, `text`). Every example must be runnable as-is (real URLs, real flags). Show expected output in a separate `text` block right after. Pin versions in examples (`http-ping@1.0.0`).
- **Links:** Relative paths inside the repo (`./user-guide.md`), absolute URLs only for external specs. Link every term to the Glossary on first use.
- **Numbers:** Integer milliseconds, space before unit (`12 ms` in prose, `12ms` in machine output — never mix within one doc).
- **Accessibility:** Meaning never carried by color alone; every table has a header row; alt text for any image.
- **Do / Don't:**
  - Do: document current behavior; mark planned behavior "planned (not shipped)".
  - Don't: invent flags, endpoints, or exit codes. Don't copy stack traces into user docs.
- **Review checklist (every doc PR):** headings outline clean · every example re-run · every link resolves · glossary terms defined · changelog entry added if behavior changed.

---

## 7. Docs-as-code pipeline

| Concern | Decision |
|---------|----------|
| **Where docs live** | In-repo: `docs/` + root `README.md` + `CHANGELOG.md`, same repo/branch as code (`main`). No separate docs repo, no paid SaaS. |
| **Source of truth** | Markdown files on `main` are the canonical docs. GitHub renders them; the npm package ships README + LICENSE for the registry page. |
| **How they ship with the app** | (a) GitHub repo = the site. (b) npm: `README.md` is included by default and becomes the package page. (c) No build step required to read docs. If a static site is ever wanted, generate it from these same files (e.g. VitePress/Nextra on a free tier) — never fork the content. |
| **Versioning** | Docs version with the app: the `main`-branch docs describe the `main`-branch code. At each release tag, docs are frozen by the tag itself (git history is the version archive). No `docs/v1/` folders until the first breaking change, then: keep `main` = latest, cut `docs-<major>` branches from release tags. |
| **Authoring workflow** | Docs change in the same PR as the behavior change (no "docs later"), OR a docs-only PR referencing the product spec/PR. Every PR touching `src/` must also touch `docs/` or `CHANGELOG.md` — enforced by reviewer checklist, not tooling. |
| **CI (lightweight, free)** | Later (P1): a GitHub Action that (1) checks Markdown links resolve, (2) runs every fenced `bash` example in CI against a local server, (3) fails if a `src/` change lacks a `docs/`/`CHANGELOG.md` change. No paid services. |
| **Release checklist** | Bump `package.json` → write `CHANGELOG.md` entry → update README "current version" → tag `vX.Y.Z` → publish to npm. |
| **Ownership** | Docs/Tech Writing owns structure/style; Core Eng owns technical accuracy; Support owns FAQ sourcing. Any header change to this plan needs Docs lead sign-off. |

---

## 8. Glossary of domain terms

| Term | Definition | See also |
|------|-----------|----------|
| **Latency** | Time for one request to round-trip: send → server processes → response fully received, in ms. | Sample, RTT |
| **Sample** | One timed request. A run of N requests produces N samples. | Count, Latency |
| **Count** | Number of sequential requests in one run (CLI arg, default 5). | Sample |
| **min / max / avg** | Smallest / largest / mean latency across the *successful* samples of a run, integer ms. | Sample |
| **RTT (round-trip time)** | Latency measured from the client, including network transit both ways. | Latency |
| **Throughput** | Requests (or bytes) per second. http-ping does **not** measure this. | Latency |
| **Endpoint / URL** | The `http(s)://host/path` being measured. | Target |
| **Target** | The server/endpoint under test. | Endpoint |
| **HTTP status** | The server's reply code (e.g. 200, 404). http-ping records success/failure of the round-trip; status-aware reporting is a future extension. | Error |
| **Exit code** | Process status: `0` = measured OK, `1` = usage/validation error. Documented in API Reference. | Error |
| **Warm-up** | The first request(s), often slower due to DNS/TLS/connection setup. http-ping does not exclude them — a documented limitation. | Sample, Latency |
| **DNS resolution** | Turning the hostname into an IP before connecting; part of first-request latency. | Latency |
| **Timeout** | A request abandoned after a set duration; counts as a failed sample. | Error, Sample |
| **Smoke test** | A quick check that an endpoint responds at all — the canonical http-ping use case. | User Guide |
| **CI check** | Running http-ping in a build pipeline to gate on endpoint health/latency. | Admin Guide |

**Seeded FAQ questions** (to be answered in `docs/faq.md`, sourced from §4's gaps):
1. Why do I see `error` for some requests?
2. Why is no summary printed?
3. What does `avg` include — do failures count?
4. Why is my first request slower than the rest? (warm-up)
5. `httpping` says command not found — how do I fix my PATH?
6. Can I run http-ping in CI? What exit code do I gate on?

---

## Appendix — Phased rollout (for the implementing PRs)

| Phase | Deliverable | Est. effort |
|-------|-------------|-------------|
| P0 | README expansion + User Guide + API Reference + Changelog template + Glossary | ~1–2 days writing/review |
| P1 | Admin Guide + FAQ + link-check/CI action | ~1 day |
| P2 | Upgrading doc (on first breaking change) + `--help`/`--version`/per-request error reasons (product issues filed from §4) | as needed |

*This file (`docs/docs-plan.md`) is the spec. It authorizes the map and standards above; it is not itself user-facing documentation.*
