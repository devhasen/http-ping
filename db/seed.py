"""Deterministic demo seed for LatencyLedger (stdlib only, PRNG seed 42).

Run: python -m db.seed [path/to.db] [--reset]
  --reset  drop/recreate the DB file, run all migrations, then seed.

Contents (per task + docs/data-spec.md §7, scaled to /7d scope):
  2 users (pro 'demo', free 'ops'), 3 checks, ~2000 samples over 7 days,
  1 regression episode (p95 ~210 -> ~389ms, days 5-6, fake SHA abc1234),
  matching alert + delivery, gate_evaluations, rollups (sample_buckets /
  check_stats_daily rebuilt from raw samples), a session, an api_key.
Idempotent without --reset: rows use INSERT OR IGNORE / fixed ids.
All timestamps are anchored to a fixed epoch so the dataset is stable.
"""
from __future__ import annotations

import hashlib
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from db.migrations import migrate, connect  # noqa: E402

EPOCH = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)  # fixed anchor
FAKE_SHAS = ["abc1234", "def5678", "0123abc", "a1b2c3d", "deadbeef"]
USERS = [
    ("usr_demo00000001", "demo@latencyledger.local", "pro", "Demo User"),
    ("usr_ops000000001", "ops@latencyledger.local", "free", "Ops User"),
]
CHECKS = [
    # id, user, name, url, interval_sec, threshold_pct, budget_ms
    ("chk_users0000001", "usr_demo00000001", "api.example.com/users", "https://api.example.com/users", 300, 20, 250),
    ("chk_checkout001", "usr_demo00000001", "api.example.com/checkout", "https://api.example.com/checkout", 300, 20, 300),
    ("chk_search00001", "usr_ops000000001", "api.example.com/search", "https://api.example.com/search", 900, 20, None),
]

def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _pw_hash(pw: str) -> str:
    salt = hashlib.sha256(b"latencyledger-seed-salt").hexdigest()[:16]
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2-sha256$200000${salt}${digest}"

