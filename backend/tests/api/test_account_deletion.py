"""Personal account deletion (`POST /api/v1/me/account-deletion`, web and phone apps): the login is disabled and
deleted, memberships closed, the person's name and email anonymised for good (a token issued before the deletion
neither works nor restores them), the linked staff record keeps its role history without the phone number, records the
person made stay attributed to the anonymised user, the phones' sync sessions are revoked (wipe), and the company's
user managers are told. Refused for the last owner of a company (LAST_OWNER) and for platform staff."""

from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import setup_finance
from tests.support.notify import drain, member, sql, user_id

DELETE = "/api/v1/me/account-deletion"
DEVICE = "android-account-deletion"


def _expense(f: Any, api: Api) -> str:
    cat = f.owner.post("/api/v1/tenant/expense-categories", {"code": "FUEL", "name": "Fuel"})
    assert cat.status_code == 201, cat.text
    policy = f.owner.post(
        "/api/v1/tenant/policies/EXPENSE_CAPTURE/versions",
        {"scope": "TENANT", "values": {"gps_required": False, "receipt_required_above": "1000000"}, "reason": "Test"},
    )
    assert policy.status_code == 201, policy.text
    r = f.supervisor.post(
        "/api/v1/tenant/expenses",
        {
            "category_id": cat.json()["id"],
            "description": "Diesel",
            "amount": "500",
            "incurred_at": api.clock.now.isoformat(),
            "paid_from": "CASH_CUSTODY",
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_user_deletes_own_account(api: Api) -> None:
    f = setup_finance(api, "Person Hire", "PERS-1")
    tid = f.tid
    # The supervisor as a real Keycloak user of the company (in the membership mirror), with a staff phone and a phone.
    sup: Actor = member(api, tid, "supervisor", f.supervisor.subject)
    sql("UPDATE staff_member SET phone = '+255700000001' WHERE id = :i", i=f.sup_staff_id)
    expense_id = _expense(f, api)
    reg = api.client.post(
        "/api/v1/sync/devices",
        headers={**sup.headers(True, None), "X-Device-Id": DEVICE},
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.0.0"},
    )
    assert reg.status_code == 201, reg.text
    uid = user_id(sup.subject)

    assert sup.post(DELETE, {"confirm": False}).status_code == 422
    assert sup.post(DELETE, {}).status_code == 422
    r = sup.post(DELETE, {"confirm": True, "reason": "Leaving the company"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == str(uid) and body["display_name"] == f"Former user {uid.hex[:8]}"
    assert body["companies"] == ["Person Hire"]

    # Login gone; name and email anonymised; memberships closed.
    assert sup.subject in api.idp.deleted and sup.subject not in api.idp.users
    user = sql("SELECT display_name, email, is_active, deleted_at FROM app_user WHERE id = :u", u=uid)[0]
    assert user.display_name.startswith("Former user ") and user.email.endswith("@deleted.invalid")
    assert user.is_active is False and user.deleted_at is not None
    assert not sql("SELECT 1 FROM tenant_membership WHERE user_id = :u AND effective_to IS NULL", u=uid)
    # A token issued before the deletion is refused and does not bring the name back.
    refused = sup.get("/api/v1/tenant/jobs")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "USER_INACTIVE"
    assert sup.get("/api/v1/me").json()["error"]["code"] == "USER_INACTIVE"
    assert sql("SELECT display_name FROM app_user WHERE id = :u", u=uid)[0][0].startswith("Former user ")
    # The staff record keeps its role history without contact details; the records the person made stay theirs.
    staff = sql("SELECT full_name, kind, phone FROM staff_member WHERE id = :i", i=f.sup_staff_id)[0]
    assert staff.kind == "SUPERVISOR" and staff.phone is None
    assert sql("SELECT submitted_by FROM expense WHERE id = :i", i=expense_id)[0][0] == uid
    # The phone's sync session is revoked: its next call answers the wipe instruction.
    assert sql("SELECT status FROM device_session WHERE user_id = :u", u=uid)[0][0] == "REVOKED"
    # Audited, and the company's user managers are told.
    actions = {r[0] for r in sql("SELECT action FROM audit_event WHERE entity_id = :u", u=str(uid))}
    assert {"identity.account.deleted", "platform.account.deleted"} <= actions
    drain(api)
    told = sql(
        "SELECT recipient_user_id, body FROM notification WHERE notification_type = 'ACCOUNT_DELETED' AND tenant_id = :t",
        t=tid,
    )
    assert user_id(f.owner.subject) in {t[0] for t in told}
    assert all("can no longer sign in" in t[1] for t in told)
    # Deleting again: the account is already gone.
    assert sup.post(DELETE, {"confirm": True}).status_code == 403


def test_last_owner_must_close_the_company_or_hand_over(api: Api) -> None:
    t = api.onboard("Owner Hire", price="1000")
    api.activate(t)
    owner: Actor = t["owner"]
    tid = t["tenant"]["id"]
    refused = owner.post(DELETE, {"confirm": True})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "LAST_OWNER"
    assert "Owner Hire" in refused.json()["error"]["message"]
    assert owner.subject in api.idp.users  # nothing happened
    member(api, tid, "owner", "second-owner")
    done = owner.post(DELETE, {"confirm": True})
    assert done.status_code == 200, done.text
    assert owner.subject in api.idp.deleted


def test_platform_staff_use_the_platform_process(api: Api) -> None:
    r = api.platform.post(DELETE, {"confirm": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "PLATFORM_ACCOUNT"
