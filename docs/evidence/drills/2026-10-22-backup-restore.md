# Drill: Backup and restore (PostgreSQL asseta/keycloak/mlflow, Keycloak realm, MinIO)

* **Result:** PASS
* **Run:** 2026-10-22T18:44:19+00:00 → 2026-10-22T18:44:30+00:00 (10 s)
* **Target:** local docker compose stack (single host, single broker/node); script `scripts/drills/backup_restore.py`

## Commands

```bash
cd backend
uv run python ../scripts/drills/backup_restore.py
```

## Log

### Backup

* `asseta`: snapshot 2026-10-22T18:44:20+00:00, 165 tables, 113843 rows, alembic `g7asec000001`; pg_dump -Fc 11.1 MB in 1.0 s
* `keycloak`: pg_dump -Fc 0.3 MB in 0.2 s
* `mlflow`: pg_dump -Fc 0.1 MB in 0.2 s
* Keycloak realm `asseta` partial export (config; secrets masked by Keycloak): 11 clients, 2 top-level groups, 11 clients with roles; DB counts {'users': 7, 'groups': 16, 'clients': 11}
* MinIO mirror (`mc mirror`): asseta-evidence 23 objects / 5.9 MB, asseta-mlflow 3 objects / 0.7 MB in 0.5 s
* Backup total 2.1 s; the DB snapshot was 2 s old when the backup finished

### Restore into throwaway containers

* Fresh PostGIS container ready (init: roles + empty DBs) in 2.5 s; pg_restore asseta 2.0 s, keycloak 0.3 s, mlflow 0.2 s
* **RTO (fresh containers → data restored and verified): 7.8 s**; **RPO of this procedure: the backup interval** (snapshot age at backup end 2 s; no WAL archiving)
* Backup artefacts: asseta.dump, keycloak.dump, mlflow.dump, objects, realm-asseta-partial-export.json

Cleanup: removed containers asseta-drill-restore-pg, asseta-drill-restore-minio (with anonymous volumes), the mirror copy inside the minio container and the backup directory.

## Checks

| Check | Result | Detail |
|---|---|---|
| pg_restore asseta (--exit-on-error) | PASS | 2.0 s  |
| pg_restore keycloak (--exit-on-error) | PASS | 0.3 s  |
| pg_restore mlflow (--exit-on-error) | PASS | 0.2 s  |
| row counts identical for every table | PASS | 165 tables, 113843 rows; differences: none |
| rls identical after restore | PASS | 93 tables FORCE RLS, 93 ENABLE |
| policies identical after restore | PASS | 130 policies on 93 tables |
| grants identical after restore | PASS | 332 role/table grant sets |
| triggers identical after restore | PASS | 173 triggers |
| functions identical after restore | PASS | 839 functions |
| alembic identical after restore | PASS | version g7asec000001 |
| RLS enforced for asseta_app on the restored DB | PASS | tenant scope: own=5 other=0; no scope set: 0 rows visible |
| Keycloak DB restored (realm users, groups, clients) | PASS | {'users': 7, 'groups': 16, 'clients': 11} |
| MinIO buckets restored with mc mirror | PASS | 0.8 s  |
| every evidence object referenced by the restored DB exists with matching SHA-256 | PASS | 6 referenced objects verified; problems: none |
| MLflow artifact bucket restored (object count) | PASS | 3/3 |
| scratch resources removed | PASS | none left |

## Not simulated

* Loss of the Docker host / disks: restore ran on the same host from a local backup copy; a real procedure ships backups off-host (encrypted) and restores on new hardware.
* Point-in-time recovery: no WAL archiving is configured; RPO equals the backup interval.
* Kafka and Redis are not backed up (Kafka is a transport fed from the durable outbox; Redis holds only cache/pub-sub). Traccar's own H2 DB is not backed up (devices re-register; Asseta is the system of record).
* Keycloak realm restore is verified via the keycloak DB dump; the REST partial export (config only, secrets masked) is taken as a readable config record but not re-imported.
* Restored services were not started against the restored data (verification is at data level).
