"""Index for the capture-time offline policy snapshot check (security finding F-8): snapshots issued to one device
session, by policy type and issue time.

Revision ID: f8snap000001
Revises: g7asec000001
Create Date: 2026-10-22 21:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8snap000001"
down_revision: str | Sequence[str] | None = "g7asec000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_device_policy_snapshot_device_type_issued",
        "device_policy_snapshot",
        ["device_session_id", "policy_type", "issued_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_device_policy_snapshot_device_type_issued", table_name="device_policy_snapshot")
