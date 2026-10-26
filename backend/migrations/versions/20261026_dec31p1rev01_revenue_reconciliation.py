"""DEC-031 Phase 1 revenue reconciliation: the tenant's revenue reason list, revenue differences (one per machine,
period and currency) with their adjustments, approvals of non-revenue work-log time, plus the REVENUE_RECONCILIATION
platform default policy — switched OFF, so every tenant keeps today's behaviour until its owner opts in (replaceable
configuration). Adjustments are append-only; an approval takes one decision (PROPOSED -> APPROVED/REJECTED).

Security: tenant-owned FORCE RLS and explicit grants (never DELETE). A revenue difference's evidence (machine, period,
currency, opening) is immutable; its computed figures may be refreshed and its explanation/decision recorded only
while it is OPEN or EXPLANATION_PROPOSED; an EXPLAINED / CONFIRMED / CLEARED difference is final (guard trigger).

Revision ID: dec31p1rev01
Revises: dec31p3dep01
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dec31p1rev01"
down_revision: str | Sequence[str] | None = "dec31p3dep01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS = {
    "revenue_reason": "SELECT, INSERT, UPDATE",  # tenant list: edits/deactivation, never deleted
    "revenue_difference": "SELECT, INSERT, UPDATE",  # guard: figures/decision until final
    "revenue_difference_adjustment": "SELECT, INSERT",  # append-only
    "non_revenue_approval": "SELECT, INSERT, UPDATE",  # guard: one decision (PROPOSED -> APPROVED/REJECTED)
}
SEED = (
    '{"enabled": false, "non_revenue_activity_types": ["MOBILIZATION"], '
    '"deduct_non_revenue_from_working_hours": false, "deduct_non_revenue_from_prepaid_hours": false, '
    '"non_revenue_requires_approval": true, "unexplained_hours_treatment": "EXPECT_REVENUE", '
    '"unexplained_hours_rate_source": "MACHINE_RATE_CARD", "unexplained_hours_rate": null, '
    '"period": "WEEK", "tolerance_percent": "5", "tolerance_amount": null, "case_threshold_amount": null, '
    '"basis": "INVOICED_OR_PREPAID", "recheck_days": 28}'
)
_IMMUTABLE = [
    "tenant_id",
    "machine_id",
    "period_kind",
    "period_key",
    "period_start",
    "period_end",
    "local_from",
    "local_to",
    "job_id",
    "currency",
    "policy_version",
    "opened_at",
]
_NEW = ", ".join(f"NEW.{c}" for c in _IMMUTABLE)
_OLD = ", ".join(f"OLD.{c}" for c in _IMMUTABLE)


def upgrade() -> None:
    op.create_table(
        "revenue_reason",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.UUID(), nullable=True),
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_revenue_reason_code"),
    )
    op.create_index(op.f("ix_revenue_reason_tenant_id"), "revenue_reason", ["tenant_id"], unique=False)
    op.create_table(
        "revenue_difference",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("period_kind", sa.String(length=8), nullable=False),
        sa.Column("period_key", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_from", sa.Date(), nullable=False),
        sa.Column("local_to", sa.Date(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("expected_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("in_progress_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("attributed_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("difference", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("customer_work_hours", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("non_revenue_hours", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unexplained_hours", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unexplained_expected_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_id", sa.UUID(), nullable=True),
        sa.Column("explanation_note", sa.Text(), nullable=True),
        sa.Column("explained_by", sa.UUID(), nullable=True),
        sa.Column("explained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "status IN ('OPEN', 'EXPLANATION_PROPOSED', 'EXPLAINED', 'CONFIRMED', 'CLEARED')",
            name="ck_revenue_difference_status",
        ),
        sa.CheckConstraint("period_kind IN ('DAY', 'WEEK', 'JOB')", name="ck_revenue_difference_period_kind"),
        sa.ForeignKeyConstraint(["case_id"], ["anomaly_case.id"]),
        sa.ForeignKeyConstraint(["currency"], ["currency.code"]),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["revenue_reason.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "machine_id", "period_key", "currency", name="uq_revenue_difference_period"),
    )
    op.create_index(op.f("ix_revenue_difference_machine_id"), "revenue_difference", ["machine_id"], unique=False)
    op.create_index("ix_revenue_difference_status", "revenue_difference", ["tenant_id", "status"], unique=False)
    op.create_table(
        "revenue_difference_adjustment",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("difference_id", sa.UUID(), nullable=False),
        sa.Column("previous_difference", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("new_difference", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cause_type", sa.String(length=40), nullable=False),
        sa.Column("cause_id", sa.UUID(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["difference_id"], ["revenue_difference.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_revenue_difference_adjustment_difference_id"),
        "revenue_difference_adjustment",
        ["difference_id"],
        unique=False,
    )
    op.create_table(
        "non_revenue_approval",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("activity_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("activity_type", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hours", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("reason_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("proposed_by", sa.UUID(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("status IN ('PROPOSED', 'APPROVED', 'REJECTED')", name="ck_non_revenue_approval_status"),
        sa.ForeignKeyConstraint(["activity_id"], ["job_activity.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["revenue_reason.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_non_revenue_approval_activity_id"), "non_revenue_approval", ["activity_id"], unique=False)
    op.create_index(op.f("ix_non_revenue_approval_machine_id"), "non_revenue_approval", ["machine_id"], unique=False)
    op.create_index("ix_non_revenue_approval_status", "non_revenue_approval", ["tenant_id", "status"], unique=False)
    op.create_index(
        "uq_non_revenue_approval_live",
        "non_revenue_approval",
        ["tenant_id", "activity_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PROPOSED', 'APPROVED')"),
    )
    _secure()


def _secure() -> None:
    op.execute(f"""
        CREATE FUNCTION guard_revenue_difference() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status NOT IN ('OPEN', 'EXPLANATION_PROPOSED')
             OR ROW({_NEW}) IS DISTINCT FROM ROW({_OLD}) THEN
            RAISE EXCEPTION 'asseta: a decided revenue difference is final and its evidence is immutable'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_revenue_difference_guard BEFORE UPDATE OR DELETE ON revenue_difference
          FOR EACH ROW EXECUTE FUNCTION guard_revenue_difference();
        CREATE TRIGGER trg_revenue_reason_no_delete BEFORE DELETE ON revenue_reason
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        CREATE TRIGGER trg_revenue_difference_adjustment_immutable BEFORE UPDATE OR DELETE
          ON revenue_difference_adjustment FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        CREATE TRIGGER trg_non_revenue_approval_guard BEFORE UPDATE OR DELETE ON non_revenue_approval
          FOR EACH ROW EXECUTE FUNCTION guard_engine_hours_decision();
    """)
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for t in GRANTS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), 'REVENUE_RECONCILIATION', 'PLATFORM', NULL, NULL, 1,
               TIMESTAMPTZ '2000-01-01 00:00:00+00', '{SEED}'::jsonb,
               'Seeded platform default: revenue reconciliation off (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version
                           WHERE policy_type = 'REVENUE_RECONCILIATION' AND scope = 'PLATFORM');
    """)


def downgrade() -> None:
    op.execute("""
        DROP POLICY IF EXISTS p_tenant ON non_revenue_approval;
        DROP POLICY IF EXISTS p_tenant ON revenue_difference_adjustment;
        DROP POLICY IF EXISTS p_tenant ON revenue_difference;
        DROP POLICY IF EXISTS p_tenant ON revenue_reason;
        DROP TRIGGER IF EXISTS trg_revenue_difference_guard ON revenue_difference;
        DROP TRIGGER IF EXISTS trg_revenue_reason_no_delete ON revenue_reason;
        DROP FUNCTION IF EXISTS guard_revenue_difference();
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version WHERE policy_type = 'REVENUE_RECONCILIATION';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
    """)
    op.drop_table("non_revenue_approval")
    op.drop_table("revenue_difference_adjustment")
    op.drop_index("ix_revenue_difference_status", table_name="revenue_difference")
    op.drop_index(op.f("ix_revenue_difference_machine_id"), table_name="revenue_difference")
    op.drop_table("revenue_difference")
    op.drop_index(op.f("ix_revenue_reason_tenant_id"), table_name="revenue_reason")
    op.drop_table("revenue_reason")
