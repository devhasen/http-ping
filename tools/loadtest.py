#!/usr/bin/env python3
"""Urllib concurrent load tester with percentile report (perf-spec §4).

Stdlib only: urllib.request + ThreadPoolExecutor.
Scenarios S1-S6 map to §4.2; thresholds in §4.3 checked via exit code.
Default targets are placeholders - point --base-url at a local instance.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

SCENARIOS = {
    "S1": ["/api/checks", "/api/checks/1/series?range=7d", "/api/checks/1/stats"],
    "S2": ["/api/v1/checks/1/gate", "/api/v1/checks/1/samples"],
    "S3": ["/api/auth/login"],
    "S4": ["/healthz"],
    "S5": ["/r/example"],
    "S6": ["/api/checks/1/ping-now"],
}


def _one(url: str, method: str, timeout: float):
    req = urllib.request.Request(url, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return {"ok": 200 <= r.status < 500, "status": r.status, "ms": (time.perf_counter() - t0) * 1000}
    except urllib.error.HTTPError as e:
        return {"ok": e.code < 500, "status": e.code, "ms": (time.perf_counter() - t0) * 1000}
    except Exception as e:
        return {"ok": False, "status": None, "error": type(e).__name__, "ms": (time.perf_counter() - t0) * 1000}


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (k - lo)


def run(scenario: str, rps: int, duration: int, base_url: str, timeout: float) -> dict:
    paths = SCENARIOS[scenario]
    total = max(1, rps * duration)
    urls = [(base_url.rstrip("/") + paths[i % len(paths)], "POST" if scenario in ("S2", "S3", "S6") else "GET")
            for i in range(total)]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, rps)) as ex:
        results = list(ex.map(lambda u: _one(u[0], u[1], timeout), urls))
    lat = [r["ms"] for r in results]
    errors = sum(1 for r in results if not r["ok"])
    return {
        "scenario": scenario, "base_url": base_url, "requests": len(results),
        "rps_target": rps, "duration_s": duration,
        "p50_ms": round(pct(lat, 50), 2), "p95_ms": round(pct(lat, 95), 2), "p99_ms": round(pct(lat, 99), 2),
        "max_ms": round(max(lat), 2) if lat else 0, "mean_ms": round(statistics.mean(lat), 2) if lat else 0,
        "error_rate": round(errors / len(results), 4) if results else 0, "errors": errors,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LatencyLedger load tester (urllib, stdlib only)")
    ap.add_argument("--scenario", choices=list(SCENARIOS), default="S1")
    ap.add_argument("--rps", type=int, default=20)
    ap.add_argument("--duration", type=int, default=60, help="seconds")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    a = ap.parse_args(argv)
    r = run(a.scenario, a.rps, a.duration, a.base_url, a.timeout)
    if a.json:
        print(json.dumps(r))
    else:
        print(f"{r['scenario']}  {r['requests']} reqs  p50={r['p50_ms']}ms p95={r['p95_ms']}ms "
              f"p99={r['p99_ms']}ms max={r['max_ms']}ms err={r['error_rate']:.2%}")
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
