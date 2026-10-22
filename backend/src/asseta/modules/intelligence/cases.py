"""Human review of investigation cases: assign, notes, resolve with an outcome, reopen. Status OPEN -> IN_REVIEW
(on assignment or first note) -> RESOLVED; reopening returns to IN_REVIEW and the next resolution records a new,
immutable outcome. Segregation of duties: a person whose own records produced the evidence can neither be assigned
the case nor resolve it."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.models import AppUser, TenantMembership
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.dto import (
    AnomalyCaseDetailDto,
    AnomalyCaseDto,
    CaseAssignIn,
    CaseNoteDto,
    CaseNoteIn,
    CaseOutcomeDto,
    CaseReopenIn,
    CaseResolveIn,
    CaseSignalDto,
)
from asseta.modules.intelligence.linking import TOPIC
from asseta.modules.intelligence.models import (
    AnomalyCase,
    CaseNote,
    CaseNoteKind,
    CaseOutcome,
    CaseSignal,
    CaseStatus,
    SubjectType,
)

LABEL = "Case"


def _names(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return dict(session.execute(select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(wanted))).tuples().all())


def case_dtos(session: Session, cases: list[AnomalyCase]) -> list[AnomalyCaseDto]:
    ids = [c.id for c in cases]
    counts = dict(
        session.execute(
            select(CaseSignal.case_id, func.count()).where(CaseSignal.case_id.in_(ids)).group_by(CaseSignal.case_id)
        )
        .tuples()
        .all()
    )
    latest = dict(
        session.execute(
            select(CaseOutcome.case_id, CaseOutcome.outcome)
            .where(CaseOutcome.case_id.in_(ids))
            .order_by(CaseOutcome.case_id, CaseOutcome.sequence)
        )
        .tuples()
        .all()
    )
    names = _names(session, {c.assignee_user_id for c in cases})
    return [
        AnomalyCaseDto.model_validate(c).model_copy(
            update={
                "signal_count": counts.get(c.id, 0),
                "latest_outcome": latest.get(c.id) if c.status is CaseStatus.RESOLVED else None,
                "assignee_name": names.get(c.assignee_user_id) if c.assignee_user_id else None,
            }
        )
        for c in cases
    ]


class CaseService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def case(self, case_id: uuid.UUID, lock: bool = False) -> AnomalyCase:
        stmt = select(AnomalyCase).where(AnomalyCase.id == case_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Case not found")
        return row

    def detail(self, case_id: uuid.UUID) -> AnomalyCaseDetailDto:
        case = self.case(case_id)
        signals = self._s.execute(
            select(CaseSignal).where(CaseSignal.case_id == case.id).order_by(CaseSignal.observed_at)
        ).scalars()
        notes = list(
            self._s.execute(select(CaseNote).where(CaseNote.case_id == case.id).order_by(CaseNote.created_at))
            .scalars()
            .all()
        )
        outcomes = list(
            self._s.execute(select(CaseOutcome).where(CaseOutcome.case_id == case.id).order_by(CaseOutcome.sequence))
            .scalars()
            .all()
        )
        names = _names(self._s, {n.author_user_id for n in notes} | {o.decided_by for o in outcomes})
        return AnomalyCaseDetailDto(
            case=case_dtos(self._s, [case])[0],
            signals=[CaseSignalDto.model_validate(x) for x in signals],
            notes=[
                CaseNoteDto.model_validate(n).model_copy(
                    update={"author_name": names.get(n.author_user_id) if n.author_user_id else None}
                )
                for n in notes
            ],
            outcomes=[
                CaseOutcomeDto.model_validate(o).model_copy(update={"decided_by_name": names.get(o.decided_by)})
                for o in outcomes
            ],
        )

    # --- segregation of duties ----------------------------------------------------------------------------------
    def _is_involved(self, case: AnomalyCase, user_id: uuid.UUID) -> bool:
        staff_id = self._s.execute(
            select(StaffMember.id)
            .join(AppUser, AppUser.keycloak_subject == StaffMember.keycloak_subject)
            .where(AppUser.id == user_id)
        ).scalar_one_or_none()
        if (case.subject_type is SubjectType.USER and case.subject_id == user_id) or (
            staff_id is not None and staff_id in (case.staff_member_id, case.subject_id)
        ):
            return True
        for users, staff in self._s.execute(
            select(CaseSignal.involved_user_ids, CaseSignal.involved_staff_ids).where(CaseSignal.case_id == case.id)
        ).tuples():
            if user_id in users or (staff_id is not None and staff_id in staff):
                return True
        return False

    # --- commands -------------------------------------------------------------------------------------------------
    def _changed(self, case: AnomalyCase, action: str, before: dict[str, str | None], reason: str | None) -> None:
        case.updated_at = self._now
        flush_versioned(self._s, LABEL)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"intelligence.case.{action}",
            entity_type="anomaly_case",
            entity_id=case.id,
            tenant_id=self._tid,
            before=before,
            after={
                "status": case.status.value,
                "assignee_user_id": str(case.assignee_user_id) if case.assignee_user_id else None,
            },
            reason=reason,
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CaseUpdated",
            key=str(case.id),
            payload={"case_id": str(case.id), "action": action, "status": case.status.value},
            tenant_id=self._tid,
        )

    def _before(self, case: AnomalyCase) -> dict[str, str | None]:
        return {
            "status": case.status.value,
            "assignee_user_id": str(case.assignee_user_id) if case.assignee_user_id else None,
        }

    def assign(self, case_id: uuid.UUID, body: CaseAssignIn) -> AnomalyCaseDetailDto:
        case = self.case(case_id, lock=True)
        check_version(case.version, body.version, LABEL)
        if case.status is CaseStatus.RESOLVED:
            raise Conflict("Case is resolved; reopen it first", code="CASE_RESOLVED")
        member = self._s.execute(
            select(TenantMembership.id).where(
                TenantMembership.tenant_id == self._tid,
                TenantMembership.user_id == body.assignee_user_id,
                TenantMembership.effective_to.is_(None),
            )
        ).first()
        if member is None:
            raise BusinessRuleViolation("Assignee is not a member of this tenant", code="ASSIGNEE_NOT_MEMBER")
        if self._is_involved(case, body.assignee_user_id):
            raise BusinessRuleViolation(
                "This person's own records are part of the evidence; assign someone else",
                code="SEGREGATION_OF_DUTIES",
            )
        before = self._before(case)
        case.assignee_user_id = body.assignee_user_id
        case.status = CaseStatus.IN_REVIEW
        self._changed(case, "assigned", before, None)
        return self.detail(case.id)

    def add_note(self, case_id: uuid.UUID, body: CaseNoteIn) -> CaseNoteDto:
        case = self.case(case_id, lock=True)
        note = self._note(case, CaseNoteKind.NOTE, body.body)
        if case.status is CaseStatus.OPEN:
            before = self._before(case)
            case.status = CaseStatus.IN_REVIEW
            self._changed(case, "noted", before, None)
        else:
            self._audit.record(
                actor=self._ctx.audit_actor(),
                action="intelligence.case.noted",
                entity_type="anomaly_case",
                entity_id=case.id,
                tenant_id=self._tid,
                after={"note_id": str(note.id)},
            )
        return CaseNoteDto.model_validate(note)

    def _note(self, case: AnomalyCase, kind: CaseNoteKind, text: str) -> CaseNote:
        note = CaseNote(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            case_id=case.id,
            kind=kind,
            body=text,
            author_user_id=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(note)
        self._s.flush()
        return note

    def resolve(self, case_id: uuid.UUID, body: CaseResolveIn) -> AnomalyCaseDetailDto:
        case = self.case(case_id, lock=True)
        check_version(case.version, body.version, LABEL)
        if case.status is CaseStatus.RESOLVED:
            raise Conflict("Case is already resolved", code="CASE_RESOLVED")
        if self._is_involved(case, self._ctx.user_id):
            sod_violation(self._tid, self._ctx.user_id, "resolve", "anomaly_case", case.id)
            raise BusinessRuleViolation(
                "You cannot resolve a case built on your own records", code="SEGREGATION_OF_DUTIES"
            )
        sequence = int(
            self._s.execute(
                select(func.coalesce(func.max(CaseOutcome.sequence), 0)).where(CaseOutcome.case_id == case.id)
            ).scalar_one()
        )
        self._s.add(
            CaseOutcome(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                case_id=case.id,
                sequence=sequence + 1,
                outcome=body.outcome,
                explanation=body.explanation,
                decided_by=self._ctx.user_id,
                decided_at=self._now,
            )
        )
        self._s.flush()  # the case guard requires the outcome to exist before the case becomes RESOLVED
        before = self._before(case)
        case.status, case.resolved_at, case.resolved_by = CaseStatus.RESOLVED, self._now, self._ctx.user_id
        self._changed(case, "resolved", before, f"{body.outcome.value}: {body.explanation}")
        return self.detail(case.id)

    def reopen(self, case_id: uuid.UUID, body: CaseReopenIn) -> AnomalyCaseDetailDto:
        case = self.case(case_id, lock=True)
        check_version(case.version, body.version, LABEL)
        if case.status is not CaseStatus.RESOLVED:
            raise Conflict("Only a resolved case can be reopened", code="CASE_NOT_RESOLVED")
        self._note(case, CaseNoteKind.REOPEN, body.reason)
        before = self._before(case)
        case.status, case.resolved_at, case.resolved_by = CaseStatus.IN_REVIEW, None, None
        self._changed(case, "reopened", before, body.reason)
        return self.detail(case.id)
