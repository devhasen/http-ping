# LatencyLedger — Observability

Source specs: `docs/analytics-spec.md`, `docs/perf-spec.md`. Stdlib-only, first-party only.

## Modules

| File | Purpose |
|---|---|
| `observability/metrics.py` | Counters/histograms, Prometheus text format |
| `observability/logging.py` | Structured JSON logger with PII redaction |
| `observability/events.py` | 38-event taxonomy, envelope writer, `events` DDL |
| `observability/health.py` | `GET /healthz` payload (DB, scheduler lag, queue, RSS) |
| `tools/loadtest.py` | Urllib load tester S1–S6 with percentile report |

## Reading metrics

`GET /metrics` returns (or `render_metrics()` in-process):

```text
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/healthz",status="200"} 1234
# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{endpoint="/healthz",le="0.025"} 1200
http_request_duration_seconds_bucket{endpoint="/healthz",le="+Inf"} 1234
http_request_duration_seconds_sum{endpoint="/healthz"} 3.2
http_request_duration_seconds_count{endpoint="/healthz"} 1234
```

Counter = monotonic count (`http_requests_total`, `gate_evaluations_total`,
`alerts_raised_total`). Histogram = cumulative buckets + sum/count; p95 is
derived from bucket counts (`le` lines), e.g. smallest `le` whose count ≥
0.95 × `+Inf` count. Record per request via `observe_http(status, dt, endpoint)`.

Budgets to compare against: perf-spec §1.2 (e.g. `/healthz` p95 ≤ 25 ms,
gate ≤ 150 ms, ingest ≤ 100 ms).

## Reading logs

One JSON object per line on stdout:

```json
{"ts":"2026-11-08T04:00:00Z","level":"INFO","logger":"app","msg":"request","endpoint":"/healthz","status":200,"email":"<16-hex-hash>"}
```

`sanitize()` hashes `email/password/api_key/token/...` and reduces `url` to
`{url_hash, url_host}` before emission (analytics-spec §8). Never log raw IP,
email, keys, or full URLs. Tail/filter: `jq 'select(.level=="ERROR")' app.log`.

## Dashboards (admin, `/admin/analytics` — analytics-spec §5)

D1 Growth (signups/activated), D2 Funnels, D3 Retention heatmap, D4 Alert
quality/precision, D5 Revenue & CI gate pass/fail. Queries run server-side
against `events` (indexes cover 90d), cached 60s. If dashboards regress, check
§4 cohort SQL in the analytics spec.

## Alert rules (suggested)

| Alert | Condition | Severity |
|---|---|---|
| 5xx rate | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.001` | page |
| Endpoint p95 breach | histogram p95 > perf-spec §1.2 budget 5m | page |
| Scheduler stall | `scheduler_heartbeat_lag_s > 10` (`/healthz`) | page |
| Queue growth | `ingest_queue_depth > 500` | warn |
| Memory | `rss_mb > 450` for 5m | warn |
| Alert precision | useful/(useful+false_positive) < 70% 30d | ticket |
| PII scan | any raw PII in `properties` | page immediately |

Error budget: 5xx < 0.1% excl. 4xx (perf-spec §1.2).

## Weekly report template

Generated Mon 09:00, emailed to admins, posted to `/admin/analytics/weekly`
(analytics-spec §9). Trailing 7d vs prior 7d:

```markdown
# LatencyLedger — Weekly Metrics (YYYY-MM-DD → YYYY-MM-DD)

## North Star
- Alerts acted on (delivered → viewed ≤1h): N (+X% WoW)

## Growth
- Signups: N (+X%) | Activation (first check ≤24h): N (X%, target ≥40%)
- Median time-to-first-chart: Xm Ys

## Retention
- W4 retention: X% (target ≥25%) | DAU: N | WAU: N

## Alert quality
- Raised: N | Delivered: N (X%) | Viewed: N | Acked useful: N
- Precision: X% (target ≥70%) | False-positive rate: X%

## CI gate
- Evaluated: N (pass N / fail N) | Fail rate: X% | GitHub Actions share: X%

## Revenue
- Free: N | Pro: N (+N) | Team: N (+N) | MRR: $N | Free→paid: X% (target ≥3%)

## Data quality
- Unknown events: N | PII scans: clean | Late events: X%
- Ingest p95: Nms | Scheduler uptime: X%

## Experiments
- <id>: <result, CI> — <decision>

## Notes
- <ships, incidents, decisions>
```

Column formatting: Δ% vs prior week in parentheses; every KPI from
product-spec §5 appears once; missed targets flagged `⚠` with owner note.

## Load tests

```bash
python tools/loadtest.py --scenario S1 --rps 20 --duration 60 --base-url http://localhost:8000
python tools/loadtest.py --scenario S2 --rps 50 --duration 30 --base-url http://localhost:8000 --json
```

Exit 0 = ran; thresholds in perf-spec §4.3 (p95/error/RSS). A >20% p95
regression vs the archived run blocks release (§8).
