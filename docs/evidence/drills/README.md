# Hardening drill evidence (Gate 7E, prompt.md §10 #12)

All drills ran on 2026-10-22 against the local docker compose stack (one host; one container per service; Kafka
single broker, 1 partition per topic). The disruption drills used a throwaway tenant "Drill 7E 97b194"
(`631e2fc6-da50-4fec-8b72-cda8802dd00a`, 100 machines with simulated OsmAnd trackers) created through the platform
API by `scripts/drills/drill_tenant.py`. It was removed afterwards by its id: dry run first (102 054 rows reported,
nothing changed), then the real purge (`PURGE OK … rows=102054 keycloak_groups=1 users_removed=2`). The demo tenant
"Kilimanjaro Earthworks" was not touched; it is the only tenant left.

| Drill | Evidence | Result | Key numbers |
|---|---|---|---|
| (a) Backup / restore | [backup-restore](2026-10-22-backup-restore.md) | PASS | 165 tables / 113 843 rows identical; 93 tables FORCE RLS, 130 policies, 332 grant sets, 173 triggers, alembic `g7asec000001` identical; RLS probe as `asseta_app` on the restored DB; Keycloak users/groups/clients identical; every referenced evidence object SHA-256 verified; **backup 3 s, RTO 7.8 s** (fresh containers → verified); RPO = backup interval |
| (b) Telemetry load | [telemetry-load](2026-10-22-telemetry-load.md) | PASS | 100 machines × 63 positions (+200 duplicates, 300 late, out-of-order mix) = 6 300 stored, 0 lost, 0 duplicated, 0 quarantined. Direct gateway path: 58–66 positions/s, p95 send→stored 0.04 s, p95 send→`machine_latest_position` 0.54 s. Via Traccar (3 500-message burst in 2.5 s): server 78–107 positions/s, p95 send→stored 31 s (API-bound). Timeline lag drained 28 s after the last position |
| (c) Kafka outage | [kafka-outage](2026-10-22-kafka-outage.md) | PASS | 60 s broker outage under activity: 0 failed API calls, readiness `degraded` (HTTP 200), outbox peaked at 150 events; relay drained 9.3 s after start; all 3 consumer groups at lag 0 within 56 s; 136 broker-level redeliveries absorbed: 0 lost / 0 duplicated positions, 52/52 job events notified once |
| (d) API / worker restarts | [restart-under-load](2026-10-22-restart-under-load.md) | PASS | api + 7 workers restarted (SIGTERM) + timeline-worker SIGKILL under activity; API ready 3.8 s after restart, WebSocket client re-authenticated after 6.8 s; 14 client calls failed only during the API restart (connection reset; clients retry with idempotency keys); 0 lost/duplicated effects, 78/78 job events notified once |
| (e) Object-store outage | [object-store-outage](2026-10-22-object-store-outage.md) | PASS | photo upload → 503 `DEPENDENCY_UNAVAILABLE` envelope with correlation id (3.3 s); machines/telemetry/jobs/sync bootstrap unaffected; resumable blob session kept its chunks and completed after MinIO returned (object SHA-256 verified) |
| (f) Queue backlog | [queue-backlog](2026-10-22-queue-backlog.md) | PASS | timeline + notification workers stopped during 2 000 positions + 60 jobs: notification backlog 2 060 cleared in 12 s; timeline backlog 2 000 (1 h-late fixes, worst case for replays) cleared in 145 s; 0 lost / 0 duplicated |

## Defects found by the drills and fixed

1. **Hot gateway row serialised all ingestion (High, availability).** Every `POST /telemetry/traccar` updated
   `telemetry_gateway.last_seen_at` inside the request transaction. At 20 concurrent senders the requests queued on
   that one row lock while holding pool connections; the API stopped answering, `/health/ready` included, until it
   was restarted (first attempt, 17:30 UTC; no evidence file — the script crashed on the client timeout, and the
   stuck `pg_stat_activity` state was recorded in the session). Fix: throttled heartbeat taken with
   `FOR UPDATE SKIP LOCKED` (`modules/telemetry/router.py::touch_gateway`).
2. **Pool ↔ threadpool convoy (High, availability).** Second attempt (17:50 UTC): with the gateway row fixed, a
   3 500-message Traccar burst still hung the API. Requests that had finished their SQL waited for a threadpool
   slot to validate the response (FastAPI runs that in a second hop for sync endpoints) while still holding their
   connection, row locks and open transaction; the slots were held by requests waiting 30 s for a connection.
   Fixes: the ingest endpoint commits before returning; `lock_timeout` 5 s and
   `idle_in_transaction_session_timeout` 60 s on the app engine (`core/config.py`, `core/db.py`) with lock timeouts
   mapped to a retryable 503 `DATABASE_BUSY` (`core/errors.py`); tracker capability "observed" writes throttled
   to once a minute (`modules/telemetry/ingestion.py`). Tests: `tests/api/test_telemetry_gateway_heartbeat.py`
   (3 tests; the first two fail on the old code).
3. **Timeline worker throughput (Medium, freshness).** One full replay per message: 824 s to drain 5 894 messages
   ([superseded run](2026-10-22-telemetry-load-run1-per-event-replay.md)). Fix: batches of up to 500 messages
   coalesced to one replay per machine from the earliest event time (`workers/timeline_worker.py::coalesce`;
   `tests/unit/test_timeline_coalesce.py`; every geospatial API test now drains through the same coalescing).
   Same load: 28 s.

Two first-run verification bugs in the drill scripts themselves (a strict `is_late` expectation for the async
Traccar path and a too-narrow time window in the backlog check; also a `t`/`True` comparison in the RLS
inventory) were corrected and those drills re-run; the evidence files are from the re-runs.

## Open findings (not fixed here)

* **API throughput (Medium):** one uvicorn process sustains ≈ 60–110 positions/s; a Traccar burst above that
  queues inside Traccar (p95 31 s to store) and readiness probes time out during the burst (recovers by itself).
  Production should run several API processes/replicas and rate-limit the gateway at the proxy (see security.md F-5).
* **Single partition topics (Low):** Kafka topics are auto-created with 1 partition, so each consumer group has one
  active consumer. Create `asseta.telemetry.position` with N partitions (key = machine keeps ordering) before
  scaling timeline workers.
* **Residue of the drills in shared stores (Info):** the throwaway platform user's `app_user` row, the deactivated
  tracker model "Drill-OsmAnd-97b194", 100 auto-registered devices in Traccar's own database, a few objects under
  `asseta-evidence/tenants/631e2fc6-…/` and the events in Kafka topics. None is reachable from any tenant; delete
  manually if wanted (the drills never delete objects or volumes of the running stack).
