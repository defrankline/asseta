"""Audit of manual overrides of on-device OCR (Gate 6, prompt.md R1-H "manual correction audit"): every meter capture
where an OCR reading existed but the stored reading was entered by a person — the supervisor corrected the OCR value
(`manually_corrected`) or the capture was taken in MANUAL mode — with OCR vs entered value, confidence, engine, who,
when and the machine, plus the related MANUAL_CORRECTION exception and its review status. Tenant RLS scope only;
OCR confidence is shown as recorded, never as proof either way (prompt.md §7)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from asseta.core.paging import PageParams
from asseta.modules.fleet.models import Machine
from asseta.modules.identity.models import AppUser, TenantMembership
from asseta.modules.intelligence.insights_dto import (
    ManualOverrideItemDto,
    ManualOverrideReportDto,
    ManualOverrideSummaryDto,
)
from asseta.modules.jobs.models import Job
from asseta.modules.meter.models import ExceptionStatus, ExceptionType, JobException, MeterCapture


def _filtered(
    tenant_id: uuid.UUID,
    captured_from: datetime | None,
    captured_to: datetime | None,
    machine_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> list[Any]:
    conds: list[Any] = [
        MeterCapture.tenant_id == tenant_id,
        MeterCapture.ocr_value.is_not(None),
        or_(MeterCapture.manually_corrected.is_(True), MeterCapture.capture_mode == "MANUAL"),
    ]
    if captured_from is not None:
        conds.append(MeterCapture.captured_at >= captured_from)
    if captured_to is not None:
        conds.append(MeterCapture.captured_at < captured_to)
    if machine_id is not None:
        conds.append(MeterCapture.machine_id == machine_id)
    if user_id is not None:
        conds.append(MeterCapture.supervisor_user_id == user_id)
    return conds


def _exception_join() -> Any:
    return and_(
        JobException.meter_capture_id == MeterCapture.id,
        JobException.exception_type == ExceptionType.MANUAL_CORRECTION,
    )


def manual_override_report(
    session: Session,
    tenant_id: uuid.UUID,
    paging: PageParams,
    *,
    captured_from: datetime | None = None,
    captured_to: datetime | None = None,
    machine_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> ManualOverrideReportDto:
    conds = _filtered(tenant_id, captured_from, captured_to, machine_id, user_id)
    summary_row = session.execute(
        select(
            func.count(MeterCapture.id.distinct()),
            func.count(MeterCapture.id.distinct()).filter(MeterCapture.manually_corrected.is_(True)),
            func.count(MeterCapture.id.distinct()).filter(
                MeterCapture.capture_mode == "MANUAL", MeterCapture.manually_corrected.is_(False)
            ),
            func.count(MeterCapture.id.distinct()).filter(MeterCapture.reading != MeterCapture.ocr_value),
            func.count(JobException.id.distinct()).filter(JobException.status == ExceptionStatus.OPEN),
        )
        .select_from(MeterCapture)
        .outerjoin(JobException, _exception_join())
        .where(*conds)
    ).one()
    members = select(TenantMembership.user_id).where(TenantMembership.tenant_id == tenant_id)
    stmt = (
        select(MeterCapture, Machine.asset_code, Machine.name, Job.job_number, AppUser.display_name, JobException)
        .join(Machine, Machine.id == MeterCapture.machine_id)
        .join(Job, Job.id == MeterCapture.job_id)
        .outerjoin(
            AppUser,
            and_(AppUser.id == MeterCapture.supervisor_user_id, AppUser.id.in_(members)),
        )
        .outerjoin(JobException, _exception_join())
        .where(*conds)
        .order_by(MeterCapture.captured_at.desc(), MeterCapture.id)
        .limit(paging.page_size)
        .offset((paging.page - 1) * paging.page_size)
    )
    items = []
    for cap, asset_code, machine_name, job_number, user_name, exc in session.execute(stmt).all():
        ocr: Decimal | None = cap.ocr_value
        items.append(
            ManualOverrideItemDto(
                capture_id=cap.id,
                captured_at=cap.captured_at,
                received_at=cap.received_at,
                machine_id=cap.machine_id,
                asset_code=asset_code,
                machine_name=machine_name,
                job_id=cap.job_id,
                job_number=job_number,
                kind=cap.kind.value,
                capture_mode=cap.capture_mode,
                manually_corrected=cap.manually_corrected,
                ocr_value=ocr,
                entered_value=cap.reading,
                difference=None if ocr is None else cap.reading - ocr,
                ocr_confidence=cap.ocr_confidence,
                ocr_engine=cap.ocr_engine,
                captured_by_user_id=cap.supervisor_user_id,
                captured_by_name=user_name,
                state=cap.state.value,
                exception_id=exc.id if exc is not None else None,
                exception_status=exc.status.value if exc is not None else None,
            )
        )
    total = int(summary_row[0])
    return ManualOverrideReportDto(
        summary=ManualOverrideSummaryDto(
            total=total,
            manual_corrections=int(summary_row[1]),
            manual_mode_with_ocr=int(summary_row[2]),
            value_differs=int(summary_row[3]),
            exceptions_open=int(summary_row[4]),
        ),
        items=items,
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
