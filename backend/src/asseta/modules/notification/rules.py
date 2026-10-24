"""Code-defined rules: domain event -> notification intents (type, audience, text, link). Finite and reviewable;
per-user/tenant preferences then pick channels. Lookups run in the event tenant's RLS scope.

Gate 6 seam: fraud/anomaly rules publish `AnomalyDetected` (payload: kind, severity, title, body, entity_type,
entity_id, link, audience_permission) on the outbox; the rule below turns it into notifications unchanged."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import AssignmentRole, Machine, MachineAssignment, StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.notification.types import Severity


@dataclass(frozen=True)
class DomainEvent:
    event_id: uuid.UUID
    event_type: str
    tenant_id: uuid.UUID | None
    payload: dict[str, Any]
    correlation_id: str | None = None


@dataclass(frozen=True)
class Audience:
    kind: str  # tenant_permission | tenant_role | tenant_user | tenant_staff | platform_permission
    value: str


@dataclass(frozen=True)
class Intent:
    type: str
    audiences: tuple[Audience, ...]
    title: str
    body: str
    dedupe: str
    link: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    severity: Severity | None = None  # overrides the type default (e.g. alert severity)
    data: dict[str, Any] = field(default_factory=dict)


def perm(code: str) -> Audience:
    return Audience("tenant_permission", code)


def platform(code: str) -> Audience:
    return Audience("platform_permission", code)


def user(user_id: object) -> Audience:
    return Audience("tenant_user", str(user_id))


def staff(staff_id: object) -> Audience:
    return Audience("tenant_staff", str(staff_id))


Rule = Callable[[Session, DomainEvent], list[Intent]]
RULES: dict[str, Rule] = {}


def rule(*event_types: str) -> Callable[[Rule], Rule]:
    def register(fn: Rule) -> Rule:
        for t in event_types:
            RULES[t] = fn
        return fn

    return register


def _key(e: DomainEvent, suffix: str = "") -> str:
    return f"evt:{e.event_id}{':' + suffix if suffix else ''}"


def _machine_label(session: Session, machine_id: object) -> str:
    try:
        mid = uuid.UUID(str(machine_id))
    except ValueError:
        return "a machine"
    row = session.execute(select(Machine.asset_code, Machine.name).where(Machine.id == mid)).first()
    return f"{row[0]} ({row[1]})" if row else "a machine"


def _supervisors(session: Session, machine_id: object) -> list[uuid.UUID]:
    """The supervisor(s) currently assigned to the machine: "the supervisor concerned"."""
    try:
        mid = uuid.UUID(str(machine_id))
    except ValueError:
        return []
    return list(
        session.execute(
            select(MachineAssignment.staff_member_id).where(
                MachineAssignment.machine_id == mid,
                MachineAssignment.role == AssignmentRole.SUPERVISOR,
                MachineAssignment.effective_to.is_(None),
            )
        ).scalars()
    )


# --- platform commerce ---------------------------------------------------------------------------------------------
@rule("PlatformInvoiceIssued")
def _invoice_issued(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "PLATFORM_INVOICE_ISSUED",
            (perm("tenant.billing.read"),),
            f"Asseta invoice {p['invoice_number']}",
            f"{p['currency']} {p['total']} due {p.get('due_date', 'per your agreement')}.",
            _key(e),
            "/tenant/subscription",
            "platform_invoice",
            p["invoice_id"],
        )
    ]


@rule("PlatformInvoiceVoided")
def _invoice_voided(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "PLATFORM_INVOICE_VOIDED",
            (perm("tenant.billing.read"),),
            f"Asseta invoice {p['invoice_number']} voided",
            f"Reason: {p['reason']}",
            _key(e),
            "/tenant/subscription",
            "platform_invoice",
            p["invoice_id"],
        )
    ]


@rule("PlatformPaymentRecorded")
def _payment_recorded(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "PLATFORM_PAYMENT_AWAITING_VERIFICATION",
            (platform("platform.payment.manage"),),
            "Payment awaiting verification",
            f"{p['currency']} {p['amount']} ref {p['reference']} was recorded and needs verification.",
            _key(e),
            "/platform/payments",
            "platform_payment",
            p["payment_id"],
        )
    ]


@rule("PlatformPaymentVerified")
def _payment_verified(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "PLATFORM_PAYMENT_VERIFIED",
            (perm("tenant.billing.read"),),
            "Payment received",
            f"Thank you: {p['currency']} {p['amount']} has been verified and applied.",
            _key(e),
            "/tenant/subscription",
            "platform_payment",
            p["payment_id"],
        )
    ]


@rule("PlatformInvoiceLineFulfilled")
def _fulfilled(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    credits = p.get("effect", {}).get("sms_credits")
    body = f"{credits:,} SMS credits added to your wallet." if credits else f"{p['description']} is now settled."
    return [
        Intent(
            "INVOICE_LINE_FULFILLED",
            (perm("tenant.billing.read"),),
            f"Paid: {p['description'][:120]}",
            body,
            _key(e),
            "/tenant/sms-wallet" if credits else "/tenant/subscription",
            "platform_invoice",
            p["invoice_id"],
        )
    ]


@rule("PlatformInvoiceLineReversed")
def _reversed(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    if p["status"] != "REVERSAL_FLAGGED":
        return []
    return [
        Intent(
            "FULFILMENT_REVERSAL_FLAGGED",
            (platform("platform.invoice.void"),),
            f"Review reversal on {p['invoice_number']}",
            f"Line {p['line_no']} ({p['description'][:120]}) could not be fully reversed.",
            _key(e),
            f"/platform/invoices/{p['invoice_id']}",
            "platform_invoice",
            p["invoice_id"],
        )
    ]


@rule("SubscriptionStatusChanged")
def _subscription(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    text = f"Subscription changed from {p['from']} to {p['to']} on {p['effective_date']}."
    return [
        Intent(
            "SUBSCRIPTION_STATUS_CHANGED",
            (perm("tenant.billing.read"),),
            "Subscription status changed",
            text,
            _key(e),
            "/tenant/subscription",
            "subscription",
            p["subscription_id"],
        ),
        Intent(
            "SUBSCRIPTION_STATUS_CHANGED",
            (platform("platform.subscription.manage"),),
            "Tenant subscription status changed",
            text,
            _key(e, "platform"),
            f"/platform/tenants/{e.tenant_id}",
            "subscription",
            p["subscription_id"],
        ),
    ]


# --- operations: actions -------------------------------------------------------------------------------------------
@rule("ApprovalRequested")
def _approval(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "APPROVAL_REQUESTED",
            (perm("tenant.approval.expense"),),
            "Expense approval requested",
            f"{p['currency']} {p['amount']}: {p['reason']}",
            _key(e),
            "/tenant/approvals",
            "approval",
            p["approval_id"],
        )
    ]


@rule("ExpenseApproved", "ExpenseRejected")
def _expense_decided(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    if p.get("auto") or not p.get("submitted_by"):
        return []
    verdict = "approved" if e.event_type == "ExpenseApproved" else "rejected"
    return [
        Intent(
            "EXPENSE_DECIDED",
            (user(p["submitted_by"]),),
            f"Expense {verdict}",
            f"Your expense of {p['currency']} {p['amount']} was {verdict}.",
            _key(e),
            "/tenant/expenses",
            "expense",
            p["expense_id"],
        )
    ]


def _staff_name(session: Session, staff_id: object) -> str | None:
    try:
        sid = uuid.UUID(str(staff_id))
    except ValueError:
        return None
    return session.execute(select(StaffMember.full_name).where(StaffMember.id == sid)).scalar_one_or_none()


def _site_name(session: Session, site_id: object) -> str | None:
    try:
        sid = uuid.UUID(str(site_id))
    except ValueError:
        return None
    return session.execute(select(JobSite.name).where(JobSite.id == sid)).scalar_one_or_none()


@rule("JobPendingApproval")
def _job_pending(session: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    jid = p.get("job_id")
    number = p.get("job_number", "")
    body = f"Job {number} was submitted for price approval."
    if requester := p.get("requested_by_staff_id"):
        who = _staff_name(session, requester) or "a supervisor"
        body = f"Job {number} was requested from the field by {who}."
        if note := p.get("request_note"):
            body += f" {note[:300]}"
    return [
        Intent(
            "JOB_AWAITING_APPROVAL",
            (perm("tenant.job.approve"),),
            "Job awaiting approval",
            body,
            _key(e),
            f"/tenant/jobs/{jid}" if jid else "/tenant/jobs",
            "job",
            jid,
        )
    ]


@rule("JobApproved")
def _job_approved(session: Session, e: DomainEvent) -> list[Intent]:
    """The named supervisor learns the job is theirs to start: their own request approved, or a job the office
    created and assigned to them."""
    p = e.payload
    jid, number, supervisor = p.get("job_id"), p.get("job_number", ""), p.get("supervisor_id")
    if not supervisor:
        return []
    link = f"/tenant/field/jobs/{jid}" if jid else "/tenant/field/jobs"
    if p.get("requested_by_staff_id") == supervisor:
        return [
            Intent(
                "JOB_REQUEST_APPROVED",
                (staff(supervisor),),
                f"Job {number} approved",
                f"Your job request {number} was approved; you can start it.",
                _key(e),
                link,
                "job",
                jid,
            )
        ]
    where = _machine_label(session, p.get("machine_id"))
    if p.get("job_site_id") and (site := _site_name(session, p["job_site_id"])):
        where += f" at {site}"
    return [
        Intent(
            "JOB_ASSIGNED",
            (staff(supervisor),),
            f"New job {number} assigned to you",
            f"New job {number} assigned to you: {where}.",
            _key(e),
            link,
            "job",
            jid,
        )
    ]


@rule("JobCancelled")
def _job_cancelled(_: Session, e: DomainEvent) -> list[Intent]:
    """A declined field request (or a cancelled job) reaches the supervisor it was for, with the reason."""
    p = e.payload
    jid, number, supervisor = p.get("job_id"), p.get("job_number", ""), p.get("supervisor_id")
    if not supervisor:
        return []
    requested = p.get("requested_by_staff_id") == supervisor
    verb = "declined" if requested else "cancelled"
    reason = p.get("reason") or "no reason given"
    return [
        Intent(
            "JOB_CANCELLED",
            (staff(supervisor),),
            f"Job {number} {verb}",
            f"Job {number} {verb}: {reason}",
            _key(e),
            f"/tenant/field/jobs/{jid}" if jid else "/tenant/field/jobs",
            "job",
            jid,
        )
    ]


@rule("CustomerPaymentRecorded")
def _customer_payment(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "CUSTOMER_PAYMENT_TO_VERIFY",
            (perm("tenant.finance.verify"),),
            "Customer payment to verify",
            f"{p['currency']} {p['amount']} ({p['method']}) was recorded and needs verification.",
            _key(e),
            "/tenant/customer-payments",
            "customer_payment",
            p["payment_id"],
        )
    ]


@rule("CashHandoverRecorded")
def _handover(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "CASH_HANDOVER_TO_VERIFY",
            (perm("tenant.finance.verify"),),
            "Cash handover to verify",
            f"A supervisor handed over {p['currency']} {p['amount']}; confirm receipt.",
            _key(e),
            "/tenant/cash/handovers",
            "cash_handover",
            p["handover_id"],
        )
    ]


# --- customer hours ------------------------------------------------------------------------------------------------
HOURS_LINKS = {
    "DISCOUNT": "/tenant/hours/discounts",
    "CREDIT": "/tenant/hours/credit",
    "TRANSFER": "/tenant/hours/transfers",
    "CANCELLATION": "/tenant/hours/cancellations",
}
HOURS_ENTITIES = {
    "DISCOUNT": "customer_discount",
    "CREDIT": "credit_arrangement",
    "TRANSFER": "hours_transfer",
    "CANCELLATION": "hours_cancellation",
}


@rule("HoursApprovalRequested")
def _hours_approval(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    kind = str(p.get("kind", ""))
    return [
        Intent(
            "HOURS_APPROVAL_REQUESTED",
            (perm(p["audience_permission"]),),
            "Customer hours: approval needed",
            f"{p.get('summary', '')}. The requester cannot approve it themselves.",
            _key(e),
            HOURS_LINKS.get(kind, "/tenant/hours"),
            HOURS_ENTITIES.get(kind),
            p["entity_id"],
        )
    ]


@rule("HoursApprovalDecided")
def _hours_decided(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    kind = str(p.get("kind", "")).replace("_", " ").lower()
    return [
        Intent(
            "HOURS_APPROVAL_DECIDED",
            (user(p["user_id"]),),
            f"Your {kind} request was {str(p['outcome']).lower()}",
            f"The {kind} you submitted is now {p['outcome']}.",
            _key(e),
            "/tenant/hours",
            None,
            p["entity_id"],
        )
    ]


@rule("CustomerHoursOverrun")
def _hours_overrun(session: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "HOURS_OVERRUN",
            (perm("tenant.meter.review"), perm("tenant.hours.credit_activate")),
            f"Hours beyond purchase — job {p.get('job_number', '')}",
            f"{_machine_label(session, p.get('machine_id'))}: {p['excess_hours']} of {p['billable_hours']} billable "
            "hours were not covered by activated customer hours. Activate more hours or review the exception.",
            _key(e),
            "/tenant/exceptions",
            "job_exception",
            p["exception_id"],
        )
    ]


@rule("CustomerHoursExpired")
def _hours_expired(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "HOURS_EXPIRED",
            (perm("tenant.hours.read"),),
            f"Hours expired — {p['purchase_number']}",
            f"{p['hours']} unused hours of {p['purchase_number']} passed the tenant expiry period.",
            _key(e),
            f"/tenant/hours/purchases/{p['purchase_id']}",
            "hours_purchase",
            p["purchase_id"],
        )
    ]


# --- anomalies -----------------------------------------------------------------------------------------------------
@rule("TrackingAlertRaised")
def _alert(session: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    machine = _machine_label(session, p.get("machine_id"))
    severity = Severity(p["severity"]) if p.get("severity") in Severity.__members__ else Severity.WARNING
    audiences = [perm("tenant.fleet.alert_manage")]
    audiences += [staff(s) for s in _supervisors(session, p.get("machine_id"))]
    title = f"{p['type'].replace('_', ' ').title()} — {machine}"
    return [
        Intent(
            "TRACKING_ALERT",
            tuple(audiences),
            title,
            p.get("title") or title,
            _key(e),
            "/tenant/alerts",
            "alert",
            p["alert_id"],
            severity,
            {"alert_type": p["type"]},
        )
    ]


@rule("MeterExceptionRaised")
def _meter(session: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    kinds = ", ".join(p["exception_types"])
    return [
        Intent(
            "METER_EXCEPTION",
            (perm("tenant.meter.review"),),
            "Meter reading needs review",
            f"{_machine_label(session, p.get('machine_id'))}: {kinds}.",
            _key(e),
            "/tenant/exceptions",
            "meter_capture",
            p["capture_id"],
            Severity.CRITICAL if p.get("blocking") else Severity.WARNING,
        )
    ]


@rule("SyncAnomalyDetected")
def _sync(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "SYNC_ANOMALY",
            (perm("tenant.device.manage"),),
            "Field device anomaly",
            p["detail"],
            _key(e),
            "/tenant/access",
            "device_session",
            p.get("device_session_id"),
        )
    ]


@rule("SegregationOfDutiesViolation")
def _sod(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "SOD_VIOLATION_ATTEMPT",
            (perm("tenant.access.manage"),),
            "Segregation-of-duties attempt blocked",
            f"A user tried to {p['action']} their own {p['entity_type'].replace('_', ' ')}; it was refused.",
            _key(e),
            "/tenant/access",
            p["entity_type"],
            p.get("entity_id"),
        )
    ]


@rule("AnomalyDetected")
def _anomaly(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    severity = Severity(p["severity"]) if p.get("severity") in Severity.__members__ else Severity.WARNING
    return [
        Intent(
            "ANOMALY_DETECTED",
            (perm(p.get("audience_permission", "tenant.fleet.alert_manage")),),
            p["title"],
            p.get("body", ""),
            _key(e),
            p.get("link"),
            p.get("entity_type"),
            p.get("entity_id"),
            severity,
            {"kind": p.get("kind")},
        )
    ]


@rule("MlModelDriftDetected")
def _ml_drift(_: Session, e: DomainEvent) -> list[Intent]:
    p = e.payload
    return [
        Intent(
            "ML_MODEL_DRIFT",
            (platform("platform.ml.read"),),
            f"Feature drift on {p['name']} v{p['version']}",
            p.get("summary", ""),
            _key(e),
            f"/platform/models/{p['model_version_id']}",
            "model_version",
            p["model_version_id"],
        )
    ]


# --- lightweight "entity changed" pushes (open screens refresh) ----------------------------------------------------
ENTITY_CHANGES: dict[str, tuple[str, str, str]] = {
    # event_type -> (entity, id payload key, action)
    "TrackingAlertRaised": ("alert", "alert_id", "created"),
    "PositionStored": ("fleet.position", "machine_id", "updated"),
    "ApprovalRequested": ("approval", "approval_id", "created"),
    "ExpenseApproved": ("expense", "expense_id", "approved"),
    "ExpenseRejected": ("expense", "expense_id", "rejected"),
    "CustomerPaymentRecorded": ("customer_payment", "payment_id", "created"),
    "CustomerPaymentVerified": ("customer_payment", "payment_id", "verified"),
    "CashHandoverRecorded": ("cash_handover", "handover_id", "created"),
    "CashHandoverVerified": ("cash_handover", "handover_id", "verified"),
    "HireInvoiceIssued": ("hire_invoice", "invoice_id", "issued"),
    "HoursPurchaseRecorded": ("hours_purchase", "purchase_id", "created"),
    "CustomerHoursActivated": ("hours_purchase", "purchase_id", "updated"),
    "CustomerHoursExpired": ("hours_purchase", "purchase_id", "updated"),
    "HireInvoiceVoided": ("hire_invoice", "invoice_id", "voided"),
    "MeterCaptured": ("meter_capture", "capture_id", "created"),
    "MeterExceptionRaised": ("meter_exception", "capture_id", "created"),
    "PlatformInvoiceIssued": ("platform_invoice", "invoice_id", "issued"),
    "PlatformInvoiceVoided": ("platform_invoice", "invoice_id", "voided"),
    "PlatformPaymentRecorded": ("platform_payment", "payment_id", "created"),
    "PlatformPaymentVerified": ("platform_payment", "payment_id", "verified"),
    "PlatformInvoiceLineFulfilled": ("platform_invoice", "invoice_id", "fulfilled"),
    "SubscriptionStatusChanged": ("subscription", "subscription_id", "updated"),
    "AnomalyDetected": ("case", "entity_id", "updated"),
    "CaseUpdated": ("case", "case_id", "updated"),
}
PLATFORM_ENTITY_EVENTS = frozenset(
    {
        "PlatformInvoiceIssued",
        "PlatformInvoiceVoided",
        "PlatformPaymentRecorded",
        "PlatformPaymentVerified",
        "PlatformInvoiceLineFulfilled",
        "SubscriptionStatusChanged",
    }
)


def entity_change(e: DomainEvent) -> dict[str, Any] | None:
    spec = ENTITY_CHANGES.get(e.event_type) or (
        ("job", "job_id", "updated") if e.event_type.startswith("Job") else None
    )
    if spec is None:
        return None
    entity, key, action = spec
    value = e.payload.get(key)
    return {"entity": entity, "id": str(value) if value else None, "action": action}
