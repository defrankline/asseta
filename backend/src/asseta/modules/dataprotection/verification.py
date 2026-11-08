"""Runs and records balance verifications: on demand (tenant owner or platform) and as a scheduled sweep (policy
DATA_PROTECTION; off by default). A run only reports differences; the ledger prevails and nothing is corrected."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.modules.dataprotection.balance_checks import verify_tenant
from asseta.modules.dataprotection.balance_report import Report
from asseta.modules.dataprotection.models import BalanceVerificationRun, VerificationOutcome, VerificationTrigger
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import Tenant, TenantStatus

log = structlog.get_logger()
SWEEP = AuditActor(None, [], "scheduler")
FINDINGS_CAP = 500  # what a run stores; the summary still counts every mismatch


def _record(
    s: Session,
    report: Report,
    trigger: VerificationTrigger,
    requested_by: uuid.UUID | None,
    now: datetime,
    finished: datetime,
) -> BalanceVerificationRun:
    policy = PolicyService(s).data_protection(report.tenant_id, at=now)
    findings = report.findings[:FINDINGS_CAP]
    run = BalanceVerificationRun(
        id=uuid.uuid4(),
        tenant_id=report.tenant_id,
        trigger=trigger,
        requested_by=requested_by,
        started_at=now,
        finished_at=finished,
        outcome=VerificationOutcome.MISMATCHES if report.findings else VerificationOutcome.MATCHED,
        checked_count=report.checked_total,
        mismatch_count=len(report.findings),
        summary=report.summary(),
        findings=[f.to_json() for f in findings],
        findings_truncated=len(report.findings) > len(findings),
        policy_version=policy.version_stamp,
    )
    s.add(run)
    s.flush()
    return run


def run_verification(
    s: Session,
    tenant_id: uuid.UUID,
    trigger: VerificationTrigger,
    actor: AuditActor,
    requested_by: uuid.UUID | None,
    now: datetime,
) -> BalanceVerificationRun:
    """Verifies one tenant in the current transaction (which must be scoped to that tenant) and audits the result."""
    report = verify_tenant(s, tenant_id, now)
    run = _record(s, report, trigger, requested_by, now, now)
    AuditService(s).record(
        actor=actor,
        action="tenant.balance_verification.completed",
        entity_type="balance_verification_run",
        entity_id=run.id,
        tenant_id=tenant_id,
        after={"outcome": run.outcome.value, "checked": run.checked_count, "mismatches": run.mismatch_count},
        policy_version=run.policy_version,
    )
    if report.findings:
        log.warning(
            "balance_verification_mismatches",
            tenant_id=str(tenant_id),
            mismatches=len(report.findings),
            run=str(run.id),
        )
    return run


@dataclass
class SweepSummary:
    tenants: int = 0
    verified: int = 0
    failures: int = 0


def run_balance_verification_sweep(session_factory: Callable[[], Session], now: datetime) -> SweepSummary:
    """Tenants that opted in (DATA_PROTECTION.balance_verification_enabled), once per their configured interval."""
    summary = SweepSummary()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        summary.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                policy = PolicyService(s).data_protection(tid, at=now).policy
                if not policy.balance_verification_enabled:
                    continue
                latest = s.execute(select(func.max(BalanceVerificationRun.started_at))).scalar()
                if latest is not None and latest > now - timedelta(days=policy.balance_verification_interval_days):
                    continue
                run_verification(s, tid, VerificationTrigger.SCHEDULED, SWEEP, None, now)
                summary.verified += 1
        except Exception:
            log.exception("balance_verification_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    log.info("balance_verification_sweep_completed", **summary.__dict__)
    return summary
