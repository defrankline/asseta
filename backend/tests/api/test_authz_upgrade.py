"""Release upgrade semantics for Keycloak-authoritative permissions: permissions introduced by a new release are
granted to template-matching role groups; permissions an owner deliberately removed are not re-added."""

from sqlalchemy import create_engine, text

from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.modules.identity.authz_sync import AuthzSyncService
from tests.support.api import Api


def _forget(code: str) -> None:
    """Simulate a deployment that predates `code`: it was never offered to any role group."""
    engine = create_engine(get_settings().migration_database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM role_template_grant WHERE permission_code = :c"), {"c": code})
    engine.dispose()


def test_new_release_permissions_reach_existing_groups_but_removals_stick(api: Api) -> None:
    t = api.onboard("Upgrade Co", price="1")
    owner_path = f"/tenants/{t['tenant']['id']}/owner"
    owner_group = api.idp.groups[owner_path]
    platform_group = api.idp.groups["/platform/platform-owner"]
    # Owner deliberately removed tenant.policy.manage; a "new release" introduces tenant.geofence.write.
    api.idp.group_perms[owner_group].discard("tenant.policy.manage")
    api.idp.group_perms[owner_group].discard("tenant.geofence.write")
    api.idp.group_perms[platform_group].discard("platform.tracker_model.manage")
    _forget("tenant.geofence.write")
    _forget("platform.tracker_model.manage")

    with get_sessionmaker().begin() as s:
        AuthzSyncService(api.idp).full_sync(s)

    assert "tenant.geofence.write" in api.idp.group_perms[owner_group]  # new in this release -> granted
    assert "tenant.policy.manage" not in api.idp.group_perms[owner_group]  # owner's removal respected
    assert "platform.tracker_model.manage" in api.idp.group_perms[platform_group]
    perms = t["owner"].get("/api/v1/me").json()["tenants"][0]["permissions"]
    assert "tenant.geofence.write" in perms and "tenant.policy.manage" not in perms
