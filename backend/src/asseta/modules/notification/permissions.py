"""Notification permissions. Inbox/preferences/profile are self-service (own rows only, enforced by RLS too); writes
to them stay possible for READ_ONLY tenants so a suspended tenant can still work through its billing notices."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

TENANT_READ = requires("tenant.notification.read", S.TENANT, "Receive notifications; manage own inbox, preferences")
TENANT_SELF = requires(
    "tenant.notification.read",
    S.TENANT,
    "Receive notifications; manage own inbox, preferences",
    quarantine_when_read_only=True,
)
TENANT_MANAGE = requires(
    "tenant.notification.manage", S.TENANT, "Set tenant-wide notification defaults; view the SMS delivery log"
)
PLATFORM_READ = requires("platform.notification.read", S.PLATFORM, "Receive platform notifications; own inbox")
PLATFORM_MANAGE = requires(
    "platform.notification.manage", S.PLATFORM, "Platform SMS delivery log and notification test-send"
)

# The signed-in user's own inbox, one per console (both open the same page).
CATALOG.register_menu(
    MenuDef(
        "tenant.notifications",
        S.TENANT,
        "Notifications",
        "/notifications",
        96,
        "tenant.notification.read",
        "tenant.admin",
    )
)
CATALOG.register_menu(
    MenuDef(
        "platform.notifications",
        S.PLATFORM,
        "Notifications",
        "/notifications",
        96,
        "platform.notification.read",
        "platform.admin",
    )
)
