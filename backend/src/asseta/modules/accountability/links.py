"""Where management opens a record or the transactions behind a figure: console routes by record type. Mirrors the
routes notifications link to (notification.rules.RECORDS); lists accept the query filters named in `list_route`."""

import uuid
from typing import Any
from urllib.parse import urlencode

CASH = "/tenant/finance/cash"
# Record type -> console detail route prefix; `<prefix>/<id>` opens the record.
RECORD_ROUTES: dict[str, str] = {
    "hours_purchase": "/tenant/hours/purchases",
    "hours_transfer": "/tenant/hours/transfers",
    "hours_cancellation": "/tenant/hours/cancellations",
    "customer_discount": "/tenant/hours/discounts",
    "credit_arrangement": "/tenant/hours/credit",
    "hire_invoice": "/tenant/finance/invoices",
    "customer_payment": "/tenant/customer-payments",
    "cash_handover": f"{CASH}/remittances",
    "partial_remittance": f"{CASH}/remittances",
    "cash_transfer": f"{CASH}/transfers",
    "cash_float": f"{CASH}/floats",
    "supervisor_cash_custody": f"{CASH}/floats",
    "cash_retention": f"{CASH}/retentions",
    "custody_adjustment": f"{CASH}/adjustments",
    "cash_variance": f"{CASH}/variances",
    "cash_remittance_overdue": f"{CASH}/remittance-overdue",
    "adjustment_request": "/tenant/finance/adjustments/requests",
    "adjustment_entry": "/tenant/finance/adjustments",
    "job": "/tenant/jobs",
    "anomaly_case": "/tenant/cases",
    "daily_report": "/tenant/daily-reports",
    "work_allocation": "/tenant/work-allocations",
    "work_allocation_correction": "/tenant/work-allocations/corrections",
    "meter_baseline": "/tenant/meter-baselines",
    "meter_correction": "/tenant/meter-corrections",
    "meter_reset": "/tenant/meter-resets",
    "meter_capture": "/tenant/exceptions",
    "job_exception": "/tenant/exceptions",
    "classification": "/tenant/engine-hours/classifications",
    "engine_hour_classification": "/tenant/engine-hours/classifications",
    "non_revenue_approval": "/tenant/non-revenue-approvals",
    "revenue_difference": "/tenant/revenue-differences",
    "approval_request": "/tenant/approvals",
    "tracking_alert": "/tenant/alerts",
    "security_event": "/tenant/security-events",
    "expense": "/tenant/expenses",
    "customer": "/tenant/customers",
    "machine": "/tenant/machines",
    "staff_member": "/tenant/staff",
}


def record_route(record_type: str, record_id: uuid.UUID | str | None) -> str | None:
    """The record's own console route; None for a record type without one (or a record without an id)."""
    prefix = RECORD_ROUTES.get(record_type)
    return f"{prefix}/{record_id}" if prefix and record_id else None


def list_route(path: str, **filters: Any) -> str:
    """A console list with its query filters (None values are left out)."""
    query = urlencode({k: str(v) for k, v in filters.items() if v is not None})
    return f"{path}?{query}" if query else path
