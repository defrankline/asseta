"""DEC-030 gap pass: offline cash retention requests (client id, idempotent per tenant) and the daily remittance
cut-off flag (`cash.remittance_cutoff_hour`): one append-only row per custodian per tenant-local day.

Security: tenant-owned FORCE RLS, explicit grants (SELECT, INSERT only), evidence immutable (reject_mutation).

Revision ID: gaps00000001
Revises: enghrs000001
Create Date: 2026-10-25 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "gaps00000001"
down_revision: str | Sequence[str] | None = "enghrs000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "cash_remittance_overdue"


def upgrade() -> None:
    op.add_column("cash_retention", sa.Column("client_id", sa.UUID(), nullable=True))
    op.create_unique_constraint("uq_cash_retention_client", "cash_retention", ["tenant_id", "client_id"])
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("staff_member_id", sa.UUID(), sa.ForeignKey("staff_member.id"), nullable=False),
        sa.Column("local_day", sa.Date(), nullable=False),
        sa.Column("cutoff_hour", sa.Integer(), nullable=False),
        sa.Column("amounts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("flagged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "staff_member_id", "local_day", name="uq_cash_remittance_overdue_day"),
        sa.CheckConstraint("cutoff_hour BETWEEN 0 AND 23", name="ck_cash_remittance_overdue_hour"),
    )
    op.create_index(op.f(f"ix_{TABLE}_tenant_id"), TABLE, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{TABLE}_staff_member_id"), TABLE, ["staff_member_id"], unique=False)
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY p_tenant ON {TABLE} USING ({own} OR app_scope() = 'system') "
        f"WITH CHECK ({own} OR app_scope() = 'system')"
    )
    op.execute(
        f"CREATE TRIGGER trg_{TABLE}_immutable BEFORE UPDATE OR DELETE ON {TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
    )
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {TABLE} FROM asseta_app; GRANT SELECT, INSERT ON {TABLE} TO asseta_app;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS p_tenant ON {TABLE}")
    op.drop_index(op.f(f"ix_{TABLE}_staff_member_id"), table_name=TABLE)
    op.drop_index(op.f(f"ix_{TABLE}_tenant_id"), table_name=TABLE)
    op.drop_table(TABLE)
    op.drop_constraint("uq_cash_retention_client", "cash_retention", type_="unique")
    op.drop_column("cash_retention", "client_id")
