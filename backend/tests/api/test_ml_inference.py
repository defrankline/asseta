"""Gate 6D: bounded shadow/active inference with provenance, tenant visibility (API + RLS), the hard switch, artifact
failures that never stop deterministic rules, disabled models, and drift monitoring."""

import dataclasses
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.intelligence.inference import SURFACED_TITLE, clear_bundle_cache
from asseta.modules.intelligence.ml_monitoring import run_drift_cycle
from asseta.workers.intelligence_worker import run_ml_cycle
from tests.support.api import Actor, Api
from tests.support.finance import complete_job, setup_finance
from tests.support.idp import InMemoryObjectStore
from tests.support.intelligence import fraud_policy, signals, sweep
from tests.support.ml import LENIENT, act, fleet_for, infer, last_week_end, model, shifted_week, store, train
from tests.support.notify import sql


def fleet_tenant(api: Api, name: str, n: int = 8) -> tuple[str, Actor, list[str]]:
    t = api.onboard(name, price="1000")
    owner = t["owner"]
    return t["tenant"]["id"], owner, api.add_machines(owner, n, prefix=name[:3].upper())


def tenant_count(tid: str, table: str) -> int:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        return int(s.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608 - fixed names


def no_fraud(*payloads: Any) -> None:
    """No accusation wording; the policy-type identifier FRAUD_CONTROLS (a version stamp) is not wording."""
    for p in payloads:
        assert "fraud" not in json.dumps(p).lower().replace("fraud_controls", "")


def deployed(api: Api, tid: str, objects: InMemoryObjectStore, machines: list[str], mode: str = "shadow") -> str:
    store(tid, fleet_for(tid, machines, last_week_end(api.clock.now)), api.clock.now)
    m = train(tid, api.clock.now, LENIENT, store=objects)["model_id"]
    if mode == "active":
        assert act(api.platform, m, "approve").status_code == 200
    r = act(api.platform, m, f"deploy-{mode}", "Observe the model")
    assert r.status_code == 200, r.text
    return str(m)


def test_shadow_predictions_carry_provenance_and_stay_platform_only(api: Api) -> None:
    tid, owner, machines = fleet_tenant(api, "Shadow Co")
    objects = InMemoryObjectStore()
    m = deployed(api, tid, objects, machines)
    result = infer(api.clock.now, objects, tid)
    [run] = result.results
    assert (run.outcome.value, run.input_rows, run.written, run.surfaced) == ("OK", 8, 8, 0)

    rows = sql("SELECT * FROM prediction ORDER BY subject_id")
    assert len(rows) == 8 and {r.decision_state for r in rows} == {"SHADOW"}
    p = rows[0]
    assert str(p.model_version_id) == m and p.model_name == "machine-week-anomaly" and p.deployment_mode == "SHADOW"
    assert p.evaluation_id is not None and p.approval_id is None and p.case_id is None
    assert len(p.feature_snapshot_ids) == 13 and p.as_of == last_week_end(api.clock.now)
    assert p.feature_set_hash and p.policy_version.startswith("FRAUD_CONTROLS@") and float(p.threshold) == 0.98
    assert p.calibrated is True and p.score is not None and p.raw_score is not None and p.baseline_raw_score is not None
    assert p.explanations and p.contributions[0]["reference_scope"] in ("machine", "fleet")
    stored_ids = {str(r.id) for r in sql("SELECT id FROM feature_snapshot WHERE entity_id = :e", e=p.subject_id)}
    assert {str(i) for i in p.feature_snapshot_ids} <= stored_ids
    [audit] = sql("SELECT * FROM inference_audit")
    assert (audit.outcome, audit.input_rows, audit.predictions_written, audit.reason) == ("OK", 8, 8, None)
    assert audit.latency_ms >= 0 and str(audit.tenant_id) == tid

    # Tenants never see shadow output: API and RLS.
    assert owner.get("/api/v1/tenant/ml/predictions").json()["total"] == 0
    assert owner.get("/api/v1/tenant/cases").json()["total"] == 0
    status = owner.get("/api/v1/tenant/ml/status").json()
    assert (status["state"], status["label"]) == ("LEARNING_SHADOW", "Learning (shadow)")
    assert tenant_count(tid, "prediction") == 0 and tenant_count(tid, "inference_audit") == 0
    assert tenant_count(tid, "model_drift") == 0
    no_fraud(status, [r.explanations for r in rows])

    # Platform sees everything with provenance; re-running is idempotent.
    listing = api.platform.get("/api/v1/platform/ml/predictions", model_version_id=m).json()
    assert listing["total"] == 8 and listing["items"][0]["feature_snapshot_ids"]
    again = infer(api.clock.now, objects, tid).results[0]
    assert (again.outcome.value, again.written) == ("OK", 0) and sql("SELECT count(*) AS n FROM prediction")[0].n == 8
    mon = model(api.platform, m)["monitoring"]
    assert mon["predictions_by_state"] == {"SHADOW": 8} and mon["runs_by_outcome"] == {"OK": 2}
    assert mon["latency_p50_ms"] is not None and mon["latency_p95_ms"] >= mon["latency_p50_ms"]
    with get_sessionmaker().begin() as s, pytest.raises(DBAPIError):
        apply_scope(s, DbScope.SYSTEM, None, None)
        s.execute(text("UPDATE prediction SET decision_state = 'SURFACED'"))


def test_active_model_above_threshold_surfaces_a_neutral_case(api: Api) -> None:
    tid, owner, machines = fleet_tenant(api, "Active Co")
    objects = InMemoryObjectStore()
    end = last_week_end(api.clock.now) - timedelta(weeks=1)
    snaps = fleet_for(tid, machines, end, anomaly_rate=0.0)  # clean history: calibration sees normal weeks only
    store(tid, snaps, api.clock.now - timedelta(weeks=1))
    m = train(tid, api.clock.now, LENIENT, store=objects)["model_id"]
    assert act(api.platform, m, "approve").status_code == 200
    assert act(api.platform, m, "deploy-active", "Go live").status_code == 200
    unusual = shifted_week(
        [s for s in snaps if s.entity_id == machines[0]],
        fuel_litres=6,
        litres_per_meter_hour=6,
        outside_geofence_minutes=20,
        km_travelled=8,
        expense_total=10,
    )
    normal = shifted_week([s for s in snaps if s.entity_id != machines[0]])
    store(tid, unusual + normal, api.clock.now)

    [run] = infer(api.clock.now, objects, tid).results
    assert run.outcome.value == "OK" and run.surfaced >= 1
    rows = {str(r.subject_id): r for r in sql("SELECT * FROM prediction")}
    hit = rows[machines[0]]
    assert hit.decision_state == "SURFACED" and hit.would_surface and float(hit.score) >= 0.98
    assert hit.approval_id is not None and hit.case_id is not None and hit.deployment_mode == "ACTIVE"
    assert {r.decision_state for r in rows.values()} <= {"SURFACED", "BELOW_THRESHOLD"}
    surfaced = [r for r in rows.values() if r.decision_state == "SURFACED"]
    assert all(r.case_id is not None for r in surfaced)

    case = owner.get(f"/api/v1/tenant/cases/{hit.case_id}").json()
    assert case["case"]["title"] == SURFACED_TITLE and case["case"]["subject_type"] == "MACHINE"
    assert case["case"]["machine_id"] == machines[0]
    [link] = [s for s in case["signals"] if s["source_type"] == "PREDICTION"]
    assert link["source_id"] == str(hit.id) and "machine's median" in " ".join(link["evidence"]["observations"])
    preds = owner.get("/api/v1/tenant/ml/predictions").json()
    assert preds["total"] == len(surfaced) and "score" not in json.dumps(preds)
    assert tenant_count(tid, "prediction") == len(surfaced)  # RLS: SURFACED rows only
    status = owner.get("/api/v1/tenant/ml/status").json()
    assert (status["state"], status["label"]) == ("ACTIVE", "Active")
    no_fraud(case, preds, status, owner.get("/api/v1/tenant/cases").json())


def test_hard_switch_off_means_no_inference_and_one_skipped_audit(api: Api) -> None:
    tid, owner, machines = fleet_tenant(api, "Switch Co")
    objects = InMemoryObjectStore()
    deployed(api, tid, objects, machines)
    r = api.platform.put("/api/v1/platform/ml/settings", {"inference_enabled": False, "reason": "Incident review"})
    assert r.status_code == 200, r.text
    result = infer(api.clock.now, objects)
    assert result.switched_off and result.results == []
    [audit] = sql("SELECT * FROM inference_audit")
    assert audit.outcome == "SKIPPED" and audit.tenant_id is None and "switched off" in audit.reason
    assert sql("SELECT count(*) AS n FROM prediction")[0].n == 0
    status = owner.get("/api/v1/tenant/ml/status").json()
    assert (status["state"], status["label"]) == ("MODEL_OFF", "Model off")


def test_artifact_failures_are_audited_and_deterministic_rules_keep_running(api: Api) -> None:
    f = setup_finance(api, "Fail Co", "FAIL-1")
    t0 = api.clock.now
    complete_job(api, f, f.c.job_id, "500.0", "508.0", 9)
    body = {"event_type": "USAGE", "litres": "120", "machine_id": f.c.t.machine_id, "unit_price": "3000"}
    assert f.supervisor.post("/api/v1/tenant/fuel-events", body | {"occurred_at": t0.isoformat()}).status_code == 201
    fraud_policy(f.owner, fuel_max_litres_per_meter_hour="10")
    machines = [f.c.t.machine_id, *api.add_machines(f.owner, 7)]
    objects = InMemoryObjectStore()
    m = deployed(api, f.tid, objects, machines)
    key = sql("SELECT artifact_key FROM model_version WHERE id = :m", m=m)[0].artifact_key

    clear_bundle_cache()
    assert run_ml_cycle(InMemoryObjectStore(), api.clock.now) is not None  # object storage lost the artifact
    [missing] = sql("SELECT * FROM inference_audit WHERE outcome = 'ERROR'")
    assert "artifact unavailable" in missing.reason and str(missing.model_version_id) == m

    data, ctype, sha = objects.objects[key]
    objects.objects[key] = (data[:-1] + b"\x00", ctype, sha)  # swapped/corrupted artifact
    result = infer(api.clock.now, objects, f.tid)
    assert result.results[0].outcome.value == "ERROR" and "digest mismatch" in (result.results[0].reason or "")
    assert sql("SELECT count(*) AS n FROM prediction")[0].n == 0
    assert sql("SELECT count(*) AS n FROM inference_audit WHERE outcome = 'ERROR'")[0].n == 2

    assert sweep(api, f.tid).signals == 1  # deterministic detection is unaffected
    assert [s["rule_code"] for s in signals(f.owner)] == ["FUEL_ALLOWANCE_EXCEEDED"]


def test_disabled_model_is_never_scored(api: Api) -> None:
    tid, _, machines = fleet_tenant(api, "Off Co")
    objects = InMemoryObjectStore()
    m = deployed(api, tid, objects, machines)
    assert act(api.platform, m, "disable", "Withdrawn after review").status_code == 200
    assert infer(api.clock.now, objects).results == []
    assert sql("SELECT count(*) AS n FROM prediction")[0].n == 0
    assert sql("SELECT count(*) AS n FROM inference_audit")[0].n == 0


def _drift_model(api: Api, name: str, **factors: float) -> tuple[str, str]:
    """Train on the synthetic fleet, then add four later weeks whose values are the training rows (re-dated onto
    pseudo-machines), optionally scaled — so the recent window has exactly the training distribution or a shift."""
    tid, _, machines = fleet_tenant(api, name)
    objects = InMemoryObjectStore()
    end = last_week_end(api.clock.now) - timedelta(weeks=4)
    snaps = fleet_for(tid, machines, end)
    store(tid, snaps, api.clock.now)
    m = train(tid, api.clock.now - timedelta(weeks=4), LENIENT, store=objects)["model_id"]
    assert act(api.platform, m, "deploy-shadow", "Observe the model").status_code == 200
    train_end = datetime.fromisoformat(model(api.platform, m)["manifest"]["train_end"])
    train_rows = [s for s in snaps if s.as_of <= train_end]
    train_weeks = sorted({s.as_of for s in train_rows})
    copies = []
    for i, week in enumerate(train_weeks):
        for s in (x for x in train_rows if x.as_of == week):
            copies.append(
                dataclasses.replace(
                    s,
                    entity_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{s.entity_id}/{i // 4}")),
                    as_of=end + timedelta(weeks=1 + i % 4),
                    value=None if s.value is None else s.value * factors.get(s.feature_code, 1.0),
                )
            )
    store(tid, copies, api.clock.now)
    return tid, str(m)


def test_drift_is_stable_on_the_training_distribution_and_flags_a_shift(api: Api) -> None:
    _, stable = _drift_model(api, "Stable Co")
    _, shifted = _drift_model(api, "Shift Co", fuel_litres=3.0, litres_per_meter_hour=3.0, km_travelled=4.0)
    rows = {str(r.model_version_id): r for r in run_drift_cycle(get_sessionmaker(), api.clock.now)}
    assert rows[stable].level.value == "STABLE" and rows[shifted].level.value == "DRIFT"
    assert rows[stable].n_recent == rows[stable].n_train > 30
    drift = model(api.platform, shifted)["drift"]
    by_feature = {f["feature"]: f for f in drift["features"]}
    assert by_feature["fuel_litres"]["level"] == "DRIFT" and by_feature["fuel_litres"]["psi"] >= 0.25
    assert drift["level"] == "DRIFT" and "fuel_litres" in drift["summary"]
    assert model(api.platform, stable)["drift"]["level"] == "STABLE"
    [event] = sql("SELECT payload FROM outbox_event WHERE event_type = 'MlModelDriftDetected'")
    assert event.payload["model_version_id"] == shifted and "fuel_litres" in event.payload["features"]
    assert run_drift_cycle(get_sessionmaker(), api.clock.now) == []  # at most daily unless forced
    run_drift_cycle(get_sessionmaker(), api.clock.now, force=True)
    assert sql("SELECT count(*) AS n FROM outbox_event WHERE event_type = 'MlModelDriftDetected'")[0].n == 1
    history = api.platform.get(f"/api/v1/platform/ml/models/{shifted}/drift").json()
    assert history["total"] == 2
