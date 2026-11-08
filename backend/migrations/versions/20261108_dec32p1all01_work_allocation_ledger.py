"""DEC-032 Phase 1: every engine hour allocated.

- `work_allocation` ("Ledger 3"): append-only (guard trigger allows only a row's status transition and decision
  stamps; no DELETE grant), tenant FORCE RLS, and a gist exclusion constraint that refuses overlapping meter ranges
  among a machine's ACTIVE entries, so the same engine hours cannot be allocated twice (needs btree_gist).
- `machine_changeover` (A3) and `daily_operational_report` (A4): append-only, tenant FORCE RLS.
- `revenue_difference.value_at_risk_amount` (A5).
- ENGINE_HOURS gains in_job_time_counts_as_customer_work (true), changeover_splits_billing (false),
  allocation_correction_requires_approval (true), unexplained_flag_amount_hours (null) and
  daily_report_evidence_required (false) as a new platform version: today's behaviour for every tenant.
- REVENUE_RECONCILIATION's platform default treatment becomes VALUE_AT_RISK (D1). A tenant with its own
  unexplained_hours_treatment keeps it.
- Existing history is backfilled from the engine ledger. If that fails (a later release jumped straight here and its
  models no longer fit this schema), the migration still succeeds and the idempotent scheduler sweep fills it.

Revision ID: dec32p1all01
Revises: setup01chk01
Create Date: 2026-11-08 09:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
import structlog
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dec32p1all01"
down_revision: str | Sequence[str] | None = "setup01chk01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = structlog.get_logger()
OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
ENGINE_KEYS = (
    '{"in_job_time_counts_as_customer_work": true, "changeover_splits_billing": false, '
    '"allocation_correction_requires_approval": true, "unexplained_flag_amount_hours": null, '
    '"daily_report_evidence_required": false}'
)
ENGINE_REASON = "Seeded platform default: DEC-032 work allocation ledger switches (behaviour unchanged; replaceable)"
REVENUE_REASON = "Seeded platform default: DEC-032 D1 unexplained hours shown as value at risk (replaceable)"
STAMPS = "ARRAY['status', 'superseded_at', 'decided_by', 'decided_at', 'decision_note']"
REPORT_STAMPS = "ARRAY['status', 'reviewed_by', 'reviewed_at', 'review_note']"


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY p_tenant ON {table} USING ({OWN} OR app_scope() = 'system') "
        f"WITH CHECK ({OWN} OR app_scope() = 'system')"
    )


def _grants(table: str, privileges: str) -> None:
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {table} FROM asseta_app; GRANT {privileges} ON {table} TO asseta_app;
          END IF;
        END $$;
    """)


