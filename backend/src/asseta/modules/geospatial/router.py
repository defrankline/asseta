"""Tenant geospatial endpoints: sites, geofences, fleet map, history/playback, proximity, alerts."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session, utcnow
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.geospatial.dto import (
    AlertActionIn,
    AlertDto,
    GeofenceDto,
    GeofenceEventDto,
    GeofenceIn,
    JobSiteDto,
    JobSiteIn,
    JobSiteUpdateIn,
)
from asseta.modules.geospatial.fleet_map import FleetMapService, MachineMapDto
from asseta.modules.geospatial.history import HistoryDto, HistoryService, NearbyMachineDto
from asseta.modules.geospatial.models import AlertStatus, AlertType, TrackingAlert
from asseta.modules.geospatial.sites_service import SiteService
from asseta.modules.geospatial.timeline import TimelineProcessor
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext

FLEET_READ = requires("tenant.fleet.read", S.TENANT, "View fleet map, positions, history and alerts")
ALERT_MANAGE = requires("tenant.fleet.alert_manage", S.TENANT, "Acknowledge and resolve tracking alerts")
GEOFENCE_READ = requires("tenant.geofence.read", S.TENANT, "View job sites and geofences")
GEOFENCE_WRITE = requires("tenant.geofence.write", S.TENANT, "Manage job sites and geofences")
for menu in (
    MenuDef("tenant.fleet_map", S.TENANT, "Fleet map", "/tenant/fleet", 10, "tenant.fleet.read"),
    MenuDef("tenant.geofences", S.TENANT, "Sites & geofences", "/tenant/geofences", 50, "tenant.geofence.read"),
    MenuDef("tenant.alerts", S.TENANT, "Alerts", "/tenant/alerts", 60, "tenant.fleet.read"),
):
    CATALOG.register_menu(menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["geospatial"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
GeoRead = Annotated[RequestContext, Depends(GEOFENCE_READ)]
GeoWrite = Annotated[RequestContext, Depends(GEOFENCE_WRITE)]
MAX_HISTORY_DAYS = 31


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


@router.get("/fleet/map", response_model=list[MachineMapDto], operation_id="getFleetMap")
def fleet_map(session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(FLEET_READ)]) -> list[MachineMapDto]:
    return FleetMapService(session, _tid(ctx)).fleet(now)


@router.get("/fleet/machines/{machine_id}", response_model=MachineMapDto, operation_id="getMachineStatus")
def machine_status(
    machine_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(FLEET_READ)]
) -> MachineMapDto:
    rows = FleetMapService(session, _tid(ctx)).fleet(now, machine_id)
    if not rows:
        raise NotFound("Machine not found")
    return rows[0]


@router.get("/fleet/machines/{machine_id}/history", response_model=HistoryDto, operation_id="getMachineHistory")
def history(
    machine_id: uuid.UUID,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FLEET_READ)],
    frm: Annotated[datetime, Query(alias="from")],
    to: datetime,
) -> HistoryDto:
    if to <= frm or (to - frm).days > MAX_HISTORY_DAYS:
        raise BusinessRuleViolation(f"Range must be positive and at most {MAX_HISTORY_DAYS} days", code="BAD_RANGE")
    return HistoryService(session, _tid(ctx)).history(machine_id, frm, to)


@router.get("/fleet/nearby", response_model=list[NearbyMachineDto], operation_id="getNearbyMachines")
def nearby(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FLEET_READ)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    radius_m: Annotated[float, Query(gt=0, le=100_000)] = 1000,
) -> list[NearbyMachineDto]:
    return HistoryService(session, _tid(ctx)).nearby(lon, lat, radius_m)


@router.get("/job-sites", response_model=list[JobSiteDto], operation_id="listJobSites")
def sites(
    session: DbSession,
    ctx: GeoRead,
    q: Annotated[str | None, Query(max_length=100)] = None,
    include_inactive: IncludeInactive = False,
) -> list[JobSiteDto]:
    return SiteService(session, _tid(ctx), ctx.audit_actor()).sites(q, include_inactive)


@router.post("/job-sites", response_model=JobSiteDto, status_code=201, operation_id="createJobSite")
def create_site(
    body: JobSiteIn, session: DbSession, ctx: Annotated[RequestContext, Depends(GEOFENCE_WRITE)]
) -> JobSiteDto:
    return SiteService(session, _tid(ctx), ctx.audit_actor()).create_site(body)


@router.get("/job-sites/{site_id}", response_model=JobSiteDto, operation_id="getJobSite")
def get_site(site_id: uuid.UUID, session: DbSession, ctx: GeoRead) -> JobSiteDto:
    svc = SiteService(session, _tid(ctx), ctx.audit_actor())
    return svc.site_dto(svc.site(site_id))


@router.put("/job-sites/{site_id}", response_model=JobSiteDto, operation_id="updateJobSite")
def update_site(site_id: uuid.UUID, body: JobSiteUpdateIn, session: DbSession, ctx: GeoWrite) -> JobSiteDto:
    return SiteService(session, _tid(ctx), ctx.audit_actor()).update_site(site_id, body)


@router.post("/job-sites/{site_id}/deactivate", response_model=JobSiteDto, operation_id="deactivateJobSite")
def deactivate_site(site_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: GeoWrite) -> JobSiteDto:
    """Refused while an open job (DRAFT..IN_PROGRESS) is at the site (SITE_IN_USE)."""
    return SiteService(session, _tid(ctx), ctx.audit_actor()).set_site_active(site_id, False, body.reason, body.version)


@router.post("/job-sites/{site_id}/reactivate", response_model=JobSiteDto, operation_id="reactivateJobSite")
def reactivate_site(site_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: GeoWrite) -> JobSiteDto:
    return SiteService(session, _tid(ctx), ctx.audit_actor()).set_site_active(site_id, True, body.reason, body.version)


@router.get("/geofences", response_model=list[GeofenceDto], operation_id="listGeofences")
def geofences(session: DbSession, ctx: GeoRead, include_inactive: IncludeInactive = False) -> list[GeofenceDto]:
    return SiteService(session, _tid(ctx), ctx.audit_actor()).geofences(include_inactive)


@router.get("/geofences/{geofence_id}", response_model=GeofenceDto, operation_id="getGeofence")
def get_geofence(geofence_id: uuid.UUID, session: DbSession, ctx: GeoRead) -> GeofenceDto:
    svc = SiteService(session, _tid(ctx), ctx.audit_actor())
    return svc.to_dto(svc.geofence(geofence_id))


def _set_geofence_active(
    session: Session, ctx: RequestContext, geofence_id: uuid.UUID, active: bool, body: LifecycleChangeIn, now: datetime
) -> GeofenceDto:
    svc = SiteService(session, _tid(ctx), ctx.audit_actor())
    dto, effective = svc.set_geofence_active(geofence_id, active, body.reason, body.version, now)
    timeline = TimelineProcessor(session, _tid(ctx))
    for machine_id in svc.affected_machines(geofence_id):  # derived events from `effective` follow the change
        timeline.replay(machine_id, effective)
    return dto


@router.post("/geofences/{geofence_id}/deactivate", response_model=GeofenceDto, operation_id="deactivateGeofence")
def deactivate_geofence(
    geofence_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: GeoWrite
) -> GeofenceDto:
    """Stops alerting/evaluation from now; past enter/exit events are kept."""
    return _set_geofence_active(session, ctx, geofence_id, False, body, now)


@router.post("/geofences/{geofence_id}/reactivate", response_model=GeofenceDto, operation_id="reactivateGeofence")
def reactivate_geofence(
    geofence_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: GeoWrite
) -> GeofenceDto:
    return _set_geofence_active(session, ctx, geofence_id, True, body, now)


@router.post("/geofences", response_model=GeofenceDto, status_code=201, operation_id="createGeofence")
def create_geofence(
    body: GeofenceIn, session: DbSession, ctx: Annotated[RequestContext, Depends(GEOFENCE_WRITE)]
) -> GeofenceDto:
    return SiteService(session, _tid(ctx), ctx.audit_actor()).create_geofence(body)


@router.put("/geofences/{geofence_id}", response_model=GeofenceDto, operation_id="updateGeofence")
def update_geofence(
    geofence_id: uuid.UUID,
    body: GeofenceIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(GEOFENCE_WRITE)],
) -> GeofenceDto:
    svc = SiteService(session, _tid(ctx), ctx.audit_actor())
    dto, effective = svc.update_geofence(geofence_id, body, now)
    timeline = TimelineProcessor(session, _tid(ctx))
    for machine_id in svc.affected_machines(geofence_id):  # history before `effective` is not rewritten
        timeline.replay(machine_id, effective)
    return dto


@router.get("/geofence-events", response_model=list[GeofenceEventDto], operation_id="listGeofenceEvents")
def geofence_events(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FLEET_READ)],
    frm: Annotated[datetime, Query(alias="from")],
    to: datetime,
    machine_id: uuid.UUID | None = None,
) -> list[GeofenceEventDto]:
    rows = SiteService(session, _tid(ctx), ctx.audit_actor()).events(machine_id, frm, to)
    return [GeofenceEventDto.model_validate(r) for r in rows]


@router.get("/alerts", response_model=Page[AlertDto], operation_id="listTrackingAlerts")
def alerts(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FLEET_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: AlertStatus | None = None,
    alert_type: AlertType | None = None,
    machine_id: uuid.UUID | None = None,
) -> Page[AlertDto]:
    stmt = select(TrackingAlert).order_by(TrackingAlert.event_time.desc())
    if status:
        stmt = stmt.where(TrackingAlert.status == status)
    if alert_type:
        stmt = stmt.where(TrackingAlert.alert_type == alert_type)
    if machine_id:
        stmt = stmt.where(TrackingAlert.machine_id == machine_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[AlertDto.model_validate(a) for a in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/alerts/{alert_id}/action", response_model=AlertDto, operation_id="actOnTrackingAlert")
def alert_action(
    alert_id: uuid.UUID, body: AlertActionIn, session: DbSession, ctx: Annotated[RequestContext, Depends(ALERT_MANAGE)]
) -> AlertDto:
    alert = session.execute(
        select(TrackingAlert).where(TrackingAlert.id == alert_id).with_for_update()
    ).scalar_one_or_none()
    if alert is None:
        raise NotFound("Alert not found")
    if alert.status in (AlertStatus.RESOLVED, AlertStatus.SUPERSEDED):
        raise Conflict(f"Alert already {alert.status.value}", code="ALERT_CLOSED")
    if body.action == "ACKNOWLEDGE":
        alert.status, alert.acknowledged_by, alert.acknowledged_at = AlertStatus.ACKNOWLEDGED, ctx.user_id, utcnow()
    else:
        if not body.note:
            raise BusinessRuleViolation("Resolution note required", code="NOTE_REQUIRED")
        alert.status, alert.resolved_at, alert.resolution_note = AlertStatus.RESOLVED, utcnow(), body.note
    session.flush()
    return AlertDto.model_validate(alert)
