"""DEC-032: the phone model on a device session, shown on Administration -> Devices when the app reports it.

Revision ID: dec32fx3dev01
Revises: dec32p4mgt01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dec32fx3dev01"
down_revision: str | Sequence[str] | None = "dec32p4mgt01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("device_session", sa.Column("device_model", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("device_session", "device_model")
