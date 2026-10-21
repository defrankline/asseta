"""Gate 5 (R1-G): tenant customer hire invoices from completed jobs — the invoice equals the job's billable
summary, issued invoices are immutable (API + DB), a job is never invoiced twice, corrections only by reversal."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from tests.support.api import Api
from tests.support.finance import FinCtx, complete_job, issue_invoice, priced_job, setup_finance, tenant_sql

TERMS = {
    "standby_treatment": "STANDBY_RATE",
    "standby_rate": "20000",
    "mobilization_fee": "50000",
    "discount_percent": "10",
    "tax_rate_percent": "18",
}


def _billed_job(api: Api, f: FinCtx, number: str = "J-100", opening: str = "1000.0") -> dict[str, Any]:
    f.owner.post(f"/api/v1/tenant/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "replaced"})
    job_id = priced_job(api, f, number, **TERMS)
    closing = str(Decimal(opening) + 10)
    return complete_job(api, f, job_id, opening, closing, 10.5, downtime_h=1, standby_h=2)


def _d(v: str) -> Decimal:
    return Decimal(v)


def test_invoice_from_completed_job_equals_billable_summary(api: Api) -> None:
    f = setup_finance(api)
    early = f.accountant.post("/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [f.c.job_id]})
    assert early.status_code == 422 and early.json()["error"]["code"] == "JOB_NOT_BILLABLE"  # approved, not completed

    s = _billed_job(api, f)
    assert (_d(s["meter_hours"]), _d(s["nonbillable_hours"])) == (Decimal(10), Decimal(3))
    assert (_d(s["billable_hours"]), _d(s["standby_hours"])) == (Decimal(7), Decimal(2))
    ch = s["charges"]
    assert [(line["kind"], _d(line["amount"])) for line in ch["lines"]] == [
        ("HIRE", Decimal("595000")),  # 7.0 h x 85,000 rate card
        ("STANDBY", Decimal("40000")),  # 2.0 h x 20,000
        ("MOBILIZATION", Decimal("50000")),
        ("DISCOUNT", Decimal("-68500")),  # 10% of 685,000
        ("TAX", Decimal("110970")),  # 18% of 616,500
    ]
    assert _d(ch["total"]) == Decimal("727470")

    draft = f.accountant.post(
        "/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [s["job"]["id"]], "notes": "Nov"}
    )
    assert draft.status_code == 201, draft.text
    inv = draft.json()
    assert inv["status"] == "DRAFT" and inv["invoice_number"] is None and inv["payment_state"] is None
    assert [(x["kind"], _d(x["quantity"]), _d(x["unit_price"]), _d(x["amount"])) for x in inv["lines"]] == [
        (x["kind"], _d(x["quantity"]), _d(x["unit_price"]), _d(x["amount"])) for x in ch["lines"]
    ]  # single source of truth: the job summary
    for k in ("subtotal", "discount_total", "tax_total", "total"):
        assert _d(inv[k]) == _d(ch[k])
    assert {x["machine_id"] for x in inv["lines"]} == {f.c.t.machine_id}

    issued = f.accountant.post(f"/api/v1/tenant/hire-invoices/{inv['id']}/issue", {}).json()
    assert issued["status"] == "ISSUED" and issued["invoice_number"] == "HINV-2026-00001"
    assert issued["payment_state"] == "UNPAID" and _d(issued["balance"]) == Decimal("727470")
    assert issued["due_date"] == "2026-12-01"  # issue date (tenant local) + customer terms (30 days)
    events = tenant_sql(f.tid, "SELECT event_type FROM outbox_event WHERE topic = 'asseta.finance'")
    assert [e[0] for e in events] == ["HireInvoiceIssued"]
    actions = {r[0] for r in tenant_sql(f.tid, "SELECT action FROM audit_event WHERE action LIKE 'finance.%'")}
    assert {"finance.invoice.drafted", "finance.invoice.issued"} <= actions


def test_issued_invoice_is_immutable_and_job_cannot_be_double_invoiced(api: Api) -> None:
    f = setup_finance(api)
    job_id = _billed_job(api, f)["job"]["id"]
    inv = issue_invoice(f, [job_id])
    # API: no edits; issuing again is refused; a second invoice for the same job is refused.
    again = f.accountant.post(f"/api/v1/tenant/hire-invoices/{inv['id']}/issue", {})
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVOICE_NOT_DRAFT"
    dup = f.accountant.post("/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [job_id]})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "JOB_ALREADY_INVOICED"
    twice = f.accountant.post(
        "/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [job_id, job_id]}
    )
    assert twice.json()["error"]["code"] == "DUPLICATE_JOB"
    other = f.owner.post("/api/v1/tenant/customers", {"code": "C2", "name": "Other Customer"}).json()["id"]
    wrong = f.accountant.post("/api/v1/tenant/hire-invoices", {"customer_id": other, "job_ids": [job_id]})
    assert wrong.json()["error"]["code"] == "JOB_CUSTOMER_MISMATCH"
    # Supervisors cannot invoice.
    assert (
        f.supervisor.post(
            "/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [job_id]}
        ).status_code
        == 403
    )

    # Database: even the application role cannot rewrite the snapshot, its lines, or delete anything.
    statements = [
        "UPDATE tenant_hire_invoice SET total = 1 WHERE id = :i",
        "UPDATE tenant_hire_invoice SET invoice_number = 'HINV-X' WHERE id = :i",
        "UPDATE tenant_hire_invoice SET status = 'DRAFT' WHERE id = :i",
        "DELETE FROM tenant_hire_invoice WHERE id = :i",
        "UPDATE hire_invoice_line SET amount = 1 WHERE invoice_id = :i",
        "DELETE FROM hire_invoice_line WHERE invoice_id = :i",
        "INSERT INTO hire_invoice_line (id, invoice_id, tenant_id, line_no, kind, job_id, machine_id, description,"
        " quantity, unit_price, amount) SELECT gen_random_uuid(), id, tenant_id, 99, 'HIRE', :j, :m, 'extra', 1, 1, 1"
        " FROM tenant_hire_invoice WHERE id = :i",
        "UPDATE hire_invoice_job SET job_id = job_id WHERE invoice_id = :i",
    ]
    for sql in statements:
        with pytest.raises(DBAPIError, match=r"asseta: |permission denied"):
            tenant_sql(f.tid, sql, i=inv["id"], j=job_id, m=f.c.t.machine_id)
    assert f.accountant.get(f"/api/v1/tenant/hire-invoices/{inv['id']}").json()["total"] == inv["total"]


def test_void_creates_reversal_releases_job_and_numbering_continues(api: Api) -> None:
    f = setup_finance(api)
    job_id = _billed_job(api, f)["job"]["id"]
    inv = issue_invoice(f, [job_id])
    assert f.accountant.post(f"/api/v1/tenant/hire-invoices/{inv['id']}/void", {}).status_code == 422  # reason
    voided = f.accountant.post(
        f"/api/v1/tenant/hire-invoices/{inv['id']}/void", {"reason": "Wrong customer contact on invoice"}
    )
    assert voided.status_code == 200, voided.text
    v = voided.json()
    assert v["status"] == "VOIDED" and v["invoice_number"] == "HINV-2026-00001" and v["total"] == inv["total"]
    rows = tenant_sql(f.tid, "SELECT kind, amount, reason FROM financial_adjustment WHERE invoice_id = :i", i=inv["id"])
    assert [(r[0], r[1]) for r in rows] == [("INVOICE_REVERSAL", Decimal(inv["total"]))]
    again = f.accountant.post(f"/api/v1/tenant/hire-invoices/{inv['id']}/void", {"reason": "twice"})
    assert again.json()["error"]["code"] == "INVOICE_ALREADY_VOIDED"
    bal = f.accountant.get(f"/api/v1/tenant/customers/{f.customer_id}/balance").json()[0]
    assert (_d(bal["invoiced"]), _d(bal["reversed"]), _d(bal["balance"])) == (Decimal(inv["total"]),) * 2 + (
        Decimal(0),
    )

    # The job is invoiceable again; a discarded draft needs no reversal; numbering is sequential, gap-free.
    draft = f.accountant.post("/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": [job_id]})
    discarded = f.accountant.post(f"/api/v1/tenant/hire-invoices/{draft.json()['id']}/void", {"reason": "redo"}).json()
    assert discarded["status"] == "VOIDED" and discarded["invoice_number"] is None
    assert len(tenant_sql(f.tid, "SELECT 1 FROM financial_adjustment")) == 1
    reissued = issue_invoice(f, [job_id])
    assert reissued["invoice_number"] == "HINV-2026-00002"
    listed = f.accountant.get("/api/v1/tenant/hire-invoices", status="ISSUED").json()
    assert [i["id"] for i in listed["items"]] == [reissued["id"]]
    voided_events = tenant_sql(
        f.tid, "SELECT payload->>'invoice_number' FROM outbox_event WHERE event_type = 'HireInvoiceVoided'"
    )
    assert [r[0] for r in voided_events] == ["HINV-2026-00001"]
    assert uuid.UUID(reissued["id"])
