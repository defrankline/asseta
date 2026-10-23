"""Supervisor sync inbox: `sync_revision` on the field records a supervisor creates (meter captures and their
exceptions, meter resets, work log, acknowledgements, expenses, fuel events, cash collections and handovers) so
devices can pull their own records by delta after sync; index for capture -> exception lookups.

Revision ID: inbox0000001
Revises: f8snap000001
Create Date: 2026-10-23 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "inbox0000001"
down_revision: str | Sequence[str] | None = "f8snap000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [
    "meter_capture",
    "job_exception",
    "meter_reset_event",
    "job_activity",
    "customer_acknowledgement",
    "expense",
    "fuel_event",
    "customer_payment",
    "cash_handover",
]


def upgrade() -> None:
    """Upgrade schema."""
    for t in TABLES:
        op.add_column(
            t,
            sa.Column(
                "sync_revision", sa.BigInteger(), server_default=sa.text("nextval('sync_revision_seq')"), nullable=False
            ),
        )
        op.create_index(op.f(f"ix_{t}_sync_revision"), t, ["sync_revision"], unique=False)
    op.create_index(op.f("ix_job_exception_meter_capture_id"), "job_exception", ["meter_capture_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_job_exception_meter_capture_id"), table_name="job_exception")
    for t in reversed(TABLES):
        op.drop_index(op.f(f"ix_{t}_sync_revision"), table_name=t)
        op.drop_column(t, "sync_revision")
