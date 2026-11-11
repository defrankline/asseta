"""Company closure (deletion) API DTOs."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from asseta.modules.dataprotection.models import DeletionStatus

Reason = Annotated[str, StringConstraints(min_length=3, max_length=1000, strip_whitespace=True)]


class CompanyDeletionIn(BaseModel):
    confirm_name: Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)] = Field(
        description="The company's display name, typed by the owner (case does not matter)"
    )
    reason: Reason


class DeletionReasonIn(BaseModel):
    reason: Reason


class CompanyDeletionRequestDto(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    status: DeletionStatus
    reason: str
    requested_by: uuid.UUID | None
    requested_by_name: str | None
    requested_at: datetime
    waiting_days: int = Field(description="The platform-wide waiting period when the request was made")
    scheduled_for: datetime = Field(description="When the deletion runs (no earlier)")
    policy_version: str
    cancelled_by: uuid.UUID | None
    cancelled_by_name: str | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    execute_now_by: uuid.UUID | None = Field(description="Platform staff who ran it before the waiting period ended")
    execute_now_at: datetime | None
    execute_now_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    attempts: int
    last_error: str | None = Field(description="Why the last attempt stopped; the worker retries from where it was")
    steps_done: list[str] = Field(description="Finished deletion steps, in order")


class CompanyDeletionStatusDto(BaseModel):
    """What the owner's "Close company" screen needs: the name to type, the waiting period and the current request."""

    tenant_id: uuid.UUID
    company_name: str
    waiting_days: int = Field(description="Current platform-wide waiting period before a requested deletion runs")
    request: CompanyDeletionRequestDto | None = Field(
        description="The active request (REQUESTED / IN_PROGRESS), else the latest one, else null"
    )
