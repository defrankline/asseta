"""Gate 7 report exports (R1-I): every CSV parses back to the same rows, order and filters as its list endpoint;
spreadsheet formula injection is neutralised; PDFs are paginated with page numbers; row caps add a truncation note;
permissions match the list endpoint; every export is audited."""

import csv
import io
import re
import uuid
import zlib
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import Response

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.geospatial.alerts import AlertService
from asseta.modules.geospatial.models import AlertSeverity, AlertType
from asseta.modules.reports import router as reports_router
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, category, complete_job, expense_policy, issue_invoice, role, setup_finance
from tests.support.notify import sql

R = "/api/v1/tenant/reports"
INJECTION = '=HYPERLINK("http://evil.example","click")'


def _ok(r: Response, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def parse_csv(r: Response) -> list[dict[str, str]]:
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    assert b"\r\n" in r.content
    text = r.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def pdf_text(content: bytes) -> bytes:
    """Concatenated (decompressed) content streams of a PDF."""
    out = b""
    for raw in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", content, re.S):
        try:
            out += zlib.decompress(raw)
        except zlib.error:
            out += raw
    return out


def page_labels(text: bytes) -> list[tuple[int, int]]:
    """Footer "Page X of N" labels (fpdf2 writes the total-pages alias as a separate text run)."""
    return [(int(a), int(b)) for a, b in re.findall(rb"\(Page (\d+) of \) Tj \((\d+)\) Tj", text)]


def _alert(tid: str, machine_id: str, title: str, minutes: int, api: Api) -> None:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        AlertService(s, uuid.UUID(tid)).raise_alert(
            alert_type=AlertType.GEOFENCE_EXIT,
            severity=AlertSeverity.WARNING,
            event_time=api.clock.now - timedelta(minutes=minutes),
            dedupe_key=f"test:{title}",
            title=title,
            evidence={"test": True},
            machine_id=uuid.UUID(machine_id),
        )


@pytest.fixture
def data(api: Api) -> FinCtx:
    f = setup_finance(api)
    complete_job(api, f, f.c.job_id, "1000.0", "1008.0", 9, downtime_h=1.5)
    issue_invoice(f, [f.c.job_id])
    _ok(f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "100000"}), 201)
    misc = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="50000")
    for amount, text in (
        ("30000", "hydraulic hose"),
        ("120000", INJECTION),
        ("5000", "-2+3 grease"),
        ("700", "@SUM(A1)"),
    ):
        _ok(
            f.supervisor.post(
                "/api/v1/tenant/expenses",
                {
                    "category_id": misc,
                    "description": text,
                    "amount": amount,
                    "incurred_at": api.clock.now.isoformat(),
                    "machine_id": f.c.t.machine_id,
                    "paid_from": "CASH_CUSTODY",
                },
            ),
            201,
        )
    _alert(f.tid, f.c.t.machine_id, "Left the quarry", 30, api)
    _alert(f.tid, f.c.t.machine_id, "+cmd|' /C calc'!A0", 10, api)
    return f


