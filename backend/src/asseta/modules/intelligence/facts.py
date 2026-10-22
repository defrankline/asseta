"""Point-in-time fact loader: domain rows -> `asseta.ml.features` input records for one tenant as of T.

Every query keeps a fact only when its **event time** is inside (since, T] **and** its **recording time** is <= T, so
a snapshot computed today for last month's T sees exactly what the live system could have seen at T (a phone that
synced two days late does not leak backward). `compute_snapshots` re-applies the same rule per `as_of`, so one load
for the newest T of a backfill is safe for every earlier T too. Status changes decided after T are ignored the same
way (an expense rejected after T still counted at T).

Sources (fact record: table -> event time / recording time):

* MeterInterval: meter_capture OPENING+CLOSING of a job -> closing `captured_at` / max(`received_at`) of the pair.
* EngineInterval: machine_position_event ignition or engine_hours, per tenant-local day -> fix `event_time` /
  max fix `received_at`.
* PositionSample: machine_position_event (GOOD, one per 5 min) + geofences -> `event_time` / `received_at`.
* FuelEntry: fuel_event PURCHASE/ISSUE into a machine -> `occurred_at` / `recorded_at`.
* ExpenseEntry: expense with a machine -> `incurred_at` / `submitted_at`.
* CashEntry RECEIVED: customer_payment CASH -> `received_at` / `recorded_at`; supervisor_cash_custody ->
  `occurred_at` / `created_at`. HANDED_OVER: cash_handover -> `handed_at` / `recorded_at`.
* ExceptionEvent: job_exception -> capture `captured_at` (else `created_at`) / `created_at`; tracking_alert ->
  `event_time` / `created_at`.

Notes and deliberate limits (documented, not hidden):

* Engine time comes from raw position fixes rather than `machine_state_event`: state events are rebuilt (deleted and
  re-inserted) when late data arrives, which would restamp their `created_at` and break the recording-time rule.
  Engine-on time is the sum of fix gaps (capped at 30 min) after an ignition-on fix; idle is the part with speed
  below 3 km/h. Machines without ignition fall back to engine-hour counter increments.
* Geofence membership is evaluated spatially against ALLOWED_AREA / SITE_BOUNDARY geofences created by T and not
  deactivated before the fix; an in-place geometry edit is not versioned, so history uses the current shape.
* Cash is held by people, not machines: a supervisor's cash movements are attributed to the machine(s) they were
  assigned to (SUPERVISOR assignment effective at the event and recorded by T).
* A meter interval is attributed to the week its CLOSING reading falls in (long jobs land in one week).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from asseta.ml.features import (
    MAX_POSITION_GAP,
    CashDirection,
    CashEntry,
    EngineInterval,
    ExceptionEvent,
    ExpenseEntry,
    FuelEntry,
    MachineFacts,
    MeterInterval,
    PositionSample,
)

IDLE_SPEED_KMH = 3.0
# Engine-on time uses one fix per machine-minute (gaps are summed, so this is lossless for runs > 1 min);
# spatial features use at most one fix per machine per 5 minutes. Both are literals in the SQL below.
ENGINE_SAMPLE_SECONDS = 60
POSITION_SAMPLE_SECONDS = 300


@dataclass
class _Acc:
    coverage_start: datetime | None
    meter: list[MeterInterval] = field(default_factory=list)
    engine: list[EngineInterval] = field(default_factory=list)
    fuel: list[FuelEntry] = field(default_factory=list)
    positions: list[PositionSample] = field(default_factory=list)
    expenses: list[ExpenseEntry] = field(default_factory=list)
    cash: list[CashEntry] = field(default_factory=list)
    exceptions: list[ExceptionEvent] = field(default_factory=list)


_MACHINES = """
SELECT id, created_at FROM machine
WHERE tenant_id = :t AND created_at <= :as_of AND (deactivated_at IS NULL OR deactivated_at > :since)
"""

_METER = """
WITH caps AS (
  SELECT DISTINCT ON (job_id, kind) job_id, machine_id, kind, reading, captured_at, received_at, capture_mode,
         manually_corrected
  FROM meter_capture
  WHERE tenant_id = :t AND state <> 'REJECTED' AND captured_at <= :as_of AND received_at <= :as_of
  ORDER BY job_id, kind, received_at DESC
)
SELECT c.machine_id, c.captured_at AS event_time, greatest(c.received_at, o.received_at) AS recorded_at,
       (c.reading - o.reading) AS hours, (c.capture_mode = 'MANUAL' OR c.manually_corrected) AS manual
FROM caps c JOIN caps o ON o.job_id = c.job_id AND o.kind = 'OPENING'
WHERE c.kind = 'CLOSING' AND c.captured_at > :since AND c.reading >= o.reading
"""

_ENGINE_FIXES = """
SELECT DISTINCT ON (machine_id, floor(extract(epoch FROM event_time) / 60))
       machine_id, event_time, received_at, ignition, engine_hours, speed_kmh
