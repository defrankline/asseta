"""Pure risk-signal rules (ADR-007). Each rule takes plain facts plus policy thresholds and returns `SignalFinding`s
whose evidence holds facts and thresholds only — never a conclusion about a person. Deterministic and identical for
the periodic sweep and event-driven runs; the dedupe key makes every run idempotent."""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from asseta.modules.intelligence.models import RuleCode, SignalSeverity, SubjectType

RULE_VERSIONS: dict[RuleCode, int] = dict.fromkeys(RuleCode, 1)
LITRES_PER_HOUR_PLACES = Decimal("0.001")


@dataclass(frozen=True)
class SignalFinding:
    rule_code: RuleCode
    severity: SignalSeverity
    subject_type: SubjectType
    subject_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    dedupe_key: str
    evidence: dict[str, Any]
    policy_version: str
    machine_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID | None = None
    involved_user_ids: tuple[uuid.UUID, ...] = ()
    involved_staff_ids: tuple[uuid.UUID, ...] = ()


def _iso(at: datetime | None) -> str | None:
    return at.isoformat() if at is not None else None


def _ids(values: Iterable[uuid.UUID | None]) -> tuple[uuid.UUID, ...]:
    return tuple(sorted({v for v in values if v is not None}, key=str))


# --- MACHINE_FUEL_ABOVE_NORM (DEC-031 S2) ----------------------------------------------------------------------
@dataclass(frozen=True)
class MachineFuelPeriod:
    """All fuel issued or purchased into a machine in one tenant-local period vs its engine hours (meter ledger)."""

    machine_id: uuid.UUID
    period_kind: str  # DAY | WEEK
    period_key: str  # 2026-11-01 | 2026-W44
    start: datetime
    end: datetime
    litres_into_machine: Decimal
    engine_hours: Decimal
    fuel_event_ids: tuple[uuid.UUID, ...]
    recorded_by: tuple[uuid.UUID, ...]


def machine_fuel_above_norm(
    p: MachineFuelPeriod, norm: Decimal | None, norm_source: str, policy_version: str
) -> SignalFinding | None:
    """Litres per engine hour above the norm for the machine. No signal when the rule is off (no norm) or the
    period's engine hours are zero."""
    if norm is None or p.engine_hours <= 0:
        return None
    rate = (p.litres_into_machine / p.engine_hours).quantize(LITRES_PER_HOUR_PLACES)
    if rate <= norm:
        return None
    hours = p.engine_hours.quantize(Decimal("0.01"))
    return SignalFinding(
        RuleCode.MACHINE_FUEL_ABOVE_NORM,
        SignalSeverity.WARNING,
        SubjectType.MACHINE,
        p.machine_id,
        p.start,
        p.end,
        f"MFUEL:{p.machine_id}:{p.period_key}",
        {
            "period_kind": p.period_kind,
            "period": p.period_key,
            "litres_into_machine": str(p.litres_into_machine),
            "engine_hours": str(hours),
            "litres_per_engine_hour": str(rate),
            "norm_litres_per_engine_hour": str(norm),
            "norm_source": norm_source,
            "fuel_event_ids": [str(i) for i in p.fuel_event_ids],
        },
        policy_version=policy_version,
        machine_id=p.machine_id,
        involved_user_ids=_ids(p.recorded_by),
    )


# --- DUPLICATE_RECEIPT -----------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ReceiptUse:
    expense_id: uuid.UUID
    sha256: str
    incurred_at: datetime
    submitted_at: datetime
    submitted_by: uuid.UUID | None
    custodian_staff_id: uuid.UUID | None
    machine_id: uuid.UUID | None
    amount: Decimal
    currency: str


def duplicate_receipts(
    uses: Sequence[ReceiptUse],
    lookback_days: int,
    policy_version: str,
    candidates: set[uuid.UUID] | None = None,
) -> list[SignalFinding]:
    """The same receipt image (SHA-256) on another expense whose incurred time is within `lookback_days`. Reported
    on the later-submitted expense; `candidates` limits which expenses may be reported."""
    by_hash: dict[str, list[ReceiptUse]] = defaultdict(list)
    for u in uses:
        by_hash[u.sha256].append(u)
    window = timedelta(days=lookback_days)
    out = []
    for sha, group in by_hash.items():
        ordered = sorted({u.expense_id: u for u in group}.values(), key=lambda u: (u.submitted_at, str(u.expense_id)))
        for i, cur in enumerate(ordered):
            if candidates is not None and cur.expense_id not in candidates:
                continue
            earlier = [u for u in ordered[:i] if abs(cur.incurred_at - u.incurred_at) <= window]
            if not earlier:
                continue
            out.append(
                SignalFinding(
                    RuleCode.DUPLICATE_RECEIPT,
                    SignalSeverity.WARNING,
                    SubjectType.EXPENSE,
                    cur.expense_id,
                    min(u.incurred_at for u in [*earlier, cur]),
                    cur.incurred_at,
                    f"DR:{cur.expense_id}:{sha}",
                    {
                        "receipt_sha256": sha,
                        "expense_id": str(cur.expense_id),
                        "incurred_at": _iso(cur.incurred_at),
                        "amount": str(cur.amount),
                        "currency": cur.currency,
                        "same_receipt_on": [
                            {
                                "expense_id": str(u.expense_id),
                                "incurred_at": _iso(u.incurred_at),
                                "submitted_at": _iso(u.submitted_at),
                                "amount": str(u.amount),
                                "currency": u.currency,
                            }
                            for u in earlier
                        ],
                        "lookback_days": lookback_days,
                    },
                    policy_version=policy_version,
                    machine_id=cur.machine_id,
                    staff_member_id=cur.custodian_staff_id,
                    involved_user_ids=_ids(u.submitted_by for u in [*earlier, cur]),
                    involved_staff_ids=_ids(u.custodian_staff_id for u in [*earlier, cur]),
                )
            )
    return out