def test_csv_matches_list_endpoints_for_the_same_filters(api: Api, data: FinCtx) -> None:
    f, o = data, data.owner
    jobs = parse_csv(o.get(f"{R}/jobs.csv", status="COMPLETED"))
    listed = _ok(o.get("/api/v1/tenant/jobs", status="COMPLETED"))["items"]
    assert [r["Job"] for r in jobs] == [j["job_number"] for j in listed] == ["J-001"]
    assert jobs[0]["Customer"] == "Road Builders Ltd" and jobs[0]["Hourly rate"] == listed[0]["hourly_rate"]
    assert jobs[0]["Started"].endswith("+03:00")  # instants in the tenant timezone

    readings = parse_csv(o.get(f"{R}/readings.csv", job_id=f.c.job_id))
    listed = _ok(o.get("/api/v1/tenant/meter-captures", job_id=f.c.job_id))["items"]
    assert [Decimal(r["Reading"]) for r in readings] == [Decimal(c["reading"]) for c in listed]
    assert [r["Kind"] for r in readings] == ["CLOSING", "OPENING"]  # latest captured first, like the list

    expenses = parse_csv(o.get(f"{R}/expenses.csv", status="APPROVED"))
    listed = _ok(o.get("/api/v1/tenant/expenses", status="APPROVED"))["items"]
    assert len(expenses) == len(listed) == 3
    assert [Decimal(r["Amount"]) for r in expenses] == [Decimal(e["amount"]) for e in listed]
    assert {r["Category"] for r in expenses} == {"Spares"}
    pending = parse_csv(o.get(f"{R}/expenses.csv", status="PENDING_APPROVAL"))
    assert [r["Description"] for r in pending] == ["'" + INJECTION]  # formula neutralised
    descriptions = {r["Description"] for r in expenses}
    assert {"'-2+3 grease", "'@SUM(A1)", "hydraulic hose"} == descriptions

    alerts = parse_csv(o.get(f"{R}/alerts.csv", status="OPEN"))
    listed = _ok(o.get("/api/v1/tenant/alerts", status="OPEN"))["items"]
    assert [r["Title"].removeprefix("'") for r in alerts] == [a["title"] for a in listed]
    assert alerts[0]["Title"] == "'+cmd|' /C calc'!A0"

    fleet = parse_csv(o.get(f"{R}/fleet.csv"))
    mapped = _ok(o.get("/api/v1/tenant/fleet/map"))
    assert [r["Asset code"] for r in fleet] == [m["asset_code"] for m in mapped]
    assert fleet[0]["Reported work"] == mapped[0]["reported_work_status"]
    assert parse_csv(o.get(f"{R}/fleet.csv", connectivity="OFFLINE")) == []

    window = {"from": "2026-11-01", "to": "2026-11-02"}
    cash = parse_csv(o.get(f"{R}/cash.csv", **window))
    summary = _ok(o.get("/api/v1/tenant/cash/supervisor-summary", **window))
    assert [(r["Supervisor"], Decimal(r["Outstanding"])) for r in cash] == [
        (s["staff_name"], Decimal(s["closing_outstanding"])) for s in summary
    ]
    assert Decimal(cash[0]["Outstanding"]) == Decimal(100000 - 30000 - 5000 - 700)

    utilisation = parse_csv(o.get(f"{R}/utilisation.csv"))
    insights = _ok(o.get("/api/v1/tenant/insights"))["utilisation"]
    assert [(r["Asset code"], r["Status"]) for r in utilisation] == [(u["asset_code"], u["status"]) for u in insights]


def test_subscription_reports_tenant_and_platform(api: Api, data: FinCtx) -> None:
    sid = data.c.t.tenant["subscription_id"]
    api.generate(sid, api.clock.now.date() + timedelta(days=31))
    rows = parse_csv(data.owner.get(f"{R}/subscription.csv"))
    invoices = _ok(data.owner.get("/api/v1/tenant/billing/invoices"))
    assert [r["Invoice / asset"] for r in rows if r["Record"].startswith("INVOICE")] == [
        i["invoice_number"] for i in invoices
    ]
    assert invoices and [r["Record"] for r in rows].count("ENROLLMENT") == 1

    platform = parse_csv(api.platform.get("/api/v1/platform/reports/subscription.csv", tenant_id=data.tid))
    listed = _ok(api.platform.get("/api/v1/platform/invoices", tenant_id=data.tid))["items"]
    assert [r["Invoice"] for r in platform] == [i["invoice_number"] for i in listed]
    assert {r["Tenant"] for r in platform} == {"Hire Co"}
    assert data.owner.get("/api/v1/platform/reports/subscription.csv").status_code == 403
    audit = _ok(api.platform.get("/api/v1/platform/audit-events", action_prefix="platform.report."))["items"]
    assert audit[0]["entity_id"] == "subscription" and audit[0]["after"]["filters"] == {"tenant_id": data.tid}


