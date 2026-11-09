"""Owner decision 2026-11: only a holder of `tenant.access.assign_approvers` gives or removes a role that carries
approvals, decided by the permissions a role carries and never by its name."""

import uuid
from pathlib import Path
from typing import Any

import asseta
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.role_templates import ASSIGN_APPROVERS_PERMISSION
from tests.api.test_managed_service import assign, grant, refreshed, staff
from tests.support.api import PLATFORM_SUBJECT, Actor, Api

A = "/api/v1/tenant/access"
CODE = "APPROVER_ROLE_ASSIGN_FORBIDDEN"
MESSAGE = "Only the company owner can give someone a role that approves things."


def _invite(actor: Actor, email: str, role: str) -> Any:
    return actor.post(f"{A}/members", {"email": email, "first_name": "New", "last_name": "Person", "role_key": role})


def _refused(r: Any) -> None:
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == CODE and r.json()["error"]["message"] == MESSAGE


def _member(api: Api, tid: str, owner: Actor, email: str, role: str) -> Actor:
    assert _invite(owner, email, role).status_code == 201
    return api.tenant_user(email, tid)


def _user_id(owner: Actor, email: str) -> str:
    return str(next(m["user_id"] for m in owner.get(f"{A}/members").json() if m["email"] == email))


def _custom_role(api: Api, tid: str, key: str, codes: set[str]) -> None:
    gid = api.idp.ensure_group(f"/tenants/{tid}/{key}")
    api.idp.set_group_permissions(gid, codes)
    _mirror(api, tid)


def _mirror(api: Api, tid: str) -> None:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        AuthzSyncService(api.idp).pull_role_mirror(s, only_tenant=uuid.UUID(tid))


def _refusals(owner: Actor) -> list[dict[str, Any]]:
    rows = owner.get("/api/v1/tenant/security-events", kind="PERMISSION_DENIED").json()["items"]
    return [e for e in rows if e["permission"] == ASSIGN_APPROVERS_PERMISSION]


