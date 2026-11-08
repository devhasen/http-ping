# http-ping — Infrastructure Spec

> **Status:** SPEC ONLY (desk-12, SRE/Infra lead). No code, no infra changes in this document.
> **Date:** 2026-11-08
> **Repo:** `devhasen/http-ping` (`main`)
> **Sources researched:** `README.md`, `package.json`, `tsconfig.json`, `src/index.ts`
> **Upstream dependency:** `docs/product-spec.md` (Product Manager, desk-1) — **did not exist at spec time** (checked after a ~15s wait + `git pull origin main`; `docs/` was empty). Where product behaviour is unstated, this spec makes explicit, conservative assumptions marked `[ASSUMPTION]` below; if the product spec contradicts them, the product spec wins and this document needs a revision.
> **Hard constraint:** No paid infra SaaS required. Everything must run on a ~$6/mo single VPS or locally.

## 0. Current state (as-found)

| Item | Value |
|---|---|
| Project | `http-ping` v1.0.0 — "Measure HTTP request latency" |
| Runtime | Node.js (TypeScript compiled to CommonJS, `target: ES2020`, `outDir: dist`) |
| Bin | `httpping` → `dist/index.js` |
| Scripts | `build: tsc`, `start: node dist/index.js` |
| Dependencies | `typescript@^5.0.0` (dev), `@types/node@^20.0.0` (dev). **Zero runtime deps.** Uses global `fetch` (Node ≥18 required). |
| Current behaviour | CLI: `httpping <url> [count]` — sequential `fetch` + `res.text()` per iteration, prints per-request ms, then min/max/avg. |
| Data layer | **None.** No DB, no env vars, no config, no HTTP server today. |
| Infra | **None.** No Dockerfile, no compose file, no CI, no `/health`, no `/metrics`. |

### 0.1 Assumptions forced by the missing product spec

These drive the infra design and must be confirmed/overridden by `docs/product-spec.md`:

- **[A1 — SaaS shape]** http-ping becomes a hosted service (web UI + API) that runs HTTP latency checks against user-supplied URLs on demand and/or on a schedule, storing results (checks, users, API keys) in SQLite. Rationale: the brief asks for SQLite backup strategy and a docker-compose design; a pure CLI has neither. If the product spec instead specifies Postgres/Redis/object storage, §5–§6 must be rewritten.
- **[A2 — Single SQLite file]** One SQLite DB file (`/data/http-ping.db`) is the system of record. No distributed transactions; concurrent writers are serialised by SQLite's built-in locking (WAL mode). This is what makes the single-VPS design viable.
- **[A3 — Auth/secrets exist]** The service has at minimum: a session/API secret, OAuth client secret (if social login), and SMTP creds (if email). All supplied via env vars / secrets file — never baked into the image.
- **[A4 — Probe egress]** The service makes outbound HTTPS requests to arbitrary URLs. The host (§1) needs outbound internet and DNS; firewall rules must not block egress. SSRF guardrails (block private/loopback/link-local targets) are a product/security requirement, not an infra luxury — flagged here because the reverse proxy and firewall configs depend on it.

---

## 1. Environment topology — single VPS, three tiers

One physical host runs all three environments. Isolation is by **process + container + env + separate data volumes**, not by separate machines. This is the correct trade-off at $6/mo: simple to operate, cheap to rebuild, and honest about its limits (see §8 DR targets).

### 1.1 Host baseline

| Item | Spec |
|---|---|
| OS | Ubuntu 24.04 LTS (or Debian 12) x86_64, kernel 6.x |
| Sizing | 1 vCPU, 1 GB RAM, 20–25 GB disk (§7) |
| User | Non-root deploy user `deploy` (sudo only for `systemctl`, `docker`, `ufw`) |
| SSH | Key-only auth, `PasswordAuthentication no`, non-default port optional |
| Firewall | `ufw`: allow `22/tcp`, `80/tcp`, `443/tcp`; deny all else inbound; allow all outbound |
| Time | `chrony` / `systemd-timesyncd`, UTC everywhere |
| Swap | 1 GB swapfile (protects Node from OOM on a 1 GB box during builds) |

### 1.2 Processes and ports

| Component | Port(s) | Bound to | Notes |
|---|---|---|---|
| nginx (reverse proxy) | 80, 443 | `0.0.0.0` | Only public listener. TLS termination here. |
| App (Node) | 3000 | `127.0.0.1` only | Never exposed directly. Health/metrics on this port, internal-only. |
| Admin tools (§2) | 3001 (optional) | `127.0.0.1` only | Behind nginx location with basic-auth + IP allowlist, or `docker exec` only. |
| Node metrics exporter (optional) | 9100 | `127.0.0.1` only | If §4 Prometheus-node-exporter is used. |
| SSH | 22 | `0.0.0.0` | Key-only. |

