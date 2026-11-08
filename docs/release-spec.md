# LatencyLedger — Release / Tech-Lead Specification

**Product:** LatencyLedger (continuous API latency regression tracking with CI gates)
**Owner:** Release Manager / Tech Lead (desk-16)
**Status:** Spec — for implementation by backend / frontend / QA / ops teams
**Constraints:** GitHub-based repo; free CI only (GitHub Actions free tier); Python 3.11+ stdlib-only app; vanilla JS frontend with no build step.

This spec governs *how LatencyLedger ships*. Product behaviour is defined in
`docs/product-spec.md`; system shape in `docs/architecture.md`. Where this spec
and the product spec disagree on scope, the product spec wins; where they
disagree on process, this spec wins.

---

## 1. Release process — branching, PR policy, review

### 1.1 Decision: trunk-based development (TBD), not GitFlow

**Chosen: trunk-based development with short-lived feature branches.**

| Criterion | Trunk-based (chosen) | GitFlow |
|---|---|---|
| Team shape | Async **agent** team, small, one repo, one deliverable | — |
| Release cadence | Continuous; `main` always shippable | Long-lived `develop`/`release/*` branches |
| Merge-conflict risk | Low — branches live ≤ 3 days, often ≤ 1 | High — `develop` diverges from `main` |
| Free-CI cost | One CI run per PR + one per merge | Runs on every long-lived branch |
| Fit for stdlib monolith | Single deployable; no need to cherry-pick across release branches pre-1.0 | Pays off for binary/multi-variant releases |
| Downside | Needs disciplined PR size + feature flags (§5) to keep `main` shippable | — |

Rationale in one line: LatencyLedger is a single stdlib Python app with a
static frontend, built by a small async team on free CI — the coordination
cost of GitFlow (long-lived branches, back-merge choreography, release-branch
patching) buys nothing until there are multiple supported release lines.

### 1.2 Branch model

- `main` — the trunk. Always buildable, always passing CI (§4), always
  deployable. Direct pushes to `main` are **forbidden** except for a
  Release Manager hotfix (§6) and the version-tag commit pattern in §3.
- `feat/<short-name>` — feature work (e.g. `feat/regression-detector`).
- `fix/<short-name>` — bug fixes (e.g. `fix/ssrf-redirect-recheck`).
- `docs/<short-name>` — docs-only changes.
- `chore/<short-name>` — CI, config, refactoring with no behaviour change.
- `release/vX.Y.Z` — **only** when a release needs stabilisation while new
  work continues (not expected before v1.0). Cut from `main`, tagged, merged
  back to `main` within 48h. If you are creating one to work around a big PR,
  stop and split the PR instead.

Rules:

- Branch from latest `main`; rebase onto `main` before requesting review if
  behind by more than one merge.
- Branch lifetime target: **≤ 3 working days**. Longer → split, or land
  behind a feature flag (§5) in smaller slices.
- One concern per branch/PR. A PR that needs "and also" is two PRs.
- Squash-merge by default (keeps `main` history linear and changelog-friendly);
  preserve the PR description as the commit body.

### 1.3 PR policy

