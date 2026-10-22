"""Gate 7 security: FORCE RLS + explicit grants (never DELETE) on push_device, notification_routing and
notification_delivery, with guards.

- push_device: only the owning user (any request scope incl. the self-service `user` scope) or the SYSTEM worker;
  owner/token/created_at immutable; a device may be (re)bound only to no tenant or the current tenant scope.
- notification_routing: like notification_preference (own rows + the tenant default in the tenant's scope).
- notification_delivery: written by the SYSTEM worker only; readable in its own context; content immutable and
  only PENDING rows change.

Revision ID: g7asec000001
Revises: g7a1c0000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g7asec000001"
down_revision: str | None = "g7a1c0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("push_device", "notification_routing", "notification_delivery")
GRANTS = dict.fromkeys(TABLES, "SELECT, INSERT, UPDATE")
SYSTEM = "app_scope() = 'system'"
ACTOR = "app_actor_id()"
OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
SELF = f"(app_scope() IN ('tenant', 'platform', 'user') AND user_id = {ACTOR})"
BINDABLE = "(tenant_id IS NULL OR (app_scope() = 'tenant' AND tenant_id = app_tenant_id()))"
POLICIES: dict[str, list[str]] = {
    "push_device": [
        f"CREATE POLICY p_read ON push_device FOR SELECT USING ({SYSTEM} OR {SELF})",
        f"CREATE POLICY p_insert ON push_device FOR INSERT WITH CHECK ({SYSTEM} OR ({SELF} AND {BINDABLE}))",
        f"CREATE POLICY p_update ON push_device FOR UPDATE USING ({SYSTEM} OR {SELF}) WITH CHECK ({SYSTEM} OR {SELF})",
    ],
    "notification_routing": [
        "CREATE POLICY p_owner ON notification_routing USING ({c}) WITH CHECK ({c})".format(
            c=f"{SYSTEM} OR ({OWN} AND (user_id = {ACTOR} OR user_id IS NULL))"
            f" OR (app_scope() = 'platform' AND tenant_id IS NULL AND user_id = {ACTOR})"
        )
    ],
    "notification_delivery": [
        f"CREATE POLICY p_read ON notification_delivery FOR SELECT USING ({SYSTEM} OR {OWN}"
        " OR (app_scope() = 'platform' AND tenant_id IS NULL))",
        f"CREATE POLICY p_write ON notification_delivery FOR INSERT WITH CHECK ({SYSTEM})",
        f"CREATE POLICY p_update ON notification_delivery FOR UPDATE USING ({SYSTEM}) WITH CHECK ({SYSTEM})",
    ],
}
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION guard_push_device() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR NEW.user_id <> OLD.user_id OR NEW.token_sha256 <> OLD.token_sha256
             OR NEW.created_at <> OLD.created_at THEN
            {DENY};
          END IF;
          IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id AND NEW.tenant_id IS NOT NULL
             AND app_scope() <> 'system' AND NEW.tenant_id IS DISTINCT FROM app_tenant_id() THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_notification_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['status','attempts','next_attempt_at','last_error','provider',
                                        'provider_message_id','sent_at','updated_at'];
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'PENDING'
             OR (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_push_device_guard BEFORE UPDATE OR DELETE ON push_device
          FOR EACH ROW EXECUTE FUNCTION guard_push_device();
        CREATE TRIGGER trg_notification_delivery_guard BEFORE UPDATE OR DELETE ON notification_delivery
          FOR EACH ROW EXECUTE FUNCTION guard_notification_delivery();
    """)
    for t in TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        for stmt in POLICIES[t]:
            op.execute(stmt)
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
    """)


def downgrade() -> None:
    for t in TABLES:
        for name in ("p_read", "p_insert", "p_update", "p_owner", "p_write"):
            op.execute(f"DROP POLICY IF EXISTS {name} ON {t}")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    op.execute("""
        DROP TRIGGER IF EXISTS trg_push_device_guard ON push_device;
        DROP TRIGGER IF EXISTS trg_notification_delivery_guard ON notification_delivery;
        DROP FUNCTION IF EXISTS guard_push_device();
        DROP FUNCTION IF EXISTS guard_notification_delivery();
    """)
