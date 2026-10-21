"""Gate 2: telemetry partitions (+DEFAULT), GiST indexes, RLS, telemetry immutability, seeded TRACKING policy.

Revision ID: g2sec0000001
Revises: 6fc89a8ea8b0
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g2sec0000001"
down_revision: str | None = "6fc89a8ea8b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARTITIONED = {"machine_position_event": "event_time", "tracker_ingestion_event": "received_at"}
TENANT_OWNED = [
    "operating_area",
    "machine_category",
    "staff_member",
    "machine_assignment",
    "tracker",
    "tracker_capability",
    "tracker_assignment",
    "job_site",
    "geofence",
    "geofence_machine",
    "geofence_event",
    "tracking_alert",
    "machine_latest_position",
    "machine_state_event",
    "machine_position_event",
]
GATE2_TABLES = [*TENANT_OWNED, "tracker_ingestion_event", "tracker_model", "telemetry_gateway", "policy_version"]
IMMUTABLE = ["machine_position_event"]  # original telemetry evidence is never edited (prompt.md §3.7)
SEED_TRACKING = """{"live_max_age_seconds": 300, "stale_after_seconds": 1800, "offline_after_seconds": 21600,
 "max_position_accuracy_m": 100.0, "geofence_tolerance_m": 30.0, "moving_speed_kmh": 3.0, "stop_min_seconds": 300,
 "max_plausible_speed_kmh": 120.0, "future_timestamp_tolerance_seconds": 300, "max_replay_age_days": 30,
 "low_power_voltage": null, "operating_window_start": null, "operating_window_end": null,
 "operating_weekdays": [0, 1, 2, 3, 4, 5, 6]}"""


def upgrade() -> None:
    # Monthly partitions are created ahead by ensure_telemetry_partitions(); DEFAULT catches anything else
    # (e.g. far-past replays) so ingestion never fails on a missing partition.
    op.execute("""
    CREATE FUNCTION ensure_telemetry_partitions(months_ahead int DEFAULT 3, months_back int DEFAULT 2)
    RETURNS void LANGUAGE plpgsql AS $$
    DECLARE t text; col text; m date; start_m date := date_trunc('month', now())::date;
    BEGIN
      FOREACH t IN ARRAY ARRAY['machine_position_event', 'tracker_ingestion_event'] LOOP
        FOR i IN -months_back..months_ahead LOOP
          m := (start_m + make_interval(months => i))::date;
          EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                         t || '_' || to_char(m, 'YYYYMM'), t, m, (m + interval '1 month')::date);
        END LOOP;
      END LOOP;
    END $$;
    """)
    for table in PARTITIONED:
        op.execute(f"CREATE TABLE {table}_default PARTITION OF {table} DEFAULT")
    op.execute("SELECT ensure_telemetry_partitions(14, 14)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_latest_location ON machine_latest_position USING gist (location)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_site_center ON job_site USING gist (center)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_position_event_time_brin ON machine_position_event USING brin (event_time)"
    )

    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for table in [*TENANT_OWNED, "tracker_ingestion_event"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table in TENANT_OWNED:
        op.execute(
            f"CREATE POLICY p_tenant ON {table} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    # Raw ingestion log: tenants see/insert their own; unresolved (tenant NULL) rows are system-only.
    op.execute(
        f"CREATE POLICY p_tenant ON tracker_ingestion_event USING ({own} OR app_scope() = 'system') "
        f"WITH CHECK ({own} OR app_scope() = 'system')"
    )
    # Platform-owned catalogs/config: everyone reads; only platform/system writes.
    for table in ["tracker_model", "telemetry_gateway"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY p_read ON {table} FOR SELECT USING (true)")
        op.execute(
            f"CREATE POLICY p_write ON {table} FOR ALL USING (app_scope() IN ('platform','system')) "
            "WITH CHECK (app_scope() IN ('platform','system'))"
        )
    op.execute(
        "ALTER TABLE policy_version ENABLE ROW LEVEL SECURITY; ALTER TABLE policy_version FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"CREATE POLICY p_read ON policy_version FOR SELECT USING (tenant_id IS NULL OR {own} "
        "OR app_scope() IN ('system'))"
    )
    op.execute(
        f"CREATE POLICY p_insert ON policy_version FOR INSERT WITH CHECK ("
        f"(tenant_id IS NULL AND app_scope() IN ('platform','system')) OR {own})"
    )
    op.execute(
        "CREATE TRIGGER trg_policy_version_immutable BEFORE UPDATE OR DELETE ON policy_version "
        "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
    )
    for table in IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            -- Grant only Gate 2 tables: never re-grant privileges earlier revisions revoked (e.g. invoice DELETE).
            GRANT SELECT, INSERT, UPDATE, DELETE ON {", ".join(GATE2_TABLES)} TO asseta_app;
            REVOKE UPDATE, DELETE ON machine_position_event, policy_version FROM asseta_app;
            REVOKE DELETE ON tracker, tracker_assignment, tracking_alert, tracker_ingestion_event FROM asseta_app;
            GRANT EXECUTE ON FUNCTION ensure_telemetry_partitions(int, int) TO asseta_app;
          END IF;
        END $$;
    """)
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,
                                    reason, created_at, source)
        VALUES (gen_random_uuid(), 'TRACKING', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
                '{SEED_TRACKING}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_policy_version_immutable ON policy_version")
    for table in IMMUTABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
    for table in [*TENANT_OWNED, "tracker_ingestion_event", "tracker_model", "telemetry_gateway", "policy_version"]:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {table}; DROP POLICY IF EXISTS p_read ON {table};"
            f"DROP POLICY IF EXISTS p_write ON {table}; DROP POLICY IF EXISTS p_insert ON {table};"
            f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY; ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
        )
    op.execute("DELETE FROM policy_version WHERE source = 'migration'")
    op.execute(
        "DROP INDEX IF EXISTS ix_latest_location; DROP INDEX IF EXISTS ix_job_site_center;"
        "DROP INDEX IF EXISTS ix_position_event_time_brin"
    )
    op.execute("DROP FUNCTION IF EXISTS ensure_telemetry_partitions(int, int)")
    # Partitions are dropped with their parent tables by the previous revision's downgrade.
