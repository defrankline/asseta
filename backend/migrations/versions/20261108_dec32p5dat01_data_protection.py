"""DEC-032 Phase 5: tenant data export jobs, balance verification runs (append-only, read by the platform as counts)
and the tenant go-live marker that locks the data reset tool; policy type DATA_PROTECTION (sweep off by default).

Revision ID: dec32p5dat01
Revises: dec32p3ind01
Create Date: 2026-11-08 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dec32p5dat01"
down_revision: str | Sequence[str] | None = "dec32p3ind01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPORT = "tenant_data_export"
RUN = "balance_verification_run"
OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"


def _tables() -> None:
    op.create_table(
        EXPORT,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=300), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("table_count", sa.Integer(), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_data_export_tenant_id"), EXPORT, ["tenant_id"])
    op.create_index("ix_tenant_data_export_status", EXPORT, ["status", "requested_at"])
    op.create_index(
        "uq_tenant_data_export_active",
        EXPORT,
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )
    op.create_table(
        RUN,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("checked_count", sa.Integer(), nullable=False),
        sa.Column("mismatch_count", sa.Integer(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("findings_truncated", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_balance_verification_tenant_time", RUN, ["tenant_id", "started_at"])


def _security() -> None:
    for table in (EXPORT, RUN):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {table} USING ({OWN} OR app_scope() = 'system') "
            f"WITH CHECK ({OWN} OR app_scope() = 'system')"
        )
    op.execute(f"CREATE POLICY p_platform_read ON {RUN} FOR SELECT USING (app_scope() = 'platform')")
    op.execute(f"""
        CREATE TRIGGER trg_{RUN}_immutable BEFORE UPDATE OR DELETE ON {RUN}
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {RUN} FROM asseta_app; GRANT SELECT, INSERT ON {RUN} TO asseta_app;
            REVOKE ALL ON {EXPORT} FROM asseta_app; GRANT SELECT, INSERT, UPDATE ON {EXPORT} TO asseta_app;
          END IF;
        END $$;
    """)


def upgrade() -> None:
    _tables()
    _security()
    op.add_column("tenant", sa.Column("live_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant", sa.Column("live_marked_by", sa.UUID(), nullable=True))
    op.add_column("tenant", sa.Column("live_note", sa.Text(), nullable=True))
    op.execute("""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), 'DATA_PROTECTION', 'PLATFORM', NULL, NULL, 1,
               TIMESTAMPTZ '2000-01-01 00:00:00+00',
               '{"balance_verification_enabled": false, "balance_verification_interval_days": 7,
                 "data_export_retention_days": 7}'::jsonb,
               'Seeded platform default: balance verification sweep off (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version
                           WHERE policy_type = 'DATA_PROTECTION' AND scope = 'PLATFORM');
    """)


def downgrade() -> None:
    op.execute("""
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version WHERE policy_type = 'DATA_PROTECTION';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
    """)
    op.drop_column("tenant", "live_note")
    op.drop_column("tenant", "live_marked_by")
    op.drop_column("tenant", "live_at")
    op.drop_table(RUN)
    op.drop_table(EXPORT)