FROM machine_position_event
WHERE tenant_id = :t AND quality <> 'IMPLAUSIBLE_JUMP' AND (ignition IS NOT NULL OR engine_hours IS NOT NULL)
  AND event_time > :since_gap AND event_time <= :as_of AND received_at <= :as_of
ORDER BY machine_id, floor(extract(epoch FROM event_time) / 60), event_time
"""

_POSITIONS = """
WITH pts AS (
  SELECT DISTINCT ON (machine_id, floor(extract(epoch FROM event_time) / 300))
         machine_id, event_time, received_at, location
  FROM machine_position_event
  WHERE tenant_id = :t AND quality = 'GOOD' AND event_time > :since AND event_time <= :as_of
    AND received_at <= :as_of
  ORDER BY machine_id, floor(extract(epoch FROM event_time) / 300), event_time
)
SELECT pts.machine_id, pts.event_time, pts.received_at, ST_Y(pts.location) AS lat, ST_X(pts.location) AS lon,
       g.inside, g.site
FROM pts LEFT JOIN LATERAL (
  SELECT bool_or(ST_Covers(gf.area, pts.location::geography)) FILTER (WHERE gf.kind = 'ALLOWED_AREA') AS inside,
         (array_agg(coalesce(gf.job_site_id, gf.id)::text ORDER BY gf.created_at, gf.id)
            FILTER (WHERE ST_Covers(gf.area, pts.location::geography)))[1] AS site
  FROM geofence gf
  WHERE gf.tenant_id = :t AND gf.kind IN ('ALLOWED_AREA', 'SITE_BOUNDARY') AND gf.created_at <= :as_of
    AND (gf.deactivated_at IS NULL OR gf.deactivated_at > pts.event_time)
    AND (gf.applies_to_all_machines OR EXISTS (
          SELECT 1 FROM geofence_machine gm WHERE gm.geofence_id = gf.id AND gm.machine_id = pts.machine_id))
) g ON true
ORDER BY pts.machine_id, pts.event_time
"""

_FUEL = """
SELECT machine_id, occurred_at AS event_time, recorded_at, litres FROM fuel_event
WHERE tenant_id = :t AND machine_id IS NOT NULL AND event_type IN ('PURCHASE', 'ISSUE')
  AND occurred_at > :since AND occurred_at <= :as_of AND recorded_at <= :as_of
"""

_EXPENSES = """
SELECT machine_id, incurred_at AS event_time, submitted_at AS recorded_at, amount FROM expense
WHERE tenant_id = :t AND machine_id IS NOT NULL AND incurred_at > :since AND incurred_at <= :as_of
  AND submitted_at <= :as_of AND NOT (status = 'REJECTED' AND decided_at IS NOT NULL AND decided_at <= :as_of)
"""

# Cash movements of a supervisor, attributed to the machines they were assigned to at the time (recorded by T).
_CASH = """
WITH moves AS (
  SELECT received_by_staff_id AS staff_id, received_at AS event_time, recorded_at, amount, 'RECEIVED' AS direction
  FROM customer_payment
  WHERE tenant_id = :t AND method = 'CASH' AND received_by_staff_id IS NOT NULL
    AND NOT (status = 'REJECTED' AND verified_at IS NOT NULL AND verified_at <= :as_of)
  UNION ALL
  SELECT staff_member_id, occurred_at, created_at, amount, 'RECEIVED' FROM supervisor_cash_custody
  WHERE tenant_id = :t
  UNION ALL
  SELECT staff_member_id, handed_at, recorded_at, amount, 'HANDED_OVER' FROM cash_handover
  WHERE tenant_id = :t AND NOT (status = 'REJECTED' AND verified_at IS NOT NULL AND verified_at <= :as_of)
)
SELECT DISTINCT a.machine_id, m.event_time, m.recorded_at, m.amount, m.direction
FROM moves m JOIN machine_assignment a
  ON a.tenant_id = :t AND a.staff_member_id = m.staff_id AND a.role = 'SUPERVISOR'
 AND a.effective_from <= m.event_time AND (a.effective_to IS NULL OR a.effective_to > m.event_time)
 AND a.created_at <= :as_of
WHERE m.event_time > :since AND m.event_time <= :as_of AND m.recorded_at <= :as_of
"""

_EXCEPTIONS = """
SELECT je.machine_id, coalesce(mc.captured_at, je.created_at) AS event_time, je.created_at AS recorded_at,
       je.exception_type AS code
FROM job_exception je LEFT JOIN meter_capture mc ON mc.id = je.meter_capture_id
WHERE je.tenant_id = :t AND je.created_at <= :as_of
  AND coalesce(mc.captured_at, je.created_at) > :since AND coalesce(mc.captured_at, je.created_at) <= :as_of
UNION ALL
SELECT machine_id, event_time, created_at, alert_type FROM tracking_alert
WHERE tenant_id = :t AND machine_id IS NOT NULL AND event_time > :since AND event_time <= :as_of
  AND created_at <= :as_of
