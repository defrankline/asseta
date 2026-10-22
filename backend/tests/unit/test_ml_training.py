import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from asseta.ml.datasets import ReadinessStatus, build_matrix
from asseta.ml.features import R1_FEATURES, FeatureSnapshot
from asseta.ml.synthetic import fleet_snapshots, generate_fleet
from asseta.ml.tracking import MlflowTracker, NullTracker, TrackingError, tracker_from_env
from asseta.ml.training import TrainingStatus, load_model_bundle, train_and_evaluate


@cache
def snapshots() -> tuple[FeatureSnapshot, ...]:
    return tuple(fleet_snapshots(generate_fleet(n_machines=8, weeks=14, seed=3)))


class RecordingTracker:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def log_run(self, **kw: Any) -> str | None:
        self.calls.append(kw)
        return "run-123"


class BrokenClient:
    """Stands in for an unreachable MLflow server: every client call fails to connect."""

    def __getattr__(self, name: str) -> Any:
        def fail(*_a: Any, **_k: Any) -> None:
            raise ConnectionError("mlflow down")

        return fail


def test_synthetic_fleet_is_deterministic_and_labelled() -> None:
    a, b = generate_fleet(n_machines=4, weeks=6, seed=1), generate_fleet(n_machines=4, weeks=6, seed=1)
    assert a == b
    assert generate_fleet(n_machines=4, weeks=6, seed=2) != a
    heavy = generate_fleet(n_machines=4, weeks=8, seed=1, anomaly_rate=1.0)
    assert heavy.anomalies and all(an.week_end in heavy.week_ends[3:] for an in heavy.anomalies)
    assert heavy.is_anomalous(heavy.anomalies[0].machine_id, heavy.anomalies[0].week_end)


def test_no_history_yields_insufficient_data_without_model() -> None:
    out = train_and_evaluate([], seed=0)
    assert out.status is TrainingStatus.INSUFFICIENT_DATA and not out.has_model and out.run_id is None
    small = fleet_snapshots(generate_fleet(n_machines=3, weeks=4, seed=0))
    tracker = RecordingTracker()
    out = train_and_evaluate(small, tracker=tracker, seed=0)
    assert out.status is TrainingStatus.INSUFFICIENT_DATA
    assert out.readiness.status is ReadinessStatus.INSUFFICIENT_DATA
    assert any("machines" in r for r in out.readiness.reasons)
    assert out.model_bytes is None and out.evaluation is None and tracker.calls == []


def test_train_and_evaluate_end_to_end_with_null_tracker_is_deterministic() -> None:
    a = train_and_evaluate(snapshots(), tracker=NullTracker(), seed=5)
    b = train_and_evaluate(snapshots(), tracker=NullTracker(), seed=5)
    assert a.status is TrainingStatus.TRAINED and a.has_model and a.run_id is None and a.tracking_error is None
    assert a.manifest is not None and a.evaluation is not None and a.model_metrics is not None
    assert b.manifest is not None and b.evaluation is not None
    assert a.evaluation.metrics == b.evaluation.metrics and a.evaluation.passed == b.evaluation.passed
    assert a.manifest.content_hash == b.manifest.content_hash
    assert a.manifest.splits["test"].rows > 0 and a.model_metrics.calibrated
    assert a.evaluation.reasons  # pass or fail, always explained
    bundle = load_model_bundle(a.model_bytes or b"", a.model_sha256 or "")
    base_rows, cand_rows = bundle.score(build_matrix(snapshots(), R1_FEATURES))
    assert len(base_rows) == len(cand_rows) == 8 * 14
    assert all(r.calibrated for r in cand_rows if r.raw_score is not None)
    with pytest.raises(ValueError, match="digest"):
        load_model_bundle(a.model_bytes or b"", "0" * 64)


def test_tracker_receives_manifest_and_model_artifacts() -> None:
    tracker = RecordingTracker()
    out = train_and_evaluate(snapshots(), tracker=tracker, seed=1)
    assert out.run_id == "run-123"
    call = tracker.calls[0]
    manifest = json.loads(call["artifacts"]["manifest.json"])
    assert manifest["feature_set_hash"] == out.feature_set_hash
    assert call["artifacts"]["model.pkl"] == out.model_bytes
    assert call["tags"]["asseta.tenant_id"] == "tenant-demo" and "passed" in call["metrics"]


def test_unreachable_mlflow_still_produces_local_outcome() -> None:
    tracker = MlflowTracker("http://mlflow.invalid", client=BrokenClient())  # type: ignore[arg-type]
    with pytest.raises(TrackingError):
        tracker.log_run(experiment="x", run_name="r", params={}, metrics={}, artifacts={}, tags={})
    out = train_and_evaluate(snapshots(), tracker=tracker, seed=1)
    assert out.status is TrainingStatus.TRAINED and out.has_model
    assert out.run_id is None and out.tracking_error and "ConnectionError" in out.tracking_error


def test_tracker_from_env() -> None:
    env: Mapping[str, str] = {}
    assert isinstance(tracker_from_env(env), NullTracker)
    assert isinstance(tracker_from_env({"ASSETA_MLFLOW_TRACKING_URI": "  "}), NullTracker)


def test_mlflow_adapter_against_local_file_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")  # file store is maintenance-only in MLflow 3; fine for tests
    monkeypatch.setenv("MLFLOW_DISABLE_AGENT_HINT", "1")
    uri = (tmp_path / "mlruns").as_uri()
    tracker = tracker_from_env({"ASSETA_MLFLOW_TRACKING_URI": uri})
    assert isinstance(tracker, MlflowTracker)
    run_id = tracker.log_run(
        experiment="asseta-test",
        run_name="unit",
        params={"seed": 1, "algorithm": "isolation_forest"},
        metrics={"recall": 0.5, "nan_is_skipped": float("nan")},
        artifacts={"manifest.json": b'{"a": 1}', "model.pkl": b"\x00\x01"},
        tags={"asseta.tenant_id": "t1"},
    )
    assert run_id
    from mlflow.tracking import MlflowClient

    run = MlflowClient(tracking_uri=uri).get_run(run_id)
    assert run.info.status == "FINISHED"
    assert run.data.metrics == {"recall": 0.5} and run.data.params["seed"] == "1"
    assert {a.path for a in MlflowClient(tracking_uri=uri).list_artifacts(run_id)} == {"manifest.json", "model.pkl"}
