"""Engine-hour ageing [3.2.8]: an UNEXPLAINED ledger segment older than the tenant's
`unexplained_investigation_after_days` produces a signal that opens (or joins) an investigation case on the
machine. Time never reclassifies the segment: it stays UNEXPLAINED until a person's explanation is approved.
The sweep also refreshes the machine-level engine-hour flags (unexplained segments, overlaps, missing daily
reports). Runs in the tenant's RLS scope; idempotent (dedupe keys)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from asseta.modules.fleet.models import Machine
from asseta.modules.intelligence.models import RuleCode, SignalSeverity, SubjectType
from asseta.modules.intelligence.rules import SignalFinding
from asseta.modules.meter.engine_hours import EngineHoursMonitor, MachineLedger, load_machine_ledger


def refresh_engine_hour_flags(s: Session, tenant_id: uuid.UUID, now: datetime) -> int:
    monitor = EngineHoursMonitor(s, tenant_id, now)
    return monitor.flag_all() + monitor.flag_missing_daily_reports()


def _amount_finding(machine: Machine, ml: MachineLedger, now: datetime) -> SignalFinding | None:
    """[DEC-032 A6] Cumulative open unexplained hours of the machine above the tenant's amount open an investigation
    regardless of age. Each further multiple of the amount raises again (dedupe per multiple, joining the same case)."""
    amount = ml.policy.policy.unexplained_flag_amount_hours
    items = ml.open_items()
    if amount is None or not items:
        return None
    total = sum((i.explainable_hours for i in items), Decimal(0))
    if total <= amount:
        return None
    multiple = int(total // amount)
    first = items[0]
    return SignalFinding(
        rule_code=RuleCode.UNEXPLAINED_ENGINE_HOURS,
        severity=SignalSeverity.WARNING,
        subject_type=SubjectType.MACHINE,
        subject_id=machine.id,
        window_start=first.start.at,
        window_end=items[-1].end.at,
        dedupe_key=f"unexplained-amount:{machine.id}:{first.start.ref}:{multiple}",
        evidence={
            "machine_code": machine.asset_code,
            "basis": "AMOUNT",
            "hours": str(total),
            "flag_amount_hours": str(amount),
            "open_segments": len(items),
            "opened_at": first.opened_at.isoformat(),
            "age_days": (now - first.opened_at).days,
        },
        policy_version=ml.policy.version_stamp,
        machine_id=machine.id,
    )


def detect_aged_unexplained_hours(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[SignalFinding]:
    findings = []
    for machine in EngineHoursMonitor(s, tenant_id, now).baselined_machines():
        ml = load_machine_ledger(s, tenant_id, machine, now)
        if (amount := _amount_finding(machine, ml, now)) is not None:
            findings.append(amount)
        days = ml.policy.policy.unexplained_investigation_after_days
        if days is None:
            continue
        for i in ml.open_items():
            if now - i.opened_at < timedelta(days=days):
                continue
            findings.append(
                SignalFinding(
                    rule_code=RuleCode.UNEXPLAINED_ENGINE_HOURS,
                    severity=SignalSeverity.WARNING,
                    subject_type=SubjectType.MACHINE,
                    subject_id=machine.id,
                    window_start=i.start.at,
                    window_end=i.end.at,
                    dedupe_key=f"unexplained-hours:{machine.id}:{i.start.ref}:{i.end.ref}",
                    evidence={
                        "machine_code": machine.asset_code,
                        "hours": str(i.explainable_hours),
                        "start_ref": str(i.start.ref),
                        "end_ref": str(i.end.ref),
                        "start_reading": str(i.start.reading),
                        "end_reading": str(i.end.reading),
                        "opened_at": i.opened_at.isoformat(),
                        "age_days": (now - i.opened_at).days,
                        "investigation_after_days": days,
                        "classification": i.classification.value,
                    },
                    policy_version=ml.policy.version_stamp,
                    machine_id=machine.id,
                )
            )
    return findings
