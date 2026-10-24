"""Accountability design C (cash custody chain): any active staff member can be a custodian without a login;
recorders record on custodians' behalf per tenant policy; field-to-field transfers move accountability only when
acknowledged (never a company receipt); floats are acknowledged; remittances record the amount actually received;
differences become variances (case above the threshold, resolution, write-off with segregation of duties);
retentions, custody adjustments, reason lists, the full-remittance flag, drill-down and offline operations."""

import uuid
from decimal import Decimal
from typing import Any

import pytest

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, setup_finance, tenant_sql

C = "/api/v1/tenant/cash"
T0 = "2026-11-01T06:00:00+00:00"
T1 = "2026-11-01T07:00:00+00:00"
DEVICE = "android-chain-0001"


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _err(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def _staff(f: FinCtx, name: str, kind: str = "OPERATOR", login: Actor | None = None) -> str:
    body: dict[str, Any] = {"full_name": name, "kind": kind}
    if login is not None:
        body["keycloak_subject"] = login.subject
    return str(_ok(f.owner.post("/api/v1/tenant/staff", body))["id"])


def _held(actor: Actor, staff_id: str) -> dict[str, Decimal]:
    rows = _ok(actor.get(f"{C}/custody", staff_member_id=staff_id), 200)
    row = next(r for r in rows if r["currency"] == "TZS")
    return {k: Decimal(v) for k, v in row.items() if k not in ("staff_member_id", "currency", "as_of")}


def _collect(actor: Actor, f: FinCtx, staff_id: str, amount: str) -> Any:
    body = {"customer_id": f.customer_id, "amount": amount, "received_at": T0, "staff_member_id": staff_id}
    return _ok(actor.post(f"{C}/collections", body))


def test_recorders_and_field_transfers(api: Api) -> None:
    f = setup_finance(api)
    mgr, sup, acct = f.manager, f.supervisor, f.accountant
    operator = _staff(f, "Operator Juma")
    mgr_staff = _staff(f, "Field Manager", "OTHER", login=mgr)

    # Any active staff member is a custodian; the picker shows who has no login.
    found = _ok(mgr.get(f"{C}/custodians", q="juma"), 200)["items"]
    assert [(c["staff_member_id"], c["has_login"]) for c in found] == [(operator, False)]

    # The manager (a recorder) records a collection on the operator's behalf (tenant default allows it).
    paid = _collect(mgr, f, operator, "300000")
    assert paid["received_by_staff_id"] == operator and paid["status"] == "CLAIMED"

    # Operator -> manager, recorded by the manager who is the receiver: that is the acknowledgement, with the
    # amount actually received. The 10,000 difference stays with the operator as an open variance (case opened).
    t = _ok(
        mgr.post(
            f"{C}/transfers",
            {
                "from_staff_id": operator,
                "to_staff_id": mgr_staff,
                "amount": "300000",
                "amount_received": "290000",
                "transferred_at": T1,
            },
        )
    )
    assert (t["status"], t["ack_method"], t["amount_received"]) == (
        "ACKNOWLEDGED",
        "RECORDER_IS_RECEIVER",
        "290000.0000",
    )
    assert _held(acct, operator)["outstanding"] == 10000 and _held(acct, mgr_staff)["outstanding"] == 290000
    v = _ok(acct.get(f"{C}/variances/{t['variance_id']}"), 200)
    assert (v["source_type"], v["staff_member_id"], Decimal(v["amount"]), v["status"]) == (
        "TRANSFER",
        operator,
        Decimal(10000),
        "OPEN",
    )
    assert v["case_id"] is not None  # above the default threshold (0): an investigation case, never a verdict

    # Supervisor -> operator: pending, still in the supervisor's custody (in transit) and not a company receipt.
    sup_staff = f.sup_staff_id
    _collect(sup, f, sup_staff, "80000")
    p = _ok(sup.post(f"{C}/transfers", {"to_staff_id": operator, "amount": "50000", "transferred_at": T1}))
    assert p["status"] == "PENDING_ACKNOWLEDGEMENT" and p["from_staff_id"] == sup_staff
    held = _held(acct, sup_staff)
    assert (held["outstanding"], held["in_transit_out"]) == (Decimal(80000), Decimal(50000))
    assert _held(acct, operator)["in_transit_in"] == 50000
    _err(sup.post(f"{C}/transfers/{p['id']}/acknowledgement", {"acknowledged": True}), 422, "SEGREGATION_OF_DUTIES")
    acked = _ok(mgr.post(f"{C}/transfers/{p['id']}/acknowledgement", {"acknowledged": True}), 200)
    assert (acked["status"], acked["ack_method"], acked["variance_id"]) == ("ACKNOWLEDGED", "ON_BEHALF", None)
    assert _held(acct, sup_staff)["outstanding"] == 30000 and _held(acct, operator)["outstanding"] == 60000
    _err(mgr.post(f"{C}/transfers/{p['id']}/acknowledgement", {"acknowledged": True}), 409, "TRANSFER_ALREADY_DECIDED")

    # A disputed transfer moves nothing and records the difference against the sender.
    d = _ok(sup.post(f"{C}/transfers", {"to_staff_id": mgr_staff, "amount": "20000", "transferred_at": T1}))
    disputed = _ok(mgr.post(f"{C}/transfers/{d['id']}/acknowledgement", {"acknowledged": False, "note": "none"}), 200)
    assert (disputed["status"], disputed["ack_method"]) == ("DISPUTED", "RECEIVER")
    assert _held(acct, sup_staff)["outstanding"] == 30000
    dv = _ok(acct.get(f"{C}/variances/{disputed['variance_id']}"), 200)
    assert (dv["staff_member_id"], Decimal(dv["received_amount"])) == (sup_staff, Decimal(0))

    # Recorders see the transfers; the receiver's list filter works.
    listed = _ok(mgr.get(f"{C}/transfers", staff_member_id=mgr_staff), 200)
    assert {x["id"] for x in listed["items"]} == {t["id"], d["id"]}

    # Tenant switches recording-for-others off: field users move only their own custody / their own transfers.
    cash_policy(f, recorders_may_record_for_others=False)
    body = {"customer_id": f.customer_id, "amount": "1", "received_at": T0, "staff_member_id": operator}
    _err(sup.post(f"{C}/collections", body), 403, "NOT_CUSTODIAN")
    _err(
        sup.post(
            f"{C}/transfers", {"from_staff_id": operator, "to_staff_id": mgr_staff, "amount": "1", "transferred_at": T1}
        ),
        403,
        "NOT_CUSTODIAN",
    )
    # ... and without receiver acknowledgement, a transfer counts at the declared amount when recorded.
    cash_policy(f, transfer_ack_required=False)
    auto = _ok(sup.post(f"{C}/transfers", {"to_staff_id": mgr_staff, "amount": "10000", "transferred_at": T1}))
    assert (auto["status"], auto["ack_method"]) == ("ACKNOWLEDGED", "NOT_REQUIRED")
    assert _held(acct, sup_staff)["outstanding"] == 20000


def test_float_acknowledgement(api: Api) -> None:
    f = setup_finance(api)
    acct, acct2 = f.accountant, f.accountant2
    operator = _staff(f, "Operator Asha")
    cash_policy(f, float_ack_required=True)  # a tenant capability (platform default: off)
    fl = _ok(acct.post(f"{C}/floats", {"staff_member_id": operator, "amount": "100000"}))
    assert (fl["ack_required"], fl["ack_status"]) == (True, "PENDING")
    held = _held(acct, operator)
    assert (held["outstanding"], held["pending_floats"]) == (Decimal(0), Decimal(100000))
    waiting = _ok(acct.get(f"{C}/floats", awaiting_acknowledgement=True), 200)
    assert [x["id"] for x in waiting["items"]] == [fl["id"]]
    # The issuer cannot confirm receipt on the receiver's behalf.
    _err(acct.post(f"{C}/floats/{fl['id']}/acknowledgement", {"acknowledged": True}), 422, "SEGREGATION_OF_DUTIES")
    done = _ok(
        acct2.post(f"{C}/floats/{fl['id']}/acknowledgement", {"acknowledged": True, "amount_received": "95000"}), 200
    )
    assert (done["ack_status"], done["amount_received"]) == ("ACKNOWLEDGED", "95000.0000")
    assert _held(acct, operator)["outstanding"] == 95000
    v = _ok(acct.get(f"{C}/variances", source_type="FLOAT"), 200)["items"]
    assert [(x["staff_member_id"], x["counterparty_staff_id"], Decimal(x["amount"])) for x in v] == [
        (None, operator, Decimal(5000))
    ]
    _err(
        acct2.post(f"{C}/floats/{fl['id']}/acknowledgement", {"acknowledged": True}), 409, "FLOAT_ALREADY_ACKNOWLEDGED"
    )
    # Tenant without float acknowledgement: counted when issued (pre-existing behaviour, the platform default).
    cash_policy(f)
    legacy = _ok(acct.post(f"{C}/floats", {"staff_member_id": operator, "amount": "5000"}))
    assert legacy["ack_status"] == "NOT_REQUIRED" and _held(acct, operator)["outstanding"] == 100000
    _err(
        acct2.post(f"{C}/floats/{legacy['id']}/acknowledgement", {"acknowledged": True}), 422, "FLOAT_ACK_NOT_REQUIRED"
    )


def test_remittance_received_amount_partial_flag_retention_and_writeoff(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct, acct2 = f.manager, f.accountant, f.accountant2
    operator = _staff(f, "Operator Baraka")
    _collect(mgr, f, operator, "200000")

    # Remitting less than the expected balance without an approved retention is flagged (not refused).
    h1 = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "100000", "handed_at": T1}))
    assert (Decimal(h1["expected_balance"]), Decimal(h1["partial_shortfall"])) == (Decimal(200000), Decimal(100000))

    # A retention is requested by a recorder and approved by someone else holding the approval permission.
    r = _ok(mgr.post(f"{C}/retentions", {"staff_member_id": operator, "amount": "50000", "reason": "Fuel float"}))
    _err(mgr.post(f"{C}/retentions/{r['id']}/decision", {"approve": True}), 403, "PERMISSION_DENIED")
    assert _ok(acct.post(f"{C}/retentions/{r['id']}/decision", {"approve": True}), 200)["status"] == "APPROVED"
    assert _held(acct, operator)["approved_retention"] == 50000
    h2 = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "50000", "handed_at": T1}))
    assert h2["partial_shortfall"] is None  # 200,000 - 100,000 claimed - 50,000 - 50,000 retained

    # The office records what it actually counted; older clients send no amount (= the declared amount).
    v1 = _ok(acct2.post(f"{C}/handovers/{h1['id']}/decision", {"verified": True, "amount_received": "90000"}), 200)
    assert v1["amount_received"] == "90000.0000"
    v2 = _ok(acct.post(f"{C}/handovers/{h2['id']}/decision", {"verified": True}), 200)
    assert v2["amount_received"] == "50000.0000"
    assert _held(acct, operator)["outstanding"] == 60000  # 200,000 - 90,000 - 50,000
    variance = _ok(acct.get(f"{C}/variances", source_type="REMITTANCE"), 200)["items"][0]
    assert (variance["staff_member_id"], Decimal(variance["amount"])) == (operator, Decimal(10000))

    # Reasons are the tenant's own list; once it has one, a reason must be chosen.
    reason = _ok(f.owner.post(f"{C}/reasons", {"kind": "WRITE_OFF", "label": "Counting loss"}))
    _err(
        acct.post(f"{C}/variances/{variance['id']}/write-off-proposal", {"note": "Lost in counting"}),
        422,
        "REASON_REQUIRED",
    )
    # Write-off approval is required by default: direct write-off is refused, proposal + independent approval.
    _err(
        acct.post(f"{C}/variances/{variance['id']}/resolution", {"outcome": "WRITTEN_OFF", "note": "lost"}),
        422,
        "WRITEOFF_APPROVAL_REQUIRED",
    )
    proposed = _ok(
        acct.post(
            f"{C}/variances/{variance['id']}/write-off-proposal",
            {"note": "Lost in counting", "reason_id": reason["id"]},
        ),
        200,
    )
    assert proposed["status"] == "WRITE_OFF_PROPOSED"
    _err(
        acct.post(f"{C}/variances/{variance['id']}/write-off-decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES"
    )
    _err(mgr.post(f"{C}/variances/{variance['id']}/write-off-decision", {"approve": True}), 403, "PERMISSION_DENIED")
    done = _ok(acct2.post(f"{C}/variances/{variance['id']}/write-off-decision", {"approve": True}), 200)
    assert (done["status"], done["outcome"]) == ("RESOLVED", "WRITTEN_OFF")
    assert _held(acct, operator)["outstanding"] == 50000  # the written-off difference leaves custody

    # Every reconciliation figure drills down to its transactions.
    def drill(figure: str) -> list[dict[str, Any]]:
        q = {"staff_member_id": operator, "from": "2026-11-01", "to": "2026-11-01", "figure": figure}
        return list(_ok(acct.get(f"{C}/reconciliation/transactions", **q), 200)["items"])

    assert [(x["entity_type"], Decimal(x["amount"])) for x in drill("written_off")] == [
        ("cash_variance", Decimal(10000))
    ]
    assert sorted(Decimal(x["amount"]) for x in drill("verified_handovers")) == [Decimal(50000), Decimal(90000)]
    assert [x["entity_id"] for x in drill("collections")] != []
    day = _ok(
        acct.get(f"{C}/reconciliation", staff_member_id=operator, **{"from": "2026-11-01", "to": "2026-11-01"}), 200
    )["days"][0]
    assert (Decimal(day["written_off"]), Decimal(day["verified_handovers"]), Decimal(day["outstanding"])) == (
        Decimal(10000),
        Decimal(140000),
        Decimal(50000),
    )

    # Tenants that do not require write-off approval let a write-off holder resolve directly (not their own record).
    cash_policy(f, writeoff_requires_approval=False)
    h3 = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "10000", "handed_at": T1}))
    _ok(acct.post(f"{C}/handovers/{h3['id']}/decision", {"verified": True, "amount_received": "9000"}), 200)
    v3 = next(x for x in _ok(acct.get(f"{C}/variances", status="OPEN"), 200)["items"] if x["source_id"] == h3["id"])
    body = {"outcome": "WRITTEN_OFF", "note": "small loss", "reason_id": reason["id"]}
    _err(acct.post(f"{C}/variances/{v3['id']}/resolution", body), 422, "SEGREGATION_OF_DUTIES")
    assert _ok(acct2.post(f"{C}/variances/{v3['id']}/resolution", body), 200)["outcome"] == "WRITTEN_OFF"
    # Rejected remittances carry no received amount.
    h4 = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "1000", "handed_at": T1}))
    _err(
        acct.post(f"{C}/handovers/{h4['id']}/decision", {"verified": False, "amount_received": "1"}),
        422,
        "AMOUNT_RECEIVED_INVALID",
    )
    # Retention is a capability: off => no retention may be requested.
    cash_policy(f, retention_allowed=False)
    _err(
        mgr.post(f"{C}/retentions", {"staff_member_id": operator, "amount": "1", "reason": "keep"}),
        422,
        "RETENTION_NOT_ALLOWED",
    )