def _new_platform_version(ptype: str, patch: str, reason: str, unless: str) -> None:
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
               (SELECT max(version) + 1 FROM policy_version
                 WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL),
               cur.effective_from, cur.values || '{patch}'::jsonb, '{reason}', now(), 'migration'
          FROM (SELECT policy_type, effective_from, values FROM policy_version
                 WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL
                   AND effective_from <= now()
                 ORDER BY effective_from DESC, version DESC LIMIT 1) cur
         WHERE {unless};
    """)


def _backfill() -> None:
    """Fill the ledger from the engine ledger, tenant by tenant, in one savepoint. Skipped on an empty database."""
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT NOT EXISTS (SELECT 1 FROM meter_capture)")).scalar():
        return
    from sqlalchemy.orm import Session

    from asseta.core.db import DbScope, apply_scope
    from asseta.modules.meter.allocation_models import AllocationSource
    from asseta.modules.meter.allocation_writer import AllocationSummary, sweep_tenant

    now = datetime.now(UTC)
    summary = AllocationSummary()
    try:
        with bind.begin_nested(), Session(bind=bind, join_transaction_mode="create_savepoint") as session:
            apply_scope(session, DbScope.SYSTEM, None, None)
            tenants = list(session.execute(sa.text("SELECT id FROM tenant WHERE status <> 'CLOSED'")).scalars())
            for tenant_id in tenants:
                apply_scope(session, DbScope.TENANT, tenant_id, None)
                sweep_tenant(session, tenant_id, now, summary, AllocationSource.BACKFILL)
            session.commit()
        log.info("work_allocation_backfill_completed", **summary.__dict__)
    except Exception:
        log.exception("work_allocation_backfill_failed_scheduler_will_fill")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.add_column(
        "revenue_difference", sa.Column("value_at_risk_amount", sa.Numeric(18, 4), server_default="0", nullable=False)
    )
    op.create_table(
        "machine_changeover",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("machine_id", sa.UUID(), sa.ForeignKey("machine.id"), nullable=False),
        sa.Column("capture_id", sa.UUID(), sa.ForeignKey("meter_capture.id"), nullable=False),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("job.id"), nullable=False),
        sa.Column("from_customer_id", sa.UUID(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("to_customer_id", sa.UUID(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("to_job_id", sa.UUID(), sa.ForeignKey("job.id"), nullable=True),
        sa.Column("recorded_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capture_id", name="uq_machine_changeover_capture"),
    )
    for col in ("tenant_id", "machine_id", "job_id"):
        op.create_index(op.f(f"ix_machine_changeover_{col}"), "machine_changeover", [col])
    op.create_table(
        "work_allocation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("machine_id", sa.UUID(), sa.ForeignKey("machine.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_ref", sa.UUID(), nullable=False),
        sa.Column("start_reading", sa.Numeric(14, 2), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ref", sa.UUID(), nullable=False),
        sa.Column("end_reading", sa.Numeric(14, 2), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meter_epoch", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customer.id"), nullable=True),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("job.id"), nullable=True),
        sa.Column("activity_type", sa.String(length=24), nullable=True),
        sa.Column("reason_id", sa.UUID(), sa.ForeignKey("engine_hour_reason.id"), nullable=True),
        sa.Column("classification_id", sa.UUID(), sa.ForeignKey("engine_hour_classification.id"), nullable=True),
        sa.Column("changeover_id", sa.UUID(), sa.ForeignKey("machine_changeover.id"), nullable=True),
        sa.Column("reading_review", sa.String(length=16), nullable=False),
        sa.Column("lots", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_attachment_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("origin_key", sa.String(length=120), nullable=False),
        sa.Column("origin_hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("supersedes_id", sa.UUID(), sa.ForeignKey("work_allocation.id"), nullable=True),
        sa.Column("correction_group_id", sa.UUID(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.UUID(), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("hours > 0 AND end_reading - start_reading = hours", name="ck_work_allocation_range"),
    )
    op.create_index("ix_work_allocation_machine_day", "work_allocation", ["tenant_id", "machine_id", "work_date"])
    op.create_index("ix_work_allocation_customer_day", "work_allocation", ["tenant_id", "customer_id", "work_date"])
    op.create_index("ix_work_allocation_group", "work_allocation", ["tenant_id", "correction_group_id"])
    op.create_index("ix_work_allocation_status", "work_allocation", ["tenant_id", "status"])
    op.create_index(op.f("ix_work_allocation_machine_id"), "work_allocation", ["machine_id"])
    op.create_index(op.f("ix_work_allocation_job_id"), "work_allocation", ["job_id"])
    op.create_index(op.f("ix_work_allocation_supersedes_id"), "work_allocation", ["supersedes_id"])
    op.execute("""
        ALTER TABLE work_allocation ADD CONSTRAINT ex_work_allocation_no_overlap
          EXCLUDE USING gist (tenant_id WITH =, machine_id WITH =, meter_epoch WITH =,
                              numrange(start_reading, end_reading, '[)') WITH &&)
          WHERE (status = 'ACTIVE')
    """)
    op.create_table(
        "daily_operational_report",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("machine_id", sa.UUID(), sa.ForeignKey("machine.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("opening_ref", sa.UUID(), sa.ForeignKey("meter_capture.id"), nullable=False),
        sa.Column("opening_reading", sa.Numeric(14, 2), nullable=False),
        sa.Column("closing_ref", sa.UUID(), sa.ForeignKey("meter_capture.id"), nullable=False),
        sa.Column("closing_reading", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("billable_hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("unbillable_hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("difference_hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("unbillable", postgresql.JSONB(), nullable=False),
        sa.Column("allocations", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_attachment_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("supersedes_id", sa.UUID(), sa.ForeignKey("daily_operational_report.id"), nullable=True),
        sa.Column("duplicate_of_id", sa.UUID(), sa.ForeignKey("daily_operational_report.id"), nullable=True),
        sa.Column("submitted_by", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_report_machine_date", "daily_operational_report", ["tenant_id", "machine_id", "report_date"]
    )
    op.create_index("ix_daily_report_status", "daily_operational_report", ["tenant_id", "status"])
    op.create_index(op.f("ix_daily_operational_report_machine_id"), "daily_operational_report", ["machine_id"])

    for table in ("work_allocation", "machine_changeover", "daily_operational_report"):
        _rls(table)
    op.execute(f"""
        CREATE FUNCTION guard_work_allocation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'asseta: a work allocation is never deleted' USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (to_jsonb(NEW) - {STAMPS}) IS DISTINCT FROM (to_jsonb(OLD) - {STAMPS})
             OR NOT ((OLD.status = 'PROPOSED' AND NEW.status IN ('ACTIVE', 'REJECTED'))
                     OR (OLD.status = 'ACTIVE' AND NEW.status = 'SUPERSEDED')) THEN
            RAISE EXCEPTION 'asseta: only a work allocation''s status may change (corrections supersede)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_work_allocation_guard BEFORE UPDATE OR DELETE ON work_allocation
          FOR EACH ROW EXECUTE FUNCTION guard_work_allocation();

        CREATE FUNCTION guard_machine_changeover() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'asseta: a changeover is a record of fact (append-only)'
            USING ERRCODE = 'insufficient_privilege';
        END $$;
        CREATE TRIGGER trg_machine_changeover_guard BEFORE UPDATE OR DELETE ON machine_changeover
          FOR EACH ROW EXECUTE FUNCTION guard_machine_changeover();

        CREATE FUNCTION guard_daily_report() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'asseta: a daily report is never deleted' USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (to_jsonb(NEW) - {REPORT_STAMPS}) IS DISTINCT FROM (to_jsonb(OLD) - {REPORT_STAMPS})
             OR NOT ((OLD.status = 'SUBMITTED' AND NEW.status IN ('REVIEWED', 'RETURNED', 'SUPERSEDED'))
                     OR (OLD.status = 'RETURNED' AND NEW.status = 'SUPERSEDED')) THEN
            RAISE EXCEPTION 'asseta: only a daily report''s review status may change'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_daily_report_guard BEFORE UPDATE OR DELETE ON daily_operational_report
          FOR EACH ROW EXECUTE FUNCTION guard_daily_report();
    """)
    _grants("work_allocation", "SELECT, INSERT, UPDATE")
    _grants("machine_changeover", "SELECT, INSERT")
    _grants("daily_operational_report", "SELECT, INSERT, UPDATE")
    _new_platform_version(
        "ENGINE_HOURS", ENGINE_KEYS, ENGINE_REASON, "NOT (cur.values ? 'in_job_time_counts_as_customer_work')"
    )
    _new_platform_version(
        "REVENUE_RECONCILIATION",
        '{"unexplained_hours_treatment": "VALUE_AT_RISK"}',
        REVENUE_REASON,
        "cur.values ->> 'unexplained_hours_treatment' <> 'VALUE_AT_RISK'",
    )
    _backfill()


def downgrade() -> None:
    for ptype, reason in (("ENGINE_HOURS", ENGINE_REASON), ("REVENUE_RECONCILIATION", REVENUE_REASON)):
        op.execute(f"""
            SELECT set_config('app.scope', 'system', true);
            ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
            DELETE FROM policy_version
             WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND source = 'migration' AND reason = '{reason}';
            ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        """)
    for table in ("work_allocation", "machine_changeover", "daily_operational_report"):
        op.execute(f"DROP POLICY IF EXISTS p_tenant ON {table}")
    op.execute("DROP TRIGGER IF EXISTS trg_work_allocation_guard ON work_allocation")
    op.execute("DROP FUNCTION IF EXISTS guard_work_allocation()")
    op.execute("DROP TRIGGER IF EXISTS trg_machine_changeover_guard ON machine_changeover")
    op.execute("DROP FUNCTION IF EXISTS guard_machine_changeover()")
    op.execute("DROP TRIGGER IF EXISTS trg_daily_report_guard ON daily_operational_report")
    op.execute("DROP FUNCTION IF EXISTS guard_daily_report()")
    op.drop_table("daily_operational_report")
    op.drop_table("work_allocation")
    op.drop_table("machine_changeover")
    op.drop_column("revenue_difference", "value_at_risk_amount")