> **Rule:** Anything not on 80/443/22 is localhost-only or firewall-denied. The app port must never be reachable from the internet — verify with `ss -tlnp` and an external `curl` in the deploy runbook (§9).

### 1.3 How the three environments map onto one host

| Environment | How it runs | Data | URL |
|---|---|---|---|
| **dev** (local) | `docker compose up` on the developer's laptop (Linux/macOS/Windows). App builds from source; hot or plain restart. | Bind-mounted `./data/` on laptop (throwaway). | `http://localhost:3000` (proxy bypassed; app direct) |
| **staging** | Compose project `staging` on the VPS, app on `127.0.0.1:3001`, own volume `staging-data`. Seeds / synthetic checks only. | `staging` SQLite volume. **Never** prod data. | `https://staging.http-ping.example.com` |
| **prod** | Compose project `prod` on the VPS, app on `127.0.0.1:3000`, volume `prod-data`. | `prod` SQLite volume + nightly backups (§5). | `https://http-ping.example.com` |

Staging and prod run side-by-side on the same box but as **separate compose projects** (`-p staging` / `-p prod`) with separate env files and volumes. If disk/RAM pressure ever bites, staging is the first thing to stop — it is not load-bearing.

### 1.4 Reverse proxy config sketches

**Option A — nginx (recommended default).** Already assumed available via `apt`; easiest to reason about.

```nginx
# /etc/nginx/sites-available/http-ping
upstream http_ping_prod  { server 127.0.0.1:3000; }
upstream http_ping_stage { server 127.0.0.1:3001; }

server {
    listen 80;
    server_name http-ping.example.com staging.http-ping.example.com;
    # ACME HTTP-01 challenge (certbot webroot)
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name http-ping.example.com;
    ssl_certificate     /etc/letsencrypt/live/http-ping.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/http-ping.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 1m;

    location / {
        proxy_pass http://http_ping_prod;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Trust-proxy: app reads X-Forwarded-Proto only from 127.0.0.1 (see §2)
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;   # probes can be slow; don't cut them off early
    }

    # Health is public (for uptime checkers); metrics is localhost-only.
    location /health  { access_log off; proxy_pass http://http_ping_prod; }
    location /metrics { return 404; }   # never proxied publicly; direct localhost access only
}

server {
    listen 443 ssl http2;
    server_name staging.http-ping.example.com;
    ssl_certificate     /etc/letsencrypt/live/staging.http-ping.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.http-ping.example.com/privkey.pem;

    location / {
        proxy_pass http://http_ping_stage;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Option B — Caddy (simpler, automatic HTTPS).** Use this if the solo operator prefers zero certbot babysitting; otherwise nginx above.

```caddyfile
# /etc/caddy/Caddyfile
http-ping.example.com {
    reverse_proxy 127.0.0.1:3000
    handle_path /metrics { abort }   # block public metrics
    header Strict-Transport-Security "max-age=31536000; includeSubDomains"
}

staging.http-ping.example.com {
    reverse_proxy 127.0.0.1:3001
}
```

Caddy terminates TLS and renews certs automatically (ACME). Pick **one** of nginx/Caddy per host — do not run both.

---

## 2. Docker design

### 2.1 Dockerfile — multi-stage, non-root, healthcheck

```dockerfile
# syntax=docker/dockerfile:1
# ---- Stage 1: build -------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
# Install deps first (cached until package manifests change).
COPY package.json package-lock.json ./
# --omit=dev in the runtime stage; here we need tsc only.
RUN npm ci --ignore-scripts
COPY tsconfig.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

# ---- Stage 2: runtime -----------------------------------------------------
FROM node:22-alpine AS runtime
ENV NODE_ENV=production
WORKDIR /app

# Non-root user — never run Node as root.
RUN addgroup -S app && adduser -S app -G app

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/package.json ./package.json

# Writable data dir for SQLite; contents mounted as a volume in compose.
RUN mkdir -p /data && chown -R app:app /data
USER app

