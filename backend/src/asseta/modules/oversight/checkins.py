"""Site check-ins (DEC-031 M3). A supervisor checks in by GPS at the site at the tenant's scheduled times (sync op
SITE_CHECKIN, or the web). Stored append-only; the person sees their own check-ins and schedule; the office lists
everyone's. Missed check-ins are derived (scorecard item MISSED_CHECKIN), never stored."""

import uuid
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.modules.finance.common import resolve_staff
from asseta.modules.fleet.models import StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.meter.models import GpsStatus
from asseta.modules.oversight.dto import CheckinSlotDto, MySiteCheckinsDto, SiteCheckinDto, SiteCheckinIn
from asseta.modules.oversight.models import SiteCheckin
from asseta.modules.oversight.scorecard import ScorecardBuilder, day_bounds, tenant_tz
from asseta.modules.policy.service import PolicyService

FUTURE_TOLERANCE = timedelta(minutes=10)
MAX_DAYS = 93


def checkin_dto(row: SiteCheckin, max_distance_m: int | None) -> SiteCheckinDto:
    dto = SiteCheckinDto.model_validate(row)
    if max_distance_m is not None and row.distance_m is not None:
        dto.within_distance = row.distance_m <= max_distance_m
    return dto


def period(tz_now: date, day_from: date | None, day_to: date | None, default_days: int) -> tuple[date, date]:
    last = day_to or tz_now
    first = day_from or last - timedelta(days=default_days - 1)
    if first > last:
        raise BusinessRuleViolation("day_from must not be after day_to", code="INVALID_PERIOD")
    if (last - first).days + 1 > MAX_DAYS:
        raise BusinessRuleViolation(f"At most {MAX_DAYS} days", code="PERIOD_TOO_LONG")
    return first, last


