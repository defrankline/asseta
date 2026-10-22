"""Gate 6D: the synthetic shadow-mode demonstration — development only, clearly marked, never mixed into real training,
insights or tenant views."""

import uuid
from collections.abc import Iterator

import pytest

from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.ml.tracking import NullTracker
from asseta.modules.intelligence.ml_demo import DEMO_MODEL_NAME, DemoRefused, check_environment, run_demo
from asseta.tools import ml_cli
from tests.support.api import Api
from tests.support.idp import InMemoryObjectStore
from tests.support.ml import act, train
from tests.support.notify import sql


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ASSETA_ENVIRONMENT", "production")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("ASSETA_ENVIRONMENT")
    get_settings.cache_clear()


def test_demo_command_refuses_outside_development(production: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert ml_cli.main(["demo", "--tenant", str(uuid.uuid4())]) == 2
    assert "DEMO_REFUSED" in capsys.readouterr().err
    for env in ("production", "staging", "test"):
        with pytest.raises(DemoRefused):
            check_environment(env)
    assert sql("SELECT count(*) AS n FROM feature_snapshot")[0].n == 0


def test_demo_runs_shadow_inference_on_marked_synthetic_data_only(api: Api) -> None:
    t = api.onboard("Demo Co", price="1000")
    tid, owner = t["tenant"]["id"], t["owner"]
    api.add_machines(owner, 1)
    objects = InMemoryObjectStore()
    result = run_demo(
        get_sessionmaker(), uuid.UUID(tid), api.clock.now, objects, NullTracker(), environment="development"
    )
    assert result.readiness == "READY" and result.model_status == "DEPLOYED_SHADOW"
    [run] = result.inference
    assert (run["outcome"], run["input_rows"], run["predictions_written"]) == ("OK", 8, 8)
    sources = sql("SELECT source, count(*) AS n FROM feature_snapshot GROUP BY source")
    assert [(r.source, r.n) for r in sources] == [("synthetic", result.snapshots_written)]
    models = sql("SELECT name, manifest->>'snapshot_source' AS src, status FROM model_version")
    assert [(m.name, m.src, m.status) for m in models] == [(DEMO_MODEL_NAME, "synthetic", "DEPLOYED_SHADOW")]
    assert {r.decision_state for r in sql("SELECT decision_state FROM prediction")} == {"SHADOW"}

    # Never promoted, never mixed into real training, insights or tenant views.
    r = act(api.platform, str(result.model_version_id), "approve")
    assert r.status_code == 422 and r.json()["error"]["code"] == "SYNTHETIC_MODEL"
    assert train(tid, api.clock.now)["readiness"] == "INSUFFICIENT_DATA"
    status = owner.get("/api/v1/tenant/ml/status").json()
    assert status["state"] == "NOT_ENOUGH_HISTORY" and status["deployed"] is None
    assert owner.get("/api/v1/tenant/ml/predictions").json()["total"] == 0
    [fuel] = owner.get("/api/v1/tenant/insights").json()["fuel_efficiency"]
    assert fuel["status"] == "INSUFFICIENT_DATA"
