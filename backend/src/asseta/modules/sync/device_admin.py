"""Administration -> Devices: the company's registered phones with the person each belongs to (DEC-032)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import NotFound
from asseta.core.paging import Page, PageParams, paginate
from asseta.core.search import ilike_any
from asseta.modules.accountability.names import fill_names
from asseta.modules.identity.models import AppUser
from asseta.modules.sync.dto import TenantDeviceDto
from asseta.modules.sync.models import DeviceSession


def _dtos(session: Session, rows: list[DeviceSession]) -> list[TenantDeviceDto]:
    named = select(AppUser.id, AppUser.display_name).where(AppUser.id.in_({r.user_id for r in rows}))
    people = {row.id: row.display_name for row in session.execute(named)}
    return fill_names(
        session,
        [TenantDeviceDto.model_validate(r).model_copy(update={"user_name": people.get(r.user_id)}) for r in rows],
    )


def device_page(session: Session, paging: PageParams) -> Page[TenantDeviceDto]:
    stmt = (
        select(DeviceSession)
        .outerjoin(AppUser, AppUser.id == DeviceSession.user_id)
        .order_by(DeviceSession.registered_at.desc(), DeviceSession.id)
    )
    match = ilike_any(
        paging.q,
        AppUser.display_name,
        DeviceSession.device_id,
        DeviceSession.device_model,
        DeviceSession.platform,
        DeviceSession.app_version,
    )
    if match is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return Page(items=_dtos(session, rows), total=total, page=paging.page, page_size=paging.page_size)


def get_device(session: Session, device_session_id: uuid.UUID) -> DeviceSession:
    row = session.get(DeviceSession, device_session_id)
    if row is None:
        raise NotFound("Device session not found")
    return row


def device_dto(session: Session, row: DeviceSession) -> TenantDeviceDto:
    return _dtos(session, [row])[0]
