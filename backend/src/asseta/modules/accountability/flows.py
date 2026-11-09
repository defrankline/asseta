"""Every proposal/decision flow in one registry (guideline section 8): what is waiting for a decision, and who proposed
or decided what. Ledger rows exist only once decided, so the pending picture has to come from each flow's own table.
One declaration per flow drives the dashboard counts, the pending list and the employee view: each is a single
UNION ALL query in the caller's RLS scope, never one query per flow or per row."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Numeric, String, and_, case, cast, func, literal, null, select, union_all
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from asseta.modules.adjustments.models import AdjustmentRequest, AdjustmentRequestStatus
from asseta.modules.expenses.models import ApprovalRequest, ApprovalStatus
from asseta.modules.finance.custody_models import (
    CashDecisionStatus,
    CashRetention,
    CashVariance,
    CustodyAdjustment,
    VarianceStatus,
)
from asseta.modules.finance.deposit_models import PartialRemittanceApproval
from asseta.modules.finance.models import CashHandover, CustomerPayment, SettlementStatus
from asseta.modules.hours.models import (
    CreditArrangement,
    CustomerDiscount,
    HoursCancellation,
    HoursTransfer,
    ProposalStatus,
    RequestStatus,
)
from asseta.modules.intelligence.models import AnomalyCase
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.meter.allocation_models import (
    AllocationStatus,
    DailyOperationalReport,
    DailyReportStatus,
    WorkAllocation,
)
from asseta.modules.meter.engine_models import (
    EngineHourClassification,
    MachineMeterBaseline,
    MeterCorrection,
    MeterProposalStatus,
)
from asseta.modules.meter.models import MeterResetEvent
from asseta.modules.policy.capabilities import (
    CASH_CUSTODY,
    CUSTOMER_HOURS,
    ENGINE_HOURS,
    INVESTIGATIONS,
    REVENUE_RECONCILIATION,
)
from asseta.modules.revenue.models import (
    NonRevenueApproval,
    NonRevenueApprovalStatus,
    RevenueDifference,
    RevenueDifferenceStatus,
)


@dataclass(frozen=True)
class Flow:
    key: str  # the dashboard's count name
    record_type: str  # links.RECORD_ROUTES key
    id: Any
    status: Any
    pending: ColumnElement[bool]
    requested_by: Any
    requested_at: Any
    decided_by: Any
    decided_at: Any
    reference: Any = None
    amount: Any = None
    unit: str | None = None  # MONEY | HOURS | READING | PERCENT
    currency: Any = None
    customer_id: Any = None
    machine_id: Any = None
    staff_member_id: Any = None
    adjustment: bool = False  # counts as a pending adjustment (section 8, not only as an approval)
    capability: str | None = None
    history: bool = True  # appears in a person's requested/decided history (False: another flow covers the row)


def _text_uuid(column: Any) -> Any:
    """One value per group: PostgreSQL has no min(uuid)."""
    return cast(func.min(cast(column, String)), UUID(as_uuid=True))


_w = WorkAllocation
_correction_groups = (
    select(
        _w.correction_group_id.label("id"),
        case(
            (func.bool_or(_w.status == AllocationStatus.PROPOSED), "PROPOSED"),
            (func.bool_or(_w.status == AllocationStatus.REJECTED), "REJECTED"),
            else_="APPROVED",
        ).label("status"),
        _text_uuid(_w.recorded_by).label("requested_by"),
        func.min(_w.created_at).label("requested_at"),
        _text_uuid(_w.decided_by).label("decided_by"),
        func.max(_w.decided_at).label("decided_at"),
        func.sum(_w.hours).label("hours"),
        _text_uuid(_w.machine_id).label("machine_id"),
        _text_uuid(_w.customer_id).label("customer_id"),
    )
    .where(_w.correction_group_id.is_not(None))
    .group_by(_w.correction_group_id)
    .subquery("correction_groups")
)
_g = _correction_groups.c

_r, _t, _c, _d, _a = AdjustmentRequest, HoursTransfer, HoursCancellation, CustomerDiscount, CreditArrangement
_mc, _cl, _mb, _mr = MeterCorrection, EngineHourClassification, MachineMeterBaseline, MeterResetEvent
_nr, _rt, _ca, _v, _pr = NonRevenueApproval, CashRetention, CustodyAdjustment, CashVariance, PartialRemittanceApproval
_ap, _p, _h, _j, _dr, _ac, _rd = (
    ApprovalRequest,
    CustomerPayment,
    CashHandover,
    Job,
    DailyOperationalReport,
    AnomalyCase,
    RevenueDifference,
)

FLOWS: tuple[Flow, ...] = (
    # --- adjustments: the proposals that post to the adjustments ledger once decided ---------------------------------
    Flow(
        "adjustment_requests", "adjustment_request", _r.id, _r.status,
        _r.status == AdjustmentRequestStatus.PROPOSED,
        _r.proposed_by, _r.proposed_at, _r.decided_by, _r.decided_at,
        reference=_r.request_number, amount=func.coalesce(_r.amount, _r.hours),
        unit="MONEY_OR_HOURS", currency=_r.currency, customer_id=_r.customer_id, machine_id=_r.machine_id,
        adjustment=True,
    ),
    Flow(
        "hours_transfers", "hours_transfer", _t.id, _t.status, _t.status == RequestStatus.PENDING,
        _t.requested_by, _t.requested_at, _t.decided_by, _t.decided_at,
        reference=_t.transfer_number, amount=_t.hours, unit="HOURS", machine_id=_t.from_machine_id,
        adjustment=True, capability=CUSTOMER_HOURS,
    ),
    Flow(
        "hours_cancellations", "hours_cancellation", _c.id, _c.status, _c.status == RequestStatus.PENDING,
        _c.requested_by, _c.requested_at, _c.decided_by, _c.decided_at,
        adjustment=True, capability=CUSTOMER_HOURS,
    ),
    Flow(
        "credit_arrangements", "credit_arrangement", _a.id, _a.status, _a.status == ProposalStatus.PROPOSED,
        _a.proposed_by, _a.proposed_at, _a.decided_by, _a.decided_at,
        amount=_a.limit_amount, unit="MONEY", currency=_a.currency, customer_id=_a.customer_id,
        adjustment=True, capability=CUSTOMER_HOURS,
    ),
    Flow(
        "meter_corrections", "meter_correction", _mc.id, _mc.status, _mc.status == MeterProposalStatus.PROPOSED,
        _mc.proposed_by, _mc.proposed_at, _mc.decided_by, _mc.decided_at,
        amount=_mc.new_reading - _mc.old_reading, unit="READING", machine_id=_mc.machine_id,
        adjustment=True, capability=ENGINE_HOURS,
    ),
    Flow(
        "allocation_corrections", "work_allocation_correction", _g.id, _g.status, _g.status == "PROPOSED",
        _g.requested_by, _g.requested_at, _g.decided_by, _g.decided_at,
        amount=_g.hours, unit="HOURS", customer_id=_g.customer_id, machine_id=_g.machine_id,
        adjustment=True, capability=ENGINE_HOURS,
    ),
    Flow(
        "classifications", "classification", _cl.id, _cl.status, _cl.status == MeterProposalStatus.PROPOSED,
        _cl.proposed_by, _cl.proposed_at, _cl.decided_by, _cl.decided_at,
        amount=_cl.hours, unit="HOURS", machine_id=_cl.machine_id,
        adjustment=True, capability=ENGINE_HOURS,
    ),
    Flow(
        "non_revenue_approvals", "non_revenue_approval", _nr.id, _nr.status,
        _nr.status == NonRevenueApprovalStatus.PROPOSED,
        _nr.proposed_by, _nr.proposed_at, _nr.decided_by, _nr.decided_at,
        amount=_nr.hours, unit="HOURS", machine_id=_nr.machine_id,
        adjustment=True, capability=REVENUE_RECONCILIATION,
    ),
    Flow(
        "custody_adjustments", "custody_adjustment", _ca.id, _ca.status, _ca.status == CashDecisionStatus.PENDING,
        _ca.created_by, _ca.created_at, _ca.decided_by, _ca.decided_at,
        reference=_ca.adjustment_number, amount=_ca.amount, unit="MONEY", currency=_ca.currency,
        staff_member_id=_ca.staff_member_id, adjustment=True, capability=CASH_CUSTODY,
    ),
    Flow(
        "write_offs", "cash_variance", _v.id, _v.status, _v.status == VarianceStatus.WRITE_OFF_PROPOSED,
        _v.proposed_by, _v.proposed_at, _v.resolved_by, _v.resolved_at,
        amount=_v.amount, unit="MONEY", currency=_v.currency, staff_member_id=_v.staff_member_id,
        adjustment=True, capability=CASH_CUSTODY, history=False,
    ),
    Flow(
        "variance_closures", "cash_variance", _v.id, _v.status, _v.status == VarianceStatus.CLOSURE_PROPOSED,
        _v.proposed_by, _v.proposed_at, _v.resolved_by, _v.resolved_at,
        amount=_v.amount, unit="MONEY", currency=_v.currency, staff_member_id=_v.staff_member_id,
        adjustment=True, capability=CASH_CUSTODY,
    ),
    # --- approvals that are not adjustments ---------------------------------------------------------------------------
    Flow(
        "discounts", "customer_discount", _d.id, _d.status, _d.status == ProposalStatus.PROPOSED,
        _d.proposed_by, _d.proposed_at, _d.decided_by, _d.decided_at,
        amount=_d.percent, unit="PERCENT", customer_id=_d.customer_id, capability=CUSTOMER_HOURS,
    ),
    Flow(
        "meter_baselines", "meter_baseline", _mb.id, _mb.status, _mb.status == MeterProposalStatus.PROPOSED,
        _mb.proposed_by, _mb.proposed_at, _mb.decided_by, _mb.decided_at,
        amount=_mb.reading, unit="READING", machine_id=_mb.machine_id, capability=ENGINE_HOURS,
    ),
    Flow(
        "meter_resets", "meter_reset", _mr.id, _mr.status, _mr.status == "PENDING",
        _mr.requested_by, _mr.created_at, _mr.decided_by, _mr.decided_at,
        amount=_mr.new_reading, unit="READING", machine_id=_mr.machine_id,
    ),
    Flow(
        "cash_retentions", "cash_retention", _rt.id, _rt.status, _rt.status == CashDecisionStatus.PENDING,
        _rt.created_by, _rt.created_at, _rt.decided_by, _rt.decided_at,
        reference=_rt.retention_number, amount=_rt.amount, unit="MONEY", currency=_rt.currency,
        staff_member_id=_rt.staff_member_id, capability=CASH_CUSTODY,
    ),
    Flow(
        "partial_reasons", "partial_remittance", _pr.handover_id, _pr.status,
        _pr.status == CashDecisionStatus.PENDING.value,
        _pr.created_by, _pr.created_at, _pr.decided_by, _pr.decided_at, capability=CASH_CUSTODY,
    ),
    Flow(
        "approval_requests", "approval_request", _ap.id, _ap.status, _ap.status == ApprovalStatus.PENDING,
        _ap.requested_by, _ap.requested_at, _ap.decided_by, _ap.decided_at,
        amount=_ap.amount, unit="MONEY", currency=_ap.currency,
    ),
    Flow(
        "payments_to_verify", "customer_payment", _p.id, _p.status, _p.status == SettlementStatus.CLAIMED,
        _p.recorded_by, _p.recorded_at, _p.verified_by, _p.verified_at,
        reference=_p.collection_number, amount=_p.amount, unit="MONEY", currency=_p.currency,
        customer_id=_p.customer_id, staff_member_id=_p.received_by_staff_id,
    ),
    Flow(
        "remittances_to_verify", "cash_handover", _h.id, _h.status, _h.status == SettlementStatus.CLAIMED,
        _h.recorded_by, _h.recorded_at, _h.verified_by, _h.verified_at,
        reference=_h.remittance_number, amount=_h.amount, unit="MONEY", currency=_h.currency,
        staff_member_id=_h.staff_member_id,
    ),
    Flow(
        "jobs_awaiting_approval", "job", _j.id, _j.status, _j.status == JobStatus.PENDING_APPROVAL,
        None, _j.created_at, _j.approved_by, _j.approved_at,
        reference=_j.job_number, machine_id=_j.machine_id, staff_member_id=_j.requested_by_staff_id,
    ),
    Flow(
        "daily_reports_to_review", "daily_report", _dr.id, _dr.status, _dr.status == DailyReportStatus.SUBMITTED,
        _dr.submitted_by, _dr.submitted_at, _dr.reviewed_by, _dr.reviewed_at,
        amount=_dr.total_hours, unit="HOURS", machine_id=_dr.machine_id, capability=ENGINE_HOURS,
    ),
    Flow(
        "case_closures", "anomaly_case", _ac.id, _ac.status, _ac.closure_proposed_at.is_not(None),
        _ac.closure_proposed_by, _ac.closure_proposed_at, _ac.resolved_by, _ac.resolved_at,
        reference=_ac.case_number, machine_id=_ac.machine_id, staff_member_id=_ac.staff_member_id,
        capability=INVESTIGATIONS,
    ),
    Flow(
        "revenue_decisions", "revenue_difference", _rd.id, _rd.status,
        _rd.status == RevenueDifferenceStatus.EXPLANATION_PROPOSED,
        _rd.explained_by, _rd.explained_at, _rd.decided_by, _rd.decided_at,
        amount=_rd.difference, unit="MONEY", currency=_rd.currency, machine_id=_rd.machine_id,
        capability=REVENUE_RECONCILIATION,
    ),
)  # fmt: skip

_UUID = UUID(as_uuid=True)
COLUMNS = (
    "key",
    "record_type",
    "id",
    "status",
    "reference",
    "requested_by",
    "requested_at",
    "decided_by",
    "decided_at",
    "amount",
    "unit",
    "currency",
    "customer_id",
    "machine_id",
    "staff_member_id",
)


def _typed(value: Any, type_: Any) -> Any:
    return cast(null() if value is None else value, type_)


def _select(f: Flow, where: ColumnElement[bool]) -> Any:
    return select(
        literal(f.key, String).label("key"),
        literal(f.record_type, String).label("record_type"),
        _typed(f.id, _UUID).label("id"),
        cast(f.status, String).label("status"),
        _typed(f.reference, String).label("reference"),
        _typed(f.requested_by, _UUID).label("requested_by"),
        f.requested_at.label("requested_at"),
        _typed(f.decided_by, _UUID).label("decided_by"),
        f.decided_at.label("decided_at"),
        _typed(f.amount, Numeric).label("amount"),
        _typed(f.unit, String).label("unit"),
        _typed(f.currency, String).label("currency"),
        _typed(f.customer_id, _UUID).label("customer_id"),
        _typed(f.machine_id, _UUID).label("machine_id"),
        _typed(f.staff_member_id, _UUID).label("staff_member_id"),
    ).where(where)


def _active(disabled: Iterable[str], adjustments_only: bool) -> list[Flow]:
    off = set(disabled)
    return [f for f in FLOWS if f.capability not in off and (f.adjustment or not adjustments_only)]


def pending_union(disabled: Iterable[str], *, adjustments_only: bool = False) -> Any:
    """Everything waiting for a decision, as one subquery with the COLUMNS above."""
    return union_all(*[_select(f, f.pending) for f in _active(disabled, adjustments_only)]).subquery("pending")


@dataclass(frozen=True)
class PendingCount:
    count: int
    oldest_at: datetime | None


def pending_counts(s: Session, disabled: Iterable[str]) -> dict[str, PendingCount]:
    """Waiting records per flow key: one query. A key is absent when nothing waits."""
    sub = pending_union(disabled)
    rows = s.execute(select(sub.c.key, func.count(), func.min(sub.c.requested_at)).group_by(sub.c.key)).all()
    return {key: PendingCount(int(n), oldest) for key, n, oldest in rows}


def adjustment_keys() -> frozenset[str]:
    return frozenset(f.key for f in FLOWS if f.adjustment)


def history(
    s: Session,
    user_id: uuid.UUID,
    side: str,
    start: datetime | None,
    end: datetime | None,
    limit: int,
    *,
    adjustments_only: bool = False,
) -> tuple[list[Any], bool]:
    """Records this login proposed (`side` = requested) or decided (decided), latest first, up to `limit`; the flag says
    more exist. One query across every flow."""
    parts = []
    for f in FLOWS:
        if not f.history or (adjustments_only and not f.adjustment):
            continue
        person, at = (f.requested_by, f.requested_at) if side == "requested" else (f.decided_by, f.decided_at)
        if person is None:
            continue
        conds: list[ColumnElement[bool]] = [person == user_id, at.is_not(None)]
        if start is not None:
            conds.append(at >= start)
        if end is not None:
            conds.append(at < end)
        parts.append(_select(f, and_(*conds)))
    sub = union_all(*parts).subquery("history")
    at_column = sub.c.requested_at if side == "requested" else sub.c.decided_at
    rows = list(s.execute(select(sub).order_by(at_column.desc(), sub.c.id).limit(limit + 1)).all())
    return rows[:limit], len(rows) > limit
