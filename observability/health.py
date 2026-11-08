"""Health/readiness for GET /healthz (perf-spec §1.2, §3.6, §7).

Reports DB ping, scheduler heartbeat lag, ingest queue depth, process RSS.
Must never queue behind ingest; keep it cheap and side-effect free.
"""
from __future__ import annotations

import os
import sqlite3
import time

try:
    import resource
except ImportError:  # non-Unix
    resource = None  # type: ignore


def process_rss_mb() -> float:
    if resource is not None:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # KB on Linux
    return 0.0


def _db_ok(db_path: str | None, conn: sqlite3.Connection | None) -> bool:
    try:
        c = conn or (sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) if db_path else None)
        if c is None:
            return False
        c.execute("SELECT 1").fetchone()
        if conn is None:
            c.close()
        return True
    except Exception:
        return False


def health_status(*, db_path: str | None = None, conn: sqlite3.Connection | None = None,
                  scheduler_last_beat_ts: float | None = None, ingest_queue_depth: int = 0,
                  uptime_s: float | None = None, version: str = "0.1.0") -> dict:
    now = time.time()
    beat_lag = (now - scheduler_last_beat_ts) if scheduler_last_beat_ts is not None else None
    db_ok = _db_ok(db_path, conn)
    # Scheduler stall >10s (perf-spec §7) degrades health but DB failure is critical.
    status = "ok" if db_ok and (beat_lag is None or beat_lag <= 10) else ("degraded" if db_ok else "error")
    return {
        "status": status,
        "version": version,
        "db_ok": db_ok,
        "scheduler_heartbeat_lag_s": round(beat_lag, 3) if beat_lag is not None else None,
        "ingest_queue_depth": ingest_queue_depth,
        "queue_warn": ingest_queue_depth > 500,
        "rss_mb": round(process_rss_mb(), 1),
        "rss_warn_450mb": process_rss_mb() > 450,
        "uptime_s": round(uptime_s, 1) if uptime_s is not None else None,
        "ts": now,
    }
