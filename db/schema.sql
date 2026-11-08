-- ============================================================
-- LatencyLedger 0001_init.sql — consolidated baseline (SQLite >=3.40)
-- Source: docs/data-spec.md (LatencyLedger) reconciled with docs/db-spec.md
-- conventions (UTC ISO-8601 TEXT timestamps, 0/1 booleans, INTEGER minor units,
-- secrets as hashes, FKs enforced per-connection, STRICT deliberately not used).
-- P0 scope: 9 core + 3 derived + 3 platform + 3 ops tables + projects (P1,
-- required by task) + schema_migrations = 20 tables.
-- NOTE: schema_migrations is bootstrapped by db/migrations.py (IF NOT EXISTS)
-- before any migration; it is reproduced here so db/schema.sql is standalone.
-- P1/P2 tables (alert_channels deliveries are P0 core per data-spec; status_pages,
-- page_components, chat_subscriptions, subscriptions/invoices/data_exports, regions,
-- teams/team_members) are NOT created until their feature ships, but their FK
-- targets (users, checks, projects) exist now so those migrations are additive.
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

-- ---------- migration bookkeeping ----------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT    NOT NULL PRIMARY KEY,   -- e.g. '0001_init'
    name        TEXT    NOT NULL,
    applied_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    checksum    TEXT    NOT NULL                -- sha256 of the migration file
);

-- ---------- reference: plan_limits (seeded at migration) ----------
CREATE TABLE plan_limits (
    plan               TEXT    NOT NULL PRIMARY KEY CHECK (plan IN ('free','pro','team')),
    max_checks         INTEGER NOT NULL CHECK (max_checks >= 0),
    min_interval_sec   INTEGER NOT NULL CHECK (min_interval_sec >= 10),
    history_days       INTEGER NOT NULL CHECK (history_days >= 1),
    max_channels       INTEGER NOT NULL CHECK (max_channels >= 0),
    ci_gates_per_day   INTEGER NOT NULL CHECK (ci_gates_per_day >= 0),
    created_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ---------- 1. users ----------
CREATE TABLE users (
    id                TEXT PRIMARY KEY CHECK (id LIKE 'usr\_%' ESCAPE '\'),
    email             TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (email LIKE '%@%' AND length(email) <= 254),
    email_verified_at TEXT,
    pw_hash           TEXT NOT NULL CHECK (length(pw_hash) > 0),
    plan              TEXT NOT NULL DEFAULT 'free' REFERENCES plan_limits(plan) ON DELETE RESTRICT,
    display_name      TEXT CHECK (display_name IS NULL OR length(display_name) <= 120),
    is_admin          INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0,1)),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    deleted_at        TEXT,
    CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);
CREATE INDEX idx_users_plan ON users (plan);
CREATE INDEX idx_users_created ON users (created_at);

-- ---------- 2. sessions ----------
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    expires_at  TEXT NOT NULL CHECK (expires_at > created_at),
    last_seen_at TEXT,
    ip_hash     TEXT CHECK (ip_hash IS NULL OR length(ip_hash) <= 128),
    user_agent  TEXT CHECK (user_agent IS NULL OR length(user_agent) <= 256)
);
CREATE INDEX idx_sessions_user_expires ON sessions (user_id, expires_at);

-- ---------- 3. api_keys ----------
CREATE TABLE api_keys (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label       TEXT CHECK (label IS NULL OR length(label) <= 64),
    prefix      TEXT NOT NULL CHECK (length(prefix) BETWEEN 1 AND 32),
    hash        TEXT NOT NULL UNIQUE CHECK (length(hash) = 64),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_used_at TEXT,
    revoked_at  TEXT,
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);
CREATE INDEX idx_api_keys_user ON api_keys (user_id);

