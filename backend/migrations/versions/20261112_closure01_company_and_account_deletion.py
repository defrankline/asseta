"""Company closure and account deletion: company_deletion_request (one active per company, readable by the company
and the platform, never deleted by the app role), tenant.deleted_at / tenant.deletion_request_id (the minimal closed
tenant row) and app_user.deleted_at (an anonymised account is never restored from a token or the Keycloak mirror).
The DATA_PROTECTION key company_deletion_waiting_days (platform-wide, 30 days) defaults in the schema; no policy rows
are written.

Revision ID: closure01
Revises: jobwin01
Create Date: 2026-11-12 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "closure01"
down_revision: str | Sequence[str] | None = "jobwin01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "company_deletion_request"
OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
PLATFORM = "app_scope() IN ('platform', 'system')"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("waiting_days", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("cancelled_by", sa.UUID(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("execute_now_by", sa.UUID(), nullable=True),
        sa.Column("execute_now_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execute_now_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_company_deletion_request_tenant_id"), TABLE, ["tenant_id"])
    op.create_index("ix_company_deletion_request_due", TABLE, ["status", "scheduled_for"])
    op.create_index(
        "uq_company_deletion_request_active",
        TABLE,
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('REQUESTED', 'IN_PROGRESS')"),
    )
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY p_access ON {TABLE} USING ({OWN} OR {PLATFORM}) WITH CHECK ({OWN} OR {PLATFORM})")
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {TABLE} FROM asseta_app; GRANT SELECT, INSERT, UPDATE ON {TABLE} TO asseta_app;
          END IF;
        END $$;
    """)
    op.add_column("tenant", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant", sa.Column("deletion_request_id", sa.UUID(), nullable=True))
    op.add_column("app_user", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("app_user", "deleted_at")
    op.drop_column("tenant", "deletion_request_id")
    op.drop_column("tenant", "deleted_at")
    op.execute(f"DROP POLICY IF EXISTS p_access ON {TABLE}")
    op.drop_index("uq_company_deletion_request_active", table_name=TABLE)
    op.drop_index("ix_company_deletion_request_due", table_name=TABLE)
    op.drop_index(op.f("ix_company_deletion_request_tenant_id"), table_name=TABLE)
    op.drop_table(TABLE)
