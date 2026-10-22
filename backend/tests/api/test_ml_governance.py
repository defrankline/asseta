"""Gate 6C: training from per-tenant snapshots, readiness, the model lifecycle (approve / deploy / rollback /
disable), the inference hard switch, permissions, DB immutability and tenant isolation of governance records."""

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.ml.datasets import TenantMixingError
from asseta.ml.synthetic import fleet_snapshots, generate_fleet
from asseta.ml.tracking import MlflowTracker
from asseta.ml.training import train_and_evaluate
from tests.support.api import Actor, Api
from tests.support.idp import InMemoryObjectStore
from tests.support.ml import LENIENT, STRICT, act, load_synthetic, model, train
from tests.support.notify import sql

GOVERNANCE = ("feature_snapshot", "model_version", "model_evaluation", "model_approval", "model_readiness")


class BrokenClient:
    """An unreachable MLflow server: every client call fails to connect."""

    def __getattr__(self, name: str) -> Any:
        def fail(*_a: Any, **_k: Any) -> None:
            raise ConnectionError("mlflow down")

        return fail


def tenant(api: Api, name: str) -> tuple[str, Actor]:
    t = api.onboard(name, price="1000")
    return t["tenant"]["id"], t["owner"]


def status(owner: Actor) -> dict[str, Any]:
    r = owner.get("/api/v1/tenant/ml/status")
    assert r.status_code == 200, r.text
    assert "score" not in r.text.lower()  # plain readiness/deployment facts only
    out: dict[str, Any] = r.json()
    return out


def test_insufficient_data_records_readiness_and_no_model(api: Api) -> None:
    tid, owner = tenant(api, "Fresh Co")
    assert status(owner)["readiness"] is None and "Not assessed" in status(owner)["summary"]
    r = api.platform.post(f"/api/v1/platform/ml/tenants/{tid}/train", {})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["model"] is None and out["readiness"]["status"] == "INSUFFICIENT_DATA"
    assert out["readiness"]["reasons"] and out["readiness"]["minimums"]["min_machines"] == 5
    assert sql("SELECT count(*) AS n FROM model_version")[0].n == 0
    s = status(owner)
    assert s["readiness"]["status"] == "INSUFFICIENT_DATA" and s["deployed"] is None
    assert s["summary"].startswith("Not enough history") and s["inference_enabled"] is True
    listing = api.platform.get("/api/v1/platform/ml/readiness", status="INSUFFICIENT_DATA").json()
    assert [x["tenant_id"] for x in listing["items"]] == [tid] and listing["items"][0]["tenant_name"] == "Fresh Co"


def test_synthetic_fleet_trains_an_evaluated_model_against_the_baseline(api: Api) -> None:
    tid, owner = tenant(api, "Fleet Co")
    assert load_synthetic(tid, api.clock.now) == 8 * 14 * 13
    r = api.platform.post(f"/api/v1/platform/ml/tenants/{tid}/train", {})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["readiness"]["status"] == "READY" and out["model"]["status"] == "EVALUATED"
    m = out["model"]
    assert (m["version"], m["algorithm"], m["baseline_algorithm"]) == (1, "ISOLATION_FOREST", "ROBUST_Z_BASELINE")
    assert m["mlflow_run_id"] is None and "not configured" in m["tracking_note"]
    detail = model(api.platform, m["id"])
    ev = detail["evaluation"]
    assert set(ev["metrics"]) >= {"baseline", "candidate", "recall_lift"}
    assert "recall_at_k" in ev["metrics"]["baseline"] and "alert_rate" in ev["metrics"]["candidate"]
    assert ev["reasons"] and ev["criteria"]["promotion"]["min_recall_lift"] == 0.05
    assert [a["action"] for a in detail["approvals"]] == ["TRAIN"]
    assert detail["manifest"]["rows"]["train"] > 0 and len(detail["manifest"]["feature_codes"]) == 13
    [stored] = sql("SELECT artifact_key, artifact_sha256 FROM model_version")
    assert stored.artifact_key.startswith(f"platform/ml-models/{tid}/machine-week-anomaly/")
    s = status(owner)
    assert s["readiness"]["status"] == "READY" and s["deployed"] is None
    second = api.platform.post(f"/api/v1/platform/ml/tenants/{tid}/train", {}).json()
    assert second["model"]["version"] == 2  # versions are numbered per tenant + name