EXPOSE 3000
# Healthcheck hits the internal /health endpoint (see §4.1).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "dist/index.js"]
```

Design notes:

- **Multi-stage:** build stage has `typescript` + `src/`; runtime stage contains only `node_modules` (prod), `dist/`, and `package.json`. Final image ≈ 130–160 MB (Node 22-alpine baseline dominates). No compiler, no source, no npm cache in the shipped image.
- **Non-root:** `USER app` (uid 1001-ish via `adduser -S`). `/data` is chowned so SQLite can create/write the DB. If the app needs to read-only the filesystem elsewhere, add `read_only: true` in compose (§2.2).
- **Healthcheck:** a dependency-free Node one-liner (no `curl`/`wget` in alpine by default) that fails the container if `/health` stops returning 2xx. Compose `depends_on: service_healthy` and restart policies key off this.
- **Pin the base image digest** in production (`node:22-alpine@sha256:...`) once the first image is built; bump deliberately, not accidentally.
- **Build context:** `.dockerignore` must exclude `node_modules/`, `dist/`, `data/`, `.git/`, `docs/`, `.agent-office/` — images must be reproducible from a clean checkout.

### 2.2 docker-compose design

`docker-compose.yml` — app plus optional admin tools. The app service is required; admin tools are behind a profile so a minimal prod deploy never starts them.

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: http-ping:prod
    container_name: http-ping-app
    restart: unless-stopped
    env_file:
      - .env.prod          # secrets; never committed (see §9.3)
    environment:
      NODE_ENV: production
      PORT: "3000"
      DATABASE_URL: "file:/data/http-ping.db"
      TRUST_PROXY: "127.0.0.1"   # only trust X-Forwarded-* from the proxy
    ports:
      - "127.0.0.1:3000:3000"    # localhost only — do not publish to 0.0.0.0
    volumes:
      - prod-data:/data
    read_only: true
    tmpfs:
      - /tmp
    deploy:
      resources:
        limits:
          cpus: "1.0"            # 1 vCPU host — leave headroom for nginx
          memory: 384M
        reservations:
          memory: 192M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"            # docker-level rotation; see §3.3
    healthcheck:
      test: ["CMD", "node", "-e",
             "fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  # ---- optional admin tooling (profile: tools) ----
  # SQLite shell for ad-hoc inspection. Never published on a port.
  sqlite-cli:
    image: alpine:3.20
    profiles: ["tools"]
    entrypoint: ["sh", "-c", "apk add --no-cache sqlite && sh"]
    stdin_open: true
    tty: true
    volumes:
      - prod-data:/data
    depends_on:
      app: { condition: service_healthy }

  # Prometheus scrape target (optional; see §4.3).
  node-exporter:
    image: prom/node-exporter:latest
    profiles: ["tools"]
    container_name: http-ping-node-exporter
    restart: unless-stopped
    ports:
      - "127.0.0.1:9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/host:ro

volumes:
  prod-data:
    name: http-ping-prod-data
```

Compose project naming: `docker compose -p staging -f docker-compose.yml -f docker-compose.staging.yml up -d` for staging (override `container_name`, `ports`, `.env` file, volume name). Local dev: `docker compose up` with a `.env` default and the `dev-data` bind mount.

| Service | Required? | Image | Port | Steady-state RAM |
|---|---|---|---|---|
| `app` | Yes | local build `http-ping:prod` | `127.0.0.1:3000` | ~120–200 MB |
| `sqlite-cli` | No (profile `tools`) | `alpine:3.20` | — (exec only) | ~0 (on exec) |
| `node-exporter` | No (profile `tools`) | `prom/node-exporter:latest` | `127.0.0.1:9100` | ~20 MB |

Secrets live in `.env.prod` (mode `600`, owned by `deploy`, never committed). Compose only references the file path — no secret values in the YAML.

---

## 3. Service management

### 3.1 Compose restart policies (primary)

The app is managed by Docker Compose restart policies, not by systemd directly. This is deliberate: one mechanism for local dev, staging, and prod — same command everywhere.

| Policy | Value | Effect |
|---|---|---|
| `restart: unless-stopped` | `app`, `node-exporter` | Container restarts on crash and on host reboot; stays stopped if explicitly stopped. |
| Healthcheck-gated `depends_on` | `service_healthy` | Dependents wait until the app is actually healthy (not just running). |
| `deploy.resources.limits` | 1.0 CPU / 384 MB | Prevents a runaway probe loop from starving nginx/SSH. Kernel OOM kills the container, not the host. |

Docker itself: `systemctl enable docker` so the daemon starts at boot; containers with `unless-stopped` come back automatically.

### 3.2 systemd unit (oracle / fallback — when compose isn't used)

If a deployment ever runs the app without compose (e.g. native Node under `systemd`), use this unit as the contract. It is the **fallback**, not the default — compose (§3.1) is how staging/prod actually run.

```ini
# /etc/systemd/system/http-ping.service
[Unit]
Description=http-ping SaaS app
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/http-ping
EnvironmentFile=/etc/http-ping/http-ping.env
ExecStart=/usr/bin/node dist/index.js
Restart=on-failure
RestartSec=3
# Backstop: if it flaps, systemd gives up after 5 starts in 60s
StartLimitIntervalSec=60
StartLimitBurst=5
# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/data
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
```

