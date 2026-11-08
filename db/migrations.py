"""Idempotent SQLite migration runner (stdlib only).

Usage: python -m db.migrations [path/to.db] [--migrations-dir DIR]
Env:   HTTPPING_DB / LATENCYLEDGER_DB override the default path.

Boot order (per docs/db-spec.md §5): open DB, PRAGMA journal_mode=WAL /
foreign_keys=ON / busy_timeout / synchronous=NORMAL, bootstrap
schema_migrations, apply pending migrations in filename order each in its
own transaction (schema_migrations row inserted in the SAME transaction),
then PRAGMA foreign_key_check + integrity_check. Checksum mismatch on an
already-applied version is a hard failure.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MIGRATIONS_DIR = REPO_ROOT / "migrations"
SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT NOT NULL PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    checksum    TEXT NOT NULL
);
"""

def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # auto_vacuum is only honoured at CREATE time; set before any table exists
    conn.executescript(
        "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;"
        " PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;"
        " PRAGMA temp_store=MEMORY; PRAGMA auto_vacuum=INCREMENTAL;"
    )
    return conn

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def applied_versions(conn) -> dict[str, str]:
    conn.execute(SCHEMA_MIGRATIONS_DDL)
    return {r["version"]: r["checksum"]
            for r in conn.execute("SELECT version, checksum FROM schema_migrations")}

def migrate(db_path: str | Path, migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> list[str]:
    conn = connect(db_path)
    try:
        applied = applied_versions(conn)
        files = sorted(migrations_dir.glob("*.sql"))
        done: list[str] = []
        for f in files:
            version = f.stem  # e.g. 0001_init
            checksum = _sha256(f)
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(
                        f"migration {version} changed after being applied "
                        f"(expected {applied[version][:12]}…, got {checksum[:12]}…). "
                        "Migrations are immutable; add a new migration instead."
                    )
                continue
            _sql = f.read_text(encoding="utf-8")
            # PRAGMA journal_mode/synchronous are no-ops inside a transaction;
            # strip any leading PRAGMA lines from the migration body.
            sql = "\n".join(
                ln for ln in _sql.splitlines()
                if not ln.strip().upper().startswith("PRAGMA ")
            )
            # One transaction per migration; bookkeeping row in the same txn.
            # NB: executescript() implicitly commits any pending Python-level
            # txn, so BEGIN/COMMIT must be *inside* the script itself.
            insert = (
                "INSERT INTO schema_migrations (version, name, checksum) VALUES "
                f"('{version}', '{f.name}', '{checksum}');"
            )
            script = "BEGIN IMMEDIATE;\n" + sql + "\n" + insert + "\nCOMMIT;"
            try:
                conn.executescript(script)
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            done.append(version)
        # Post-run integrity gates (fail boot on violation).
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            raise RuntimeError(f"foreign_key_check violations: {fk[:5]}")
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise RuntimeError(f"integrity_check failed: {ok}")
        return done
    finally:
        conn.close()

def main(argv: list[str] | None = None) -> int:
    args = [a for a in (argv if argv is not None else sys.argv[1:]) if not a.startswith("--")]
    db_path = args[0] if args else None
    import os
    if db_path is None:
        db_path = os.environ.get("LATENCYLEDGER_DB") or os.environ.get("HTTPPING_DB") or "data/latencyledger.db"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    done = migrate(db_path)
    print(f"migrations applied: {done or 'none (already up to date)'} -> {db_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
