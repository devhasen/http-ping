"""First-party event taxonomy writer + events table DDL (analytics-spec §1–§2).

No third-party analytics. Events follow {object}_{action} snake_case.
Properties are flat JSON; PII (email/url/key/raw IP) never stored (§8).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any

# 38-event catalogue (analytics-spec §1.1), grouped for review.
EVENTS: dict[str, str] = {
    "page_view": "Route change / initial load",
    "signup_started": "Click Sign up CTA",
    "signup_completed": "POST /api/auth/register -> 201",
    "signup_failed": "Register -> 4xx",
    "login_started": "Submit login form",
    "login_completed": "POST /api/auth/login -> 200",
    "login_failed": "Login -> 401/429",
    "logout_completed": "POST /api/auth/logout",
    "check_added": "POST /api/checks -> 201",
    "check_add_failed": "Check create -> 4xx/402",
    "check_edited": "PATCH /api/checks/{id} -> 200",
    "check_deleted": "DELETE /api/checks/{id} -> 200",
    "check_duplicated": "Duplicate action",
    "ping_now_run": "POST /api/checks/{id}/ping-now",
    "chart_viewed": "History chart rendered (>=2 points)",
    "chart_range_changed": "User switches 24h/7d/30d",
    "sample_ingested": "Worker/CI sample written (1% sampled)",
    "regression_alert_raised": "Detector fires (+20% rule)",
    "alert_viewed": "Alert row expanded",
    "alert_acknowledged": "User marks alert acked/useful",
    "alert_delivered": "Email/webhook/chat send attempted",
    "alert_delivery_failed": "Delivery after 3 attempts",
    "alert_channel_added": "POST /api/checks/{id}/alert-channels",
    "api_key_created": "POST /api/keys -> 201",
    "api_key_revoked": "DELETE /api/keys/{id}",
    "gate_evaluated": "POST /api/v1/checks/{id}/gate",
    "gate_failed": "Gate -> 422",
    "public_report_toggled": "Toggle is_public",
    "public_report_viewed": "Anonymous GET /r/{slug}",
    "export_requested": "GET /api/checks/{id}/export",
    "project_created": "Projects CRUD (P1)",
    "project_deleted": "Projects CRUD (P1)",
    "status_page_viewed": "GET /s/{slug}",
    "plan_upgraded": "Admin/manual or Stripe upgrade (P1)",
    "plan_downgraded": "Downgrade / cancel",
    "onboarding_step_completed": "Wizard step done",
    "experiment_assigned": "User enters experiment",
    "experiment_exposed": "User sees treatment UI",
    "feature_disabled": "Flag off / power user opts out",
}

EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS events (
  event_id      TEXT PRIMARY KEY,
  event_name    TEXT NOT NULL,
  user_id       TEXT,
  anonymous_id  TEXT,
  session_id    TEXT,
  source        TEXT DEFAULT 'web',
  event_ts      INTEGER NOT NULL,   -- ms epoch, client
  received_ts   INTEGER NOT NULL,   -- ms epoch, server
  properties    TEXT NOT NULL DEFAULT '{}'  -- JSON, flat
);
CREATE INDEX IF NOT EXISTS idx_events_name_ts ON events(event_name, event_ts);
CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_events_anon_ts ON events(anonymous_id, event_ts);
"""

# Property keys rejected at ingest (analytics-spec §8).
PII_KEYS = {"email", "password", "api_key", "token", "secret", "target", "raw_ip", "url"}


def hash_value(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:16]


def tracked_event(event_name: str, properties: dict[str, Any] | None = None, *,
                  user_id: str | None = None, anonymous_id: str | None = None,
                  session_id: str | None = None, source: str = "web",
                  event_ts: int | None = None, sdk_version: str = "0.1.0", app_version: str = "0.1.0") -> dict:
    """Build a validated event envelope. Raises ValueError on unknown name / PII keys."""
    if event_name not in EVENTS:
        raise ValueError(f"unknown event: {event_name}")
    props = dict(properties or {})
    bad = PII_KEYS & {k.lower() for k in props}
    if bad:
        raise ValueError(f"PII keys not allowed in properties: {sorted(bad)}; hash them first")
    if not all(isinstance(v, (str, int, float, bool)) or v is None for v in props.values()):
        raise ValueError("properties must be flat scalars (no nested objects/arrays except allowlisted fields)")
    now_ms = int(time.time() * 1000)
    return {
        "event_id": str(uuid.uuid4()),
        "event_name": event_name,
        "user_id": user_id,
        "anonymous_id": anonymous_id,
        "session_id": session_id,
        "source": source,
        "event_ts": event_ts if event_ts is not None else now_ms,
        "received_ts": now_ms,
        "properties": props,
        "sdk_version": sdk_version,
        "app_version": app_version,
    }


def write_event(conn: sqlite3.Connection, event_name: str, properties: dict | None = None, **kw) -> dict:
    ev = tracked_event(event_name, properties, **kw)
    conn.execute(
        "INSERT INTO events (event_id, event_name, user_id, anonymous_id, session_id, source, event_ts, received_ts, properties)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ev["event_id"], ev["event_name"], ev["user_id"], ev["anonymous_id"], ev["session_id"],
         ev["source"], ev["event_ts"], ev["received_ts"], json.dumps(ev["properties"])),
    )
    return ev


def ensure_events_table(conn: sqlite3.Connection) -> None:
    conn.executescript(EVENTS_DDL)
