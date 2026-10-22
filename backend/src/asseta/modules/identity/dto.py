"""Identity API DTOs."""

import uuid
from datetime import date

from pydantic import BaseModel

from asseta.modules.tenancy.models import TenantAccessState, TenantStatus


class MenuDto(BaseModel):
    key: str
    label: str
    path: str
    order: int
    group: str  # MenuGroupDto.key


class MenuGroupDto(BaseModel):
    """A side-navigation section; listed only when at least one of its menus is visible, in `order`."""

    key: str
    label: str
    order: int


class MandateBadgeDto(BaseModel):
    """Present when access to this tenant comes from a managed-service mandate (DEC-018)."""

    mandate_id: uuid.UUID
    reference: str
    scope: str
    ends_on: date | None


class TenantAccessDto(BaseModel):
    tenant_id: uuid.UUID
    name: str
    status: TenantStatus
    access_state: TenantAccessState
    permissions: list[str]
    menus: list[MenuDto]
    menu_groups: list[MenuGroupDto]
    mandate: MandateBadgeDto | None = None


class MeDto(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    platform_permissions: list[str]
    platform_menus: list[MenuDto]
    platform_menu_groups: list[MenuGroupDto]
    tenants: list[TenantAccessDto]
