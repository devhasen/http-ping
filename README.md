# LatencyLedger

Continuous API latency regression tracking with CI gates — know when your API got slower before your users do.

LatencyLedger extends the `httpping` latency-measurement core into a full SaaS: it polls your URLs on a schedule, stores every sample, computes p50/p95/p99, and alerts you when p95 drifts >20% above its rolling baseline — even while uptime still looks "green". A CI gate endpoint lets you fail a build when a latency budget is blown.

## Quick start (no API keys, no pip install)

```bash
python3 -m app.main          # stdlib-only, http://localhost:8000
# or
docker compose up
```

Requires Python >= 3.11. `requirements.txt` is intentionally empty — the backend runs on the standard library alone.

## Features (sprint 1)

- URL checks on a schedule (1m–1h), manual "ping now" (10 requests, min/max/avg/p50/p95/p99)
- Latency history charts (24h / 7d / 30d), no build step, vanilla JS + canvas
- Regression alerts (+20% p95 vs baseline, cooldown, email/webhook)
- CI gate: `POST /api/v1/checks/{id}/gate` with `{p95_ms}` budget → pass/fail
- Public read-only report links, API keys for CI

## Docs

- [Product spec](docs/product-spec.md) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md) · [Design system](docs/design-system.md)

## License

MIT — see [LICENSE](LICENSE).
