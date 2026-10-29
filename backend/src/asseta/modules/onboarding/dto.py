"""Go-live setup checklist DTOs."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from asseta.modules.onboarding.checklist import StepKey, StepStatus

Reason = Annotated[str, StringConstraints(min_length=3, max_length=500, strip_whitespace=True)]


class SetupCheckDto(BaseModel):
    key: str
    label: str
    done: bool
    optional: bool = Field(description="Advice only: never holds the step back")
    done_count: int | None
    total_count: int | None
    link: str = Field(description="Web route of the screen that fixes this part")
    required_permission: str


class NotNeededDto(BaseModel):
    reason: str | None
    marked_by: uuid.UUID
    marked_by_name: str | None = None
    marked_at: datetime


class SetupStepDto(BaseModel):
    key: StepKey
    order: int
    title: str
    description: str = Field(description="Plain-English explanation of what to do and why")
    status: StepStatus
    done_count: int | None = Field(description="e.g. machines with an approved starting reading")
    total_count: int | None = Field(description="e.g. active machines; null when a count means nothing")
    link: str = Field(description="Web route of the screen to do it (the first part still to do)")
    required_permission: str = Field(description="Permission needed to do this step on that screen")
    can_mark_not_needed: bool
    not_needed: NotNeededDto | None = Field(default=None, description="Set while the owner marked it as not needed")
    checks: list[SetupCheckDto] = Field(default_factory=list, description="The parts of the step, each with a link")


class SetupChecklistDto(BaseModel):
    steps: list[SetupStepDto]
    steps_done: int = Field(description="DONE + NOT_NEEDED steps")
    steps_total: int = Field(description="Steps that apply (NOT_APPLICABLE excluded)")
    percent: int = Field(ge=0, le=100)
    complete: bool
    dismissed: bool
    dismissed_by: uuid.UUID | None = None
    dismissed_by_name: str | None = None
    dismissed_at: datetime | None = None
    controls_confirmed_by: uuid.UUID | None = None
    controls_confirmed_by_name: str | None = None
    controls_confirmed_at: datetime | None = None
    as_of: datetime


class NotNeededIn(BaseModel):
    reason: Reason = Field(description="Why this step does not apply to the business")


class ConfirmControlsIn(BaseModel):
    note: Annotated[str, StringConstraints(max_length=500, strip_whitespace=True)] | None = None
