"""Entity lifecycle security: managed master data is deactivated, never deleted. Revoke DELETE from the
application role on every lifecycle-managed table (FORCE RLS and tenant policies from earlier revisions stay).

Revision ID: l1sec0000001
Revises: e9b931142c67
"""

from collections.abc import Sequence

from alembic import op

revision: str = "l1sec0000001"
down_revision: str | None = "e9b931142c67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Explicit privileges per lifecycle-managed table (no DELETE: history is kept, records are deactivated/closed).
GRANTS: dict[str, str] = {
    "customer": "SELECT, INSERT, UPDATE",
    "staff_member": "SELECT, INSERT, UPDATE",
    "job_site": "SELECT, INSERT, UPDATE",
    "machine_category": "SELECT, INSERT, UPDATE",
    "operating_area": "SELECT, INSERT, UPDATE",
    "rental_contract": "SELECT, INSERT, UPDATE",
    "job": "SELECT, INSERT, UPDATE",
    "geofence": "SELECT, INSERT, UPDATE",
    "tracker_model": "SELECT, INSERT, UPDATE",
    "expense_category": "SELECT, INSERT, UPDATE",
}


def upgrade() -> None:
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
    """)


def downgrade() -> None:
    # Privileges are deliberately not widened again on downgrade: re-granting DELETE on master data would
    # reopen hard deletes of records with history. The previous revisions never relied on it.
    pass
