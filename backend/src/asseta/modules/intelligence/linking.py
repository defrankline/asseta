"""Attach signals of any source to investigation cases. A signal for a subject that already has an OPEN/IN_REVIEW
case whose last signal is within the policy grouping window joins that case (severity = max); otherwise a new case
is opened. Engine-running-without-work evidence (tracker engine-on without a job, the machine-day summary, after-hours
movement) of one machine and tenant-local day joins ONE case keyed by that machine-day when the machine's
`engine_without_work_case_min_minutes` is set (DEC-031 S1); such a case takes no other signals. Opening and
escalating publish the `AnomalyDetected` notification seam. Idempotent: a source links once."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import Machine
from asseta.modules.intelligence.models import (
    ACTIVE_CASE_STATUSES,
    SEVERITY_RANK,
    AnomalyCase,
    AnomalyCaseCounter,
    CaseSignal,
    CaseSourceType,
    CaseStatus,
    SignalSeverity,
    SubjectType,
)
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import TenantSettings

TOPIC = "asseta.intelligence"
SYSTEM_ACTOR = AuditActor(None, [], "intelligence")
CASE_AUDIENCE = "tenant.case.manage"
# Evidence of a machine running without work, grouped per machine-day when the tenant switches S1 on.
ENGINE_DAY_CODES = frozenset({"UNREPORTED_ENGINE_ACTIVITY", "ENGINE_RUNNING_WITHOUT_WORK", "UNAUTHORIZED_MOVEMENT"})
ENGINE_DAY_PREFIX = "engine-day"


def engine_day_key(machine_id: uuid.UUID, day: date) -> str:
    return f"{ENGINE_DAY_PREFIX}:{machine_id}:{day.isoformat()}"


def engine_day_title(machine: Machine | None, day: date) -> str:
    who = f"{machine.asset_code} " if machine is not None else ""
    return f"Engine running without work: {who}on {day.isoformat()}"


@dataclass(frozen=True)
class CaseItem:
    source_type: CaseSourceType
    source_id: uuid.UUID
    code: str
    title: str  # neutral wording only ("needs review", never a verdict)
    severity: SignalSeverity
    observed_at: datetime
    evidence: dict[str, Any]
    subject_type: SubjectType
    subject_id: uuid.UUID
    policy_version: str
    machine_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID | None = None
    involved_user_ids: tuple[uuid.UUID, ...] = ()
    involved_staff_ids: tuple[uuid.UUID, ...] = ()


@dataclass
class LinkStats:
    linked: int = 0
    opened: list[uuid.UUID] = field(default_factory=list)
    escalated: list[uuid.UUID] = field(default_factory=list)


def case_link(case_id: uuid.UUID) -> str:
    return f"/tenant/cases/{case_id}"


class CaseLinker:
    def __init__(self, session: Session, tenant_id: uuid.UUID, now: datetime, grouping_hours: int):
        self._s, self._tid, self._now = session, tenant_id, now
        self.tenant_id = tenant_id
        self._window = timedelta(hours=grouping_hours)
        self._audit = AuditService(session)
        self.stats = LinkStats()
        self._tz: ZoneInfo | None = None

    def already_linked(self, source_type: CaseSourceType, source_id: uuid.UUID) -> bool:
        return (
            self._s.execute(
                select(CaseSignal.id).where(CaseSignal.source_type == source_type, CaseSignal.source_id == source_id)
            ).first()
            is not None
        )

    def link(self, item: CaseItem) -> AnomalyCase | None:
        """Returns the case the item joined (None when it was already linked)."""
        lock = f"case:{self._tid}:{item.subject_type.value}:{item.subject_id}"
        self._s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": lock})
        if self.already_linked(item.source_type, item.source_id):
            return None
        group = self._group(item)
        if group is not None:
            match = AnomalyCase.group_key == group[0]
        else:
            match = and_(
                AnomalyCase.subject_type == item.subject_type,
                AnomalyCase.subject_id == item.subject_id,
                AnomalyCase.group_key.is_(None),
                AnomalyCase.last_signal_at >= item.observed_at - self._window,
            )
        case = self._s.execute(
            select(AnomalyCase)
            .where(match, AnomalyCase.status.in_(ACTIVE_CASE_STATUSES))
            .order_by(AnomalyCase.last_signal_at.desc())
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if case is None:
            case = self._open(item, group)
        else:
            self._join(case, item)
        self._s.add(
            CaseSignal(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                case_id=case.id,
                source_type=item.source_type,
                source_id=item.source_id,
                code=item.code,
                severity=item.severity,
                observed_at=item.observed_at,
                evidence=item.evidence,
                involved_user_ids=list(item.involved_user_ids),
                involved_staff_ids=list(item.involved_staff_ids),
                linked_at=self._now,
            )
        )
        self._s.flush()
        self.stats.linked += 1
        return case

    def _group(self, item: CaseItem) -> tuple[str, str] | None:
        """(group key, case title) for engine-running-without-work evidence when the machine's S1 switch is on."""
        if item.code not in ENGINE_DAY_CODES or item.machine_id is None:
            return None
        eff = PolicyService(self._s).fraud_controls(self._tid, item.machine_id, at=self._now)
        if eff.policy.engine_without_work_case_min_minutes is None:
            return None
        if self._tz is None:
            ts = self._s.get(TenantSettings, self._tid)
            self._tz = ZoneInfo(ts.timezone if ts else "UTC")
        day = item.observed_at.astimezone(self._tz).date()
        return engine_day_key(item.machine_id, day), engine_day_title(self._s.get(Machine, item.machine_id), day)

    def _number(self) -> str:
        year = self._now.year
        n = self._s.execute(
            pg_insert(AnomalyCaseCounter)
            .values(tenant_id=self._tid, year=year, last_number=1)
            .on_conflict_do_update(
                index_elements=["tenant_id", "year"], set_={"last_number": AnomalyCaseCounter.last_number + 1}
            )
            .returning(AnomalyCaseCounter.last_number)
        ).scalar_one()
        return f"CASE-{year}-{n:05d}"

    def _open(self, item: CaseItem, group: tuple[str, str] | None = None) -> AnomalyCase:
        case = AnomalyCase(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            case_number=self._number(),
            title=group[1] if group else item.title,
            group_key=group[0] if group else None,
            subject_type=item.subject_type,
            subject_id=item.subject_id,
            machine_id=item.machine_id,
            job_id=item.job_id,
            staff_member_id=item.staff_member_id,
            severity=item.severity,
            status=CaseStatus.OPEN,
            opened_at=self._now,
            last_signal_at=item.observed_at,
            policy_version=item.policy_version,
            created_at=self._now,
            updated_at=self._now,
        )
        self._s.add(case)
        self._s.flush()
        self._audit.record(
            actor=SYSTEM_ACTOR,
            action="intelligence.case.opened",
            entity_type="anomaly_case",
            entity_id=case.id,
            tenant_id=self._tid,
            after={"case_number": case.case_number, "severity": case.severity.value, "source": item.code},
            policy_version=item.policy_version[:64],
        )
        self._announce(case, "CASE_OPENED", f"{case.case_number} opened: {case.title}. Needs review.")
        self.stats.opened.append(case.id)
        return case

    def _join(self, case: AnomalyCase, item: CaseItem) -> None:
        before = case.severity
        case.last_signal_at = max(case.last_signal_at, item.observed_at)
        case.updated_at = self._now
        escalated = SEVERITY_RANK[item.severity] > SEVERITY_RANK[before]
        if escalated:
            case.severity = item.severity
        self._s.flush()
        self._audit.record(
            actor=SYSTEM_ACTOR,
            action="intelligence.case.signal_linked",
            entity_type="anomaly_case",
            entity_id=case.id,
            tenant_id=self._tid,
            before={"severity": before.value},
            after={"severity": case.severity.value, "source": item.code, "source_id": str(item.source_id)},
        )
        if escalated:
            self._announce(
                case, "CASE_ESCALATED", f"{case.case_number}: severity raised to {case.severity.value} by {item.title}."
            )
            self.stats.escalated.append(case.id)

    def _announce(self, case: AnomalyCase, kind: str, body: str) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="AnomalyDetected",
            key=str(case.subject_id),
            payload={
                "kind": kind,
                "severity": case.severity.value,
                "title": f"Needs review: {case.title}",
                "body": body,
                "entity_type": "case",
                "entity_id": str(case.id),
                "link": case_link(case.id),
                "audience_permission": CASE_AUDIENCE,
            },
            tenant_id=self._tid,
        )


def signal_count(session: Session, case_id: uuid.UUID) -> int:
    return int(session.execute(select(func.count()).where(CaseSignal.case_id == case_id)).scalar_one())
