"""R1-B tenant user/role administration via Keycloak (authoritative) with an effective-dated membership mirror."""

from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api


def test_invite_grant_revoke_history_and_last_owner_guard(api: Api) -> None:
    a = api.onboard("Access Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    r = owner.post(
        "/api/v1/tenant/access/members",
        {"email": "sup@access.example.com", "first_name": "Sue", "last_name": "Pervisor", "role_key": "supervisor"},
    )
    assert r.status_code == 201 and r.json()["created_account"] and r.json()["temporary_password"]
    sup_user_id = r.json()["user_id"]

    sup = api.tenant_user("sup@access.example.com", tid)
    assert sup.groups == [f"/tenants/{tid}/supervisor"]
    assert sup.get("/api/v1/tenant/access/members").status_code == 403  # supervisors cannot administer access
    members = {
        m["email"]: [x["role_key"] for x in m["roles"]] for m in owner.get("/api/v1/tenant/access/members").json()
    }
    assert members["sup@access.example.com"] == ["supervisor"] and members[owner_email(a)] == ["owner"]

    # An existing account (another tenant's owner) is granted a role here without a new account/password.
    b = api.onboard("Other Access", price="1")
    r2 = owner.post(
        "/api/v1/tenant/access/members",
        {"email": owner_email(b), "first_name": "B", "last_name": "O", "role_key": "accountant"},
    )
    assert r2.json()["created_account"] is False and r2.json()["temporary_password"] is None

    after = owner.post(f"/api/v1/tenant/access/members/{sup_user_id}/roles/supervisor/revoke")
    assert after.status_code == 200 and "sup@access.example.com" not in {m["email"] for m in after.json()}
    revoked = Actor(api, sup.subject, sorted(api.idp.memberships[sup.subject]), tid)
    assert revoked.get("/api/v1/tenant/machines").status_code == 403

    owner_id = next(
        m["user_id"] for m in owner.get("/api/v1/tenant/access/members").json() if m["email"] == owner_email(a)
    )
    last = owner.post(f"/api/v1/tenant/access/members/{owner_id}/roles/owner/revoke")
    assert last.json()["error"]["code"] == "LAST_OWNER"

    with get_sessionmaker().begin() as s:  # history retained: revoked membership closed, not deleted
        apply_scope(s, DbScope.SYSTEM, None, None)
        closed = s.execute(
            text(
                "SELECT count(*) FROM tenant_membership WHERE tenant_id = :t AND user_id = :u "
                "AND effective_to IS NOT NULL"
            ),
            {"t": tid, "u": sup_user_id},
        ).scalar_one()
        assert closed == 1


def owner_email(onboarded: dict[str, object]) -> str:
    return str(onboarded["owner_email"])


def _invite(owner: Actor, email: str, role: str = "supervisor") -> str:
    r = owner.post(
        "/api/v1/tenant/access/members",
        {"email": email, "first_name": "Sue", "last_name": "Pervisor", "role_key": role},
    )
    assert r.status_code == 201, r.json()
    return str(r.json()["user_id"])


def _by_email(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(m["email"]): m for m in rows}