def seed(db_path: str | Path) -> dict[str, int]:
    rng = random.Random(42)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        counts: dict[str, int] = {"users": 0, "checks": 0, "samples": 0, "alerts": 0}
        for uid, email, plan, name in USERS:
            cur = conn.execute(
                "INSERT OR IGNORE INTO users (id,email,pw_hash,plan,display_name,email_verified_at,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (uid, email, _pw_hash("demo1234"), plan, name, _fmt(EPOCH), _fmt(EPOCH), _fmt(EPOCH)),
            )
            counts["users"] += cur.rowcount
        # 1 session + 1 api_key for the demo user (fixed ids -> idempotent)
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id,user_id,created_at,expires_at,last_seen_at,ip_hash,user_agent)"
            " VALUES (?,?,?,?,?,?,?)",
            ("sess_demo0000001", "usr_demo00000001", _fmt(EPOCH), _fmt(EPOCH + timedelta(days=30)),
             _fmt(EPOCH + timedelta(hours=1)), hashlib.sha256(b"127.0.0.1").hexdigest()[:32], "seed/1.0"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO api_keys (id,user_id,label,prefix,hash,created_at)"
            " VALUES (?,?,?,?,?,?)",
            ("key_demo00000001", "usr_demo00000001", "CI prod", "ll_demo000",
             hashlib.sha256(b"ll_demo00000000000000000000000000").hexdigest(), _fmt(EPOCH)),
        )
        for cid, uid, name, url, interval, thr, budget in CHECKS:
            cur = conn.execute(
                "INSERT OR IGNORE INTO checks (id,user_id,name,url,interval_sec,threshold_pct,budget_ms,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, uid, name, url, interval, thr, budget, _fmt(EPOCH), _fmt(EPOCH)),
            )
            counts["checks"] += cur.rowcount

        # --- samples: 7 days, effective 5-min density (every 300s for 300s checks,
        # every 900s for the 900s check). Deterministic random walk + injected
        # regression on checkout for days 5-6 (~p95 210 -> 389). ---
        sample_rows = []
        for cid, _uid, _name, _url, interval, _thr, _b in CHECKS:
            # ~15-min effective density -> ~670 samples/check over 7d (~2000 total,
            # per task spec; raw scheduler interval stays 300/900s in `checks`)
            step = 900
            base = 180.0
            t = EPOCH
            end = EPOCH + timedelta(days=7)
            while t <= end:
                # regression window: checkout, days 5-6 (offset 4d..6d from EPOCH)
                is_regress = cid == "chk_checkout001" and timedelta(days=4) <= (t - EPOCH) < timedelta(days=6)
                drift = 1.85 if is_regress else 1.0
                # diurnal wave + jitter
                wave = 1.0 + 0.15 * (1 if 8 <= t.hour < 18 else -1)
                ms = max(20.0, rng.gauss(base * drift * wave, 25 * drift))
                is_err = rng.random() < (0.02 if cid == "chk_search00001" else 0.003)
                if is_err:
                    sample_rows.append((cid, _fmt(t), None, None, None, rng.choice(["timeout","connect"]), None, None, "scheduler"))
                else:
                    sample_rows.append((cid, _fmt(t), round(ms, 1), 200, 1024, None,
                                        FAKE_SHAS[int((t - EPOCH).total_seconds() // step) % len(FAKE_SHAS)] if cid == "chk_checkout001" else None,
                                        None, "scheduler"))
                t += timedelta(seconds=step)
        # Idempotency: skip re-insert if samples already exist for the window
        existing = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO samples (check_id,ts,ms,status,size_bytes,error_kind,git_sha,note,source)"
                " VALUES (?,?,?,?,?,?,?,?,?)", sample_rows)
            counts["samples"] = len(sample_rows)

        # --- regression alert (matches the injected episode) ---
        alert_ts = _fmt(EPOCH + timedelta(days=5, hours=1))
        cur = conn.execute(
            "INSERT OR IGNORE INTO alerts (id,check_id,kind,observed_p95,baseline_p95,delta_pct,cooldown_until,created_at,acked_at,acked_by)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (1, "chk_checkout001", "regression", 389.0, 210.0, 85.2,
             _fmt(EPOCH + timedelta(days=5, hours=7)), alert_ts, None, None),
        )
        counts["alerts"] += cur.rowcount
        conn.execute(
            "INSERT OR IGNORE INTO alert_channels (id,check_id,kind,target,enabled,created_at) VALUES (?,?,?,?,?,?)",
            ("chn_demo_email01", "chk_checkout001", "email", "demo@latencyledger.local", 1, _fmt(EPOCH)),
        )
        conn.execute(
            "INSERT OR IGNORE INTO deliveries (id,alert_id,channel_id,status,attempts,delivered_at,ts) VALUES (?,?,?,?,?,?,?)",
            (1, 1, "chn_demo_email01", 200, 1, alert_ts, alert_ts),
        )

        # --- gate evaluations (deterministic, 70% pass target) ---
        for i in range(20):
            gt = EPOCH + timedelta(days=i % 7, hours=i)
            observed = round(rng.gauss(220, 40), 1)
            passed = 1 if observed <= 300 else 0
            conn.execute(
                "INSERT INTO gate_evaluations (check_id,user_id,budget_ms,observed_p95,window_n,pass,git_sha,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                ("chk_checkout001", "usr_demo00000001", 300, observed, 50, passed,
                 FAKE_SHAS[i % len(FAKE_SHAS)], _fmt(gt)),
            )

        # --- rollups rebuilt from raw samples (pure function of samples, §5.3) ---
        for cid, *_ in CHECKS:
            rows = conn.execute(
                "SELECT ts, ms, error_kind FROM samples WHERE check_id=? ORDER BY ts", (cid,)).fetchall()
            by_day: dict[str, list] = {}
            for r in rows:
                by_day.setdefault(r["ts"][:10], []).append(r)
            for day, day_rows in by_day.items():
                ok = sorted(r["ms"] for r in day_rows if r["ms"] is not None)
                n, n_err = len(day_rows), len(day_rows) - len(ok)
                def pct(p):
                    if not ok: return None
                    k = (len(ok) - 1) * p
                    lo = int(k); hi = min(lo + 1, len(ok) - 1)
                    return round(ok[lo] + (ok[hi] - ok[lo]) * (k - lo), 1)
                uptime = round(100 * len(ok) / n, 2) if n else None
                conn.execute(
                    "INSERT OR REPLACE INTO check_stats_daily"
                    " (check_id,day,n,n_errors,min_ms,p50_ms,p95_ms,p99_ms,max_ms,avg_ms,uptime_pct,updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, day, n, n_err, ok[0] if ok else None, pct(0.5), pct(0.95), pct(0.99),
                     ok[-1] if ok else None, round(sum(ok)/len(ok),1) if ok else None, uptime, _fmt(EPOCH)),
                )
            # 1h buckets (bucket_sec=3600) for chart reads
            by_bucket: dict[str, list] = {}
            for r in rows:
                by_bucket.setdefault(r["ts"][:13] + ":00:00Z", []).append(r)
            for bstart, brows in by_bucket.items():
                ok = sorted(r["ms"] for r in brows if r["ms"] is not None)
                conn.execute(
                    "INSERT OR REPLACE INTO sample_buckets"
                    " (check_id,bucket_start,bucket_sec,n,n_errors,avg_ms,p95_ms,min_ms,max_ms,updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (cid, bstart, 3600, len(brows), len(brows) - len(ok),
                     round(sum(ok)/len(ok),1) if ok else None,
                     ok[int(0.95*(len(ok)-1))] if ok else None,
                     ok[0] if ok else None, ok[-1] if ok else None, _fmt(EPOCH)),
                )
        conn.execute("COMMIT")
        return counts
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    reset = "--reset" in args
    args = [a for a in args if not a.startswith("--")]
    db_path = Path(args[0]) if args else REPO_ROOT / "data" / "latencyledger.db"
    if reset and db_path.exists():
        db_path.unlink()
        for suffix in ("-wal", "-shm"):
            p = db_path.with_name(db_path.name + suffix)
            if p.exists(): p.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    migrate(db_path)
    counts = seed(db_path)
    print(f"seed complete: {counts} -> {db_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
