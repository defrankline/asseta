"""Go-live setup checklist endpoints (`/api/v1/tenant/setup-checklist`): read the live checklist, mark a step as not
needed (and undo), confirm the default controls, dismiss the banner (and show it again). Reading needs
`tenant.setup.read`; the owner's choices need `tenant.setup.manage`. Every choice is appended and audited."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation
from asseta.modules.accountability.names import named
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.onboarding.checklist import SETUP_READ_PERMISSION, STEP_BY_KEY, ChecklistResult, StepKey, compute
from asseta.modules.onboarding.dto import (
    ConfirmControlsIn,
    NotNeededDto,
    NotNeededIn,
    SetupCheckDto,
    SetupChecklistDto,
    SetupStepDto,
)
from asseta.modules.onboarding.models import SetupChoiceAction, TenantSetupChoice

SETUP_MANAGE_PERMISSION = "tenant.setup.manage"
SETUP_READ = requires(SETUP_READ_PERMISSION, S.TENANT, "See the go-live setup checklist and its progress")
SETUP_MANAGE = requires(
    SETUP_MANAGE_PERMISSION, S.TENANT, "Mark setup steps as not needed, confirm default controls, dismiss the checklist"
)
CATALOG.register_menu(
    MenuDef(
        "tenant.setup",
        S.TENANT,
        "Go-live checklist",
        "/tenant/setup",
        6,
        SETUP_READ_PERMISSION,
        group="tenant.overview",
    )
)

router = APIRouter(prefix="/api/v1/tenant/setup-checklist", tags=["setup-checklist"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]


def to_dto(result: ChecklistResult, now: datetime) -> SetupChecklistDto:
    steps = []
    for r in result.steps:
        ev, step = r.evaluation, r.step
        steps.append(
            SetupStepDto(
                key=step.key,
                order=r.order,
                title=step.title,
                description=step.description,
                status=r.status,
                done_count=ev.done_count,
                total_count=ev.total_count,
                link=ev.link or step.link,
                required_permission=step.required_permission,
                can_mark_not_needed=step.can_mark_not_needed,
                not_needed=NotNeededDto(
                    reason=r.not_needed.reason, marked_by=r.not_needed.marked_by, marked_at=r.not_needed.marked_at
                )
                if r.not_needed
                else None,
                checks=[
                    SetupCheckDto(
                        key=c.key,
                        label=c.label,
                        done=c.done,
                        optional=c.optional,
                        done_count=c.done_count,
                        total_count=c.total_count,
                        link=c.link,
                        required_permission=c.required_permission,
                    )
                    for c in ev.checks
                ],
            )
        )
    ch = result.choices
    return SetupChecklistDto(
        steps=steps,
        steps_done=result.steps_done,
        steps_total=result.steps_total,
        percent=result.percent,
        complete=result.complete,
        dismissed=ch.dismissed,
        dismissed_by=ch.dismissed_by,
        dismissed_at=ch.dismissed_at,
        controls_confirmed_by=ch.controls_confirmed_by,
        controls_confirmed_at=ch.controls_confirmed_at,
        as_of=now,
    )


class SetupChoiceService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def checklist(self) -> SetupChecklistDto:
        return to_dto(compute(self._s, self._tid, self._now), self._now)

    def _append(self, action: SetupChoiceAction, step_key: str | None, reason: str | None, **after: Any) -> None:
        row = TenantSetupChoice(
            tenant_id=self._tid,
            action=action,
            step_key=step_key,
            reason=reason,
            recorded_by=self._ctx.user_id,
            recorded_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action=f"tenant.setup.{action.value.lower()}",
            entity_type="tenant_setup_choice",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"action": action.value, "step_key": step_key, **after},
            reason=reason,
        )

    def mark_not_needed(self, key: StepKey, reason: str) -> SetupChecklistDto:
        step = STEP_BY_KEY[key]
        if not step.can_mark_not_needed:
            raise BusinessRuleViolation(
                f"The step '{step.title}' cannot be marked as not needed", code="SETUP_STEP_REQUIRED"
            )
        current = compute(self._s, self._tid, self._now)
        if key not in current.choices.not_needed:
            self._append(SetupChoiceAction.STEP_NOT_NEEDED, key.value, reason)
        return self.checklist()

    def undo_not_needed(self, key: StepKey) -> SetupChecklistDto:
        current = compute(self._s, self._tid, self._now)
        if key in current.choices.not_needed:
            self._append(SetupChoiceAction.STEP_NEEDED, key.value, None)
        return self.checklist()

    def confirm_controls(self, note: str | None) -> SetupChecklistDto:
        self._append(SetupChoiceAction.CONTROLS_CONFIRMED, None, note)
        return self.checklist()

    def set_dismissed(self, dismissed: bool) -> SetupChecklistDto:
        current = compute(self._s, self._tid, self._now)
        if current.choices.dismissed != dismissed:
            action = SetupChoiceAction.DISMISSED if dismissed else SetupChoiceAction.UNDISMISSED
            self._append(action, None, None)
        return self.checklist()


@router.get("", response_model=SetupChecklistDto, operation_id="getSetupChecklist")
@named
def get_setup_checklist(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SETUP_READ)]
) -> SetupChecklistDto:
    """The ordered go-live steps, each computed live from the tenant's data: DONE, TODO, NOT_NEEDED (the owner marked
    it) or NOT_APPLICABLE (the capability it configures is switched off). `steps_done` of `steps_total` (NOT_NEEDED
    counts as done; NOT_APPLICABLE steps are left out) and `percent` give the progress; each step links to the exact
    screen that completes it."""
    return SetupChoiceService(session, ctx, now).checklist()


@router.post("/steps/{key}/not-needed", response_model=SetupChecklistDto, operation_id="markSetupStepNotNeeded")
@named
def mark_step_not_needed(
    key: StepKey, body: NotNeededIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SETUP_MANAGE)]
) -> SetupChecklistDto:
    """Mark a step as not needed for the business (with a reason). Refused with 422 SETUP_STEP_REQUIRED for steps
    every tenant needs. A step whose data is complete stays DONE."""
    return SetupChoiceService(session, ctx, now).mark_not_needed(key, body.reason)


@router.delete("/steps/{key}/not-needed", response_model=SetupChecklistDto, operation_id="undoSetupStepNotNeeded")
@named
def undo_step_not_needed(
    key: StepKey, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SETUP_MANAGE)]
) -> SetupChecklistDto:
    """Undo a "not needed" mark (the step counts again)."""
    return SetupChoiceService(session, ctx, now).undo_not_needed(key)


@router.post("/confirm-controls", response_model=SetupChecklistDto, operation_id="confirmSetupControls")
@named
def confirm_controls(
    body: ConfirmControlsIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SETUP_MANAGE)],
) -> SetupChecklistDto:
    """The owner confirms that the platform default controls are fine (completes CONTROLS_CHOSEN without changing a
    policy)."""
    return SetupChoiceService(session, ctx, now).confirm_controls(body.note)


@router.post("/dismiss", response_model=SetupChecklistDto, operation_id="dismissSetupChecklist")
@named
def dismiss_checklist(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SETUP_MANAGE)]
) -> SetupChecklistDto:
    """Hide the go-live banner for everyone in the tenant (the checklist page stays available)."""
    return SetupChoiceService(session, ctx, now).set_dismissed(True)


@router.delete("/dismiss", response_model=SetupChecklistDto, operation_id="undismissSetupChecklist")
@named
def undismiss_checklist(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SETUP_MANAGE)]
) -> SetupChecklistDto:
    """Show the go-live banner again."""
    return SetupChoiceService(session, ctx, now).set_dismissed(False)
