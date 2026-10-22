"""Remove throwaway tenants from a LOCAL docker-compose stack (destructive; dev only).

Usage (from backend/, with the stack's API and workers stopped):
  uv run python scripts/purge_tenants.py ../.env --name-prefix "Field E2E " --dry-run  # report only, rolls back
  uv run python scripts/purge_tenants.py ../.env --name-prefix "Field E2E " --yes      # by display-name prefix
  uv run python scripts/purge_tenants.py ../.env --tenant <uuid> [--tenant <uuid>] --yes

Unlike demo_reset.py (which empties everything), this keeps every other tenant intact. In ONE transaction, as the
superuser with row triggers off (immutability guards would otherwise refuse): deletes every row whose `tenant_id`
is a purged tenant across all tenant-scoped tables (partitions included), their roles' permission/template rows,
the tenant rows, and app users who belonged only to purged tenants. It then checks EVERY foreign key for dangling
references and rolls back if any exist, so nothing kept can point at removed data. Keycloak: deletes the purged
tenants' `/tenants/<id>` groups and any `/tenants/*` group whose tenant no longer exists in the database.
Refuses to run unless the database and Keycloak are on localhost and `--yes` is given.
"""

import argparse
import contextlib
import sys
import uuid
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_reset import TIMEOUT, admin_headers, read_env

DANGLING_FKS = """
SELECT c.conrelid::regclass::text AS child, a.attname AS col, c.confrelid::regclass::text AS parent,
       af.attname AS parent_col
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = c.confkey[1]
WHERE c.contype = 'f' AND array_length(c.conkey, 1) = 1 AND c.connamespace = 'public'::regnamespace
  AND NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid = c.conrelid)
"""


def tenant_tables(conn: psycopg.Connection) -> list[str]:
    """Tables with a tenant_id column; partitioned parents only (deleting from them reaches the partitions)."""
    return [
        r[0]
        for r in conn.execute(
            "SELECT c.table_name FROM information_schema.columns c JOIN pg_class k ON k.relname = c.table_name "
            "WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id' AND k.relkind IN ('r', 'p') "
            "AND NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid = k.oid) AND c.table_name <> 'tenant'"
        )
    ]


def dangling(conn: psycopg.Connection) -> list[str]:
    found = []
    for child, col, parent, parent_col in conn.execute(DANGLING_FKS).fetchall():
        n = conn.execute(
            f'SELECT count(*) FROM {child} x WHERE x."{col}" IS NOT NULL '  # noqa: S608 - catalog identifiers
            f'AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p."{parent_col}" = x."{col}")'
        ).fetchone()
        if n and n[0]:
            found.append(f"{child}.{col} -> {parent}.{parent_col}: {n[0]}")
    return found


class DryRunRollback(Exception):
    """Raised inside the transaction to undo a dry run after counting."""


def purge_database(env: dict[str, str], ids: list[uuid.UUID], dry_run: bool) -> dict[str, int]:
    port = env.get("ASSETA_PG_PORT", "5433")
    dsn = f"postgresql://postgres:{env['POSTGRES_SUPERUSER_PASSWORD']}@localhost:{port}/asseta"
    counts: dict[str, int] = {}
    with contextlib.suppress(DryRunRollback):  # a dry run counts, then rolls back
        _purge(dsn, ids, counts, dry_run)
    return counts


