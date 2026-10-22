"""Drill (e): object store (MinIO) outage; evidence uploads fail cleanly and resume (throwaway drill tenant).

    cd backend && uv run python ../scripts/drills/object_store_outage.py

1. Baseline: machine photo upload 201; a resumable sync blob upload (≈700 KB, 3 × 256 KiB chunks) is started as a
   registered field device and its first chunk sent.
2. `docker compose stop minio`: readiness must report object_store down (degraded, HTTP 200); a machine photo upload
   must return the 503 error envelope (DEPENDENCY_UNAVAILABLE), not a 500 or a hang; the rest of the API keeps working
   (machine list, telemetry ingestion, job creation); the blob session keeps accepting chunks (staged in Postgres)
   but `complete` returns 503 and the staged chunks survive.
3. `docker compose start minio`: readiness recovers; the SAME blob session completes (no re-upload), the object is
   readable from MinIO with the declared SHA-256; photo uploads succeed again.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import timedelta
from typing import Any

import boto3
import httpx
from botocore.config import Config
from drill_common import (
    API,
    ENV,
    Evidence,
    Session,
    compose,
    expect,
    guard_local,
    load_state,
    now_utc,
    readiness,
    ready_summary,
    wait_until,
)

from asseta.tools.gps_simulator import Fix, traccar_payload

PNG = b"\x89PNG\r\n\x1a\n"


def image(size: int) -> bytes:
    return PNG + os.urandom(size - len(PNG))


def code(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error", {}).get("code", ""))
    except ValueError:
        return "(no JSON)"


def main() -> None:
    guard_local()
    state = load_state()
    s = Session(state)
    tid = state["tenant_id"]
    m = state["machines"][0]
    ev = Evidence("object-store-outage", "Object store (MinIO) outage: clean 503, rest of API up, resumable upload")
    ev.say(f"Throwaway tenant `{tid}`; machine `{m['machine_id']}`.")
    ev.say("")

    def photo() -> httpx.Response:
        return httpx.post(
            f"{API}/tenant/machines/{m['machine_id']}/photos",
            headers=s.headers(),
            files={"file": ("drill.png", image(40_000), "image/png")},
            timeout=60,
        )

    r = photo()
    ev.check("baseline: machine photo upload 201", r.status_code == 201, f"HTTP {r.status_code}")
    device = f"drill-device-{uuid.uuid4().hex[:8]}"
    expect(
        httpx.post(
            f"{API}/sync/devices",
            headers=s.headers(),
            timeout=30,
            json={"device_id": device, "platform": "ANDROID", "app_version": "drill-1"},
        ),
        201,
        "register",
    )
    dh: dict[str, str] = {"X-Device-Id": device}
    blob = image(700_000)
    sha = hashlib.sha256(blob).hexdigest()
    sess = expect(
        httpx.post(
            f"{API}/sync/blobs",
            headers={**s.headers(), **dh},
            timeout=30,
            json={"sha256": sha, "size_bytes": len(blob), "purpose": "METER_PHOTO"},
        ),
        201,
        "start",
    )
    cs, total = sess["chunk_size"], sess["total_chunks"]

    def chunk(i: int) -> httpx.Response:
        return httpx.put(
            f"{API}/sync/blobs/{sess['id']}/chunks/{i}",
            headers={**s.headers(idempotent=False), **dh},
            content=blob[i * cs : (i + 1) * cs],
            timeout=60,
        )

    r = chunk(0)
    ev.check(
        "baseline: blob session started and chunk 0 accepted",
        r.status_code == 200,
        f"session {sess['id']}, {total} chunks of {cs} B",
    )

    t0 = time.monotonic()
    compose("stop", "minio", capture=True)
    stop_s = time.monotonic() - t0
    rd = readiness()
    ev.say(f"* `docker compose stop minio` {stop_s:.1f} s; readiness: {ready_summary(rd)}")
    ev.check(
        "readiness reports object_store down, overall degraded (HTTP 200)",
        rd.get("http_status") == 200 and rd.get("checks", {}).get("object_store", {}).get("status") == "down",
        ready_summary(rd),
    )
    t1 = time.monotonic()
    r = photo()
    ev.check(
        "photo upload during outage → 503 error envelope (DEPENDENCY_UNAVAILABLE)",
        r.status_code == 503 and code(r) == "DEPENDENCY_UNAVAILABLE",
        f"HTTP {r.status_code} {code(r)} in {time.monotonic() - t1:.1f} s; correlation_id present: "
        f"{bool(r.json().get('error', {}).get('correlation_id')) if r.status_code == 503 else '-'}",
    )
    other: dict[str, Any] = {}
    other["GET /tenant/machines"] = httpx.get(f"{API}/tenant/machines", headers=s.headers(), timeout=30).status_code
    fix = Fix(now_utc().replace(microsecond=0) - timedelta(seconds=5), -6.8, 39.28, 0, 0)
    other["POST /telemetry/traccar"] = httpx.post(
        f"{API}/telemetry/traccar",
        json=traccar_payload(m["device"], fix),
        headers={"X-Asseta-Gateway-Key": ENV["ASSETA_TRACCAR_GATEWAY_KEY"]},
        timeout=30,
    ).status_code
    other["POST /tenant/jobs"] = httpx.post(
        f"{API}/tenant/jobs",
        headers=s.headers(),
        timeout=30,
        json={
            "contract_id": state["contract_id"],
            "job_number": f"DRL-OS-{uuid.uuid4().hex[:6]}",
            "machine_id": m["machine_id"],
            "planned_start": now_utc().isoformat(),
            "hourly_rate": "50000",
        },
    ).status_code
    other["GET /sync/bootstrap"] = httpx.get(
        f"{API}/sync/bootstrap", headers={**s.headers(), **dh}, timeout=30
    ).status_code
    ev.check("rest of the API works during the outage", all(200 <= v < 300 for v in other.values()), str(other))
    resp = [chunk(i) for i in range(1, total)]
    chunks = [c.status_code for c in resp]
    ev.check(
        "remaining chunks accepted during the outage (staged in Postgres)",
        all(c == 200 for c in chunks),
        f"{chunks}; received_chunks {resp[-1].json().get('received_chunks') if resp else '-'}",
    )
    r = httpx.post(f"{API}/sync/blobs/{sess['id']}/complete", headers={**s.headers(), **dh}, timeout=60)
    ev.check(
        "blob complete during outage → 503 envelope, session kept",
        r.status_code == 503,
        f"HTTP {r.status_code} {code(r)}",
    )

    compose("start", "minio", capture=True)
    t_ready = wait_until(lambda: readiness().get("status") == "ok", 180, 0.5)
    ev.say(
        f"* `docker compose start minio`; readiness ok after {t_ready if t_ready is None else round(t_ready, 1)} s; "
        f"total object-store downtime {time.monotonic() - t0:.0f} s"
    )
    ev.check("readiness recovers", t_ready is not None, "")
    t3 = time.monotonic()
    done = wait_until(
        lambda: (
            httpx.post(f"{API}/sync/blobs/{sess['id']}/complete", headers={**s.headers(), **dh}, timeout=60).status_code
            == 200
        ),
        120,
        2.0,
    )
    final = httpx.post(f"{API}/sync/blobs/{sess['id']}/complete", headers={**s.headers(), **dh}, timeout=60).json()
    ev.check(
        "same blob session completes after recovery without re-upload",
        done is not None and final.get("status") == "COMPLETE" and final.get("attachment_id"),
        f"{final.get('status')} attachment {final.get('attachment_id')} after {done} s "
        f"(first complete attempt {time.monotonic() - t3:.1f} s after readiness)",
    )
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://localhost:{ENV.get('ASSETA_MINIO_PORT', '9100')}",
        aws_access_key_id=ENV["MINIO_ROOT_USER"],
        aws_secret_access_key=ENV["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    obj = s3.get_object(Bucket="asseta-evidence", Key=f"tenants/{tid}/evidence/{sha}")["Body"].read()
    ev.check("stored object SHA-256 matches the declared hash", hashlib.sha256(obj).hexdigest() == sha, sha[:16])
    r = photo()
    ev.check("photo uploads succeed again", r.status_code == 201, f"HTTP {r.status_code}")
    ev.check("final readiness ok", readiness().get("status") == "ok", ready_summary(readiness()))
    ev.write(
        not_simulated=[
            "Object-store data loss or bucket corruption (covered by the backup/restore drill's object hash check).",
            "Slow / partially failing S3 (timeouts, 5xx from a healthy endpoint); here the endpoint is unreachable.",
            "Presigned URL behaviour for clients during the outage (URLs are signed locally; downloads fail at MinIO).",
            "MLflow artefact storage (MLflow keeps working for metadata; training records runs locally when down).",
        ],
        commands=["cd backend", "uv run python ../scripts/drills/object_store_outage.py"],
    )


if __name__ == "__main__":
    main()
