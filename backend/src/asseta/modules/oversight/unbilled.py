"""Unbilled work (DEC-031 M2): completed, billing-ready jobs (INVOICE billing) not on an issued invoice more than
OVERSIGHT.unbilled_after_days after completion. Read model over jobs, the job summary (billing-ready, charges) and
invoice claims — the same rule invoicing applies, never a second copy. Off while unbilled_after_days is null."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import DbScope
from asseta.core.search import ilike_any
from asseta.modules.finance.models import HireInvoiceJob, HireInvoiceStatus, TenantHireInvoice
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Customer, Job, JobStatus, RentalContract
from asseta.modules.jobs.service import JobService
from asseta.modules.oversight.dto import UnbilledJobDto
from asseta.modules.policy.schemas import BillingMode
from asseta.modules.policy.service import PolicyService


def system_ctx(tenant_id: uuid.UUID, subject: str) -> RequestContext:
    return RequestContext(uuid.UUID(int=0), subject, DbScope.TENANT, tenant_id, frozenset(), frozenset())


def unbilled_jobs(
    s: Session,
    tenant_id: uuid.UUID,
    now: datetime,
    *,
    q: str | None = None,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
) -> list[UnbilledJobDto]:
    """Oldest first. Empty while the check is off."""
    after = PolicyService(s).oversight(tenant_id, at=now).policy.unbilled_after_days
    if after is None:
        return []
    issued = (
        select(HireInvoiceJob.job_id)
        .join(TenantHireInvoice, TenantHireInvoice.id == HireInvoiceJob.invoice_id)
        .where(HireInvoiceJob.released_at.is_(None), TenantHireInvoice.status != HireInvoiceStatus.DRAFT)
    )
    stmt = (
        select(Job, RentalContract.customer_id)
        .join(RentalContract, RentalContract.id == Job.contract_id)
        .join(Customer, Customer.id == RentalContract.customer_id)
        .where(
            Job.status == JobStatus.COMPLETED,
            Job.billing_mode == BillingMode.INVOICE,
            Job.completed_at.is_not(None),
            Job.completed_at <= now - timedelta(days=after),
            Job.id.not_in(issued),
        )
        .order_by(Job.completed_at, Job.id)
    )
    if customer_id:
        stmt = stmt.where(RentalContract.customer_id == customer_id)
    if machine_id:
        stmt = stmt.where(Job.machine_id == machine_id)
    if site_id:
        stmt = stmt.where(Job.job_site_id == site_id)
    if (cond := ilike_any(q, Job.job_number, Customer.name)) is not None:
        stmt = stmt.where(cond)
    jobs = JobService(s, system_ctx(tenant_id, "system:oversight"))
    out = []
    for job, cust in s.execute(stmt).all():
        summary = jobs.summary(job.id)
        if not summary.billing_ready:
            continue
        assert job.completed_at is not None
        draft = s.execute(
            select(HireInvoiceJob.invoice_id).where(
                HireInvoiceJob.job_id == job.id, HireInvoiceJob.released_at.is_(None)
            )
        ).scalar_one_or_none()
        out.append(
            UnbilledJobDto(
                job_id=job.id,
                job_number=job.job_number,
                machine_id=job.machine_id,
                customer_id=cust,
                job_site_id=job.job_site_id,
                supervisor_staff_id=job.supervisor_id,
                completed_at=job.completed_at,
                days_unbilled=(now - job.completed_at).days,
                billable_hours=summary.billable_hours,
                currency=job.currency,
                total=summary.charges.total if summary.charges else None,
                draft_invoice_id=draft,
            )
        )
    return out
