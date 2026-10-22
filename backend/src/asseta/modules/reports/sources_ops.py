"""Operational report definitions: fleet, jobs, meter readings, alerts and utilisation. Each row source calls the
list endpoint's own query builder / service with the same filters and sort, then adds display names."""

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.geospatial.alerts import alert_list_query
from asseta.modules.geospatial.fleet_map import Connectivity, FleetMapService, filter_fleet
from asseta.modules.geospatial.models import AlertStatus, AlertType
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.insights import machine_insights
from asseta.modules.jobs.lifecycle import job_list_query
from asseta.modules.jobs.models import Customer, Job, JobStatus, RentalContract
from asseta.modules.meter.models import CaptureState, ReadingKind
from asseta.modules.meter.service import capture_list_query
from asseta.modules.reports.definitions import ReportColumn as C
from asseta.modules.reports.definitions import ReportDefinition


class _Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")


def machine_codes(session: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = session.execute(select(Machine.id, Machine.asset_code).where(Machine.id.in_(wanted))).tuples()
    return dict(rows.all())


def job_numbers(session: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return dict(session.execute(select(Job.id, Job.job_number).where(Job.id.in_(wanted))).tuples().all())


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


# --- fleet ------------------------------------------------------------------------------------------------------
class FleetReportFilters(_Filters):
    q: str | None = Field(default=None, max_length=100, description="Asset code or name contains")
    connectivity: Connectivity | None = None
    machine_status: MachineStatus | None = None


def _fleet(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, FleetReportFilters)
    status = f.machine_status.value if f.machine_status else None
    rows = filter_fleet(FleetMapService(session, _tid(ctx)).fleet(now), f.q, f.connectivity, status)
    return [r.model_dump() for r in rows[: limit + 1]]


FLEET = ReportDefinition(
    code="fleet",
    title="Fleet status",
    description="Machines with tracker connectivity, last seen, reported work and observed state",
    scope=S.TENANT,
    permission="tenant.fleet.read",
    columns=(
        C("asset_code", "Asset code"),
        C("name", "Machine", width=1.6),
        C("machine_status", "Status"),
        C("connectivity", "Connectivity"),
        C("last_message_at", "Last seen", "instant", 1.3),
        C("position_time", "Position time", "instant", 1.3),
        C("latitude", "Latitude", "decimal"),
        C("longitude", "Longitude", "decimal"),
        C("accuracy_m", "Accuracy (m)", "decimal", 0.8),
        C("reported_work_status", "Reported work"),
        C("observed_engine", "Engine (observed)", width=0.9),
        C("location_compliance", "Location"),
        C("supervisor", "Supervisor", width=1.3),
        C("open_alerts", "Open alerts", "int", 0.7),
    ),
    source=_fleet,
    filters=FleetReportFilters,
    list_operation="getFleetMap",
    notes=("Positions older than the tracking policy's live window are last-known, not live.",),
)


# --- jobs -------------------------------------------------------------------------------------------------------
class JobsReportFilters(_Filters):
    q: str | None = Field(default=None, max_length=100, description="Job number contains")
    status: JobStatus | None = None
    machine_id: uuid.UUID | None = None


def _jobs(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, JobsReportFilters)
    jobs = list(session.execute(job_list_query(f.q, f.status, f.machine_id).limit(limit + 1)).scalars())
    machines = machine_codes(session, (j.machine_id for j in jobs))
    customers = dict(
        session.execute(
            select(RentalContract.id, Customer.name)
            .join(Customer, Customer.id == RentalContract.customer_id)
            .where(RentalContract.id.in_({j.contract_id for j in jobs}))
        )
        .tuples()
        .all()
    )
    return [
        {
            "job_number": j.job_number,
            "status": j.status,
            "machine": machines.get(j.machine_id),
            "customer": customers.get(j.contract_id),
            "planned_start": j.planned_start,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "hourly_rate": j.hourly_rate,
            "currency": j.currency,
            "rate_source": j.rate_source,
        }
        for j in jobs
    ]


JOBS = ReportDefinition(
    code="jobs",
    title="Jobs",
    description="Jobs with status, machine, customer, schedule and agreed rate",
    scope=S.TENANT,
    permission="tenant.job.read",
    columns=(
        C("job_number", "Job"),
        C("status", "Status"),
        C("machine", "Machine"),
        C("customer", "Customer", width=1.6),
        C("planned_start", "Planned start", "instant", 1.2),
        C("started_at", "Started", "instant", 1.2),
        C("completed_at", "Completed", "instant", 1.2),
        C("hourly_rate", "Hourly rate", "money"),
        C("currency", "Currency", width=0.6),
        C("rate_source", "Rate source", width=1.2),
    ),
    source=_jobs,
    filters=JobsReportFilters,
    list_operation="listJobs",
)


# --- meter readings ---------------------------------------------------------------------------------------------
class ReadingsReportFilters(_Filters):
    job_id: uuid.UUID | None = None
    machine_id: uuid.UUID | None = None
    kind: ReadingKind | None = None
    state: CaptureState | None = None
    captured_from: datetime | None = None
    captured_to: datetime | None = Field(default=None, description="Exclusive")


def _readings(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, ReadingsReportFilters)
    stmt = capture_list_query(f.job_id, f.machine_id, f.kind, f.state, f.captured_from, f.captured_to)
    captures = list(session.execute(stmt.limit(limit + 1)).scalars())
    machines = machine_codes(session, (c.machine_id for c in captures))
    jobs = job_numbers(session, (c.job_id for c in captures))
    return [
        {
            "captured_at": c.captured_at,
            "machine": machines.get(c.machine_id),
            "job": jobs.get(c.job_id),
            "kind": c.kind,
            "reading": c.reading,
            "capture_mode": c.capture_mode,
            "ocr_value": c.ocr_value,
            "ocr_confidence": None if c.ocr_confidence is None else round(c.ocr_confidence, 3),
            "manually_corrected": c.manually_corrected,
            "gps_status": c.gps_status,
            "accuracy_m": c.accuracy_m,
            "state": c.state,
            "received_at": c.received_at,
        }
        for c in captures
    ]


READINGS = ReportDefinition(
    code="readings",
    title="Meter readings",
    description="Opening/closing hour-meter readings with OCR, GPS evidence status and review state",
    scope=S.TENANT,
    permission="tenant.meter.read",
    columns=(
        C("captured_at", "Captured", "instant", 1.2),
        C("machine", "Machine"),
        C("job", "Job"),
        C("kind", "Kind", width=0.8),
        C("reading", "Reading", "decimal"),
        C("capture_mode", "Mode", width=0.8),
        C("ocr_value", "OCR value", "decimal"),
        C("ocr_confidence", "OCR confidence", "decimal", 0.8),
        C("manually_corrected", "Corrected", "bool", 0.7),
        C("gps_status", "GPS", width=0.8),
        C("accuracy_m", "GPS accuracy (m)", "decimal", 0.8),
        C("state", "State"),
        C("received_at", "Received", "instant", 1.2),
    ),
    source=_readings,
    filters=ReadingsReportFilters,
    list_operation="listMeterCaptures",
)


# --- alerts -----------------------------------------------------------------------------------------------------
class AlertsReportFilters(_Filters):
    status: AlertStatus | None = None
    alert_type: AlertType | None = None
    machine_id: uuid.UUID | None = None


def _alerts(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, AlertsReportFilters)
    alerts = list(session.execute(alert_list_query(f.status, f.alert_type, f.machine_id).limit(limit + 1)).scalars())
    machines = machine_codes(session, (a.machine_id for a in alerts))
    return [
        {
            "event_time": a.event_time,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "status": a.status,
            "machine": machines.get(a.machine_id) if a.machine_id else None,
            "title": a.title,
            "acknowledged_at": a.acknowledged_at,
            "resolved_at": a.resolved_at,
            "resolution_note": a.resolution_note,
        }
        for a in alerts
    ]


ALERTS = ReportDefinition(
    code="alerts",
    title="Tracking alerts",
    description="Geofence, tamper, power, GPS and connectivity alerts with their handling",
    scope=S.TENANT,
    permission="tenant.fleet.read",
    columns=(
        C("event_time", "Event time", "instant", 1.2),
        C("alert_type", "Type", width=1.2),
        C("severity", "Severity", width=0.8),
        C("status", "Status", width=0.9),
        C("machine", "Machine"),
        C("title", "Title", width=2.6),
        C("acknowledged_at", "Acknowledged", "instant", 1.2),
        C("resolved_at", "Resolved", "instant", 1.2),
        C("resolution_note", "Resolution note", width=1.8),
    ),
    source=_alerts,
    filters=AlertsReportFilters,
    list_operation="listTrackingAlerts",
)


# --- utilisation ------------------------------------------------------------------------------------------------
class UtilisationReportFilters(_Filters):
    pass


def _utilisation(
    session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int
) -> list[dict[str, Any]]:
    _, items = machine_insights(session, _tid(ctx), now)
    return [
        {
            "asset_code": u.asset_code,
            "machine_name": u.machine_name,
            "status": u.status,
            "weeks_observed": u.weeks_observed,
            "hours_observed": round(sum(w.hours for w in u.weekly), 2),
            "hours_per_available_day": u.hours_per_available_day,
            "trend": u.trend,
            "trend_hours_per_week": u.trend_hours_per_week,
            "message": u.message,
        }
        for u in items[: limit + 1]
    ]


UTILISATION = ReportDefinition(
    code="utilisation",
    title="Machine utilisation",
    description="Weekly worked hours per machine (meter, else engine hours) over the last 12 weeks, with trend",
    scope=S.TENANT,
    permission="tenant.fleet.read",
    columns=(
        C("asset_code", "Asset code"),
        C("machine_name", "Machine", width=1.5),
        C("status", "Status", width=1.2),
        C("weeks_observed", "Weeks observed", "int", 0.8),
        C("hours_observed", "Hours observed", "decimal", 0.9),
        C("hours_per_available_day", "Hours / day", "decimal", 0.8),
        C("trend", "Trend", width=0.6),
        C("trend_hours_per_week", "Trend h/week", "decimal", 0.8),
        C("message", "Note", width=3.0),
    ),
    source=_utilisation,
    filters=UtilisationReportFilters,
    list_operation="getTenantInsights",
    notes=("Insights with too little history are INSUFFICIENT_DATA, never estimated.",),
)
