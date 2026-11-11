"""Company closure (deletion): an owner asks to close the company (typed name, reason); it turns read-only at once and
stays so through billing runs; any holder of the permission can cancel (normal access returns); the platform-wide
waiting period (a platform-only DATA_PROTECTION setting) passes and the data protection sweep deletes EVERYTHING of the
company, keeping only the platform's billing records, the closure audit and a minimal closed tenant row; Keycloak users
who belong nowhere else are deleted (the rest keep their other companies); files and Traccar devices go; a deletion
that fails halfway resumes where it stopped; the platform can run it early with its own permission and a reason."""

import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI

from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.modules.dataprotection import closure_executor as ce
from asseta.modules.dataprotection.closure_executor import ClosureDeps, psycopg_dsn, run_due_closures
from asseta.modules.dataprotection.tenant_tables import CLOSURE_AUDIT_KEEP, CLOSURE_KEEP, DISCOVER
from asseta.modules.identity.role_templates import APPROVER_CONTROL_PERMISSIONS, TENANT_TEMPLATES, template_permissions
from asseta.workers.billing_scheduler import run_billing_cycle
from tests.support.api import Actor, Api
from tests.support.finance import complete_job, issue_invoice, setup_finance
from tests.support.idp import InMemoryObjectStore
from tests.support.notify import drain, member, platform_owner, sql, user_id

CLOSE = "/api/v1/tenant/company/deletion-request"
PLATFORM = "/api/v1/platform/deletion-requests"


class FakeTraccar:
    def __init__(self) -> None:
        self.removed: list[str] = []

    def remove(self, unique_ids: list[str]) -> list[str]:
        self.removed += unique_ids
        return [f"{u}: removed" for u in unique_ids]


class FlakyStore:
    """The test object store, failing every delete while `broken`."""

    def __init__(self, inner: Any):
        self.inner, self.broken = inner, True

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = self.inner.list_keys(prefix)
        return keys

    def delete(self, key: str) -> None:
        if self.broken:
            raise RuntimeError("object store unavailable")
        self.inner.delete(key)


def _store(api: Api) -> InMemoryObjectStore:
    app: FastAPI = api.client.app  # type: ignore[assignment]
    store: InMemoryObjectStore = app.state.object_store
    return store


def _deps(api: Api, *, store: Any = None, traccar: FakeTraccar | None = None) -> ClosureDeps:
    return ClosureDeps(
        session_factory=get_sessionmaker(),
        store=store or _store(api),
        idp=api.idp,
        owner_dsn=psycopg_dsn(get_settings().migration_database_url),
        clock=api.clock,
        traccar=traccar,
    )


def _counts(tid: str, op: str = "=") -> dict[str, int]:
    """Rows per discovered tenant-scoped table with a tenant_id, for `tenant_id = tid` (or `<>`)."""
    out: dict[str, int] = {}
    url = psycopg_dsn(get_settings().migration_database_url)
    with psycopg.connect(url, autocommit=True) as conn, conn.transaction(force_rollback=True):
        conn.execute("SELECT set_config('app.scope', 'system', true)")
        for table, has_tid in conn.execute(DISCOVER).fetchall():
            if has_tid:
                query = f"SELECT count(*) FROM {table} WHERE tenant_id {op} %s"  # noqa: S608 - catalog names
                row = conn.execute(query, (tid,)).fetchone()
                out[table] = row[0] if row else 0
    return out


def _request(owner: Actor, name: str, reason: str = "We are winding up the business") -> dict[str, Any]:
    r = owner.post(CLOSE, {"confirm_name": name, "reason": reason})
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def _types(tenant_id: str | None, user: uuid.UUID) -> list[str]:
    """The company-closure notifications of one recipient, oldest first."""
    cond = "notification_type LIKE 'COMPANY_%' AND " + ("tenant_id IS NULL" if tenant_id is None else "tenant_id = :t")
    rows = sql(
        f"SELECT notification_type FROM notification WHERE {cond} AND recipient_user_id = :u ORDER BY created_at",  # noqa: S608
        t=tenant_id,
        u=user,
    )
    return [r[0] for r in rows]


