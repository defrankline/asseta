"""Penetration checks (prompt.md §10 #11) for storage URLs, devices, offline policies and role changes.

(vi)  presigned evidence URLs: short TTL, tenant-prefixed server-derived keys (client file names never reach the key),
      the real S3 signer embeds the expiry; other tenants get 404. Live MinIO expiry: tests/integration/
      test_minio_live.py::test_presigned_url_works_then_expires.
(vii) revoked device refused on EVERY sync endpoint, device ids bound to their user; stale offline policy snapshots
      are refreshed on the next contact and recorded next to the server stamp; foreign snapshots refused; role
      revocation and permission removal take effect on the next request, even for a still-valid token.
"""

import hashlib
import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

from asseta.core.config import get_settings
from asseta.core.storage import S3ObjectStore
from tests.support.api import Actor, Api
from tests.support.finance import setup_finance
from tests.support.idp import InMemoryObjectStore
from tests.support.jobs import capture, fix, photo, setup_job, unique_jpeg
from tests.support.notify import sync_mirror

T = "/api/v1/tenant"
DEVICE = "pen-device-0001"


def _store(api: Api) -> InMemoryObjectStore:
    store: InMemoryObjectStore = api.client.app.state.object_store  # type: ignore[attr-defined]
    return store


def test_presigned_urls_are_short_lived_tenant_scoped_and_keys_server_derived(api: Api) -> None:
    f = setup_finance(api, "Url Co", "URL-1")
    other = api.onboard("Url Other", price="1")["owner"]
    ttl = get_settings().presigned_url_ttl_seconds
    assert 30 <= ttl <= 300  # config bound is 30..3600; the deployed default is 300 s

    # Hostile client file names: the object key is derived from tenant + content hash, never from the name.
    hostile = api.client.post(
        f"{T}/attachments",
        headers=f.owner.headers(True, None),
        files={"file": ("../../../../etc/passwd.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "METER_PHOTO"},
    )
    assert hostile.status_code == 201, hostile.text
    machine_photo = api.client.post(
        f"{T}/machines/{f.c.t.machine_id}/photos",
        headers=f.owner.headers(True, None),
        files={"file": ("..\\..\\boot.ini", unique_jpeg(), "image/jpeg")},
        data={"caption": "../../x"},
    ).json()
    urls = {
        f"{T}/attachments/{hostile.json()['id']}/url": "evidence",
        f"{T}/attachments/{photo(api, f.owner)}/url": "evidence",
        f"{T}/machines/{f.c.t.machine_id}/photos/{machine_photo['id']}/url": "photos",
    }
    for path, kind in urls.items():
        r = f.owner.get(path)
        assert r.status_code == 200, r.text
        assert r.json()["expires_in_seconds"] == ttl and f"X-Amz-Expires={ttl}" in r.json()["url"]
        assert f"/tenants/{f.tid}/" in r.json()["url"] and kind in r.json()["url"]
        assert other.get(path).status_code == 404  # another tenant cannot mint a URL for it
    for key in _store(api).objects:
        assert key.startswith("tenants/") and ".." not in key and "\\" not in key and "passwd" not in key, key


def test_real_s3_signer_embeds_expiry_and_no_secret() -> None:
    """Pure local signing (no network): the URL carries a SigV4 signature with X-Amz-Expires, never the secret."""
    store = S3ObjectStore("http://minio:9000", "https://files.example.com", "evidence", "AKIDPEN", "s3cr3t-pen", 1.0)
    url = store.presigned_get("tenants/t1/evidence/" + "a" * 64, 300)
    q = parse_qs(urlparse(url).query)
    assert urlparse(url).netloc == "files.example.com"  # signed for the public host, not the internal one
    assert q["X-Amz-Expires"] == ["300"] and q["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"] and q["X-Amz-Signature"]
    assert "s3cr3t-pen" not in url


def _sup(api: Api, owner: Actor, tid: str, machine_id: str, subject: str) -> Actor:
    sup = Actor(api, subject, [f"/tenants/{tid}/supervisor"], tid, email=f"{subject}@pen.example.com")
    staff = owner.post(f"{T}/staff", {"full_name": subject, "kind": "SUPERVISOR", "keycloak_subject": subject}).json()
    r = owner.post(
        f"{T}/machines/{machine_id}/assignments",
        {"staff_member_id": staff["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert r.status_code == 201, r.text
    return sup


def _h(actor: Actor, device: str = DEVICE) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": device}


def test_revoked_device_is_refused_on_every_sync_endpoint_and_device_ids_are_user_bound(api: Api) -> None:
    c = setup_job(api, "Device Co", "DEV-1")
    tid = c.t.tenant["tenant"]["id"]
    sup = _sup(api, c.owner, tid, c.t.machine_id, "sup-dev")
    reg = api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1"}
    )
    assert reg.status_code == 201, reg.text
    data = unique_jpeg()
    blob = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(sup),
        json={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "purpose": "METER_PHOTO"},
    ).json()

    # Another user of the same tenant presenting this device id is not that device.
    thief = Actor(api, "sup-thief", [f"/tenants/{tid}/supervisor"], tid, email="thief@pen.example.com")
    assert api.client.get("/api/v1/sync/bootstrap", headers=_h(thief)).json()["error"]["code"] == (
        "DEVICE_NOT_REGISTERED"
    )

    dev = c.owner.get(f"{T}/devices").json()[0]
    assert c.owner.post(f"{T}/devices/{dev['id']}/revoke", {"reason": "Phone lost on site"}).status_code == 200
    note = {
        "id": str(uuid.uuid4()),
        "op_type": "JOB_ACTIVITY",
        "payload": {"job_id": c.job_id, "client_id": str(uuid.uuid4()), "activity_type": "NOTE"},
        "created_at_device": api.clock.now.isoformat(),
        "depends_on": [],
    }
    calls: list[tuple[str, str, dict[str, Any]]] = [
        ("GET", "/api/v1/sync/bootstrap", {}),
        ("GET", "/api/v1/sync/changes?cursor=0", {}),
        ("POST", "/api/v1/sync/push", {"json": {"device_now": api.clock.now.isoformat(), "operations": [note]}}),
        ("POST", "/api/v1/sync/blobs", {"json": {"sha256": "b" * 64, "size_bytes": 10, "purpose": "METER_PHOTO"}}),
        ("PUT", f"/api/v1/sync/blobs/{blob['id']}/chunks/0", {"content": data}),
        ("POST", f"/api/v1/sync/blobs/{blob['id']}/complete", {}),
        ("POST", "/api/v1/sync/devices", {"json": {"device_id": DEVICE, "platform": "ANDROID", "app_version": "2"}}),
    ]
    for method, url, kw in calls:
        r = api.client.request(method, url, headers=_h(sup), **kw)
        assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_REVOKED", (url, r.text)
        assert r.json()["error"]["details"][0]["issue"] == "WIPE_LOCAL_DATA"


def test_stale_offline_policy_is_refreshed_recorded_and_foreign_snapshots_refused(api: Api) -> None:
    c = setup_job(api, "Policy Co", "POL-1")
    tid = c.t.tenant["tenant"]["id"]
    sup = _sup(api, c.owner, tid, c.t.machine_id, "sup-pol")
    api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "IOS", "app_version": "1"}
    )
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    old = {s["scope_key"]: s for s in boot["policy_snapshots"] if s["policy_type"] == "METER_CAPTURE"}["tenant"]
    changed = c.owner.post(
        f"{T}/policies/METER_CAPTURE/versions",
        {"scope": "TENANT", "values": {"opening_mode": "MANUAL"}, "reason": "Owner switches to manual opening"},
    )
    assert changed.status_code == 201, changed.text
    # Next contact hands the device the new version (the old snapshot is superseded, never silently kept).
    delta = api.client.get(f"/api/v1/sync/changes?cursor={boot['cursor']}", headers=_h(sup)).json()
    new = {s["scope_key"]: s for s in delta["policy_snapshots"] if s["policy_type"] == "METER_CAPTURE"}["tenant"]
    assert new["version_stamp"] != old["version_stamp"] and changed.json()["id"] in new["version_ids"]

    # A capture made offline under the stale snapshot is accepted against it, with BOTH stamps recorded.
    now = api.clock.now
    r = c.owner.post(
        f"{T}/meter-captures",
        capture(
            c.job_id, "OPENING", "10.0", now, photo_id=photo(api, c.owner), gps=fix(now), snapshot=old["version_ids"]
        ),
    )
    assert r.status_code == 201, r.text
    stamp = r.json()["capture"]["policy_version"]
    assert new["version_stamp"] in stamp and "|device:" in stamp

    # Snapshot ids from another tenant are not resolvable here (RLS) -> refused, not applied.
    b = api.onboard("Policy Other", price="1")
    foreign = (
        b["owner"]
        .post(
            f"{T}/policies/METER_CAPTURE/versions",
            {"scope": "TENANT", "values": {"manual_photo_required": False}, "reason": "B lenient"},
        )
        .json()["id"]
    )
    bad = c.owner.post(
        f"{T}/meter-captures",
        capture(c.job_id, "OPENING", "11.0", now, gps=fix(now), snapshot=[foreign], capture_id=str(uuid.uuid4())),
    )
    assert bad.json()["error"]["code"] == "POLICY_SNAPSHOT_UNKNOWN", bad.text


def test_role_revocation_and_permission_removal_apply_to_still_valid_tokens(api: Api) -> None:
    a = api.onboard("Role Co", price="1")
    tid, owner = a["tenant"]["id"], a["owner"]
    r = owner.post(
        f"{T}/access/members",
        {"email": "mgr@role.example.com", "first_name": "M", "last_name": "G", "role_key": "manager"},
    )
    assert r.status_code == 201, r.text
    mgr = api.tenant_user("mgr@role.example.com", tid)
    stale_token = api.tokens.mint(mgr.subject, mgr.groups, email=mgr.email)  # issued before any change
    stale = {"Authorization": f"Bearer {stale_token}", "X-Tenant-ID": tid}
    assert api.client.get(f"{T}/machines", headers=stale).status_code == 200

    # Permission removed from the role group (Keycloak, mirrored): the unchanged token loses it on the next request.
    path = f"/tenants/{tid}/manager"
    gid = api.idp.groups[path]
    api.idp.set_group_permissions(gid, api.idp.group_perms[gid] - {"tenant.machine.read"})
    sync_mirror(api)
    assert api.client.get(f"{T}/machines", headers=stale).status_code == 403
    assert api.client.get(f"{T}/jobs", headers=stale).status_code == 200  # other permissions untouched

    # Role revoked through Asseta: the still-valid token (group claim present until expiry) is refused at once.
    revoked = owner.post(f"{T}/access/members/{r.json()['user_id']}/roles/manager/revoke")
    assert revoked.status_code == 200, revoked.text
    denied = api.client.get(f"{T}/jobs", headers=stale)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "TENANT_ACCESS_DENIED", denied.text
    fresh = Actor(api, mgr.subject, sorted(api.idp.memberships[mgr.subject]), tid)
    assert fresh.get(f"{T}/jobs").status_code == 403

    # Re-granted through Asseta: access returns (the deny is tied to the closed membership, not the person).
    again = owner.post(
        f"{T}/access/members",
        {"email": "mgr@role.example.com", "first_name": "M", "last_name": "G", "role_key": "manager"},
    )
    assert again.status_code == 201, again.text
    assert api.tenant_user("mgr@role.example.com", tid).get(f"{T}/jobs").status_code == 200