-- ---------- 4. projects (P1 grouping, FK target for checks.project_id) ----------
CREATE TABLE projects (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL CHECK (length(trim(name)) > 0 AND length(name) <= 120),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_projects_user ON projects (user_id);

-- ---------- 5. checks ----------
CREATE TABLE checks (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id     TEXT REFERENCES projects(id) ON DELETE SET NULL,
    name           TEXT NOT NULL CHECK (length(trim(name)) > 0 AND length(name) <= 120),
    url            TEXT NOT NULL CHECK (length(url) <= 2048 AND (url LIKE 'http://%' OR url LIKE 'https://%')),
    interval_sec   INTEGER NOT NULL CHECK (interval_sec IN (60,300,900,3600)),
    threshold_pct  REAL NOT NULL DEFAULT 20 CHECK (threshold_pct > 0 AND threshold_pct <= 500),
    budget_ms      REAL CHECK (budget_ms IS NULL OR (budget_ms > 0 AND budget_ms < 60000)),
    is_public      INTEGER NOT NULL DEFAULT 0 CHECK (is_public IN (0,1)),
    slug           TEXT UNIQUE CHECK (slug IS NULL OR slug <> ''),
    last_checked_at TEXT,
    next_check_at  TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (is_public = 0 OR slug IS NOT NULL)
);
CREATE INDEX idx_checks_user ON checks (user_id);
CREATE INDEX idx_checks_next_check ON checks (next_check_at);
CREATE INDEX idx_checks_project ON checks (project_id) WHERE project_id IS NOT NULL;

-- ---------- 6. samples (fact table, append-only) ----------
CREATE TABLE samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id    TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    ts          TEXT NOT NULL,
    ms          REAL CHECK (ms IS NULL OR (ms >= 0 AND ms < 60000)),
    status      INTEGER CHECK (status IS NULL OR (status BETWEEN 100 AND 599)),
    size_bytes  INTEGER CHECK (size_bytes IS NULL OR (size_bytes >= 0 AND size_bytes <= 1048576)),
    error_kind  TEXT CHECK (error_kind IS NULL OR error_kind IN ('timeout','dns','connect','tls','other')),
    git_sha     TEXT CHECK (git_sha IS NULL OR (length(git_sha) BETWEEN 7 AND 40 AND git_sha NOT GLOB '*[^0-9a-f]*')),
    note        TEXT CHECK (note IS NULL OR length(note) <= 512),
    source      TEXT NOT NULL DEFAULT 'scheduler' CHECK (source IN ('scheduler','manual','ci')),
    client_sample_id TEXT CHECK (client_sample_id IS NULL OR length(client_sample_id) <= 64)
);
CREATE INDEX idx_samples_check_ts ON samples (check_id, ts);
CREATE INDEX idx_samples_ts ON samples (ts);
CREATE INDEX idx_samples_check_source_ts ON samples (check_id, source, ts);
-- dedupe key used by CI ingest (§5.2): unique only when client supplies an id
CREATE UNIQUE INDEX uq_samples_client_id ON samples (check_id, client_sample_id) WHERE client_sample_id IS NOT NULL;

-- ---------- 7. alerts ----------
CREATE TABLE alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id        TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL DEFAULT 'regression' CHECK (kind IN ('regression','down','recovery')),
    observed_p95    REAL NOT NULL CHECK (observed_p95 >= 0),
    baseline_p95    REAL NOT NULL CHECK (baseline_p95 > 0),
    delta_pct       REAL NOT NULL,
    cooldown_until  TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    acked_at        TEXT,
    acked_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    CHECK (acked_at IS NULL OR acked_at >= created_at)
);
CREATE INDEX idx_alerts_check_created ON alerts (check_id, created_at DESC);
CREATE INDEX idx_alerts_created ON alerts (created_at);

-- ---------- 8. alert_channels ----------
CREATE TABLE alert_channels (
    id         TEXT PRIMARY KEY,
    check_id   TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('email','webhook','chat')),
    target     TEXT NOT NULL CHECK (length(target) > 0 AND length(target) <= 2048),
    enabled    INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_alert_channels_check ON alert_channels (check_id);

-- ---------- 9. deliveries ----------
CREATE TABLE deliveries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id    INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    channel_id  TEXT NOT NULL REFERENCES alert_channels(id) ON DELETE CASCADE,
    status      INTEGER NOT NULL DEFAULT 0 CHECK (status = 0 OR (status BETWEEN 100 AND 599)),
    attempts    INTEGER NOT NULL DEFAULT 1 CHECK (attempts BETWEEN 1 AND 3),
    last_error  TEXT CHECK (last_error IS NULL OR length(last_error) <= 512),
    delivered_at TEXT,
    ts          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_deliveries_alert ON deliveries (alert_id);
CREATE INDEX idx_deliveries_channel_ts ON deliveries (channel_id, ts);

