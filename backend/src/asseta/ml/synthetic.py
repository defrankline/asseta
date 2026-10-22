"""Deterministic synthetic fleet for tests and demos — never used in production paths.

Generates plausible machine-day facts (weekday shifts, light Saturdays, idle Sundays, refuelling every few working
days, hourly tracker fixes around a site, occasional expenses, weekly cash hand-overs, rare exceptions, some
offline-late syncs) for N machines over W weeks, plus a few labelled anomalous machine-weeks so a demo can show
what shadow mode would have surfaced. Labels exist only here; production has no "anomaly = true" field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import numpy as np

from asseta.ml.features import (
    R1_FEATURES,
    CashDirection,
    CashEntry,
    EngineInterval,
    ExceptionEvent,
    ExpenseEntry,
    FeatureRegistry,
    FeatureSnapshot,
    FuelEntry,
    MachineFacts,
    MeterInterval,
    PositionSample,
    compute_snapshots,
)

DEFAULT_START = datetime(2026, 1, 5, tzinfo=UTC)  # a Monday
_BASE_LAT, _BASE_LON = -15.4167, 28.2833


class SyntheticAnomalyKind(StrEnum):
    EXCESS_FUEL = "EXCESS_FUEL"  # fuel logged at ~2.5x the machine's usual rate
    UNCAPTURED_ENGINE = "UNCAPTURED_ENGINE"  # engine ran on days with no meter capture (sensor machines)
    OFF_SITE = "OFF_SITE"  # hours spent far outside the geofence


@dataclass(frozen=True, slots=True)
class SyntheticAnomaly:
    machine_id: str
    week_end: datetime  # equals the as_of of the machine-week snapshot it affects
    kind: SyntheticAnomalyKind


@dataclass(frozen=True, slots=True)
class SyntheticFleet:
    tenant_id: str
    facts: tuple[MachineFacts, ...]
    anomalies: tuple[SyntheticAnomaly, ...]
    week_ends: tuple[datetime, ...]

    def is_anomalous(self, machine_id: str, as_of: datetime) -> bool:
        return any(a.machine_id == machine_id and a.week_end == as_of for a in self.anomalies)


def _offset(lat: float, lon: float, north_km: float, east_km: float) -> tuple[float, float]:
    return lat + north_km / 111.0, lon + east_km / (111.0 * math.cos(math.radians(lat)))


def _machine(
    rng: np.random.Generator,
    tenant_id: str,
    machine_id: str,
    start: datetime,
    weeks: int,
    anomalies: dict[int, SyntheticAnomalyKind],
    sensor: bool,
) -> MachineFacts:
    base_hours = rng.uniform(5.0, 9.0)
    lpmh = rng.uniform(8.0, 22.0)
    idle_share = rng.uniform(0.1, 0.3)
    manual_prob = rng.uniform(0.05, 0.3)
    site_lat, site_lon = _offset(_BASE_LAT, _BASE_LON, rng.uniform(-30, 30), rng.uniform(-30, 30))
    site_no = 0
    meter: list[MeterInterval] = []
    engine: list[EngineInterval] = []
    fuel: list[FuelEntry] = []
    positions: list[PositionSample] = []
    expenses: list[ExpenseEntry] = []
    cash: list[CashEntry] = []
    exceptions: list[ExceptionEvent] = []
    unfuelled_hours = 0.0
    for day in range(weeks * 7):
        week = day // 7
        kind = anomalies.get(week)
        date = start + timedelta(days=day)
        dow = date.weekday()
        if day % 28 == 0 and day:
            site_no += 1  # machine moves to a new contract site every four weeks
            site_lat, site_lon = _offset(site_lat, site_lon, rng.uniform(-8, 8), rng.uniform(-8, 8))
        if dow < 5:
            hours = max(0.0, base_hours * rng.normal(1.0, 0.15))
        elif dow == 5 and rng.random() < 0.6:
            hours = max(0.0, 0.4 * base_hours * rng.normal(1.0, 0.2))
        else:
            hours = 0.0
        end = date + timedelta(hours=17)
        site = f"{machine_id}-site-{site_no}"
        if hours > 0:
            lag = timedelta(hours=float(rng.uniform(0.1, 2.0)))
            if rng.random() < 0.05:
                lag += timedelta(days=float(rng.uniform(1.0, 3.0)))  # offline phone synced late
            skip_meter = kind is SyntheticAnomalyKind.UNCAPTURED_ENGINE and dow in (1, 2, 3)
            if not skip_meter:
                meter.append(
                    MeterInterval(
                        end, end + lag, round(hours * rng.normal(1.0, 0.01), 1), bool(rng.random() < manual_prob)
                    )
                )
            if sensor:
                eng = hours * rng.normal(1.02, 0.02)
                engine.append(EngineInterval(end, end + timedelta(minutes=5), eng, eng * idle_share))
            unfuelled_hours += hours
            if rng.random() < 0.45:
                rate = lpmh * (2.5 if kind is SyntheticAnomalyKind.EXCESS_FUEL else 1.0)
                litres = rate * unfuelled_hours * rng.normal(1.0, 0.07)
                fuel.append(FuelEntry(end, end + timedelta(minutes=30), round(litres, 1)))
                unfuelled_hours = 0.0
            if rng.random() < 0.15:
                expenses.append(ExpenseEntry(end, end + timedelta(hours=1), round(float(rng.lognormal(4.0, 0.5)), 2)))
            if rng.random() < 0.03:
                exceptions.append(ExceptionEvent(end, end + timedelta(minutes=1), "METER_GAP"))
        fixes = range(7, 18) if hours > 0 else (8, 13, 18)
        for h in fixes:
            t = date + timedelta(hours=h)
            lat, lon = _offset(site_lat, site_lon, rng.normal(0, 0.1), rng.normal(0, 0.1))
            inside = not (rng.random() < 0.02)
            if kind is SyntheticAnomalyKind.OFF_SITE and dow in (2, 4) and 10 <= h <= 15:
                lat, lon = _offset(site_lat, site_lon, 15.0 + rng.normal(0, 0.5), 5.0)
                inside = False
            positions.append(PositionSample(t, t + timedelta(seconds=30), lat, lon, site, inside))
        if dow == 4:
            received = round(float(rng.uniform(500, 1500)), 2)
            cash.append(CashEntry(end, end + timedelta(minutes=10), received, CashDirection.RECEIVED))
            handed = received if rng.random() < 0.9 else round(received * 0.5, 2)
            ht = end + timedelta(hours=20)
            cash.append(CashEntry(ht, ht + timedelta(minutes=10), handed, CashDirection.HANDED_OVER))
    return MachineFacts(
        tenant_id,
        machine_id,
        start,
        tuple(meter),
        tuple(engine),
        tuple(fuel),
        tuple(positions),
        tuple(expenses),
        tuple(cash),
        tuple(exceptions),
    )


def generate_fleet(
    tenant_id: str = "tenant-demo",
    n_machines: int = 12,
    weeks: int = 16,
    seed: int = 7,
    start: datetime = DEFAULT_START,
    anomaly_rate: float = 0.04,
    sensor_share: float = 0.7,
) -> SyntheticFleet:
    """Same arguments -> identical fleet. Anomalies are placed only after the first three (warm-up) weeks."""
    rng = np.random.default_rng(seed)
    week_ends = tuple(start + timedelta(days=7 * (w + 1)) for w in range(weeks))
    facts: list[MachineFacts] = []
    labels: list[SyntheticAnomaly] = []
    for m in range(n_machines):
        machine_id = f"M{m + 1:03d}"
        sensor = bool(rng.random() < sensor_share)
        kinds = [k for k in SyntheticAnomalyKind if sensor or k is not SyntheticAnomalyKind.UNCAPTURED_ENGINE]
        chosen: dict[int, SyntheticAnomalyKind] = {}
        for w in range(3, weeks):
            if rng.random() < anomaly_rate:
                chosen[w] = kinds[int(rng.integers(len(kinds)))]
        labels.extend(SyntheticAnomaly(machine_id, week_ends[w], k) for w, k in sorted(chosen.items()))
        facts.append(_machine(np.random.default_rng([seed, m]), tenant_id, machine_id, start, weeks, chosen, sensor))
    return SyntheticFleet(tenant_id, tuple(facts), tuple(labels), week_ends)


def fleet_snapshots(fleet: SyntheticFleet, registry: FeatureRegistry = R1_FEATURES) -> list[FeatureSnapshot]:
    """Weekly point-in-time snapshots (as_of = each week end) for every machine."""
    return [s for f in fleet.facts for as_of in fleet.week_ends for s in compute_snapshots(registry, f, as_of)]
