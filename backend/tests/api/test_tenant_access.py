"""R1-B tenant user/role administration via Keycloak (authoritative) with an effective-dated membership mirror."""

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
