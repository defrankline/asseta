"""Gate 3: RLS, evidence immutability guards, grants and seeded METER_CAPTURE / HIRE_BILLING policies.

Revision ID: g3sec0000001
Revises: 453481275268
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g3sec0000001"
down_revision: str | None = "453481275268"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [
    "customer",
    "rental_rate_policy",
    "rental_contract",
    "job",
    "job_activity",
    "customer_acknowledgement",
    "capture_attachment",
    "meter_capture",
    "meter_reset_event",
    "job_exception",
]
IMMUTABLE = ["job_activity", "customer_acknowledgement", "capture_attachment", "rental_rate_policy"]
METER = (
    '{"opening_mode": "AUTOMATIC", "closing_mode": "AUTOMATIC", "manual_photo_required": true,'
    ' "min_ocr_confidence": 0.85, "max_recapture_attempts": 3, "manual_correction_requires_review": true,'
    ' "gps_enforcement": "SOFT", "gps_max_accuracy_m": 50.0, "gps_max_age_seconds": 120,'
    ' "tracker_comparison_window_seconds": 300, "tracker_distance_tolerance_m": 150.0,'
    ' "max_hours_per_elapsed_hour": "1.05", "continuity_tolerance_hours": "0.5",'
    ' "telemetry_engine_hours_tolerance": "0.5"}'
)
BILLING = '{"billable_hours_increment": "0.1", "rounding": "HALF_UP"}'


def upgrade() -> None:
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for t in TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    for t in IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER trg_{t}_immutable BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )
    op.execute("""
        CREATE FUNCTION guard_meter_capture() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR NEW.state <> 'SUPERSEDED'
             OR (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state') THEN
            RAISE EXCEPTION 'asseta: meter capture evidence is immutable (only supersession allowed)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_meter_capture_guard BEFORE UPDATE OR DELETE ON meter_capture
          FOR EACH ROW EXECUTE FUNCTION guard_meter_capture();
        CREATE FUNCTION guard_job_exception() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR (to_jsonb(NEW) - ARRAY['status','reviewed_by','reviewed_at','review_note'])
             IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','reviewed_by','reviewed_at','review_note']) THEN
            RAISE EXCEPTION 'asseta: exception evidence is immutable (only review fields change)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_job_exception_guard BEFORE UPDATE OR DELETE ON job_exception
          FOR EACH ROW EXECUTE FUNCTION guard_job_exception();
    """)
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            GRANT SELECT, INSERT, UPDATE ON {", ".join(TABLES)} TO asseta_app;
            REVOKE UPDATE ON {", ".join(IMMUTABLE)} FROM asseta_app;
          END IF;
        END $$;
    """)
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,
                                    reason, created_at, source)
        SELECT gen_random_uuid(), t, 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00', v::jsonb,
               'Seeded platform default (replaceable configuration)', now(), 'migration'
        FROM (VALUES ('METER_CAPTURE', '{METER}'), ('HIRE_BILLING', '{BILLING}')) AS s(t, v)
        WHERE NOT EXISTS (SELECT 1 FROM policy_version p WHERE p.policy_type = s.t AND p.scope = 'PLATFORM');
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_meter_capture_guard ON meter_capture;"
        "DROP TRIGGER IF EXISTS trg_job_exception_guard ON job_exception;"
        "DROP FUNCTION IF EXISTS guard_meter_capture(); DROP FUNCTION IF EXISTS guard_job_exception();"
    )
    for t in IMMUTABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_immutable ON {t}")
    for t in TABLES:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {t}; ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;"
            f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"
        )
    # Platform policy seeds are immutable (policy_version trigger) and harmless to keep; re-upgrade is idempotent.