def test_invite_with_a_role_that_approves_needs_the_permission(api: Api) -> None:
    a = api.onboard("Grant Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    admin = _member(api, tid, owner, "admin@grant.example.com", "administrator")

    before = dict(api.idp.users)
    _refused(_invite(admin, "new@grant.example.com", "manager"))
    assert api.idp.users == before  # refused before anything changed at the identity provider
    events = _refusals(owner)
    assert len(events) == 1 and events[0]["request_path"] == f"{A}/members"

    # Roles without approvals stay with whoever manages access; a holder may give any role.
    assert _invite(admin, "sup@grant.example.com", "supervisor").status_code == 201
    assert _invite(owner, "mgr@grant.example.com", "manager").status_code == 201


def test_removing_a_role_that_approves_needs_the_permission(api: Api) -> None:
    a = api.onboard("Revoke Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    admin = _member(api, tid, owner, "admin@revoke.example.com", "administrator")
    _member(api, tid, owner, "mgr@revoke.example.com", "manager")
    _member(api, tid, owner, "op@revoke.example.com", "operator")

    mgr_id = _user_id(owner, "mgr@revoke.example.com")
    _refused(admin.post(f"{A}/members/{mgr_id}/roles/manager/revoke"))
    assert len(_refusals(owner)) == 1
    op_id = _user_id(owner, "op@revoke.example.com")
    assert admin.post(f"{A}/members/{op_id}/roles/operator/revoke").status_code == 200
    assert owner.post(f"{A}/members/{mgr_id}/roles/manager/revoke").status_code == 200


def test_role_is_judged_by_what_it_carries_not_its_name(api: Api) -> None:
    a = api.onboard("Custom Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    admin = _member(api, tid, owner, "admin@custom.example.com", "administrator")
    _custom_role(api, tid, "shift-lead", {"tenant.job.read", "tenant.job.approve"})
    _custom_role(api, tid, "delegate", {ASSIGN_APPROVERS_PERMISSION})  # carries no approval but reaches them
    _custom_role(api, tid, "viewer", {"tenant.job.read"})

    _refused(_invite(admin, "a@custom.example.com", "shift-lead"))
    _refused(_invite(admin, "b@custom.example.com", "delegate"))
    assert _invite(admin, "c@custom.example.com", "viewer").status_code == 201
    assert _invite(owner, "d@custom.example.com", "shift-lead").status_code == 201
    flags = {r["role_key"]: r["carries_approvals"] for m in owner.get(f"{A}/members").json() for r in m["roles"]}
    assert flags == {"owner": True, "administrator": False, "viewer": False, "shift-lead": True}


def test_nobody_gives_themselves_such_a_role_without_the_permission(api: Api) -> None:
    a = api.onboard("Self Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    admin = _member(api, tid, owner, "admin@self.example.com", "administrator")

    _refused(_invite(admin, "admin@self.example.com", "manager"))
    events = _refusals(owner)
    assert len(events) == 1 and events[0]["detail"]["self"] is True
    assert sorted(api.idp.memberships[admin.subject]) == [f"/tenants/{tid}/administrator"]
    assert _invite(owner, str(a["owner_email"]), "manager").status_code == 201  # a holder may


def test_a_tenant_always_keeps_a_holder(api: Api) -> None:
    a = api.onboard("Holder Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    _custom_role(api, tid, "delegate", {ASSIGN_APPROVERS_PERMISSION, "tenant.access.manage", "tenant.access.read"})
    first = _member(api, tid, owner, "first@holder.example.com", "delegate")
    # The tenant takes the right off its owner group: the delegate is now the only holder.
    owner_gid = api.idp.groups[f"/tenants/{tid}/owner"]
    api.idp.set_group_permissions(owner_gid, api.idp.group_perms[owner_gid] - {ASSIGN_APPROVERS_PERMISSION})
    _mirror(api, tid)

    first_id = _user_id(first, "first@holder.example.com")
    last = first.post(f"{A}/members/{first_id}/roles/delegate/revoke")
    assert last.status_code == 422 and last.json()["error"]["code"] == "LAST_APPROVER_ASSIGNER"
    assert _invite(first, "second@holder.example.com", "delegate").status_code == 201
    assert first.post(f"{A}/members/{first_id}/roles/delegate/revoke").status_code == 200


def test_mandate_staff_never_count_as_the_remaining_holder(api: Api) -> None:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    a = api.onboard("Holder Mandate Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    _custom_role(api, tid, "delegate", {ASSIGN_APPROVERS_PERMISSION, "tenant.access.manage", "tenant.access.read"})
    delegate = _member(api, tid, owner, "client@holder.example.com", "delegate")
    actor = staff(api, "staff-holder", "staff-holder@asseta.local")
    assert assign(api, grant(api, tid), "staff-holder@asseta.local", "delegate").status_code == 200
    owner_gid = api.idp.groups[f"/tenants/{tid}/owner"]
    api.idp.set_group_permissions(owner_gid, api.idp.group_perms[owner_gid] - {ASSIGN_APPROVERS_PERMISSION})
    _mirror(api, tid)
    assert refreshed(api, actor, tid).get(f"{A}/members").status_code == 200

    client_id = _user_id(delegate, "client@holder.example.com")
    last = delegate.post(f"{A}/members/{client_id}/roles/delegate/revoke")
    assert last.status_code == 422 and last.json()["error"]["code"] == "LAST_APPROVER_ASSIGNER"


def test_mandate_staff_act_only_where_the_scope_allows(api: Api) -> None:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    a = api.onboard("Mandate Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    full_owner = staff(api, "staff-owner", "staff-owner@asseta.local")
    full_admin = staff(api, "staff-admin", "staff-admin@asseta.local")
    full = grant(api, tid)
    assert assign(api, full, "staff-owner@asseta.local", "owner").status_code == 200
    assert assign(api, full, "staff-admin@asseta.local", "administrator").status_code == 200

    _refused(_invite(refreshed(api, full_admin, tid), "x@mandate.example.com", "manager"))
    assert _invite(refreshed(api, full_owner, tid), "y@mandate.example.com", "manager").status_code == 201
    assert _refusals(owner)


def test_operations_mandate_is_not_widened(api: Api) -> None:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    a = api.onboard("Ops Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    actor = staff(api, "staff-ops", "staff-ops@asseta.local")
    _custom_role(api, tid, "field-helper", {"tenant.job.read"})
    ops = grant(api, tid, scope="OPERATIONS")

    r = assign(api, ops, "staff-ops@asseta.local", "owner")
    assert r.status_code == 422 and r.json()["error"]["code"] == "MANDATE_ROLE_SCOPE"
    events = owner.get("/api/v1/tenant/security-events", kind="PERMISSION_DENIED").json()["items"]
    assert [e["action"] for e in events if e["action"] == "mandate_assign"] == ["mandate_assign"]

    # The role gains access administration after staff were assigned it: the scope still decides.
    assert assign(api, ops, "staff-ops@asseta.local", "field-helper").status_code == 200
    gid = api.idp.groups[f"/tenants/{tid}/field-helper"]
    api.idp.set_group_permissions(
        gid, {"tenant.job.read", "tenant.access.read", "tenant.access.manage", ASSIGN_APPROVERS_PERMISSION}
    )
    _mirror(api, tid)
    _refused(_invite(refreshed(api, actor, tid), "z@ops.example.com", "manager"))


def test_no_route_can_edit_a_roles_permissions() -> None:
    """Custom roles are edited only in Keycloak today, so rule 2 has no route to guard. A route that starts changing a
    role's permissions must apply the same refusal; this fails until it is reviewed against that rule."""
    root = Path(asseta.__file__).parent
    callers = {
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if "set_group_permissions(" in p.read_text() and p.name not in ("idp.py", "keycloak_admin.py")
    }
    assert callers == {"modules/identity/authz_sync.py"}
