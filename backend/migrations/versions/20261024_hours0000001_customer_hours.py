"""Customer hours (accountability design A, controls 3.1): walk-in customers (customer.kind), job billing mode,
hours purchases HP-<yyyy>-<nnnnn>, payment links and evidence, discounts, credit arrangements, the append-only hours
ledger, work execution allocations, transfers, cancellations and tenant reason lists. Existing customers stay
REGISTERED and existing jobs INVOICE (the behaviour before customer hours). RLS/grants/guards: hrssec000001.

Revision ID: hours0000001
Revises: jobreq000001
Create Date: 2026-10-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "hours0000001"
down_revision: str | Sequence[str] | None = "jobreq000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "hours_reason_code",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("DISCOUNT", "CREDIT", "TRANSFER", "CANCELLATION", name="reasonkind", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.UUID(), nullable=True),
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "kind", "code", name="uq_hours_reason_code"),
    )
    op.create_index(op.f("ix_hours_reason_code_tenant_id"), "hours_reason_code", ["tenant_id"], unique=False)
    op.create_table(
        "hours_sequence",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("series", sa.String(length=8), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "series", "year"),
    )
    op.create_table(
        "credit_arrangement",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_code_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PROPOSED",
                "APPROVED",
                "REJECTED",
                "WITHDRAWN",
                "REVOKED",
                name="proposalstatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("proposed_by", sa.UUID(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_credit_arrangement_dates"
        ),
        sa.CheckConstraint("limit_amount > 0", name="ck_credit_arrangement_limit"),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["currency.code"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reason_code_id"],
            ["hours_reason_code.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_arrangement_customer_id"), "credit_arrangement", ["customer_id"], unique=False)
    op.create_index(op.f("ix_credit_arrangement_tenant_id"), "credit_arrangement", ["tenant_id"], unique=False)
    op.create_table(
        "customer_discount",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("percent", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_code_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PROPOSED",
                "APPROVED",
                "REJECTED",
                "WITHDRAWN",
                "REVOKED",
                name="proposalstatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("proposed_by", sa.UUID(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_customer_discount_dates"),
        sa.CheckConstraint("percent > 0 AND percent <= 100", name="ck_customer_discount_percent"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reason_code_id"],
            ["hours_reason_code.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_discount_customer_id"), "customer_discount", ["customer_id"], unique=False)
    op.create_index(op.f("ix_customer_discount_tenant_id"), "customer_discount", ["tenant_id"], unique=False)
    op.create_table(
        "hours_purchase",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("purchase_number", sa.String(length=32), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("job_site_id", sa.UUID(), nullable=True),
        sa.Column("hours", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_card_id", sa.UUID(), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("discount_id", sa.UUID(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("effective_rate", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.UUID(), nullable=True),
        sa.Column("cancellation_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("amount >= 0 AND hourly_rate >= 0 AND effective_rate >= 0", name="ck_hours_purchase_money"),
        sa.CheckConstraint("hours > 0", name="ck_hours_purchase_hours"),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["currency.code"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer.id"],
        ),
        sa.ForeignKeyConstraint(
            ["discount_id"],
            ["customer_discount.id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_site_id"],
            ["job_site.id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"],
            ["rental_rate_policy.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "client_id", name="uq_hours_purchase_client"),
        sa.UniqueConstraint("tenant_id", "purchase_number", name="uq_hours_purchase_number"),
    )
    op.create_index(
        "ix_hours_purchase_customer_machine", "hours_purchase", ["tenant_id", "customer_id", "machine_id"], unique=False
    )
    op.create_index(op.f("ix_hours_purchase_machine_id"), "hours_purchase", ["machine_id"], unique=False)
    op.create_index(op.f("ix_hours_purchase_tenant_id"), "hours_purchase", ["tenant_id"], unique=False)
    op.create_table(
        "payment_evidence",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("attachment_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["capture_attachment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["customer_payment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", "attachment_id", name="uq_payment_evidence"),
    )
    op.create_index(op.f("ix_payment_evidence_payment_id"), "payment_evidence", ["payment_id"], unique=False)
    op.create_index(op.f("ix_payment_evidence_tenant_id"), "payment_evidence", ["tenant_id"], unique=False)
    op.create_table(
        "hours_cancellation",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("purchase_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_code_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "WITHDRAWN", name="requeststatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["hours_purchase.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reason_code_id"],
            ["hours_reason_code.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hours_cancellation_purchase_id"), "hours_cancellation", ["purchase_id"], unique=False)
    op.create_index(op.f("ix_hours_cancellation_tenant_id"), "hours_cancellation", ["tenant_id"], unique=False)
    op.create_index(
        "uq_hours_cancellation_pending",
        "hours_cancellation",
        ["purchase_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'APPROVED')"),
    )
    op.create_table(
        "hours_payment_allocation",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("purchase_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_hours_allocation_amount"),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["customer_payment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["hours_purchase.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hours_payment_allocation_payment_id"), "hours_payment_allocation", ["payment_id"], unique=False
    )
    op.create_index(
        op.f("ix_hours_payment_allocation_purchase_id"), "hours_payment_allocation", ["purchase_id"], unique=False
    )
    op.create_index(
        op.f("ix_hours_payment_allocation_tenant_id"), "hours_payment_allocation", ["tenant_id"], unique=False
    )
    op.create_table(
        "hours_transfer",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("purchase_id", sa.UUID(), nullable=False),
        sa.Column("from_machine_id", sa.UUID(), nullable=False),
        sa.Column("to_machine_id", sa.UUID(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_code_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "WITHDRAWN", name="requeststatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("from_machine_id <> to_machine_id", name="ck_hours_transfer_machines"),
        sa.CheckConstraint("hours > 0", name="ck_hours_transfer_hours"),
        sa.ForeignKeyConstraint(
            ["from_machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["hours_purchase.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reason_code_id"],
            ["hours_reason_code.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_machine_id"],
            ["machine.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "client_id", name="uq_hours_transfer_client"),
    )
    op.create_index(op.f("ix_hours_transfer_purchase_id"), "hours_transfer", ["purchase_id"], unique=False)
    op.create_index(op.f("ix_hours_transfer_tenant_id"), "hours_transfer", ["tenant_id"], unique=False)
    op.create_table(
        "work_execution_allocation",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("billable_hours", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("exception_id", sa.UUID(), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("billable_hours >= 0", name="ck_wea_hours"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer.id"],
        ),
        sa.ForeignKeyConstraint(
            ["exception_id"],
            ["job_exception.id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_work_execution_allocation_job"),
    )
    op.create_index(
        op.f("ix_work_execution_allocation_customer_id"), "work_execution_allocation", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_work_execution_allocation_machine_id"), "work_execution_allocation", ["machine_id"], unique=False
    )
    op.create_index(
        op.f("ix_work_execution_allocation_tenant_id"), "work_execution_allocation", ["tenant_id"], unique=False
    )
    op.create_table(
        "hours_ledger_entry",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("purchase_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum(
                "ACTIVATED",
                "CONSUMED",
                "TRANSFER_OUT",
                "TRANSFER_IN",
                "EXPIRED",
                "REVERSAL",
                name="ledgerentrytype",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("hours", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "activation_source",
            sa.Enum("PAYMENT", "CREDIT", name="activationsource", native_enum=False, length=16),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("allocation_id", sa.UUID(), nullable=True),
        sa.Column("transfer_id", sa.UUID(), nullable=True),
        sa.Column("cancellation_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(entry_type = 'ACTIVATED') = (activation_source IS NOT NULL)", name="ck_hours_ledger_activation"
        ),
        sa.CheckConstraint("hours > 0", name="ck_hours_ledger_hours"),
        sa.ForeignKeyConstraint(
            ["allocation_id"],
            ["work_execution_allocation.id"],
        ),
        sa.ForeignKeyConstraint(
            ["cancellation_id"],
            ["hours_cancellation.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer.id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["customer_payment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["hours_purchase.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["hours_transfer.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hours_ledger_customer_machine",
        "hours_ledger_entry",
        ["tenant_id", "customer_id", "machine_id"],
        unique=False,
    )
    op.create_index(op.f("ix_hours_ledger_entry_allocation_id"), "hours_ledger_entry", ["allocation_id"], unique=False)
    op.create_index(op.f("ix_hours_ledger_entry_job_id"), "hours_ledger_entry", ["job_id"], unique=False)
    op.create_index(op.f("ix_hours_ledger_entry_machine_id"), "hours_ledger_entry", ["machine_id"], unique=False)
    op.create_index("ix_hours_ledger_purchase", "hours_ledger_entry", ["purchase_id", "occurred_at"], unique=False)
    op.add_column(
        "customer",
        sa.Column(
            "kind",
            sa.Enum("REGISTERED", "WALK_IN", name="customerkind", native_enum=False, length=16),
            server_default="REGISTERED",
            nullable=False,
        ),
    )
    op.add_column(
        "job",
        sa.Column(
            "billing_mode",
            sa.Enum("PREPAID_HOURS", "INVOICE", name="billingmode", native_enum=False, length=16),
            server_default="INVOICE",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job", "billing_mode")
    op.drop_column("customer", "kind")
    op.drop_index("ix_hours_ledger_purchase", table_name="hours_ledger_entry")
    op.drop_index(op.f("ix_hours_ledger_entry_machine_id"), table_name="hours_ledger_entry")
    op.drop_index(op.f("ix_hours_ledger_entry_job_id"), table_name="hours_ledger_entry")
    op.drop_index(op.f("ix_hours_ledger_entry_allocation_id"), table_name="hours_ledger_entry")
    op.drop_index("ix_hours_ledger_customer_machine", table_name="hours_ledger_entry")
    op.drop_table("hours_ledger_entry")
    op.drop_index(op.f("ix_work_execution_allocation_tenant_id"), table_name="work_execution_allocation")
    op.drop_index(op.f("ix_work_execution_allocation_machine_id"), table_name="work_execution_allocation")
    op.drop_index(op.f("ix_work_execution_allocation_customer_id"), table_name="work_execution_allocation")
    op.drop_table("work_execution_allocation")
    op.drop_index(op.f("ix_hours_transfer_tenant_id"), table_name="hours_transfer")
    op.drop_index(op.f("ix_hours_transfer_purchase_id"), table_name="hours_transfer")
    op.drop_table("hours_transfer")
    op.drop_index(op.f("ix_hours_payment_allocation_tenant_id"), table_name="hours_payment_allocation")
    op.drop_index(op.f("ix_hours_payment_allocation_purchase_id"), table_name="hours_payment_allocation")
    op.drop_index(op.f("ix_hours_payment_allocation_payment_id"), table_name="hours_payment_allocation")
    op.drop_table("hours_payment_allocation")
    op.drop_index(
        "uq_hours_cancellation_pending",
        table_name="hours_cancellation",
        postgresql_where=sa.text("status IN ('PENDING', 'APPROVED')"),
    )
    op.drop_index(op.f("ix_hours_cancellation_tenant_id"), table_name="hours_cancellation")
    op.drop_index(op.f("ix_hours_cancellation_purchase_id"), table_name="hours_cancellation")
    op.drop_table("hours_cancellation")
    op.drop_index(op.f("ix_payment_evidence_tenant_id"), table_name="payment_evidence")
    op.drop_index(op.f("ix_payment_evidence_payment_id"), table_name="payment_evidence")
    op.drop_table("payment_evidence")
    op.drop_index(op.f("ix_hours_purchase_tenant_id"), table_name="hours_purchase")
    op.drop_index(op.f("ix_hours_purchase_machine_id"), table_name="hours_purchase")
    op.drop_index("ix_hours_purchase_customer_machine", table_name="hours_purchase")
    op.drop_table("hours_purchase")
    op.drop_index(op.f("ix_customer_discount_tenant_id"), table_name="customer_discount")
    op.drop_index(op.f("ix_customer_discount_customer_id"), table_name="customer_discount")
    op.drop_table("customer_discount")
    op.drop_index(op.f("ix_credit_arrangement_tenant_id"), table_name="credit_arrangement")
    op.drop_index(op.f("ix_credit_arrangement_customer_id"), table_name="credit_arrangement")
    op.drop_table("credit_arrangement")
    op.drop_table("hours_sequence")
    op.drop_index(op.f("ix_hours_reason_code_tenant_id"), table_name="hours_reason_code")
    op.drop_table("hours_reason_code")
