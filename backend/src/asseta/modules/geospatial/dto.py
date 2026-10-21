import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.geospatial.models import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    GeofenceKind,
    GeofenceShape,
    GeofenceTransition,
)

Lon = Annotated[float, Field(ge=-180, le=180)]
Lat = Annotated[float, Field(ge=-90, le=90)]
Position = tuple[Lon, Lat]  # GeoJSON order: [longitude, latitude]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GeoPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: Position


class GeoPolygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[Position]] = Field(min_length=1)

    @model_validator(mode="after")
    def _closed(self) -> "GeoPolygon":
        for ring in self.coordinates:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("each ring needs >= 4 positions and must be closed")
        return self


class GeoLineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[Position] = Field(min_length=2)


class JobSiteIn(BaseModel):
    code: Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
    address: str | None = Field(default=None, max_length=300)
    center: GeoPoint


class JobSiteUpdateIn(JobSiteIn):
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class JobSiteDto(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    address: str | None
    center: GeoPoint
    is_active: bool
    version: int = 1
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


class GeofenceIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
    kind: GeofenceKind
    job_site_id: uuid.UUID | None = None
    polygon: GeoPolygon | None = None
    corridor: GeoLineString | None = None
    corridor_width_m: float | None = Field(default=None, gt=0, le=5000)
    machine_ids: list[uuid.UUID] = Field(default_factory=list, description="Empty = applies to all machines")
    version: int | None = Field(
        default=None, ge=1, description="On update: optimistic concurrency token (STALE_VERSION when outdated)"
    )

    @model_validator(mode="after")
    def _shape(self) -> "GeofenceIn":
        if (self.polygon is None) == (self.corridor is None):
            raise ValueError("provide exactly one of polygon or corridor")
        if self.corridor is not None and self.corridor_width_m is None:
            raise ValueError("corridor requires corridor_width_m")
        return self


class GeofenceDto(BaseModel):
    id: uuid.UUID
    name: str
    kind: GeofenceKind
    shape: GeofenceShape
    job_site_id: uuid.UUID | None
    corridor_width_m: float | None
    source_geometry: dict[str, Any]
    area_geojson: dict[str, Any]
    area_m2: float
    machine_ids: list[uuid.UUID]
    is_active: bool
    version: int
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


class GeofenceEventDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    geofence_id: uuid.UUID
    transition: GeofenceTransition
    event_time: datetime
    distance_m: float
    policy_version: str


class AlertDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID | None
    tracker_id: uuid.UUID | None
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    event_time: datetime
    title: str
    evidence: dict[str, Any]
    policy_version: str | None
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None


class AlertActionIn(BaseModel):
    action: Literal["ACKNOWLEDGE", "RESOLVE"]
    note: str | None = Field(default=None, max_length=1000)
