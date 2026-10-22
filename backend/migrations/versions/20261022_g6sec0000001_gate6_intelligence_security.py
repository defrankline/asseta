"""Gate 6 security: tenant-owned FORCE RLS and explicit grants (never DELETE) on the intelligence tables, append-only
signal links / notes / outcomes, status-only risk-signal updates, the investigation-case guard (subject frozen,
allowed transitions only, severity never lowered, resolution needs an outcome), seeded FRAUD_CONTROLS platform policy.

Revision ID: g6sec0000001
Revises: g6a1c0000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g6sec0000001"
down_revision: str | None = "g6a1c0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS: dict[str, str] = {
    "risk_signal": "SELECT, INSERT, UPDATE",  # guard: OPEN -> LINKED/DISMISSED only, evidence frozen
    "anomaly_case": "SELECT, INSERT, UPDATE",  # guard: subject frozen, transitions, severity only upwards
    "anomaly_case_counter": "SELECT, INSERT, UPDATE",
    "case_signal": "SELECT, INSERT",
    "case_note": "SELECT, INSERT",
    "case_outcome": "SELECT, INSERT",
}
APPEND_ONLY = ["case_signal", "case_note", "case_outcome"]
GUARDED = {"risk_signal": "guard_risk_signal", "anomaly_case": "guard_anomaly_case"}
FRAUD_SEED = (
    '{"engine_activity_min_minutes": 30, "fuel_max_litres_per_meter_hour": null, '
    '"expense_threshold_per_machine_per_week": null, "cash_outstanding_max_hours": 48, '
    '"cash_outstanding_max_amount": null, "case_grouping_window_hours": 72, "duplicate_receipt_lookback_days": 90, '
    '"authorization_tolerance_minutes": 5, "detection_lookback_hours": 168}'
)
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION guard_risk_signal() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'OPEN' OR NEW.status NOT IN ('LINKED', 'DISMISSED')
             OR (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status') THEN
            RAISE EXCEPTION 'asseta: risk signal evidence is immutable (status OPEN -> LINKED/DISMISSED only)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION severity_rank(s text) RETURNS int LANGUAGE sql IMMUTABLE AS
        $$ SELECT CASE s WHEN 'INFO' THEN 0 WHEN 'WARNING' THEN 1 WHEN 'CRITICAL' THEN 2 END $$;
        CREATE FUNCTION guard_anomaly_case() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['severity','status','assignee_user_id','last_signal_at','resolved_at',
                                        'resolved_by','updated_at','version'];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: case subject and opening facts are immutable'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (OLD.status, NEW.status) NOT IN (('OPEN','OPEN'), ('OPEN','IN_REVIEW'), ('OPEN','RESOLVED'),
              ('IN_REVIEW','IN_REVIEW'), ('IN_REVIEW','RESOLVED'), ('RESOLVED','IN_REVIEW')) THEN
            RAISE EXCEPTION 'asseta: case transition % -> % is not permitted', OLD.status, NEW.status
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF severity_rank(NEW.severity) < severity_rank(OLD.severity) THEN
            RAISE EXCEPTION 'asseta: case severity is never lowered' USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF NEW.status = 'RESOLVED' AND OLD.status <> 'RESOLVED' AND (NEW.resolved_by IS NULL OR NOT EXISTS (
               SELECT 1 FROM case_outcome o WHERE o.case_id = NEW.id AND o.decided_at = NEW.resolved_at
                 AND o.decided_by = NEW.resolved_by)) THEN
            RAISE EXCEPTION 'asseta: resolving a case requires a recorded outcome'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
    """)
    for t, fn in GUARDED.items():
        op.execute(f"CREATE TRIGGER trg_{t}_guard BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION {fn}()")
    for t in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER trg_{t}_immutable BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for t in GRANTS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,
                                    reason, created_at, source)
        SELECT gen_random_uuid(), 'FRAUD_CONTROLS', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
               '{FRAUD_SEED}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version WHERE policy_type = 'FRAUD_CONTROLS' AND scope = 'PLATFORM');
    """)


def downgrade() -> None:
    for t in GRANTS:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {t}; ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;"
            f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"
        )
    for t in APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_immutable ON {t}")
    for t in GUARDED:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_guard ON {t}")
    op.execute(
        "DROP FUNCTION IF EXISTS guard_anomaly_case(); DROP FUNCTION IF EXISTS guard_risk_signal();"
        "DROP FUNCTION IF EXISTS severity_rank(text);"
    )
    # The FRAUD_CONTROLS platform seed is immutable (policy_version trigger) and harmless; re-upgrade is idempotent.
