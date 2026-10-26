"""Accountability design D: refused attempts are kept as security events and listed; conflicted/rejected offline
operations are reviewed through a controlled, audited process; the accountability dashboard summarises the 3.6
oversight list (tiles configurable per tenant)."""

import uuid
from typing import Any

import pytest

from tests.support.api import Actor, Api
from tests.support.finance import cash_policy, setup_finance, tenant_sql

DEVICE = "android-oversight-01"
T1 = "2026-11-01T07:00:00+00:00"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def test_refused_attempts_are_security_events(api: Api) -> None:
    f = setup_finance(api)
    sup, acct, owner = f.supervisor, f.accountant, f.owner
    assert sup.get("/api/v1/tenant/cash/custody/me").status_code == 200
    assert sup.get("/api/v1/tenant/cash/variances").status_code == 403  # missing tenant.finance.read
    assert sup.get("/api/v1/tenant/security-events").status_code == 403
    # A segregation-of-duties attempt: the recorder tries to verify their own remittance.
    h = _ok(
        acct.post(
            "/api/v1/tenant/cash/handovers",
            {"staff_member_id": f.sup_staff_id, "amount": "100", "handed_at": T1},
        ),
        201,
    )
    sod = acct.post(f"/api/v1/tenant/cash/handovers/{h['id']}/decision", {"verified": True})
    assert sod.status_code == 422 and sod.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"

    events = _ok(owner.get("/api/v1/tenant/security-events"))["items"]
    kinds = {(e["kind"], e["permission"] or e["action"]) for e in events}
    assert ("PERMISSION_DENIED", "tenant.finance.read") in kinds
    assert ("PERMISSION_DENIED", "tenant.security_event.read") in kinds
    assert ("SEGREGATION_OF_DUTIES", "verify") in kinds
    denied = _ok(owner.get("/api/v1/tenant/security-events", kind="PERMISSION_DENIED", q="variances"))["items"]
    assert [e["request_path"] for e in denied] == ["/api/v1/tenant/cash/variances"]
    assert denied[0]["actor_display_name"] is not None
    # The manager template can read them; events are tenant-scoped (RLS) and append-only.
    assert _ok(f.manager.get("/api/v1/tenant/security-events"))["total"] == len(events)
    with pytest.raises(Exception, match=r"not permitted|permission denied"):
        tenant_sql(f.tid, "DELETE FROM security_event")


def test_sync_conflict_review(api: Api) -> None:
    f = setup_finance(api)
    sup, mgr, owner = f.supervisor, f.manager, f.owner
    r = api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.2"}
    )
    assert r.status_code == 201, r.text
    op_id = str(uuid.uuid4())
    push = api.client.post(
        "/api/v1/sync/push",
        headers=_h(sup),
        json={
            "device_now": api.clock.now.isoformat(),
            "operations": [
                {
                    "id": op_id,
                    "op_type": "CASH_TRANSFER_ACKNOWLEDGEMENT",
                    "created_at_device": T1,
                    "payload": {"transfer_id": str(uuid.uuid4()), "acknowledged": True},
                }
            ],
        },
    )
    assert push.json()["results"][0]["status"] == "REJECTED", push.text

    assert sup.get("/api/v1/tenant/sync/conflicts").status_code == 403
    page = _ok(mgr.get("/api/v1/tenant/sync/conflicts", resolved=False))
    assert page["total"] == 1
    item = page["items"][0]
    assert (item["operation_id"], item["status"], item["error_code"], item["device_id"]) == (
        op_id,
        "REJECTED",
        "TRANSFER_NOT_FOUND",
        DEVICE,
    )
    assert item["payload"]["acknowledged"] is True and item["resolution"] is None

    body = {"outcome": "DISMISSED", "reason": "Transfer was never recorded; nothing to apply"}
    # The person who submitted the operation cannot resolve it (supervisor also lacks the permission).
    assert sup.post(f"/api/v1/tenant/sync/conflicts/{op_id}/resolution", body).status_code == 403
    done = _ok(mgr.post(f"/api/v1/tenant/sync/conflicts/{op_id}/resolution", body))
    assert done["resolution"]["outcome"] == "DISMISSED"
    again = mgr.post(f"/api/v1/tenant/sync/conflicts/{op_id}/resolution", body)
    assert again.status_code == 409 and again.json()["error"]["code"] == "SYNC_CONFLICT_ALREADY_RESOLVED"
    assert _ok(mgr.get("/api/v1/tenant/sync/conflicts", resolved=False))["total"] == 0
    assert _ok(mgr.get(f"/api/v1/tenant/sync/conflicts/{op_id}"))["resolution"]["reason"] == body["reason"]
    audit = _ok(owner.get("/api/v1/tenant/audit-events", entity_type="client_operation"))["items"]
    assert [a["action"] for a in audit] == ["sync.operation.dismissed"]
    bad = mgr.post(
        f"/api/v1/tenant/sync/conflicts/{uuid.uuid4()}/resolution",
        {"outcome": "RECAPTURED", "reason": "re-entered", "recaptured_entity_type": "cash_transfer"},
    )
    assert bad.status_code == 422  # entity type and id go together


