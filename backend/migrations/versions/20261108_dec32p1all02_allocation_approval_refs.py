"""DEC-032 A1: the approval reference on a work allocation (engine-hour classification, non-revenue approval or
correction). Written with the entry, so the guard trigger needs no change; the scheduler sweep supersedes existing
entries that gain a reference.

Revision ID: dec32p1all02
Revises: dec32p1all01
Create Date: 2026-11-08 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dec32p1all02"
down_revision: str | Sequence[str] | None = "dec32p1all01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("work_allocation", sa.Column("approval_ref_type", sa.String(length=32), nullable=True))
    op.add_column(
        "work_allocation",
        sa.Column("approval_ref_ids", postgresql.ARRAY(sa.UUID()), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("work_allocation", "approval_ref_ids")
    op.drop_column("work_allocation", "approval_ref_type")