`systemctl enable --now http-ping` on install; `systemctl status http-ping` / `journalctl -u http-ping -f` for ops. The `LimitNOFILE` matters: probing loops open many sockets; the default 1024 soft limit is too low for a latency-probe service.

### 3.3 Log rotation

Two layers, both mandatory on a 20 GB disk:

1. **Docker container logs** — capped by the `max-size`/`max-file` options in §2.2 (10 MB × 3). Prevents the classic "container logs ate the disk" outage.
2. **System logs (journald)** — cap the journal so it can't grow unbounded:

```ini
# /etc/systemd/journald.conf.d/http-ping.conf
[Journal]
SystemMaxUse=500M
SystemKeepFree=1G
Compress=yes
```

3. **App-level logs** — the app writes structured (JSON) logs to stdout; anything the app writes to files under `/data` (e.g. probe traces) must be rotated by the same policy: daily, keep 7, compress. Never let the app write unbounded files next to the SQLite DB.

---

## 4. Monitoring

All monitoring runs **on the same VPS** (no external SaaS). External checks are free-tier uptime pingers only (§4.4).

### 4.1 `/health` — liveness + readiness

| Property | Value |
|---|---|
| Method / path | `GET /health` |
| Auth | **None** (public, proxied) — must be cheap and safe to hammer |
| Response | `200 {"status":"ok","version":"<git-sha>","uptime_s":<int>}` or `503 {"status":"degraded",...}` |
| Checks | Process alive + event loop responsive + SQLite reachable (`SELECT 1`) + one probe worker thread/pool not wedged |
| Budget | Must return in < 200 ms p95. No outbound fetch on this path (a slow probe of a third-party site must never flip `/health` red). |
| Return codes | `200` = ok; `503` = degraded (DB unreachable or worker pool wedged). Any non-2xx fails Docker healthcheck, uptime checkers, and nginx `proxy_pass` health logic. |

**Liveness vs readiness split (recommended):**

- `GET /health` — liveness. Process + event loop + DB ping. Fails the container healthcheck.
- `GET /ready` — readiness. Also checks that the probe worker pool has capacity and the last successful backup is < 26 h old. Used by the deploy health gate (§9.1), not by the Docker healthcheck.

### 4.2 `/metrics` — Prometheus exposition

| Property | Value |
|---|---|
| Method / path | `GET /metrics` |
| Format | Prometheus text exposition (`text/plain; version=0.0.4`) |
| Access | **Localhost-only** (nginx returns 404 publicly; §1.4). Scrape at 15–30 s intervals from a local Prometheus, or from a user's existing Prometheus if they have one. |
| Cardinality rule | **Never** put target URL, user ID, or raw hostname in a label — cardinality explosion. Use buckets/coarse groups. |

Minimum metric set:

```
# HELP http_probes_total Total latency probes executed.
# TYPE http_probes_total counter
http_probes_total{result="ok"} 12345
http_probes_total{result="error"} 67
http_probes_total{result="timeout"} 12

# HELP http_probe_duration_milliseconds Probe latency.
# TYPE http_probe_duration_milliseconds histogram
http_probe_duration_milliseconds_bucket{le="50"} 100
http_probe_duration_milliseconds_bucket{le="200"} 9000
http_probe_duration_milliseconds_bucket{le="1000"} 12000
http_probe_duration_milliseconds_bucket{le="+Inf"} 12345

# HELP http_requests_total HTTP requests by route family (no raw paths).
http_requests_total{route="api"} 5000

# HELP process_resident_memory_bytes Resident memory.
# HELP sqlite_db_size_bytes Size of the SQLite database file.
# HELP sqlite_wal_size_bytes Size of the WAL file (growth = writer pressure).
# HELP last_backup_age_seconds Seconds since last successful backup.
```

If the product spec defines a job queue (§6), add `probe_queue_depth` and `probe_queue_oldest_age_seconds` gauges.

### 4.3 Log shipping (no SaaS)

- Primary: Docker `json-file` logging driver with rotation (§3.3) + `journalctl` for anything outside containers.
- Forwarding (optional, free): `journald` → `systemd-cat`-free; if the operator later wants off-box logs, `vector` or `promtail` in a `tools` profile shipping to a self-hosted Loki, or `rsyslog` to a second box. **Not required at launch** — the constraint says no paid SaaS, and on-disk rotation plus alerting (§4.5) is sufficient for a single-host service.
- Log format: JSON to stdout, one object per line, with `ts`, `level`, `msg`, plus `req_id` correlation. Never log raw target URLs at `info` level (cardinality + PII risk); log coarse probe class instead.

### 4.4 Uptime checks (external, free tier)

