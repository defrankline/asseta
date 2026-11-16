"""An offline money record that became impossible only because the server moved on is held for review, never dropped."""

import uuid
from typing import Any

import pytest

from asseta.modules.sync.conflicts import MONEY_CONFLICT_CODES, MONEY_OPERATIONS, is_conflict
from tests.support.api import Actor, Api
from tests.support.finance import role, setup_finance
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
    assert is_conflict("CREDIT_INVOICE_PAYMENT", "INVOICE_PAID")
    assert not is_conflict("METER_CAPTURE", "INVOICE_PAID")
    assert not is_conflict("CASH_COLLECTION", "NOT_FOUND")
    assert not is_conflict("HOURS_PURCHASE", "PAYMENT_NOT_PERMITTED")
