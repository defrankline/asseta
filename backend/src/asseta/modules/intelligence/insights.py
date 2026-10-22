"""Baseline insights (ADR-007 "Baseline insights", prompt.md R1-H): fuel efficiency and utilisation per machine from
the tenant's weekly point-in-time feature snapshots (source `observed` only), and the weekly cash-flow trend from
verified receipts and approved expenses. Everything runs in the caller's tenant RLS scope.

Each insight is either READY with values, or INSUFFICIENT_DATA with the minimum history needed and what is missing —
never a number computed from too little evidence. Comparisons are against the machine's own history (median and a
robust band), not against other machines or people.
"""

import math
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.ml.baseline import fuel_efficiency_insight, robust_band, utilization_insight, weekly_trend
from asseta.modules.expenses.models import Expense, ExpenseStatus
from asseta.modules.finance.models import CustomerPayment, SettlementStatus
from asseta.modules.fleet.models import Machine
from asseta.modules.intelligence.facts import week_ends
from asseta.modules.intelligence.feature_store import tenant_zone
from asseta.modules.intelligence.insights_dto import (
    CashFlowInsightDto,
    CashFlowWeekDto,
    FuelEfficiencyInsightDto,
    Trend,
    UtilisationInsightDto,
    WeeklyHoursDto,
)
from asseta.modules.intelligence.ml_models import SOURCE_OBSERVED, FeatureSnapshotRecord
from asseta.modules.tenancy.models import TenantSettings

HISTORY_WEEKS = 12
FUEL_MIN_WEEKS = 4
UTILISATION_MIN_WEEKS = 4
CASHFLOW_MIN_WEEKS = 6
CURRENT_MAX_AGE = timedelta(days=14)  # a "current" fuel week older than this is not current
_CODES = ("litres_per_meter_hour", "meter_hours", "engine_hours", "exceptions_count")
_CENT = Decimal("0.0001")
METHOD = [
    "Fuel efficiency: litres per captured meter hour in the latest week, compared with the median of the machine's "
    f"own previous weeks; outside the band median +/- max(3 x MAD x 1.4826, 15% of median) is shown as outside the "
    f"usual range. Needs {FUEL_MIN_WEEKS} previous weeks with both fuel and meter hours.",
    "Utilisation: captured meter hours (engine hours when no reading was captured) per calendar day of the observed "
    f"weeks, with the weekly trend. Needs {UTILISATION_MIN_WEEKS} observed weeks.",
    "Cash flow: verified customer receipts minus approved expenses per tenant-local week, with a least-squares trend. "
    f"Needs {CASHFLOW_MIN_WEEKS} complete weeks since the first recorded receipt or expense.",
    "Only weekly snapshots computed from your own records are used (point-in-time: facts recorded after a week's end "
    "never change that week).",
]


@dataclass(frozen=True)
class _Week:
    as_of: datetime
    values: dict[str, float | None]


def _machines(session: Session) -> list[Machine]:
    return list(
        session.execute(select(Machine).where(Machine.deactivated_at.is_(None)).order_by(Machine.asset_code)).scalars()
    )


def _weekly(session: Session, tenant_id: uuid.UUID, now: datetime) -> dict[uuid.UUID, list[_Week]]:
    rows = session.execute(
        select(
            FeatureSnapshotRecord.entity_id,
            FeatureSnapshotRecord.as_of,
            FeatureSnapshotRecord.feature_code,
            FeatureSnapshotRecord.value,
        ).where(
            FeatureSnapshotRecord.tenant_id == tenant_id,
            FeatureSnapshotRecord.source == SOURCE_OBSERVED,
            FeatureSnapshotRecord.feature_code.in_(_CODES),
            FeatureSnapshotRecord.as_of > now - timedelta(weeks=HISTORY_WEEKS),
            FeatureSnapshotRecord.as_of <= now,
        )
    ).all()
    grouped: dict[uuid.UUID, dict[datetime, dict[str, float | None]]] = defaultdict(dict)
    for entity_id, as_of, code, value in rows:
        grouped[entity_id].setdefault(as_of, {})[code] = None if value is None else float(value)
    return {eid: [_Week(as_of, values) for as_of, values in sorted(weeks.items())] for eid, weeks in grouped.items()}