- **Primary:** a free uptime pinger (e.g. UptimeRobot, Better Stack free, or a cron `curl` from a second host) hitting the public `https://http-ping.example.com/health` every 5 min, alerting on 2 consecutive failures.
- **Secondary (cheap, runs on the same box):** a cron that curls `/health` locally and writes a heartbeat file; if the heartbeat is stale, send mail via local `sendmail`/MSMTP. This catches Docker/nginx failures that an external pinger also catches, but also catches "the box is fine, the app is wedged" without relying on third-party availability.
- **TLS check:** the external pinger must verify the cert is valid and > 14 days from expiry; alert on failure.

### 4.5 Alert rules

If a local Prometheus + Alertmanager are run (both in `tools` profile, localhost-only), the following rules are mandatory at launch. If only free external pingers are used, rules 1–3 must still be approximated by the heartbeat cron.

| # | Alert | Condition | Severity | Action |
|---|---|---|---|---|
| 1 | `HttpPingDown` | `up == 0` for 2 min (or 2 failed pings) | page/email now | SSH in, `docker compose ps`, restart app (§9.2) |
| 2 | `HighErrorRate` | probe error rate > 20% over 5 min | email | Check egress/DNS; probe errors often = target site down, not us |
| 3 | `BackupStale` | `last_backup_age_seconds > 26h` | email | Run backup manually; investigate cron (§5) |
| 4 | `DiskPressure` | node-exporter: disk > 80% full | email | Rotate/clean logs (§9.4); prune old backups |
| 5 | `MemoryPressure` | container RSS > 90% of 384 MB limit or host swap > 50% | email | Restart app; investigate probe fan-out |
| 6a | `CertExpiringSoon` | TLS cert < 14 days to expiry | email | Renew cert (certbot/Caddy) |
| 6b | `CertExpiringCritical` | TLS cert < 3 days to expiry | page/email now | Emergency renewal |
| 7 | `HighProbeLatency` | p95 probe latency > 10 s over 15 min | email | Check target sites / host egress bandwidth |

All alerts go to at least one human-reachable channel (email to the operator, or a webhook to a chat channel the operator already uses). An alert with no recipient is not an alert.

---

## 5. Backup strategy — SQLite

### 5.1 What is backed up

- **Primary:** the SQLite database file(s) in the `prod-data` volume: `http-ping.db` + `-wal` + `-shm` (WAL mode). Back up the **logical** database (via the SQLite backup API / `.backup`), not a raw file copy — a raw copy of a live WAL database can be corrupt or inconsistent.
- **Secondary:** config — `.env.prod` (encrypted), `docker-compose.yml`, nginx/Caddy config, `Dockerfile`. These are in git except `.env.prod`; the env file is backed up encrypted (§5.2).
- **Not backed up:** container images (rebuildable), `node_modules` (reinstallable), staging data (ephemeral by definition).

### 5.2 Backup method

**Manual / on-demand:**

```bash
# Live, consistent logical backup without stopping the app.
docker run --rm -v http-ping-prod-data:/data -v "$PWD/backups:/backups" alpine:3.20 \
  sh -c "apk add --no-cache sqlite && sqlite3 /data/http-ping.db \".backup '/backups/http-ping-\$(date -u +%F_%H%M).db'\""
```

Or, from inside the running app container (same thing, no extra pull):

```bash
docker compose exec -T app sqlite3 /data/http-ping.db ".backup '/data/backups/http-ping-$(date -u +%F_%H%M).db'"
```

**Scheduled (cron):** nightly at 02:00 UTC, plus 7-day retention, compressed, with off-box copy if the operator has anywhere to put it (a second VPS, S3-compatible bucket, or `rsync` to a laptop — the constraint bans *paid* SaaS, not *off-box copies*).

```cron
# /etc/cron.d/http-ping-backup  (owned by root, 0644)
0 2 * * * root /usr/local/bin/http-ping-backup.sh >> /var/log/http-ping-backup.log 2>&1
```

```bash
#!/usr/bin/env bash
# /usr/local/bin/http-ping-backup.sh
set -euo pipefail
TS=$(date -u +%F_%H%M%S)
BACKUP_DIR=/var/backups/http-ping
mkdir -p "$BACKUP_DIR"
docker compose -p prod exec -T app \
  sqlite3 /data/http-ping.db ".backup '/data/backups/http-ping-$TS.db'"
docker run --rm -v http-ping-prod-data:/data -v "$BACKUP_DIR:/backups" alpine:3.20 \
  sh -c "cd /data/backups && tar -czf - http-ping-$TS.db | gzip -9 > /backups/http-ping-$TS.db.gz && rm http-ping-$TS.db"
# Optional off-box copy (uncomment + fill in):
# rsync -az "$BACKUP_DIR/http-ping-$TS.db.gz" backup-host:/backups/http-ping/

# Prune: keep last 7 nightly backups; keep one per month for 12 months.
find "$BACKUP_DIR" -name 'http-ping-*.db.gz' -mtime +7 -delete
# (Monthly archive copy: copy the 1st-of-month backup to $BACKUP_DIR/monthly/ before pruning.)
```

