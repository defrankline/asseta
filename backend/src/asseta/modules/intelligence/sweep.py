"""Detector orchestration for one tenant (always in that tenant's RLS scope): the periodic sweep re-examines the
policy lookback window; `handle_event` runs the cheap event-driven checks for a single domain event. Both are
idempotent (risk-signal dedupe keys, one case link per source)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.geospatial.models import TrackingAlert
from asseta.modules.intelligence.detectors_asset_safety import detect_engine_without_work, detect_machine_fuel
from asseta.modules.intelligence.detectors_engine_hours import (
    detect_aged_unexplained_hours,
    refresh_engine_hour_flags,
)
from asseta.modules.intelligence.detectors_finance import (
    detect_cash_not_handed_over,
    detect_duplicate_receipts,
    detect_expense_threshold,
    detect_fuel_allowance,
)
from asseta.modules.intelligence.detectors_telemetry import detect_engine_activity
from asseta.modules.intelligence.detectors_work import detect_work_without_authorization
from asseta.modules.intelligence.linking import CaseLinker
from asseta.modules.intelligence.models import CaseSourceType
from asseta.modules.intelligence.rules import SignalFinding
from asseta.modules.intelligence.sources import (
    SOD_EVENT,
    link_open_signals,
    link_sources,
    meter_exception_item,
    sod_item,
    store_findings,
    tracking_alert_item,
)
from asseta.modules.meter.models import JobException
from asseta.modules.policy.service import PolicyService


@dataclass
class IntelligenceSweepResult:
    signals: int = 0
    linked: int = 0
    cases_opened: int = 0
    cases_escalated: int = 0


def _finish(s: Session, tenant_id: uuid.UUID, findings: list[SignalFinding], linker: CaseLinker, now: datetime) -> int:
    added = store_findings(s, tenant_id, now, findings)
    link_open_signals(s, linker)
    return added


def _result(added: int, linker: CaseLinker) -> IntelligenceSweepResult:
    st = linker.stats
    return IntelligenceSweepResult(added, st.linked, len(st.opened), len(st.escalated))


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> IntelligenceSweepResult:
    eff = PolicyService(s).fraud_controls(tenant_id, at=now)
    since = now - timedelta(hours=eff.policy.detection_lookback_hours)
    findings = [
        *detect_engine_activity(s, tenant_id, now, since),
        *detect_duplicate_receipts(s, eff, since),
        *detect_fuel_allowance(s, tenant_id, since),
        *detect_expense_threshold(s, tenant_id, now, since),
        *detect_cash_not_handed_over(s, tenant_id, now, eff),
        *detect_work_without_authorization(s, eff, since),
    ]
    refresh_engine_hour_flags(s, tenant_id, now)
    findings += detect_aged_unexplained_hours(s, tenant_id, now)
    findings += detect_engine_without_work(s, tenant_id, now, since)
    findings += detect_machine_fuel(s, tenant_id, now, since)
    linker = CaseLinker(s, tenant_id, now, eff.policy.case_grouping_window_hours)
    added = _finish(s, tenant_id, findings, linker, now)
    link_sources(s, linker, since, eff.version_stamp)
    return _result(added, linker)


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def handle_event(
    s: Session, tenant_id: uuid.UUID, now: datetime, event_id: uuid.UUID, event_type: str, payload: dict[str, Any]
) -> IntelligenceSweepResult:
    """Event-driven detection for one outbox event; unknown event types are ignored."""
    eff = PolicyService(s).fraud_controls(tenant_id, at=now)
    linker = CaseLinker(s, tenant_id, now, eff.policy.case_grouping_window_hours)
    since = now - timedelta(hours=eff.policy.detection_lookback_hours)
    added = 0
    if event_type == "ExpenseSubmitted" and (expense_id := _uuid(payload.get("expense_id"))):
        findings = [
            *detect_duplicate_receipts(s, eff, since, {expense_id}),
            *detect_work_without_authorization(s, eff, since, {expense_id}),
        ]
        added = _finish(s, tenant_id, findings, linker, now)
    elif event_type == "TrackingAlertRaised" and (alert_id := _uuid(payload.get("alert_id"))):
        alert = s.get(TrackingAlert, alert_id)
        if alert and (item := tracking_alert_item(s, alert, eff.version_stamp)):
            linker.link(item)
    elif event_type == "MeterExceptionRaised" and (capture_id := _uuid(payload.get("capture_id"))):
        for e in s.execute(select(JobException).where(JobException.meter_capture_id == capture_id)).scalars():
            if item := meter_exception_item(s, e, eff.version_stamp):
                linker.link(item)
    elif event_type == SOD_EVENT and not linker.already_linked(CaseSourceType.SOD_EVENT, event_id):
        if item := sod_item(s, event_id, now, payload, eff.version_stamp):
            linker.link(item)
    return _result(added, linker)
