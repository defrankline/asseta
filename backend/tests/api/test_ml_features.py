"""Gate 6B: point-in-time fact loading from real domain rows, weekly snapshots and tenant isolation of features."""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.ml.features import MachineFacts
from asseta.modules.intelligence.facts import load_tenant_facts, week_ends
from tests.support.api import Api
from tests.support.finance import FinCtx, complete_job, setup_finance
from tests.support.notify import sql

DAR_TZ = ZoneInfo("Africa/Dar_es_Salaam")


def facts(tid: str, as_of: datetime, days: int = 14) -> dict[str, MachineFacts]:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        return {
            f.machine_id: f for f in load_tenant_facts(s, uuid.UUID(tid), as_of, as_of - timedelta(days=days), DAR_TZ)
        }


def fuel(f: FinCtx, at: datetime, litres: str) -> None:
    body = {"event_type": "ISSUE", "litres": litres, "machine_id": f.c.t.machine_id}
    body |= {"occurred_at": at.isoformat(), "unit_price": "3000"}
    r = f.supervisor.post("/api/v1/tenant/fuel-events", body)
    assert r.status_code == 201, r.text


def test_late_recorded_fact_is_excluded_even_if_it_happened_before_as_of(api: Api) -> None:
    f = setup_finance(api, "Pit Co", "PIT-1")
    t0 = api.clock.now
    complete_job(api, f, f.c.job_id, "500.0", "508.0", 9)  # meter interval closes at t0 + 9h
    fuel(f, t0 + timedelta(hours=2), "40")  # recorded promptly (t0 + 9h)
    api.clock.set_at(t0 + timedelta(days=3))
    fuel(f, t0 + timedelta(hours=3), "25")  # happened at t0 + 3h but synced three days later
    as_of = t0 + timedelta(days=1)

    then = facts(f.tid, as_of)[f.c.t.machine_id]
    assert [m.meter_hours for m in then.meter] == [8.0]
    assert [x.litres for x in then.fuel] == [40.0]  # the late sync is invisible at as_of
    assert all(x.recorded_at <= as_of for x in then.fuel) and all(m.recorded_at <= as_of for m in then.meter)
    later = facts(f.tid, t0 + timedelta(days=4))[f.c.t.machine_id]
    assert sorted(x.litres for x in later.fuel) == [25.0, 40.0]
    before_close = facts(f.tid, t0 + timedelta(hours=5))[f.c.t.machine_id]
    assert before_close.meter == () and [x.litres for x in before_close.fuel] == []


def test_weekly_snapshots_from_real_facts_are_append_only(api: Api) -> None:
    f = setup_finance(api, "Snap Co", "SNAP-1")
    complete_job(api, f, f.c.job_id, "100.0", "106.5", 8)
    fuel(f, api.clock.now - timedelta(hours=1), "52")
    api.clock.set_at(datetime(2026, 11, 3, 9, tzinfo=UTC))
    body = {"from_date": "2026-10-26", "to_date": "2026-11-08"}
    r = api.platform.post(f"/api/v1/platform/ml/tenants/{f.tid}/snapshots", body)
    assert r.status_code == 200, r.text
    run = r.json()
    week_end = datetime(2026, 11, 2, tzinfo=DAR_TZ)
    assert datetime.fromisoformat(run["week_ends"][-1]) == week_end and run["skipped_future"] == 1
    assert run["written"] > 0 and run["machines"] >= 1
    rows = {
        r.feature_code: r
        for r in sql(
            "SELECT feature_code, value, n_inputs, data_cutoff, window_start FROM feature_snapshot"
            " WHERE tenant_id = :t AND entity_id = :m AND as_of = :a",
            t=f.tid,
            m=f.c.t.machine_id,
            a=week_end,
        )
    }
    assert float(rows["meter_hours"].value) == 6.5 and rows["meter_hours"].n_inputs == 1
    assert float(rows["fuel_litres"].value) == 52.0
    assert float(rows["litres_per_meter_hour"].value) == pytest.approx(8.0)
    assert rows["engine_hours"].value is None  # no sensor: honest absence, not zero
    assert rows["meter_hours"].window_start == week_end - timedelta(days=7)
    assert {d.code for d in sql("SELECT code FROM feature_definition")} >= {"meter_hours", "fuel_litres"}

    again = api.platform.post(f"/api/v1/platform/ml/tenants/{f.tid}/snapshots", body)
    assert again.status_code == 200 and again.json()["written"] == 0 and again.json()["skipped_existing"] > 0
    with get_sessionmaker().begin() as s:  # append-only even for the owning tenant
        apply_scope(s, DbScope.TENANT, uuid.UUID(f.tid), None)
        with pytest.raises(DBAPIError):
            s.execute(text("UPDATE feature_snapshot SET value = 1"))


def test_snapshots_are_tenant_isolated(api: Api) -> None:
    a = setup_finance(api, "Iso A", "ISO-A")
    b = api.onboard("Iso B", price="1000")
    b_tid = b["tenant"]["id"]
    [b_machine] = api.add_machines(b["owner"], 1, prefix="ISOB")
    complete_job(api, a, a.c.job_id, "10.0", "15.0", 6)
    api.clock.set_at(datetime(2026, 11, 3, 9, tzinfo=UTC))
    r = api.platform.post(
        f"/api/v1/platform/ml/tenants/{a.tid}/snapshots", {"from_date": "2026-11-01", "to_date": "2026-11-02"}
    )
    assert r.status_code == 200 and r.json()["written"] > 0
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(b_tid), None)
        assert s.execute(text("SELECT count(*) FROM feature_snapshot")).scalar_one() == 0
        with pytest.raises(DBAPIError):  # cannot write into another tenant's features either
            s.execute(
                text(
                    "INSERT INTO feature_snapshot (id, tenant_id, entity_type, entity_id, feature_code,"
                    " feature_version, as_of, window_start, window_end, n_inputs, computed_at) VALUES"
                    " (gen_random_uuid(), :t, 'MACHINE', gen_random_uuid(), 'x', 1, now(), now(), now(), 0, now())"
                ),
                {"t": a.tid},
            )
    assert set(facts(b_tid, api.clock.now)) == {b_machine}  # B's loader never sees A's machines
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(a.tid), None)
        assert s.execute(text("SELECT count(DISTINCT tenant_id) FROM feature_snapshot")).scalar_one() == 1


def test_week_ends_are_tenant_local_and_future_ones_refused(api: Api) -> None:
    ends = week_ends(datetime(2026, 10, 20, tzinfo=UTC), datetime(2026, 11, 10, tzinfo=UTC), DAR_TZ)
    assert [e.isoformat() for e in ends] == [
        "2026-10-26T00:00:00+03:00",
        "2026-11-02T00:00:00+03:00",
        "2026-11-09T00:00:00+03:00",
    ]
    f = setup_finance(api, "Range Co", "RANGE-1")
    r = api.platform.post(
        f"/api/v1/platform/ml/tenants/{f.tid}/snapshots", {"from_date": "2025-01-01", "to_date": "2026-10-31"}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "SNAPSHOT_RANGE_TOO_LARGE"
    owner = f.owner.post(
        f"/api/v1/platform/ml/tenants/{f.tid}/snapshots", {"from_date": "2026-10-26", "to_date": "2026-11-02"}
    )
    assert owner.status_code == 403
