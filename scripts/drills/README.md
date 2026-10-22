# Hardening drills

Scripted, repeatable failure and recovery drills for prompt.md §10 #12. Each writes Markdown evidence (commands,
timings, results, PASS/FAIL, what is NOT simulated) to `docs/evidence/drills/<date>-<drill>.md`. Results of the
2026-10-22 run: [docs/evidence/drills/README.md](../../docs/evidence/drills/README.md).

**Local only.** Every script refuses to run unless the API and Keycloak URLs from `.env` are on localhost,
`ASSETA_ENVIRONMENT` is not `production` and the compose project `asseta` is running. Secrets are read from `.env`
into memory and never printed. Disruption drills always restart what they stop and verify recovery before
finishing. Nothing here deletes Docker volumes, drops the live databases or deletes objects of the running stack;
the backup drill restores into throwaway containers that it removes.

Run from `backend/` (uses the backend virtualenv):

```bash
cd backend
uv run python ../scripts/drills/drill_tenant.py create --machines 100   # throwaway tenant via the platform API
uv run python ../scripts/drills/telemetry_load.py        # (b) 100 machines x 63 fixes, Traccar + direct paths
uv run python ../scripts/drills/kafka_outage.py          # (c) stop/start kafka under activity
uv run python ../scripts/drills/restart_under_load.py    # (d) restart api + every worker, WebSocket reconnect
uv run python ../scripts/drills/object_store_outage.py   # (e) stop/start minio, 503 envelope, resumable upload
uv run python ../scripts/drills/queue_backlog.py         # (f) backlog with timeline + notification workers stopped
uv run python ../scripts/drills/backup_restore.py        # (a) dump + restore into throwaway containers, verify
uv run python ../scripts/drills/drill_tenant.py purge --dry-run   # always first: reports, changes nothing
uv run python ../scripts/drills/drill_tenant.py purge --yes       # removes exactly the recorded tenant id
```

| File | Purpose |
|---|---|
| `drill_common.py` | env + localhost guard, compose/psql/Kafka-lag helpers, evidence writer, throwaway-tenant session |
| `drill_tenant.py` | create / purge the throwaway tenant (state in `.drills/tenant.json`, 0600, gitignored) |
| `drill_activity.py` | background activity (positions + job submissions) and exactly-once verification |
| `telemetry_load.py`, `kafka_outage.py`, `restart_under_load.py`, `object_store_outage.py`, `queue_backlog.py`, `backup_restore.py` | the drills |

Notes:
* `drill_tenant.py purge` uses `backend/scripts/purge_tenants.py`'s routines for the single recorded tenant id and
  refuses if that tenant's name does not start with "Drill 7E ". It never purges by name prefix.
* The drills are idempotent in the sense that they can be re-run on the same throwaway tenant (earlier positions
  are excluded from comparisons); `backup_restore.py` needs no tenant.
* Durations are for one laptop-class Docker host; compare trends between runs, not absolute numbers with production.
