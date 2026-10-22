"""Gate 6D security: FORCE RLS, explicit grants (never UPDATE or DELETE) and append-only guards on `prediction`,
`inference_audit` and `model_drift`.

* `prediction`: platform/system scopes read and insert; a tenant may read **only its own SURFACED rows** — shadow,
  below-threshold and insufficient-data predictions are platform-only (prompt.md §7: shadow models never produce
  user-facing findings).
* `inference_audit`, `model_drift`: platform/system only.

Revision ID: g6dsec000001
Revises: g6d1c0000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g6dsec000001"
down_revision: str | None = "g6d1c0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("prediction", "inference_audit", "model_drift")


def upgrade() -> None:
    platform = "app_scope() IN ('platform', 'system')"
    surfaced = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id() AND decision_state = 'SURFACED')"
    for t in TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{t}_immutable BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY p_platform ON {t} USING ({platform}) WITH CHECK ({platform})")
    op.execute(f"CREATE POLICY p_tenant_surfaced ON prediction FOR SELECT USING ({surfaced})")
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT SELECT, INSERT ON {t} TO asseta_app;" for t in TABLES)
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS p_tenant_surfaced ON prediction")
    for t in TABLES:
        op.execute(
            f"DROP POLICY IF EXISTS p_platform ON {t}; DROP TRIGGER IF EXISTS trg_{t}_immutable ON {t};"
            f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"
        )