def test_owner_edits_deactivates_reactivates_and_resets_passwords(api: Api) -> None:
    a = api.onboard("People Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    sup_id = _invite(owner, "sup@people.example.com")
    sub = api.idp.subject_for("sup@people.example.com")
    base = "/api/v1/tenant/access/members"

    # Another role, then a name correction (the account belongs to this company alone).
    after = owner.post(f"{base}/{sup_id}/roles/accountant").json()
    roles = _by_email(after)["sup@people.example.com"]["roles"]
    assert sorted(r["role_key"] for r in roles) == ["accountant", "supervisor"]
    renamed = owner.put(f"{base}/{sup_id}/name", {"first_name": "Susan", "last_name": "Mwita"})
    assert renamed.status_code == 200
    assert _by_email(renamed.json())["sup@people.example.com"]["display_name"] == "Susan Mwita"
    assert api.idp.names[sub] == ("Susan", "Mwita")

    # Reset: a new one-time password, signed out everywhere.
    reset = owner.post(f"{base}/{sup_id}/reset-password")
    assert reset.status_code == 200 and reset.json()["temporary_password"] == api.idp.passwords[sub]
    assert api.idp.logouts == [sub]

    # Deactivate: roles gone, sign-in disabled and signed out; records stay; listed as inactive.
    deact = owner.post(f"{base}/{sup_id}/deactivate")
    assert deact.status_code == 200
    row = _by_email(deact.json())["sup@people.example.com"]
    assert row["status"] == "INACTIVE" and row["deactivated_at"] is not None
    assert sorted(r["role_key"] for r in row["roles"]) == ["accountant", "supervisor"]
    assert sub in api.idp.disabled and api.idp.memberships[sub] == set() and api.idp.logouts[-1] == sub
    active = owner.get(base).json()
    assert "sup@people.example.com" not in _by_email(active)
    assert "sup@people.example.com" in _by_email(owner.get(base, status="INACTIVE").json())
    stale = Actor(api, sub, [f"/tenants/{tid}/supervisor"], tid)  # a token issued before: refused at once
    assert stale.get("/api/v1/tenant/machines").status_code == 403
    # Inactive: no reset, no extra role, no re-invite; reactivate instead.
    assert owner.post(f"{base}/{sup_id}/reset-password").json()["error"]["code"] == "MEMBER_INACTIVE"
    assert owner.post(f"{base}/{sup_id}/roles/supervisor").json()["error"]["code"] == "MEMBER_INACTIVE"
    react = owner.post(f"{base}/{sup_id}/reactivate")
    assert react.status_code == 200
    row = _by_email(react.json())["sup@people.example.com"]
    assert row["status"] == "ACTIVE"
    assert sorted(r["role_key"] for r in row["roles"]) == ["accountant", "supervisor"]
    assert sub not in api.idp.disabled
    assert api.tenant_user("sup@people.example.com", tid).get("/api/v1/tenant/machines").status_code == 200

    # Adding a deactivated person again also brings them back, with the role given now.
    owner.post(f"{base}/{sup_id}/deactivate")
    assert sub in api.idp.disabled
    again = owner.post(
        base, {"email": "sup@people.example.com", "first_name": "S", "last_name": "M", "role_key": "accountant"}
    )
    assert again.status_code == 201 and again.json()["created_account"] is False
    assert sub not in api.idp.disabled
    row = _by_email(owner.get(base).json())["sup@people.example.com"]
    assert [r["role_key"] for r in row["roles"]] == ["accountant"]


def test_people_management_guards(api: Api) -> None:
    a = api.onboard("Guard Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    base = "/api/v1/tenant/access/members"
    owner_id = next(m["user_id"] for m in owner.get(base).json() if m["email"] == owner_email(a))

    roles = {r["role_key"]: r["carries_approvals"] for r in owner.get("/api/v1/tenant/access/roles").json()}
    assert roles["owner"] is True and roles["supervisor"] is False

    # Never on one's own account.
    assert owner.post(f"{base}/{owner_id}/deactivate").json()["error"]["code"] == "SELF_NOT_ALLOWED"
    assert owner.post(f"{base}/{owner_id}/reset-password").json()["error"]["code"] == "SELF_NOT_ALLOWED"

    # Someone who also belongs to another company: their name and password are not changed from here, and
    # deactivating them here leaves their sign-in (and the other company) alone.
    b = api.onboard("Elsewhere Co", price="1")
    shared_id = _invite(owner, owner_email(b), role="accountant")
    shared_sub = api.idp.subject_for(owner_email(b))
    assert owner.post(f"{base}/{shared_id}/reset-password").json()["error"]["code"] == "ACCOUNT_USED_ELSEWHERE"
    named = owner.put(f"{base}/{shared_id}/name", {"first_name": "X", "last_name": "Y"})
    assert named.json()["error"]["code"] == "ACCOUNT_USED_ELSEWHERE"
    assert owner.post(f"{base}/{shared_id}/deactivate").status_code == 200
    assert shared_sub not in api.idp.disabled and shared_sub not in api.idp.logouts
    assert f"/tenants/{b['tenant']['id']}/owner" in api.idp.memberships[shared_sub]

    # A supervisor cannot manage people; an unknown person is not found.
    _invite(owner, "sup@guard.example.com")
    sup = api.tenant_user("sup@guard.example.com", tid)
    assert sup.post(f"{base}/{owner_id}/deactivate").status_code == 403
    assert owner.post(f"{base}/00000000-0000-4000-8000-000000000000/deactivate").status_code == 404