def test_variance_resolution_reasons_and_adjustments(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct, acct2 = f.manager, f.accountant, f.accountant2
    operator = _staff(f, "Operator Neema")
    _collect(mgr, f, operator, "40000")
    h = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "40000", "handed_at": T1}))
    _ok(acct.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "amount_received": "41000"}), 200)
    v = _ok(acct.get(f"{C}/variances"), 200)["items"][0]
    assert Decimal(v["amount"]) == -1000  # more received than declared: still a difference to explain

    reason = _ok(acct.post(f"{C}/reasons", {"kind": "VARIANCE", "label": "Counting error"}))
    _err(
        acct.post(f"{C}/variances/{v['id']}/resolution", {"outcome": "CORRECTED_ERROR", "note": "recount"}),
        422,
        "REASON_REQUIRED",
    )
    wrong_kind = _ok(acct.post(f"{C}/reasons", {"kind": "RETENTION", "label": "Working float"}))
    body = {"outcome": "CORRECTED_ERROR", "note": "recount", "reason_id": wrong_kind["id"]}
    _err(acct.post(f"{C}/variances/{v['id']}/resolution", body), 422, "REASON_INVALID")
    body["reason_id"] = reason["id"]
    resolved = _ok(acct.post(f"{C}/variances/{v['id']}/resolution", body), 200)
    assert (resolved["status"], resolved["outcome"]) == ("RESOLVED", "CORRECTED_ERROR")
    _err(acct.post(f"{C}/variances/{v['id']}/resolution", body), 409, "VARIANCE_NOT_OPEN")

    # Reason list lifecycle: edit, deactivate (hidden by default), reactivate; duplicates refused.
    _err(acct.post(f"{C}/reasons", {"kind": "VARIANCE", "label": "counting ERROR"}), 409, "DUPLICATE_REASON")
    edited = _ok(acct.patch(f"{C}/reasons/{reason['id']}", {"label": "Counting mistake"}), 200)
    assert edited["label"] == "Counting mistake"
    _ok(acct.post(f"{C}/reasons/{reason['id']}/deactivate", {"reason": "merged"}), 200)
    assert _ok(mgr.get(f"{C}/reasons", kind="VARIANCE"), 200)["total"] == 0
    assert _ok(mgr.get(f"{C}/reasons", kind="VARIANCE", include_inactive=True), 200)["total"] == 1
    _ok(acct.post(f"{C}/reasons/{reason['id']}/reactivate", {"reason": "needed"}), 200)

    # Custody corrections: proposed with a reason, counted only once approved by someone else.
    adj = _ok(
        acct.post(
            f"{C}/adjustments",
            {"staff_member_id": operator, "kind": "ADJUSTMENT", "amount": "1000", "reason": "Recount surplus returned"},
        )
    )
    assert _held(acct, operator)["outstanding"] == -1000  # 40,000 - 41,000 received
    _err(acct.post(f"{C}/adjustments/{adj['id']}/decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES")
    _err(
        mgr.post(
            f"{C}/adjustments", {"staff_member_id": operator, "kind": "ADJUSTMENT", "amount": "1", "reason": "x y z"}
        ),
        403,
        "PERMISSION_DENIED",
    )
    assert _ok(acct2.post(f"{C}/adjustments/{adj['id']}/decision", {"approve": True}), 200)["status"] == "APPROVED"
    assert _held(acct, operator)["outstanding"] == 0
    rev = acct.post(
        f"{C}/adjustments", {"staff_member_id": operator, "kind": "REVERSAL", "amount": "-5", "reason": "undo it"}
    )
    assert rev.status_code == 422  # a reversal names the record it reverses
    _err(
        acct.post(
            f"{C}/adjustments",
            {
                "staff_member_id": operator,
                "kind": "REVERSAL",
                "amount": "-5",
                "reason": "undo it",
                "reverses_entity_type": "cash_handover",
                "reverses_entity_id": str(uuid.uuid4()),
            },
        ),
        404,
        "REVERSED_RECORD_NOT_FOUND",
    )
    listed = _ok(acct.get(f"{C}/adjustments", staff_member_id=operator), 200)
    assert [a["status"] for a in listed["items"]] == ["APPROVED"]


def test_remittance_decision_columns_frozen_by_trigger(api: Api) -> None:
    f = setup_finance(api)
    _collect(f.manager, f, f.sup_staff_id, "10000")
    h = _ok(f.supervisor.post(f"{C}/handovers", {"amount": "10000", "handed_at": T1}))
    _ok(f.accountant.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "amount_received": "9000"}), 200)
    for sql in (
        "UPDATE cash_handover SET amount_received = 10000 WHERE id = :i",
        "UPDATE cash_handover SET amount = 9000 WHERE id = :i",
        "UPDATE cash_variance SET amount = 1 WHERE source_id = :i",
        "DELETE FROM cash_variance WHERE source_id = :i",
    ):
        with pytest.raises(Exception, match=r"immutable|not permitted|permission denied"):
            tenant_sql(f.tid, sql, i=h["id"])


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _push(api: Api, actor: Actor, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": ops}
    )
    assert r.status_code == 200, r.text
    return list(r.json()["results"])