# --- FUEL_ALLOWANCE_EXCEEDED -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class FuelWindow:
    """Fuel recorded on a machine over an approved machine report (its previous reading to its reading)."""

    machine_id: uuid.UUID
    report_id: uuid.UUID
    report_number: str
    opening_reading: Decimal
    closing_reading: Decimal
    opening_at: datetime
    closing_at: datetime
    litres_into_machine: Decimal  # ISSUE (+ PURCHASE straight into the machine)
    litres_used: Decimal  # USAGE log
    fuel_event_ids: tuple[uuid.UUID, ...]
    recorded_by: tuple[uuid.UUID, ...]


def fuel_allowance_exceeded(w: FuelWindow, allowance: Decimal | None, policy_version: str) -> SignalFinding | None:
    """Litres per meter hour above the allowance. Issued and used litres are compared separately (the larger one
    counts) so fuel issued and then logged as used is not double counted. No signal when the rule is off or meter
    hours are unknown/zero."""
    hours = w.closing_reading - w.opening_reading
    if allowance is None or hours <= 0:
        return None
    litres = max(w.litres_into_machine, w.litres_used)
    rate = (litres / hours).quantize(LITRES_PER_HOUR_PLACES)
    if rate <= allowance:
        return None
    return SignalFinding(
        RuleCode.FUEL_ALLOWANCE_EXCEEDED,
        SignalSeverity.WARNING,
        SubjectType.MACHINE,
        w.machine_id,
        w.opening_at,
        w.closing_at,
        f"FUEL:MR:{w.report_id}",
        {
            "machine_report_number": w.report_number,
            "opening_reading": str(w.opening_reading),
            "closing_reading": str(w.closing_reading),
            "meter_hours": str(hours),
            "litres_into_machine": str(w.litres_into_machine),
            "litres_used": str(w.litres_used),
            "litres_compared": str(litres),
            "litres_per_meter_hour": str(rate),
            "allowance_litres_per_meter_hour": str(allowance),
            "fuel_event_ids": [str(i) for i in w.fuel_event_ids],
        },
        policy_version=policy_version,
        machine_id=w.machine_id,
        involved_user_ids=_ids(w.recorded_by),
    )


# --- EXPENSE_THRESHOLD_EXCEEDED --------------------------------------------------------------------------------
@dataclass(frozen=True)
class MachineWeekSpend:
    machine_id: uuid.UUID
    iso_year: int
    iso_week: int
    week_start: datetime
    week_end: datetime
    currency: str
    total: Decimal  # approved + pending, tenant base currency only
    expense_ids: tuple[uuid.UUID, ...]
    submitted_by: tuple[uuid.UUID, ...]


def expense_threshold_exceeded(
    spend: MachineWeekSpend, threshold: Decimal | None, policy_version: str
) -> SignalFinding | None:
    if threshold is None or spend.total <= threshold:
        return None
    week = f"{spend.iso_year}-W{spend.iso_week:02d}"
    return SignalFinding(
        RuleCode.EXPENSE_THRESHOLD_EXCEEDED,
        SignalSeverity.WARNING,
        SubjectType.MACHINE,
        spend.machine_id,
        spend.week_start,
        spend.week_end,
        f"EXPW:{spend.machine_id}:{week}",
        {
            "iso_week": week,
            "currency": spend.currency,
            "approved_and_pending_total": str(spend.total),
            "threshold_per_week": str(threshold),
            "expense_ids": [str(i) for i in spend.expense_ids],
        },
        policy_version=policy_version,
        machine_id=spend.machine_id,
        involved_user_ids=_ids(spend.submitted_by),
    )


# --- CASH_NOT_HANDED_OVER --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CustodyPosition:
    staff_member_id: uuid.UUID
    user_id: uuid.UUID | None
    currency: str
    outstanding: Decimal
    held_since: datetime  # when outstanding custody last went from zero to positive
    as_of: datetime


def cash_not_handed_over(
    pos: CustodyPosition, max_hours: int, max_amount: Decimal | None, policy_version: str
) -> list[SignalFinding]:
    """Outstanding supervisor custody (same computation as cash reconciliation) held longer than `max_hours` or
    above `max_amount`. One finding per exceeded limit, so a later amount breach escalates the open case."""
    if pos.outstanding <= 0:
        return []
    held_hours = (pos.as_of - pos.held_since).total_seconds() / 3600
    reasons = []
    if held_hours > max_hours:
        reasons.append(("HELD_LONGER_THAN_LIMIT", SignalSeverity.WARNING))
    if max_amount is not None and pos.outstanding > max_amount:
        reasons.append(("ABOVE_AMOUNT_LIMIT", SignalSeverity.CRITICAL))
    evidence = {
        "currency": pos.currency,
        "outstanding": str(pos.outstanding),
        "held_since": _iso(pos.held_since),
        "held_hours": round(held_hours, 1),
        "max_hours": max_hours,
        "max_amount": str(max_amount) if max_amount is not None else None,
    }
    return [
        SignalFinding(
            RuleCode.CASH_NOT_HANDED_OVER,
            severity,
            SubjectType.STAFF,
            pos.staff_member_id,
            pos.held_since,
            pos.as_of,
            f"CASH:{pos.staff_member_id}:{pos.currency}:{pos.held_since.isoformat()}:{reason}",
            {**evidence, "limit": reason},
            policy_version=policy_version,
            staff_member_id=pos.staff_member_id,
            involved_user_ids=_ids([pos.user_id]),
            involved_staff_ids=(pos.staff_member_id,),
        )
        for reason, severity in reasons
    ]
