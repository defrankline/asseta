"""Gate 6B/6C security: FORCE RLS and explicit grants (never DELETE) on the ML tables, immutability of definitions,
snapshots, evaluations, approvals and readiness, the guarded `model_version` status graph (plus: ACTIVE needs a
passing evaluation and an APPROVE), and the seeded platform inference switch.

* Tenant-scoped (`feature_snapshot`): the owning tenant (its RLS scope) and system workers read/insert.
* Governance (`model_version`, `model_evaluation`, `model_approval`, `model_readiness`): platform/system write;
  a tenant may read only its own rows.
* Platform reference (`feature_definition`, `ml_setting`): readable from every scope, written by platform/system.

Revision ID: g6sec0000002
Revises: g6b1c0000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g6sec0000002"
down_revision: str | None = "g6b1c0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS: dict[str, str] = {
    "feature_definition": "SELECT, INSERT",
    "feature_snapshot": "SELECT, INSERT",
    "model_version": "SELECT, INSERT, UPDATE",  # guard: status graph only, everything else frozen
    "model_evaluation": "SELECT, INSERT",
    "model_approval": "SELECT, INSERT",
    "model_readiness": "SELECT, INSERT",
    "ml_setting": "SELECT, INSERT, UPDATE",
}
IMMUTABLE = ["feature_definition", "feature_snapshot", "model_evaluation", "model_approval", "model_readiness"]
TENANT_OWNED = ["feature_snapshot"]
GOVERNANCE = ["model_version", "model_evaluation", "model_approval", "model_readiness"]
REFERENCE = ["feature_definition", "ml_setting"]
TRANSITIONS = [
    ("TRAINED", "EVALUATED"),
    ("TRAINED", "REJECTED"),
    ("TRAINED", "DISABLED"),
    ("EVALUATED", "APPROVED"),
    ("EVALUATED", "DEPLOYED_SHADOW"),
    ("EVALUATED", "REJECTED"),
    ("EVALUATED", "RETIRED"),
    ("EVALUATED", "DISABLED"),
    ("APPROVED", "DEPLOYED_SHADOW"),
    ("APPROVED", "DEPLOYED_ACTIVE"),
    ("APPROVED", "REJECTED"),
    ("APPROVED", "RETIRED"),
    ("APPROVED", "DISABLED"),
    ("DEPLOYED_SHADOW", "DEPLOYED_ACTIVE"),
    ("DEPLOYED_SHADOW", "RETIRED"),
    ("DEPLOYED_SHADOW", "DISABLED"),
    ("DEPLOYED_ACTIVE", "RETIRED"),
    ("DEPLOYED_ACTIVE", "DISABLED"),
    ("RETIRED", "DEPLOYED_SHADOW"),  # rollback
    ("RETIRED", "DEPLOYED_ACTIVE"),  # rollback (approval + passing evaluation re-checked below)
    ("RETIRED", "DISABLED"),
]
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def upgrade() -> None:
    pairs = ", ".join(f"('{a}','{b}')" for a, b in TRANSITIONS)
    op.execute(f"""
        CREATE FUNCTION guard_model_version() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['status','status_changed_at','deployed_at','lock_version'];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'TRAINED' THEN
              RAISE EXCEPTION 'asseta: a model version starts as TRAINED' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
          END IF;
          IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: model version lineage is immutable' USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF NEW.status <> OLD.status AND (OLD.status, NEW.status) NOT IN ({pairs}) THEN
            RAISE EXCEPTION 'asseta: model transition % -> % is not permitted', OLD.status, NEW.status
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF NEW.status = 'DEPLOYED_ACTIVE' AND OLD.status <> 'DEPLOYED_ACTIVE' AND (
               NOT EXISTS (SELECT 1 FROM model_evaluation e WHERE e.model_version_id = NEW.id AND e.passed)
               OR NOT EXISTS (SELECT 1 FROM model_approval a WHERE a.model_version_id = NEW.id
                                AND a.action = 'APPROVE')) THEN
            RAISE EXCEPTION 'asseta: active deployment needs a passing evaluation and an approval'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_model_version_guard BEFORE INSERT OR UPDATE OR DELETE ON model_version
          FOR EACH ROW EXECUTE FUNCTION guard_model_version();
    """)
    for t in IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER trg_{t}_immutable BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    platform = "app_scope() IN ('platform', 'system')"
    for t in GRANTS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
    for t in TENANT_OWNED:
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    for t in GOVERNANCE:
        op.execute(f"CREATE POLICY p_platform ON {t} USING ({platform}) WITH CHECK ({platform})")
        op.execute(f"CREATE POLICY p_tenant_read ON {t} FOR SELECT USING ({own})")
    for t in REFERENCE:
        op.execute(f"CREATE POLICY p_read ON {t} FOR SELECT USING (true)")
        op.execute(f"CREATE POLICY p_insert ON {t} FOR INSERT WITH CHECK ({platform})")
    op.execute(f"CREATE POLICY p_update ON ml_setting FOR UPDATE USING ({platform}) WITH CHECK ({platform})")
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO ml_setting (id, inference_enabled, reason, updated_by, updated_at, lock_version)
        VALUES (1, true, 'Platform default: inference may run for deployed models only.', NULL, now(), 1)
        ON CONFLICT (id) DO NOTHING;
    """)


def downgrade() -> None:
    for t in GRANTS:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {t}; DROP POLICY IF EXISTS p_platform ON {t};"
            f"DROP POLICY IF EXISTS p_tenant_read ON {t}; DROP POLICY IF EXISTS p_read ON {t};"
            f"DROP POLICY IF EXISTS p_insert ON {t}; DROP POLICY IF EXISTS p_update ON {t};"
            f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"
        )
    for t in IMMUTABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_immutable ON {t}")
    op.execute("DROP TRIGGER IF EXISTS trg_model_version_guard ON model_version")
    op.execute("DROP FUNCTION IF EXISTS guard_model_version()")
