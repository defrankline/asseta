"""Pure helpers of the demo `field` command (backend/scripts/demo_tenant_live.py): the planned field history stays
inside working hours after the seed and before now, each machine is sold hours, gets an opening report and then
reports that add up to its meter, and the generated evidence images are valid, unique PNGs."""

import argparse
import importlib.util
import json
import struct
import sys
import zlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any
from zoneinfo import ZoneInfo

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "demo_tenant_live.py"


@pytest.fixture(scope="module")
def demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("demo_tenant_live", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_tenant_live"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


TZ = ZoneInfo("Africa/Dar_es_Salaam")
OPENINGS = {"EX-01": Decimal("6423.1"), "EX-02": Decimal("3181.9"), "WL-01": Decimal("5014.0")}


def local(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=TZ).astimezone(UTC)


def plan(demo: ModuleType, seeded: datetime, now: datetime) -> tuple[Any, Any, Any, Any]:
    rules = demo.Rules()
    past, today = demo.field_days(seeded + timedelta(minutes=15), now - timedelta(minutes=10), rules)
    runs, events = demo.plan_field(past, today, OPENINGS)
    return past, today, runs, events


def by_kind(events: list[Any], kind: str, machine: str | None = None) -> list[Any]:
    return [e for e in events if e.kind == kind and (machine is None or e.machine == machine)]


def test_full_week_matches_the_requested_days(demo: ModuleType) -> None:
    seeded, now = local(2026, 10, 15, 9), local(2026, 10, 24, 15, 30)  # seeded 9 days ago
    past, today, _runs, events = plan(demo, seeded, now)
    assert len(past) == 4 and len(today) == 1

    def days_ago(t: datetime) -> int:
        return (now.astimezone(TZ).date() - t.astimezone(TZ).date()).days

    assert days_ago(by_kind(events, "OPENING", "WL-01")[0].at) == 4
    assert days_ago(by_kind(events, "OPENING", "EX-01")[0].at) == 3
    assert days_ago(by_kind(events, "OPENING", "EX-02")[0].at) == 2
    assert days_ago(by_kind(events, "REPORT", "WL-01")[-1].at) == 1  # its hire ended yesterday, all reported
    for code in ("EX-01", "EX-02"):  # still working: today's hours are left to report live in the app
        assert days_ago(by_kind(events, "REPORT", code)[-1].at) == 1
    assert all(e.machine != "TP-01" for e in events)  # no starting reading: its opening report is made live


@pytest.mark.parametrize(
    ("seeded", "now"),
    [
        (local(2026, 10, 15, 9), local(2026, 10, 24, 15, 30)),  # a week of history
        (local(2026, 10, 22, 14), local(2026, 10, 24, 12)),  # two short days
        (local(2026, 10, 24, 7), local(2026, 10, 24, 16)),  # seeded this morning: all of it today
        (local(2026, 10, 20, 11), local(2026, 10, 24, 6)),  # before work today: past days only
    ],
)
def test_plan_is_ordered_in_hours_after_the_seed_and_before_now(
    demo: ModuleType, seeded: datetime, now: datetime
) -> None:
    past, today, runs, events = plan(demo, seeded, now)
    days = past + today
    lo, hi = demo.field_window(demo.Rules())
    assert [e.at for e in events] == sorted(e.at for e in events)
    for e in events:
        if e.kind == "FLOAT":  # issued by the office just before the first working period
            assert seeded < e.at < days[0][0]
            continue
        assert seeded + timedelta(minutes=15) <= e.at <= now - timedelta(minutes=10), e
        t = e.at.astimezone(TZ).time()
        assert lo <= t <= hi, e
    kinds: set[str] = set()
    for code, run in runs.items():
        [sale], [opening] = by_kind(events, "SALE", code), by_kind(events, "OPENING", code)
        assert sale.at < opening.at < min(seg.start for seg in run.segments)
        assert opening.data["reading"] == run.opening == OPENINGS[code]
        kinds |= {seg.kind for seg in run.segments}
        assert all(seg.note for seg in run.segments if seg.kind != "WORK")
        assert all(seg.start < seg.end for seg in run.segments)
        # Every report accounts for the meter since the previous reading: customer hours plus idle (standby) hours.
        prev_at, prev = opening.at, run.opening
        for e in by_kind(events, "REPORT", code):
            r = e.data["report"]
            assert r.at == e.at and r.reading > prev
            assert r.customer_hours + r.idle_hours == r.reading - prev and r.idle_hours >= 0
            elapsed_h = Decimal((r.at - prev_at).total_seconds()) / 3600
            assert r.reading - prev <= elapsed_h * Decimal("1.05")  # server: meter can't outrun the clock
            prev_at, prev = r.at, r.reading
        used = sum((r.customer_hours for r in run.reports), Decimal(0))
        assert Decimal(sale.data["hours"]) >= used  # the customer paid for every hour reported for them
        if run.finished_at:
            assert by_kind(events, "REPORT", code)[-1].at > run.finished_at
    assert {"WORK", "STANDBY", "DOWNTIME"} <= kinds
    assert by_kind(events, "HANDOVER")[0].at > max(e.at for e in by_kind(events, "SALE"))
    assert len(by_kind(events, "FUEL_ISSUE")) == 3 and len(by_kind(events, "FUEL_PURCHASE")) == 1
    assert {e.data["category"] for e in by_kind(events, "EXPENSE")} == {"SPARES", "TYRES", "FUEL", "ALLOWANCE"}


def test_no_usable_time_yields_no_days(demo: ModuleType) -> None:
    seeded = local(2026, 10, 24, 16)
    past, today = demo.field_days(seeded, local(2026, 10, 24, 17), demo.Rules())
    assert past == [] and today == []
    with pytest.raises(ValueError, match="no usable working period"):
        demo.plan_field([], [], OPENINGS)


def test_operating_window_and_weekdays_are_respected(demo: ModuleType) -> None:
    rules = demo.Rules(window_start="08:00", window_end="16:00", weekdays=[0, 1, 2, 3, 4])  # Mon-Fri
    past, today = demo.field_days(local(2026, 10, 16, 6), local(2026, 10, 24, 15), rules)  # 24 Oct 2026 is a Saturday
    days = past + today
    assert today == [] and len(past) == 4
    for s, e in days:
        assert s.astimezone(TZ).weekday() < 5
        assert s.astimezone(TZ).hour >= 8 and e.astimezone(TZ).hour <= 16


def test_meter_counts_work_and_standby_only(demo: ModuleType) -> None:
    t0 = local(2026, 10, 20, 8)
    run = demo.MachineRun("EX-01", t0, Decimal("100.0"))
    run.segments = [
        demo.Segment("WORK", t0, t0 + timedelta(hours=2)),
        demo.Segment("STANDBY", t0 + timedelta(hours=2), t0 + timedelta(hours=3)),
        demo.Segment("DOWNTIME", t0 + timedelta(hours=3), t0 + timedelta(hours=4)),
    ]
    assert run.meter_at(t0 + timedelta(hours=1, minutes=30)) == Decimal("101.5")
    assert run.meter_at(t0 + timedelta(hours=10)) == Decimal("103.0")


def test_opening_meters_follow_the_tracker_engine_hours(demo: ModuleType) -> None:
    state = {"units": [{"code": "EX-01", "hours_ms": int(6425.37 * 3_600_000), "home": [-6.7, 39.0]}]}
    meters = demo.opening_meters(state)
    assert meters["EX-01"] == Decimal("6425.3")  # from its tracker
    assert meters["EX-02"] == Decimal("3180.2")  # falls back to the seed baseline


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    length, kind = struct.unpack(">I4s", data[8:16])
    assert kind == b"IHDR" and length == 13
    body = data[16:29]
    assert struct.unpack(">I", data[29:33])[0] == zlib.crc32(b"IHDR" + body)
    width, height = struct.unpack(">II", body[:8])
    return width, height


def test_png_images_are_valid_deterministic_and_unique(demo: ModuleType) -> None:
    a = demo.png_image("6423.1", "capture-1")
    assert a == demo.png_image("6423.1", "capture-1")
    assert a != demo.png_image("6423.1", "capture-2")  # same digits, another capture: never a duplicate image
    width, height = _png_size(a)
    idat_len = struct.unpack(">I", a[33:37])[0]
    raw = zlib.decompress(a[41 : 41 + idat_len])
    assert len(raw) == height * (width + 1)
    assert width > 0 and height > 0 and len(a) < 256 * 1024  # one upload chunk


def test_demo_supervisor_only_accepts_the_seeded_account(demo: ModuleType, tmp_path: Path) -> None:
    state: dict[str, Any] = {
        "tenant_id": "t1",
        "users": {"supervisor": {"user_id": "u1", "email": "supervisor.wambura@demo.asseta.co.tz", "subject": "k1"}},
        "staff": {"supervisor": "s1"},
    }
    args = argparse.Namespace(out_dir=str(tmp_path), slug="wambura", demo_domain="demo.asseta.co.tz")
    with pytest.raises(demo.Refuse, match="No credentials file"):
        demo.demo_supervisor(args, state)
    creds = tmp_path / "demo-wambura-credentials.json"
    creds.write_text(
        json.dumps({"tenant_id": "t1", "accounts": {"supervisor": {"email": "owner@wambura.co.tz", "password": "x"}}})
    )
    with pytest.raises(demo.Refuse, match=r"must be supervisor\.wambura@demo\.asseta\.co\.tz"):
        demo.demo_supervisor(args, state)
    creds.write_text(
        json.dumps(
            {
                "tenant_id": "t1",
                "accounts": {"supervisor": {"email": "supervisor.wambura@demo.asseta.co.tz", "password": "x"}},
            }
        )
    )
    who = demo.demo_supervisor(args, state)
    assert (who.user_id, who.subject, who.staff_id) == ("u1", "k1", "s1")
    state["users"]["supervisor"]["preexisting"] = True
    with pytest.raises(demo.Refuse):
        demo.demo_supervisor(args, state)


def test_seed_refuses_a_tenant_whose_data_was_reset_for_go_live(demo: ModuleType) -> None:
    class FakeApi:
        def __init__(self, total: int):
            self.total = total
            self.calls: list[tuple[str, dict[str, Any]]] = []

        def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
            self.calls.append((path, params))
            return {"total": self.total, "items": [{"occurred_at": "2026-10-28T10:00:00Z"}] * self.total}

    tenant = {"id": "t1", "display_name": "Real Co"}
    fresh = FakeApi(0)
    demo.refuse_if_reset(fresh, tenant)
    assert fresh.calls == [
        ("/platform/audit-events", {"tenant_id": "t1", "action_prefix": "platform.tenant.data_reset", "page_size": 1})
    ]
    with pytest.raises(demo.Refuse, match="data reset for go-live"):
        demo.refuse_if_reset(FakeApi(1), tenant)
