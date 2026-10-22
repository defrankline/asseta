"""Model lifecycle decisions and the platform inference hard switch (ADR-007 "Model lifecycle", prompt.md §7).

Rules (also enforced in the database by `guard_model_version`):
* at most one deployed version (shadow or active) per (tenant, model name) — deploying another retires it;
* DEPLOY_SHADOW needs an evaluation (passing is not required: shadow is how a model gets observed);
* DEPLOY_ACTIVE needs a *passing* evaluation and a prior APPROVE recorded by a platform admin;
* ROLLBACK retires the current deployed version and redeploys the previously deployed one in the mode it had;
* DISABLE is immediate and final for that version; REJECT closes an undeployed candidate;
* the platform switch `inference_enabled = false` means no inference runs anywhere (consumed by Gate 6D).
Every action needs a reason, is appended to `model_approval`, audited and (deploy/disable/switch) published.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned
from asseta.core.outbox import OutboxWriter
from asseta.modules.intelligence.linking import TOPIC
from asseta.modules.intelligence.ml_models import (
    DEPLOYED_STATUSES,
    MODEL_TRANSITIONS,
    MlSetting,
    ModelAction,
    ModelApproval,
    ModelEvaluation,
    ModelStatus,
    ModelVersion,
)

LABEL = "Model version"
DEFAULT_INFERENCE_ENABLED = True
DEFAULT_SETTING_REASON = "Platform default: inference may run for deployed models only."

_ACTION_TARGET: dict[ModelAction, ModelStatus] = {
    ModelAction.APPROVE: ModelStatus.APPROVED,
    ModelAction.REJECT: ModelStatus.REJECTED,
    ModelAction.DEPLOY_SHADOW: ModelStatus.DEPLOYED_SHADOW,
    ModelAction.DEPLOY_ACTIVE: ModelStatus.DEPLOYED_ACTIVE,
    ModelAction.DISABLE: ModelStatus.DISABLED,
    ModelAction.RETIRE: ModelStatus.RETIRED,
}
_ACTION_FROM: dict[ModelAction, frozenset[ModelStatus]] = {
    ModelAction.APPROVE: frozenset({ModelStatus.EVALUATED, ModelStatus.DEPLOYED_SHADOW}),
    ModelAction.REJECT: frozenset({ModelStatus.TRAINED, ModelStatus.EVALUATED, ModelStatus.APPROVED}),
    ModelAction.DEPLOY_SHADOW: frozenset({ModelStatus.EVALUATED, ModelStatus.APPROVED}),
    ModelAction.DEPLOY_ACTIVE: frozenset({ModelStatus.EVALUATED, ModelStatus.APPROVED, ModelStatus.DEPLOYED_SHADOW}),
    ModelAction.DISABLE: frozenset(
        {
            ModelStatus.TRAINED,
            ModelStatus.EVALUATED,
            ModelStatus.APPROVED,
            ModelStatus.DEPLOYED_SHADOW,
            ModelStatus.DEPLOYED_ACTIVE,
            ModelStatus.RETIRED,
        }
    ),
    ModelAction.RETIRE: frozenset(
        {ModelStatus.EVALUATED, ModelStatus.APPROVED, ModelStatus.DEPLOYED_SHADOW, ModelStatus.DEPLOYED_ACTIVE}
    ),
}


@dataclass(frozen=True)
class MlSettingView:
    inference_enabled: bool
    reason: str
    updated_by: uuid.UUID | None
    updated_at: datetime | None
    lock_version: int


def current_ml_setting(session: Session) -> MlSettingView:
    row = session.get(MlSetting, 1)
    if row is None:
        return MlSettingView(DEFAULT_INFERENCE_ENABLED, DEFAULT_SETTING_REASON, None, None, 0)
    return MlSettingView(row.inference_enabled, row.reason, row.updated_by, row.updated_at, row.lock_version)


def inference_enabled(session: Session) -> bool:
    """The hard switch every inference path (Gate 6D) must check first."""
    return current_ml_setting(session).inference_enabled


class MlGovernanceService:
    def __init__(self, session: Session, actor: AuditActor, now: datetime):
        self._s, self._actor, self._now = session, actor, now
        self._audit = AuditService(session)

    def model(self, model_id: uuid.UUID, lock: bool = False) -> ModelVersion:
        stmt = select(ModelVersion).where(ModelVersion.id == model_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Model version not found")
        return row

    def evaluation(self, model_id: uuid.UUID) -> ModelEvaluation | None:
        return self._s.execute(
            select(ModelEvaluation).where(ModelEvaluation.model_version_id == model_id)
        ).scalar_one_or_none()

    def _approved(self, model_id: uuid.UUID) -> bool:
        return (
            self._s.execute(
                select(ModelApproval.id).where(
                    ModelApproval.model_version_id == model_id, ModelApproval.action == ModelAction.APPROVE
                )
            ).first()
            is not None
        )

    # --- commands -------------------------------------------------------------------------------------------------
    def act(self, model_id: uuid.UUID, action: ModelAction, reason: str, lock_version: int | None) -> ModelVersion:
        model = self.model(model_id, lock=True)
        check_version(model.lock_version, lock_version, LABEL)
        if action is ModelAction.ROLLBACK:
            return self._rollback(model, reason)
        if action is ModelAction.TRAIN:
            raise BusinessRuleViolation("Training is a job, not a lifecycle action", code="INVALID_MODEL_ACTION")
        self._preconditions(model, action)
        if action in (ModelAction.DEPLOY_SHADOW, ModelAction.DEPLOY_ACTIVE):
            self._retire_other_deployed(model, reason)
        target = _ACTION_TARGET[action]
        if action is ModelAction.APPROVE and model.status is ModelStatus.DEPLOYED_SHADOW:
            target = ModelStatus.DEPLOYED_SHADOW  # approval recorded; the shadow deployment continues
        self._move(model, action, target, reason)
        if action in (ModelAction.DEPLOY_SHADOW, ModelAction.DEPLOY_ACTIVE):
            self._emit("MlModelDeployed", model, action)
        elif action is ModelAction.DISABLE:
            self._emit("MlModelDisabled", model, action)
        return model

    def _preconditions(self, model: ModelVersion, action: ModelAction) -> None:
        evaluation = self.evaluation(model.id)
        if action in (ModelAction.DEPLOY_SHADOW, ModelAction.DEPLOY_ACTIVE, ModelAction.APPROVE) and evaluation is None:
            raise BusinessRuleViolation("The model has no evaluation yet", code="EVALUATION_REQUIRED")
        if action in (ModelAction.APPROVE, ModelAction.DEPLOY_ACTIVE) and evaluation and not evaluation.passed:
            raise BusinessRuleViolation(
                "The evaluation did not pass the promotion criteria; only shadow deployment is possible",
                code="EVALUATION_NOT_PASSED",
            )
        if action is ModelAction.DEPLOY_ACTIVE and not self._approved(model.id):
            raise BusinessRuleViolation(
                "Active deployment requires a recorded platform approval first", code="APPROVAL_REQUIRED"
            )
        if action is ModelAction.APPROVE and self._approved(model.id):
            raise Conflict("This model version is already approved", code="ALREADY_APPROVED")
        if model.status not in _ACTION_FROM[action]:
            raise Conflict(
                f"{action.value} is not possible while the model is {model.status.value}",
                code="INVALID_MODEL_TRANSITION",
            )

    def _move(
        self,
        model: ModelVersion,
        action: ModelAction,
        target: ModelStatus,
        reason: str,
        related: uuid.UUID | None = None,
    ) -> None:
        before = model.status
        if target is not before and target not in MODEL_TRANSITIONS[before]:
            raise Conflict(f"{before.value} -> {target.value} is not permitted", code="INVALID_MODEL_TRANSITION")
        self._s.add(
            ModelApproval(
                id=uuid.uuid4(),
                tenant_id=model.tenant_id,
                model_version_id=model.id,
                model_name=model.name,
                action=action,
                from_status=before,
                to_status=target,
                related_model_version_id=related,
                reason=reason,
                decided_by=self._actor.user_id,
                decided_at=self._now,
            )
        )
        self._s.flush()  # the DB guard checks approvals before an ACTIVE deployment
        if target is not before:
            model.status, model.status_changed_at = target, self._now
            if target in DEPLOYED_STATUSES:
                model.deployed_at = self._now
        flush_versioned(self._s, LABEL, "MODEL_ALREADY_DEPLOYED", "Another version is already deployed")
        self._audit.record(
            actor=self._actor,
            action=f"platform.ml.model.{action.value.lower()}",
            entity_type="model_version",
            entity_id=model.id,
            tenant_id=model.tenant_id,
            before={"status": before.value},
            after={"status": target.value, "version": model.version, "related_model_version_id": str(related or "")},
            reason=reason,
        )

    def _deployed_other(self, model: ModelVersion) -> ModelVersion | None:
        return self._s.execute(
            select(ModelVersion)
            .where(
                ModelVersion.tenant_id == model.tenant_id,
                ModelVersion.name == model.name,
                ModelVersion.status.in_(DEPLOYED_STATUSES),
                ModelVersion.id != model.id,
            )
            .with_for_update()
        ).scalar_one_or_none()

    def _retire_other_deployed(self, model: ModelVersion, reason: str) -> None:
        current = self._deployed_other(model)
        if current is not None:
            note = f"Superseded by version {model.version}: {reason}"
            self._move(current, ModelAction.RETIRE, ModelStatus.RETIRED, note, related=model.id)

    def _rollback(self, model: ModelVersion, reason: str) -> ModelVersion:
        if model.status not in DEPLOYED_STATUSES:
            raise Conflict("Only the deployed version can be rolled back", code="MODEL_NOT_DEPLOYED")
        previous = self._s.execute(
            select(ModelVersion, ModelApproval.to_status)
            .join(ModelApproval, ModelApproval.model_version_id == ModelVersion.id)
            .where(
                ModelApproval.tenant_id == model.tenant_id,
                ModelApproval.model_name == model.name,
                ModelApproval.to_status.in_(DEPLOYED_STATUSES),
                ModelVersion.id != model.id,
                ModelVersion.status == ModelStatus.RETIRED,
            )
            .order_by(ModelApproval.seq.desc())
            .limit(1)
            .with_for_update(of=ModelVersion)
        ).first()
        if previous is None:
            raise Conflict("There is no previously deployed version to roll back to", code="NO_PREVIOUS_DEPLOYMENT")
        target_model, mode = previous
        self._move(model, ModelAction.ROLLBACK, ModelStatus.RETIRED, reason, related=target_model.id)
        self._move(target_model, ModelAction.ROLLBACK, mode, reason, related=model.id)
        self._emit("MlModelDeployed", target_model, ModelAction.ROLLBACK)
        return model

    def _emit(self, event_type: str, model: ModelVersion, action: ModelAction) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type=event_type,
            key=str(model.id),
            payload={
                "model_version_id": str(model.id),
                "name": model.name,
                "version": model.version,
                "status": model.status.value,
                "action": action.value,
            },
            tenant_id=model.tenant_id,
        )

    # --- platform hard switch -----------------------------------------------------------------------------------
    def update_settings(self, enabled: bool, reason: str, lock_version: int | None) -> MlSettingView:
        self._s.execute(
            pg_insert(MlSetting)
            .values(
                id=1,
                inference_enabled=DEFAULT_INFERENCE_ENABLED,
                reason=DEFAULT_SETTING_REASON,
                updated_at=self._now,
                lock_version=0,  # the default, materialised; the change below makes it version 1
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        row = self._s.execute(select(MlSetting).where(MlSetting.id == 1).with_for_update()).scalar_one()
        self._s.refresh(row)
        check_version(row.lock_version, lock_version, "ML settings")
        before = row.inference_enabled
        row.inference_enabled, row.reason = enabled, reason
        row.updated_by, row.updated_at = self._actor.user_id, self._now
        flush_versioned(self._s, "ML settings")
        self._audit.record(
            actor=self._actor,
            action="platform.ml.settings.updated",
            entity_type="ml_setting",
            entity_id="1",
            tenant_id=None,
            before={"inference_enabled": before},
            after={"inference_enabled": enabled},
            reason=reason,
        )
        if before != enabled:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="MlInferenceSwitched",
                key="ml_setting",
                payload={"inference_enabled": enabled, "reason": reason},
                tenant_id=None,
            )
        return current_ml_setting(self._s)