def test_lifecycle_rules(api: Api) -> None:
    tid, owner = tenant(api, "Life Co")
    load_synthetic(tid, api.clock.now)
    good = train(tid, api.clock.now, LENIENT)
    weak = train(tid, api.clock.now, STRICT)
    assert good["passed"] is True and weak["passed"] is False
    v1, v2, p = good["model_id"], weak["model_id"], api.platform

    r = act(p, v1, "deploy-active")
    assert r.status_code == 422 and r.json()["error"]["code"] == "APPROVAL_REQUIRED"
    for action in ("deploy-active", "approve"):
        r = act(p, v2, action)
        assert r.status_code == 422 and r.json()["error"]["code"] == "EVALUATION_NOT_PASSED"
    assert act(p, v2, "deploy-shadow", "x").status_code == 422  # a reason is required (>= 3 chars)
    r = act(p, v2, "deploy-shadow", "Observe in shadow")  # shadow does not need a passing evaluation
    assert r.status_code == 200 and r.json()["model"]["status"] == "DEPLOYED_SHADOW"
    assert status(owner)["deployed"]["mode"] == "SHADOW"

    key = str(uuid.uuid4())
    first = p.post(f"/api/v1/platform/ml/models/{v1}/approve", {"reason": "Metrics reviewed"}, key=key)
    replay = p.post(f"/api/v1/platform/ml/models/{v1}/approve", {"reason": "Metrics reviewed"}, key=key)
    assert first.status_code == replay.status_code == 200 and first.json() == replay.json()
    assert first.json()["model"]["status"] == "APPROVED"
    stale = act(p, v1, "deploy-active", lock_version=1)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    r = act(p, v1, "deploy-active", "Go live")
    assert r.status_code == 200 and r.json()["model"]["status"] == "DEPLOYED_ACTIVE"
    assert model(p, v2)["model"]["status"] == "RETIRED"  # one deployed version per tenant + name
    deployed = sql("SELECT count(*) AS n FROM model_version WHERE status LIKE 'DEPLOYED%'")[0].n
    assert deployed == 1 and status(owner)["deployed"] == {
        "name": "machine-week-anomaly",
        "version": 1,
        "mode": "ACTIVE",
        "deployed_at": status(owner)["deployed"]["deployed_at"],
    }

    r = act(p, v1, "rollback", "False positives in week 1")
    assert r.status_code == 200 and r.json()["model"]["status"] == "RETIRED"
    assert model(p, v2)["model"]["status"] == "DEPLOYED_SHADOW"  # previous version, in the mode it had
    assert act(p, v1, "rollback").json()["error"]["code"] == "MODEL_NOT_DEPLOYED"
    r = act(p, v2, "disable", "Disabled pending review")
    assert r.status_code == 200 and r.json()["model"]["status"] == "DISABLED"
    assert status(owner)["deployed"] is None
    assert act(p, v2, "deploy-shadow").json()["error"]["code"] == "INVALID_MODEL_TRANSITION"
    actions = [a["action"] for a in model(p, v2)["approvals"]]
    assert actions == ["TRAIN", "DEPLOY_SHADOW", "RETIRE", "ROLLBACK", "DISABLE"]
    events = sql("SELECT event_type FROM outbox_event WHERE event_type LIKE 'MlModel%' ORDER BY created_at")
    assert [e.event_type for e in events].count("MlModelDeployed") == 3 and events[-1].event_type == "MlModelDisabled"
    audit = sql("SELECT action, reason FROM audit_event WHERE action LIKE 'platform.ml.model.%'")
    assert {a.action for a in audit} >= {"platform.ml.model.approve", "platform.ml.model.rollback"}
    listed = p.get("/api/v1/platform/ml/models", tenant_id=tid, status="DISABLED").json()
    assert [x["id"] for x in listed["items"]] == [v2] and listed["items"][0]["evaluation_passed"] is False

    # Database guards as the application role: approvals/evaluations append-only, status graph enforced.
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.PLATFORM, None, None)
        for stmt in (
            "UPDATE model_approval SET reason = 'rewritten'",
            "DELETE FROM model_approval",
            "UPDATE model_evaluation SET passed = true",
            f"UPDATE model_version SET status = 'DEPLOYED_ACTIVE' WHERE id = '{v2}'",  # noqa: S608
            f"UPDATE model_version SET feature_set_hash = 'x' WHERE id = '{v1}'",  # noqa: S608
            "DELETE FROM model_version",
        ):
            with pytest.raises(DBAPIError), s.begin_nested():
                s.execute(text(stmt))


