# Operating runbook (Release 1)

Audience: the platform operator running Asseta with Docker Compose (development and initial deployment, prompt.md
§2). The production deployment at https://asseta.co.tz (host nginx, `compose.prod.yaml`, `scripts/*-live.sh`) is
described in [deployment-live.md](deployment-live.md); the procedures below apply to it with
`scripts/compose-live.sh` in place of `docker compose`. Related: [architecture](architecture.md), [security](security.md), [offline sync failure matrix](offline-sync.md#failure-matrix),
[GPS commissioning](gps-hardware.md), [model governance](model-governance.md), [release acceptance](release1-acceptance.md).

## 1. Services

| Service | Role | Health signal |
|---|---|---|
| `postgres` | PostgreSQL 18 + PostGIS 3.6 (`asseta`, `keycloak`, `mlflow` databases) | compose healthcheck `pg_isready` |
| `keycloak` | Identity + authorization (realm `asseta`, ADR-001) | compose healthcheck (`/health/ready` on 9000) |
| `kafka` | Domain events (KRaft, single broker) | `kafka-consumer-groups.sh` (§5.3) |
| `redis` | WebSocket fan-out, short-lived caches | readiness `redis` |
| `minio` | S3-compatible evidence store (bucket `asseta-evidence`) + MLflow artifacts (`asseta-mlflow`) | readiness `object_store` |
| `mlflow-db-init`, `migrate` | One-shot: MLflow DB role; `alembic upgrade head` + `asseta-bootstrap` (buckets, Traccar gateway key hash) | exit code 0 |
| `api` | FastAPI modular monolith (`/api/v1`) | `/api/v1/health/live`, `/api/v1/health/ready` |
| `outbox-relay` | `outbox_event` → Kafka | outbox backlog SQL (§5.2) |
| `timeline-worker` | Kafka `asseta.telemetry.position` → per-machine replay (geofences, states, alerts); group `asseta-timeline` | consumer lag |
| `connectivity-worker` | 60 s sweeps: LIVE/STALE/OFFLINE, stale alerts, monthly telemetry partitions | logs; `*_default` partitions empty |
| `intelligence-worker` | Risk signals (event-driven + sweep), hourly shadow inference, daily drift; group `asseta-intelligence` | consumer lag; inference audit |
| `notification-worker` | Rules → inbox + WebSocket + SMS/PUSH/EMAIL; group `asseta-notification` | consumer lag; `notification_delivery` |
| `notification-scheduler` | Reminders (idempotent per tenant-local day), membership mirror refresh | logs |
| `billing-scheduler` | Subscription renewals + entitlement evaluation (idempotent) | logs; invoices |
| `mlflow` | Experiment runs/artifacts (optional for the product path) | `http://127.0.0.1:5500` |
| `web` | nginx serving the console, proxies `/api/` and `/api/v1/ws` to `api`; request rate and size limits (§2) | `http://127.0.0.1:5173` |
| `traccar` (profile `telemetry`) | Device protocol gateway → `POST /api/v1/telemetry/traccar` | Traccar UI 8082 (local only) |
| `mailpit` | Dev-only SMTP sink | `http://127.0.0.1:8025` |

All workers are the same image (`asseta/api:dev`) with a different command and scale horizontally: the relay claims
with `FOR UPDATE SKIP LOCKED`; consumers share Kafka consumer groups.

## 2. Deployment

```bash
cp .env.example .env                      # replace every CHANGE_ME (openssl rand -base64 32)
docker compose --profile telemetry up -d --build
docker compose ps                         # migrate + mlflow-db-init: Exited (0); everything else Up/healthy
curl -s localhost:8000/api/v1/health/ready
```

* `docker compose down` stops the stack; volumes (`pgdata`, `kafkadata`, `miniodata`, `traccardata`) persist.
  **`down -v` destroys all data — never in production.**
* All published ports bind to `127.0.0.1` (PG 5433, Keycloak 8080, Kafka 29192, Redis 6380, MinIO 9100/9101,
  API 8000, web 5173, Traccar 8082/5055, MLflow 5500, Mailpit 8025). Change them in `.env` if they collide.
* **Production at asseta.co.tz:** [deployment-live.md](deployment-live.md) implements everything in this and the
  next bullets: host nginx site templates (`deploy/nginx/`) with the F-5/F-6 limits, Keycloak in production mode at
  `/auth`, the console as static releases, all ports on `127.0.0.1`, and `scripts/deploy-live.sh` for every update.
* **TLS / reverse proxy (production):** put a TLS-terminating reverse proxy (nginx, Caddy, Traefik, or a cloud LB)
  in front of `web` (console + `/api/` + WebSocket upgrade on `/api/v1/ws`) and Keycloak; only 443 is public, plus
  the device protocol ports of approved tracker models on the Traccar host ([gps-hardware.md](gps-hardware.md)).
  Set `ASSETA_PUBLIC_KEYCLOAK_URL` and `ASSETA_WEB_URL` to the public `https://` URLs (the token issuer is derived from
  the Keycloak URL; CORS from the web URL) and rebuild `web` (`VITE_KEYCLOAK_URL` is a build arg). Run Keycloak with
  `start` (not `start-dev`) behind the proxy (`KC_PROXY_HEADERS=xforwarded`). Never expose Postgres, Redis, Kafka,
  MinIO console, MLflow, Mailpit or the Traccar UI.
* **Request limits at the web proxy** (`web/nginx.conf`, [security.md](security.md) F-5/F-6): per client IP,
  `/api/` 30 r/s with a burst of 150; report exports, ML training, invoice generation and test sends an extra
  1 r/s, burst 10; the gateway path 50 r/s, burst 200. Excess gets 429 `RATE_LIMITED` (JSON envelope,
  `Retry-After: 1`; logged by nginx at `warn` as `limiting requests`). Bodies above 11 MiB get 413
  `PAYLOAD_TOO_LARGE` from nginx, and from the API too (`ASSETA_MAX_REQUEST_BYTES`; keep both in step).
  Traccar and the workers talk to `api:8000` directly and are never throttled here.
  **Behind a TLS proxy, set `ASSETA_TRUSTED_PROXY_CIDR`** to the proxy's address (for example `172.18.0.0/16` or
  the proxy host's `/32`) and have it send `X-Forwarded-For`. Otherwise every client shares the proxy's single
  bucket and normal use is throttled. Never set it to `0.0.0.0/0`, because clients could then choose their own
  bucket. If many phones share one carrier NAT address and see 429s, raise the `api` zone rate or burst in
  `web/nginx.conf` and rebuild `web`.
* Production Keycloak caches themes: restart it after changing `infra/keycloak/themes/asseta`.
* An already-imported realm keeps its settings: switch the login theme once (Admin console → Realm settings →
  Themes → `asseta`, or `PUT /admin/realms/asseta {"loginTheme":"asseta"}`).

## 3. Configuration and secrets

* All configuration is environment-only (`backend/src/asseta/core/config.py`, `ASSETA_*`); `.env.example` lists
  every variable with placeholders; `.env` is gitignored and never committed. Startup validates channel/provider
  configuration and fails fast on an invalid combination.
* Secrets: Postgres superuser / `asseta_owner` / `asseta_app` / `keycloak` / `mlflow` passwords, Keycloak admin,
  `ASSETA_API_CLIENT_SECRET` (confidential client `asseta-api`), Redis, MinIO root, `ASSETA_TRACCAR_GATEWAY_KEY`,
  SMS (NextSMS), SMTP, FCM service-account JSON and APNs `.p8` (mounted read-only files via `*_FILE` paths, e.g. in a
  `compose.override.yaml`). In production use the host's secret manager to render `.env` (or Docker secrets); never
  bake secrets into images.
* Rotation:
  | Secret | How |
  |---|---|
  | Traccar gateway key | change `.env`, `docker compose up -d migrate traccar` (bootstrap stores the new SHA-256); emergency: `POST /api/v1/platform/telemetry-gateways/{id}/deactivate` |
  | `ASSETA_API_CLIENT_SECRET` | regenerate in Keycloak (client `asseta-api` → Credentials), update `.env`, `docker compose up -d api` and workers |
  | DB role passwords | `ALTER ROLE … PASSWORD …` as superuser, update `.env`, recreate dependent services |
  | MinIO root | update MinIO and `.env` together, recreate `minio`, `api`, workers, `mlflow` |
  | Redis | update `.env`, recreate `redis` and its clients |
  | Provider keys (SMS/SMTP/FCM/APNs) | replace in `.env`/mounted files, recreate `api` and `notification-worker` |

## 4. Upgrades and migrations

1. Back up (§6) and note the current `alembic_version`.
2. `git pull` the release; `docker compose build`.
3. `docker compose up -d migrate` — runs `alembic upgrade head` as `asseta_owner` (not superuser) and the idempotent
   `asseta-bootstrap`. API and workers wait for it (`service_completed_successfully`).
4. `docker compose up -d` — the API syncs the permission catalog to Keycloak at startup (fail-fast; it restarts until
   Keycloak answers). New permissions reach existing role groups once (DEC-015).
5. Verify: `/health/ready`, `docker compose ps`, outbox backlog (§5.2), consumer lag (§5.3).

* CI proves every migration `upgrade → downgrade base → upgrade` plus `alembic check` (`.github/workflows/ci.yml`);
  track.md also records up/down cycles on a populated database.
* **Rollback stance:** prefer roll-forward (fix migration). Downgrades are tested but some data-carrying migrations
  cannot restore dropped information; for a failed production upgrade, restore the pre-upgrade backup into the
  previous release instead of downgrading in place.

## 5. Monitoring and health

### 5.1 Health
* `GET /api/v1/health/live` → `{"status":"ok"}` (process up).
* `GET /api/v1/health/ready` → per-dependency status (`database`, `redis`, `kafka`, `keycloak`, `object_store`);
  HTTP 503 only when the database is down; other failures report `degraded` and the API keeps serving what it can.
* Logs: structured JSON (structlog, UTC ISO timestamps) on stdout with the request `X-Correlation-ID`; use
  `docker compose logs -f api outbox-relay timeline-worker …`. Metrics/tracing exporters are **not** implemented in
  R1 — health, the SQL/Kafka checks below and logs are the monitoring surface.

### 5.2 Outbox backlog (events not yet in Kafka)
```sql
-- psql as asseta_owner on the asseta database
SELECT set_config('app.scope','system',false);
SELECT count(*) FILTER (WHERE published_at IS NULL) AS pending, max(attempts) AS max_attempts,
       min(created_at) FILTER (WHERE published_at IS NULL) AS oldest_pending
FROM outbox_event;
SELECT topic, left(last_error, 120), count(*) FROM outbox_event WHERE published_at IS NULL GROUP BY 1, 2;
```
Alert when `pending` grows for > 5 min or `oldest_pending` is older than a few minutes. Retries back off
exponentially to ≤ 300 s; rows are never dropped (there is no dead-letter: a permanently failing row stays pending
with `last_error` for an operator).

### 5.3 Kafka consumer lag
```bash
docker compose exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --all-groups        # groups: asseta-timeline, asseta-notification, asseta-intelligence
```
`LAG` should return to 0 within seconds under normal load. Consumers deduplicate on the `event_id` header, so
re-delivery after a restart is harmless.

### 5.4 Telemetry
* Quarantine: `GET /api/v1/tenant/telemetry/ingestion-events?status=QUARANTINED`, or as system
  `SELECT quarantine_reason, count(*) FROM tracker_ingestion_event WHERE status='QUARANTINED' GROUP BY 1;`
  (reasons and fixes: [gps-hardware.md](gps-hardware.md#quarantine-reasons-and-troubleshooting)).
* Partitions: the connectivity worker pre-creates monthly partitions (`ensure_telemetry_partitions`, SECURITY
  DEFINER). The default partitions must stay empty: `SELECT count(*) FROM machine_position_event_default;`
* Gateway last seen: `GET /api/v1/platform/telemetry-gateways`.

### 5.5 Notifications
* Channel delivery log: `notification_delivery` (`status`, `attempts`, `next_attempt_at`, `last_error`, `provider`);
  pending backlog: `SELECT channel, status, count(*) FROM notification_delivery GROUP BY 1,2;` (system scope).
  Also visible in the console (tenant notification settings → delivery log). SMS: `sms_delivery` + tenant SMS wallet.
* Dev e-mail inbox: Mailpit `http://127.0.0.1:8025`.

### 5.6 ML
Inference audit, drift and readiness on the platform Models page / `GET /api/v1/platform/ml/*`; response procedure in
[model-governance.md §6](model-governance.md#6-monitoring-and-drift-response).

## 6. Backup and restore (production procedure)

What must be backed up together (one consistent point in time per component):

| Component | Method | Notes |
|---|---|---|
| `asseta` database | `pg_dump -Fc` | all business data, audit, outbox, telemetry partitions |
| `keycloak` database | `pg_dump -Fc` | users, credentials, groups (= tenant role grants), clients |
| `mlflow` database | `pg_dump -Fc` | experiment runs (governance record is in `asseta`) |
| Keycloak realm config | admin REST `partial-export` (clients, groups, roles; secrets masked) | readable config record only; the `keycloak` dump is the backup that is restored |
| MinIO buckets `asseta-evidence`, `asseta-mlflow` | `mc mirror` | evidence is content-addressed and write-once, so incremental mirrors are safe |
| `.env` + mounted key files | secret manager | never stored next to the data backups unencrypted |

Kafka is **not** backed up: every event originates in `outbox_event` (published rows are retained) and consumers
are idempotent; derived timeline state is rebuilt by replay from PostGIS positions.

### 6.1 Back up
Production: `scripts/backup-live.sh` runs exactly these steps against the live stack (plus retention and an optional
off-host rsync), `scripts/restore-live.sh <dir>` runs §6.2 with confirmation prompts
([deployment-live.md §6](deployment-live.md#6-backups)).
```bash
set -a; . ./.env; set +a                      # secrets only into the environment, never echoed
TS=$(date -u +%Y%m%dT%H%M%SZ); mkdir -p backups/$TS
for db in asseta keycloak mlflow; do
  docker compose exec -T -e PGPASSWORD="$POSTGRES_SUPERUSER_PASSWORD" postgres \
    pg_dump -U postgres -Fc "$db" > backups/$TS/$db.dump
done
# Keycloak config record (admin token from the master realm; never printed)
KC_TOKEN=$(curl -s -d grant_type=password -d client_id=admin-cli -d "username=$KEYCLOAK_ADMIN_USER" \
  --data-urlencode "password=$KEYCLOAK_ADMIN_PASSWORD" \
  http://localhost:8080/realms/master/protocol/openid-connect/token | jq -r .access_token)
curl -s -X POST -H "Authorization: Bearer $KC_TOKEN" \
  "http://localhost:8080/admin/realms/asseta/partial-export?exportClients=true&exportGroupsAndRoles=true" \
  > backups/$TS/realm-asseta-partial-export.json
# MinIO: AFTER the database dumps (content-addressed objects => every key the dump references is mirrored).
# Uses the `mc` bundled in the pinned minio image; credentials stay inside the container environment.
docker compose exec -T minio sh -c 'mc alias set src http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null \
  && mc mirror --quiet src/asseta-evidence /tmp/bk/asseta-evidence && mc mirror --quiet src/asseta-mlflow /tmp/bk/asseta-mlflow; \
  rc=$?; mc alias rm src >/dev/null; exit $rc'
docker compose cp minio:/tmp/bk backups/$TS/objects && docker compose exec -T minio rm -rf /tmp/bk
(cd backups/$TS && find . -type f -exec shasum -a 256 {} + > SHA256SUMS)
```
Encrypt and copy the backup off-host. Schedule: databases at least daily (RPO ≤ 24 h by default; tighten with WAL
archiving / PITR if the business needs a smaller RPO — not configured in R1), MinIO mirror at least daily.

### 6.2 Restore (order matters)
1. Stop writers: `docker compose stop api outbox-relay billing-scheduler timeline-worker connectivity-worker
   intelligence-worker notification-worker notification-scheduler traccar`.
2. Postgres: on a fresh volume the image's `infra/postgres/init/01-roles.sh` creates the roles (`asseta_owner`,
   `asseta_app`, `keycloak`); create `mlflow` too (`infra/postgres/mlflow-db.sh`). Recreate each database empty
   (`DROP DATABASE …; CREATE DATABASE asseta OWNER asseta_owner TEMPLATE template0;` likewise `keycloak`, `mlflow`) and
   restore as the superuser, keeping ownership: `pg_restore -U postgres -d <db> --exit-on-error <db>.dump`. The dump
   recreates the extensions, grants, FORCE RLS flags, policies and immutability triggers (verified by the drill).
3. MinIO: `mc mirror` the backup back into `asseta-evidence` (and `asseta-mlflow`).
4. Start Keycloak, then `docker compose up -d migrate` (no-op if the schema is at head; applies newer migrations
   when restoring into a newer release), then the rest.
5. Verify (all must pass before reopening traffic):
   ```sql
   SELECT version_num FROM alembic_version;                      -- matches the release
   SELECT relname FROM pg_class WHERE relrowsecurity AND NOT relforcerowsecurity AND relkind IN ('r','p');  -- 0 rows
   SELECT count(*) FROM pg_class WHERE relforcerowsecurity;      -- same as before the backup
   -- row counts per table compared with the source (the drill script does this for every table)
   ```
   Hash-check the evidence objects (`capture_attachment`, `machine_photo` rows: object key + SHA-256) against the restored bucket; `/health/ready` all
   `ok`; a known user can sign in; the fleet map shows the last known positions.
6. Re-enable Traccar last; it retries buffered forwards. Tracker data received meanwhile by Traccar is forwarded on
   start; devices buffer according to their own capability.

The procedure is exercised by `scripts/drills/backup_restore.py`: a consistent exported snapshot is dumped, restored
into a throwaway PostGIS container and a throwaway MinIO container (never into the live databases or buckets) and
verified table by table; measured RTO/RPO are in the drill results below.

## 7. Incident procedures

Each entry: detect → contain → recover → verify. Client-side behaviour for the same failures:
[offline-sync.md failure matrix](offline-sync.md#failure-matrix).

| Failure (§6) | Detect | Action | Verify |
|---|---|---|---|
| **Network flaps** (phones / trackers) | Sync push retries, `DUPLICATE` outcomes; tracker gaps then late fixes | None required: pushes are idempotent per operation id; tracker data is accepted by event time | One effect per operation (`client_operation`); late positions flagged `is_late`, current position unchanged |
| **Duplicate delivery** (sync, Traccar retries, Kafka redelivery) | `DUPLICATE` counts in push results / ingest `duplicates` | None: dedupe on operation id, `(tracker, event_time)`, consumer `event_id` | No duplicate captures/expenses/payments; alerts superseded, not doubled |
| **Long offline period** | Device `offline_grant_until` passed; snapshot expiry | Device must reconnect to refresh grant/policy snapshot; captures already taken are validated against the snapshot they used | Server records both policy stamps; nothing silently re-priced |
| **Lost / stolen phone** | Report from staff | Tenant owner: `POST /api/v1/tenant/devices/{id}/revoke` (reason) → next contact gets `DEVICE_REVOKED` + `WIPE_LOCAL_DATA`; disable/reset the user in Keycloak if credentials may be exposed; re-registration is refused | Device list shows revoked; audit `sync.device.revoked` |
| **Expired / revoked device session** | `DEVICE_REVOKED` / `DEVICE_NOT_REGISTERED` refusals; device past `offline_grant_until` | User signs in again online to register a new session; unsynced local data on a revoked device is wiped by design (evidence already synced is kept) | New device session active |
| **Suspended subscription** | Entitlement `READ_ONLY`/`BLOCKED`; sync `QUARANTINED` | Platform: resolve payment, `POST /api/v1/platform/subscriptions/{sid}/transitions` (`to_status`, `effective_date`, `reason`) or entitlement auto-lift on verified payment; nothing is deleted | Quarantined pushes are applied when devices re-send after reactivation |
| **Deleted / reassigned machine** | Sync `CONFLICT` with `server_state`; telemetry `UNASSIGNED`/`NOT_ENROLLED` quarantine | Machines are retired, never deleted (`POST /tenant/machines/{id}/deactivate`); reassign tracker with `replace_existing_primary`; supervisors pull the new job state | Data attaches to the assignment valid at event time; no double billing on swap |
| **GPS disabled / denied** | Captures with `NO_FIX`/`PERMISSION_DENIED`; `GPS_UNAVAILABLE` exceptions | Per METER_CAPTURE policy: SOFT → provisional + exception for review; HARD → rejected; coach the user to enable location | Exceptions reviewed before billing |
| **Kafka down** | readiness `kafka: down`; outbox `pending` grows; consumer errors in worker logs | API, sync and telemetry ingestion continue (positions stored synchronously); `docker compose up -d kafka` / fix broker | Relay drains automatically; consumer lag returns to 0; no duplicates (idempotent consumers) |
| **Object store down** | readiness `object_store: down`; uploads/evidence reads return 503 `DEPENDENCY_UNAVAILABLE` | Restore MinIO / storage; everything else keeps working; blob chunks stay staged in Postgres | Devices retry blob `complete`; presigned reads work again |
| **Tracker backlog** (buffered GPS after outage, or Traccar backlog after API downtime) | Burst of ingestions with old `fixTime`; timeline consumer lag | None for data within `max_replay_age_days` (default 30); older is quarantined `TOO_OLD` (raise the policy deliberately if justified) | History shows late fixes at their real times; alerts re-evaluated idempotently |
| **API down / crash loop** | `/health/live` fails; container restarting | `docker compose logs api`; typical causes: Keycloak unreachable at startup (catalog sync fail-fast), DB down, bad config. Traccar retries forwards; phones keep queuing | `/health/ready` ok; outbox and Traccar backlogs drain |
| **Database down** | readiness HTTP 503 | Restore Postgres (or restore from backup §6.2); all services reconnect | Row counts, FORCE RLS check, alembic version |
| **Keycloak down** | readiness `keycloak: down`; sign-in fails | Existing access tokens remain valid until expiry (≤ 300 s); restore Keycloak (DB + realm) | Sign-in works; API restart succeeds (catalog sync) |
| **Request flood / 429s** | `limiting requests` warnings in `docker compose logs web`; clients get 429 `RATE_LIMITED` | A single abusive IP: block it at the edge proxy or firewall. Legitimate users throttled behind a TLS proxy: check `ASSETA_TRUSTED_PROXY_CIDR` (§2). A shared carrier NAT: raise the `api` zone in `web/nginx.conf` | 429s stop for normal use; the API stays responsive (`/health/ready`) |
| **Leaked gateway key** | Unexpected ingestion from unknown sources | Deactivate gateway, rotate key (§3) | 401 for the old key |
| **Model misbehaviour / drift** | `ML_MODEL_DRIFT` notification, inference audit failures | Hard switch off, then [model-governance.md §6](model-governance.md#6-monitoring-and-drift-response) | No new predictions; deterministic rules continue |

Security incidents (suspected cross-tenant access, compromised account): disable the Keycloak user / end the
managed-service mandate (refused on the next request), preserve `audit_event`, and follow [security.md](security.md).

## 8. Routine operations

* **Billing:** `POST /api/v1/platform/subscriptions/{id}/invoices/generate {"as_of": "YYYY-MM-DD"}` — idempotent; the
  billing scheduler runs renewals + entitlement evaluation automatically.
* **Quarantine review** weekly (§5.4); **default partitions** empty; **outbox** pending ≈ 0; **consumer lag** ≈ 0.
* **Gateway key rotation** per policy (§3).

## 9. Local demo baseline (dev only, destructive)
```
docker compose stop api outbox-relay billing-scheduler timeline-worker connectivity-worker
cd backend && uv run python scripts/demo_reset.py ../.env --keep <platform-owner-email> --yes
cd .. && docker compose run --rm migrate && docker compose up -d
cd backend && uv run python scripts/demo_seed.py ../.env ../.demo/credentials.json
```
`demo_reset.py` deletes every Keycloak user except `--keep`, all `/tenants/*` groups and throwaway clients, and empties
the business tables (reference data and platform-default policies are kept/re-seeded). `demo_seed.py` builds one
full tenant ("Kilimanjaro Earthworks": owner, supervisor, accountant, 5 machines / 4 simulated trackers via Traccar,
sites + geofences, customers, contracts, jobs). Demo passwords go only to `.demo/credentials.json` (0600, gitignored).
Throwaway tenants from smoke/E2E runs: `scripts/purge_tenants.py ../.env --tenant <uuid> --dry-run` first, then
`--yes` (local stack only, API and workers stopped). Never use either script against production.

## 10. Drill results

Scripts: `scripts/drills/` (see its README): backup/restore, telemetry load, Kafka outage, API/worker restart under
load, object-store outage, queue backlog recovery. Each writes its evidence to `docs/evidence/drills/`.

Latest run: 2026-10-22, all **PASS** — full table, defects found and open findings in
[evidence/drills/README.md](evidence/drills/README.md).

| Drill | Evidence | Measured |
|---|---|---|
| Backup / restore | [backup-restore](evidence/drills/2026-10-22-backup-restore.md) | backup 3 s; **RTO 7.8 s** into fresh containers, all tables/RLS/grants/triggers/alembic/Keycloak/evidence hashes verified; **RPO = backup interval** (no WAL archiving) |
| Telemetry load | [telemetry-load](evidence/drills/2026-10-22-telemetry-load.md) | 6 300 positions, 0 lost/dup; direct p95 0.04 s to store, 0.54 s to latest; Traccar burst p95 31 s (API-bound); timeline drained 28 s after the burst |
| Kafka outage (60 s) | [kafka-outage](evidence/drills/2026-10-22-kafka-outage.md) | API 0 failures; outbox drained 9.3 s after broker start; consumers at lag 0 in 56 s |
| API / worker restarts | [restart-under-load](evidence/drills/2026-10-22-restart-under-load.md) | API ready 3.8 s; WebSocket reconnect 6.8 s; workers resume, 0 lost/duplicated effects |
| Object-store outage | [object-store-outage](evidence/drills/2026-10-22-object-store-outage.md) | uploads 503 `DEPENDENCY_UNAVAILABLE`, rest of API up; resumable blob completes after recovery |
| Queue backlog | [queue-backlog](evidence/drills/2026-10-22-queue-backlog.md) | notification 2 060 msgs in 12 s; timeline 2 000 late msgs in 145 s |

Operational consequences of the drills:
* **Database safety valves** (app role, `core/config.py`): `ASSETA_DB_LOCK_TIMEOUT_MS` (default 5000),
  `ASSETA_DB_IDLE_IN_TRANSACTION_TIMEOUT_MS` (default 60000) and `ASSETA_DB_STATEMENT_TIMEOUT_MS` (default 30000 for
  the API; workers use `ASSETA_WORKER_DB_STATEMENT_TIMEOUT_MS`, default 300000; migrate/bootstrap run without it;
  0 disables any of them). A lock wait beyond the limit returns 503 `DATABASE_BUSY` and a cancelled statement 503
  `QUERY_TIMEOUT`, both retryable (Traccar and the apps retry). Watch for these in the API log
  (`database_operational_error`, `sqlstate` 55P03 or 57014). Persistent lock errors mean a hot row or a stuck
  transaction (`pg_stat_activity`, `pg_blocking_pids`). Repeated `QUERY_TIMEOUT` on one report or list means a
  missing index or too wide a filter: fix the query rather than raising the limit. Raise it only deliberately and
  for a known long operation. Backup, restore and purge scripts connect directly and are not bound by it.
* **Capacity:** one API process ingests ≈ 60–110 positions/s. Size API processes/replicas for the expected tracker
  report rate with headroom. A gateway that reaches the API through the web proxy is limited per IP (§2); during an over-capacity burst Traccar queues
  and readiness probes may time out until it drains.
* **Kafka partitions:** topics are auto-created with 1 partition. Before running more than one timeline worker,
  create `asseta.telemetry.position` with N partitions (key = machine id keeps per-machine order).
* **Recovery is automatic** for Kafka, MinIO and worker restarts; no manual replay was needed in any drill. Relay
  retry backoff is capped at 300 s, so after a long broker outage the drain can start up to 5 min after recovery.

## 11. Reset a tenant's data before go-live

For a tenant that was used for demos or a trial and now goes live as the real company: erase its business data and
keep the company itself. One-off, per tenant, production-safe; it never touches another tenant or platform data.

| Kept | Deleted (every row of this tenant) |
|---|---|
| The tenant row and its settings (name, timezone, currency) | Machines, categories, operating areas, photos, trackers, positions, alerts, telemetry ingestion |
| Asseta subscription and platform billing: agreement, rate versions, subscription and its status/entitlement events, platform invoices (as issued), payments, credits, SMS wallet | Sites, geofences, site check-ins; per-machine billing enrollments of the deleted machines and their un-invoiced charges |
| Keycloak accounts and their tenant groups (not touched at all), the role mirror, tenant memberships | Customers, contracts, rate cards, jobs, readings, work logs, exceptions, acknowledgements, approvals |
| Staff records and their login links | Expenses, categories, fuel, receipts; the whole cash chain (custody, handovers, transfers, variances, retentions, adjustments, overdue); deposit accounts |
| Managed-service mandates, push-device registrations | Hire invoices, customer payments, allocations, evidence; customer hours; engine-hour baselines/corrections/classifications; revenue reconciliation |
| Platform-level audit events (`platform.*`, `billing.*`) | Cases, signals, insights, ML trained on the tenant's data; notifications, inbox, SMS log; reason lists; the tenant's own policy versions (platform defaults apply again); number counters (job, `HP-`, `HINV-` numbering restarts); the tenant's business audit and security events; its object-store files (`tenants/<id>/`, `platform/ml-models/<id>/`) |

Tables are discovered from the schema; a tenant-scoped table that `backend/scripts/reset_tenant_data.py` does not
classify stops the run before anything changes (classify it there when a new module adds one). The database part is
one transaction as the schema owner (guard triggers and forced RLS are lifted only inside it), so it either completes
or changes nothing. An issued platform invoice line that billed a demo machine keeps every printed field; only its
internal pointer to the deleted per-machine charge is cleared. Platform invoices already issued for demo machines
stay as they are; credit them in Platform -> Billing if the client should not pay them.

Before: deploy this release (the API must know the reset revocation, or phones could not register again), stop the
demo feed if it runs (Ctrl-C in its terminal, or `docker stop` the `asseta-api-run-*` container running it), and pick a quiet moment: the transaction locks the
tenant tables for a few seconds (other tenants' requests wait, they do not fail).

```bash
cd /home/asseta
scripts/backup-live.sh                                                        # 1. backup (required: < 2 h old)
scripts/reset-tenant-data.sh --registration-number 2026/10/0001               # 2. dry run: tenant, id, counts
scripts/reset-tenant-data.sh --registration-number 2026/10/0001 --yes         # 3. real run: type the tenant name
#   with Traccar clean-up: TRACCAR_ADMIN_EMAIL=you@example.com scripts/reset-tenant-data.sh ... --yes --remove-traccar-devices
scripts/reset-tenant-data.sh --registration-number 2026/10/0001               # 4. verify: TOTAL rows 0, objects 0
```
`--tenant-id <uuid>` selects by id instead. The dry run prints the tenant name and id, the rows per table that would
be deleted and kept, the object-store object count, the active phone sessions and the Traccar devices of the trackers
(remove them in Traccar, or let `--remove-traccar-devices` do it). The real run also needs `--yes`, a complete
`scripts/backup-live.sh` backup younger than `RESET_BACKUP_MAX_AGE_MIN` (120) minutes under `BACKUP_ROOT` (or
`--backup-confirmed` when you have one elsewhere) and the tenant name typed exactly. It records the platform audit
event `platform.tenant.data_reset` (counts, operator = `--operator`, default `<user>@<host>`, backup directory),
deletes the objects after the commit (if that part fails, run the same command again: the database part is then a
no-op) and moves the seeder's `.deploy/demo-*-state.json` of the tenant aside.

Verify (step 4 plus): Platform -> Audit log shows `platform.tenant.data_reset` for the tenant; signed in as the
tenant owner, Fleet, Jobs, Finance and the dashboards are empty; Platform -> Tenants shows the subscription unchanged.

What users see:
* **Web:** same sign-in, same roles; every list is empty and numbering starts again (first job `J-<year>-001`).
* **Phones** (supervisor app, Android and iOS): every device session of the tenant is revoked with the reset reason.
  On its next sync the app gets the wipe instruction: it erases its local database, evidence files and tokens and
  returns to the sign-in screen with the revocation message ("revoked by your administrator ... local data was
  erased"). Tell users to simply sign in again: the reset revocation does not lock the phone out; it registers again
  and starts from a fresh bootstrap (an empty fleet until real data exists). A phone that registers but still holds
  the old data is told to wipe on its first delta pull or upload, so demo data never comes back. Unsynced work on a
  phone at the time of the reset is discarded with the rest (it belonged to the erased records).

Afterwards `scripts/seed-demo-tenant.sh seed` refuses this tenant (it carries the reset event): demo data goes only
into a separate demo tenant. The demo accounts and demo staff that `seed` created remain (accounts are never touched);
deactivate them in People and Keycloak if the company does not use them. Undo = restore the backup of step 1 (§6.2):
that restores the whole database, i.e. every tenant, to that moment.
