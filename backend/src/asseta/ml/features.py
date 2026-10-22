"""Versioned feature catalog and point-in-time feature computation (ADR-007 "ML data foundation").

Features are pure functions over plain fact records so the database layer can feed them later without this package
knowing about SQLAlchemy. Two rules make the snapshots safe to train on:

* **Point-in-time**: a snapshot `as_of` T only sees facts whose event time *and* recording time are <= T. A meter
  capture synced from an offline phone two days late must not appear in a snapshot computed before it arrived,
  otherwise training would learn from information the live system could not have had.
* **Honest absence**: when the inputs cannot support a value the result is `None`, never `0`. A machine with no meter
  intervals has an unknown fuel efficiency, not an efficiency of zero.

Definitions are immutable per (code, version); changing a computation means bumping the version, which changes the
feature-set hash recorded with every training run.
"""

from __future__ import annotations

import hashlib
import itertools
import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol


class FeatureEntity(StrEnum):
    MACHINE = "MACHINE"
    JOB = "JOB"
    STAFF = "STAFF"


class FeatureDomain(StrEnum):
    SPATIAL = "SPATIAL"
    METER = "METER"
    TELEMETRY = "TELEMETRY"
    FINANCE = "FINANCE"
    BEHAVIOR = "BEHAVIOR"


class FactSource(StrEnum):
    """Which observed-fact stream a feature reads (documents lineage; the DB layer maps these to tables)."""

    METER_INTERVAL = "METER_INTERVAL"
    ENGINE_INTERVAL = "ENGINE_INTERVAL"
    FUEL = "FUEL"
    POSITION = "POSITION"
    EXPENSE = "EXPENSE"
    CASH = "CASH"
    EXCEPTION = "EXCEPTION"


class CashDirection(StrEnum):
    RECEIVED = "RECEIVED"
    HANDED_OVER = "HANDED_OVER"


# --- Observed fact records -----------------------------------------------------------------------------------------
# Every record carries `event_time` (when it happened in the field) and `recorded_at` (when the server learned it).


