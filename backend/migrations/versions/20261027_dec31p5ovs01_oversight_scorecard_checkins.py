"""DEC-031 Phase 5 (is everyone on top of things?): site check-ins (M3) and the OVERSIGHT policy's new keys.

- `site_checkin`: a supervisor's GPS check-in at the site (sync op SITE_CHECKIN or the web); append-only (guard
  trigger, no UPDATE/DELETE grant), tenant FORCE RLS (system scope for sweeps). Rows exist only while a tenant
  switches site check-ins on.
- OVERSIGHT gains scorecard_enabled (false), near_threshold_percent (90), repeat_pattern_count (null),
  repeat_pattern_window_days (30), repeat_pattern_items, unbilled_after_days (null), idle_after_days (null),
  site_checkin_required (false), site_checkin_times ([]), site_checkin_window_minutes (60) and
  site_checkin_max_distance_m (null) as a new platform version (previous values carried over): every tenant keeps
  today's behaviour until its owner opts in (replaceable configuration).

Revision ID: dec31p5ovs01
Revises: dec31p4hrs01
Create Date: 2026-10-27 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dec31p5ovs01"
down_revision: str | Sequence[str] | None = "dec31p4hrs01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "site_checkin"
NEW_KEYS = (
    '{"scorecard_enabled": false, "near_threshold_percent": "90", "repeat_pattern_count": null, '
    '"repeat_pattern_window_days": 30, '
    '"repeat_pattern_items": ["CASH_DIFFERENCE", "REVENUE_DIFFERENCE", "MISSING_DAILY_REPORT"], '
    '"unbilled_after_days": null, "idle_after_days": null, "site_checkin_required": false, '
    '"site_checkin_times": [], "site_checkin_window_minutes": 60, "site_checkin_max_distance_m": null}'
)
SEED_REASON = "Seeded platform default: DEC-031 scorecard, unbilled/idle checks and site check-ins off (replaceable)"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("staff_member_id", sa.UUID(), sa.ForeignKey("staff_member.id"), nullable=False),
        sa.Column("recorded_by", sa.UUID(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gps_status", sa.String(length=20), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("job_site_id", sa.UUID(), sa.ForeignKey("job_site.id"), nullable=True),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("job.id"), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("device_session_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "client_id", name="uq_site_checkin_client"),
    )
    op.create_index(op.f(f"ix_{TABLE}_tenant_id"), TABLE, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{TABLE}_job_site_id"), TABLE, ["job_site_id"], unique=False)
    op.create_index("ix_site_checkin_staff_time", TABLE, ["tenant_id", "staff_member_id", "captured_at"])

    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY p_tenant ON {TABLE} USING ({own} OR app_scope() = 'system') "
        f"WITH CHECK ({own} OR app_scope() = 'system')"
    )
    op.execute(f"""
        CREATE FUNCTION guard_site_checkin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'asseta: a site check-in is a record of fact (append-only)'
            USING ERRCODE = 'insufficient_privilege';
        END $$;
        CREATE TRIGGER trg_{TABLE}_guard BEFORE UPDATE OR DELETE ON {TABLE}
          FOR EACH ROW EXECUTE FUNCTION guard_site_checkin();
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {TABLE} FROM asseta_app; GRANT SELECT, INSERT ON {TABLE} TO asseta_app;
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
               (SELECT max(version) + 1 FROM policy_version
                 WHERE policy_type = 'OVERSIGHT' AND scope = 'PLATFORM' AND tenant_id IS NULL),
               cur.effective_from, cur.values || '{NEW_KEYS}'::jsonb, '{SEED_REASON}', now(), 'migration'
          FROM (SELECT policy_type, effective_from, values FROM policy_version
                 WHERE policy_type = 'OVERSIGHT' AND scope = 'PLATFORM' AND tenant_id IS NULL
                   AND effective_from <= now()
                 ORDER BY effective_from DESC, version DESC LIMIT 1) cur
         WHERE NOT (cur.values ? 'scorecard_enabled');
    """)


def downgrade() -> None:
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version
         WHERE policy_type = 'OVERSIGHT' AND scope = 'PLATFORM' AND source = 'migration'
           AND reason = '{SEED_REASON}';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        DROP POLICY IF EXISTS p_tenant ON {TABLE};
        DROP TRIGGER IF EXISTS trg_{TABLE}_guard ON {TABLE};
        DROP FUNCTION IF EXISTS guard_site_checkin();
    """)
    op.drop_table(TABLE)
