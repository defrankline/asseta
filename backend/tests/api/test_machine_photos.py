"""R1-B machine photos: magic-byte validation, content-hash idempotency, size limit, tenant-scoped short-lived URLs,
DB immutability (acceptance §10 #11 storage URL access)."""

from httpx import Response
from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"asseta-test-image"


def _upload(api: Api, owner: Actor, machine_id: str, data: bytes, caption: str = "Front view") -> Response:
    r: Response = api.client.post(
        f"/api/v1/tenant/machines/{machine_id}/photos",
        headers=owner.headers(True, None),
        files={"file": ("photo.jpg", data, "image/jpeg")},
        data={"caption": caption},
    )
    return r


def test_machine_photo_lifecycle_and_isolation(api: Api) -> None:
    t = api.onboard("Photo Co", price="1")
    owner = t["owner"]
    [machine_id] = api.add_machines(owner, 1)
    r = _upload(api, owner, machine_id, JPEG)
    assert r.status_code == 201, r.text
    photo = r.json()
    assert photo["content_type"] == "image/jpeg" and len(photo["sha256"]) == 64
    again = _upload(api, owner, machine_id, JPEG, caption="different caption")
    assert again.json()["id"] == photo["id"]
    fake = _upload(api, owner, machine_id, b"%PDF-1.7 not an image")
    assert fake.json()["error"]["code"] == "UNSUPPORTED_MEDIA"

    url = owner.get(f"/api/v1/tenant/machines/{machine_id}/photos/{photo['id']}/url").json()
    assert url["expires_in_seconds"] == 300 and f"tenants/{t['tenant']['id']}/" in url["url"]
    assert "X-Amz-Expires=300" in url["url"]

    other = api.onboard("Photo Other", price="1")["owner"]
    assert other.get(f"/api/v1/tenant/machines/{machine_id}/photos").status_code == 404
    assert other.get(f"/api/v1/tenant/machines/{machine_id}/photos/{photo['id']}/url").status_code == 404
    assert _upload(api, other, machine_id, JPEG).status_code == 404

    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        try:
            s.execute(text("UPDATE machine_photo SET caption = 'tampered'"))
            raise AssertionError("photo evidence mutated")
        except Exception as exc:
            assert "permission denied" in str(exc) or "immutable" in str(exc)
