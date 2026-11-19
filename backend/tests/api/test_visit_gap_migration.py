"""Migration visit01 fills the time and place since the last visit of reports made before it.

The database is taken back to adr8fix01 (the columns do not exist) after real reports were made through the API,
then upgraded again as the RLS-bound owner role (FORCE row-level security, like live). The data step must really
have run: an earlier data step once matched no rows under RLS without anyone noticing."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from asseta.core.config import get_settings
from tests.support.api import Api
from tests.support.finance import tenant_sql
from tests.support.machine_reports import T, bought, cust, later, ok, report_body, setup_reports, submit
from tests.support.meter import fix
from tests.support.telemetry import DAR

COLUMNS = (
    "previous_visit_at, since_previous_visit_seconds, previous_visit_lat, previous_visit_lng, "
    "previous_visit_accuracy_m, previous_visit_place, previous_visit_site_name, visit_place, visit_site_name"
)


def _cfg() -> Config:
    cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    cfg.attributes["url"] = get_settings().migration_database_url
    return cfg


@pytest.fixture
def at_head() -> Iterator[None]:
    yield
    command.upgrade(_cfg(), "head")  # whatever happened, the rest of the suite runs at head


def test_the_backfill_fills_existing_reports(api: Api, at_head: None) -> None:
    ctx = setup_reports(api, "Backfill Hire Ltd", "VIS-1")
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 10)
    centre = {"type": "Point", "coordinates": [DAR[1], DAR[0]]}
    site = ok(f.owner.post(f"{T}/job-sites", {"code": "YARD", "name": "Main yard", "center": centre}), 201)
    corners = ((-0.01, -0.01), (0.01, -0.01), (0.01, 0.01), (-0.01, 0.01), (-0.01, -0.01))
    ring = [[DAR[1] + dx, DAR[0] + dy] for dx, dy in corners]
    fence = {"type": "Polygon", "coordinates": [ring]}
    ok(
        f.owner.post(
            f"{T}/geofences",
            {"name": "Yard", "kind": "SITE_BOUNDARY", "job_site_id": site["id"], "polygon": fence},
        ),
        201,
    )
    first = submit(f.supervisor, report_body(m, "1002", later(api, 2), [cust(f.customer_id, 2)]))
    ok(f.manager.post(f"{T}/machine-reports/{first['id']}/reject", {"reason": "Wrong customer"}))
    second_at = later(api, 30)
    body = report_body(m, "1003", second_at, [cust(f.customer_id, 3)])
    body["capture"]["gps"] = fix(second_at, lat=DAR[0] + 0.5, lon=DAR[1])
    second = submit(f.supervisor, body)
    sql = f"SELECT id, {COLUMNS} FROM machine_report ORDER BY submitted_at"  # noqa: S608 - constant columns
    before = [tuple(r) for r in tenant_sql(f.tid, sql)]
    assert before[1][2] == 30 * 3600 and before[1][7] == "Main yard" and before[0][9] == "Main yard"

    command.downgrade(_cfg(), "adr8fix01")
    command.upgrade(_cfg(), "head")

    after = [tuple(r) for r in tenant_sql(f.tid, sql)]
    assert [r[0] for r in after] == [r[0] for r in before]
    assert str(after[1][0]) == second["id"]
    # Everything comes back as it was computed at submit, except the phone's area labels (the readings had none).
    assert after == before
    first_row, second_row = after
    assert first_row[1] is None and first_row[2] is None  # first visit
    assert second_row[2] == 30 * 3600 and second_row[3] == DAR[0] and second_row[7] == "Main yard"
    assert second_row[9] is None  # outside every site