class _Fact(Protocol):
    @property
    def event_time(self) -> datetime: ...

    @property
    def recorded_at(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class MeterInterval:
    """Hour-meter hours accrued in an interval ending at `event_time` (from captures)."""

    event_time: datetime
    recorded_at: datetime
    meter_hours: float
    manual: bool = False


@dataclass(frozen=True, slots=True)
class EngineInterval:
    """Sensor engine-on hours (and idle share) ending at `event_time`; only machines with a telematics sensor."""

    event_time: datetime
    recorded_at: datetime
    engine_hours: float
    idle_hours: float = 0.0


@dataclass(frozen=True, slots=True)
class FuelEntry:
    event_time: datetime
    recorded_at: datetime
    litres: float


@dataclass(frozen=True, slots=True)
class PositionSample:
    event_time: datetime
    recorded_at: datetime
    lat: float
    lon: float
    site_id: str | None = None
    inside_geofence: bool | None = None


@dataclass(frozen=True, slots=True)
class ExpenseEntry:
    event_time: datetime
    recorded_at: datetime
    amount: float


@dataclass(frozen=True, slots=True)
class CashEntry:
    event_time: datetime
    recorded_at: datetime
    amount: float
    direction: CashDirection


@dataclass(frozen=True, slots=True)
class ExceptionEvent:
    event_time: datetime
    recorded_at: datetime
    code: str


@dataclass(frozen=True, slots=True)
class MachineFacts:
    """All observed facts for one machine of one tenant.

    `coverage_start` is when Asseta began observing the machine (registration / tracker install). Additive features
    (fuel, expenses, exceptions) may legitimately be 0 inside a covered window, but are `None` when the window starts
    before coverage, because "no records" then means "not yet observed", not "nothing happened".
    """

    tenant_id: str
    machine_id: str
    coverage_start: datetime | None = None
    meter: tuple[MeterInterval, ...] = ()
    engine: tuple[EngineInterval, ...] = ()
    fuel: tuple[FuelEntry, ...] = ()
    positions: tuple[PositionSample, ...] = ()
    expenses: tuple[ExpenseEntry, ...] = ()
    cash: tuple[CashEntry, ...] = ()
    exceptions: tuple[ExceptionEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class WindowFacts:
    """Facts visible at `as_of` inside (as_of - window, as_of]; the only thing a feature function sees."""

    as_of: datetime
    window: timedelta
    covered: bool
    meter: tuple[MeterInterval, ...]
    engine: tuple[EngineInterval, ...]
    fuel: tuple[FuelEntry, ...]
    positions: tuple[PositionSample, ...]
    expenses: tuple[ExpenseEntry, ...]
    cash: tuple[CashEntry, ...]
    exceptions: tuple[ExceptionEvent, ...]


def _visible[F: _Fact](records: Iterable[F], start: datetime, as_of: datetime) -> tuple[F, ...]:
    # Both clocks must be <= as_of: late-recorded data cannot leak backward into an earlier snapshot.
    return tuple(r for r in records if start < r.event_time <= as_of and r.recorded_at <= as_of)


def window_facts(facts: MachineFacts, as_of: datetime, window: timedelta) -> WindowFacts:
    start = as_of - window
    return WindowFacts(
        as_of=as_of,
        window=window,
        covered=facts.coverage_start is not None and facts.coverage_start <= start,
        meter=_visible(facts.meter, start, as_of),
        engine=_visible(facts.engine, start, as_of),
        fuel=_visible(facts.fuel, start, as_of),
        positions=tuple(sorted(_visible(facts.positions, start, as_of), key=lambda p: p.event_time)),
        expenses=_visible(facts.expenses, start, as_of),
        cash=_visible(facts.cash, start, as_of),
        exceptions=_visible(facts.exceptions, start, as_of),
    )


@dataclass(frozen=True, slots=True)
class Computed:
    """A feature function's result: the value plus the records it actually used (for cutoff/lineage)."""

    value: float | None
    used: tuple[_Fact, ...] = ()


FeatureFn = Callable[[WindowFacts], Computed]


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    code: str
    version: int
    entity: FeatureEntity
    domain: FeatureDomain
    window: timedelta
    unit: str
    description: str
    inputs: tuple[FactSource, ...]
    compute: FeatureFn = field(compare=False, repr=False)

    @property
    def key(self) -> str:
        return f"{self.code}@{self.version}"

    @property
    def window_label(self) -> str:
        return f"{self.window.days}d" if self.window.seconds == 0 else f"{int(self.window.total_seconds())}s"

    @property
    def label(self) -> str:
        """Human wording used in explanations ("litres per meter hour")."""
        return self.code.replace("_", " ")


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """One point-in-time feature value; mirrors the planned `feature_snapshot` table row."""

    tenant_id: str
    entity: FeatureEntity
    entity_id: str
    feature_code: str
    feature_version: int
    as_of: datetime
    window: str
    value: float | None
    data_cutoff: datetime | None
    n_inputs: int


class FeatureRegistry:
    """An ordered, immutable set of feature definitions with a stable identity hash."""

    def __init__(self, definitions: Sequence[FeatureDefinition]) -> None:
        codes = [d.code for d in definitions]
        if len(set(codes)) != len(codes):
            raise ValueError("feature codes must be unique within a feature set")
        self._defs = tuple(sorted(definitions, key=lambda d: d.code))
        self._by_code = {d.code: d for d in self._defs}

    @property
    def definitions(self) -> tuple[FeatureDefinition, ...]:
        return self._defs

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(d.code for d in self._defs)

    @property
    def max_window(self) -> timedelta:
        return max((d.window for d in self._defs), default=timedelta(0))

    def get(self, code: str) -> FeatureDefinition:
        return self._by_code[code]

    def feature_set_hash(self) -> str:
        """sha256 over sorted `code@version`; any version bump yields a different hash (and a new model lineage)."""
        payload = "\n".join(sorted(d.key for d in self._defs)).encode()
        return hashlib.sha256(payload).hexdigest()


def compute_snapshots(registry: FeatureRegistry, facts: MachineFacts, as_of: datetime) -> list[FeatureSnapshot]:
    """Compute every registered feature for one machine at `as_of` (window filtering done once per window)."""
    cache: dict[timedelta, WindowFacts] = {}
    out: list[FeatureSnapshot] = []
    for d in registry.definitions:
        wf = cache.get(d.window)
        if wf is None:
            wf = cache[d.window] = window_facts(facts, as_of, d.window)
        result = d.compute(wf)
        value = None if result.value is None or not math.isfinite(result.value) else float(result.value)
        out.append(
            FeatureSnapshot(
                tenant_id=facts.tenant_id,
                entity=d.entity,
                entity_id=facts.machine_id,
                feature_code=d.code,
                feature_version=d.version,
                as_of=as_of,
                window=d.window_label,
                value=value,
                data_cutoff=max((r.recorded_at for r in result.used), default=None),
                n_inputs=len(result.used),
            )
        )
    return out


# --- R1 machine-week feature computations ---------------------------------------------------------------------------

MIN_METER_HOURS_FOR_RATIO = 0.5  # below this a litres/hour ratio is dominated by rounding noise
MAX_POSITION_GAP = timedelta(minutes=30)  # longer gaps are tracker-offline time, not observed time outside a fence
_EARTH_RADIUS_KM = 6371.0088


def _sum_meter(w: WindowFacts) -> Computed:
    return Computed(sum(m.meter_hours for m in w.meter), w.meter) if w.meter else Computed(None)


def _sum_engine(w: WindowFacts) -> Computed:
    return Computed(sum(e.engine_hours for e in w.engine), w.engine) if w.engine else Computed(None)


def _meter_vs_engine_gap(w: WindowFacts) -> Computed:
    meter, engine = _sum_meter(w), _sum_engine(w)
    if meter.value is None or engine.value is None:
        return Computed(None)
    return Computed(engine.value - meter.value, meter.used + engine.used)


def _idle_engine_ratio(w: WindowFacts) -> Computed:
    engine = _sum_engine(w)
    if engine.value is None or engine.value <= 0:
        return Computed(None)
    return Computed(sum(e.idle_hours for e in w.engine) / engine.value, engine.used)


def _haversine_km(a: PositionSample, b: PositionSample) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _km_travelled(w: WindowFacts) -> Computed:
    pts = w.positions
    if len(pts) < 2:
        return Computed(None)
    return Computed(sum(_haversine_km(a, b) for a, b in itertools.pairwise(pts)), pts)


def _distinct_sites(w: WindowFacts) -> Computed:
    if not w.positions:
        return Computed(None)
    return Computed(float(len({p.site_id for p in w.positions if p.site_id is not None})), w.positions)


def _outside_geofence_minutes(w: WindowFacts) -> Computed:
    known = [p for p in w.positions if p.inside_geofence is not None]
    if len(known) < 2:
        return Computed(None)
    minutes = 0.0
    for a, b in itertools.pairwise(known):
        if a.inside_geofence is False:
            minutes += min(b.event_time - a.event_time, MAX_POSITION_GAP).total_seconds() / 60
    return Computed(minutes, tuple(known))


def _additive[F: _Fact](w: WindowFacts, records: tuple[F, ...], value: Callable[[F], float]) -> Computed:
    # Zero is only a real observation when the whole window was covered (see MachineFacts docstring).
    if not records and not w.covered:
        return Computed(None)
    return Computed(float(sum(value(r) for r in records)), records)


def _fuel_litres(w: WindowFacts) -> Computed:
    return _additive(w, w.fuel, lambda f: f.litres)


def _litres_per_meter_hour(w: WindowFacts) -> Computed:
    meter, fuel = _sum_meter(w), _fuel_litres(w)
    if meter.value is None or meter.value < MIN_METER_HOURS_FOR_RATIO or fuel.value is None:
        return Computed(None)
    return Computed(fuel.value / meter.value, meter.used + fuel.used)


def _expense_total(w: WindowFacts) -> Computed:
    return _additive(w, w.expenses, lambda e: e.amount)


def _cash_outstanding(w: WindowFacts) -> Computed:
    return _additive(w, w.cash, lambda c: c.amount if c.direction is CashDirection.RECEIVED else -c.amount)


def _exceptions_count(w: WindowFacts) -> Computed:
    return _additive(w, w.exceptions, lambda _e: 1.0)


def _manual_capture_ratio(w: WindowFacts) -> Computed:
    if not w.meter:
        return Computed(None)
    return Computed(sum(1 for m in w.meter if m.manual) / len(w.meter), w.meter)


_WEEK = timedelta(days=7)
_M, _D, _S = FeatureEntity.MACHINE, FeatureDomain, FactSource


def _def(
    code: str, domain: FeatureDomain, unit: str, desc: str, inputs: tuple[FactSource, ...], fn: FeatureFn
) -> FeatureDefinition:
    return FeatureDefinition(code, 1, _M, domain, _WEEK, unit, desc, inputs, fn)


R1_FEATURE_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    _def("meter_hours", _D.METER, "h", "Hour-meter hours captured in the week.", (_S.METER_INTERVAL,), _sum_meter),
    _def(
        "engine_hours",
        _D.TELEMETRY,
        "h",
        "Sensor engine-on hours (sensor machines only).",
        (_S.ENGINE_INTERVAL,),
        _sum_engine,
    ),
    _def(
        "meter_vs_engine_gap",
        _D.TELEMETRY,
        "h",
        "Engine-on hours minus captured meter hours.",
        (_S.METER_INTERVAL, _S.ENGINE_INTERVAL),
        _meter_vs_engine_gap,
    ),
    _def(
        "idle_engine_ratio",
        _D.TELEMETRY,
        "ratio",
        "Share of engine-on time spent idling.",
        (_S.ENGINE_INTERVAL,),
        _idle_engine_ratio,
    ),
    _def(
        "km_travelled", _D.SPATIAL, "km", "Great-circle distance between tracker fixes.", (_S.POSITION,), _km_travelled
    ),
    _def(
        "distinct_sites",
        _D.SPATIAL,
        "count",
        "Distinct sites visited by tracker fixes.",
        (_S.POSITION,),
        _distinct_sites,
    ),
    _def(
        "outside_geofence_minutes",
        _D.SPATIAL,
        "min",
        "Observed minutes outside the job geofence (gaps capped).",
        (_S.POSITION,),
        _outside_geofence_minutes,
    ),
    _def("fuel_litres", _D.FINANCE, "l", "Fuel litres logged.", (_S.FUEL,), _fuel_litres),
    _def(
        "litres_per_meter_hour",
        _D.METER,
        "l/h",
        "Fuel litres per captured meter hour.",
        (_S.FUEL, _S.METER_INTERVAL),
        _litres_per_meter_hour,
    ),
    _def(
        "expense_total",
        _D.FINANCE,
        "currency",
        "Field expenses recorded against the machine.",
        (_S.EXPENSE,),
        _expense_total,
    ),
    _def(
        "cash_outstanding",
        _D.FINANCE,
        "currency",
        "Cash received less cash handed over in the week.",
        (_S.CASH,),
        _cash_outstanding,
    ),
    _def(
        "exceptions_count",
        _D.BEHAVIOR,
        "count",
        "Deterministic meter/tracking exceptions raised.",
        (_S.EXCEPTION,),
        _exceptions_count,
    ),
    _def(
        "manual_capture_ratio",
        _D.BEHAVIOR,
        "ratio",
        "Share of meter captures entered manually.",
        (_S.METER_INTERVAL,),
        _manual_capture_ratio,
    ),
)

R1_FEATURES = FeatureRegistry(R1_FEATURE_DEFINITIONS)
