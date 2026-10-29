"""Identity API DTOs."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

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
    disabled_capabilities: list[str] = Field(
        default_factory=list,
        description="Tenant capabilities switched off by policy (e.g. CUSTOMER_HOURS); their menus are omitted",
    )
    mandate: MandateBadgeDto | None = None
    # Go-live setup checklist progress for a banner (null when the user lacks tenant.setup.read).
    setup_complete: bool | None = Field(default=None, description="All applicable go-live steps done")
    setup_percent: int | None = Field(default=None, description="Go-live checklist progress, 0-100")
    setup_steps_done: int | None = Field(default=None, description="e.g. 2 (of setup_steps_total)")
    setup_steps_total: int | None = Field(default=None, description="Applicable go-live steps (e.g. 13)")
    setup_dismissed: bool | None = Field(default=None, description="The owner hid the go-live banner")


class MeDto(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    platform_permissions: list[str]
    platform_menus: list[MenuDto]
    platform_menu_groups: list[MenuGroupDto]
    tenants: list[TenantAccessDto]
