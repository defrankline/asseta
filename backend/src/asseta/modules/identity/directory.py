"""Tenant people directory: display names for user ids a tenant member already sees on records ("recorded by",
"decided by", "requested by"). Only display names, never e-mail, and only for users who are or were members of the
requested tenant, so an id from another tenant resolves to nothing."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.models import AppUser, TenantMembership
from asseta.modules.identity.principal import RequestContext

DIRECTORY_READ = requires("tenant.directory.read", S.TENANT, "See colleagues' display names on records")
MAX_IDS = 100
UUID_LIST = rf"^[0-9a-fA-F-]{{36}}(,[0-9a-fA-F-]{{36}}){{0,{MAX_IDS - 1}}}$"

router = APIRouter(prefix="/api/v1/tenant/people", tags=["tenant-people"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


class PersonDto(BaseModel):
    user_id: uuid.UUID
    display_name: str


@router.get("", response_model=list[PersonDto], operation_id="listTenantPeople")
def list_people(
    ctx: Annotated[RequestContext, Depends(DIRECTORY_READ)],
    session: DbSession,
    ids: Annotated[str, Query(pattern=UUID_LIST, description=f"Comma-separated user ids (at most {MAX_IDS})")],
) -> list[PersonDto]:
    try:
        wanted = {uuid.UUID(raw) for raw in ids.split(",")}
    except ValueError as exc:
        raise BusinessRuleViolation("ids must be comma-separated UUIDs", code="INVALID_IDS") from exc
    members = (
        select(TenantMembership.user_id)
        .where(TenantMembership.tenant_id == ctx.tenant_id, TenantMembership.user_id.in_(wanted))
        .distinct()
    )
    rows = session.execute(
        select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(members)).order_by(AppUser.display_name)
    ).all()
    return [PersonDto(user_id=r.id, display_name=r.display_name) for r in rows]
