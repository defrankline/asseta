"""Risk-signal and investigation-case DTOs (class names are unique across the API for OpenAPI)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.intelligence.models import (
    CaseNoteKind,
    CaseOutcomeKind,
    CaseSourceType,
    CaseStatus,
    RuleCode,
    SignalSeverity,
    SignalStatus,
    SubjectType,
)

Version = Annotated[int | None, Field(default=None, ge=1, description="Optimistic concurrency token from last read")]


class _Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RiskSignalDto(_Dto):
    id: uuid.UUID
    rule_code: RuleCode
    rule_version: int
    severity: SignalSeverity
    subject_type: SubjectType
    subject_id: uuid.UUID
    machine_id: uuid.UUID | None
    job_id: uuid.UUID | None
    staff_member_id: uuid.UUID | None
    window_start: datetime
    window_end: datetime
    evidence: dict[str, Any]
    policy_version: str
    dedupe_key: str
    status: SignalStatus
    created_at: datetime


class AnomalyCaseDto(_Dto):
    id: uuid.UUID
    case_number: str
    title: str
    subject_type: SubjectType
    subject_id: uuid.UUID
    machine_id: uuid.UUID | None
    job_id: uuid.UUID | None
    staff_member_id: uuid.UUID | None
    severity: SignalSeverity
    status: CaseStatus
    assignee_user_id: uuid.UUID | None
    assignee_name: str | None = None
    opened_at: datetime
    last_signal_at: datetime
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None
    signal_count: int = 0
    latest_outcome: CaseOutcomeKind | None = None
    policy_version: str
    version: int


class CaseSignalDto(_Dto):
    id: uuid.UUID
    source_type: CaseSourceType
    source_id: uuid.UUID
    code: str
    severity: SignalSeverity
    observed_at: datetime
    evidence: dict[str, Any]
    linked_at: datetime


class CaseNoteDto(_Dto):
    id: uuid.UUID
    kind: CaseNoteKind
    body: str
    author_user_id: uuid.UUID | None
    author_name: str | None = None
    created_at: datetime


class CaseOutcomeDto(_Dto):
    id: uuid.UUID
    sequence: int
    outcome: CaseOutcomeKind
    explanation: str
    decided_by: uuid.UUID
    decided_by_name: str | None = None
    decided_at: datetime


class AnomalyCaseDetailDto(BaseModel):
    case: AnomalyCaseDto
    signals: list[CaseSignalDto]
    notes: list[CaseNoteDto]
    outcomes: list[CaseOutcomeDto]


class CaseAssignIn(BaseModel):
    assignee_user_id: uuid.UUID
    version: Version = None


class CaseNoteIn(BaseModel):
    body: Annotated[str, StringConstraints(min_length=1, max_length=4000, strip_whitespace=True)]


class CaseResolveIn(BaseModel):
    outcome: CaseOutcomeKind
    explanation: Annotated[str, StringConstraints(min_length=10, max_length=4000, strip_whitespace=True)]
    version: Version = None


class CaseReopenIn(BaseModel):
    reason: Annotated[str, StringConstraints(min_length=10, max_length=2000, strip_whitespace=True)]
    version: Version = None
