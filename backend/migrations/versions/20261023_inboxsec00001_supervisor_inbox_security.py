"""Supervisor sync inbox: bump `sync_revision` on every update of the mutable field records (review, decision,
verification, supersession) so the change reaches the device in the next delta pull.

Triggers fire alphabetically, so each table's evidence guard (`trg_<t>_guard`) still compares the unbumped row
before `trg_<t>_sync_revision` assigns the new revision. Append-only tables (work log, acknowledgements, fuel) never
update and keep their insert revision. No new tables: RLS and grants are unchanged.

Revision ID: inboxsec00001
Revises: inbox0000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "inboxsec00001"
down_revision: str | None = "inbox0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MUTABLE = ["meter_capture", "job_exception", "meter_reset_event", "expense", "customer_payment", "cash_handover"]


def upgrade() -> None:
    for t in MUTABLE:
        op.execute(
            f"CREATE TRIGGER trg_{t}_sync_revision BEFORE UPDATE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION bump_sync_revision()"
        )


def downgrade() -> None:
    for t in MUTABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_sync_revision ON {t}")
