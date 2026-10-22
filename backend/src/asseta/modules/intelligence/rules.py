"""Pure risk-signal rules (ADR-007). Each rule takes plain facts plus policy thresholds and returns `SignalFinding`s
whose evidence holds facts and thresholds only — never a conclusion about a person. Deterministic and identical for
the periodic sweep and event-driven runs; the dedupe key makes every run idempotent."""

import itertools
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
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
    job_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID | None = None
    involved_user_ids: tuple[uuid.UUID, ...] = ()
    involved_staff_ids: tuple[uuid.UUID, ...] = ()


def _iso(at: datetime | None) -> str | None:
    return at.isoformat() if at is not None else None


def _ids(values: Iterable[uuid.UUID | None]) -> tuple[uuid.UUID, ...]:
    return tuple(sorted({v for v in values if v is not None}, key=str))


# --- UNREPORTED_ENGINE_ACTIVITY --------------------------------------------------------------------------------
@dataclass(frozen=True)
class EngineState:
    at: datetime
    on: bool


@dataclass(frozen=True)
class EngineHoursSample:
    at: datetime
    engine_hours: Decimal


@dataclass(frozen=True)
class EngineRun:
    start: datetime
    end: datetime
    ongoing: bool  # still running when observed (end = observation time)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobWindow:
    """When a job was IN_PROGRESS: [started_at, completed_at), open-ended while still running."""

    job_id: uuid.UUID
    job_number: str
    start: datetime
    end: datetime | None


def runs_from_states(states: Sequence[EngineState], now: datetime) -> list[EngineRun]:
    """Engine-on runs from event-time ordered ENGINE ON/OFF states (include the last state before the window so a
    run's start is its real ON transition and stays stable across sweeps)."""
    runs, start = [], None
    for s in sorted(states, key=lambda x: x.at):
        if s.on and start is None:
            start = s.at
        elif not s.on and start is not None:
            runs.append(EngineRun(start, s.at, False, {"basis": "IGNITION"}))
            start = None
    if start is not None:
        runs.append(EngineRun(start, now, True, {"basis": "IGNITION"}))
    return runs


def runs_from_engine_hours(samples: Sequence[EngineHoursSample], window_start: datetime) -> list[EngineRun]:
    """Runs where consecutive engine-hour readings increase. A run that already began before the window is skipped:
    an earlier sweep evaluated it (keeps its dedupe key stable)."""
    ordered = sorted(samples, key=lambda x: x.at)
    runs: list[EngineRun] = []
    first: EngineHoursSample | None = None
    last: EngineHoursSample | None = None
    for a, b in itertools.pairwise(ordered):
        if b.engine_hours > a.engine_hours:
            if first is None:
                first = a
            last = b
            continue
        if first is not None and last is not None:
            runs.append(_hours_run(first, last))
        first = last = None
    if first is not None and last is not None:
        runs.append(_hours_run(first, last))
    return [r for r in runs if r.start >= window_start]


def _hours_run(first: EngineHoursSample, last: EngineHoursSample) -> EngineRun:
    detail = {
        "basis": "ENGINE_HOURS",
        "engine_hours_start": str(first.engine_hours),
        "engine_hours_end": str(last.engine_hours),
    }
    return EngineRun(first.at, last.at, False, detail)


def uncovered(start: datetime, end: datetime, jobs: Sequence[JobWindow]) -> list[tuple[datetime, datetime]]:
    """Parts of [start, end) not covered by any running job."""
    segments, cursor = [], start
    for j in sorted(jobs, key=lambda x: x.start):
        job_end = j.end or end
        if job_end <= cursor or j.start >= end:
            continue
        if j.start > cursor:
            segments.append((cursor, j.start))
        cursor = max(cursor, job_end)
        if cursor >= end:
            break
    if cursor < end:
        segments.append((cursor, end))
    return segments


