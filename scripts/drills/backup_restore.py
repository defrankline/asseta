"""Drill (a): backup + restore of the whole data plane into THROWAWAY containers, with verification.

    cd backend && uv run python ../scripts/drills/backup_restore.py [--keep-backup]

Backup (reads only; the running stack is not modified):
  1. One REPEATABLE READ snapshot on `asseta` is exported; exact row counts of every table, RLS flags, policies,
     grants, triggers and the alembic version are read IN that snapshot, and `pg_dump -Fc --snapshot=<id>` dumps
     exactly the same state (so counts must match 1:1 after restore).
  2. `pg_dump -Fc` of `keycloak` and `mlflow`; Keycloak realm configuration via the admin REST partial export.
  3. MinIO buckets `asseta-evidence` + `asseta-mlflow` mirrored with `mc mirror` AFTER the DB dump (objects are
     content-addressed and write-once, so every key the dump references is in the mirror).
Restore (new, temporary resources only; removed at the end):
  4. A fresh container from the same PostGIS image (`asseta-drill-restore-pg`, no network) runs the normal init
     (roles, empty databases); the databases are recreated empty and the dumps restored with `pg_restore`.
  5. A fresh MinIO container (`asseta-drill-restore-minio`, 127.0.0.1 random port) receives the mirror.
Verify: per-table row counts, FORCE/ENABLE RLS per table, policy/grant/trigger counts, alembic version, an RLS
probe as `asseta_app` (tenant scope sees only its tenant), Keycloak realm users/groups/clients, and every evidence
object referenced by the restored DB downloaded from the restored MinIO with a matching SHA-256.
Timings: backup duration, RTO (start of restore → verified), RPO of the procedure (snapshot age at backup end).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import boto3
import httpx
import psycopg
from botocore.config import Config
from drill_common import ENV, KC, ROOT, STATE_DIR, Evidence, compose, guard_local, now_utc, superuser_dsn

PG_IMAGE = "asseta/postgis:18-3.6"
PG_CT, MINIO_CT = "asseta-drill-restore-pg", "asseta-drill-restore-minio"
BUCKETS = ("asseta-evidence", "asseta-mlflow")

INVENTORY = {
    "counts": None,  # filled per table
    "rls": "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c WHERE "
    "c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') ORDER BY 1",
    "policies": "SELECT tablename, count(*) FROM pg_policies WHERE schemaname = 'public' GROUP BY 1 ORDER BY 1",
    "grants": "SELECT grantee, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) FROM "
    "information_schema.role_table_grants WHERE table_schema = 'public' AND grantee IN ('asseta_app', 'asseta_owner') "
    "GROUP BY 1, 2 ORDER BY 1, 2",
    "triggers": "SELECT event_object_table, count(*) FROM information_schema.triggers WHERE trigger_schema = 'public' "
    "GROUP BY 1 ORDER BY 1",
    "functions": "SELECT count(*) FROM pg_proc WHERE pronamespace = 'public'::regnamespace",
    "alembic": "SELECT version_num FROM alembic_version",
}
TABLES = "SELECT c.relname FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r' ORDER BY 1"


def run(cmd: list[str], *, stdout: Any = None) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        cmd, stdout=stdout if stdout is not None else subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=1800
    )


def inventory_conn(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    tables = [r[0] for r in conn.execute(TABLES).fetchall()]
    out["counts"] = {t: conn.execute(f'SELECT count(*) FROM public."{t}"').fetchone()[0] for t in tables}  # type: ignore[index]  # noqa: S608
    for k, q in INVENTORY.items():
        if q:
            out[k] = [list(map(str, r)) for r in conn.execute(q).fetchall()]
    return out


def restored_inventory() -> dict[str, Any]:
    """Same inventory on the restored DB, via psql inside the throwaway container (no network exposure)."""
    out: dict[str, Any] = {}
    tables = psql_ct("asseta", TABLES)
    union = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM public.\"{t}\"" for t in tables)  # noqa: S608
    out["counts"] = {r.split("\t")[0]: int(r.split("\t")[1]) for r in psql_ct("asseta", union)}
    for k, q in INVENTORY.items():
        if q:
            out[k] = [[{"t": "True", "f": "False"}.get(c, c) for c in r.split("\t")] for r in psql_ct("asseta", q)]
    return out


def psql_ct(db: str, query: str, user: str = "postgres", env: tuple[str, ...] = ()) -> list[str]:
    extra = ["-h", "127.0.0.1"] if user != "postgres" else []
    p = subprocess.run(
        [
            "docker",
            "exec",
            *env,
            PG_CT,
            "psql",
            *extra,
            "-U",
            user,
            "-d",
            db,
            "-v",
            "ON_ERROR_STOP=1",
            "-qAtF",
            "\t",
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if p.returncode != 0:
        raise RuntimeError(f"psql failed: {p.stderr.strip()[:300]}")
    return [line for line in p.stdout.splitlines() if line]


def cleanup_containers() -> None:
    for ct in (PG_CT, MINIO_CT):
        subprocess.run(["docker", "rm", "-f", "-v", ct], capture_output=True, check=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-backup", action="store_true", help="keep the backup directory (default: delete)")
    a = ap.parse_args()
    guard_local()
    ev = Evidence("backup-restore", "Backup and restore (PostgreSQL asseta/keycloak/mlflow, Keycloak realm, MinIO)")
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    bk = STATE_DIR / f"backup-{stamp}"
    bk.mkdir(parents=True, mode=0o700)
    cleanup_containers()
    try:
        _drill(ev, bk)
    finally:
        cleanup_containers()
        subprocess.run(
            ["docker", "compose", "exec", "-T", "minio", "rm", "-rf", "/tmp/drill-backup"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if not a.keep_backup:
            shutil.rmtree(bk, ignore_errors=True)
        ev.say("")
        ev.say(
            f"Cleanup: removed containers {PG_CT}, {MINIO_CT} (with anonymous volumes), the mirror copy inside "
            f"the minio container and {'(kept) ' if a.keep_backup else ''}the backup directory."
        )
        left = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=asseta-drill-restore", "-q"], capture_output=True, text=True
        ).stdout.strip()
        ev.check("scratch resources removed", left == "", left or "none left")
        ev.write(
            not_simulated=[
                "Loss of the Docker host / disks: restore ran on the same host from a local backup copy; a real "
                "procedure ships backups off-host (encrypted) and restores on new hardware.",
                "Point-in-time recovery: no WAL archiving is configured; RPO equals the backup interval.",
                "Kafka and Redis are not backed up (Kafka is a transport fed from the durable outbox; Redis holds "
                "only cache/pub-sub). Traccar's own H2 DB is not backed up (devices re-register; Asseta is the system "
                "of record).",
                "Keycloak realm restore is verified via the keycloak DB dump; the REST partial export (config only, "
                "secrets masked) is taken as a readable config record but not re-imported.",
                "Restored services were not started against the restored data (verification is at data level).",
            ],
            commands=["cd backend", "uv run python ../scripts/drills/backup_restore.py"],
        )


def _drill(ev: Evidence, bk: Path) -> None:
    ev.say("### Backup")
    ev.say("")
    t_backup = time.monotonic()
    with psycopg.connect(superuser_dsn("asseta")) as snap:
        snap.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snap_id = snap.execute("SELECT pg_export_snapshot()").fetchone()[0]  # type: ignore[index]
        snap_at = snap.execute("SELECT now()").fetchone()[0]  # type: ignore[index]
        source = inventory_conn(snap)
        t0 = time.monotonic()
        with open(bk / "asseta.dump", "wb") as f:
            run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(ROOT / "compose.yaml"),
                    "exec",
                    "-T",
                    "postgres",
                    "pg_dump",
                    "-U",
                    "postgres",
                    "-Fc",
                    f"--snapshot={snap_id}",
                    "-d",
                    "asseta",
                ],
                stdout=f,
            )
        dump_s = time.monotonic() - t0
        snap.execute("COMMIT")
    size = (bk / "asseta.dump").stat().st_size
    ev.say(
        f"* `asseta`: snapshot {snap_at.isoformat(timespec='seconds')}, {len(source['counts'])} tables, "
        f"{sum(source['counts'].values())} rows, alembic `{source['alembic'][0][0]}`; pg_dump -Fc "
        f"{size / 1e6:.1f} MB in {dump_s:.1f} s"
    )
    kc_src: dict[str, int] = {}
    for db in ("keycloak", "mlflow"):
        t0 = time.monotonic()
        with open(bk / f"{db}.dump", "wb") as f:
            run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(ROOT / "compose.yaml"),
                    "exec",
                    "-T",
                    "postgres",
                    "pg_dump",
                    "-U",
                    "postgres",
                    "-Fc",
                    "-d",
                    db,
                ],
                stdout=f,
            )
        ev.say(
            f"* `{db}`: pg_dump -Fc {(bk / f'{db}.dump').stat().st_size / 1e6:.1f} MB in {time.monotonic() - t0:.1f} s"
        )
    with psycopg.connect(superuser_dsn("keycloak")) as kc:
        for name, q in KC_QUERIES.items():
            kc_src[name] = int(kc.execute(q).fetchone()[0])  # type: ignore[index]
    token = httpx.post(
        f"{KC}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ENV["KEYCLOAK_ADMIN_USER"],
            "password": ENV["KEYCLOAK_ADMIN_PASSWORD"],
        },
        timeout=30,
    ).json()["access_token"]
    export = httpx.post(
        f"{KC}/admin/realms/asseta/partial-export",
        params={"exportClients": "true", "exportGroupsAndRoles": "true"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    export.raise_for_status()
    (bk / "realm-asseta-partial-export.json").write_text(export.text)
    realm = export.json()
    ev.say(
        f"* Keycloak realm `asseta` partial export (config; secrets masked by Keycloak): "
        f"{len(realm.get('clients', []))} clients, {len(realm.get('groups', []))} top-level groups, "
        f"{len(realm.get('roles', {}).get('client', {}))} clients with roles; DB counts {kc_src}"
    )
    t0 = time.monotonic()
    mirror = (
        'mc alias set drillsrc http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && '
        + " && ".join(f"mc mirror --quiet drillsrc/{b} /tmp/drill-backup/{b}" for b in BUCKETS)
        + "; rc=$?; mc alias rm drillsrc >/dev/null; exit $rc"
    )
    compose(
        "exec",
        "-T",
        "minio",
        "sh",
        "-c",
        f"rm -rf /tmp/drill-backup && mkdir -p /tmp/drill-backup && {mirror}",
        capture=True,
    )
    compose("cp", "minio:/tmp/drill-backup", str(bk / "objects"), capture=True)
    compose("exec", "-T", "minio", "rm", "-rf", "/tmp/drill-backup", capture=True)
    objs = {b: [p for p in (bk / "objects" / b).rglob("*") if p.is_file()] for b in BUCKETS}
    ev.say(
        "* MinIO mirror (`mc mirror`): "
        + ", ".join(f"{b} {len(v)} objects / {sum(p.stat().st_size for p in v) / 1e6:.1f} MB" for b, v in objs.items())
        + f" in {time.monotonic() - t0:.1f} s"
    )
    backup_s = time.monotonic() - t_backup
    rpo = (now_utc() - snap_at).total_seconds()
    ev.say(f"* Backup total {backup_s:.1f} s; the DB snapshot was {rpo:.0f} s old when the backup finished")
    ev.say("")

    ev.say("### Restore into throwaway containers")
    ev.say("")
    t_rto = time.monotonic()
    pw = {k: secrets.token_urlsafe(18) for k in ("su", "owner", "app", "kc", "minio")}
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            PG_CT,
            "--network",
            "none",
            "-e",
            f"POSTGRES_PASSWORD={pw['su']}",
            "-e",
            f"ASSETA_OWNER_DB_PASSWORD={pw['owner']}",
            "-e",
            f"ASSETA_APP_DB_PASSWORD={pw['app']}",
            "-e",
            f"KEYCLOAK_DB_PASSWORD={pw['kc']}",
            PG_IMAGE,
        ]
    )
    ok = False
    for _ in range(120):
        p = subprocess.run(
            ["docker", "exec", PG_CT, "pg_isready", "-U", "postgres", "-d", "asseta", "-h", "127.0.0.1"],
            capture_output=True,
        )
        if p.returncode == 0:
            ok = True
            break
        time.sleep(1)
    if not ok:
        raise RuntimeError("restore container did not become ready")
    init_s = time.monotonic() - t_rto
    psql_ct("postgres", "CREATE ROLE mlflow LOGIN PASSWORD 'x'")  # role exists in production via mlflow-db-init
    for db, owner in (("asseta", "asseta_owner"), ("keycloak", "keycloak"), ("mlflow", "mlflow")):
        psql_ct("postgres", f"DROP DATABASE IF EXISTS {db}")
        psql_ct("postgres", f"CREATE DATABASE {db} OWNER {owner} TEMPLATE template0")
    run(["docker", "cp", str(bk / "asseta.dump"), f"{PG_CT}:/tmp/asseta.dump"])
    run(["docker", "cp", str(bk / "keycloak.dump"), f"{PG_CT}:/tmp/keycloak.dump"])
    run(["docker", "cp", str(bk / "mlflow.dump"), f"{PG_CT}:/tmp/mlflow.dump"])
    timings = {}
    for db in ("asseta", "keycloak", "mlflow"):
        t0 = time.monotonic()
        r = subprocess.run(
            ["docker", "exec", PG_CT, "pg_restore", "-U", "postgres", "-d", db, "--exit-on-error", f"/tmp/{db}.dump"],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        timings[db] = time.monotonic() - t0
        ev.check(
            f"pg_restore {db} (--exit-on-error)", r.returncode == 0, f"{timings[db]:.1f} s {r.stderr.strip()[:200]}"
        )
    ev.say(
        f"* Fresh PostGIS container ready (init: roles + empty DBs) in {init_s:.1f} s; pg_restore "
        + ", ".join(f"{k} {v:.1f} s" for k, v in timings.items())
    )
    restored = restored_inventory()
    diff = {t: (n, restored["counts"].get(t)) for t, n in source["counts"].items() if restored["counts"].get(t) != n}
    ev.check(
        "row counts identical for every table",
        not diff and len(restored["counts"]) == len(source["counts"]),
        f"{len(source['counts'])} tables, {sum(source['counts'].values())} rows; differences: {diff or 'none'}",
    )
    for key in ("rls", "policies", "grants", "triggers", "functions", "alembic"):
        same = [list(map(str, r)) for r in restored[key]] == source[key]
        detail = {
            "rls": lambda r: (
                f"{sum(1 for x in r if x[2] in ('t', 'True'))} tables FORCE RLS, "
                f"{sum(1 for x in r if x[1] in ('t', 'True'))} ENABLE"
            ),
            "policies": lambda r: f"{sum(int(x[1]) for x in r)} policies on {len(r)} tables",
            "grants": lambda r: f"{len(r)} role/table grant sets",
            "triggers": lambda r: f"{sum(int(x[1]) for x in r)} triggers",
            "functions": lambda r: f"{r[0][0]} functions",
            "alembic": lambda r: f"version {r[0][0]}",
        }[key](source[key])
        ev.check(f"{key} identical after restore", same, detail)
    tenants = psql_ct("asseta", "SELECT id FROM tenant ORDER BY created_at LIMIT 1")
    if tenants:
        t = tenants[0]
        probe = (
            f"BEGIN; SELECT set_config('app.scope','tenant',true), set_config('app.tenant_id','{t}',true); "
            f"SELECT count(*) FILTER (WHERE tenant_id = '{t}'), count(*) FILTER (WHERE tenant_id <> '{t}') "
            "FROM machine; COMMIT;"
        )
        own, other = psql_ct("asseta", probe, user="asseta_app", env=("-e", f"PGPASSWORD={pw['app']}"))[-1].split("\t")
        unscoped = psql_ct(
            "asseta", "SELECT count(*) FROM machine", user="asseta_app", env=("-e", f"PGPASSWORD={pw['app']}")
        )[-1]
        ev.check(
            "RLS enforced for asseta_app on the restored DB",
            other == "0" and unscoped == "0",
            f"tenant scope: own={own} other={other}; no scope set: {unscoped} rows visible",
        )
    kc_restored = {k: int(psql_ct("keycloak", q)[0]) for k, q in KC_QUERIES.items()}
    ev.check("Keycloak DB restored (realm users, groups, clients)", kc_restored == kc_src, f"{kc_restored}")

    t0 = time.monotonic()
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            MINIO_CT,
            "-p",
            "127.0.0.1::9000",
            "-e",
            "MINIO_ROOT_USER=drill",
            "-e",
            f"MINIO_ROOT_PASSWORD={pw['minio']}",
            minio_image(),
            "server",
            "/data",
        ]
    )
    port = run(["docker", "port", MINIO_CT, "9000/tcp"]).stdout.decode().strip().split(":")[-1]
    run(["docker", "cp", str(bk / "objects"), f"{MINIO_CT}:/tmp/restore"])
    restore_cmd = (
        'for i in $(seq 1 30); do mc alias set dst http://127.0.0.1:9000 drill "$MINIO_ROOT_PASSWORD" '
        ">/dev/null 2>&1 && break; sleep 1; done; "
        + " && ".join(f"mc mb -p dst/{b} >/dev/null && mc mirror --quiet /tmp/restore/{b} dst/{b}" for b in BUCKETS)
    )
    r = subprocess.run(["docker", "exec", MINIO_CT, "sh", "-c", restore_cmd], capture_output=True, text=True)
    ev.check(
        "MinIO buckets restored with mc mirror",
        r.returncode == 0,
        f"{time.monotonic() - t0:.1f} s {r.stderr.strip()[:200]}",
    )
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://127.0.0.1:{port}",
        aws_access_key_id="drill",
        aws_secret_access_key=pw["minio"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    refs = [
        r.split("\t")
        for r in psql_ct(
            "asseta",
            "SELECT object_key, sha256 FROM capture_attachment UNION ALL SELECT object_key, sha256 FROM machine_photo",
        )
    ]
    bad = []
    for key, sha in refs:
        try:
            data = s3.get_object(Bucket="asseta-evidence", Key=key)["Body"].read()
            if hashlib.sha256(data).hexdigest() != sha:
                bad.append(f"{key}: hash mismatch")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{key}: {type(exc).__name__}")
    ev.check(
        "every evidence object referenced by the restored DB exists with matching SHA-256",
        not bad and bool(refs),
        f"{len(refs)} referenced objects verified; problems: {bad[:5] or 'none'}",
    )
    mlflow_n = sum(
        1
        for _ in s3.get_paginator("list_objects_v2").paginate(Bucket="asseta-mlflow")
        for _ in (_.get("Contents") or [])
    )
    ev.check(
        "MLflow artifact bucket restored (object count)",
        mlflow_n == len(objs["asseta-mlflow"]),
        f"{mlflow_n}/{len(objs['asseta-mlflow'])}",
    )
    rto = time.monotonic() - t_rto
    ev.say(
        f"* **RTO (fresh containers → data restored and verified): {rto:.1f} s**; **RPO of this procedure: the "
        f"backup interval** (snapshot age at backup end {rpo:.0f} s; no WAL archiving)"
    )
    ev.say(f"* Backup artefacts: {', '.join(sorted(p.name for p in bk.iterdir()))}")
    (bk / "inventory.json").write_text(json.dumps(source, default=str))


KC_QUERIES = {
    "users": "SELECT count(*) FROM user_entity u JOIN realm r ON r.id = u.realm_id WHERE r.name = 'asseta'",
    "groups": "SELECT count(*) FROM keycloak_group g JOIN realm r ON r.id = g.realm_id WHERE r.name = 'asseta'",
    "clients": "SELECT count(*) FROM client c JOIN realm r ON r.id = c.realm_id WHERE r.name = 'asseta'",
}


def minio_image() -> str:
    """The exact image (digest) the stack's MinIO runs."""
    return str(json.loads(compose("config", "--format", "json", capture=True).stdout)["services"]["minio"]["image"])


if __name__ == "__main__":
    main()