- **Title format:** `type(scope): summary` — e.g. `feat(gate): add p95 budget endpoint`.
  Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`.
- Every PR **links an issue** (or states why there is none) and fills the PR
  template: *What / Why / How to verify / Screenshots or curl output / Risk*.
- **No self-merge** for non-trivial PRs: the author cannot be the sole
  approver.
- **Review requirements:**
  - **1 approval** from a reviewer other than the author for any code change.
  - **2 approvals** for changes touching `app/auth.py`, `app/checks.py`
    (SSRF guard), `app/db.py`/`app/schema.sql`, `.github/workflows/*`, or
    `Dockerfile`/`docker-compose.yml`.
  - Docs-only PRs: 1 approval, may be an async agent sign-off on the rendered
    markdown.
  - **All blocking CI checks green** before merge (§4). No "merge now, fix
    CI later" on `main`.
  - Review SLA: reviewers respond within **1 working day** (async team);
    approve-with-comments counts as approved if blocking issues are listed.
  - If a PR is stale (> 5 days without author response), the Release Manager
    may close it or take it over — say so in a comment first.
- **Merge discipline:** merge only when the branch is **green and up to date**
  with `main`; delete the branch after merge. Never leave merged branches
  around (`office/*` worker branches are managed by Agent Office tooling).

### 1.4 Versioning branches and tags

Tags are the release record: `vX.Y.Z` (see §2). A tag points at the merge
commit on `main` that shipped that version. No floating tags, no `latest`
tag on git; `latest` may exist only as a Docker image tag (§3).

---

## 2. Versioning, changelog, tag signing

### 2.1 Semantic Versioning rules (SemVer 2.0.0)

`VERSION = MAJOR.MINOR.PATCH`, bumped by the **observable contract**:

- **MAJOR** — breaking change to a public contract: REST API shape
  (`/api/*`, `/api/v1/*` responses, status codes, or error envelope),
  database schema without an automatic migration path (see §6), removal of
  an env var or endpoint, or a change to the Docker/compose interface that
  breaks an existing deployment. **Pre-1.0 exception:** see §2.2.
- **MINOR** — backward-compatible new capability: new endpoint, new optional
  field, new flag, new UI view, new alert channel.
- **PATCH** — backward-compatible fix: bug fix, perf improvement, docs/security
  fix, or a dependency/CI fix with no behaviour change.

Operating rules:

- **Minor bump, not major, when in doubt pre-1.0** — v0.x exists to allow
  rapid iteration (§2.2); the *changelog* is where breaking changes are
  called out loudly.
- The **current version lives in `pyproject.toml`** (`project.version`) and is
  the single source of truth. Code that needs the version (e.g. `/healthz`,
  CLI `--version`) reads it; it is never hard-coded in two places.
- The version in `pyproject.toml` **must match the git tag** for a release.
  Mismatch is a release-blocking defect (§4).
- A release that changes the schema **must** ship its migration in the same PR
  and state the downgrade story in the changelog (§6).

### 2.2 Pre-1.0 policy (0.x)

Per SemVer §8, anything may change in `0.y.z`. For LatencyLedger this means:

- `0.MINOR.PATCH` bumps follow the same rules with MAJOR pinned at 0.
- **Breaking changes are allowed but must be flagged** in the changelog with
  a `Breaking:` prefix and a migration note. "0.x, so no one will mind" is
  not a migration plan.
- The **API surface is frozen at v1.0** (§10): after that, breaking changes
  require a MAJOR bump and a deprecation period (§2.3).

### 2.3 Deprecation (applies from v1.0)

- Announce deprecation in the changelog and in `docs/` **at least one MINOR
  release** before removal.
- Deprecation window: **≥ 90 days** for public APIs, **≥ 1 MINOR** for env vars.
- Deprecations are additive-only (a `Deprecation:` warning header / log line);
  behaviour does not change until the removal MAJOR/MINOR.

### 2.4 Changelog format — Keep a Changelog

- File: `CHANGELOG.md` at repo root. Format follows
  [keepachangelog.com](https://keepachangelog.com/en/1.0.0/) (v1.0.0 structure).
- Sections, in order: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`,
  `Security`. **Omit empty sections** — no placeholder noise.
- **`## [Unreleased]`** section at the top accumulates changes between
  releases. Every merged PR that changes user-visible behaviour adds its
  entry under Unreleased *in the same PR*. Doc-only/internal refactors that
  have no observable effect may be omitted.
- At release time, the `Unreleased` block is renamed to
  `## [X.Y.Z] - YYYY-MM-DD` and a **new empty `Unreleased`** block is started
  above it. The bottom of the file carries reference links:

  ```markdown
  [Unreleased]: https://github.com/devhasen/http-ping/compare/vX.Y.Z...HEAD
  [X.Y.Z]: https://github.com/devhasen/http-ping/compare/vW.V.U...vX.Y.Z
  ```

- Entries are **one line each**, written for users (not commit messages):
  "Regression alert now fires for p95 rises above a configurable threshold
  (default 20%)." Not: "refactored detector.py".
- `## [Unreleased]` must never contain a released version — if a heading
  says `Unreleased` and carries a date, that is a release-process bug.

### 2.5 Tag signing

Goal: a tag you can verify came from this repo, not a re-uploaded fork.

- Release tags (`vX.Y.Z`) **must be signed**. Preferred: **SSH signing** with
  a maintainer key (GitHub verifies SSH-signed tags natively). GPG is
  acceptable if SSH signing is unavailable.
- Setup (one-time, per maintainer): generate an SSH key for signing, add it
  as a **signing key** on the GitHub account, set repo config to verify
  signatures, then tag with `git tag -s vX.Y.Z -m "vX.Y.Z"`.
- **Unsigned tags are blocked in CI:** the release workflow (§3) verifies the
  tag signature and fails the release if it is missing or untrusted. This is
  a merge-blocking check on the release commit.
- Unsigned *annotated* tags on `main` for non-release purposes (e.g. a
  milestone marker) are allowed but must not be named `vX.Y.Z`.
- The Release Manager's public SSH signing key is recorded in `docs/`
  (a `MAINTAINERS` note) so anyone can verify offline with
  `git tag -v vX.Y.Z`.

---

## 3. Build & release pipeline

All automation runs on **GitHub Actions (free tier only)** — this constrains
us: no paid runners, no self-hosted runners, no third-party CI. Everything
below is achievable with `actions/checkout`, `actions/setup-python`, and
`docker/build-push-action` (all free for public repos).

### 3.1 Pipeline stages

```
merge to main ──► [1] version bump ──► [2] tests ──► [3] build ──► [4] publish
```

| Step | What happens | Gate |
|---|---|---|
| **1. Version bump** | Release Manager (or `release` PR) bumps `project.version` in `pyproject.toml`, rolls `CHANGELOG.md` (§2.4), and tags the merge commit `vX.Y.Z` (signed, §2.5). No code change in the bump commit — version + changelog only. | Bump commit is green before tagging |
| **2. Tests** | `python -m pytest -q` on Python 3.11/3.12/3.13 (§4). Version-vs-tag check (`pyproject.toml` == tag). | Blocking |
| **3. Docker build** | `docker build` the `Dockerfile` (`python:3.11-slim`, stdlib only). Smoke-test the image: boot, `GET /healthz` → 200, register → create check → ping-now (scripted curl). | Blocking |
| **4. Publish** | Push image to **GHCR** (`ghcr.io/devhasen/http-ping:X.Y.Z` + `:latest` on MINOR/MAJOR only, never on PATCH-only pre-1.0 — see note). Create a **GitHub Release** from the tag with changelog notes + the `CHANGELOG.md` diff + Docker pull command. | Release exists before the tag is announced |

Notes:

- **GHCR, not Docker Hub** — already authenticated by Actions (`GITHUB_TOKEN`),
  no extra secrets, free for public repos.
- `:latest` moves only on MINOR and MAJOR bumps (and v1.0). A PATCH must not
  silently move `latest` — that hides the version from `docker pull`.
- The **release notes** on the GitHub Release are generated from the
  `CHANGELOG.md` section for that version — no hand-written duplicate.
- **No publish happens without a green tag-verify** (§2.5). Manual publish
  outside the workflow is a process violation; if someone must, they file a
  post-incident note against this spec.

### 3.2 CI triggers

| Trigger | Workflow | Cost control |
|---|---|---|
| `pull_request` to `main` | `ci.yml` — tests + lint + scans (§4) | Path filters skip Docker build on docs-only PRs |
| Push to `main` | `ci.yml` (same checks) + Docker build + smoke | Single run per merge |
| Tag `v*.*.*` | `release.yml` — verify signature → test → build → publish → GitHub Release | Only on real releases |
| Cron (weekly) | `nightly.yml` — full test matrix + dependency scan (§4) | Keeps the free-tier minute budget sane |

Free-tier budget discipline: tests must finish in **< 5 minutes** on
`ubuntu-latest`. If a test suite grows past that, split it — don't pay
for bigger runners.

### 3.3 Local parity

Whatever CI runs, a contributor can run locally with the same commands in
`CONTRIBUTING.md`. If a check only exists in CI YAML, it will rot.

---

## 4. Quality gates — merge-blocking vs advisory

"Blocking" = the merge button (or the Release Manager) refuses to merge.
"Advisory" = reported on the PR, fixed in follow-up, never a reason to
block a merge.

### 4.1 Merge-blocking gates

| Gate | Command / mechanism | Threshold |
|---|---|---|
| **Unit & API tests** | `python -m pytest -q` (Python 3.11–3.13) | All pass; zero skipped without a reason comment |
| **Coverage gate** | `coverage` on `app/stats.py`, `app/detector.py`, `app/auth.py` | **≥ 70%** line coverage on each of these three (product-spec KPI); overall ≥ 60% advisory |
| **Lint / type sanity** | `python -m compileall app` + `python -m py_compile` on all modules; `ruff check app tests` if available, else `python -m pyflakes` — *one* linter, chosen once, recorded here | Zero errors. Warnings advisory. |
| **Stdlib-only guard** | CI asserts `requirements.txt` is empty (or unchanged without a PR discussion — `CONTRIBUTING.md` §3) and `import` scan finds no non-stdlib import in `app/` | Blocking: a new runtime dependency without justification fails CI |
| **Security: secret scan** | `gitleaks` (free, in Actions) on the PR diff | Zero findings — a leaked secret is an incident, not a style nit |
| **Security: SSRF regression tests** | `tests/test_ssrf.py` — private/loopback/link-local IPs blocked, redirect re-check, timeout, 1MB cap (architecture.md) | All pass. These tests are **non-deletable** without 2 approvals + a security note |
| **Frontend smoke** | `curl` the static pages from the ephemeral test server; assert 200 + no `innerHTML` with user data in `app.js` (grep gate) | 200 on `/`, `/r/{slug}` (public), `/healthz` |
| **Version/tag consistency** | On release commits & tags: `pyproject.toml` version == git tag | Blocking on `v*` tags |
| **Tag signature** | `git tag -v` in release workflow (§2.5) | Blocking on `v*` tags |

### 4.2 Advisory gates (reported, not blocking)

| Gate | Tool | When it is promoted to blocking |
|---|---|---|
| **Dependency audit** | `pip-audit` on the (empty) runtime deps + dev deps | Immediately, if a runtime dependency is ever added |
| **SAST** | CodeQL (free for public repos) — `python` queries | Once the codebase exceeds ~5k LOC or the first high-severity advisory is ignored twice |
| **Coverage (overall)** | overall `app/` coverage ≥ 60% | Raise with the gate after v1.0 |
| **Performance smoke** | Ingest latency p95 < 2s (product-spec KPI) measured in the API tests | If a PR regresses it > 20% |
| **Accessibility spot-check** | Manual: keyboard walkthrough + `prefers-reduced-motion` (design-system.md) | When a frontend framework or build step is introduced |
| **Docker image scan** | `trivy image` on the built image | Once we take on non-stdlib bases or CVE-driven rebuilds become routine |

### 4.3 Gate ownership

- **QA** owns test and coverage gates; **security reviewer** owns SSRF/secret
  gates; **Release Manager** owns version/tag/signature gates and may
  grant a **one-time, written waiver** for an advisory gate only — never for
  a blocking gate. A waiver is a comment on the PR, expires with the release,
  and is logged in the changelog if it affects users.

---

## 5. Feature flags — simple env/DB-based flags for a stdlib app

Goal: land half-finished work on `main` without exposing it, with **zero
paid services** and no frontend build step. Two sources, one lookup order.

### 5.1 Design

```python
# app/flags.py  (stdlib only)
import os, sqlite3

# Precedence, highest first:
#   1. explicit env override:  LLFLAG_<NAME>=0|1
#   2. DB override row:        feature_flags(name, enabled, updated_at, updated_by)
#   3. code default:           DEFAULTS = {"oauth_login": False, ...}

def enabled(name: str, conn=None) -> bool:
    env = os.environ.get(f"LLFLAG_{name.upper()}")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    if conn is not None:
        row = conn.execute(
            "SELECT enabled FROM feature_flags WHERE name=?", (name,)
        ).fetchone()
        if row is not None:
            return bool(row[0])
    return DEFAULTS.get(name, False)
```

- **Env flags (`LLFLAG_*`)** — for ops/self-hosters and CI: set in
  `docker-compose.yml` / `.env`. These are the *deployment-level* switches
  (e.g. `RUN_SCHEDULER`, SMTP on/off, `OAUTH_ENABLED` — already in
  architecture.md / product-spec.md as env flags).
- **DB flags (`feature_flags` table)** — for per-deployment product switches
  an admin can flip at runtime without a restart (e.g. enabling the P1
  status page, a new alert channel). Admin-only write endpoint:
  `POST /api/admin/flags {name, enabled}` behind session auth + plan check.
- **Code defaults** — the safe value (usually `False` for new features).
  Every flag is registered in `DEFAULTS` with a one-line comment; an
  unregistered flag name returns `False` and logs a warning — silent typos
  must not turn a feature on.

Schema (added by migration, see §6):

```sql
CREATE TABLE IF NOT EXISTS feature_flags(
  name TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT DEFAULT datetime('now'),
  updated_by TEXT
);
```

### 5.2 Flag lifecycle rules

1. **Every flag has an owner and a removal ticket.** The PR that introduces a
   flag states: default, owner, and the issue that will remove it.
2. **Flags ship off by default** unless the flag is purely an ops kill-switch
   that defaults on (scheduler, rate limiting). Product features default off.
3. **A flag lives ≤ 1 MINOR release.** When the feature is validated, the
   flag is removed and the code path is made unconditional — dead flags are
   how a stdlib codebase rots. The removal PR is blocking-gated like any
   other.
4. **Frontend reads flags via the API**, never by guessing: `GET /api/config`
   returns `{flags: {name: bool}}` for the caller's plan, and `app.js`
   hides/shows accordingly. Features behind a flag must be **invisible** in
   the UI when off — not just disabled.
5. **No flag in the middle of a request path that changes security posture.**
   SSRF guard, auth, and rate limiting are code, not flags.
6. **Flag changes are audited:** DB writes record `updated_by` + timestamp;
   env-flag changes are in version-controlled compose/env examples.

### 5.3 Planned flags for v0.1.0

| Flag | Default | Purpose |
|---|---|---|
| `RUN_SCHEDULER` (env, existing) | `1` | Split web/worker containers |
| `OAUTH_ENABLED` (env, existing) | `0` | GitHub/Google login stub (P2) |
| `SMTP_ENABLED` (env) | `0` | Email alerts off without SMTP config |
| `BILLING_STRIPE` (env) | `0` | Stripe behind flag; manual plan toggle until then (product-spec §4) |
| `PUBLIC_REPORTS` (DB) | `1` | Kill-switch for public report links if abused |
| `REGRESSION_ALERTS` (DB) | `1` | Kill-switch for the detector if false positives spike |

---

## 6. Rollback plan per release type

General principles: **every release is revertible in < 15 minutes**, the
rollback path is **stated in the changelog entry** for that release, and
`main` is never force-pushed except by the Release Manager for a tag
correction (§6.3).

### 6.1 PATCH release (bug fix, no schema change)

| Step | Action |
|---|---|
| Detect | `GET /healthz` failing, or error-rate spike in logs, or user report |
| Roll back | Redeploy the **previous Docker image tag** (`ghcr.io/...:X.Y.Z-1`) — the image is immutable and retained in GHCR. Config/env unchanged. |
| Data | No migration to undo. Samples/alerts written by the bad version are **kept** (they are append-only facts); the detector just stops reading them. |
| Re-release | Fix on `main`, bump PATCH, new tag. The bad tag stays in history (marked "superseded" in the release notes) — never rewritten. |

Time to rollback: **~5 minutes** (image pull + redeploy).

### 6.2 MINOR release (new feature, backward compatible, additive schema)

| Step | Action |
|---|---|
| Detect | Feature visibly broken, or a regression in an existing path |
| First lever | **Flip the feature flag off** (§5) — no redeploy, no code change. This is the primary rollback for MINORs and the reason every new feature ships behind a flag. |
| Second lever | If the break is outside the flagged feature, redeploy the previous image (as in §6.1). |
| Data | Additive schema (new table / new nullable column) is **left in place** on rollback. Roll-forward is safe because migrations are idempotent (`PRAGMA user_version`, architecture.md). Never drop a table/column to "clean up" after a rollback. |
| Re-release | Fix, PATCH bump, new tag. The flag stays off until the fixed MINOR is verified. |

Time to rollback: **~1 minute** (flag flip) or ~5 minutes (image).

### 6.3 MAJOR release (breaking API/schema change) — pre-1.0 and post-1.0

| Step | Action |
|---|---|
| Detect | Breaking change causes client failures or data loss risk |
| Roll back | Redeploy previous image **and** restore the DB from the pre-release backup (see below). A MAJOR with a schema change is **not** roll-back-able by image alone — plan for a DB restore. |
| Backup | **Pre-release DB snapshot is mandatory** for any release with a schema migration: `sqlite3 data.db ".backup data-pre-<version>.db"`, retained for **≥ 30 days**. No snapshot, no release. CI enforces this by failing the release workflow if the migration PR lacks a `## Rollback` section. |
| Data | Restoring the snapshot **discards samples written since the release** — this must be called out in the incident note. If that loss is unacceptable, prefer a forward-fix MAJOR+1 over a restore. |
| Tag correction | If a tag was wrong (wrong version, unsigned), the Release Manager may delete and re-create it **within 24h and before any downstream pin**. After 24h, the tag is immutable history — fix forward with a new version. |
| Re-release | A new MAJOR (or a PATCH, if the break was accidental and no client could have adopted it yet) with a `Breaking:` changelog note and a migration/rollback note. |

Time to rollback: **~15 minutes** (image + DB restore + verification).

### 6.4 Emergency hotfix (production down)

1. Branch `fix/<name>` from the **last good tag**, not from `main` tip if
   `main` has moved on.
2. Fix + tests + 1 approval (Release Manager may self-approve if no other
   reviewer is reachable within 4h — recorded in the PR).
3. Merge to `main`, bump PATCH, tag, pipeline runs end-to-end (§3).
4. **Cherry-pick** the fix onto `main` if the branch diverged, and verify
   `main` is still green (trunk-based keeps this trivial — another reason
   for §1).
5. Post-incident note in the changelog under the hotfix version.

---

## 7. Definition of Done & Definition of Ready

### 7.1 Definition of Ready (DoR) — before anyone writes code

A ticket/story is Ready when **all** of these are true:

- [ ] **User value stated** in one sentence ("As a …, I …, so that …") — from
  product-spec §2 or a linked issue.
- [ ] **Acceptance criteria are testable** — each AC names an endpoint, a
  status code, or a number (e.g. "422 {pass:false, observed_p95} when over
  budget"), not "works well".
- [ ] **Scope is one concern** — if it needs "and also", it is split.
- [ ] **API/DB contract sketched** — request/response shape and any schema
  change are written in the ticket, with the migration and rollback note.
- [ ] **Flag decision made** — new flag name, default, owner (§5).
- [ ] **Open questions answered** — no "TBD" in the ticket at kickoff.
- [ ] **Design reference linked** — design-system.md token/component, or
  "no UI change".
- [ ] **Estimate ≤ 3 days** — larger work is a milestone, not a ticket.

The Release Manager (or the ticket author) checks DoR before the ticket is
picked up. A ticket that fails DoR goes back with comments — no exceptions
for "quick" work.

### 7.2 Definition of Done (DoD) — before a PR is merged

A PR is Done when **all** of these are true:

- [ ] **Code** — snake_case, type hints on public functions, module
  docstrings; no non-stdlib runtime import (§4.1 stdlib guard green).
- [ ] **Tests** — new/changed logic has tests; coverage gate (§4.1) green;
  SSRF tests untouched and passing.
- [ ] **CI green** — every blocking gate (§4.1) passing on the PR.
- [ ] **Docs** — `CHANGELOG.md` Unreleased entry added; `docs/` updated if
  behaviour changed (`CONTRIBUTING.md` §6).
- [ ] **Flag** — feature behind a flag (§5) with owner + removal ticket, or
  an explicit "no flag needed" note.
- [ ] **Security self-check** — no new `innerHTML` with user data, no new
  unvalidated input path, no secret in the diff (secret scan green).
- [ ] **Verification** — author pasted curl output or a screenshot in the PR;
  a reviewer reproduced it.
- [ ] **Review** — required approvals obtained (§1.3), review comments
  resolved, branch up to date with `main`.
- [ ] **Rollback note** — PR states how to undo it (flag flip / image /
  DB restore), per §6 for its release type.

A merged PR that fails DoD is reverted or fixed forward in a follow-up PR
within 2 working days — the DoD failure is itself a bug in the process.

---

## 8. Team rituals — adapted to an async agent team

No standups, no sync meetings that could be a doc. Every ritual produces an
**artifact in the repo or on the PR** — if it isn't written down, it didn't
happen.

### 8.1 Spec review (async, replaces design review)

- **When:** on any PR that changes a public contract (`/api/*`, schema,
  env vars) or adds a flag.
- **How:** the author posts the contract diff in the PR; reviewers comment
  asynchronously within 1 working day. The Release Manager checks the DoR
  (§7.1) at the same time.
- **Artifact:** the contract diff + reviewer sign-off on the PR. Contract
  decisions are copied into `docs/architecture.md` by the merging PR.

### 8.2 Integration day (weekly, replaces the "big-bang merge")

- **When:** every Friday (or the last working day of the sprint).
- **What:** each in-flight branch is merged to `main` (or explicitly
  deferred with a reason). The full CI suite + Docker smoke (§3) must be
  green on `main` by end of day.
- **Why:** trunk-based only works if integration is *frequent*. A branch
  that survives integration day unmerged must justify itself in a comment
  or be split (§1.2).
- **Artifact:** a short `docs/integration-log.md` entry (one line per merged
  PR + any integration breakage found and fixed).

### 8.3 Demo (async, replaces show-and-tell)

- **When:** at the end of each sprint / milestone.
- **How:** the team records a **scripted demo** (a shell script + captured
  output, or an animated GIF if available — never a live screen-share) against
  a running Docker container, and posts it on the milestone issue + in
  `docs/demo-<milestone>.md`.
- **Content:** the happy path from the product spec (§2, P0 stories), plus
  one failure path (e.g. regression alert firing, CI gate failing).
- **Artifact:** `docs/demo-<milestone>.md` with the exact commands to
  reproduce. A demo that can't be reproduced from the doc is not a demo.

### 8.4 Release retro (after each release)

- One PR comment thread on the release: what broke, what the gates missed,
  one process fix to ship in the next sprint. Filed as an issue if it needs
  work.
- **Artifact:** the thread + any resulting change to this spec (merged as a
  `docs/` PR, 1 approval).

### 8.5 Office hours / unblocking

- A **blocked** agent posts on the issue: what is blocked, what was tried,
  what is needed, and a deadline after which the Release Manager will
  re-scope. Silence for > 1 working day on a blocked ticket escalates to
  the Release Manager automatically.
- Agents never wait idle: if blocked, pick up the next Ready ticket (§7.1).

---

## 9. First release — v0.1.0 milestone plan

**v0.1.0 = the P0 scope of `docs/product-spec.md` §2 (stories 1–8).** That is
the first *shippable* LatencyLedger: auth, URL checks, manual ping, history
chart, regression alerts, API keys, CI gate, public reports, Docker.

### 9.1 Milestone count: **7 milestones** (M1–M7)

M1–M6 are build milestones; **M7 is the release milestone** (hardening,
docs, tag, publish). Each milestone is mergeable on its own — no milestone
leaves `main` unshippable.

| # | Milestone | Hero outcome | Key deliverables | Owner (lead) |
|---|---|---|---|---|
| **M1** | **Repo & skeleton** | `python3 -m app.main` boots, `/healthz` 200, CI green | `app/main.py`, `app/config.py`, `app/router.py`, `app/db.py` + `schema.sql` + user_version migrations, Docker + compose, `ci.yml`, README quick-start verified | Backend + Ops |
| **M2** | **Auth & identity** | Register → login → logout → `/api/auth/me` | `app/auth.py` (pbkdf2_hmac ≥100k iters, session cookie), `users`/`sessions`/`api_keys` tables, login rate limit, `POST/GET/DELETE /api/keys` (ll_ keys, hash-only storage) | Backend |
| **M3** | **Checks & sampling** | Add a check, watch samples land in SQLite | `app/checks.py` (validation + SSRF guard), `app/sampler.py` (urllib fetch+timing, redirect-off, 10s timeout, 1MB cap), `app/scheduler.py` (in-process thread, `RUN_SCHEDULER` flag), check CRUD API, `POST .../ping-now` (N=10, min/max/avg/p50/p95/p99) | Backend |
| **M4** | **Stats & detector** | p95 computed; regression alert fires on injected drift | `app/stats.py` (percentiles, bucketing, rolling baseline), `app/detector.py` (+20% rule, min 50 samples, 6h cooldown), `app/alerts.py` (email via smtplib behind `SMTP_ENABLED`, webhook POST + retry), `alerts`/`deliveries` tables, `/series` + `/stats` endpoints; **coverage gate ≥70% on stats/detector/auth from this milestone on** | Backend + QA |
| **M5** | **CI gate & public API** | `POST /api/v1/checks/{id}/gate` passes/fails on a p95 budget | `app/gate.py`, `POST /api/v1/checks/{id}/samples` (CI ingestion, per-key rate limit), API-key auth on `/api/v1/*`, `examples/github-actions.yml` verified end-to-end in CI | Backend + QA |
| **M6** | **Frontend & public reports** | Dashboard, check detail, history chart, public link — all with no build step | `app/static/` (`index.html`, `app.js`, `style.css`, `check.html`, `r.html`), canvas chart (p50/p95/baseline/SHA ticks), alert banner, `/r/{slug}` public report, session-cookie UI auth, design-system tokens (§design-system.md), empty states | Frontend |
| **M7** | **Release** | v0.1.0 tagged, signed, published, demo-able | Hardening pass (SSRF tests, secret scan, perf smoke), `CHANGELOG.md` rolled to v0.1.0, README + `examples/` + `SECURITY.md` final, Docker image published to GHCR, GitHub Release, demo doc (§8.3) | Release Mgr + all |

### 9.2 Order of implementation & dependencies

```
M1 (skeleton, DB, Docker, CI)
 └─► M2 (auth + API keys)          ─┐
      └─► M3 (checks + sampler)     │  M3 needs M2 (ownership) but
           └─► M4 (stats+detector) │  M4's stats/detector are pure
                └─► M5 (CI gate)   │  functions — can be built/tested
                     │              │  in parallel against M3's samples
                     ▼              │
                M6 (frontend) ◄─────┘  M6 needs M3/M4/M5 APIs; can start
                     │                 against stubbed JSON from M3 on
                     ▼                 (contract-first, §9.3)
                M7 (release)
```

- **Backend critical path:** M1 → M2 → M3 → M4 → M5 → M7. M4's `stats.py` and
  `detector.py` are **pure functions** (architecture.md) — they can be written
  and unit-tested against fixed fixtures *before* the sampler exists, which
  de-risks the critical path.
- **Frontend (M6)** starts as soon as M3's check-CRUD contract is sketched
  (contract-first), against stub responses, and integrates for real once
  M4/M5's `/series`, `/stats`, and `/gate` are live.
- **QA** is not a final phase: test cases are written with each milestone
  (unit for M4, API for M2/M3/M5, SSRF for M3, frontend smoke for M6).

### 9.3 Integration points (contract-first)

These are the seams where teams meet — a change here is a spec review (§8.1):

| Seam | Contract | Producer → Consumer |
|---|---|---|
| `GET /api/checks`, `POST /api/checks`, `GET/PATCH/DELETE /api/checks/{id}` | JSON shapes in product-spec §2 ACs | Backend (M3) → Frontend (M6) |
| `POST /api/checks/{id}/ping-now` → `{samples:[{ms,status}], stats:{min,max,avg,p50,p95,p99}}` | sorted array + server-side stats | Backend (M3/M4) → Frontend (M6) |
| `GET /api/checks/{id}/series?range=24h\|7d\|30d` → bucketed `{ts, avg, p95}` | bucketing in `stats.py` | Backend (M4) → Frontend chart (M6) |
| `POST /api/v1/checks/{id}/gate {p95_ms}` → 200 `{pass:true}` / 422 `{pass:false, observed_p95}` | gate semantics in `gate.py` | Backend (M5) → CI users + `examples/github-actions.yml` |
| `GET /r/{slug}` public JSON + HTML | no auth, no leaked fields | Backend (M3) → Frontend (M6) |
| `feature_flags` table + `GET /api/config` (§5) | flag read path | Backend (M1) → Frontend + Ops |

### 9.4 Risks & mitigations

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| **Scheduler reliability in a single process** (product-spec §6) — missed ticks, duplicate ingest | Medium / high | `RUN_SCHEDULER` env split (§5), WAL SQLite, idempotent ingest, `/healthz` scheduler heartbeat (M1/M3); a stall webhook in M4 |
| **False-positive regression alerts erode trust** | Medium / high | Min-50-samples, +20% hysteresis, 6h cooldown (product-spec §2.5); detector tested with injected drift in M4; `REGRESSION_ALERTS` DB kill-switch (§5.3) |
| **SSRF / abuse via the checker** (product-spec §6) — using LatencyLedger as a proxy | Medium / **critical** | SSRF guard in M3 *before* any sampler ships; non-deletable tests (§4.1); private/loopback block at DNS **and** connect, redirect re-check, timeout, 1MB cap |
| **SQLite write contention** as samples grow | Low (v0.1.0) / medium | Single-writer queue, WAL, short transactions (M1/M3); Postgres path documented (architecture.md) — not a v0.1.0 blocker |
| **Auth bugs** (session fixation, timing, key leakage) | Low / critical | M2 is gated by 2 approvals (§1.3) + `test_auth.py`; pbkdf2 ≥100k iters, constant-time compare, hash-only key storage (architecture.md) |
| **Frontend integration slips** (M6 is last and largest) | Medium / medium | Contract-first start from M3 (§9.2); stubbed JSON so M6 never waits on M4/M5; integration day weekly (§8.2) catches drift early |
| **Free-CI minute budget** exceeded | Low / low | Path filters, <5min test budget (§3.2); weekly cron instead of per-PR full matrix |
| **Scope creep from P1** (projects, status page, Stripe) | **High** / medium | P1 is explicitly out of v0.1.0; every P1 ask becomes a Ready-check (§7.1) for the *next* release, not a v0.1.0 add-on |

---

## 10. Post-launch — v1.0 criteria

v1.0 is a **contract freeze**, not a feature dump. LatencyLedger is "1.0"
when **all** of the following are true — and not before:

### 10.1 Product criteria

- [ ] **P0 scope (product-spec §2 stories 1–8) shipped and stable** for ≥ 4
      consecutive weeks with no MAJOR-breaking change.
- [ ] **P1 scope (stories 9–14) shipped**: projects, alert channels
      (Slack/Discord), status page, CSV/JSON export, commit (git SHA)
      annotation, billing behind the Stripe flag with the manual plan
      toggle as the default path.
- [ ] **Public API frozen:** `/api/*` and `/api/v1/*` (including the CI gate)
      are under a deprecation policy (§2.3) and a MAJOR bump is required to
      break them.
- [ ] **Success metrics (product-spec §5) hit minimums for one full month:**
      activation ≥ 40% (first check within 24h), W4 retention ≥ 25%,
      ≥ 30% of Pro users get ≥ 1 true regression alert, alert precision
      ≥ 70%, scheduler uptime ≥ 99.9%, ingest p95 < 2s.

### 10.2 Engineering criteria

- [ ] **DB migration story proven:** at least one schema migration shipped and
      rolled back (§6.3 DB-restore path) in a staging/self-host drill, with
      the drill recorded in `docs/`.
- [ ] **Coverage gate raised:** stats/detector/auth ≥ 70% is the floor; a
      **v1.0 target of ≥ 80%** on those modules is met and the gate updated.
- [ ] **Security posture:** CodeQL promoted from advisory to blocking (§4.2),
      no open high-severity findings, `SECURITY.md` disclosure process
      exercised at least once (or explicitly table-tabled with a reason).
- [ ] **Self-host story verified:** a clean `docker compose up` on a fresh
      machine reaches a working dashboard with no external keys (product-spec
      §3) — this is the OSS conversion funnel, so it is a release criterion,
      not a nicety.
- [ ] **Observability:** `/healthz`, structured logs, and the scheduler-stall
      alert are live in the reference deployment; an OpenTelemetry hook point
      is documented even if not exported (P2).

### 10.3 Process criteria

- [ ] **This spec's process has run for ≥ 2 release cycles** (branching §1,
      changelog §2.4, pipeline §3, gates §4, flags §5, rollback §6, DoD §§7,
      rituals §8) — v1.0 is declared on a *proven* process, not a first
      attempt at one.
- [ ] The GitHub Release for v1.0 is signed (§2.5), the image is on GHCR,
      and the **migration guide from v0.x** is published in `docs/`.

### 10.4 What v1.0 is not

- It is not "all P2 features" (multi-region, ML anomaly, teams, OAuth).
  Those are v1.x candidates behind flags (§5), chosen by the same DoR/DoD
  process.
- It is not a rewrite. The stdlib-only constraint holds through v1.0; a
  framework migration is a MAJOR-bump proposal with its own spec, not a
  v1.0 surprise.

---

*End of release spec. Companion docs: `docs/product-spec.md` (what),
`docs/architecture.md` (how it fits together), `docs/roadmap.md` (when),
`docs/design-system.md` (what it looks like).*
