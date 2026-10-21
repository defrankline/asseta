# Operating runbook (Gate 0/1 coverage)

## Start / stop
`docker compose up -d --build` · `docker compose ps` · `docker compose logs -f api outbox-relay` ·
`docker compose down` (volumes persist; `down -v` destroys data — never in production).

## Health
* Liveness: `GET /api/v1/health/live`. Readiness: `GET /api/v1/health/ready` → per-dependency status; `503` only
  when the database is down; other dependencies report `degraded`.
* The API refuses to start if the Keycloak permission sync fails (fail-fast; Compose restarts it).

## Migrations
Run by the one-shot `migrate` service (`alembic upgrade head` as `asseta_owner`) before `api`/`outbox-relay`.
CI verifies upgrade → downgrade → upgrade and `alembic check` (no model drift).

## Outbox / Kafka backlog
```sql
SELECT set_config('app.scope','system',false);
SELECT count(*) FILTER (WHERE published_at IS NULL) AS pending, max(attempts), min(created_at) FILTER (WHERE published_at IS NULL)
FROM outbox_event;
```
Kafka down ⇒ events accumulate with `attempts`, `last_error`, exponential `next_attempt_at` (≤300 s); API writes
continue. When Kafka returns, the relay drains automatically. Scale relays horizontally (SKIP LOCKED).

## Billing operations
* Generate due invoices: `POST /api/v1/platform/subscriptions/{id}/invoices/generate {"as_of": "YYYY-MM-DD"}` —
  idempotent; already-invoiced periods are reported, never re-issued.
* Evaluate entitlements after payments/overdue: `POST .../entitlement/evaluate` (also automatic on payment decision).

## Telemetry operations
* Workers: `timeline-worker` (Kafka consumer, per-machine ordered replays), `connectivity-worker` (60 s sweeps;
  also pre-creates monthly partitions via `ensure_telemetry_partitions`). Positions outside created partitions land
  in `*_default` partitions — monitor and keep empty: `SELECT count(*) FROM machine_position_event_default;`
* Quarantine review: `GET /api/v1/tenant/telemetry/ingestion-events?status=QUARANTINED` (tenant) or, as system,
  `SELECT quarantine_reason, count(*) FROM tracker_ingestion_event WHERE status='QUARANTINED' GROUP BY 1;`
  `UNKNOWN_DEVICE` usually means a tracker not yet registered; `UNASSIGNED`/`NOT_ENROLLED` mean commissioning gaps.
* Kafka outage: positions are still stored synchronously; timeline events queue in the outbox and replay when Kafka
  returns (replays are idempotent).
* Gateway key rotation: change `ASSETA_TRACCAR_GATEWAY_KEY`, run `docker compose up -d migrate traccar`.

## Pending for later gates
Backup/restore drill, TLS reverse proxy configuration, metrics/tracing, scheduled billing/entitlement runs,
incident procedures — tracked in track.md Gate 7.

## Branding: login theme and landing page
* Keycloak uses the `asseta` login theme (`infra/keycloak/themes/asseta`, mounted read-only into the container and
  set as `loginTheme` in `realm-asseta.json`). An already-imported realm must be switched once: Admin console →
  Realm settings → Themes → Login theme `asseta` (or `PUT /admin/realms/asseta {"loginTheme":"asseta"}`).
* Production Keycloak (`start`, not `start-dev`) caches themes: restart after changing theme files.
* The public landing page shows a "Request a demo" mail link only when `VITE_CONTACT_EMAIL` is set at web build time.

## Local demo baseline (dev only, destructive)
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
Simulated positions are a one-off burst: the map correctly shows them ageing to stale/offline over time.