-- ---------- 10. sample_buckets (derived) ----------
CREATE TABLE sample_buckets (
    check_id     TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    bucket_start TEXT NOT NULL,
    bucket_sec   INTEGER NOT NULL CHECK (bucket_sec IN (300,3600)),
    n            INTEGER NOT NULL DEFAULT 0 CHECK (n >= 0),
    n_errors     INTEGER NOT NULL DEFAULT 0 CHECK (n_errors >= 0 AND n_errors <= n),
    avg_ms       REAL CHECK (avg_ms IS NULL OR avg_ms >= 0),
    p95_ms       REAL CHECK (p95_ms IS NULL OR p95_ms >= 0),
    min_ms       REAL CHECK (min_ms IS NULL OR min_ms >= 0),
    max_ms       REAL CHECK (max_ms IS NULL OR max_ms >= 0),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (check_id, bucket_sec, bucket_start)
);

-- ---------- 11. check_stats_daily (derived) ----------
CREATE TABLE check_stats_daily (
    check_id     TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    day          TEXT NOT NULL CHECK (day GLOB '????-??-??'),
    n            INTEGER NOT NULL DEFAULT 0 CHECK (n >= 0),
    n_errors     INTEGER NOT NULL DEFAULT 0 CHECK (n_errors >= 0 AND n_errors <= n),
    min_ms       REAL CHECK (min_ms IS NULL OR min_ms >= 0),
    p50_ms       REAL CHECK (p50_ms IS NULL OR p50_ms >= 0),
    p95_ms       REAL CHECK (p95_ms IS NULL OR p95_ms >= 0),
    p99_ms       REAL CHECK (p99_ms IS NULL OR p99_ms >= 0),
    max_ms       REAL CHECK (max_ms IS NULL OR max_ms >= 0),
    avg_ms       REAL CHECK (avg_ms IS NULL OR avg_ms >= 0),
    uptime_pct   REAL CHECK (uptime_pct IS NULL OR (uptime_pct BETWEEN 0 AND 100)),
    baseline_p95 REAL CHECK (baseline_p95 IS NULL OR baseline_p95 > 0),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (check_id, day)
);
CREATE INDEX idx_check_stats_day ON check_stats_daily (day);

-- ---------- 12. gate_evaluations (derived/audit) ----------
CREATE TABLE gate_evaluations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id     TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    budget_ms    REAL NOT NULL CHECK (budget_ms > 0 AND budget_ms < 60000),
    observed_p95 REAL NOT NULL CHECK (observed_p95 >= 0),
    window_n     INTEGER NOT NULL CHECK (window_n > 0),
    pass         INTEGER NOT NULL CHECK (pass IN (0,1)),
    git_sha      TEXT CHECK (git_sha IS NULL OR (length(git_sha) BETWEEN 7 AND 40 AND git_sha NOT GLOB '*[^0-9a-f]*')),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_gate_evals_check_created ON gate_evaluations (check_id, created_at DESC);

-- ---------- 13. events (platform) ----------
CREATE TABLE events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (length(kind) > 0 AND length(kind) <= 64),
    user_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    anon_id    TEXT,
    session_id TEXT,
    properties TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(properties) AND length(properties) <= 4096),
    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_events_kind_ts ON events (kind, ts);
CREATE INDEX idx_events_user_ts ON events (user_id, ts) WHERE user_id IS NOT NULL;

-- ---------- 14. event_properties (EAV sidecar) ----------
CREATE TABLE event_properties (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    key      TEXT NOT NULL CHECK (length(key) > 0 AND length(key) <= 64),
    value    TEXT,
    PRIMARY KEY (event_id, key)
);

-- ---------- 15. audit_log (platform, append-only) ----------
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    actor_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL CHECK (action IN ('login','logout','key.created','key.revoked','check.deleted','data.erased','plan.changed','export.created','check.created','check.updated','alert.acked','project.created')),
    target_kind TEXT,
    target_id   TEXT,
    detail      TEXT CHECK (detail IS NULL OR (json_valid(detail) AND length(detail) <= 4096)),
    ip_hash     TEXT CHECK (ip_hash IS NULL OR length(ip_hash) <= 128)
);
CREATE INDEX idx_audit_actor_ts ON audit_log (actor_id, ts) WHERE actor_id IS NOT NULL;