def test_pdf_is_titled_paginated_and_audited(api: Api, data: FinCtx) -> None:
    r = data.owner.get(f"{R}/expenses.pdf", status="APPROVED")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert 'filename="asseta-expenses-2026-11-01.pdf"' in r.headers["content-disposition"]
    text = pdf_text(r.content)
    assert page_labels(text) == [(1, 1)] and b"Expenses" in text and b"status=APPROVED" in text
    assert b"Hire Co" in text and b"Africa/Dar_es_Salaam" in text
    events = sql(
        "SELECT action, entity_id, after, tenant_id::text FROM audit_event WHERE action = 'report.exported'"
        " ORDER BY occurred_at"
    )
    assert [(e.entity_id, e.after["format"], e.after["filters"], e.after["rows"]) for e in events] == [
        ("expenses", "pdf", {"status": "APPROVED"}, 3)
    ]
    assert events[0].tenant_id == data.tid


def test_row_caps_add_truncation_note(api: Api, data: FinCtx, monkeypatch: pytest.MonkeyPatch) -> None:
    caps = {"csv": ("text/csv; charset=utf-8", 2), "pdf": ("application/pdf", 1)}
    monkeypatch.setattr(reports_router, "FORMATS", caps)
    r = data.owner.get(f"{R}/expenses.csv")
    assert r.headers["x-report-truncated"] == "true" and r.headers["x-report-rows"] == "2"
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"), newline="")))
    assert len(rows) == 4 and rows[-1][0].startswith("TRUNCATED: only the first 2 rows")
    assert "narrow the filters" in rows[-1][0]
    pdf = data.owner.get(f"{R}/expenses.pdf")
    assert pdf.headers["x-report-truncated"] == "true"
    assert b"TRUNCATED: only the first 1 rows" in pdf_text(pdf.content)
    full = data.owner.get(f"{R}/jobs.csv")
    assert full.headers["x-report-truncated"] == "false"


def test_multi_page_pdf_numbers_every_page(api: Api, data: FinCtx) -> None:
    misc = category(data, "FUEL", "Fuel")
    for i in range(70):
        body = {
            "category_id": misc,
            "description": f"Fuel top-up {i:03d} — with a long note so rows wrap ✓",
            "amount": "100",
            "incurred_at": (api.clock.now - timedelta(minutes=i)).isoformat(),
            "paid_from": "COMPANY",
        }
        _ok(data.owner.post("/api/v1/tenant/expenses", body), 201)
    text = pdf_text(data.owner.get(f"{R}/expenses.pdf").content)
    labels = page_labels(text)
    pages = len(labels)
    assert pages >= 2 and labels == [(i, pages) for i in range(1, pages + 1)]
    assert text.count(b"Description") >= pages  # header row repeated on every page


def test_permissions_mirror_the_list_endpoints(api: Api, data: FinCtx) -> None:
    sup = data.supervisor
    assert sup.get(f"{R}/cash.csv").status_code == 403  # no tenant.finance.read
    assert (
        sup.get("/api/v1/tenant/cash/supervisor-summary", **{"from": "2026-11-01", "to": "2026-11-01"}).status_code
        == 403
    )
    assert sup.get(f"{R}/jobs.pdf").status_code == 200
    menu = {d["code"] for d in _ok(data.accountant.get(R))}
    assert menu == {"jobs", "cash", "expenses", "subscription"}
    assert {d["code"] for d in _ok(data.owner.get(R))} == {
        "fleet", "jobs", "readings", "cash", "expenses", "alerts", "subscription", "utilisation"
    }  # fmt: skip
    jobs_def = next(d for d in _ok(data.owner.get(R)) if d["code"] == "jobs")
    assert jobs_def["csv_path"] == f"{R}/jobs.csv" and jobs_def["filters"] == ["q", "status", "machine_id"]
    operator: Actor = role(api, data.tid, "operator", "op-2")
    assert operator.get(R).status_code == 403
    assert data.accountant.get(f"{R}/fleet.csv").status_code == 403
    other = api.onboard("Other Co", price="1")
    api.activate(other)
    leaked = other["owner"].get(f"{R}/expenses.csv")
    assert parse_csv(leaked) == []  # RLS: another tenant's export never sees these rows
    assert data.owner.get(f"{R}/jobs.csv", bogus="1").status_code == 422  # unknown filters are refused
