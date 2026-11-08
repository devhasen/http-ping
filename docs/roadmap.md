# LatencyLedger Roadmap

## Sprint 1 (P0 — build now)
Auth + API keys; check CRUD + scheduler; sample ingest; stats (p50/p95/p99) + history chart; regression detector + email/webhook alerts; CI gate endpoint; public report links; Docker; tests (≥70% on core).

## Sprint 2 (P1)
Projects; alert channels (Slack/Discord); status page; CSV/JSON export; commit (git SHA) annotation on charts; Stripe behind env flag (manual plan toggle until then).

## Later (P2)
Multi-region checks; z-score anomaly detection; teams/workspaces with roles; OAuth login (stub now, enable with env keys); Postgres adapter; OpenTelemetry export.

## Milestones
- M1: Alpha — single-user, 10 beta checks, manual alert review.
- M2: Public launch — CI gate + GitHub Actions example, 100 signups.
- M3: 50 paying users ($450 MRR) — requires P1 alert channels + status pages.