**Backup integrity verification** (after each run, fail loudly if it fails):

- `sqlite3 "$BACKUP" "PRAGMA integrity_check;"` must return `ok`.
- A backup that has never been restore-tested is a hope, not a backup (§5.3).

### 5.3 Restore drills

| Drill | Frequency | Procedure | Pass criteria |
|---|---|---|---|
| Restore to staging | **Monthly** | Restore latest nightly backup into the staging volume (`docker compose -p staging` stop app → copy `.db.gz` in → restore → start). Run `/health` + a smoke probe. | App boots on restored DB, `/health` 200, smoke check returns data. |
| Restore to local | Quarterly | Same, on a laptop (`docker compose up` with the restored DB bind-mounted). | App runs offline; dev can debug against prod-shaped data. |
| Full DR restore (§8) | Semi-annual | Provision a fresh VPS from the §7 spec, restore the latest backup + config, bring up the app. | Meets the RTO target in §8. |

Record each drill in a short log (date, backup used, elapsed time, result). A drill that has never been run on a fresh host is **not** validated — mark it as such.

### 5.4 Retention summary

| Tier | Retention | Location |
|---|---|---|
| Nightly | 7 days | VPS `/var/backups/http-ping/` |
| Monthly (1st) | 12 months | VPS + off-box copy if available |
| Pre-deploy | Kept until the next successful deploy + 24 h | VPS `/var/backups/http-ping/predeploy/` |

---

## 6. Scaling path — single host to multi-instance

Current design (single host, single SQLite) is correct for launch. This section names, in advance, what breaks and what to change when it does — so a future operator doesn't have to rediscover it under load.

### 6.1 What breaks first (in order)

| Order | Bottleneck | Symptom | Mitigation before re-architecture |
|---|---|---|---|
| 1 | Single SQLite writer | `SQLITE_BUSY` / WAL growth; write latency spikes | Enable WAL mode + `busy_timeout=5000`; batch writes; reduce probe-result write frequency (aggregate in memory, flush every N s) |
| 2 | Single Node process, 1 vCPU | Event-loop saturation under concurrent probes; p95 probe latency climbs | Raise `cpus` limit; run 2 Node workers with `SO_REUSEPORT` behind nginx upstream; move probes to a worker pool / queue |
| 3 | Host RAM (1 GB) | OOM kills; swap pressure | Raise container memory limit; move to a 2 GB VPS before anything else |
| 4 | Host disk I/O | SQLite fsync stalls; WAL checkpoint slow | Move DB to faster SSD; increase `cache_size`; consider `synchronous=NORMAL` (WAL-safe durability trade-off, document it) |
| 5 | Egress bandwidth / port exhaustion | Probe failures; `EMFILE` | Raise `LimitNOFILE`; add connection pooling to targets; rate-limit fan-out |

### 6.2 What to change at each step

| Step | Change | Notes |
|---|---|---|
| **A → B** | Add a job queue for probes (even an in-process queue + separate worker container). Decouple "API receives request" from "probe executes". | Queue in SQLite (a table) is enough at this scale; no Redis yet. |
| **B → C** | Move SQLite → Postgres. The DB layer must be abstracted behind a repository interface from day one so this is a driver swap, not a rewrite. | Postgres on a second VPS or a managed free-tier, whichever the operator prefers. Backups switch from §5 to `pg_dump` + WAL archiving. |
| **C → D** | Horizontal app instances behind the reverse proxy (nginx upstream with 2+ backends). App must be stateless: sessions in the DB/Redis, no in-process state, no sticky sessions. | The probe queue (§6.2 B) becomes the coordination point; workers scale independently of the API. |
| **D → E** | Separate DB host from app hosts; add a real queue (Redis/Postgres-backed). | Only when probe volume justifies it. |

### 6.3 Architectural rules to hold from day one

1. **Stateless app:** no in-memory sessions, no in-process caches that matter, no "the instance that created it must serve it" logic. This is what makes step D trivial.
2. **DB access behind a repository interface:** SQLite today, Postgres later — the app code never issues raw SQL outside the repository.
3. **Probes are jobs, not inline requests:** a probe always goes through the queue/worker path, even if today the queue is in-process. This is the seam that later becomes a real distributed queue.
4. **No local filesystem state besides the DB:** uploads/cache go to the DB or object storage, never to ephemeral container disk. (The only local file is the SQLite DB, which is the system of record in the single-host design.)

---

## 7. Cost estimate — minimal VPS

