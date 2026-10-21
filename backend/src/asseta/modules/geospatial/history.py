"""Route playback, stop/trip timeline, time-in-location and proximity queries (event-time ordered)."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from asseta.core.errors import NotFound
from asseta.modules.policy.service import PolicyService

MAX_POINTS = 10_000


class TrackPointDto(BaseModel):
    event_time: datetime
    longitude: float
    latitude: float
    accuracy_m: float | None
    speed_kmh: float | None
    heading_deg: float | None
    ignition: bool | None
    quality: str
    is_late: bool
    received_at: datetime


class StopDto(BaseModel):
    start: datetime
    end: datetime
    duration_seconds: int
    longitude: float
    latitude: float


class SiteVisitDto(BaseModel):
    geofence_id: uuid.UUID
    geofence_name: str
    entered_at: datetime | None  # None: already inside at window start
    exited_at: datetime | None  # None: still inside at window end
    duration_seconds: int


class HistoryDto(BaseModel):
    machine_id: uuid.UUID
    points: list[TrackPointDto]
    truncated: bool
    stops: list[StopDto]
    distance_km: float
    site_visits: list[SiteVisitDto]
    policy_version: str


class NearbyMachineDto(BaseModel):
    machine_id: uuid.UUID
    asset_code: str
    distance_m: float
    position_time: datetime


class HistoryService:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tenant_id = session, tenant_id

    def history(self, machine_id: uuid.UUID, frm: datetime, to: datetime) -> HistoryDto:
        if self._s.execute(text("SELECT 1 FROM machine WHERE id = :m"), {"m": machine_id}).first() is None:
            raise NotFound("Machine not found")  # RLS: other tenants' machines are invisible
        eff = PolicyService(self._s).tracking(self._tenant_id, machine_id, at=to)
        rows = self._s.execute(
            text("""
            SELECT event_time, ST_X(location) lon, ST_Y(location) lat, accuracy_m, speed_kmh, heading_deg, ignition,
                   quality, is_late, received_at
            FROM machine_position_event WHERE machine_id = :m AND event_time >= :f AND event_time < :t
            ORDER BY event_time LIMIT :lim"""),
            {"m": machine_id, "f": frm, "t": to, "lim": MAX_POINTS + 1},
        ).all()
        points = [
            TrackPointDto(
                event_time=r.event_time,
                longitude=r.lon,
                latitude=r.lat,
                accuracy_m=r.accuracy_m,
                speed_kmh=r.speed_kmh,
                heading_deg=r.heading_deg,
                ignition=r.ignition,
                quality=r.quality,
                is_late=r.is_late,
                received_at=r.received_at,
            )
            for r in rows
        ]
        truncated = len(points) > MAX_POINTS
        points = points[:MAX_POINTS]
        usable = [p for p in points if p.quality != "IMPLAUSIBLE_JUMP"]
        distance = self._s.execute(
            text("""
            SELECT COALESCE(ST_Length(ST_MakeLine(location ORDER BY event_time)::geography), 0) / 1000
            FROM machine_position_event WHERE machine_id = :m AND event_time >= :f AND event_time < :t
              AND quality <> 'IMPLAUSIBLE_JUMP'"""),
            {"m": machine_id, "f": frm, "t": to},
        ).scalar_one()
        return HistoryDto(
            machine_id=machine_id,
            points=points,
            truncated=truncated,
            stops=self._stops(usable, eff.policy.moving_speed_kmh, eff.policy.stop_min_seconds),
            distance_km=round(float(distance), 3),
            site_visits=self._visits(machine_id, frm, to),
            policy_version=eff.version_stamp,
        )

    @staticmethod
    def _stops(points: list[TrackPointDto], moving_kmh: float, min_seconds: int) -> list[StopDto]:
        stops: list[StopDto] = []
        run: list[TrackPointDto] = []
        for p in [*points, None]:
            stopped = p is not None and p.speed_kmh is not None and p.speed_kmh < moving_kmh
            if stopped and p is not None:
                run.append(p)
                continue
            if run and (run[-1].event_time - run[0].event_time).total_seconds() >= min_seconds:
                stops.append(
                    StopDto(
                        start=run[0].event_time,
                        end=run[-1].event_time,
                        duration_seconds=int((run[-1].event_time - run[0].event_time).total_seconds()),
                        longitude=sum(x.longitude for x in run) / len(run),
                        latitude=sum(x.latitude for x in run) / len(run),
                    )
                )
            run = []
        return stops

    def _visits(self, machine_id: uuid.UUID, frm: datetime, to: datetime) -> list[SiteVisitDto]:
        rows = self._s.execute(
            text("""
            SELECT e.geofence_id, g.name, e.transition, e.event_time,
                   (SELECT transition FROM geofence_event p WHERE p.machine_id = e.machine_id
                      AND p.geofence_id = e.geofence_id AND p.event_time < :f ORDER BY event_time DESC LIMIT 1) prior
            FROM geofence_event e JOIN geofence g ON g.id = e.geofence_id
            WHERE e.machine_id = :m AND e.event_time >= :f AND e.event_time < :t
            ORDER BY e.geofence_id, e.event_time"""),
            {"m": machine_id, "f": frm, "t": to},
        ).all()
        visits: list[SiteVisitDto] = []
        open_: dict[uuid.UUID, tuple[str, datetime | None]] = {}
        for r in rows:
            if r.geofence_id not in open_ and r.transition == "EXIT" and r.prior == "ENTER":
                open_[r.geofence_id] = (r.name, None)  # inside at window start
            if r.transition == "ENTER":
                open_[r.geofence_id] = (r.name, r.event_time)
            elif r.geofence_id in open_:
                name, entered = open_.pop(r.geofence_id)
                visits.append(
                    SiteVisitDto(
                        geofence_id=r.geofence_id,
                        geofence_name=name,
                        entered_at=entered,
                        exited_at=r.event_time,
                        duration_seconds=int((r.event_time - (entered or frm)).total_seconds()),
                    )
                )
        for gid, (name, entered) in open_.items():
            visits.append(
                SiteVisitDto(
                    geofence_id=gid,
                    geofence_name=name,
                    entered_at=entered,
                    exited_at=None,
                    duration_seconds=int((to - (entered or frm)).total_seconds()),
                )
            )
        return visits

    def nearby(self, lon: float, lat: float, radius_m: float) -> list[NearbyMachineDto]:
        rows = self._s.execute(
            text("""
            SELECT m.id, m.asset_code, lp.event_time,
                   ST_Distance(lp.location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) d
            FROM machine_latest_position lp JOIN machine m ON m.id = lp.machine_id
            WHERE ST_DWithin(lp.location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r)
            ORDER BY d"""),
            {"lon": lon, "lat": lat, "r": radius_m},
        ).all()
        return [
            NearbyMachineDto(
                machine_id=r.id, asset_code=r.asset_code, distance_m=round(float(r.d), 1), position_time=r.event_time
            )
            for r in rows
        ]
