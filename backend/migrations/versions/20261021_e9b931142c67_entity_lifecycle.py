"""entity_lifecycle: soft deactivation metadata and optimistic-concurrency versions for managed records

Revision ID: e9b931142c67
Revises: g5sec0000001
Create Date: 2026-10-21 18:06:43.198743

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9b931142c67"
down_revision: str | Sequence[str] | None = "g5sec0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Records with history are never deleted: deactivation records who/when/why.
DEACTIVATABLE = [
    "customer",
    "expense_category",
    "geofence",
    "job_site",
    "machine",
    "machine_category",
    "operating_area",
    "staff_member",
    "tracker_model",
]
NEW_IS_ACTIVE = ["machine_category", "operating_area"]
NEW_VERSION = [
    "customer",
    "expense_category",
    "job_site",
    "machine_category",
    "operating_area",
    "rental_contract",
    "staff_member",
    "tenant",
    "tracker",
    "tracker_model",
]


def _add_backfilled(table: str, name: str, type_: sa.types.TypeEngine[object], default: str) -> None:
    """NOT NULL column: backfill existing rows through a temporary server default, then drop it (ORM owns it)."""
    op.add_column(table, sa.Column(name, type_, nullable=False, server_default=sa.text(default)))
    op.alter_column(table, name, server_default=None)


def upgrade() -> None:
    """Upgrade schema."""
    for table in NEW_IS_ACTIVE:
        _add_backfilled(table, "is_active", sa.Boolean(), "true")
    for table in NEW_VERSION:
        _add_backfilled(table, "version", sa.Integer(), "1")
    for table in DEACTIVATABLE:
        op.add_column(table, sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deactivated_by", sa.UUID(), nullable=True))
        op.add_column(table, sa.Column("deactivation_reason", sa.Text(), nullable=True))
    op.add_column("rental_contract", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rental_contract", sa.Column("closed_by", sa.UUID(), nullable=True))
    op.add_column("rental_contract", sa.Column("close_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for column in ("close_reason", "closed_by", "closed_at"):
        op.drop_column("rental_contract", column)
    for table in DEACTIVATABLE:
        for column in ("deactivation_reason", "deactivated_by", "deactivated_at"):
            op.drop_column(table, column)
    for table in NEW_VERSION:
        op.drop_column(table, "version")
    for table in NEW_IS_ACTIVE:
        op.drop_column(table, "is_active")
