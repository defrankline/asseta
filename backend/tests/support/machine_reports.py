"""ADR-008 helpers: a company with a machine assigned to a supervisor, an approved meter baseline, customers with
activated hours, and machine report payload builders."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance
from tests.support.hours import RATE, hours_policy, purchase, verify
from tests.support.meter import fix

T = "/api/v1/tenant"
BASELINE = "1000"


def ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def code(r: Any) -> str:
    return str(r.json()["error"]["code"])


@dataclass
class ReportCtx:
    f: FinCtx
    machine_id: str
    reasons: dict[str, str]  # code -> id


def baseline(api: Api, f: FinCtx, machine_id: str, reading: str = BASELINE) -> None:
    proposed = ok(
        f.owner.post(
            f"{T}/meter-baselines",
            {
                "machine_id": machine_id,
                "reading": reading,
                "captured_at": (api.clock.now - timedelta(hours=2)).isoformat(),
                "note": "Starting reading",
            },
        ),
        201,
    )
    ok(
        f.manager.post(
            f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Checked on site"}
        )
    )


def setup_reports(api: Api, name: str = "Report Co", device: str = "MR-1") -> ReportCtx:
    f = setup_finance(api, name, device)
    baseline(api, f, f.c.t.machine_id)
    reasons = {r["code"]: r["id"] for r in ok(f.owner.get(f"{T}/machine-report-reasons"))}
    return ReportCtx(f, f.c.t.machine_id, reasons)


def second_machine(api: Api, ctx: ReportCtx, assign_to: str | None = None, prefix: str = "MRB") -> str:
    """Another machine with an approved baseline, assigned (SUPERVISOR) to the given staff member."""
    f = ctx.f
    [machine_id] = api.add_machines(f.owner, 1, prefix=prefix)
    staff = assign_to or f.sup_staff_id
    ok(
        f.owner.post(
            f"{T}/machines/{machine_id}/assignments",
            {"staff_member_id": staff, "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
        ),
        201,
    )
    baseline(api, f, machine_id)
    return machine_id


def bought(api: Api, f: FinCtx, hours: int, customer_id: str | None = None) -> dict[str, Any]:
    """A registered customer's order paid by bank and verified: `hours` activated hours."""
    p = purchase(api, f.accountant, f, str(hours), customer_id=customer_id, pay=str(hours * RATE))
    verify(f.accountant2, p["payment"]["id"])
    return p


def customer(f: FinCtx, code_: str, name: str) -> str:
    return str(ok(f.owner.post(f"{T}/customers", {"code": code_, "name": name}), 201)["id"])


def reading(machine_id: str, value: str, at: datetime, capture_id: str | None = None) -> dict[str, Any]:
    return {
        "id": capture_id or str(uuid.uuid4()),
        "machine_id": machine_id,
        "kind": "DAILY",
        "capture_mode": "MANUAL",
        "reading": value,
        "gps": fix(at),
        "device_id": "android-report-device",
        "captured_at": at.isoformat(),
    }


def cust(customer_id: str, hours: str | int | Decimal) -> dict[str, Any]:
    return {"kind": "CUSTOMER", "customer_id": customer_id, "hours": str(hours)}


def idle(reason_id: str, hours: str | int | Decimal, note: str = "Waited for the site to open") -> dict[str, Any]:
    return {"kind": "NON_PRODUCTIVE", "reason_id": reason_id, "hours": str(hours), "note": note}


def report_body(
    machine_id: str, value: str | None, at: datetime | None, lines: list[dict[str, Any]], **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"id": str(uuid.uuid4()), "machine_id": machine_id, "lines": lines, **extra}
    if value is not None:
        assert at is not None
        body["capture"] = reading(machine_id, value, at)
    return body


def submit(actor: Actor, body: dict[str, Any], status: int = 201) -> Any:
    return ok(actor.post(f"{T}/machine-reports", body), status)


def later(api: Api, hours: float) -> datetime:
    """Move the clock forward (readings are spaced like real working hours) and return the new time."""
    api.clock.set_at(api.clock.now + timedelta(hours=hours))
    now: datetime = api.clock.now
    return now


def field_credit(f: FinCtx, on: bool = True) -> None:
    hours_policy(f, field_credit_sales=on, field_noncash_payments=True)


def opening_body(machine_id: str, value: str, at: datetime, **extra: Any) -> dict[str, Any]:
    """An opening report: the machine's first reading, no lines (the machine has no starting reading yet)."""
    return {
        "id": str(uuid.uuid4()),
        "machine_id": machine_id,
        "opening": True,
        "lines": [],
        "capture": reading(machine_id, value, at),
        **extra,
    }
