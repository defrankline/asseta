"""Deterministic GPS tracker simulator (clearly a simulator — not hardware validation).

Generates Traccar-forwarding-format payloads along a waypoint route so ingestion, late/out-of-order delivery,
duplicates and geofence logic can be exercised reproducibly. Two delivery modes:

* `post_to_asseta`: POST payloads to /api/v1/telemetry/traccar with a gateway key (bypasses Traccar).
* `send_osmand`: act as an OsmAnd-protocol device against a real Traccar server (port 5055), so Traccar's own
  forwarding delivers to Asseta — the end-to-end path used for "demonstrable simulated GPS device".

CLI: python -m asseta.tools.gps_simulator --device SIM-001 --traccar http://localhost:5055 --points 30
"""

import argparse
import itertools
import math
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

EARTH_RADIUS_M = 6_371_000.0
KMH_TO_KNOTS = 1 / 1.852


@dataclass(frozen=True)
class Fix:
    time: datetime
    lat: float
    lon: float
    speed_kmh: float
    course: float
    ignition: bool | None = True
    accuracy_m: float | None = 5.0
    valid: bool = True
    hours_ms: int | None = None
    power_v: float | None = None
    alarm: str | None = None


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def route(
    waypoints: list[tuple[float, float]],
    start: datetime,
    speed_kmh: float,
    interval_s: int,
    dwell_points: int = 0,
    hours_start_ms: int | None = None,
) -> list[Fix]:
    """Constant-speed traversal of (lat, lon) waypoints, sampling every `interval_s`; optional dwell at end."""
    fixes: list[Fix] = []
    t = start
    step_m = speed_kmh / 3.6 * interval_s
    hours = hours_start_ms
    for a, b in itertools.pairwise(waypoints):
        seg = _distance_m(a, b)
        n = max(1, math.ceil(seg / step_m)) if step_m > 0 else 1
        for i in range(n):
            f = i / n
            fixes.append(
                Fix(t, a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, speed_kmh, _bearing(a, b), hours_ms=hours)
            )
            t += timedelta(seconds=interval_s)
            hours = hours + interval_s * 1000 if hours is not None else None
    last = waypoints[-1]
    for _ in range(dwell_points + 1):
        fixes.append(Fix(t, last[0], last[1], 0.0, 0.0, hours_ms=hours))
        t += timedelta(seconds=interval_s)
        hours = hours + interval_s * 1000 if hours is not None else None
    return fixes


def traccar_payload(device_id: str, fix: Fix, include_ignition: bool = True) -> dict[str, Any]:
    attrs: dict[str, Any] = {"sat": 9}
    if include_ignition and fix.ignition is not None:
        attrs["ignition"] = fix.ignition
    if fix.hours_ms is not None:
        attrs["hours"] = fix.hours_ms
    if fix.power_v is not None:
        attrs["power"] = fix.power_v
    if fix.alarm:
        attrs["alarm"] = fix.alarm
    iso = fix.time.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {
        "device": {"id": 1, "uniqueId": device_id, "name": device_id},
        "position": {
            "deviceId": 1,
            "protocol": "osmand",
            "fixTime": iso,
            "deviceTime": iso,
            "valid": fix.valid,
            "latitude": round(fix.lat, 7),
            "longitude": round(fix.lon, 7),
            "altitude": 1200.0,
            "speed": round(fix.speed_kmh * KMH_TO_KNOTS, 4),
            "course": round(fix.course, 1),
            "accuracy": fix.accuracy_m or 0.0,
            "attributes": attrs,
        },
    }


def delivery_order(fixes: list[Fix], *, duplicate_every: int = 0, swap_every: int = 0) -> Iterator[Fix]:
    """Reorders/duplicates deterministically to emulate tracker buffering and network replays."""
    out = list(fixes)
    if swap_every:
        for i in range(swap_every, len(out), swap_every):
            out[i - 1], out[i] = out[i], out[i - 1]
    for i, fix in enumerate(out):
        yield fix
        if duplicate_every and i % duplicate_every == 0:
            yield fix


def post_to_asseta(api_url: str, gateway_key: str, device_id: str, fixes: list[Fix]) -> list[dict[str, Any]]:
    results = []
    with httpx.Client(timeout=10) as client:
        for fix in fixes:
            r = client.post(
                f"{api_url}/api/v1/telemetry/traccar",
                json=traccar_payload(device_id, fix),
                headers={"X-Asseta-Gateway-Key": gateway_key},
            )
            r.raise_for_status()
            results.append(r.json())
    return results


def send_osmand(traccar_url: str, device_id: str, fixes: list[Fix], pause_s: float = 0.0) -> int:
    """OsmAnd protocol (HTTP query) to Traccar's device port; returns count of accepted messages."""
    sent = 0
    with httpx.Client(timeout=10) as client:
        for fix in fixes:
            params: dict[str, str | float | int | bool] = {
                "id": device_id,
                "lat": fix.lat,
                "lon": fix.lon,
                "timestamp": int(fix.time.timestamp()),
                "speed": round(fix.speed_kmh * KMH_TO_KNOTS, 4),
                "bearing": fix.course,
                "accuracy": fix.accuracy_m or 0,
                "valid": str(fix.valid).lower(),
            }
            if fix.ignition is not None:
                params["ignition"] = str(fix.ignition).lower()
            if client.get(traccar_url, params=params).status_code == 200:
                sent += 1
            if pause_s:
                time.sleep(pause_s)
    return sent


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--device", required=True)
    p.add_argument("--traccar", help="Traccar OsmAnd URL, e.g. http://localhost:5055")
    p.add_argument("--asseta", help="Asseta API base URL (direct mode)")
    p.add_argument("--gateway-key")
    p.add_argument("--points", type=int, default=20)
    p.add_argument("--start-lat", type=float, default=-6.7924)
    p.add_argument("--start-lon", type=float, default=39.2083)
    args = p.parse_args()
    start = datetime.now(UTC) - timedelta(seconds=30 * args.points)
    end = (args.start_lat + 0.0005 * args.points, args.start_lon + 0.0005 * args.points)
    fixes = route([(args.start_lat, args.start_lon), end], start, 12.0, 30)[: args.points]
    if args.traccar:
        print(f"sent {send_osmand(args.traccar, args.device, fixes)} OsmAnd messages")
    elif args.asseta and args.gateway_key:
        print(post_to_asseta(args.asseta, args.gateway_key, args.device, fixes)[-1])
    else:
        p.error("use --traccar, or --asseta with --gateway-key")


if __name__ == "__main__":
    main()
