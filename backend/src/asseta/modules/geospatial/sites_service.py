"""Job sites and geofences (tenant scope). Areas are stored as geography for metre-correct distance/tolerance."""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.search import ilike_any
from asseta.modules.fleet.models import Machine
from asseta.modules.geospatial.dto import GeofenceDto, GeofenceIn, GeoPoint, JobSiteDto, JobSiteIn, JobSiteUpdateIn
from asseta.modules.geospatial.models import Geofence, GeofenceEvent, GeofenceMachine, GeofenceShape, JobSite
from asseta.modules.jobs.models import Job, JobStatus

OPEN_JOB_STATES = (JobStatus.DRAFT, JobStatus.PENDING_APPROVAL, JobStatus.APPROVED, JobStatus.IN_PROGRESS)


class SiteService:
    def __init__(self, session: Session, tenant_id: uuid.UUID, actor: AuditActor):
        self._s, self._tenant_id, self._actor = session, tenant_id, actor

    # --- sites ----------------------------------------------------------------------------------------
    def site_dto(self, site: JobSite) -> JobSiteDto:
        lon, lat = self._s.execute(select(func.ST_X(site.center), func.ST_Y(site.center))).one()
        return JobSiteDto(
            id=site.id,
            code=site.code,
            name=site.name,
            address=site.address,
            center=GeoPoint(coordinates=(lon, lat)),
            is_active=site.is_active,
            version=site.version,
            deactivated_at=site.deactivated_at,
            deactivation_reason=site.deactivation_reason,
        )

    def create_site(self, body: JobSiteIn) -> JobSiteDto:
        lon, lat = body.center.coordinates
        site = JobSite(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            code=body.code,
            name=body.name,
            address=body.address,
            center=func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
        )
        try:
            with self._s.begin_nested():
                self._s.add(site)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("Site code already exists", code="DUPLICATE_SITE") from exc
        self._s.refresh(site)
        dto = self.site_dto(site)
        self._audit("geospatial.site.created", "job_site", site.id, None, dto.model_dump(mode="json"))
        return dto

    def sites(self, q: str | None = None, include_inactive: bool = False) -> list[JobSiteDto]:
        stmt = select(JobSite).order_by(JobSite.code)
        if (match := ilike_any(q, JobSite.code, JobSite.name)) is not None:
            stmt = stmt.where(match)
        if not include_inactive:
            stmt = stmt.where(JobSite.is_active.is_(True))
        return [self.site_dto(s) for s in self._s.execute(stmt).scalars()]

    def site(self, site_id: uuid.UUID, lock: bool = False) -> JobSite:
        stmt = select(JobSite).where(JobSite.id == site_id)
        site = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if site is None:  # other tenants' sites are invisible under RLS
            raise NotFound("Job site not found")
        return site

    def update_site(self, site_id: uuid.UUID, body: JobSiteUpdateIn) -> JobSiteDto:
        site = self.site(site_id, lock=True)
        check_version(site.version, body.version, "Job site")
        before = self.site_dto(site).model_dump(mode="json")
        lon, lat = body.center.coordinates
        site.code, site.name, site.address = body.code, body.name, body.address
        site.center = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        flush_versioned(self._s, "Job site", "DUPLICATE_SITE", "Site code already exists")
        self._s.refresh(site)
        dto = self.site_dto(site)
        self._audit("geospatial.site.updated", "job_site", site.id, before, dto.model_dump(mode="json"))
        return dto

    def set_site_active(self, site_id: uuid.UUID, active: bool, reason: str, version: int | None) -> JobSiteDto:
        """Deactivation is refused while an open job (DRAFT..IN_PROGRESS) is at the site; geofences, contracts and
        history keep referencing it."""
        site = self.site(site_id, lock=True)
        check_version(site.version, version, "Job site")
        if active:
            mark_active(site, "Job site")
        else:
            in_use = self._s.execute(
                select(Job.id).where(Job.job_site_id == site.id, Job.status.in_(OPEN_JOB_STATES))
            ).first()
            if in_use is not None:
                raise BusinessRuleViolation("Job site has open jobs; complete or move them first", code="SITE_IN_USE")
            mark_inactive(site, self._actor.user_id, reason, "Job site")
        flush_versioned(self._s, "Job site")
        self._s.refresh(site)
        dto = self.site_dto(site)
        verb = "reactivated" if active else "deactivated"
        self._audit(f"geospatial.site.{verb}", "job_site", site.id, None, dto.model_dump(mode="json"), reason)
        return dto

    def _audit(
        self, action: str, entity: str, entity_id: uuid.UUID, before: Any, after: Any, reason: str | None = None
    ) -> None:
        AuditService(self._s).record(
            actor=self._actor,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            tenant_id=self._tenant_id,
            before=before,
            after=after,
            reason=reason,
        )

    # --- geofences ------------------------------------------------------------------------------------
    def to_dto(self, g: Geofence) -> GeofenceDto:
        src, area, m2 = self._s.execute(  # read the *stored* geometry, never an unflushed expression
            select(
                func.ST_AsGeoJSON(Geofence.source_geometry),
                func.ST_AsGeoJSON(Geofence.area),
                func.ST_Area(Geofence.area),
            ).where(Geofence.id == g.id)
        ).one()
        machines = list(
            self._s.execute(select(GeofenceMachine.machine_id).where(GeofenceMachine.geofence_id == g.id)).scalars()
        )
        return GeofenceDto(
            id=g.id,
            name=g.name,
            kind=g.kind,
            shape=g.shape,
            job_site_id=g.job_site_id,
            corridor_width_m=g.corridor_width_m,
            source_geometry=json.loads(src),
            area_geojson=json.loads(area),
            area_m2=round(float(m2), 1),
            machine_ids=machines,
            is_active=g.is_active,
            version=g.version,
        )

    def _area(self, body: GeofenceIn) -> tuple[Any, Any, GeofenceShape]:
        shape = GeofenceShape.POLYGON if body.polygon else GeofenceShape.CORRIDOR
        geojson = body.polygon or body.corridor
        assert geojson is not None
        src = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geojson.model_dump())), 4326)
        valid, empty = self._s.execute(select(func.ST_IsValid(src), func.ST_IsEmpty(src))).one()
        if not valid or empty:
            raise BusinessRuleViolation("Geometry is invalid (self-intersecting or empty)", code="INVALID_GEOMETRY")
        if shape is GeofenceShape.CORRIDOR:
            assert body.corridor_width_m is not None  # enforced by GeofenceIn validation
            area = func.ST_Buffer(func.Geography(src), body.corridor_width_m / 2)  # width is total corridor width
        else:
            area = func.Geography(src)
        return src, area, shape

    def _check_refs(self, body: GeofenceIn) -> None:
        if body.job_site_id and self._s.get(JobSite, body.job_site_id) is None:
            raise NotFound("Job site not found")
        if body.machine_ids:
            found = set(self._s.execute(select(Machine.id).where(Machine.id.in_(body.machine_ids))).scalars())
            if missing := set(body.machine_ids) - found:
                raise NotFound(f"Machines not found: {sorted(map(str, missing))}")

    def create_geofence(self, body: GeofenceIn) -> GeofenceDto:
        self._check_refs(body)
        src, area, shape = self._area(body)
        g = Geofence(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            job_site_id=body.job_site_id,
            name=body.name,
            kind=body.kind,
            shape=shape,
            source_geometry=src,
            corridor_width_m=body.corridor_width_m,
            area=area,
            applies_to_all_machines=not body.machine_ids,
        )
        self._s.add(g)
        self._s.flush()
        self._set_machines(g.id, body.machine_ids)
        dto = self.to_dto(g)
        AuditService(self._s).record(
            actor=self._actor,
            action="geospatial.geofence.created",
            entity_type="geofence",
            entity_id=g.id,
            tenant_id=self._tenant_id,
            after={"name": g.name, "kind": g.kind.value, "area_m2": dto.area_m2},
        )
        return dto

    def update_geofence(self, geofence_id: uuid.UUID, body: GeofenceIn, now: datetime) -> tuple[GeofenceDto, datetime]:
        """New shape applies from `now`; derived events from `now` are replayed by the caller."""
        g = self.geofence(geofence_id, lock=True)
        if body.version is not None:
            check_version(g.version, body.version, "Geofence")
        self._check_refs(body)
        src, area, shape = self._area(body)
        before = self.to_dto(g).model_dump(mode="json")
        g.name, g.kind, g.job_site_id, g.shape = body.name, body.kind, body.job_site_id, shape
        g.source_geometry, g.area, g.corridor_width_m = src, area, body.corridor_width_m
        g.applies_to_all_machines, g.version = not body.machine_ids, g.version + 1
        self._s.flush()
        self._set_machines(g.id, body.machine_ids)
        self._s.refresh(g)
        dto = self.to_dto(g)
        AuditService(self._s).record(
            actor=self._actor,
            action="geospatial.geofence.updated",
            entity_type="geofence",
            entity_id=g.id,
            tenant_id=self._tenant_id,
            before=before,
            after=dto.model_dump(mode="json"),
        )
        return dto, now

    def _set_machines(self, geofence_id: uuid.UUID, machine_ids: list[uuid.UUID]) -> None:
        self._s.execute(delete(GeofenceMachine).where(GeofenceMachine.geofence_id == geofence_id))
        for mid in set(machine_ids):
            self._s.add(GeofenceMachine(geofence_id=geofence_id, machine_id=mid, tenant_id=self._tenant_id))
        self._s.flush()

    def geofence(self, geofence_id: uuid.UUID, lock: bool = False) -> Geofence:
        stmt = select(Geofence).where(Geofence.id == geofence_id)
        g = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if g is None:
            raise NotFound("Geofence not found")
        return g

    def geofences(self, include_inactive: bool = False) -> list[GeofenceDto]:
        stmt = select(Geofence).order_by(Geofence.name)
        if not include_inactive:
            stmt = stmt.where(Geofence.is_active.is_(True))
        return [self.to_dto(g) for g in self._s.execute(stmt).scalars()]

    def set_geofence_active(
        self, geofence_id: uuid.UUID, active: bool, reason: str, version: int | None, now: datetime
    ) -> tuple[GeofenceDto, datetime]:
        """Takes effect from `now`; the caller replays derived events from then (history is not rewritten)."""
        g = self.geofence(geofence_id, lock=True)
        check_version(g.version, version, "Geofence")
        if active:
            mark_active(g, "Geofence")
        else:
            mark_inactive(g, self._actor.user_id, reason, "Geofence")
        g.version += 1
        self._s.flush()
        dto = self.to_dto(g)
        verb = "reactivated" if active else "deactivated"
        self._audit(f"geospatial.geofence.{verb}", "geofence", g.id, None, {"is_active": active}, reason)
        return dto, now

    def affected_machines(self, geofence_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            self._s.execute(
                text(
                    "SELECT DISTINCT machine_id FROM machine_latest_position UNION "
                    "SELECT DISTINCT machine_id FROM geofence_event WHERE geofence_id = :g"
                ),
                {"g": geofence_id},
            ).scalars()
        )

    def events(self, machine_id: uuid.UUID | None, frm: datetime, to: datetime) -> list[GeofenceEvent]:
        stmt = select(GeofenceEvent).where(GeofenceEvent.event_time >= frm, GeofenceEvent.event_time < to)
        if machine_id:
            stmt = stmt.where(GeofenceEvent.machine_id == machine_id)
        return list(self._s.execute(stmt.order_by(GeofenceEvent.event_time)).scalars())