def test_accountability_summary(api: Api) -> None:
    f = setup_finance(api)
    cash_policy(f, remit_full_balance=True)  # a tenant capability (platform default: off)
    owner, mgr, acct = f.owner, f.manager, f.accountant
    c = "/api/v1/tenant/cash"
    operator = _ok(owner.post("/api/v1/tenant/staff", {"full_name": "Operator Zuberi", "kind": "OPERATOR"}), 201)["id"]
    _ok(
        mgr.post(
            f"{c}/collections",
            {"customer_id": f.customer_id, "amount": "70000", "received_at": T1, "staff_member_id": operator},
        ),
        201,
    )
    _ok(
        mgr.post(
            f"{c}/transfers",
            {"from_staff_id": operator, "to_staff_id": f.sup_staff_id, "amount": "20000", "transferred_at": T1},
        ),
        201,
    )
    _ok(mgr.post(f"{c}/handovers", {"staff_member_id": operator, "amount": "10000", "handed_at": T1}), 201)
    assert f.supervisor.get("/api/v1/tenant/accountability/summary").status_code == 403

    s = _ok(mgr.get("/api/v1/tenant/accountability/summary"))
    cash = s["cash"]
    assert [(r["staff_member_id"], r["outstanding"], r["in_transit_out"]) for r in cash["custodians"]] == [
        (operator, "70000.0000", "20000.0000")
    ]
    assert [(x["count"], x["amount"]) for x in cash["transfers_awaiting_acknowledgement"]] == [(1, "20000.0000")]
    assert [(x["count"], x["amount"]) for x in cash["remittances_awaiting_confirmation"]] == [(1, "10000.0000")]
    assert cash["partial_remittances_in_window"] == 1  # 70,000 held, 20,000 in transit, 10,000 remitted
    assert [(x["count"], x["amount"]) for x in s["payments"]["awaiting_confirmation"]] == [(1, "70000.0000")]
    assert s["unauthorized_attempts"]["permission_denied"] >= 1  # the supervisor's refused call above
    assert s["outstanding_approvals"]["remittances_to_verify"] == 1
    assert s["investigations"] == {"open": 0, "in_review": 0}
    hours = s["customer_hours"]
    assert hours is not None and hours["open_overruns"] == 0 and hours["purchases_by_status"] == {}
    assert s["hours_awaiting_activation"]["count"] == 0
    assert _ok(acct.get("/api/v1/tenant/accountability/summary"))["cash"] is not None

    # Tiles are tenant configuration (OVERSIGHT policy).
    r = owner.post(
        "/api/v1/tenant/policies/OVERSIGHT/versions",
        {"scope": "TENANT", "values": {"hidden_dashboard_tiles": ["cash", "payments"]}, "reason": "Owner view"},
    )
    assert r.status_code == 201, r.text
    hidden = _ok(mgr.get("/api/v1/tenant/accountability/summary"))
    assert (
        hidden["hidden_tiles"] == ["cash", "payments", "revenue_differences"]
        and hidden["cash"] is None
        and hidden["payments"] is None
    )
    assert hidden["discrepancies"] is not None
