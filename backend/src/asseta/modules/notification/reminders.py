"""Scheduled reminders (DEC-022). Each reminder's dedupe key carries its period (tenant-local date), so re-running the
scheduler any number of times in a day notifies once; the next day it reminds again while the condition holds.
Business reads run in the tenant's RLS scope; commercial checks that need platform policy run in SYSTEM scope
filtered by tenant."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import Exists, func, select
from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.modules.expenses.models import ApprovalRequest, ApprovalStatus
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.models import (
    CustomerPayment,
    HireInvoiceStatus,
    HirePaymentAllocation,
    SettlementStatus,
    TenantHireInvoice,
)
from asseta.modules.fleet.models import AssignmentRole, MachineAssignment, StaffKind, StaffMember
from asseta.modules.geospatial.models import AlertStatus, AlertType, TrackingAlert
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.meter.engine_hours import missing_daily_reports
from asseta.modules.meter.models import CaptureState, MeterCapture, ReadingKind
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.realtime import RealtimePublisher
from asseta.modules.notification.rules import Intent, perm, platform, staff
from asseta.modules.notification.settings import NotificationSettings, get_notification_settings
from asseta.modules.platform_billing.enums import BILLABLE_STATUSES, InvoiceStatus
from asseta.modules.platform_billing.models_catalog import SmsWalletEntry
from asseta.modules.platform_billing.models_ledger import PlatformInvoice
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.sms_wallet import SmsWalletService
from asseta.modules.tenancy.models import Tenant, TenantSettings, TenantStatus

log = structlog.get_logger()
OPEN_INVOICE = (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID)


@dataclass
class ReminderSummary:
    tenants: int = 0
    notifications: int = 0
    failures: int = 0


class TenantReminders:
    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime, cfg: NotificationSettings):
        self._s, self._tid, self._now, self._cfg = s, tenant_id, now, cfg
        ts = s.get(TenantSettings, tenant_id)
        self._local = now.astimezone(ZoneInfo(ts.timezone if ts else cfg.platform_timezone))
        self.day: date = self._local.date()

    def _k(self, rule: str, subject: object) -> str:
        return f"rem:{rule}:{subject}:{self.day.isoformat()}"

    def tenant_scoped(self) -> list[Intent]:
        out: list[Intent] = []
        for fn in (
            self._platform_invoices,
            self._hire_overdue,
            self._cash,
            self._approvals,
            self._trackers,
            self._jobs,
            self._daily_reports,
        ):
            out += fn()
        return out

    def _platform_invoices(self) -> list[Intent]:
        out = []
        rows = self._s.execute(
            select(PlatformInvoice).where(PlatformInvoice.status.in_(OPEN_INVOICE), PlatformInvoice.balance > 0)
        ).scalars()
        for inv in rows:
            days = (inv.due_date - self.day).days
            money = f"{inv.currency} {inv.balance.normalize():f}"
            if days < 0:
                out.append(
                    Intent(
                        "PLATFORM_INVOICE_OVERDUE",
                        (perm("tenant.billing.read"),),
                        f"Asseta invoice {inv.invoice_number} is overdue",
                        f"{money} was due {inv.due_date} ({-days} days ago).",
                        self._k("inv-overdue", inv.id),
                        "/tenant/subscription",
                        "platform_invoice",
                        str(inv.id),
                    )
                )
            elif days <= self._cfg.invoice_due_soon_days:
                out.append(
                    Intent(
                        "PLATFORM_INVOICE_DUE_SOON",
                        (perm("tenant.billing.read"),),
                        f"Asseta invoice {inv.invoice_number} due {inv.due_date}",
                        f"{money} is due in {days} day(s).",
                        self._k("inv-due", inv.id),
                        "/tenant/subscription",
                        "platform_invoice",
                        str(inv.id),
                    )
                )
        return out

    def _hire_overdue(self) -> list[Intent]:
        paid = (
            select(func.coalesce(func.sum(HirePaymentAllocation.amount), 0))
            .join(CustomerPayment, CustomerPayment.id == HirePaymentAllocation.payment_id)
            .where(
                HirePaymentAllocation.invoice_id == TenantHireInvoice.id,
                HirePaymentAllocation.released_at.is_(None),
                CustomerPayment.status == SettlementStatus.VERIFIED,
            )
            .scalar_subquery()
        )
        count = self._s.execute(
            select(func.count()).where(
                TenantHireInvoice.status == HireInvoiceStatus.ISSUED,
                TenantHireInvoice.due_date < self.day,
                TenantHireInvoice.total > paid,
            )
        ).scalar_one()
        if not count:
            return []
        return [
            Intent(
                "HIRE_INVOICE_OVERDUE",
                (perm("tenant.finance.payment"),),
                "Customer invoices overdue",
                f"{count} customer invoice(s) are past their due date.",
                self._k("hire-overdue", self._tid),
                "/tenant/hire-invoices",
                "hire_invoice",
                None,
                data={"count": count},
            )
        ]

    def _cash(self) -> list[Intent]:
        if self._local.hour < self._cfg.cash_handover_cutoff_hour:
            return []
        ctx = RequestContext(uuid.UUID(int=0), "system:reminders", DbScope.TENANT, self._tid, frozenset(), frozenset())
        custody = CashCustodyService(self._s, ctx, self._now)
        out = []
        for sup in self._s.execute(
            select(StaffMember).where(StaffMember.kind == StaffKind.SUPERVISOR, StaffMember.is_active.is_(True))
        ).scalars():
            for bal in custody.balances(sup.id):
                if bal.outstanding > Decimal(0):
                    out.append(
                        Intent(
                            "CASH_NOT_HANDED_OVER",
                            (staff(sup.id), perm("tenant.finance.verify")),
                            f"Cash not handed over: {sup.full_name}",
                            f"{bal.currency} {bal.outstanding.normalize():f} is still held at end of day.",
                            self._k(f"cash-{bal.currency}", sup.id),
                            "/tenant/cash/custody",
                            "staff_member",
                            str(sup.id),
                        )
                    )
        return out

    def _approvals(self) -> list[Intent]:
        cutoff = self._now - timedelta(hours=self._cfg.approval_pending_hours)
        rows = self._s.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.status == ApprovalStatus.PENDING, ApprovalRequest.requested_at < cutoff
            )
        ).scalars()
        return [
            Intent(
                "APPROVAL_PENDING_AGING",
                (perm("tenant.approval.expense"),),
                "Approval still waiting",
                f"{r.currency} {r.amount.normalize():f} has waited over {self._cfg.approval_pending_hours} hours.",
                self._k("approval", r.id),
                "/tenant/approvals",
                "approval",
                str(r.id),
            )
            for r in rows
        ]

    def _trackers(self) -> list[Intent]:
        count = self._s.execute(
            select(func.count(func.distinct(TrackingAlert.machine_id))).where(
                TrackingAlert.alert_type.in_([AlertType.TRACKER_STALE, AlertType.TRACKER_OFFLINE]),
                TrackingAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
        ).scalar_one()
        if not count:
            return []
        return [
            Intent(
                "TRACKERS_STALE",
                (perm("tenant.tracker.read"),),
                "Trackers not reporting",
                f"{count} machine(s) have stale or offline trackers.",
                self._k("trackers", self._tid),
                "/tenant/trackers",
                "tracker",
                None,
                data={"count": count},
            )
        ]

    def _jobs(self) -> list[Intent]:
        stale = self._now - timedelta(hours=self._cfg.job_missing_reading_hours)
        live = (CaptureState.ACCEPTED, CaptureState.PROVISIONAL)

        def has(kind: ReadingKind) -> Exists:
            return (
                select(MeterCapture.id)
                .where(MeterCapture.job_id == Job.id, MeterCapture.kind == kind, MeterCapture.state.in_(live))
                .exists()
            )

        opening = select(Job).where(
            Job.status == JobStatus.APPROVED, Job.planned_start < stale, ~has(ReadingKind.OPENING)
        )
        closing = select(Job).where(
            Job.status == JobStatus.IN_PROGRESS,
            Job.planned_end.is_not(None),
            Job.planned_end < stale,
            ~has(ReadingKind.CLOSING),
        )
        out = []
        for which, stmt in (("opening", opening), ("closing", closing)):
            for job in self._s.execute(stmt).scalars():
                audiences = (perm("tenant.job.approve"),) + ((staff(job.supervisor_id),) if job.supervisor_id else ())
                out.append(
                    Intent(
                        "JOB_MISSING_READINGS",
                        audiences,
                        f"Job {job.job_number}: {which} reading missing",
                        f"No {which} meter reading after {self._cfg.job_missing_reading_hours} hours.",
                        self._k(f"job-{which}", job.id),
                        f"/tenant/jobs/{job.id}",
                        "job",
                        str(job.id),
                    )
                )
        return out

    def _daily_reports(self) -> list[Intent]:
        """Working machines without a reading by the tenant's daily-report cut-off (engine-hour policy)."""
        out = []
        for miss in missing_daily_reports(self._s, self._tid, self._now):
            supervisors = self._s.execute(
                select(MachineAssignment.staff_member_id).where(
                    MachineAssignment.machine_id == miss.machine_id,
                    MachineAssignment.role == AssignmentRole.SUPERVISOR,
                    MachineAssignment.effective_to.is_(None),
                )
            ).scalars()
            out.append(
                Intent(
                    "MISSING_DAILY_REPORT",
                    (perm("tenant.meter.review"), *(staff(s) for s in supervisors)),
                    f"Daily report missing: {miss.machine_code}",
                    f"{miss.machine_name} worked on {miss.day} but has no meter reading before "
                    f"{miss.cutoff_hour:02d}:00.",
                    self._k("daily-report", f"{miss.machine_id}:{miss.day.isoformat()}"),
                    f"/tenant/engine-hours/machines/{miss.machine_id}",
                    "machine",
                    str(miss.machine_id),
                    data={"day": miss.day.isoformat(), "basis": miss.basis},
                )
            )
        return out

    def system_scoped(self) -> list[Intent]:
        """Wallet and upcoming entitlement restriction (needs platform policy): SYSTEM scope, this tenant only."""
        out: list[Intent] = []
        wallet = SmsWalletService(self._s)
        balance = wallet.balance(self._tid)
        if balance < self._cfg.sms_wallet_low_threshold and self._has_wallet():
            out.append(
                Intent(
                    "SMS_WALLET_LOW",
                    (perm("tenant.billing.read"),),
                    "SMS credits running low",
                    f"{balance} SMS credits left.",
                    self._k("wallet-low", self._tid),
                    "/tenant/sms-wallet",
                    "sms_wallet",
                    str(self._tid),
                )
            )
        repo = BillingRepository(self._s)
        sub = repo.current_subscription_for_tenant(self._tid)
        if sub is None or sub.status not in BILLABLE_STATUSES or sub.manually_suspended:
            return out
        overdue_since = repo.oldest_overdue_due_date(self._tid, self.day)
        if overdue_since is None:
            return out
        policy = repo.entitlement_policy(self._tid, self.day)
        overdue = (self.day - overdue_since).days
        for limit, what in ((policy.grace_days, "past due"), (policy.suspend_after_days, "suspended")):
            left = limit + 1 - overdue
            if 0 < left <= self._cfg.restriction_warning_days:
                out.append(
                    Intent(
                        "SUBSCRIPTION_RESTRICTION_UPCOMING",
                        (perm("tenant.billing.read"),),
                        f"Subscription will be {what} in {left} day(s)",
                        "Pay the overdue Asseta invoice to keep full access.",
                        self._k(f"restrict-{what}", self._tid),
                        "/tenant/subscription",
                        "subscription",
                        str(sub.id),
                    )
                )
        return out

    def _has_wallet(self) -> bool:
        return (
            self._s.execute(select(SmsWalletEntry.id).where(SmsWalletEntry.tenant_id == self._tid).limit(1)).first()
            is not None
        )