def _op(op_type: str, payload: dict[str, Any], op_id: str | None = None) -> dict[str, Any]:
    return {
        "id": op_id or str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": T1,
        "depends_on": [],
    }


def test_offline_transfer_and_acknowledgement(api: Api) -> None:
    f = setup_finance(api)
    sup, mgr, acct = f.supervisor, f.manager, f.accountant
    operator = _staff(f, "Operator Saidi")
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(sup),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.2.0"},
    )
    assert r.status_code == 201, r.text
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    assert "OP_CASH_TRANSFER" in boot["capabilities"]

    client_id = str(uuid.uuid4())
    op = _op("CASH_TRANSFER", {"client_id": client_id, "to_staff_id": operator, "amount": "7000", "transferred_at": T1})
    first = _push(api, sup, [op])[0]
    assert first["status"] == "ACKED", first
    assert _push(api, sup, [op])[0]["status"] == "DUPLICATE"
    transfer = first["result"]["entity"]
    assert transfer["status"] == "PENDING_ACKNOWLEDGEMENT"

    # A transfer to the supervisor, recorded by the manager for the operator, acknowledged from the device.
    _collect(mgr, f, operator, "9000")
    incoming = _ok(
        mgr.post(
            f"{C}/transfers",
            {"from_staff_id": operator, "to_staff_id": f.sup_staff_id, "amount": "9000", "transferred_at": T1},
        )
    )
    ack = _push(
        api,
        sup,
        [
            _op(
                "CASH_TRANSFER_ACKNOWLEDGEMENT",
                {"transfer_id": incoming["id"], "acknowledged": True, "amount_received": "8500"},
            )
        ],
    )[0]
    assert ack["status"] == "ACKED" and ack["result"]["entity"]["ack_method"] == "RECEIVER", ack
    again = _push(
        api, sup, [_op("CASH_TRANSFER_ACKNOWLEDGEMENT", {"transfer_id": incoming["id"], "acknowledged": True})]
    )[0]
    assert (again["status"], again["error"]["code"]) == ("CONFLICT", "TRANSFER_ALREADY_DECIDED")
    assert _held(acct, f.sup_staff_id)["outstanding"] == 8500

    # Floats can be acknowledged offline too (tenants that require float acknowledgement).
    cash_policy(f, float_ack_required=True)
    fl = _ok(acct.post(f"{C}/floats", {"staff_member_id": f.sup_staff_id, "amount": "3000"}))
    fa = _push(api, sup, [_op("CASH_FLOAT_ACKNOWLEDGEMENT", {"entry_id": fl["id"], "acknowledged": True})])[0]
    assert fa["status"] == "ACKED" and fa["result"]["entity"]["ack_status"] == "ACKNOWLEDGED", fa
    assert _held(acct, f.sup_staff_id)["outstanding"] == 11500
