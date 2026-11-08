"""Data protection requests and responses."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.dataprotection.models import (
    ExportFormat,
    ExportStatus,
    VerificationOutcome,
    VerificationTrigger,
)


class DataExportIn(BaseModel):
    format: ExportFormat = ExportFormat.CSV


class DataExportDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    format: ExportFormat
    status: ExportStatus
    requested_by: uuid.UUID | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    sha256: str | None
    size_bytes: int | None
    table_count: int | None
    row_count: int | None
    evidence_count: int | None
    error_code: str | None


class DownloadLinkDto(BaseModel):
    url: str
    expires_in_seconds: int


class VerificationCheckDto(BaseModel):
    check: str
    checked: int
    mismatches: int


class VerificationFindingDto(BaseModel):
    check: str
    subject_type: str
    subject_id: str
    label: str
    currency: str | None
    ledger_value: str
    stored_value: str
    difference: str
    source: str
    details: dict[str, Any]


class VerificationRunSummaryDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    trigger: VerificationTrigger
    requested_by: uuid.UUID | None
    started_at: datetime
    finished_at: datetime
    outcome: VerificationOutcome
    checked_count: int
    mismatch_count: int
    summary: list[VerificationCheckDto]


class VerificationRunDto(VerificationRunSummaryDto):
    findings: list[VerificationFindingDto]
    findings_truncated: bool


class TenantVerificationDto(BaseModel):
    """Platform view: one line per tenant, counts only (no business records leave the tenant's scope)."""

    tenant_id: uuid.UUID
    tenant_name: str
    registration_number: str | None
    live_at: datetime | None
    latest: VerificationRunSummaryDto | None


class GoLiveIn(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)