def _trend(slope: float, scale: float) -> Trend:
    if abs(slope) <= 0.05 * max(abs(scale), 1e-9):
        return "FLAT"
    return "UP" if slope > 0 else "DOWN"


def fuel_item(m: Machine, weeks: list[_Week], now: datetime) -> FuelEfficiencyInsightDto:
    series = [(w.as_of, v) for w in weeks if (v := w.values.get("litres_per_meter_hour")) is not None]
    current = series[-1] if series and now - series[-1][0] <= CURRENT_MAX_AGE else None
    history = [v for _, v in (series[:-1] if current else series)]
    base = fuel_efficiency_insight(history, current[1] if current else None, FUEL_MIN_WEEKS)
    common = {"machine_id": m.id, "asset_code": m.asset_code, "machine_name": m.name}
    if base.status.value != "READY" or current is None:
        missing = []
        if current is None:
            missing.append("No week in the last two with both fuel litres and at least 0.5 captured meter hours.")
        if len(history) < FUEL_MIN_WEEKS:
            missing.append(
                f"{len(history)} previous weeks with both fuel and meter hours; at least {FUEL_MIN_WEEKS} needed."
            )
        return FuelEfficiencyInsightDto(
            **common,
            status="INSUFFICIENT_DATA",
            week_ending=current[0] if current else None,
            current_litres_per_hour=None,
            median_litres_per_hour=None,
            band_low=None,
            band_high=None,
            outside_usual_range=None,
            weeks_observed=len(history),
            min_weeks_required=FUEL_MIN_WEEKS,
            message=base.message,
            missing=missing,
        )
    med, low, high = robust_band(history)
    outside = not (low <= current[1] <= high)
    verdict = "outside this machine's usual range — worth a look" if outside else "within this machine's usual range"
    return FuelEfficiencyInsightDto(
        **common,
        status="READY",
        week_ending=current[0],
        current_litres_per_hour=round(current[1], 3),
        median_litres_per_hour=round(med, 3),
        band_low=round(max(low, 0.0), 3),
        band_high=round(high, 3),
        outside_usual_range=outside,
        weeks_observed=len(history),
        min_weeks_required=FUEL_MIN_WEEKS,
        message=f"{base.message}; {verdict}.",
        missing=[],
    )


def utilisation_item(m: Machine, weeks: list[_Week]) -> UtilisationInsightDto:
    weekly: list[WeeklyHoursDto] = []
    for w in weeks:
        meter, engine = w.values.get("meter_hours"), w.values.get("engine_hours")
        covered = w.values.get("exceptions_count") is not None  # additive features are NULL before coverage
        if meter is not None:
            weekly.append(WeeklyHoursDto(week_ending=w.as_of, hours=round(meter, 2), source="meter"))
        elif engine is not None:
            weekly.append(WeeklyHoursDto(week_ending=w.as_of, hours=round(engine, 2), source="engine"))
        elif covered:
            weekly.append(WeeklyHoursDto(week_ending=w.as_of, hours=0.0, source="none"))
    hours = [h.hours for h in weekly]
    days = 7 * len(weekly)
    base = utilization_insight(hours, days, UTILISATION_MIN_WEEKS)
    common = {"machine_id": m.id, "asset_code": m.asset_code, "machine_name": m.name, "weekly": weekly}
    if base.status.value != "READY" or base.value is None:
        return UtilisationInsightDto(
            **common,
            status="INSUFFICIENT_DATA",
            hours_per_available_day=None,
            available_days=days,
            weeks_observed=len(weekly),
            min_weeks_required=UTILISATION_MIN_WEEKS,
            trend_hours_per_week=None,
            trend=None,
            message=base.message,
            missing=[
                f"{len(weekly)} observed weeks with meter or engine hours; at least {UTILISATION_MIN_WEEKS} needed."
            ],
        )
    slope = weekly_trend(hours)
    trend = _trend(slope, statistics.mean(hours))
    return UtilisationInsightDto(
        **common,
        status="READY",
        hours_per_available_day=round(base.value, 3),
        available_days=days,
        weeks_observed=len(weekly),
        min_weeks_required=UTILISATION_MIN_WEEKS,
        trend_hours_per_week=round(slope, 3),
        trend=trend,
        message=f"{base.message}; weekly hours trend {trend.lower()} ({slope:+.1f} h per week).",
        missing=[],
    )


