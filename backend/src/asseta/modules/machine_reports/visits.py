"""Where a machine report's reading was taken (ADR-008 §2, time and place since the last visit).

The place itself is the area label the phone's geocoder gave the reading (`meter_capture.place_name`, e.g. "Mbezi
Beach, Kinondoni, Dar es Salaam"). On top of it the server adds a company-site hint ("at Mbezi site"), looked up from
the company's own areas, never from an outside geocoding service (no location data leaves Asseta): the active site
geofences (SITE_BOUNDARY or ALLOWED_AREA; restricted areas are not sites) that contain the reading's GPS point; when
several do, the one whose site centre (or area centre) is nearest. The name is the geofence's job site name when it
belongs to a site, else the geofence's own name. None contains the point, or no coordinates: null."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

# :tid, :lat, :lng. The same statement (as SQL text) fills existing reports in migration visit01.
PLACE_SQL = """
    SELECT COALESCE(s.name, g.name)
    FROM geofence g LEFT JOIN job_site s ON s.id = g.job_site_id AND s.is_active
    WHERE g.tenant_id = {tid} AND g.is_active AND g.kind IN ('SITE_BOUNDARY', 'ALLOWED_AREA')
      AND ST_Covers(g.area, ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography)
    ORDER BY ST_Distance(
        COALESCE(s.center, ST_Centroid(g.area::geometry))::geography,
        ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography
    ), g.name
    LIMIT 1
"""


def site_name(session: Session, tenant_id: uuid.UUID, lat: float | None, lng: float | None) -> str | None:
    """The company's site the point lies in (nearest when several), or None."""
    if lat is None or lng is None:
        return None
    sql = PLACE_SQL.format(tid=":tid", lat=":lat", lng=":lng")
    found = session.execute(text(sql), {"tid": tenant_id, "lat": lat, "lng": lng}).scalar_one_or_none()
    return str(found) if found is not None else None
