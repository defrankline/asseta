"""Reset a LOCAL docker-compose stack to a clean demo baseline (destructive; dev only).

Usage (from backend/, with the stack's API and workers stopped):
  uv run python scripts/demo_reset.py ../.env --keep walkthrough.owner@asseta.local --yes

- Keycloak realm `asseta`: deletes every user except the `--keep` emails, every `/tenants/*` role group, and leftover
  throwaway clients (`smoke-*`, `field-e2e-*`). Platform role groups and the realm's own clients are kept.
- Application DB: empties every business table (tenants, fleet, telemetry, jobs, billing, audit, outbox, mandates...)
  while keeping reference data: currencies, the permission/menu catalog and the platform-default entitlement and
  policy versions (re-seeded from the same source the tests use). Run `docker compose run --rm migrate` afterwards to
  re-bootstrap the telemetry gateway, then start the API (its startup sync rebuilds the Keycloak role mirror).
Refuses to run unless the database host is localhost and `--yes` is given.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from asseta.modules.policy.schemas import SEED_DEFAULTS

TIMEOUT = 30.0
KEEP_TABLES = {"currency", "alembic_version", "spatial_ref_sys", "permission", "menu"}
THROWAWAY_CLIENT_PREFIXES = ("smoke-", "field-e2e-")
SEED_ENTITLEMENT = """INSERT INTO entitlement_policy (id, tenant_id, version, effective_from, grace_days,
  suspend_after_days, past_due_access, suspended_access, cancelled_access, reason, created_at) VALUES
  (gen_random_uuid(), NULL, 1, DATE '2000-01-01', 7, 30, 'FULL', 'READ_ONLY', 'READ_ONLY',
   'Seeded platform default (replaceable configuration)', now())"""
SEED_POLICY = """INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
  values, reason, created_at, source) VALUES (gen_random_uuid(), %s, 'PLATFORM', NULL, NULL, 1,
  TIMESTAMPTZ '2000-01-01 00:00:00+00', %s::jsonb, 'Seeded platform default (replaceable configuration)', now(),
  'migration')"""


def read_env(path: str) -> dict[str, str]:
    return dict(
        line.split("=", 1) for line in Path(path).read_text().splitlines() if "=" in line and not line.startswith("#")
    )


def admin_headers(kc: str, env: dict[str, str]) -> dict[str, str]:
    r = httpx.post(
        f"{kc}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": env["KEYCLOAK_ADMIN_USER"],
            "password": env["KEYCLOAK_ADMIN_PASSWORD"],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def reset_keycloak(env: dict[str, str], keep: set[str]) -> dict[str, int]:
    kc = env.get("ASSETA_PUBLIC_KEYCLOAK_URL", "http://localhost:8080")
    if not kc.startswith(("http://localhost", "http://127.0.0.1")):
        raise SystemExit(f"refusing: Keycloak {kc} is not local")
    base, h = f"{kc}/admin/realms/asseta", admin_headers(kc, env)
    users = httpx.get(f"{base}/users", params={"max": 1000, "briefRepresentation": "true"}, headers=h).json()
    kept = [u for u in users if (u.get("email") or u.get("username", "")).lower() in keep]
    if len(kept) != len(keep):
        raise SystemExit("refusing: a --keep account was not found in the realm")
    deleted_users = 0
    for u in users:
        if u not in kept:
            httpx.delete(f"{base}/users/{u['id']}", headers=h, timeout=TIMEOUT).raise_for_status()
            deleted_users += 1
    deleted_groups = 0
    root = httpx.get(f"{base}/group-by-path/tenants", headers=h, timeout=TIMEOUT)
    if root.status_code == 200:
        children = httpx.get(
            f"{base}/groups/{root.json()['id']}/children", params={"max": 1000}, headers=h, timeout=TIMEOUT
        ).json()
        for g in children:
            httpx.delete(f"{base}/groups/{g['id']}", headers=h, timeout=TIMEOUT).raise_for_status()
            deleted_groups += 1
    deleted_clients = 0
    for c in httpx.get(f"{base}/clients", params={"max": 1000}, headers=h, timeout=TIMEOUT).json():
        if str(c["clientId"]).startswith(THROWAWAY_CLIENT_PREFIXES):
            httpx.delete(f"{base}/clients/{c['id']}", headers=h, timeout=TIMEOUT).raise_for_status()
            deleted_clients += 1
    return {"users": deleted_users, "tenant_groups": deleted_groups, "clients": deleted_clients}


def reset_database(env: dict[str, str]) -> int:
    port = env.get("ASSETA_PG_PORT", "5433")
    dsn = f"postgresql://asseta_owner:{env['ASSETA_OWNER_DB_PASSWORD']}@localhost:{port}/asseta"
    with psycopg.connect(dsn) as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT tablename = ANY(%s) "
                "AND tablename NOT IN (SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid)",
                (sorted(KEEP_TABLES),),
            )
        ]
        conn.execute(f"TRUNCATE {', '.join(tables)} CASCADE")
        conn.execute("SELECT set_config('app.scope', 'system', true)")
        conn.execute(SEED_ENTITLEMENT)
        for ptype, values in SEED_DEFAULTS.items():
            conn.execute(SEED_POLICY, (ptype.value, json.dumps(values)))
    return len(tables)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("envfile")
    p.add_argument("--keep", action="append", required=True, help="email of a Keycloak user to keep (repeatable)")
    p.add_argument("--yes", action="store_true", help="confirm the destructive reset")
    a = p.parse_args()
    if not a.yes:
        raise SystemExit("refusing without --yes")
    env = read_env(a.envfile)
    kc = reset_keycloak(env, {k.lower() for k in a.keep})
    tables = reset_database(env)
    print(f"RESET OK keycloak={kc} tables_emptied={tables} kept={sorted(a.keep)}")


if __name__ == "__main__":
    main()