def platform_digest(s: Session, now: datetime, cfg: NotificationSettings) -> list[Intent]:
    """Platform staff: overdue platform invoices to chase (one per invoice per day)."""
    day = now.astimezone(ZoneInfo(cfg.platform_timezone)).date()
    rows = s.execute(
        select(PlatformInvoice, Tenant.display_name)
        .join(Tenant, Tenant.id == PlatformInvoice.tenant_id)
        .where(PlatformInvoice.status.in_(OPEN_INVOICE), PlatformInvoice.balance > 0, PlatformInvoice.due_date < day)
    ).all()
    return [
        Intent(
            "PLATFORM_INVOICE_OVERDUE",
            (platform("platform.payment.manage"),),
            f"{name}: invoice {inv.invoice_number} overdue",
            f"{inv.currency} {inv.balance.normalize():f} was due {inv.due_date}.",
            f"rem:platform-inv-overdue:{inv.id}:{day.isoformat()}",
            f"/platform/invoices/{inv.id}",
            "platform_invoice",
            str(inv.id),
        )
        for inv, name in rows
    ]


def run_reminders(
    session_factory: Callable[[], Session],
    now: datetime,
    publisher: RealtimePublisher | None = None,
    settings: NotificationSettings | None = None,
) -> ReminderSummary:
    cfg = settings or get_notification_settings()
    summary = ReminderSummary()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        summary.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                r = TenantReminders(s, tid, now, cfg)
                intents = r.tenant_scoped()
                apply_scope(s, DbScope.SYSTEM, None, None)
                intents += r.system_scoped()
                engine = NotificationEngine(s, r.day, now, cfg)
                summary.notifications += len(engine.deliver(tid, intents))
            if publisher is not None:
                engine.publish(publisher)
        except Exception:  # one tenant's failure never blocks the others
            log.exception("reminders_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.PLATFORM, None, None)
        intents = platform_digest(s, now, cfg)
        apply_scope(s, DbScope.SYSTEM, None, None)
        engine = NotificationEngine(s, now.date(), now, cfg)
        summary.notifications += len(engine.deliver(None, intents))
    if publisher is not None:
        engine.publish(publisher)
    log.info("reminders_completed", **summary.__dict__)
    return summary