def test_close_company_permission_is_owner_only_and_approver_class() -> None:
    held = {t.key: template_permissions(t) for t in TENANT_TEMPLATES}
    assert "tenant.company.close" in held["owner"]
    assert [k for k, codes in held.items() if "tenant.company.close" in codes] == ["owner"]
    assert "tenant.company.close" in APPROVER_CONTROL_PERMISSIONS  # only an owner can give it to anyone


def test_request_read_only_cancel_and_notifications(api: Api) -> None:
    platform_owner(api)
    t = api.onboard("Closing Hire", price="1000")
    api.activate(t)
    owner: Actor = t["owner"]
    tid = t["tenant"]["id"]
    second = member(api, tid, "owner", "second-owner")
    manager = member(api, tid, "manager", "closing-manager")

    status = owner.get(CLOSE)
    assert status.status_code == 200, status.text
    assert status.json() == {"tenant_id": tid, "company_name": "Closing Hire", "waiting_days": 30, "request": None}
    # Only holders of the permission; the typed name must match; a reason is required.
    denied = manager.post(CLOSE, {"confirm_name": "Closing Hire", "reason": "Not mine to close"})
    assert denied.status_code == 403
    wrong = owner.post(CLOSE, {"confirm_name": "Closing Hire Ltd", "reason": "Winding up"})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "CONFIRMATION_MISMATCH"
    assert owner.post(CLOSE, {"confirm_name": "Closing Hire", "reason": ""}).status_code == 422

    req = _request(owner, "  closing HIRE ")  # case and surrounding spaces do not matter
    assert req["status"] == "REQUESTED" and req["waiting_days"] == 30 and req["requested_by_name"]
    assert req["scheduled_for"][:10] == (api.clock.now + timedelta(days=30)).date().isoformat()
    again = owner.post(CLOSE, {"confirm_name": "Closing Hire", "reason": "Twice"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "DELETION_ALREADY_REQUESTED"

    # Read-only for everyone at once; reads still work; the reason is shown.
    write = owner.post("/api/v1/tenant/machines", {"asset_code": "NEW-1", "name": "New"})
    assert write.status_code == 403 and write.json()["error"]["code"] == "SUBSCRIPTION_READ_ONLY"
    assert owner.get("/api/v1/tenant/machines").status_code == 200
    me = next(x for x in owner.get("/api/v1/me").json()["tenants"] if x["tenant_id"] == tid)
    assert me["access_state"] == "READ_ONLY" and "deleted on" in me["access_state_reason"]
    # The hourly billing run does not lift it (the entitlement evaluation keeps a closing company read-only).
    run_billing_cycle(api.clock.now.date())
    assert sql("SELECT access_state FROM tenant WHERE id = :t", t=tid)[0][0] == "READ_ONLY"
    assert owner.get(CLOSE).json()["request"]["status"] == "REQUESTED"

    # Platform view.
    listed = api.platform.get(PLATFORM, status="REQUESTED")
    assert listed.status_code == 200 and [x["id"] for x in listed.json()["items"]] == [req["id"]]
    assert listed.json()["items"][0]["tenant_name"] == "Closing Hire"

    drain(api)
    owners = [user_id(owner.subject), user_id(second.subject)]
    for u in owners:
        assert _types(tid, u) == ["COMPANY_DELETION_REQUESTED"]
    assert _types(tid, user_id(manager.subject)) == []  # not allowed to close: not told to act
    assert "COMPANY_DELETION_REQUESTED" in _types(None, user_id(api.platform.subject))
    emails = sql(
        "SELECT count(*) FROM notification_delivery WHERE channel = 'EMAIL' AND notification_type = 'COMPANY_DELETION_REQUESTED'"
    )
    assert emails[0][0] >= 3  # mandatory e-mail: both owners and the platform owner

    # Any holder of the permission cancels: normal access returns.
    assert second.post(f"{CLOSE}/cancel", {"reason": ""}).status_code == 422
    cancelled = second.post(f"{CLOSE}/cancel", {"reason": "We found a buyer"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED" and cancelled.json()["cancel_reason"] == "We found a buyer"
    assert sql("SELECT access_state FROM tenant WHERE id = :t", t=tid)[0][0] == "FULL"
    assert owner.post("/api/v1/tenant/machines", {"asset_code": "NEW-1", "name": "New"}).status_code == 201
    none_left = owner.post(f"{CLOSE}/cancel", {"reason": "Again"})
    assert none_left.status_code == 404 and none_left.json()["error"]["code"] == "NO_DELETION_REQUEST"
    drain(api)
    assert _types(tid, owners[0]) == ["COMPANY_DELETION_REQUESTED", "COMPANY_DELETION_CANCELLED"]
    actions = [
        r[0]
        for r in sql(
            "SELECT action FROM audit_event WHERE tenant_id = :t AND action LIKE 'platform.company_closure.%'"
            " ORDER BY occurred_at",
            t=tid,
        )
    ]
    assert actions == ["platform.company_closure.requested", "platform.company_closure.cancelled"]
    # A cancelled request never runs.
    api.clock.set_at(api.clock.now + timedelta(days=31))
    assert run_due_closures(_deps(api)) == 0


def test_waiting_period_is_a_platform_only_setting(api: Api) -> None:
    t = api.onboard("Setting Hire", price="1000")
    api.activate(t)
    owner: Actor = t["owner"]
    tenant_try = owner.post(
        "/api/v1/tenant/policies/DATA_PROTECTION/versions",
        {"scope": "TENANT", "values": {"company_deletion_waiting_days": 1}, "reason": "Faster please"},
    )
    assert tenant_try.status_code == 422 and tenant_try.json()["error"]["code"] == "POLICY_FIELD_NOT_OVERRIDABLE"
    r = api.platform.post(
        "/api/v1/platform/policies/DATA_PROTECTION/versions",
        {
            "scope": "PLATFORM",
            "values": {
                "balance_verification_enabled": False,
                "balance_verification_interval_days": 7,
                "data_export_retention_days": 7,
                "company_deletion_waiting_days": 14,
            },
            "reason": "Owner decision: two weeks",
        },
    )
    assert r.status_code == 201, r.text
    req = _request(owner, "Setting Hire")
    assert req["waiting_days"] == 14 and req["policy_version"].startswith("DATA_PROTECTION@P")
    assert req["scheduled_for"][:10] == (api.clock.now + timedelta(days=14)).date().isoformat()


def _seed(api: Api) -> dict[str, Any]:
    f = setup_finance(api, "Gone Hire", "GONE-1")
    complete_job(api, f, f.c.job_id, "500.0", "508.0", 9, downtime_h=1)
    issue_invoice(f, [f.c.job_id])
    sid = f.c.t.tenant["subscription_id"]
    api.generate(sid, api.clock.now.date())  # a platform invoice: kept
    return {"f": f, "tid": f.tid, "owner": f.owner, "sid": sid}


def test_due_sweep_deletes_everything_and_keeps_platform_billing(api: Api) -> None:
    platform_owner(api)
    seeded = _seed(api)
    tid, owner = seeded["tid"], seeded["owner"]
    other = api.onboard("Staying Hire", price="1000")
    api.activate(other)
    other_tid = other["tenant"]["id"]
    assert other["owner"].post("/api/v1/tenant/customers", {"code": "C1", "name": "Theirs"}).status_code == 201
    only_here = member(api, tid, "accountant", "only-here")
    both = member(api, tid, "manager", "in-both")
    member(api, other_tid, "manager", "in-both")
    store = _store(api)
    store.objects.update(
        {
            f"tenants/{tid}/evidence/a": (b"a", "image/jpeg", "x"),
            f"platform/ml-models/{tid}/m.pkl": (b"m", "application/octet-stream", "x"),
            f"tenants/{other_tid}/evidence/b": (b"b", "image/jpeg", "x"),
        }
    )
    before_mine = _counts(tid)
    assert before_mine["machine"] and before_mine["job"] and before_mine["staff_member"] and before_mine["tracker"]
    assert before_mine["platform_invoice"] >= 1

    req = _request(owner, "Gone Hire")
    drain(api)
    before_theirs = _counts(other_tid)  # (after the notifications of both companies were delivered)
    traccar = FakeTraccar()
    assert run_due_closures(_deps(api, traccar=traccar)) == 0  # waiting period not over
    api.clock.set_at(api.clock.now + timedelta(days=30, minutes=1))
    assert run_due_closures(_deps(api, traccar=traccar)) == 1

    done = api.platform.get(f"{PLATFORM}/{req['id']}").json()
    assert done["status"] == "COMPLETED" and done["completed_at"] and done["last_error"] is None
    assert done["steps_done"] == ["snapshot", "subscription", "identity", "objects", "traccar", "database"]
    assert done["tenant_name"] == "Gone Hire"
    # Every table of the company is empty but the platform's billing records and the closure record.
    after = _counts(tid)
    leftovers = {t: n for t, n in after.items() if n and t not in CLOSURE_KEEP and t != "audit_event"}
    assert leftovers == {"platform_invoice_line": before_mine["platform_invoice_line"]}  # printed lines of invoices
    for t in ("platform_invoice", "commercial_agreement", "tenant_subscription", "subscription_rate_version"):
        assert after[t] == before_mine[t] > 0, t
    assert after["company_deletion_request"] == 1
    kept_audit = sql("SELECT DISTINCT action FROM audit_event WHERE tenant_id = :t", t=tid)
    patterns = [p.rstrip("%") for p in CLOSURE_AUDIT_KEEP]
    assert kept_audit and all(any(a[0].startswith(p) for p in patterns) for a in kept_audit), kept_audit
    actions = {a[0] for a in kept_audit}
    assert {"platform.company_closure.requested", "platform.company_closure.completed"} <= actions
    assert "platform.tenant.onboarded" not in actions  # carried the contact details
    # The subscription was cancelled (billing stops; its records stay).
    assert sql("SELECT status FROM tenant_subscription WHERE tenant_id = :t", t=tid)[0][0] == "CANCELLED"
    # The minimal tenant row.
    row = sql(
        "SELECT status, access_state, legal_name, display_name, contact_name, contact_email, contact_phone,"
        " deleted_at, deletion_request_id FROM tenant WHERE id = :t",
        t=tid,
    )[0]
    assert (row.status, row.access_state, row.display_name, row.contact_name, row.contact_email) == (
        "CLOSED",
        "BLOCKED",
        "Gone Hire",
        "",
        "",
    )
    assert row.contact_phone is None and row.deleted_at is not None and str(row.deletion_request_id) == req["id"]
    # Nothing of the other company changed.
    assert _counts(other_tid) == before_theirs
    # Files and Traccar devices.
    assert sorted(store.objects) == [f"tenants/{other_tid}/evidence/b"]
    assert traccar.removed == ["GONE-1"]
    # Keycloak: the company's groups are gone; people who belonged only here are deleted and anonymised, someone
    # also working for another company keeps that membership and their account.
    assert not [p for p in api.idp.groups if p.startswith(f"/tenants/{tid}")]
    assert owner.subject in api.idp.deleted and only_here.subject in api.idp.deleted
    assert both.subject not in api.idp.deleted
    assert api.idp.memberships[both.subject] == {f"/tenants/{other_tid}/manager"}
    gone = sql(
        "SELECT display_name, email, is_active, deleted_at FROM app_user WHERE keycloak_subject = :s",
        s=only_here.subject,
    )[0]
    assert gone.display_name.startswith("Former user ") and gone.is_active is False and gone.deleted_at
    assert "only-here" not in gone.email
    kept_user = sql("SELECT is_active, deleted_at FROM app_user WHERE keycloak_subject = :s", s=both.subject)[0]
    assert kept_user.is_active is True and kept_user.deleted_at is None
    # The closure record keeps counts, not the people's or devices' identifiers.
    steps = sql("SELECT steps FROM company_deletion_request WHERE id = :i", i=req["id"])[0][0]
    assert "subjects" not in steps["snapshot"] and "trackers" in steps["snapshot"]
    assert steps["identity"]["accounts_deleted"] >= 3 and steps["identity"]["accounts_kept"] == 1
    assert steps["database"]["rows_deleted"] > 100
    # A stale token of a deleted owner no longer works.
    assert owner.get("/api/v1/tenant/machines").status_code == 403
    # The platform is told; running again changes nothing.
    drain(api)
    assert "COMPANY_DELETED" in _types(None, user_id(api.platform.subject))
    assert run_due_closures(_deps(api, traccar=traccar)) == 0
    # The platform's billing scheduler leaves the closed company alone.
    assert run_billing_cycle(api.clock.now.date()).failures == []


def test_failed_deletion_resumes_where_it_stopped_and_platform_runs_it_early(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded = _seed(api)
    tid, owner = seeded["tid"], seeded["owner"]
    req = _request(owner, "Gone Hire")
    auditor = Actor(api, "platform-auditor-subject", ["/platform/platform-auditor"], email="aud@asseta.local")
    assert auditor.get(PLATFORM).status_code == 200
    assert auditor.post(f"{PLATFORM}/{req['id']}/execute", {"reason": "Owner's letter"}).status_code == 403
    assert api.platform.post(f"{PLATFORM}/{req['id']}/execute", {"reason": ""}).status_code == 422
    early = api.platform.post(f"{PLATFORM}/{req['id']}/execute", {"reason": "Owner asked in writing (letter 12 Nov)"})
    assert early.status_code == 200, early.text
    assert early.json()["execute_now_reason"].startswith("Owner asked") and early.json()["status"] == "REQUESTED"

    # 1) the object store fails: the steps before it are recorded, the error kept, a retry scheduled.
    _store(api).objects[f"tenants/{tid}/evidence/a"] = (b"a", "image/jpeg", "x")
    flaky = FlakyStore(_store(api))
    assert run_due_closures(_deps(api, store=flaky)) == 0
    state = api.platform.get(f"{PLATFORM}/{req['id']}").json()
    assert state["status"] == "IN_PROGRESS" and state["attempts"] == 1
    assert state["steps_done"] == ["snapshot", "subscription", "identity"]
    assert state["last_error"].startswith("objects: RuntimeError")
    assert run_due_closures(_deps(api, store=flaky)) == 0  # backing off: not yet retried
    assert api.platform.get(f"{PLATFORM}/{req['id']}").json()["attempts"] == 1
    cancel = owner.post(f"{CLOSE}/cancel", {"reason": "Too late?"})
    assert cancel.status_code in (403, 409)  # the deletion has started (the owner's login may already be gone)

    # 2) the database step stops after a few tables: what was emptied stays recorded.
    flaky.broken = False
    real, calls = ce._delete_table, {"n": 0}

    def stop_after_five(conn: Any, request_id: uuid.UUID, table: str, t: uuid.UUID) -> int:
        calls["n"] += 1
        if calls["n"] == 6:
            raise RuntimeError("connection lost")
        return real(conn, request_id, table, t)

    monkeypatch.setattr(ce, "_delete_table", stop_after_five)
    api.clock.set_at(api.clock.now + timedelta(minutes=6))
    assert run_due_closures(_deps(api, store=flaky)) == 0
    state = api.platform.get(f"{PLATFORM}/{req['id']}").json()
    assert state["steps_done"] == ["snapshot", "subscription", "identity", "objects", "traccar"]
    assert state["last_error"].startswith("database: RuntimeError") and state["attempts"] == 2
    progress = sql("SELECT steps->'database_tables' FROM company_deletion_request WHERE id = :i", i=req["id"])[0][0]
    assert len(progress) == 5

    # 3) resumed: it completes, from the sixth table on.
    monkeypatch.setattr(ce, "_delete_table", real)
    api.clock.set_at(api.clock.now + timedelta(minutes=11))
    assert run_due_closures(_deps(api, store=flaky)) == 1
    state = api.platform.get(f"{PLATFORM}/{req['id']}").json()
    assert state["status"] == "COMPLETED" and state["attempts"] == 3 and state["last_error"] is None
    assert not {
        t: n
        for t, n in _counts(tid).items()
        if n and t not in CLOSURE_KEEP and t not in ("audit_event", "platform_invoice_line")
    }
    assert _store(api).list_keys(f"tenants/{tid}/") == []
    steps = sql("SELECT steps FROM company_deletion_request WHERE id = :i", i=req["id"])[0][0]
    assert steps["traccar"]["skipped"].startswith("Traccar admin credentials not configured")
    actions = [
        r[0]
        for r in sql(
            "SELECT action FROM audit_event WHERE tenant_id = :t AND action LIKE 'platform.company_closure.%'"
            " ORDER BY occurred_at",
            t=tid,
        )
    ]
    assert actions == [
        "platform.company_closure.requested",
        "platform.company_closure.execute_now",
        "platform.company_closure.started",
        "platform.company_closure.completed",
    ]
    # Executing a completed request is refused.
    again = api.platform.post(f"{PLATFORM}/{req['id']}/execute", {"reason": "Once more"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "DELETION_NOT_ACTIVE"
