"""Platform ML monitoring API (`/api/v1/platform/ml/...`, platform.ml.read): predictions with full provenance (shadow
included — the platform observes shadow models, tenants never do), the inference audit log and the drift history of
a model version. The latest drift check and latency/volume stats are also on the model detail (`getMlModelVersion`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.ml_dto import MlDriftDto, MlInferenceAuditDto, MlPredictionDto
from asseta.modules.intelligence.ml_monitoring_models import (
    DecisionState,
    InferenceAudit,
    InferenceOutcome,
    ModelDrift,
    Prediction,
)
from asseta.modules.intelligence.ml_router import ML_READ

router = APIRouter(prefix="/api/v1/platform/ml", tags=["ml-governance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Read = Annotated[RequestContext, Depends(ML_READ)]
Paging = Annotated[PageParams, Depends(page_params)]


@router.get("/predictions", response_model=Page[MlPredictionDto], operation_id="listMlPredictions")
def list_predictions(
    session: DbSession,
    _: Read,
    paging: Paging,
    model_version_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    decision_state: DecisionState | None = None,
    subject_id: uuid.UUID | None = None,
) -> Page[MlPredictionDto]:
    stmt = select(Prediction).order_by(Prediction.as_of.desc(), Prediction.created_at.desc(), Prediction.id)
    filters = {
        Prediction.model_version_id: model_version_id,
        Prediction.tenant_id: tenant_id,
        Prediction.decision_state: decision_state,
        Prediction.subject_id: subject_id,
    }
    for col, value in filters.items():
        if value is not None:
            stmt = stmt.where(col == value)
    rows, total = paginate(session, stmt, paging)
    items = [MlPredictionDto.model_validate(r) for r in rows]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/inference-audit", response_model=Page[MlInferenceAuditDto], operation_id="listMlInferenceAudit")
def list_inference_audit(
    session: DbSession,
    _: Read,
    paging: Paging,
    model_version_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    outcome: InferenceOutcome | None = None,
) -> Page[MlInferenceAuditDto]:
    stmt = select(InferenceAudit).order_by(InferenceAudit.started_at.desc(), InferenceAudit.created_at.desc())
    filters = {
        InferenceAudit.model_version_id: model_version_id,
        InferenceAudit.tenant_id: tenant_id,
        InferenceAudit.outcome: outcome,
    }
    for col, value in filters.items():
        if value is not None:
            stmt = stmt.where(col == value)
    rows, total = paginate(session, stmt, paging)
    items = [MlInferenceAuditDto.model_validate(r) for r in rows]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/models/{model_id}/drift", response_model=Page[MlDriftDto], operation_id="listMlModelDrift")
def list_drift(model_id: uuid.UUID, session: DbSession, _: Read, paging: Paging) -> Page[MlDriftDto]:
    stmt = select(ModelDrift).where(ModelDrift.model_version_id == model_id).order_by(ModelDrift.computed_at.desc())
    rows, total = paginate(session, stmt, paging)
    items = [MlDriftDto.model_validate(r) for r in rows]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)
