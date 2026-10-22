# Drill: Object store (MinIO) outage: clean 503, rest of API up, resumable upload

* **Result:** PASS
* **Run:** 2026-10-22T18:36:26+00:00 → 2026-10-22T18:36:37+00:00 (12 s)
* **Target:** local docker compose stack (single host, single broker/node); script `scripts/drills/object_store_outage.py`

## Commands

```bash
cd backend
uv run python ../scripts/drills/object_store_outage.py
```

## Log

Throwaway tenant `631e2fc6-da50-4fec-8b72-cda8802dd00a`; machine `7e94cdc1-6cc2-47da-9c9a-f39329fab06f`.

* `docker compose stop minio` 0.3 s; readiness: HTTP 200 degraded (database=ok, redis=ok, kafka=ok, keycloak=ok, object_store=down)
* `docker compose start minio`; readiness ok after 0.8 s; total object-store downtime 11 s

## Checks

| Check | Result | Detail |
|---|---|---|
| baseline: machine photo upload 201 | PASS | HTTP 201 |
| baseline: blob session started and chunk 0 accepted | PASS | session fe2b88a9-2e9a-4700-bd63-9887dfde4d9d, 3 chunks of 262144 B |
| readiness reports object_store down, overall degraded (HTTP 200) | PASS | HTTP 200 degraded (database=ok, redis=ok, kafka=ok, keycloak=ok, object_store=down) |
| photo upload during outage → 503 error envelope (DEPENDENCY_UNAVAILABLE) | PASS | HTTP 503 DEPENDENCY_UNAVAILABLE in 3.3 s; correlation_id present: True |
| rest of the API works during the outage | PASS | {'GET /tenant/machines': 200, 'POST /telemetry/traccar': 202, 'POST /tenant/jobs': 201, 'GET /sync/bootstrap': 200} |
| remaining chunks accepted during the outage (staged in Postgres) | PASS | [200, 200]; received_chunks [0, 1, 2] |
| blob complete during outage → 503 envelope, session kept | PASS | HTTP 503 DEPENDENCY_UNAVAILABLE |
| readiness recovers | PASS |  |
| same blob session completes after recovery without re-upload | PASS | COMPLETE attachment ea04dc4e-be51-4bf3-a9e1-73dfd8b1ce43 after 0.05457508300605696 s (first complete attempt 0.1 s after readiness) |
| stored object SHA-256 matches the declared hash | PASS | 2677177b8eb4aebb |
| photo uploads succeed again | PASS | HTTP 201 |
| final readiness ok | PASS | HTTP 200 ok (database=ok, redis=ok, kafka=ok, keycloak=ok, object_store=ok) |

## Not simulated

* Object-store data loss or bucket corruption (covered by the backup/restore drill's object hash check).
* Slow / partially failing S3 (timeouts, 5xx from a healthy endpoint); here the endpoint is unreachable.
* Presigned URL behaviour for clients during the outage (URLs are signed locally; downloads fail at MinIO).
* MLflow artefact storage (MLflow keeps working for metadata; training records runs locally when down).