class SiteCheckinService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._policy = PolicyService(session).oversight(self._tid, at=now).policy

    def dto(self, row: SiteCheckin) -> SiteCheckinDto:
        return checkin_dto(row, self._policy.site_checkin_max_distance_m)

    def record(self, body: SiteCheckinIn, source: str, device_session_id: uuid.UUID | None = None) -> SiteCheckinDto:
        staff = resolve_staff(self._s, self._ctx, None)
        existing = self._s.execute(
            select(SiteCheckin).where(SiteCheckin.client_id == body.client_id)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.staff_member_id != staff.id:
                raise Conflict("This check-in id is already used", code="CHECKIN_ID_CONFLICT")
            return self.dto(existing)  # replay of the same check-in
        if body.captured_at > self._now + FUTURE_TOLERANCE:
            raise BusinessRuleViolation("The check-in time is in the future", code="CHECKIN_IN_FUTURE")
        site_id = body.job_site_id
        if site_id is not None and self._s.get(JobSite, site_id) is None:
            raise NotFound("Job site not found", code="JOB_SITE_NOT_FOUND")
        job = self._running_job(staff.id, body.captured_at, site_id)
        if site_id is None and job is not None:
            site_id = job.job_site_id
        distance = None
        gps = body.gps
        if site_id is not None and gps.status is GpsStatus.FIX:
            distance = self._s.execute(
                text(
                    "SELECT ST_Distance(center::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)"
                    " FROM job_site WHERE id = :site"
                ),
                {"lon": gps.longitude, "lat": gps.latitude, "site": site_id},
            ).scalar_one_or_none()
        row = SiteCheckin(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            staff_member_id=staff.id,
            recorded_by=self._ctx.user_id,
            captured_at=body.captured_at,
            received_at=self._now,
            gps_status=gps.status,
            latitude=gps.latitude,
            longitude=gps.longitude,
            accuracy_m=gps.accuracy_m,
            job_site_id=site_id,
            job_id=job.id if job else None,
            distance_m=round(float(distance), 1) if distance is not None else None,
            source=source,
            device_session_id=device_session_id,
            created_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(source.lower()),
            action="site_checkin.recorded",
            entity_type="site_checkin",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"staff_member_id": str(staff.id), "job_site_id": str(site_id) if site_id else None},
        )
        return self.dto(row)

    def _running_job(self, staff_id: uuid.UUID, at: datetime, site_id: uuid.UUID | None) -> Job | None:
        jobs = list(
            self._s.execute(
                select(Job)
                .where(
                    Job.supervisor_id == staff_id,
                    Job.status.in_([JobStatus.IN_PROGRESS, JobStatus.COMPLETED]),
                    Job.started_at.is_not(None),
                    Job.started_at <= at,
                )
                .order_by(Job.started_at.desc())
            ).scalars()
        )
        running = [j for j in jobs if j.completed_at is None or j.completed_at > at]
        same_site = [j for j in running if site_id is not None and j.job_site_id == site_id]
        candidates = same_site or running
        return candidates[0] if candidates else None

    # --- reads ------------------------------------------------------------------------------------------------
    def get(self, checkin_id: uuid.UUID) -> SiteCheckinDto:
        row = self._s.get(SiteCheckin, checkin_id)
        if row is None:
            raise NotFound("Site check-in not found", code="SITE_CHECKIN_NOT_FOUND")
        return self.dto(row)

    def query(
        self,
        staff_id: uuid.UUID | None,
        job_site_id: uuid.UUID | None,
        day_from: date | None,
        day_to: date | None,
        q: str | None,
    ) -> Select[SiteCheckin]:
        stmt = select(SiteCheckin).order_by(SiteCheckin.captured_at.desc(), SiteCheckin.id)
        tz = tenant_tz(self._s, self._tid)
        if day_from or day_to:
            first, last = period(self._now.astimezone(tz).date(), day_from, day_to, MAX_DAYS)
            start, end = day_bounds(tz, first, last)
            stmt = stmt.where(SiteCheckin.captured_at >= start, SiteCheckin.captured_at < end)
        if staff_id:
            stmt = stmt.where(SiteCheckin.staff_member_id == staff_id)
        if job_site_id:
            stmt = stmt.where(SiteCheckin.job_site_id == job_site_id)
        if q and q.strip():
            names = select(StaffMember.id).where(StaffMember.full_name.ilike(f"%{q.strip()}%"))
            stmt = stmt.where(SiteCheckin.staff_member_id.in_(names))
        return stmt

    def mine(self, day_from: date | None, day_to: date | None) -> MySiteCheckinsDto:
        staff = resolve_staff(self._s, self._ctx, None, require_active=False)
        builder = ScorecardBuilder(self._s, self._tid, self._now)
        tz = builder.tz
        first, last = period(self._now.astimezone(tz).date(), day_from, day_to, 7)
        start, end = day_bounds(tz, first, last)
        builder.load_windows(start, end)
        slots = builder.slots(start, end, staff.id)
        window = timedelta(minutes=self._policy.site_checkin_window_minutes)
        made = list(
            self._s.execute(
                select(SiteCheckin)
                .where(
                    SiteCheckin.staff_member_id == staff.id,
                    SiteCheckin.captured_at >= start - window,
                    SiteCheckin.captured_at < end + window,
                )
                .order_by(SiteCheckin.captured_at.desc())
            ).scalars()
        )
        out = []
        status: Literal["MADE", "MISSED", "DUE", "UPCOMING"]
        for slot in slots:
            hit = next((c for c in made if slot.at - slot.window <= c.captured_at <= slot.at + slot.window), None)
            if hit is not None:
                status = "MADE"
            elif slot.at + slot.window <= self._now:
                status = "MISSED"
            elif slot.at - slot.window <= self._now:
                status = "DUE"
            else:
                status = "UPCOMING"
            out.append(
                CheckinSlotDto(
                    scheduled_at=slot.at,
                    window_minutes=int(slot.window.total_seconds() // 60),
                    status=status,
                    checkin_id=hit.id if hit else None,
                    job_id=slot.job_id,
                )
            )
        return MySiteCheckinsDto(
            required=self._policy.site_checkin_required,
            times=[t.strftime("%H:%M") for t in sorted(self._policy.site_checkin_times)],
            window_minutes=self._policy.site_checkin_window_minutes,
            max_distance_m=self._policy.site_checkin_max_distance_m,
            timezone=str(tz),
            day_from=first,
            day_to=last,
            slots=out,
            checkins=[self.dto(c) for c in made if start <= c.captured_at < end],
        )
