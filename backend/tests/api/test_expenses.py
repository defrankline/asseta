"""Gate 5 (R1-G): field expenses under the versioned EXPENSE_CAPTURE policy — receipt and GPS enforcement,
auto-approval under the limit (policy version stamped), human approval above it with segregation of duties —
and fuel purchase/issue/usage events with cost attribution."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, category, expense_policy, gps, setup_finance, tenant_sql
from tests.support.jobs import unique_jpeg

E = "/api/v1/tenant/expenses"


def _receipt(api: Api, actor: Actor) -> str:
    r = api.client.post(
        "/api/v1/tenant/expense-receipts",
        headers=actor.headers(True, None),
        files={"file": ("receipt.jpg", unique_jpeg(), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _expense(api: Api, f: FinCtx, cat: str, amount: str, **kw: Any) -> dict[str, Any]:
    body = {
        "category_id": cat,
        "description": "Hydraulic hose",
        "supplier": "Kariakoo Spares",
        "amount": amount,
        "incurred_at": api.clock.now.isoformat(),
        "job_id": f.c.job_id,
        "paid_from": "CASH_CUSTODY",
        "gps": gps(api.clock.now),
        **kw,
    }
    return {k: v for k, v in body.items() if v is not None}


def test_expense_policy_receipts_gps_auto_approval_and_segregation(api: Api) -> None:
    f = setup_finance(api)
    repair = category(f, "REPAIR", "Repairs & spares")
    assert f.owner.post("/api/v1/tenant/expense-categories", {"code": "REPAIR", "name": "x"}).status_code == 409
    assert f.supervisor.post("/api/v1/tenant/expense-categories", {"code": "X", "name": "x"}).status_code == 403
    expense_policy(f, receipt_required_above="50000", gps_max_accuracy_m=50.0, auto_approve_limit="100000")
    sup = f.supervisor

    small = sup.post(E, _expense(api, f, repair, "30000"))
    assert small.status_code == 201, small.text
    s = small.json()
    assert (s["status"], s["approval_request_id"], s["receipt_required"]) == ("APPROVED", None, False)
    assert s["policy_version"] == "EXPENSE_CAPTURE@P1.T1" and s["custodian_staff_id"] == f.sup_staff_id
    assert s["machine_id"] == f.c.t.machine_id  # attributed through the job

    no_receipt = sup.post(E, _expense(api, f, repair, "80000"))
    assert no_receipt.status_code == 422 and no_receipt.json()["error"]["code"] == "RECEIPT_REQUIRED"
    rec = _receipt(api, sup)
    vague = sup.post(E, _expense(api, f, repair, "80000", receipt_attachment_ids=[rec], gps=gps(api.clock.now, 200)))
    assert vague.json()["error"]["code"] == "GPS_REQUIRED"
    no_fix = sup.post(
        E, {**_expense(api, f, repair, "80000", receipt_attachment_ids=[rec]), "gps": {"status": "TIMEOUT"}}
    )
    assert no_fix.json()["error"]["code"] == "GPS_REQUIRED"
    ok = sup.post(E, _expense(api, f, repair, "80000", receipt_attachment_ids=[rec])).json()
    assert ok["status"] == "APPROVED" and ok["receipt_attachment_ids"] == [rec] and ok["latitude"] == -6.8
    url = f.accountant.get(f"{E}/{ok['id']}/receipts/{rec}/url")
    assert url.status_code == 200 and url.json()["url"]
    mismatch = sup.post(E, _expense(api, f, repair, "100", machine_id=str(uuid.uuid4())))
    assert mismatch.json()["error"]["code"] == "ATTRIBUTION_MISMATCH"

    big = sup.post(E, _expense(api, f, repair, "250000", receipt_attachment_ids=[_receipt(api, sup)])).json()
    assert big["status"] == "PENDING_APPROVAL" and big["approval_request_id"]
    owner_big = f.owner.post(
        E,
        _expense(api, f, repair, "300000", paid_from="COMPANY", receipt_attachment_ids=[_receipt(api, f.owner)]),
    ).json()
    assert owner_big["custodian_staff_id"] is None
    usd = sup.post(E, _expense(api, f, repair, "10", currency="USD", receipt_attachment_ids=[rec])).json()
    assert (usd["status"], usd["receipt_required"]) == ("PENDING_APPROVAL", True)  # no implicit FX: always reviewed

    pending = f.manager.get("/api/v1/tenant/approvals", status="PENDING").json()
    assert {a["subject_id"] for a in pending["items"]} == {big["id"], owner_big["id"], usd["id"]}
    decide = "/api/v1/tenant/approvals/{}/decision"
    assert sup.post(decide.format(big["approval_request_id"]), {"approve": True}).status_code == 403
    own = f.owner.post(decide.format(owner_big["approval_request_id"]), {"approve": True})
    assert own.status_code == 422 and own.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    approved = f.manager.post(decide.format(owner_big["approval_request_id"]), {"approve": True, "note": "ok"})
    assert approved.json()["status"] == "APPROVED"
    rejected = f.owner.post(decide.format(big["approval_request_id"]), {"approve": False, "note": "no quote"})
    assert rejected.json()["status"] == "REJECTED"
    again = f.manager.post(decide.format(big["approval_request_id"]), {"approve": True})
    assert again.status_code == 409 and again.json()["error"]["code"] == "APPROVAL_ALREADY_DECIDED"
    statuses = {e["id"]: e["status"] for e in f.accountant.get(E).json()["items"]}
    assert (statuses[owner_big["id"]], statuses[big["id"]]) == ("APPROVED", "REJECTED")
    approved_events = tenant_sql(
        f.tid, "SELECT payload->>'auto' FROM outbox_event WHERE event_type = 'ExpenseApproved'"
    )
    assert sorted(r[0] for r in approved_events) == ["false", "true", "true"]

    for sql in (
        "UPDATE expense SET amount = 1 WHERE id = :i",
        "UPDATE expense SET status = 'APPROVED' WHERE id = :r",
        "DELETE FROM expense WHERE id = :i",
        "DELETE FROM expense_attachment",
    ):
        with pytest.raises(DBAPIError, match=r"asseta: |permission denied"):
            tenant_sql(f.tid, sql, i=ok["id"], r=big["id"])


def test_fuel_events_attribute_cost_to_machine_and_job(api: Api) -> None:
    f = setup_finance(api)
    fuel_cat = category(f, "FUEL", "Fuel")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="100000000")
    bulk = f.owner.post(E, _expense(api, f, fuel_cat, "3000000", job_id=None, paid_from="COMPANY")).json()
    now = api.clock.now.isoformat()
    fe = "/api/v1/tenant/fuel-events"
    stock = f.owner.post(
        fe,
        {
            "event_type": "PURCHASE",
            "litres": "1000",
            "unit_price": "3000",
            "expense_id": bulk["id"],
            "supplier": "Puma Energy",
            "occurred_at": now,
        },
    ).json()
    assert (stock["machine_id"], Decimal(stock["attributed_cost"])) == (None, Decimal("3000000"))
    client = str(uuid.uuid4())
    issue = {
        "client_id": client,
        "event_type": "ISSUE",
        "litres": "200",
        "unit_price": "3000",
        "job_id": f.c.job_id,
        "meter_reading": "1002.5",
        "occurred_at": now,
    }
    issued = f.supervisor.post(fe, issue).json()
    assert issued["machine_id"] == f.c.t.machine_id and Decimal(issued["attributed_cost"]) == Decimal("600000")
    assert f.supervisor.post(fe, issue).json()["id"] == issued["id"]  # same client id: one event
    usage = f.supervisor.post(
        fe, {"event_type": "USAGE", "litres": "50.5", "machine_id": f.c.t.machine_id, "occurred_at": now}
    ).json()
    assert (usage["unit_price"], usage["attributed_cost"]) == (None, "0.0000")
    bad = f.supervisor.post(fe, {"event_type": "ISSUE", "litres": "10", "unit_price": "3000", "occurred_at": now})
    assert bad.status_code == 422  # ISSUE needs a machine or job
    listed = f.accountant.get(fe, machine_id=f.c.t.machine_id).json()
    assert {x["event_type"] for x in listed["items"]} == {"ISSUE", "USAGE"}
    with pytest.raises(DBAPIError, match=r"asseta: |permission denied"):
        tenant_sql(f.tid, "UPDATE fuel_event SET litres = 1 WHERE id = :i", i=issued["id"])