def test_hard_switch_is_audited_and_reaches_tenants(api: Api) -> None:
    _, owner = tenant(api, "Switch Co")
    p = api.platform
    got = p.get("/api/v1/platform/ml/settings").json()
    assert got["inference_enabled"] is True and got["lock_version"] == 0
    assert p.put("/api/v1/platform/ml/settings", {"inference_enabled": False}).status_code == 422
    r = p.put("/api/v1/platform/ml/settings", {"inference_enabled": False, "reason": "Incident review"})
    assert r.status_code == 200 and r.json()["inference_enabled"] is False and r.json()["lock_version"] == 1
    stale = p.put("/api/v1/platform/ml/settings", {"inference_enabled": True, "reason": "Again", "lock_version": 7})
    assert stale.status_code == 409
    s = status(owner)
    assert s["inference_enabled"] is False and "switched off" in s["summary"]
    [audit] = sql("SELECT reason, after FROM audit_event WHERE action = 'platform.ml.settings.updated'")
    assert audit.reason == "Incident review" and audit.after == {"inference_enabled": False}
    [event] = sql("SELECT payload FROM outbox_event WHERE event_type = 'MlInferenceSwitched'")
    assert event.payload["inference_enabled"] is False
    auditor = Actor(api, "auditor-subject", ["/platform/platform-auditor"], email="auditor@asseta.local")
    assert auditor.get("/api/v1/platform/ml/settings").status_code == 200
    assert auditor.put("/api/v1/platform/ml/settings", {"inference_enabled": True, "reason": "Nope"}).status_code == 403


def test_permissions_and_tenant_isolation(api: Api) -> None:
    a_tid, a_owner = tenant(api, "Alpha Co")
    b_tid, b_owner = tenant(api, "Beta Co")
    load_synthetic(a_tid, api.clock.now)
    a_model = train(a_tid, api.clock.now)["model_id"]
    assert train(b_tid, api.clock.now)["readiness"] == "INSUFFICIENT_DATA"  # A's history never reaches B

    for path in ("/api/v1/platform/ml/models", "/api/v1/platform/ml/settings", "/api/v1/platform/ml/readiness"):
        assert a_owner.get(path).status_code == 403
    assert a_owner.post(f"/api/v1/platform/ml/models/{a_model}/approve", {"reason": "self"}).status_code == 403
    assert a_owner.post(f"/api/v1/platform/ml/tenants/{a_tid}/train", {}).status_code == 403
    assert api.platform.get("/api/v1/tenant/ml/status").status_code == 403  # tenant endpoint needs a tenant
    auditor = Actor(api, "auditor-2", ["/platform/platform-auditor"], email="auditor2@asseta.local")
    assert auditor.get(f"/api/v1/platform/ml/models/{a_model}").status_code == 200
    assert auditor.post(f"/api/v1/platform/ml/models/{a_model}/deploy-shadow", {"reason": "x" * 5}).status_code == 403

    b_status = status(b_owner)
    assert b_status["readiness"]["status"] == "INSUFFICIENT_DATA" and status(a_owner)["readiness"]["status"] == "READY"
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(b_tid), None)
        counts = {}
        for t in GOVERNANCE:
            query = text(f"SELECT count(*) FROM {t} WHERE tenant_id = :a")  # noqa: S608
            counts[t] = s.execute(query, {"a": a_tid}).scalar_one()
        assert counts == dict.fromkeys(GOVERNANCE, 0)
    with get_sessionmaker().begin() as s:  # tenants never write governance records, not even their own
        apply_scope(s, DbScope.TENANT, uuid.UUID(a_tid), None)
        assert s.execute(text("UPDATE model_version SET status = 'DISABLED'")).rowcount == 0  # type: ignore[attr-defined]
        for stmt in (
            "INSERT INTO ml_setting (id, inference_enabled, reason, updated_at, lock_version)"
            " VALUES (1, false, 'x', now(), 1)",
            'INSERT INTO feature_definition (id, code, version, entity, domain, "window", window_seconds, unit,'
            " description, inputs, created_at) VALUES (gen_random_uuid(), 'x', 1, 'MACHINE', 'METER', '7d', 1,"
            " 'h', 'x', '[]', now())",
        ):
            with pytest.raises(DBAPIError), s.begin_nested():
                s.execute(text(stmt))
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(a_tid), None)
        assert s.execute(text("SELECT count(*) FROM model_version")).scalar_one() == 1  # own rows readable

    mixed = [*fleet_snapshots(generate_fleet("t-a", 3, 4)), *fleet_snapshots(generate_fleet("t-b", 3, 4))]
    with pytest.raises(TenantMixingError):
        train_and_evaluate(mixed)


def test_unreachable_mlflow_still_persists_the_model(api: Api) -> None:
    tid, _ = tenant(api, "Offline Co")
    load_synthetic(tid, api.clock.now)
    store = InMemoryObjectStore()
    tracker = MlflowTracker("http://mlflow.invalid", client=BrokenClient())  # type: ignore[arg-type]
    out = train(tid, api.clock.now, tracker=tracker, store=store)
    assert out["model_id"] and out["mlflow_run_id"] is None
    assert "ConnectionError" in out["tracking_note"]
    [(key, (data, content_type, sha))] = store.objects.items()
    assert key.endswith(f"{sha}.pkl") and content_type == "application/octet-stream" and len(data) > 1000
    assert model(api.platform, out["model_id"])["model"]["tracking_note"] == out["tracking_note"]
