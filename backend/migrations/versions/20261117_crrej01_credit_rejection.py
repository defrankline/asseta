"""Owner decision: a credit sale's credit part can be rejected ("Reject credit").

`credit_invoice` gets a single rejection stamp (`rejected_at`, `rejected_by`, `rejection_reason`; the stamp and its
reason come together). The invoice stays append-only otherwise: its immutability trigger is replaced by a guard that
lets only that stamp be set, once (never cleared, never deleted). A rejected invoice is CANCELLED and its hours are
never activated. No data is written.

Revision ID: crrej01
Revises: adr8rm01
Create Date: 2026-11-17 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "crrej01"
down_revision: str | Sequence[str] | None = "adr8rm01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMPS = "ARRAY['rejected_at', 'rejected_by', 'rejection_reason']"


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_credit_invoice_immutable ON credit_invoice")
    op.add_column("credit_invoice", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("credit_invoice", sa.Column("rejected_by", sa.UUID(), nullable=True))
    op.add_column("credit_invoice", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_credit_invoice_rejection", "credit_invoice", "(rejected_at IS NULL) = (rejection_reason IS NULL)"
    )
    op.execute(f"""
        CREATE FUNCTION guard_credit_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.rejected_at IS NOT NULL OR NEW.rejected_at IS NULL
             OR (to_jsonb(NEW) - {STAMPS}) IS DISTINCT FROM (to_jsonb(OLD) - {STAMPS}) THEN
            RAISE EXCEPTION 'asseta: a credit invoice is immutable (only a single rejection stamp)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_credit_invoice_guard BEFORE UPDATE OR DELETE ON credit_invoice
          FOR EACH ROW EXECUTE FUNCTION guard_credit_invoice();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_credit_invoice_guard ON credit_invoice")
    op.execute("DROP FUNCTION IF EXISTS guard_credit_invoice()")
    op.drop_constraint("ck_credit_invoice_rejection", "credit_invoice", type_="check")
    op.drop_column("credit_invoice", "rejection_reason")
    op.drop_column("credit_invoice", "rejected_by")
    op.drop_column("credit_invoice", "rejected_at")
    op.execute("""
        CREATE TRIGGER trg_credit_invoice_immutable BEFORE UPDATE OR DELETE ON credit_invoice
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
    """)
