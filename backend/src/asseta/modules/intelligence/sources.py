"""Signal sources feeding cases: stored `risk_signal` findings plus the existing deterministic layer — confirmed or
blocking-critical meter exceptions, tamper / unauthorized-movement / restricted-area tracking alerts, and refused
segregation-of-duties attempts (outbox `SegregationOfDutiesViolation`). All titles are neutral."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.outbox import OutboxEvent
from asseta.modules.fleet.models import AssignmentRole, MachineAssignment, StaffMember
from asseta.modules.geospatial.models import AlertStatus, AlertType, TrackingAlert
from asseta.modules.identity.models import AppUser
from asseta.modules.intelligence.linking import CaseItem, CaseLinker
from asseta.modules.intelligence.models import (
    CaseSourceType,
    RiskSignal,
    RuleCode,
    SignalSeverity,
    SignalStatus,
    SubjectType,
)
from asseta.modules.intelligence.rules import RULE_VERSIONS, SignalFinding
from asseta.modules.meter.models import ExceptionStatus, JobException, MeterCapture

RULE_TITLES: dict[str, str] = {
    RuleCode.UNREPORTED_ENGINE_ACTIVITY: "Engine activity without an active job",
    RuleCode.DUPLICATE_RECEIPT: "Same receipt image on more than one expense",
    RuleCode.FUEL_ALLOWANCE_EXCEEDED: "Fuel above the allowance for the meter hours",
    RuleCode.EXPENSE_THRESHOLD_EXCEEDED: "Weekly machine spending above the threshold",
    RuleCode.CASH_NOT_HANDED_OVER: "Cash held beyond the handover limits",
    RuleCode.WORK_WITHOUT_AUTHORIZATION: "Work recorded outside an authorized job",
    RuleCode.UNEXPLAINED_ENGINE_HOURS: "Engine hours still unexplained after the review period",
    RuleCode.ENGINE_RUNNING_WITHOUT_WORK: "Engine running without work during the day",
    RuleCode.MACHINE_FUEL_ABOVE_NORM: "Fuel above the norm for the engine hours",
    RuleCode.REPEATED_PATTERN: "Repeated items to look at for one person",
}
ALERT_TITLES = {
    AlertType.TAMPER: "Tracker tamper signal",
    AlertType.UNAUTHORIZED_MOVEMENT: "Movement outside the approved operating window",
    AlertType.RESTRICTED_AREA_ENTRY: "Entry into a restricted area",
}
METER_TITLE = "Meter reading exception needs review"
SOD_TITLE = "Attempt to approve or verify own record"
SOD_EVENT = "SegregationOfDutiesViolation"
SOD_CODE = "SEGREGATION_OF_DUTIES_ATTEMPT"


def _severity(value: str) -> SignalSeverity:
    return SignalSeverity(value) if value in SignalSeverity.__members__ else SignalSeverity.WARNING


# --- risk signals ----------------------------------------------------------------------------------------------
def store_findings(s: Session, tenant_id: uuid.UUID, now: datetime, findings: Sequence[SignalFinding]) -> int:
    """Insert new findings; an existing dedupe key is left untouched (re-runs are no-ops). Returns rows added."""
    added = 0
    for f in findings:
        row_id = s.execute(
            pg_insert(RiskSignal)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                rule_code=f.rule_code,
                rule_version=RULE_VERSIONS[f.rule_code],
                severity=f.severity,
                subject_type=f.subject_type,
                subject_id=f.subject_id,
                machine_id=f.machine_id,
                job_id=f.job_id,
                staff_member_id=f.staff_member_id,
                window_start=f.window_start,
                window_end=f.window_end,
                evidence=f.evidence,
                policy_version=f.policy_version,
                dedupe_key=f.dedupe_key,
                involved_user_ids=list(f.involved_user_ids),
                involved_staff_ids=list(f.involved_staff_ids),
                status=SignalStatus.OPEN,
                created_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_risk_signal_dedupe")
            .returning(RiskSignal.id)
        ).scalar_one_or_none()
        added += row_id is not None
    return added


def link_open_signals(s: Session, linker: CaseLinker) -> None:
    for sig in s.execute(
        select(RiskSignal).where(RiskSignal.status == SignalStatus.OPEN).order_by(RiskSignal.created_at)
    ).scalars():
        linker.link(
            CaseItem(
                CaseSourceType.RISK_SIGNAL,
                sig.id,
                sig.rule_code.value,
                RULE_TITLES[sig.rule_code],
                sig.severity,
                sig.window_start,
                {"rule_version": sig.rule_version, "window_end": sig.window_end.isoformat(), **sig.evidence},
                sig.subject_type,
                sig.subject_id,
                sig.policy_version,
                sig.machine_id,
                sig.job_id,
                sig.staff_member_id,
                tuple(sig.involved_user_ids),
                tuple(sig.involved_staff_ids),
            )
        )
        sig.status = SignalStatus.LINKED
    s.flush()


# --- existing deterministic sources ----------------------------------------------------------------------------
def _staff_for_users(s: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not user_ids:
        return {}
    rows = s.execute(
        select(AppUser.id, StaffMember.id)
        .join(StaffMember, StaffMember.keycloak_subject == AppUser.keycloak_subject)
        .where(AppUser.id.in_(user_ids))
    ).all()
    return dict(rows)


def _supervisors_at(s: Session, machine_id: uuid.UUID, at: datetime) -> tuple[uuid.UUID, ...]:
    return tuple(
        s.execute(
            select(MachineAssignment.staff_member_id).where(
                MachineAssignment.machine_id == machine_id,
                MachineAssignment.role == AssignmentRole.SUPERVISOR,
                MachineAssignment.effective_from <= at,
                or_(MachineAssignment.effective_to.is_(None), MachineAssignment.effective_to > at),
            )
        ).scalars()
    )


def meter_exception_item(s: Session, e: JobException, policy_version: str) -> CaseItem | None:
    """Confirmed by a reviewer, or blocking + CRITICAL and not yet explained."""
    if not (
        e.status is ExceptionStatus.CONFIRMED
        or (e.status is ExceptionStatus.OPEN and e.blocking and e.severity == SignalSeverity.CRITICAL.value)
    ):
        return None
    supervisor = (
        s.execute(select(MeterCapture.supervisor_user_id).where(MeterCapture.id == e.meter_capture_id)).scalar()
        if e.meter_capture_id
        else None
    )
    users = {supervisor} if supervisor else set()
    evidence: dict[str, Any] = {
        "exception_type": e.exception_type.value,
        "exception_status": e.status.value,
        "blocking": e.blocking,
        "meter_capture_id": str(e.meter_capture_id) if e.meter_capture_id else None,
        "review_note": e.review_note,
        **e.evidence,
    }
    return CaseItem(
        CaseSourceType.METER_EXCEPTION,
        e.id,
        e.exception_type.value,
        METER_TITLE,
        _severity(e.severity),
        e.created_at,
        evidence,
        SubjectType.MACHINE,
        e.machine_id,
        e.policy_version or policy_version,
        e.machine_id,
        e.job_id,
        None,
        tuple(users),
        tuple(_staff_for_users(s, users).values()),
    )


def tracking_alert_item(s: Session, a: TrackingAlert, policy_version: str) -> CaseItem | None:
    if a.alert_type not in ALERT_TITLES or a.status is AlertStatus.SUPERSEDED or a.machine_id is None:
        return None
    return CaseItem(
        CaseSourceType.TRACKING_ALERT,
        a.id,
        a.alert_type.value,
        ALERT_TITLES[a.alert_type],
        _severity(a.severity.value),
        a.event_time,
        {"alert_type": a.alert_type.value, "alert_title": a.title, "alert_status": a.status.value, **a.evidence},
        SubjectType.MACHINE,
        a.machine_id,
        a.policy_version or policy_version,
        a.machine_id,
        involved_staff_ids=_supervisors_at(s, a.machine_id, a.event_time),
    )


def sod_item(s: Session, event_id: uuid.UUID, at: datetime, payload: dict[str, Any], pv: str) -> CaseItem | None:
    try:
        actor = uuid.UUID(str(payload.get("actor_user_id")))
    except ValueError:
        return None  # no attributable person: nothing to review
    staff = _staff_for_users(s, {actor}).get(actor)
    return CaseItem(
        CaseSourceType.SOD_EVENT,
        event_id,
        SOD_CODE,
        SOD_TITLE,
        SignalSeverity.WARNING,
        at,
        {
            "action": payload.get("action"),
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "outcome": "REFUSED",
        },
        SubjectType.STAFF if staff else SubjectType.USER,
        staff or actor,
        pv,
        staff_member_id=staff,
        involved_user_ids=(actor,),
        involved_staff_ids=(staff,) if staff else (),
    )


def link_sources(s: Session, linker: CaseLinker, since: datetime, policy_version: str) -> None:
    """Sweep the existing deterministic layer (bounded by `since`); already linked sources are skipped. The outbox
    has no row-level security, so SoD events are filtered by tenant explicitly."""
    for e in s.execute(
        select(JobException).where(or_(JobException.created_at >= since, JobException.reviewed_at >= since))
    ).scalars():
        if not linker.already_linked(CaseSourceType.METER_EXCEPTION, e.id) and (
            item := meter_exception_item(s, e, policy_version)
        ):
            linker.link(item)
    for a in s.execute(
        select(TrackingAlert).where(TrackingAlert.created_at >= since, TrackingAlert.alert_type.in_(ALERT_TITLES))
    ).scalars():
        if not linker.already_linked(CaseSourceType.TRACKING_ALERT, a.id) and (
            item := tracking_alert_item(s, a, policy_version)
        ):
            linker.link(item)
    for ev in s.execute(
        select(OutboxEvent).where(
            OutboxEvent.tenant_id == linker.tenant_id,
            OutboxEvent.event_type == SOD_EVENT,
            OutboxEvent.created_at >= since,
        )
    ).scalars():
        if not linker.already_linked(CaseSourceType.SOD_EVENT, ev.id) and (
            item := sod_item(s, ev.id, ev.created_at, ev.payload, policy_version)
        ):
            linker.link(item)
