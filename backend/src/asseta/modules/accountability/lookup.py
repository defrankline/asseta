"""Transaction lookup (guideline section 10): any human number, outside reference or record id resolves to what the
record is, where to open it, its status, who did it, when, and what remains outstanding. One UNION ALL finds the
matches in the caller's RLS scope; a reference matches a handful of records, so each is then read once."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import String, cast, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from asseta.modules.accountability.links import record_route
from asseta.modules.adjustments.models import AdjustmentLedgerEntry, AdjustmentRequest, AdjustmentRequestStatus
from asseta.modules.expenses.models import ApprovalRequest, Expense
from asseta.modules.finance.custody_models import (
    CashDecisionStatus,
    CashRetention,
    CashTransfer,
    CashTransferStatus,
    CashVariance,
    CustodyAdjustment,
    VarianceStatus,
)
from asseta.modules.finance.invoice_service import verified_paid
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    HireInvoiceStatus,
    SettlementStatus,
    TenantHireInvoice,
)
from asseta.modules.hours.ledger import allocated_amounts, purchase_totals
from asseta.modules.hours.models import HoursCancellation, HoursPurchase, HoursTransfer, RequestStatus
from asseta.modules.intelligence.models import AnomalyCase
from asseta.modules.jobs.models import Job, RentalContract
from asseta.modules.meter.allocation_models import DailyOperationalReport
from asseta.modules.meter.engine_models import EngineHourClassification, MeterCorrection
from asseta.modules.meter.models import MeterResetEvent
from asseta.modules.revenue.models import NonRevenueApproval, RevenueDifference, RevenueDifferenceStatus

ZERO = Decimal(0)
MONEY, HOURS = "MONEY", "HOURS"


class LookupMatchDto(BaseModel):
    record_type: str
    id: uuid.UUID
    reference: str | None
    route: str | None
    status: str | None
    recorded_by: uuid.UUID | None = None
    recorded_by_name: str | None = None
    recorded_at: datetime | None = None
    decided_by: uuid.UUID | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    machine_id: uuid.UUID | None = None
    machine_code: str | None = None
    machine_name: str | None = None
    staff_member_id: uuid.UUID | None = None
    staff_member_name: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    balance_outstanding: Decimal | None = None
    balance_unit: str | None = None
    hours_remaining: Decimal | None = None


class LookupResultDto(BaseModel):
    reference: str
    matches: list[LookupMatchDto]


def _purchase(s: Session, p: HoursPurchase) -> dict[str, Any]:
    verified, _ = allocated_amounts(s, p.id)
    return {
        "status": "CANCELLED" if p.cancelled_at else "OPEN",
        "recorded_by": p.created_by,
        "recorded_at": p.created_at,
        "customer_id": p.customer_id,
        "machine_id": p.machine_id,
        "amount": p.amount,
        "currency": p.currency,
        "balance_outstanding": ZERO if p.cancelled_at else max(ZERO, p.amount - verified),
        "balance_unit": MONEY,
        "hours_remaining": purchase_totals(s, p).remaining,
    }


def _invoice(s: Session, i: TenantHireInvoice) -> dict[str, Any]:
    issued = i.status is HireInvoiceStatus.ISSUED
    return {
        "recorded_by": i.created_by,
        "recorded_at": i.created_at,
        "decided_by": i.issued_by,
        "decided_at": i.issued_at,
        "customer_id": i.customer_id,
        "amount": i.total,
        "currency": i.currency,
        "balance_outstanding": i.total - verified_paid(s, i.id) if issued else ZERO,
        "balance_unit": MONEY,
    }


def _job(s: Session, j: Job) -> dict[str, Any]:
    contract = s.get(RentalContract, j.contract_id)
    return {
        "recorded_at": j.created_at,
        "decided_by": j.approved_by,
        "decided_at": j.approved_at,
        "customer_id": contract.customer_id if contract else None,
        "machine_id": j.machine_id,
        "staff_member_id": j.supervisor_id,
        "currency": j.currency,
    }


def _payment(_: Session, p: CustomerPayment) -> dict[str, Any]:
    waiting = p.status is SettlementStatus.CLAIMED and p.reversed_at is None
    return {
        "recorded_by": p.recorded_by,
        "recorded_at": p.recorded_at,
        "decided_by": p.verified_by,
        "decided_at": p.verified_at,
        "customer_id": p.customer_id,
        "staff_member_id": p.received_by_staff_id,
        "amount": p.amount,
        "currency": p.currency,
        "balance_outstanding": p.amount if waiting else ZERO,
        "balance_unit": MONEY,
    }


def _handover(_: Session, h: CashHandover) -> dict[str, Any]:
    balance = h.outstanding_difference if h.status is SettlementStatus.VERIFIED else h.amount
    return {
        "recorded_by": h.recorded_by,
        "recorded_at": h.recorded_at,
        "decided_by": h.verified_by,
        "decided_at": h.verified_at,
        "staff_member_id": h.staff_member_id,
        "amount": h.amount,
        "currency": h.currency,
        "balance_outstanding": balance,
        "balance_unit": MONEY,
    }


def _transfer(_: Session, t: CashTransfer) -> dict[str, Any]:
    done = t.status is CashTransferStatus.ACKNOWLEDGED
    return {
        "recorded_by": t.recorded_by,
        "recorded_at": t.recorded_at,
        "decided_by": t.acknowledged_by,
        "decided_at": t.acknowledged_at,
        "staff_member_id": t.from_staff_id,
        "amount": t.amount_declared,
        "currency": t.currency,
        "balance_outstanding": t.amount_declared - (t.amount_received or ZERO) if done else t.amount_declared,
        "balance_unit": MONEY,
    }


def _hours_transfer(_: Session, t: HoursTransfer) -> dict[str, Any]:
    return {
        "recorded_by": t.requested_by,
        "recorded_at": t.requested_at,
        "decided_by": t.decided_by,
        "decided_at": t.decided_at,
        "machine_id": t.from_machine_id,
        "amount": t.hours,
        "balance_outstanding": t.hours if t.status is RequestStatus.PENDING else ZERO,
        "balance_unit": HOURS,
    }


def _retention(_: Session, r: CashRetention) -> dict[str, Any]:
    return {
        "recorded_by": r.created_by,
        "recorded_at": r.created_at,
        "decided_by": r.decided_by,
        "decided_at": r.decided_at,
        "staff_member_id": r.staff_member_id,
        "amount": r.amount,
        "currency": r.currency,
        "balance_outstanding": ZERO if r.status is CashDecisionStatus.REJECTED else r.amount,
        "balance_unit": MONEY,
    }


def _custody_adjustment(_: Session, a: CustodyAdjustment) -> dict[str, Any]:
    return {
        "recorded_by": a.created_by,
        "recorded_at": a.created_at,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at,
        "staff_member_id": a.staff_member_id,
        "amount": a.amount,
        "currency": a.currency,
        "balance_outstanding": a.amount if a.status is CashDecisionStatus.PENDING else ZERO,
        "balance_unit": MONEY,
    }


def _request(_: Session, r: AdjustmentRequest) -> dict[str, Any]:
    value = r.amount if r.amount is not None else r.hours
    return {
        "recorded_by": r.proposed_by,
        "recorded_at": r.proposed_at,
        "decided_by": r.decided_by,
        "decided_at": r.decided_at,
        "customer_id": r.customer_id,
        "machine_id": r.machine_id,
        "amount": value,
        "currency": r.currency,
        "balance_outstanding": value if r.status is AdjustmentRequestStatus.PROPOSED else ZERO,
        "balance_unit": MONEY if r.amount is not None else HOURS,
    }


def _entry(_: Session, e: AdjustmentLedgerEntry) -> dict[str, Any]:
    return {
        "recorded_by": e.requested_by,
        "recorded_at": e.requested_at or e.posted_at,
        "decided_by": e.approved_by,
        "decided_at": e.approved_at,
        "customer_id": e.customer_id,
        "machine_id": e.machine_id,
        "staff_member_id": e.staff_member_id,
        "amount": e.amount,
        "currency": e.currency,
        "balance_outstanding": e.resulting_balance,
        "balance_unit": e.unit.value,
    }


def _case(_: Session, c: AnomalyCase) -> dict[str, Any]:
    return {
        "recorded_at": c.opened_at,
        "decided_by": c.resolved_by,
        "decided_at": c.resolved_at,
        "machine_id": c.machine_id,
        "staff_member_id": c.staff_member_id,
    }


def _variance(_: Session, v: CashVariance) -> dict[str, Any]:
    return {
        "recorded_by": v.opened_by,
        "recorded_at": v.opened_at,
        "decided_by": v.resolved_by,
        "decided_at": v.resolved_at,
        "customer_id": v.customer_id,
        "machine_id": v.machine_id,
        "staff_member_id": v.staff_member_id,
        "amount": v.amount,
        "currency": v.currency,
        "balance_outstanding": ZERO if v.status is VarianceStatus.RESOLVED else abs(v.amount),
        "balance_unit": v.unit.value,
    }


def _report(_: Session, d: DailyOperationalReport) -> dict[str, Any]:
    return {
        "recorded_by": d.submitted_by,
        "recorded_at": d.submitted_at,
        "decided_by": d.reviewed_by,
        "decided_at": d.reviewed_at,
        "machine_id": d.machine_id,
        "amount": d.total_hours,
        "balance_outstanding": d.difference_hours,
        "balance_unit": HOURS,
    }


def _proposal(_: Session, m: Any) -> dict[str, Any]:
    """Meter corrections, classifications and non-revenue approvals share these columns."""
    return {
        "recorded_by": m.proposed_by,
        "recorded_at": m.proposed_at,
        "decided_by": m.decided_by,
        "decided_at": m.decided_at,
        "machine_id": m.machine_id,
        "amount": getattr(m, "hours", None),
    }


def _reset(_: Session, m: MeterResetEvent) -> dict[str, Any]:
    return {
        "recorded_by": m.requested_by,
        "recorded_at": m.created_at,
        "decided_by": m.decided_by,
        "decided_at": m.decided_at,
        "machine_id": m.machine_id,
    }


def _difference(_: Session, d: RevenueDifference) -> dict[str, Any]:
    final = d.status not in (RevenueDifferenceStatus.OPEN, RevenueDifferenceStatus.EXPLANATION_PROPOSED)
    return {
        "recorded_by": d.explained_by,
        "recorded_at": d.opened_at,
        "decided_by": d.decided_by,
        "decided_at": d.decided_at,
        "machine_id": d.machine_id,
        "amount": d.difference,
        "currency": d.currency,
        "balance_outstanding": ZERO if final else abs(d.difference),
        "balance_unit": MONEY,
    }


def _cancellation(_: Session, c: HoursCancellation) -> dict[str, Any]:
    return {
        "recorded_by": c.requested_by,
        "recorded_at": c.requested_at,
        "decided_by": c.decided_by,
        "decided_at": c.decided_at,
    }


def _expense_approval(_: Session, a: ApprovalRequest) -> dict[str, Any]:
    return {
        "recorded_by": a.requested_by,
        "recorded_at": a.requested_at,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at,
        "amount": a.amount,
        "currency": a.currency,
    }


def _expense(_: Session, e: Expense) -> dict[str, Any]:
    return {
        "recorded_by": e.submitted_by,
        "recorded_at": e.submitted_at,
        "decided_by": e.decided_by,
        "decided_at": e.decided_at,
        "machine_id": e.machine_id,
        "staff_member_id": e.custodian_staff_id,
        "amount": e.amount,
        "currency": e.currency,
    }


@dataclass(frozen=True)
class Target:
    record_type: str
    model: Any
    describe: Callable[[Session, Any], dict[str, Any]]
    number: Any = None  # the record's own generated number
    outside: Any = None  # a reference only the outside system issues (bank, mobile money)


TARGETS = (
    Target("hours_purchase", HoursPurchase, _purchase, HoursPurchase.purchase_number),
    Target("hire_invoice", TenantHireInvoice, _invoice, TenantHireInvoice.invoice_number),
    Target("job", Job, _job, Job.job_number),
    Target("customer_payment", CustomerPayment, _payment, CustomerPayment.collection_number, CustomerPayment.reference),
    Target("cash_handover", CashHandover, _handover, CashHandover.remittance_number, CashHandover.reference),
    Target("cash_transfer", CashTransfer, _transfer, CashTransfer.transfer_number),
    Target("hours_transfer", HoursTransfer, _hours_transfer, HoursTransfer.transfer_number),
    Target("cash_retention", CashRetention, _retention, CashRetention.retention_number),
    Target("custody_adjustment", CustodyAdjustment, _custody_adjustment, CustodyAdjustment.adjustment_number),
    Target("adjustment_request", AdjustmentRequest, _request, AdjustmentRequest.request_number),
    Target("adjustment_entry", AdjustmentLedgerEntry, _entry, AdjustmentLedgerEntry.entry_number),
    Target("anomaly_case", AnomalyCase, _case, AnomalyCase.case_number),
    # Reachable by record id only: they have no number of their own.
    Target("cash_variance", CashVariance, _variance),
    Target("daily_report", DailyOperationalReport, _report),
    Target("meter_correction", MeterCorrection, _proposal),
    Target("classification", EngineHourClassification, _proposal),
    Target("non_revenue_approval", NonRevenueApproval, _proposal),
    Target("meter_reset", MeterResetEvent, _reset),
    Target("revenue_difference", RevenueDifference, _difference),
    Target("hours_cancellation", HoursCancellation, _cancellation),
    Target("approval_request", ApprovalRequest, _expense_approval),
    Target("expense", Expense, _expense),
)
_BY_TYPE = {t.record_type: t for t in TARGETS}
_UUID = UUID(as_uuid=True)
MAX_MATCHES = 20


def _as_uuid(text: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def _find(s: Session, reference: str) -> list[tuple[str, uuid.UUID]]:
    record_id = _as_uuid(reference)
    parts = []
    for t in TARGETS:
        if record_id is not None:
            cond = t.model.id == record_id
        elif t.number is None:
            continue
        else:
            # Numbers are generated in capitals, so a phone keyboard's lower case still finds them; outside references
            # are matched exactly as the bank wrote them.
            cond = t.number.in_({reference, reference.upper()})
            if t.outside is not None:
                cond = or_(cond, t.outside == reference)
        parts.append(select(literal(t.record_type, String).label("t"), cast(t.model.id, _UUID).label("i")).where(cond))
    rows = s.execute(union_all(*parts).limit(MAX_MATCHES)).all()
    return [(str(row[0]), row[1]) for row in rows]


def lookup(s: Session, reference: str) -> LookupResultDto:
    term = reference.strip()
    matches = []
    for record_type, record_id in _find(s, term):
        target = _BY_TYPE[record_type]
        row = s.get(target.model, record_id)
        if row is None:
            continue
        details = target.describe(s, row)
        if "status" not in details:
            details["status"] = getattr(row.status, "value", row.status)
        matches.append(
            LookupMatchDto(
                record_type=record_type,
                id=record_id,
                reference=getattr(row, target.number.key) if target.number is not None else None,
                route=record_route(record_type, record_id),
                **details,
            )
        )
    return LookupResultDto(reference=term, matches=matches)