"""


def _f(v: Any) -> float:
    return float(v)


def _engine_intervals(rows: list[Any], tz: ZoneInfo) -> dict[uuid.UUID, list[EngineInterval]]:
    """Per machine and tenant-local day: engine-on hours (ignition gaps, or counter increments) and idle hours."""
    by_machine: dict[uuid.UUID, list[Any]] = defaultdict(list)
    for r in rows:
        by_machine[r.machine_id].append(r)
    out: dict[uuid.UUID, list[EngineInterval]] = {}
    for machine_id, fixes in by_machine.items():
        use_ignition = any(f.ignition is not None for f in fixes)
        days: dict[Any, list[Any]] = {}  # local date -> [engine_h, idle_h, last_event, max_recorded]
        for a, b in pairwise(fixes):
            gap = min(b.event_time - a.event_time, MAX_POSITION_GAP).total_seconds() / 3600
            if use_ignition:
                on = gap if a.ignition else 0.0
            elif a.engine_hours is not None and b.engine_hours is not None:
                on = min(max(_f(b.engine_hours) - _f(a.engine_hours), 0.0), gap)
            else:
                on = 0.0
            if on <= 0:
                continue
            idle = on if a.speed_kmh is not None and a.speed_kmh < IDLE_SPEED_KMH else 0.0
            day = b.event_time.astimezone(tz).date()
            acc = days.setdefault(day, [0.0, 0.0, b.event_time, b.received_at])
            acc[0] += on
            acc[1] += idle
            acc[2] = max(acc[2], b.event_time)
            acc[3] = max(acc[3], a.received_at, b.received_at)
        out[machine_id] = [EngineInterval(v[2], v[3], v[0], v[1]) for _, v in sorted(days.items())]
    return out


def load_tenant_facts(
    session: Session, tenant_id: uuid.UUID, as_of: datetime, since: datetime, tz: ZoneInfo
) -> list[MachineFacts]:
    """All machines' facts with event time in (since, as_of] and recording time <= as_of (call in TENANT scope)."""
    p = {"t": tenant_id, "as_of": as_of, "since": since}
    acc: dict[uuid.UUID, _Acc] = {
        r.id: _Acc(coverage_start=r.created_at) for r in session.execute(text(_MACHINES), p).all()
    }

    def add(machine_id: uuid.UUID, kind: str, record: Any) -> None:
        a = acc.get(machine_id)
        if a is not None:
            getattr(a, kind).append(record)

    for r in session.execute(text(_METER), p).all():
        add(r.machine_id, "meter", MeterInterval(r.event_time, r.recorded_at, _f(r.hours), bool(r.manual)))
    fixes = session.execute(text(_ENGINE_FIXES), p | {"since_gap": since - MAX_POSITION_GAP}).all()
    for machine_id, intervals in _engine_intervals(list(fixes), tz).items():
        for e in intervals:
            if e.event_time > since:
                add(machine_id, "engine", e)
    for r in session.execute(text(_POSITIONS), p).all():
        add(r.machine_id, "positions", PositionSample(r.event_time, r.received_at, r.lat, r.lon, r.site, r.inside))
    for r in session.execute(text(_FUEL), p).all():
        add(r.machine_id, "fuel", FuelEntry(r.event_time, r.recorded_at, _f(r.litres)))
    for r in session.execute(text(_EXPENSES), p).all():
        add(r.machine_id, "expenses", ExpenseEntry(r.event_time, r.recorded_at, _f(r.amount)))
    for r in session.execute(text(_CASH), p).all():
        add(r.machine_id, "cash", CashEntry(r.event_time, r.recorded_at, _f(r.amount), CashDirection(r.direction)))
    for r in session.execute(text(_EXCEPTIONS), p).all():
        add(r.machine_id, "exceptions", ExceptionEvent(r.event_time, r.recorded_at, str(r.code)))
    return [
        MachineFacts(
            tenant_id=str(tenant_id),
            machine_id=str(machine_id),
            coverage_start=a.coverage_start,
            meter=tuple(a.meter),
            engine=tuple(a.engine),
            fuel=tuple(a.fuel),
            positions=tuple(a.positions),
            expenses=tuple(a.expenses),
            cash=tuple(a.cash),
            exceptions=tuple(a.exceptions),
        )
        for machine_id, a in sorted(acc.items(), key=lambda kv: str(kv[0]))
    ]


def week_ends(start: datetime, end: datetime, tz: ZoneInfo) -> list[datetime]:
    """Tenant-local week ends (Monday 00:00 local, i.e. the end of Sunday) in [start, end], as aware instants."""
    local = start.astimezone(tz)
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    out: list[datetime] = []
    cursor = monday.date()
    while True:
        instant = datetime(cursor.year, cursor.month, cursor.day, tzinfo=tz)
        if instant > end:
            return out
        if instant >= start:
            out.append(instant)
        cursor += timedelta(days=7)