def machine_insights(
    session: Session, tenant_id: uuid.UUID, now: datetime
) -> tuple[list[FuelEfficiencyInsightDto], list[UtilisationInsightDto]]:
    weekly = _weekly(session, tenant_id, now)
    machines = _machines(session)
    return (
        [fuel_item(m, weekly.get(m.id, []), now) for m in machines],
        [utilisation_item(m, weekly.get(m.id, [])) for m in machines],
    )


def _money(value: float | Decimal) -> Decimal:
    return Decimal(repr(value) if isinstance(value, float) else value).quantize(_CENT)


def cash_flow(session: Session, tenant_id: uuid.UUID, now: datetime) -> CashFlowInsightDto:
    tz = tenant_zone(session, tenant_id)
    currency = (
        session.execute(
            select(TenantSettings.currency).where(TenantSettings.tenant_id == tenant_id)
        ).scalar_one_or_none()
        or "TZS"
    )
    ends = week_ends(now - timedelta(weeks=HISTORY_WEEKS + 1), now, tz)[-HISTORY_WEEKS:]
    receipts = select(func.min(CustomerPayment.received_at)).where(
        CustomerPayment.status == SettlementStatus.VERIFIED, CustomerPayment.currency == currency
    )
    spent = select(func.min(Expense.incurred_at)).where(
        Expense.status == ExpenseStatus.APPROVED, Expense.currency == currency
    )
    firsts = [t for t in (session.execute(receipts).scalar_one(), session.execute(spent).scalar_one()) if t]
    first = min(firsts) if firsts else None
    weeks: list[CashFlowWeekDto] = []
    for end in ends:
        start = end - timedelta(days=7)
        if first is None or end <= first:
            continue
        r = session.execute(
            select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                CustomerPayment.status == SettlementStatus.VERIFIED,
                CustomerPayment.currency == currency,
                CustomerPayment.received_at >= start,
                CustomerPayment.received_at < end,
            )
        ).scalar_one()
        e = session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.status == ExpenseStatus.APPROVED,
                Expense.currency == currency,
                Expense.incurred_at >= start,
                Expense.incurred_at < end,
            )
        ).scalar_one()
        weeks.append(
            CashFlowWeekDto(week_start=start, week_end=end, receipts=_money(r), expenses=_money(e), net=_money(r - e))
        )
    nets = [float(w.net) for w in weeks]
    common = {
        "currency": currency,
        "weeks": weeks,
        "weeks_observed": len(weeks),
        "min_weeks_required": CASHFLOW_MIN_WEEKS,
    }
    if len(weeks) < CASHFLOW_MIN_WEEKS:
        missing = (
            ["No verified receipts or approved expenses recorded yet."]
            if first is None
            else [f"{len(weeks)} complete weeks of cash history; at least {CASHFLOW_MIN_WEEKS} needed."]
        )
        return CashFlowInsightDto(
            **common,
            status="INSUFFICIENT_DATA",
            trend_per_week=None,
            trend=None,
            median_weekly_net=None,
            message=f"{len(weeks)} weeks of cash history available; at least {CASHFLOW_MIN_WEEKS} needed for a trend.",
            missing=missing,
        )
    slope = weekly_trend(nets)
    scale = statistics.mean(abs(n) for n in nets) if any(nets) else 0.0
    trend = _trend(slope, scale)
    word = {"UP": "improving", "DOWN": "declining", "FLAT": "flat"}[trend]
    return CashFlowInsightDto(
        **common,
        status="READY",
        trend_per_week=_money(slope if math.isfinite(slope) else 0.0),
        trend=trend,
        median_weekly_net=_money(statistics.median(nets)),
        message=f"Weekly net cash {word} by {abs(slope):,.2f} {currency} per week over {len(weeks)} weeks.",
        missing=[],
    )
