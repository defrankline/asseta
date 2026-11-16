"""ADR-008: machine reports and credit invoices.

- `credit_invoice` (CI-<yyyy>-<nnnnn>, one per order with a CREDIT line) and `credit_invoice_payment` (payments linked
  to it): append-only (no UPDATE/DELETE: what was paid and the status are derived from the linked payments).
- `machine_report` (MR-<yyyy>-<nnnnn>) and `machine_report_line`: a report's only change is its single decision
  (SUBMITTED -> APPROVED | REJECTED with the decision stamps, guard trigger); lines are append-only. One SUBMITTED
  report per machine and one SUBMITTED/APPROVED report per reading (partial unique indexes).
- `hours_ledger_entry.machine_report_id`: CONSUMED entries of an approved report.
Every table has tenant FORCE RLS. The new CUSTOMER_HOURS keys (field_credit_sales, report_hours_scope,
machine_report_reminder_days) and EXPENSE_CAPTURE.fuel_enabled default in the schema; no policy rows are written, and
no tenant data is written (each tenant's default machine-report reasons come from onboarding or the one-off script
backend/scripts/seed_machine_report_reasons.py).

Revision ID: mrep01
Revises: closure01
Create Date: 2026-11-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mrep01"
down_revision: str | Sequence[str] | None = "closure01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
TABLES = ("credit_invoice", "credit_invoice_payment", "machine_report", "machine_report_line")
STAMPS = "ARRAY['status', 'decided_by', 'decided_at', 'decision_note']"


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


def upgrade() -> None:
    op.create_table(
        "credit_invoice",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("purchase_id", sa.UUID(), sa.ForeignKey("hours_purchase.id"), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("machine_id", sa.UUID(), sa.ForeignKey("machine.id"), nullable=False),
        sa.Column("currency", sa.String(length=3), sa.ForeignKey("currency.code"), nullable=False),
        sa.Column("hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "invoice_number", name="uq_credit_invoice_number"),
        sa.UniqueConstraint("purchase_id", name="uq_credit_invoice_purchase"),
        sa.CheckConstraint("amount > 0 AND unit_price >= 0 AND hours >= 0", name="ck_credit_invoice_amounts"),
    )
    op.create_index("ix_credit_invoice_customer", "credit_invoice", ["tenant_id", "customer_id"])
    op.create_index("ix_credit_invoice_due", "credit_invoice", ["tenant_id", "due_date"])
    op.create_table(
        "credit_invoice_payment",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), sa.ForeignKey("credit_invoice.id"), nullable=False),
        sa.Column("payment_id", sa.UUID(), sa.ForeignKey("customer_payment.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_credit_invoice_payment_payment"),
        sa.CheckConstraint("amount > 0", name="ck_credit_invoice_payment_amount"),
    )
    op.create_index(op.f("ix_credit_invoice_payment_tenant_id"), "credit_invoice_payment", ["tenant_id"])
    op.create_index(op.f("ix_credit_invoice_payment_invoice_id"), "credit_invoice_payment", ["invoice_id"])

    op.create_table(
        "machine_report",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("report_number", sa.String(length=32), nullable=False),
        sa.Column("machine_id", sa.UUID(), sa.ForeignKey("machine.id"), nullable=False),
        sa.Column("capture_id", sa.UUID(), sa.ForeignKey("meter_capture.id"), nullable=False),
        sa.Column("start_source", sa.String(length=16), nullable=False),
        sa.Column("start_ref", sa.UUID(), nullable=False),
        sa.Column("start_reading", sa.Numeric(14, 2), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_reading", sa.Numeric(14, 2), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meter_epoch", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("corrects_id", sa.UUID(), sa.ForeignKey("machine_report.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("submitted_by", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "report_number", name="uq_machine_report_number"),
        sa.CheckConstraint("hours > 0 AND end_reading - start_reading = hours", name="ck_machine_report_range"),
    )
    op.create_index(op.f("ix_machine_report_machine_id"), "machine_report", ["machine_id"])
    op.create_index(op.f("ix_machine_report_corrects_id"), "machine_report", ["corrects_id"])
    op.create_index("ix_machine_report_machine", "machine_report", ["tenant_id", "machine_id", "submitted_at"])
    op.create_index("ix_machine_report_status", "machine_report", ["tenant_id", "status"])
    op.create_index(
        "uq_machine_report_submitted",
        "machine_report",
        ["tenant_id", "machine_id"],
        unique=True,
        postgresql_where=sa.text("status = 'SUBMITTED'"),
    )
    op.create_index(
        "uq_machine_report_reading",
        "machine_report",
        ["capture_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('SUBMITTED', 'APPROVED')"),
    )
    op.create_table(
        "machine_report_line",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("report_id", sa.UUID(), sa.ForeignKey("machine_report.id"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customer.id"), nullable=True),
        sa.Column("reason_id", sa.UUID(), sa.ForeignKey("engine_hour_reason.id"), nullable=True),
        sa.Column("hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "line_no", name="uq_machine_report_line_no"),
        sa.CheckConstraint("hours > 0", name="ck_machine_report_line_hours"),
        sa.CheckConstraint(
            "(kind = 'CUSTOMER' AND customer_id IS NOT NULL AND reason_id IS NULL) OR "
            "(kind = 'NON_PRODUCTIVE' AND customer_id IS NULL AND reason_id IS NOT NULL AND note IS NOT NULL)",
            name="ck_machine_report_line_kind",
        ),
    )
    op.create_index(op.f("ix_machine_report_line_report_id"), "machine_report_line", ["report_id"])
    op.create_index("ix_machine_report_line_customer", "machine_report_line", ["tenant_id", "customer_id"])

    op.add_column("hours_ledger_entry", sa.Column("machine_report_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "hours_ledger_entry_machine_report_id_fkey",
        "hours_ledger_entry",
        "machine_report",
        ["machine_report_id"],
        ["id"],
    )
    op.create_index(op.f("ix_hours_ledger_entry_machine_report_id"), "hours_ledger_entry", ["machine_report_id"])

    for table in TABLES:
        _rls(table)
    op.execute(f"""
        CREATE FUNCTION guard_machine_report() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'asseta: a machine report is never deleted' USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (to_jsonb(NEW) - {STAMPS}) IS DISTINCT FROM (to_jsonb(OLD) - {STAMPS})
             OR NOT (OLD.status = 'SUBMITTED' AND NEW.status IN ('APPROVED', 'REJECTED')) THEN
            RAISE EXCEPTION 'asseta: only a machine report''s single decision may change it'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_machine_report_guard BEFORE UPDATE OR DELETE ON machine_report
          FOR EACH ROW EXECUTE FUNCTION guard_machine_report();
    """)
    for table in ("credit_invoice", "credit_invoice_payment", "machine_report_line"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
              FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        """)
        _grants(table, "SELECT, INSERT")
    # Payments lock their invoice (SELECT .. FOR UPDATE needs the UPDATE privilege); the trigger still refuses changes.
    _grants("credit_invoice", "SELECT, INSERT, UPDATE")
    _grants("machine_report", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_index(op.f("ix_hours_ledger_entry_machine_report_id"), table_name="hours_ledger_entry")
    op.drop_constraint("hours_ledger_entry_machine_report_id_fkey", "hours_ledger_entry", type_="foreignkey")
    op.drop_column("hours_ledger_entry", "machine_report_id")
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS p_tenant ON {table}")
    for table in ("credit_invoice", "credit_invoice_payment", "machine_report_line"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
    op.execute("DROP TRIGGER IF EXISTS trg_machine_report_guard ON machine_report")
    op.execute("DROP FUNCTION IF EXISTS guard_machine_report()")
    op.drop_table("machine_report_line")
    op.drop_table("machine_report")
    op.drop_table("credit_invoice_payment")
    op.drop_table("credit_invoice")
