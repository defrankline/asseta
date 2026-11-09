"""Guideline 9: a read-only company keeps access to its data (export request and download link only; audited; blocked
still refused). Administration -> Devices: the list a tenant owner sees and revoking a lost phone."""

from typing import Any

from sqlalchemy import Engine, text

from asseta.core.db import get_sessionmaker
from asseta.modules.dataprotection.export_worker_core import run_pending
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance

T = "/api/v1/tenant"
DEVICE = "lost-phone-0001"


def _access(owner_engine: Engine, tid: str, state: str) -> None:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        c.execute(text("UPDATE tenant SET access_state = :s WHERE id = :t"), {"s": state, "t": tid})


def _audit(owner_engine: Engine, tid: str, action: str) -> list[Any]:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        return list(
            c.execute(
                text("SELECT after, reason FROM audit_event WHERE tenant_id = :t AND action = :a"),
                {"t": tid, "a": action},
            ).all()
        )


def _code(r: Any) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


def _register(api: Api, f: FinCtx, device: str = DEVICE, model: str | None = "Samsung SM-A155") -> str:
    h = f.supervisor.headers(True, None) | {"X-Device-Id": device}
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=h,
        json={"device_id": device, "platform": "ANDROID", "app_version": "1.4.2", "device_model": model},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_read_only_company_can_still_request_and_download_its_export(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    _access(owner_engine, f.tid, "READ_ONLY")

    r = f.owner.post(f"{T}/data-exports", {"format": "CSV"})
    assert r.status_code == 201, r.text
    export_id = r.json()["id"]
    assert run_pending(get_sessionmaker(), api.client.app.state.object_store, api.clock.now) == 1  # type: ignore[attr-defined]
    link = f.owner.post(f"{T}/data-exports/{export_id}/download")
    assert link.status_code == 200 and link.json()["url"].startswith("https://objects.test/")

    requested = _audit(owner_engine, f.tid, "tenant.data_export.requested")
    downloaded = _audit(owner_engine, f.tid, "tenant.data_export.downloaded")
    assert [a[0]["subscription_read_only"] for a in requested + downloaded] == [True, True]


def test_exemption_covers_only_those_two_actions_and_keeps_the_permission(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    device = _register(api, f)
    _access(owner_engine, f.tid, "READ_ONLY")

    assert f.manager.post(f"{T}/data-exports", {"format": "CSV"}).status_code == 403
    assert _code(f.owner.post(f"{T}/balance-verification/runs")) == (403, "SUBSCRIPTION_READ_ONLY")
    assert _code(f.owner.post(f"{T}/devices/{device}/revoke", {"reason": "Phone lost"})) == (
        403,
        "SUBSCRIPTION_READ_ONLY",
    )
    assert f.owner.get(f"{T}/devices").status_code == 200


def test_blocked_company_still_cannot_reach_exports(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    row = f.owner.post(f"{T}/data-exports", {"format": "CSV"}).json()
    _access(owner_engine, f.tid, "BLOCKED")

    blocked = (403, "TENANT_ACCESS_BLOCKED")
    assert _code(f.owner.post(f"{T}/data-exports", {"format": "JSON"})) == blocked
    assert _code(f.owner.post(f"{T}/data-exports/{row['id']}/download")) == blocked
    assert _code(f.owner.get(f"{T}/data-exports")) == blocked


def test_normal_export_audit_is_not_marked_read_only(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    assert f.owner.post(f"{T}/data-exports", {"format": "CSV"}).status_code == 201
    assert "subscription_read_only" not in _audit(owner_engine, f.tid, "tenant.data_export.requested")[0][0]


def _rows(actor: Actor, q: str | None = None) -> list[dict[str, Any]]:
    r = actor.get(f"{T}/devices", **({"q": q} if q else {}))
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


def test_tenant_owner_lists_searches_and_revokes_a_phone(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    device_id = _register(api, f)

    row = _rows(f.owner)[0]
    assert row["id"] == device_id and row["user_name"] and row["status"] == "ACTIVE"
    assert (row["platform"], row["app_version"], row["device_model"]) == ("ANDROID", "1.4.2", "Samsung SM-A155")
    assert "last_sync_at" in row and row["revoked_by_name"] is None
    assert f.owner.get(f"{T}/devices/{device_id}").json()["id"] == device_id
    assert [r["id"] for r in _rows(f.owner, row["user_name"].split()[0])] == [device_id]
    assert [r["id"] for r in _rows(f.owner, "SM-A155")] == [device_id]
    assert _rows(f.owner, "no-such-phone") == []

    assert f.manager.get(f"{T}/devices").status_code == 403  # the permission, not the role name
    assert f.supervisor.post(f"{T}/devices/{device_id}/revoke", {"reason": "Phone lost"}).status_code == 403
    assert f.owner.post(f"{T}/devices/{device_id}/revoke", {"reason": "x"}).status_code == 422

    done = f.owner.post(f"{T}/devices/{device_id}/revoke", {"reason": "Phone reported lost"})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "REVOKED" and body["revoke_reason"] == "Phone reported lost" and body["revoked_by_name"]
    assert _audit(owner_engine, f.tid, "sync.device.revoked")[0][1] == "Phone reported lost"

    # The first revocation stands: its time, person and reason are never rewritten.
    assert _code(f.owner.post(f"{T}/devices/{device_id}/revoke", {"reason": "Second try"})) == (
        409,
        "DEVICE_ALREADY_REVOKED",
    )
    assert _rows(f.owner)[0]["revoke_reason"] == "Phone reported lost"


def test_model_is_optional_and_devices_stay_within_the_tenant(api: Api) -> None:
    f = setup_finance(api)
    other = api.onboard("Other Hire", price="1")["owner"]
    _register(api, f, device="phone-without-model", model=None)

    assert _rows(f.owner)[0]["device_model"] is None
    assert _rows(other) == []
    assert other.get(f"{T}/devices/{_rows(f.owner)[0]['id']}").status_code == 404
