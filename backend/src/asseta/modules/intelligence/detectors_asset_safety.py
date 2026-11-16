"""DEC-031 Phase 2 (asset safety) data loading: fuel against engine hours per machine-period (S2). Only closed
tenant-local periods inside the sweep lookback are evaluated, so each summary sees the whole period; dedupe keys make
re-runs no-ops. Runs in the tenant's RLS scope. The rule is a FRAUD_CONTROLS threshold that is off (None) by
default."""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import FuelEvent, FuelEventType
from asseta.modules.finance.common import tenant_settings
from asseta.modules.fleet.models import Machine
from asseta.modules.intelligence.rules import MachineFuelPeriod, SignalFinding, machine_fuel_above_norm
from asseta.modules.meter.engine_hours import load_machine_ledger
from asseta.modules.policy.schemas import FraudControlsPolicy, FuelCheckPeriod, PolicyScope, PolicyType
from asseta.modules.policy.service import EffectivePolicy, PolicyService

ZERO = Decimal(0)
FUEL_INTO_MACHINE = (FuelEventType.ISSUE, FuelEventType.PURCHASE)
NORM_KEY = "fuel_litres_per_hour_max"
NORM_SOURCES = {
    PolicyScope.MACHINE: "MACHINE",
    PolicyScope.MACHINE_CATEGORY: "MACHINE_CATEGORY",
    PolicyScope.TENANT: "TENANT",
    PolicyScope.PLATFORM: "PLATFORM",
}
Period = tuple[str, datetime, datetime]  # key, UTC start, UTC end


def overlap_fraction(start: datetime, end: datetime, w0: datetime | None, w1: datetime | None) -> Decimal:
    """Share of [start, end] inside [w0, w1) (None = unbounded). A zero-length span counts where it starts."""
    lo = start if w0 is None else max(start, w0)
    hi = end if w1 is None else min(end, w1)
    total = (end - start).total_seconds()
    if total <= 0:
        inside = (w0 is None or start >= w0) and (w1 is None or start < w1)
        return Decimal(1) if inside else ZERO
    part = (hi - lo).total_seconds()
    if part <= 0:
        return ZERO
    return Decimal(str(part)) / Decimal(str(total))


def _closed_days(tz: ZoneInfo, since: datetime, now: datetime) -> list[tuple[date, datetime, datetime]]:
    """Tenant-local days that have ended by `now` and end after `since`."""
    day = since.astimezone(tz).date()
    out: list[tuple[date, datetime, datetime]] = []
    while True:
        start = datetime.combine(day, time.min, tz).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, tz).astimezone(UTC)
        if end > now:
            return out
        if end > since:
            out.append((day, start, end))
        day += timedelta(days=1)


def _closed_periods(kind: FuelCheckPeriod, tz: ZoneInfo, since: datetime, now: datetime) -> list[Period]:
    if kind is FuelCheckPeriod.DAY:
        return [(d.isoformat(), a, b) for d, a, b in _closed_days(tz, since, now)]
    first = since.astimezone(tz).date()
    monday = first - timedelta(days=first.weekday())
    out: list[Period] = []
    while True:
        start = datetime.combine(monday, time.min, tz).astimezone(UTC)
        end = datetime.combine(monday + timedelta(days=7), time.min, tz).astimezone(UTC)
        if end > now:
            return out
        if end > since:
            iso = monday.isocalendar()
            out.append((f"{iso.year}-W{iso.week:02d}", start, end))
        monday += timedelta(days=7)


# --- S2: fuel against engine hours per machine -----------------------------------------------------------------
def _norm(
    policies: PolicyService, tenant_id: uuid.UUID, machine_id: uuid.UUID, at: datetime
) -> tuple[EffectivePolicy[FraudControlsPolicy], str]:
    """The machine's effective norm and where it is set (machine > machine category > tenant)."""
    eff = policies.fraud_controls(tenant_id, machine_id, at=at)
    source = policies.value_source(PolicyType.FRAUD_CONTROLS, NORM_KEY, tenant_id, machine_id=machine_id, at=at)
    return eff, NORM_SOURCES.get(source, "TENANT") if source is not None else "TENANT"


def detect_machine_fuel(s: Session, tenant_id: uuid.UUID, now: datetime, since: datetime) -> list[SignalFinding]:
    """Per machine and closed tenant-local period (`fuel_check_period`): litres issued or purchased into the machine
    vs its engine hours from the meter ledger (split by wall-clock time). A period is
    judged only when the machine's readings cover it from start to end."""
    tenant_eff = PolicyService(s).fraud_controls(tenant_id, at=now)
    kind = tenant_eff.policy.fuel_check_period
    if kind is None:
        return []
    periods = _closed_periods(kind, ZoneInfo(tenant_settings(s, tenant_id).timezone), since, now)
    if not periods:
        return []
    start, end = periods[0][1], periods[-1][2]
    by_machine: dict[uuid.UUID, list[FuelEvent]] = defaultdict(list)
    for f in s.execute(
        select(FuelEvent).where(
            FuelEvent.machine_id.is_not(None),
            FuelEvent.event_type.in_(FUEL_INTO_MACHINE),
            FuelEvent.occurred_at >= start,
            FuelEvent.occurred_at < end,
        )
    ).scalars():
        assert f.machine_id is not None
        by_machine[f.machine_id].append(f)
    policies, findings = PolicyService(s), []
    for machine_id, fuel in sorted(by_machine.items(), key=lambda kv: str(kv[0])):
        eff, source = _norm(policies, tenant_id, machine_id, now)
        norm = eff.policy.fuel_litres_per_hour_max
        machine = s.get(Machine, machine_id)
        if norm is None or machine is None:
            continue
        intervals = load_machine_ledger(s, tenant_id, machine, now).ledger.intervals
        if not intervals:
            continue
        first, last = min(i.start.at for i in intervals), max(i.end.at for i in intervals)
        for key, p0, p1 in periods:
            events = [f for f in fuel if p0 <= f.occurred_at < p1]
            if not events or first > p0 or last < p1:
                continue  # no fuel, or engine hours not known for the whole period
            hours = sum((i.hours * overlap_fraction(i.start.at, i.end.at, p0, p1) for i in intervals), ZERO)
            period = MachineFuelPeriod(
                machine_id,
                kind.value,
                key,
                p0,
                p1,
                sum((f.litres for f in events), Decimal(0)),
                hours,
                tuple(f.id for f in events),
                tuple(f.recorded_by for f in events if f.recorded_by),
            )
            if finding := machine_fuel_above_norm(period, norm, source, eff.version_stamp):
                findings.append(finding)
    return findings
