"""ADR-008: every machine report records the time since the machine's last visit, and where both visits were.

`meter_capture` gets `place_name` (optional area label from the phone's geocoder, e.g. "Mbezi Beach, Kinondoni, Dar
es Salaam"; REST and the sync operation METER_CAPTURE accept it).

`machine_report` gets, all nullable, server-set when a report is submitted and never changed (the report's guard
trigger already refuses any change but the decision stamps):
- `previous_visit_at`, `since_previous_visit_seconds`: last visit = the most recent earlier reading (meter capture) of
  the same machine that belongs to any machine report (opening or normal, any status, rejected ones included), by the
  reading's taken-at time (`meter_capture.captured_at`); the gap = this report's reading taken-at time minus that one,
  in whole seconds. No earlier report reading: null ("First visit").
- `previous_visit_lat`, `previous_visit_lng`, `previous_visit_accuracy_m`: that reading's GPS as it was recorded.
- `visit_place` / `previous_visit_place`: the area label the phone's geocoder gave the reading (new
  `meter_capture.place_name`, optional, max 200, stored as given; a label, not evidence). Existing readings have none,
  so the backfill leaves these null (the coordinates are still shown).
- `visit_site_name` / `previous_visit_site_name`: a hint, the company's site whose geofence (SITE_BOUNDARY /
  ALLOWED_AREA, active) contains the reading's GPS point, nearest site centre first (the site's name, else the
  geofence's); none: null. No outside geocoding service.

Data step: existing reports are filled the same way. It runs under `app.scope = system` with RLS temporarily not
forced on the tables it reads and writes, and only the report's guard trigger disabled (the pattern of adr8fix01:
without that, FORCE RLS makes the statements match no rows); all restored immediately. An assertion inside the same
window fails the migration if any report with an earlier report reading was left without its previous visit. No
tenant-specific values.

Revision ID: visit01
Revises: adr8fix01
Create Date: 2026-11-19 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "visit01"
down_revision: str | Sequence[str] | None = "adr8fix01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ_TABLES = ("machine_report", "meter_capture", "geofence", "job_site")

# The company's site containing the point of reading `c` of report `r` (as machine_reports/visits.py site_name).
PLACE = """
    SELECT COALESCE(s.name, g.name)
    FROM geofence g LEFT JOIN job_site s ON s.id = g.job_site_id AND s.is_active
    WHERE g.tenant_id = r.tenant_id AND g.is_active AND g.kind IN ('SITE_BOUNDARY', 'ALLOWED_AREA')
      AND ST_Covers(g.area, ST_SetSRID(ST_MakePoint(c.longitude, c.latitude), 4326)::geography)
    ORDER BY ST_Distance(
        COALESCE(s.center, ST_Centroid(g.area::geometry))::geography,
        ST_SetSRID(ST_MakePoint(c.longitude, c.latitude), 4326)::geography
    ), g.name
    LIMIT 1
"""

VISIT_SITE = f"""
    UPDATE machine_report AS r SET visit_site_name = ({PLACE}), visit_place = c.place_name
    FROM meter_capture AS c
    WHERE c.id = r.capture_id AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL AND r.visit_site_name IS NULL
"""

# The latest earlier report reading of the same machine, for the report `r` (its reading `c`).
PREVIOUS = """
    SELECT pc.captured_at, pc.latitude, pc.longitude, pc.accuracy_m, pc.place_name, pr.visit_site_name
    FROM machine_report pr JOIN meter_capture pc ON pc.id = pr.capture_id
    WHERE pr.machine_id = r.machine_id AND pc.captured_at < c.captured_at
    ORDER BY pc.captured_at DESC, pr.submitted_at
    LIMIT 1
"""

PREVIOUS_VISIT = f"""
    WITH prev AS (
      SELECT r.id, c.captured_at AS this_at, p.at, p.lat, p.lng, p.acc, p.place, p.site
      FROM machine_report r JOIN meter_capture c ON c.id = r.capture_id
      CROSS JOIN LATERAL ({PREVIOUS}) AS p(at, lat, lng, acc, place, site)
      WHERE r.previous_visit_at IS NULL
    )
    UPDATE machine_report AS t SET
      previous_visit_at = prev.at,
      since_previous_visit_seconds = floor(extract(epoch FROM (prev.this_at - prev.at)))::integer,
      previous_visit_lat = prev.lat,
      previous_visit_lng = prev.lng,
      previous_visit_accuracy_m = prev.acc,
      previous_visit_place = prev.place,
      previous_visit_site_name = prev.site
    FROM prev WHERE t.id = prev.id
"""

CHECK = """
    DO $$
    DECLARE missing integer;
    BEGIN
      SELECT count(*) INTO missing FROM machine_report r JOIN meter_capture c ON c.id = r.capture_id
      WHERE r.previous_visit_at IS NULL AND EXISTS (
        SELECT 1 FROM machine_report pr JOIN meter_capture pc ON pc.id = pr.capture_id
        WHERE pr.machine_id = r.machine_id AND pc.captured_at < c.captured_at);
      IF missing > 0 THEN
        RAISE EXCEPTION 'visit01: % machine reports were not filled with their previous visit', missing;
      END IF;
    END $$;
"""

COLUMNS = (
    ("previous_visit_at", sa.DateTime(timezone=True)),
    ("since_previous_visit_seconds", sa.Integer()),
    ("previous_visit_lat", sa.Float()),
    ("previous_visit_lng", sa.Float()),
    ("previous_visit_accuracy_m", sa.Float()),
    ("previous_visit_place", sa.String(200)),
    ("previous_visit_site_name", sa.String(200)),
    ("visit_place", sa.String(200)),
    ("visit_site_name", sa.String(200)),
)


def upgrade() -> None:
    op.add_column("meter_capture", sa.Column("place_name", sa.String(200), nullable=True))
    for name, type_ in COLUMNS:
        op.add_column("machine_report", sa.Column(name, type_, nullable=True))
    op.execute("SELECT set_config('app.scope', 'system', true)")
    for table in READ_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE machine_report DISABLE TRIGGER trg_machine_report_guard")
    op.execute(VISIT_SITE)  # first: a report's previous visit carries the earlier report's site hint
    op.execute(PREVIOUS_VISIT)
    op.execute(CHECK)
    op.execute("ALTER TABLE machine_report ENABLE TRIGGER trg_machine_report_guard")
    for table in READ_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column("machine_report", name)
    op.drop_column("meter_capture", "place_name")
