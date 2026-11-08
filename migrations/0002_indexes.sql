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
