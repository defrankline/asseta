"""ensure_telemetry_partitions() runs as its owner (SECURITY DEFINER, pinned search_path) and skips partitions that
already exist: the runtime role has no CREATE on the schema, and Postgres checks that privilege before honouring
IF NOT EXISTS, so the connectivity worker's monthly top-up failed every sweep.

Revision ID: t1sec0000001
Revises: d22sec000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "t1sec0000001"
down_revision: str | None = "d22sec000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BODY = """
    DECLARE t text; part text; m date; start_m date := date_trunc('month', now())::date;
    BEGIN
      IF months_ahead NOT BETWEEN 0 AND 24 OR months_back NOT BETWEEN 0 AND 24 THEN
        RAISE EXCEPTION 'months_ahead/months_back must be between 0 and 24';
      END IF;
      FOREACH t IN ARRAY ARRAY['machine_position_event', 'tracker_ingestion_event'] LOOP
        FOR i IN -months_back..months_ahead LOOP
          m := (start_m + make_interval(months => i))::date;
          part := t || '_' || to_char(m, 'YYYYMM');
          CONTINUE WHEN to_regclass(format('public.%I', part)) IS NOT NULL;
          EXECUTE format('CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.%I FOR VALUES FROM (%L) TO (%L)',
                         part, t, m, (m + interval '1 month')::date);
        END LOOP;
      END LOOP;
    END"""


def upgrade() -> None:
    op.execute(f"""
    CREATE OR REPLACE FUNCTION ensure_telemetry_partitions(months_ahead int DEFAULT 3, months_back int DEFAULT 2)
    RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $${BODY} $$;
    """)
    # Months are bounded (0..24) so a caller cannot make the owner create unbounded tables.
    op.execute("REVOKE ALL ON FUNCTION ensure_telemetry_partitions(int, int) FROM PUBLIC")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            GRANT EXECUTE ON FUNCTION ensure_telemetry_partitions(int, int) TO asseta_app;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER FUNCTION ensure_telemetry_partitions(int, int) SECURITY INVOKER RESET search_path")
