"""Gate 3 helpers: a priced, approved job on a tracked machine, plus capture payload builders."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.telemetry import DAR, Telemetry, Tracked


@dataclass
class JobCtx:
    t: Tracked
    owner: Actor
    job_id: str
    category_id: str
    contract_id: str


def unique_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0" + uuid.uuid4().bytes * 4


def photo(api: Api, actor: Actor) -> str:
    r = api.client.post(
        "/api/v1/tenant/attachments",
        headers=actor.headers(True, None),
        files={"file": ("m.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "METER_PHOTO"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def new_job(api: Api, ctx: JobCtx, number: str, machine_id: str | None = None, rate: str | None = None) -> str:
    body: dict[str, Any] = {
        "contract_id": ctx.contract_id,
        "job_number": number,
        "machine_id": machine_id or ctx.t.machine_id,
        "planned_start": api.clock.now.isoformat(),
    }
    if rate is not None:
        body["hourly_rate"] = rate  # negotiated price (no rate card for this category)
    r = ctx.owner.post("/api/v1/tenant/jobs", body)
    assert r.status_code == 201, r.text
    job_id = str(r.json()["id"])
    for action in ("SUBMIT", "APPROVE"):
        a = ctx.owner.post(f"/api/v1/tenant/jobs/{job_id}/transitions", {"action": action})
        assert a.status_code == 200, a.text
    return job_id


def setup_job(api: Api, name: str = "Hire Co", device: str = "HIRE-1") -> JobCtx:
    tel = Telemetry(api)
    t = tel.tracked_machine(name, device)
    o = t.owner
    cat = o.post("/api/v1/tenant/machine-categories", {"name": "Excavators"}).json()["id"]
    m = o.get(f"/api/v1/tenant/machines/{t.machine_id}").json()
    keys = (
        "name",
        "operating_area_id",
        "manufacturer",
        "model",
        "serial_number",
        "year_of_manufacture",
        "capacity_value",
        "capacity_unit",
        "meter_decimal_places",
        "ownership",
    )
    r = api.client.put(
        f"/api/v1/tenant/machines/{t.machine_id}",
        headers=o.headers(False, None),
        json={**{k: m[k] for k in keys}, "category_id": cat, "status": "ACTIVE", "version": m["version"]},
    )
    assert r.status_code == 200, r.text
    o.post(
        "/api/v1/tenant/rate-cards",
        {"machine_category_id": cat, "hourly_rate": "85000", "minimum_hours": "4", "reason": "2026 rate card"},
    )
    cust = o.post("/api/v1/tenant/customers", {"code": "C1", "name": "Road Builders Ltd"}).json()["id"]
    contract = o.post(
        "/api/v1/tenant/contracts",
        {"customer_id": cust, "contract_number": "CT-001", "starts_on": api.clock.now.isoformat()},
    ).json()["id"]
    ctx = JobCtx(t, o, "", cat, contract)
    ctx.job_id = new_job(api, ctx, "J-001")
    return ctx


def capture(
    job_id: str,
    kind: str,
    reading: str,
    at: datetime,
    *,
    mode: str = "AUTOMATIC",
    photo_id: str | None = None,
    gps: dict[str, Any] | None = None,
    ocr: str | None = None,
    confidence: float | None = 0.97,
    snapshot: list[str] | None = None,
    capture_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": capture_id or str(uuid.uuid4()),
        "job_id": job_id,
        "kind": kind,
        "capture_mode": mode,
        "reading": reading,
        "ocr_value": ocr if ocr is not None else (reading if mode == "AUTOMATIC" else None),
        "ocr_confidence": confidence if mode == "AUTOMATIC" else None,
        "ocr_engine": "fixture",
        "photo_attachment_id": photo_id,
        "gps": gps if gps is not None else fix(at),
        "device_id": "android-test-device",
        "captured_at": at.isoformat(),
        "policy_version_ids": snapshot or [],
    }


def fix(
    at: datetime, lat: float = DAR[0], lon: float = DAR[1], accuracy: float = 8.0, age_s: int = 5
) -> dict[str, Any]:
    return {
        "status": "FIX",
        "latitude": lat,
        "longitude": lon,
        "accuracy_m": accuracy,
        "captured_at": (at - timedelta(seconds=age_s)).isoformat(),
        "provider": "fused",
    }
