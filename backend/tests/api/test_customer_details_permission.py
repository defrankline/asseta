"""tenant.customer.details: supervisors add customers and edit their details; terms, contracts and rates stay with
tenant.customer.write (the office)."""

from typing import Any

from tests.support.api import Api
from tests.support.finance import setup_finance

C = "/api/v1/tenant"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _refused(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def test_supervisor_adds_and_edits_customers_but_not_terms_contracts_or_rates(api: Api) -> None:
    f = setup_finance(api, "Details Co", "DET-1")
    sup, owner = f.supervisor, f.owner

    created = _ok(
        sup.post(f"{C}/customers", {"code": "NEW-1", "name": "Kibaha Builders", "contact_phone": "+255700000001"}),
        201,
    )
    assert created["payment_terms_days"] == 30
    _refused(
        sup.post(f"{C}/customers", {"code": "NEW-2", "name": "Credit Co", "payment_terms_days": 60}),
        403,
        "CUSTOMER_TERMS_NOT_PERMITTED",
    )

    body = {k: created[k] for k in ("code", "name", "tax_id", "contact_name", "contact_email", "payment_terms_days")}
    edited = _ok(sup.put(f"{C}/customers/{created['id']}", {**body, "contact_phone": "+255700000002", "version": 1}))
    assert edited["contact_phone"] == "+255700000002"
    _refused(
        sup.put(f"{C}/customers/{created['id']}", {**body, "payment_terms_days": 45, "version": edited["version"]}),
        403,
        "CUSTOMER_TERMS_NOT_PERMITTED",
    )
    # Deactivating, contracts and rate cards stay with the office.
    assert (
        sup.post(
            f"{C}/customers/{created['id']}/deactivate", {"reason": "Not a customer", "version": edited["version"]}
        ).status_code
        == 403
    )
    assert sup.post(f"{C}/contracts", {"customer_id": created["id"], "contract_number": "CT-X"}).status_code == 403
    assert (
        sup.post(
            f"{C}/rate-cards",
            {"machine_category_id": created["id"], "hourly_rate": "1", "minimum_hours": "1", "reason": "nope"},
        ).status_code
        == 403
    )

    # The office still sets the terms.
    terms = _ok(
        owner.put(f"{C}/customers/{created['id']}", {**body, "payment_terms_days": 45, "version": edited["version"]})
    )
    assert terms["payment_terms_days"] == 45
