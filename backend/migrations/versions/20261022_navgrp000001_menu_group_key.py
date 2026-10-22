"""Side-navigation groups: every `menu` row belongs to a catalog menu group (parent -> children navigation). The
catalog sync at startup rewrites every row, so existing rows only need a placeholder until then.

Revision ID: navgrp000001
Revises: g6sec0000002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "navgrp000001"
down_revision: str | None = "g6sec0000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("menu", sa.Column("group_key", sa.String(64), nullable=False, server_default=""))
    op.alter_column("menu", "group_key", server_default=None)


def downgrade() -> None:
    op.drop_column("menu", "group_key")