-- ---------- 16. scheduler_heartbeats (ops) ----------
CREATE TABLE scheduler_heartbeats (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_scheduled_check_id  TEXT REFERENCES checks(id) ON DELETE SET NULL,
    checks_due               INTEGER NOT NULL DEFAULT 0 CHECK (checks_due >= 0),
    samples_written          INTEGER NOT NULL DEFAULT 0 CHECK (samples_written >= 0),
    lag_ms                   REAL CHECK (lag_ms IS NULL OR lag_ms >= 0)
);
CREATE INDEX idx_heartbeats_ts ON scheduler_heartbeats (ts);

-- ---------- 17. ingest_counters (ops) ----------
CREATE TABLE ingest_counters (
    check_id   TEXT NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    day        TEXT NOT NULL CHECK (day GLOB '????-??-??'),
    ingested   INTEGER NOT NULL DEFAULT 0 CHECK (ingested >= 0),
    rejected   INTEGER NOT NULL DEFAULT 0 CHECK (rejected >= 0),
    gate_evals INTEGER NOT NULL DEFAULT 0 CHECK (gate_evals >= 0),
    PRIMARY KEY (check_id, day)
);

-- ---------- 18. erasure_requests (ops) ----------
CREATE TABLE erasure_requests (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','completed','rejected')),
    completed_at TEXT,
    method       TEXT NOT NULL DEFAULT 'self_serve' CHECK (method IN ('self_serve','email')),
    notes        TEXT CHECK (notes IS NULL OR length(notes) <= 2048),
    CHECK (completed_at IS NULL OR completed_at >= requested_at)
);
CREATE INDEX idx_erasure_user ON erasure_requests (user_id);
CREATE INDEX idx_erasure_status ON erasure_requests (status, requested_at);

-- ---------- reference data: plan_limits (idempotent data load) ----------
INSERT INTO plan_limits (plan, max_checks, min_interval_sec, history_days, max_channels, ci_gates_per_day) VALUES
  ('free', 3,   300, 7,   1,  10),
  ('pro',  25,  60,  90,  5,  1000),
  ('team', 100, 60,  365, 20, 5000)
ON CONFLICT(plan) DO NOTHING;
-- ============================================================
-- LatencyLedger 0002_indexes.sql — performance indexes (additive, idempotent)
-- Each index maps to a hot query in docs/data-spec.md §2/§4 or the retention
-- purge. CREATE INDEX IF NOT EXISTS so re-apply during testing is harmless.
-- samples(check_id,ts) itself lives in 0001 (hot path); 0002 adds the
-- secondary/covering/partial indexes that keep chart, scheduler, retention,
-- and reporting queries off sequential scans.
-- ============================================================
PRAGMA foreign_keys = ON;

-- samples: retention purge (global, by time) + per-check error drill-down
CREATE INDEX IF NOT EXISTS idx_samples_ts_check ON samples (ts, check_id);
CREATE INDEX IF NOT EXISTS idx_samples_errors ON samples (check_id, ts) WHERE error_kind IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_samples_git_sha ON samples (git_sha) WHERE git_sha IS NOT NULL;
-- covering index for the dashboard history query (avoids table lookup)
CREATE INDEX IF NOT EXISTS idx_samples_covering ON samples (check_id, ts, ms, status);

-- checks: scheduler due-scan already in 0001; add owner+recency and public slug
CREATE INDEX IF NOT EXISTS idx_checks_user_created ON checks (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checks_public ON checks (slug) WHERE is_public = 1 AND slug IS NOT NULL;

-- alerts: unacked inbox + cooldown sweep
CREATE INDEX IF NOT EXISTS idx_alerts_unacked ON alerts (created_at) WHERE acked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_cooldown ON alerts (check_id, cooldown_until) WHERE cooldown_until IS NOT NULL;

-- deliveries / gate_evaluations / events reporting sweeps
CREATE INDEX IF NOT EXISTS idx_deliveries_ts ON deliveries (ts);
CREATE INDEX IF NOT EXISTS idx_gate_evals_created ON gate_evaluations (created_at);
CREATE INDEX IF NOT EXISTS idx_gate_evals_pass ON gate_evaluations (check_id, created_at) WHERE pass = 0;
CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);
CREATE INDEX IF NOT EXISTS idx_events_anon ON events (anon_id, ts) WHERE anon_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log (ts);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action, ts);

-- rollup rebuild / backfill helpers
CREATE INDEX IF NOT EXISTS idx_sample_buckets_start ON sample_buckets (bucket_start);
CREATE INDEX IF NOT EXISTS idx_ingest_day ON ingest_counters (day);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at);
