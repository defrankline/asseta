"""Supervisor job requests from the field: who requested the job (staff record) and what the customer asked for.

Columns only (the job table keeps its RLS policy and grants); office-created jobs leave both null.

Revision ID: jobreq000001
Revises: inboxsec00001
Create Date: 2026-10-24 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "jobreq000001"
down_revision: str | Sequence[str] | None = "inboxsec00001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("job", sa.Column("requested_by_staff_id", sa.UUID(), nullable=True))
    op.add_column("job", sa.Column("request_note", sa.Text(), nullable=True))
    op.create_foreign_key("job_requested_by_staff_id_fkey", "job", "staff_member", ["requested_by_staff_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("job_requested_by_staff_id_fkey", "job", type_="foreignkey")
    op.drop_column("job", "request_note")
    op.drop_column("job", "requested_by_staff_id")
