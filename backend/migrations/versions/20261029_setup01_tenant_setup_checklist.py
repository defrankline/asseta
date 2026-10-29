"""Go-live setup checklist: the owner's choices only (steps marked "not needed", "the default controls are fine",
the banner dismissed). Step progress is computed live from existing data, so nothing else is stored.

- `tenant_setup_choice`: append-only (guard trigger, no UPDATE/DELETE grant), tenant FORCE RLS (system scope for
  workers); the latest row per step/kind is the current choice (ordered by the identity `seq`).

Revision ID: setup01chk01
Revises: dec31p5ovs01
Create Date: 2026-10-29 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "setup01chk01"
down_revision: str | Sequence[str] | None = "dec31p5ovs01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tenant_setup_choice"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("step_key", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.UUID(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_setup_choice_tenant_seq", TABLE, ["tenant_id", "seq"])

    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY p_tenant ON {TABLE} USING ({own} OR app_scope() = 'system') "
        f"WITH CHECK ({own} OR app_scope() = 'system')"
    )
    op.execute(f"""
        CREATE FUNCTION guard_tenant_setup_choice() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'asseta: a setup choice is appended, never changed (undo appends a new row)'
            USING ERRCODE = 'insufficient_privilege';
        END $$;
        CREATE TRIGGER trg_{TABLE}_guard BEFORE UPDATE OR DELETE ON {TABLE}
          FOR EACH ROW EXECUTE FUNCTION guard_tenant_setup_choice();
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {TABLE} FROM asseta_app; GRANT SELECT, INSERT ON {TABLE} TO asseta_app;
            GRANT USAGE, SELECT ON SEQUENCE {TABLE}_seq_seq TO asseta_app;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute(f"""
        DROP POLICY IF EXISTS p_tenant ON {TABLE};
        DROP TRIGGER IF EXISTS trg_{TABLE}_guard ON {TABLE};
        DROP FUNCTION IF EXISTS guard_tenant_setup_choice();
    """)
    op.drop_table(TABLE)