def unreported_engine_activity(
    machine_id: uuid.UUID,
    runs: Sequence[EngineRun],
    jobs: Sequence[JobWindow],
    verified_since: datetime,
    min_minutes: int,
    policy_version: str,
    supervisors: Sequence[uuid.UUID] = (),
) -> list[SignalFinding]:
    """Verified engine activity (ignition on / engine hours rising) of at least `min_minutes` while no job on the
    machine was IN_PROGRESS. Only time after the capability was first verified counts."""
    out = []
    for run in runs:
        start = max(run.start, verified_since)
        if start >= run.end:
            continue
        for seg_start, seg_end in uncovered(start, run.end, jobs):
            minutes = (seg_end - seg_start).total_seconds() / 60
            if minutes < min_minutes:
                continue
            out.append(
                SignalFinding(
                    RuleCode.UNREPORTED_ENGINE_ACTIVITY,
                    SignalSeverity.WARNING,
                    SubjectType.MACHINE,
                    machine_id,
                    seg_start,
                    seg_end,
                    f"UEA:{machine_id}:{seg_start.isoformat()}",
                    {
                        **run.detail,
                        "engine_on_from": _iso(run.start),
                        "engine_on_until": _iso(run.end),
                        "still_running_when_observed": run.ongoing,
                        "uncovered_from": _iso(seg_start),
                        "uncovered_until": _iso(seg_end),
                        "uncovered_minutes": round(minutes, 1),
                        "capability_verified_since": _iso(verified_since),
                        "running_jobs_nearby": [
                            {
                                "job_id": str(j.job_id),
                                "job_number": j.job_number,
                                "from": _iso(j.start),
                                "to": _iso(j.end),
                            }
                            for j in jobs
                        ],
                        "threshold_minutes": min_minutes,
                    },
                    policy_version=policy_version,
                    machine_id=machine_id,
                    involved_staff_ids=_ids(supervisors),
                )
            )
    return out


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
    job_id: uuid.UUID | None
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
                    job_id=cur.job_id,
                    staff_member_id=cur.custodian_staff_id,
                    involved_user_ids=_ids(u.submitted_by for u in [*earlier, cur]),
                    involved_staff_ids=_ids(u.custodian_staff_id for u in [*earlier, cur]),
                )
            )
    return out


# --- FUEL_ALLOWANCE_EXCEEDED -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class FuelWindow:
    """Fuel recorded on a machine between a job's opening and closing meter readings."""

    machine_id: uuid.UUID
    job_id: uuid.UUID
    job_number: str
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
        f"FUEL:{w.job_id}",
        {
            "job_number": w.job_number,
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
        job_id=w.job_id,
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


# --- WORK_WITHOUT_AUTHORIZATION --------------------------------------------------------------------------------
@dataclass(frozen=True)
class WorkRecord:
    kind: str  # JOB_ACTIVITY | METER_CAPTURE | EXPENSE
    record_id: uuid.UUID
    job_id: uuid.UUID
    job_number: str
    machine_id: uuid.UUID
    occurred_at: datetime  # when the work/reading/spend happened (device time)
    received_at: datetime
    job_status: str
    approved_at: datetime | None
    completed_at: datetime | None
    recorded_by: uuid.UUID | None
    recorder_staff_id: uuid.UUID | None  # set when the recorder is a supervisor staff member
    recorder_assigned: bool | None  # supervisor assignment to the machine at `occurred_at` (None: not a supervisor)


def work_without_authorization(rec: WorkRecord, tolerance_minutes: int, policy_version: str) -> SignalFinding | None:
    """Work, readings or spend attributed to a job outside its authorized period [approved_at, completed_at] (plus
    clock tolerance), or recorded by a supervisor who was not assigned to the machine at the time. The online API
    refuses activity/readings on jobs that are not approved/running *at receipt*, so this catches what still
    happens: offline records synced later with an earlier device time, activity logged on a completed job after
    completion, expenses attributed to any job (no status check), and records by unassigned supervisors."""
    tol = timedelta(minutes=tolerance_minutes)
    reasons = []
    if rec.approved_at is None or rec.occurred_at < rec.approved_at - tol:
        reasons.append("BEFORE_JOB_AUTHORIZED")
    elif rec.completed_at is not None and rec.occurred_at > rec.completed_at + tol:
        reasons.append("AFTER_JOB_COMPLETED")
    if rec.recorder_assigned is False:
        reasons.append("SUPERVISOR_NOT_ASSIGNED_TO_MACHINE")
    if not reasons:
        return None
    return SignalFinding(
        RuleCode.WORK_WITHOUT_AUTHORIZATION,
        SignalSeverity.WARNING,
        SubjectType.JOB,
        rec.job_id,
        rec.occurred_at,
        rec.received_at,
        f"WWA:{rec.kind}:{rec.record_id}",
        {
            "record_type": rec.kind,
            "record_id": str(rec.record_id),
            "job_number": rec.job_number,
            "occurred_at": _iso(rec.occurred_at),
            "received_at": _iso(rec.received_at),
            "job_status_now": rec.job_status,
            "job_approved_at": _iso(rec.approved_at),
            "job_completed_at": _iso(rec.completed_at),
            "tolerance_minutes": tolerance_minutes,
            "recorder_supervisor_assigned": rec.recorder_assigned,
            "reasons": reasons,
        },
        policy_version=policy_version,
        machine_id=rec.machine_id,
        job_id=rec.job_id,
        staff_member_id=rec.recorder_staff_id,
        involved_user_ids=_ids([rec.recorded_by]),
        involved_staff_ids=_ids([rec.recorder_staff_id]),
    )
