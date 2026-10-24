"""Gate 5 / prompt.md §10 #8: supervisor cash collections minus VERIFIED handovers and APPROVED expenses reconcile
correctly over several tenant-local days; claimed-unverified handovers and pending expenses are shown separately
and never reduce accountability; verification is segregated from recording."""

from decimal import Decimal
from typing import Any

from tests.support.api import Api
from tests.support.finance import FinCtx, cash_policy, category, expense_policy, setup_finance

C = "/api/v1/tenant/cash"


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _recon(f: FinCtx) -> list[dict[str, Any]]:
    body = _ok(
        f.accountant.get(
            f"{C}/reconciliation", staff_member_id=f.sup_staff_id, **{"from": "2026-11-01", "to": "2026-11-03"}
        ),
        200,
    )
    assert body["timezone"] == "Africa/Dar_es_Salaam" and body["currency"] == "TZS"
    return [{k: (v if k == "day" else Decimal(v)) for k, v in d.items()} for d in body["days"]]


def _verify(actor: Any, handover_id: str, ok: bool = True) -> Any:
    return actor.post(f"{C}/handovers/{handover_id}/decision", {"verified": ok, "note": "counted at office"})


def test_multi_day_cash_reconciliation_with_claimed_handovers(api: Api) -> None:
    f = setup_finance(api)
    sup, acct = f.supervisor, f.accountant
    # The pre-existing custody behaviour is what a tenant gets with the custody-chain capabilities switched off:
    # floats count when issued, and field recorders move only their own custody.
    cash_policy(f, float_ack_required=False, recorders_may_record_for_others=False)
    misc = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="50000")

    def spend(amount: str, at: str) -> Any:
        body = {
            "category_id": misc,
            "description": "spares",
            "amount": amount,
            "incurred_at": at,
            "machine_id": f.c.t.machine_id,
            "paid_from": "CASH_CUSTODY",
        }
        return _ok(sup.post("/api/v1/tenant/expenses", body))

    def collect(amount: str, at: str) -> Any:
        return _ok(sup.post(f"{C}/collections", {"customer_id": f.customer_id, "amount": amount, "received_at": at}))

    def handover(amount: str, at: str) -> Any:
        return _ok(sup.post(f"{C}/handovers", {"amount": amount, "handed_at": at, "reference": "office safe"}))

    assert sup.post(f"{C}/floats", {"staff_member_id": f.sup_staff_id, "amount": "1"}).status_code == 403
    # Day 1 (tenant local 2026-11-01, UTC+3)
    _ok(
        acct.post(
            f"{C}/floats",
            {
                "staff_member_id": f.sup_staff_id,
                "amount": "100000",
                "occurred_at": "2026-11-01T06:00:00+00:00",
                "reference": "PETTY-1",
            },
        )
    )
    c1 = collect("500000", "2026-11-01T08:00:00+00:00")
    assert _ok(f.accountant2.post(f"/api/v1/tenant/customer-payments/{c1['id']}/decision", {"verified": True}), 200)
    a = spend("30000", "2026-11-01T10:00:00+00:00")
    b = spend("120000", "2026-11-01T11:00:00+00:00")
    assert (a["status"], b["status"]) == ("APPROVED", "PENDING_APPROVAL")
    h1 = handover("400000", "2026-11-01T15:00:00+00:00")
    assert h1["status"] == "CLAIMED" and h1["staff_member_id"] == f.sup_staff_id

    day1 = _recon(f)[0]
    assert (day1["approved_spending"], day1["pending_spending"]) == (Decimal(30000), Decimal(120000))
    assert (day1["verified_handovers"], day1["claimed_unverified_handovers"]) == (0, Decimal(400000))
    assert day1["outstanding"] == Decimal(570000)  # claims do not reduce accountability
    assert day1["outstanding_if_claims_verified"] == Decimal(170000)

    # Day 2: the office verifies H1 and approves expense B; more cash collected; H2 handed over but not verified.
    assert _verify(sup, h1["id"]).status_code == 403
    assert _ok(_verify(acct, h1["id"]), 200)["status"] == "VERIFIED"
    assert _verify(f.accountant2, h1["id"]).json()["error"]["code"] == "HANDOVER_ALREADY_DECIDED"
    _ok(f.manager.post(f"/api/v1/tenant/approvals/{b['approval_request_id']}/decision", {"approve": True}), 200)
    collect("200000", "2026-11-02T07:00:00+00:00")  # claimed, not yet verified by the office
    h2 = handover("150000", "2026-11-02T14:00:00+00:00")

    # Day 3 (local): a handover recorded by the office on the supervisor's behalf at 01:30 local, then rejected;
    # an expense rejected. Neither counts.
    other = _ok(f.owner.post("/api/v1/tenant/staff", {"full_name": "Other Supervisor", "kind": "SUPERVISOR"}))
    foreign = sup.post(
        f"{C}/handovers", {"staff_member_id": other["id"], "amount": "1", "handed_at": "2026-11-02T10:00:00+00:00"}
    )
    assert foreign.status_code == 403 and foreign.json()["error"]["code"] == "NOT_CUSTODIAN"
    h3 = _ok(
        acct.post(
            f"{C}/handovers",
            {"staff_member_id": f.sup_staff_id, "amount": "60000", "handed_at": "2026-11-02T22:30:00+00:00"},
        )
    )
    sod = _verify(acct, h3["id"])
    assert sod.status_code == 422 and sod.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    assert _ok(_verify(f.accountant2, h3["id"], ok=False), 200)["status"] == "REJECTED"
    c = spend("70000", "2026-11-03T08:00:00+00:00")
    _ok(f.manager.post(f"/api/v1/tenant/approvals/{c['approval_request_id']}/decision", {"approve": False}), 200)

    d1, d2, d3 = _recon(f)
    assert (d1["opening"], d1["floats_issued"], d1["collections"]) == (0, Decimal(100000), Decimal(500000))
    assert (d1["approved_spending"], d1["verified_handovers"], d1["outstanding"]) == (
        Decimal(150000),
        Decimal(400000),
        Decimal(50000),  # 0 + 100,000 + 500,000 - 150,000 - 400,000
    )
    assert (d1["claimed_unverified_handovers"], d1["pending_spending"]) == (0, 0)
    assert (d2["opening"], d2["collections"], d2["unverified_collections"]) == (
        Decimal(50000),
        Decimal(200000),
        Decimal(200000),
    )
    assert (d2["outstanding"], d2["claimed_unverified_handovers"], d2["outstanding_if_claims_verified"]) == (
        Decimal(250000),
        Decimal(150000),
        Decimal(100000),
    )
    assert (d3["opening"], d3["verified_handovers"], d3["approved_spending"], d3["outstanding"]) == (
        Decimal(250000),
        0,
        0,
        Decimal(250000),
    )
    assert d3["outstanding_if_claims_verified"] == Decimal(100000)  # H2 still claimed (cumulative)

    mine = _ok(sup.get(f"{C}/custody/me"), 200)
    assert [(m["currency"], Decimal(m["outstanding"]), Decimal(m["claimed_unverified_handovers"])) for m in mine] == [
        ("TZS", Decimal(250000), Decimal(150000))
    ]
    assert (
        sup.get(
            f"{C}/reconciliation", staff_member_id=f.sup_staff_id, **{"from": "2026-11-01", "to": "2026-11-01"}
        ).status_code
        == 403
    )
    claimed = _ok(acct.get(f"{C}/handovers", status="CLAIMED"), 200)
    assert [h["id"] for h in claimed["items"]] == [h2["id"]]