| Component | Minimal spec | Monthly ballpark (2026, major providers) |
|---|---|---|
| VPS | 1 vCPU, 1 GB RAM, 20–25 GB SSD, 1 TB transfer | **~$5–7/mo** (Hetzner CX22 ≈ €4.5, DigitalOcean Basic ≈ $6, Vultr ≈ $6, Linode/Akamai ≈ $5) |
| TLS cert | Let's Encrypt | **$0** (auto-renew via certbot/Caddy) |
| Backups | On-disk + optional off-box to existing storage | **$0** if off-box is a second box the operator already owns; otherwise +$1–2/mo for object storage |
| Uptime pinger | Free tier (UptimeRobot/Better Stack) or cron | **$0** |
| Monitoring | Local Prometheus/node-exporter (§4) | **$0** (same VPS) |
| Domain | `.com` / `.io` | ~$10–15/**year** (amortised ≈ $1/mo) |
| **Total** | | **~$6–8/mo** at launch |

Headroom path (no re-architecture needed): 2 GB RAM VPS ≈ $10–12/mo; 4 GB ≈ $20–24/mo; second VPS for off-box backups/monitoring ≈ +$5–6/mo. The $6/mo target is the *floor*, not a ceiling — budget one tier up when the first alert in §4.5 fires regularly.

> **Local-only cost:** $0. `docker compose up` on a laptop runs the full stack (app + optional tools) with no VPS at all. This is the dev environment and the restore-drill environment (§5.3).

---

## 8. Disaster recovery & RPO / RTO targets

| Scenario | Description | Recovery action | Target RTO | Target RPO |
|---|---|---|---|---|
| **Container crash** | App container dies; Docker restarts it | Automatic (`restart: unless-stopped`) | < 1 min | 0 (in-flight probe may be lost) |
| **Host reboot** | Kernel update / provider maintenance | Automatic (Docker + containers resume) | < 5 min | 0 |
| **Single-host failure** | VPS dies / provider outage | Provision new VPS (§7 spec), restore latest backup (§5), re-point DNS | **≤ 4 h** | **≤ 24 h** (last nightly backup) |
| **Data corruption** | SQLite file corrupt | Restore latest verified backup (§5.2 integrity check) | ≤ 4 h | ≤ 24 h |
| **Compromised host** | SSH key / secret leak | Wipe host, rotate all secrets (§9.3), restore from backup on fresh host, audit access logs | ≤ 8 h | ≤ 24 h |
| **Accidental data loss** | Bad migration / `DELETE` without `WHERE` | Restore latest backup to staging first, diff, merge or roll forward | ≤ 4 h | ≤ 24 h |

**Adopted targets (launch):**

| Target | Value |
|---|---|
| **RTO** (max acceptable downtime) | **4 hours** (single-host failure); **< 5 min** for container/host-restart failures |
| **RPO** (max acceptable data loss) | **24 hours** (nightly backup); 0 for in-flight requests on restart failures |

These are deliberately honest for a single-VPS service: 24 h RPO is what nightly backups give you, and 4 h RTO is what "provision a fresh box + restore" costs a solo operator. If the product spec needs tighter targets (e.g. RPO ≤ 1 h), §5 must move to more frequent backups (hourly WAL shipping) and §6 step C (Postgres) becomes a launch requirement, not a scaling step. State the higher target explicitly; don't quietly promise it.

**DR runbook summary:**

1. Provision fresh VPS from §7 spec (1 vCPU, 1 GB RAM, Ubuntu 24.04, SSH key-only, `ufw` 22/80/443).
2. Install Docker + Compose, nginx/Caddy (§1).
3. Clone repo; `docker compose -p prod pull`-equivalent (rebuild from `Dockerfile`).
4. Restore latest backup from `/var/backups/http-ping/` (or off-box copy) into the `prod-data` volume (§5.3).
5. Restore `.env.prod` (encrypted backup) — **rotate secrets first** if the old host is untrusted (§9.3).
6. `docker compose -p prod up -d`; verify `/health` 200 and a smoke probe.
7. Re-point DNS (or confirm the new host has the old IP) for the prod hostname.
8. Run a restore drill log entry (§5.3).

---

## 9. Runbooks

### 9.1 Deploy

```bash
# 0. Pull latest main and read the changelog / release notes.
git pull origin main

# 1. Pre-deploy backup (non-negotiable — see §5.4).
/usr/local/bin/http-ping-backup.sh
cp /var/backups/http-ping/http-ping-*.db.gz /var/backups/http-ping/predeploy/

# 2. Rebuild and roll the app container (zero-downtime where possible).
docker compose -p prod build app
docker compose -p prod up -d --no-deps app

# 3. Health gate — do not proceed on failure.
curl -fsS http://127.0.0.1:3000/health && echo "  <- /health OK"
curl -fsS http://127.0.0.1:3000/ready  && echo "  <- /ready OK"

# 4. Smoke test through the public proxy.
curl -fsS https://http-ping.example.com/health

# 5. Watch logs for 5 minutes.
docker compose -p prod logs -f app
```

Deploy cadence: manual `git pull` + rebuild on the VPS is acceptable at launch. If a CI is added later, it must run the same steps (backup → build → up → health gate → smoke) — automation doesn't change the runbook, it just triggers it.

### 9.2 Rollback

```bash
# If the deploy health gate (§9.1 step 3) fails, or smoke test fails:

# 1. Revert to the previous image. Keep the previous image tagged — never
#    overwrite :prod in place without a fallback tag.
docker compose -p prod up -d --no-deps http-ping:previous   # previous good image

# 2. If a migration ran and broke the schema, restore the pre-deploy backup:
docker compose -p prod stop app
# restore /var/backups/http-ping/predeploy/<latest>.db.gz into prod-data (§5.3)
docker compose -p prod start app

# 3. Verify /health and /ready, then investigate. Never retry a failed
#    migration forward without understanding why it failed.
```

**Image tagging rule:** every deploy tags the new image with the git SHA (`http-ping:<sha>`) and keeps `http-ping:previous` pointing at the last known-good image. Rollback is a tag swap, not a rebuild.

### 9.3 Rotate secrets

| Secret | Where it lives | Rotation procedure | Cadence |
|---|---|---|---|
| `SESSION_SECRET` / API signing key | `.env.prod` | Generate new value → update `.env.prod` → `docker compose -p prod up -d app` → old sessions invalidated (expected) | Every 90 days, and immediately on any leak suspicion |
| OAuth client secret | `.env.prod` + IdP dashboard | Create new secret in IdP → update `.env.prod` → restart → verify login → delete old secret in IdP | Every 90 days / on leak |
| SMTP / email creds | `.env.prod` | Same pattern as OAuth | Every 90 days / on leak |
| SSH host keys / deploy user key | `~/.ssh/authorized_keys` on VPS | Add new key → verify SSH works → remove old key → `systemctl restart ssh` | On personnel change; every 180 days |
| TLS private key | Let's Encrypt / Caddy | Automatic renewal; manual force-renew: `certbot renew --force-renewal` or Caddy reload | Automatic |
| Backup encryption key (if off-box backups are encrypted) | Operator's password manager | Re-encrypt new backups with new key; keep old key until old backups age out | Every 180 days |

**Procedure (generic):** generate → write to `.env.prod` (mode `600`) → `docker compose -p prod up -d app` → verify `/health` + affected feature (login, email, API) → update the off-box encrypted copy of `.env.prod`. Rotation that breaks the app is worse than no rotation — always verify before declaring done.

### 9.4 Rotate / clean logs

```bash
# Docker container logs are capped by §2.2 (10 MB x 3) — automatic.
# To force-rotate the journal:
sudo journalctl --rotate --vacuum-size=500M

# To prune old app log files (if the app writes any — it shouldn't, §3.3):
find /data/logs -type f -name '*.log' -mtime +7 -delete

# If disk pressure (alert §4.5 #4) fires:
df -h /            # what's full?
du -sh /var/log/* /var/backups/http-ping/* /var/lib/docker/* 2>/dev/null | sort -h
docker system prune -af --volumes   # careful: removes unused images/volumes — backup first (§5)
```

**Normal cadence:** logs rotate automatically (Docker cap + journald cap). Manual intervention only on disk-pressure alert or quarterly housekeeping.

---

## Appendix A — Compose services summary (for the report)

| Service | In `docker-compose.yml` | Required | Purpose |
|---|---|---|---|
| `app` | Yes | **Yes** | The http-ping Node service (port 3000, localhost-only) |
| `sqlite-cli` | Yes (profile `tools`) | No | Ad-hoc SQLite inspection via `docker compose run --rm sqlite-cli` |
| `node-exporter` | Yes (profile `tools`) | No | Host metrics for §4.5 alert rules |

## Appendix B — RPO / RTO targets (for the report)

| Target | Value |
|---|---|
| **RPO** | **24 hours** (nightly SQLite backup §5.2); 0 for container-restart failures |
| **RTO** | **4 hours** (single-host failure, §8); **< 5 min** for container/host-restart failures |

---

*End of infra-spec. No code or infra changes made in this document — SPEC ONLY, per desk-12 brief.*
*Next revision trigger: publication of `docs/product-spec.md` — assumptions [A1]–[A4] in §0.1 must be confirmed or the affected sections (§2, §5, §6, §8) revised.*
