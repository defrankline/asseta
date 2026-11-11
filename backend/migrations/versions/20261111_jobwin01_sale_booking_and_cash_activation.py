"""Sell hours and book the job in one step: job.hours_purchase_id (the sale a job was booked with); approved jobs on
one machine conflict only when their planned windows overlap (exclusion constraint ex_job_machine_window, btree_gist)
while a machine still runs one job at a time (uq_job_machine_running); payment_auto_verification records why the
system verified a cash payment of an hours sale (CUSTOMER_HOURS cash_activation; RLS, FORCE RLS, append-only).
The new CUSTOMER_HOURS keys default in the schema to today's behaviour; no policy rows are written.

Revision ID: jobwin01
Revises: dec33pc01
Create Date: 2026-11-11 16:55:17.242226

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "jobwin01"
down_revision: str | Sequence[str] | None = "dec33pc01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
TABLE = "payment_auto_verification"
# A job's planned window; a missing (or not-after-start) planned end leaves the window open.
WINDOW = (
    "tstzrange(planned_start, CASE WHEN planned_end IS NULL OR planned_end <= planned_start "
    "THEN 'infinity'::timestamptz ELSE planned_end END, '[)')"
)


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("handover_id", sa.UUID(), nullable=True),
        sa.Column("custodian_staff_id", sa.UUID(), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["custodian_staff_id"], ["staff_member.id"]),
        sa.ForeignKeyConstraint(["handover_id"], ["cash_handover.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["customer_payment.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_payment_auto_verification"),
    )
    op.create_index(op.f("ix_payment_auto_verification_handover_id"), TABLE, ["handover_id"], unique=False)
    op.create_index(op.f("ix_payment_auto_verification_tenant_id"), TABLE, ["tenant_id"], unique=False)
    op.add_column("job", sa.Column("hours_purchase_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_job_hours_purchase_id"), "job", ["hours_purchase_id"], unique=False)
    op.create_foreign_key("job_hours_purchase_id_fkey", "job", "hours_purchase", ["hours_purchase_id"], ["id"])
    # One running job per machine (START), and approved/running jobs may not overlap in their planned windows.
    op.create_index(
        "uq_job_machine_running", "job", ["machine_id"], unique=True, postgresql_where=sa.text("status = 'IN_PROGRESS'")
    )
    op.execute(f"""
        ALTER TABLE job ADD CONSTRAINT ex_job_machine_window
          EXCLUDE USING gist (tenant_id WITH =, machine_id WITH =, ({WINDOW}) WITH &&)
          WHERE (status IN ('APPROVED', 'IN_PROGRESS'))
    """)
    op.drop_index("uq_job_machine_active", table_name="job")
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY p_tenant ON {TABLE} USING ({OWN} OR app_scope() = 'system') "
        f"WITH CHECK ({OWN} OR app_scope() = 'system')"
    )
    op.execute(f"""
        CREATE TRIGGER trg_{TABLE}_immutable BEFORE UPDATE OR DELETE ON {TABLE}
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {TABLE} FROM asseta_app; GRANT SELECT, INSERT ON {TABLE} TO asseta_app;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    # Fails (unique violation) while a machine has more than one approved job: cancel or complete them first.
    op.create_index(
        "uq_job_machine_active",
        "job",
        ["machine_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED', 'IN_PROGRESS')"),
    )
    op.execute("ALTER TABLE job DROP CONSTRAINT IF EXISTS ex_job_machine_window")
    op.drop_index("uq_job_machine_running", table_name="job")
    op.drop_constraint("job_hours_purchase_id_fkey", "job", type_="foreignkey")
    op.drop_index(op.f("ix_job_hours_purchase_id"), table_name="job")
    op.drop_column("job", "hours_purchase_id")
    op.execute(f"DROP POLICY IF EXISTS p_tenant ON {TABLE}")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable ON {TABLE}")
    op.drop_index(op.f("ix_payment_auto_verification_tenant_id"), table_name=TABLE)
    op.drop_index(op.f("ix_payment_auto_verification_handover_id"), table_name=TABLE)
    op.drop_table(TABLE)
