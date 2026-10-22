"""Tenant people directory: display names for user ids a tenant member already sees on records ("recorded by",
"decided by", "requested by"), and a name search over current members for pickers (e.g. assigning a case). Only
display names, never e-mail, and only for members of the requested tenant, so an id from another tenant resolves
to nothing."""

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
SEARCH_LIMIT = 20
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
    ids: Annotated[
        str | None, Query(pattern=UUID_LIST, description=f"Comma-separated user ids (at most {MAX_IDS})")
    ] = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=100, description=f"Name search over current members (at most {SEARCH_LIMIT})"),
    ] = None,
) -> list[PersonDto]:
    if (ids is None) == (q is None):
        raise BusinessRuleViolation("Give exactly one of ids or q", code="INVALID_PEOPLE_QUERY")
    members = select(TenantMembership.user_id).where(TenantMembership.tenant_id == ctx.tenant_id)
    stmt = select(AppUser.id, AppUser.display_name).order_by(AppUser.display_name)
    if ids is not None:
        try:
            wanted = {uuid.UUID(raw) for raw in ids.split(",")}
        except ValueError as exc:
            raise BusinessRuleViolation("ids must be comma-separated UUIDs", code="INVALID_IDS") from exc
        stmt = stmt.where(AppUser.id.in_(members.where(TenantMembership.user_id.in_(wanted)).distinct()))
    else:
        current = members.where(TenantMembership.effective_to.is_(None)).distinct()
        pattern = "%" + (q or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(AppUser.id.in_(current), AppUser.is_active.is_(True))
        stmt = stmt.where(AppUser.display_name.ilike(pattern, escape="\\")).limit(SEARCH_LIMIT)
    return [PersonDto(user_id=r.id, display_name=r.display_name) for r in session.execute(stmt).all()]