def _purge(dsn: str, ids: list[uuid.UUID], counts: dict[str, int], dry_run: bool) -> None:
    with psycopg.connect(dsn) as conn, conn.transaction():
        conn.execute("SET LOCAL session_replication_role = replica")  # row triggers (guards, FK checks) off
        conn.execute("SELECT set_config('app.scope', 'system', true)")
        users = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT user_id FROM tenant_membership m WHERE m.tenant_id = ANY(%s) AND NOT EXISTS "
                "(SELECT 1 FROM tenant_membership o WHERE o.user_id = m.user_id AND NOT o.tenant_id = ANY(%s)) "
                "AND NOT EXISTS (SELECT 1 FROM platform_membership p WHERE p.user_id = m.user_id)",
                (ids, ids),
            )
        ]
        conn.execute(
            "DELETE FROM role_permission WHERE role_id IN (SELECT id FROM role WHERE tenant_id = ANY(%s))", (ids,)
        )
        for tid in ids:
            conn.execute("DELETE FROM role_template_grant WHERE group_path LIKE %s", (f"/tenants/{tid}/%",))
        for table in tenant_tables(conn):
            n = conn.execute(f"DELETE FROM {table} WHERE tenant_id = ANY(%s)", (ids,)).rowcount  # noqa: S608
            if n:
                counts[table] = n
        counts["tenant"] = conn.execute("DELETE FROM tenant WHERE id = ANY(%s)", (ids,)).rowcount
        conn.execute("DELETE FROM notification_profile WHERE user_id = ANY(%s)", (users,))
        counts["app_user"] = conn.execute("DELETE FROM app_user WHERE id = ANY(%s)", (users,)).rowcount
        problems = dangling(conn)
        if problems:
            detail = "\n  ".join(problems)
            raise SystemExit(f"refusing (rolled back): dangling references would remain:\n  {detail}")
        if dry_run:
            raise DryRunRollback


def purge_keycloak(env: dict[str, str], ids: list[uuid.UUID]) -> int:
    kc = env.get("ASSETA_PUBLIC_KEYCLOAK_URL", "http://localhost:8080")
    if not kc.startswith(("http://localhost", "http://127.0.0.1")):
        raise SystemExit(f"refusing: Keycloak {kc} is not local")
    port = env.get("ASSETA_PG_PORT", "5433")
    dsn = f"postgresql://postgres:{env['POSTGRES_SUPERUSER_PASSWORD']}@localhost:{port}/asseta"
    with psycopg.connect(dsn) as conn:
        live = {str(r[0]) for r in conn.execute("SELECT id FROM tenant")}
    base, h = f"{kc}/admin/realms/asseta", admin_headers(kc, env)
    root = httpx.get(f"{base}/group-by-path/tenants", headers=h, timeout=TIMEOUT)
    if root.status_code != 200:
        return 0
    deleted = 0
    children = httpx.get(f"{base}/groups/{root.json()['id']}/children", params={"max": 1000}, headers=h).json()
    for g in children:
        if g["name"] in {str(i) for i in ids} or g["name"] not in live:
            httpx.delete(f"{base}/groups/{g['id']}", headers=h, timeout=TIMEOUT).raise_for_status()
            deleted += 1
    return deleted


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("env_file")
    p.add_argument("--tenant", action="append", type=uuid.UUID, default=[])
    p.add_argument("--name-prefix")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="count what would be removed, then roll back")
    a = p.parse_args()
    if not (a.yes or a.dry_run):
        raise SystemExit("refusing: destructive; pass --yes (or --dry-run to only report)")
    env = read_env(a.env_file)
    port = env.get("ASSETA_PG_PORT", "5433")
    dsn = f"postgresql://postgres:{env['POSTGRES_SUPERUSER_PASSWORD']}@localhost:{port}/asseta"
    ids = list(a.tenant)
    if a.name_prefix:
        if len(a.name_prefix.strip()) < 4:
            raise SystemExit("refusing: --name-prefix is too broad")
        with psycopg.connect(dsn) as conn:
            rows = conn.execute("SELECT id FROM tenant WHERE display_name LIKE %s", (f"{a.name_prefix}%",))
            ids += [r[0] for r in rows]
    db = purge_database(env, ids, a.dry_run) if ids else {}
    if a.dry_run:
        print(f"DRY RUN (nothing changed) tenants={len(ids)} rows={sum(db.values())} detail={db}")
        return
    groups = purge_keycloak(env, ids)
    print(f"PURGE OK tenants={len(ids)} keycloak_groups={groups} rows={sum(db.values())} detail={db}")


if __name__ == "__main__":
    main()
