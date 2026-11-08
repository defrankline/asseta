"""DEC-032 A4: engine-hour reasons get a sync revision, so phones receive the unbillable-reason list incrementally
(deactivations included) and can submit a daily report without an online refresh.

Revision ID: dec32p1all03
Revises: dec32p1all02
Create Date: 2026-11-08 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dec32p1all03"
down_revision: str | Sequence[str] | None = "dec32p1all02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "engine_hour_reason"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "sync_revision", sa.BigInteger(), server_default=sa.text("nextval('sync_revision_seq')"), nullable=False
        ),
    )
    op.create_index(op.f(f"ix_{TABLE}_sync_revision"), TABLE, ["sync_revision"], unique=False)
    op.execute(f"""
        CREATE TRIGGER trg_{TABLE}_sync_revision BEFORE UPDATE ON {TABLE}
          FOR EACH ROW EXECUTE FUNCTION bump_sync_revision();
    """)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_sync_revision ON {TABLE}")
    op.drop_index(op.f(f"ix_{TABLE}_sync_revision"), table_name=TABLE)
    op.drop_column(TABLE, "sync_revision")
