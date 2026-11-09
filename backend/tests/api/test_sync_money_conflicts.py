"""An offline money record that became impossible only because the server moved on is held for review, never dropped."""

import uuid
from typing import Any

import pytest

from asseta.modules.sync.conflicts import MONEY_CONFLICT_CODES, MONEY_OPERATIONS, is_conflict
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, allow_direct_void, complete_job, issue_invoice, role, setup_finance
from tests.support.hours import hours_policy

DEVICE = "CONFLICT-1"


def _device(api: Api, actor: Actor) -> dict[str, str]:
    h = {**actor.headers(True, None), "X-Device-Id": DEVICE}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "2.0.0"}
    )
    assert reg.status_code == 201, reg.text
    return h


def _push(api: Api, h: dict[str, str], op_type: str, payload: dict[str, Any]) -> Any:
    now = api.clock.now.isoformat()
    op = {"id": str(uuid.uuid4()), "op_type": op_type, "created_at_device": now, "payload": payload}
    r = api.client.post("/api/v1/sync/push", headers=h, json={"device_now": now, "operations": [op]})
    assert r.status_code == 200, r.text
    return r.json()["results"][0]


def _held(result: dict[str, Any], code: str) -> None:
    assert (result["status"], result["error"]["code"]) == ("CONFLICT", code), result


def _collection(api: Api, f: FinCtx, **extra: Any) -> dict[str, Any]:
    return {
        "client_id": str(uuid.uuid4()),
        "customer_id": f.customer_id,
        "amount": "1000",
        "received_at": api.clock.now.isoformat(),
        **extra,
    }


def test_collection_against_a_voided_invoice_is_held_not_dropped(api: Api) -> None:
    f = setup_finance(api)
    allow_direct_void(f)
    h = _device(api, f.supervisor)
    complete_job(api, f, f.c.job_id, "1000", "1008", 8)
    inv = issue_invoice(f, [f.c.job_id])
    voided = f.accountant.post(f"/api/v1/tenant/hire-invoices/{inv['id']}/void", {"reason": "Wrong contact on invoice"})
    assert voided.status_code == 200, voided.text

    allocations = [{"invoice_id": inv["id"], "amount": "1000"}]
    _held(_push(api, h, "CASH_COLLECTION", _collection(api, f, allocations=allocations)), "INVOICE_NOT_OPEN")
    # Held, not applied: nothing moved into the supervisor's custody, and a reviewer can see it.
    payments = f.owner.get("/api/v1/tenant/customer-payments", customer_id=f.customer_id).json()
    assert payments["total"] == 0
    conflicts = f.owner.get("/api/v1/tenant/sync/conflicts").json()["items"]
    assert [c["op_type"] for c in conflicts] == ["CASH_COLLECTION"]


def test_hours_sale_paid_in_cash_is_held_when_hours_were_switched_off(api: Api) -> None:
    f = setup_finance(api)
    h = _device(api, f.supervisor)
    hours_policy(f, enabled=False)
    payload = {
        "client_id": str(uuid.uuid4()),
        "walk_in": {"name": "Roadside customer"},
        "machine_id": f.c.t.machine_id,
        "hours": "3",
        "payment": {"method": "CASH", "received_at": api.clock.now.isoformat()},
    }
    _held(_push(api, h, "HOURS_PURCHASE", payload), "HOURS_DISABLED")


def test_remittance_is_held_when_the_login_has_no_staff_record(api: Api) -> None:
    f = setup_finance(api)
    h = _device(api, role(api, f.tid, "supervisor", "sup-unlinked"))
    payload = {"client_id": str(uuid.uuid4()), "amount": "500", "handed_at": api.clock.now.isoformat()}
    _held(_push(api, h, "CASH_HANDOVER", payload), "STAFF_NOT_LINKED")


@pytest.mark.parametrize("code", sorted(MONEY_CONFLICT_CODES))
@pytest.mark.parametrize("op_type", sorted(MONEY_OPERATIONS))
def test_money_operations_hold_every_listed_code(op_type: str, code: str) -> None:
    assert is_conflict(op_type, code)


def test_other_operations_and_impossible_payloads_keep_their_outcome() -> None:
    assert not is_conflict("METER_CAPTURE", "MACHINE_INACTIVE")
    assert not is_conflict("EXPENSE", "STAFF_INACTIVE")
    assert is_conflict("CASH_COLLECTION", "INVOICE_NOT_OPEN")
    assert not is_conflict("CASH_COLLECTION", "NOT_FOUND")
    assert not is_conflict("HOURS_PURCHASE", "PAYMENT_NOT_PERMITTED")
