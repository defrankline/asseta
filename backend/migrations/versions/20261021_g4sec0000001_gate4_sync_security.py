"""Gate 4: sync revision triggers, RLS for sync tables, client operation guard, DEVICE_SYNC policy seed.

Revision ID: g4sec0000001
Revises: 383028d2e368
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g4sec0000001"
down_revision: str | None = "383028d2e368"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYNCED = ["job", "machine", "job_site", "customer", "rental_contract", "staff_member", "machine_assignment"]
TABLES = ["device_session", "client_operation", "device_policy_snapshot", "blob_upload_session", "blob_chunk"]
SEED = '{"offline_grant_hours": 72, "snapshot_validity_hours": 24, "max_batch_operations": 100, "clock_skew_alert_seconds": 300}'


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION bump_sync_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN NEW.sync_revision := nextval('sync_revision_seq'); RETURN NEW; END $$;
        CREATE FUNCTION guard_client_operation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'QUARANTINED'
             AND (to_jsonb(NEW) - 'attempts') IS DISTINCT FROM (to_jsonb(OLD) - 'attempts') THEN
            RAISE EXCEPTION 'asseta: client operation outcome is immutable (only quarantined ops are replayed)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_client_operation_guard BEFORE UPDATE OR DELETE ON client_operation
          FOR EACH ROW EXECUTE FUNCTION guard_client_operation();
    """)
    for t in SYNCED:
        op.execute(
            f"CREATE TRIGGER trg_{t}_sync_revision BEFORE UPDATE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION bump_sync_revision()"
        )
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for t in TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            GRANT SELECT, INSERT, UPDATE ON {", ".join(TABLES)} TO asseta_app;
            GRANT DELETE ON blob_chunk TO asseta_app;
            GRANT USAGE, SELECT ON SEQUENCE sync_revision_seq TO asseta_app;
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,
                                    reason, created_at, source)
        SELECT gen_random_uuid(), 'DEVICE_SYNC', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
               '{SEED}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version WHERE policy_type = 'DEVICE_SYNC' AND scope = 'PLATFORM');
    """)


def downgrade() -> None:
    for t in SYNCED:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_sync_revision ON {t}")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_client_operation_guard ON client_operation;"
        "DROP FUNCTION IF EXISTS guard_client_operation(); DROP FUNCTION IF EXISTS bump_sync_revision();"
    )
    for t in TABLES:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {t}; ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;"
            f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"
        )
