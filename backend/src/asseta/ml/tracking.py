"""Experiment tracking seam: MLflow when configured, a no-op otherwise.

MLflow is the run/artifact store (ADR-007); the application's own `model_version` tables remain the governance
record. Training must never depend on MLflow being reachable: `NullTracker` lets a run complete locally, and
`MlflowTracker` raises `TrackingError` on failure so the caller can record "trained, not tracked" and decide.
`mlflow` is imported lazily so API/worker processes that never train do not pay its import cost.
"""

from __future__ import annotations

import contextlib
import math
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from mlflow.tracking import MlflowClient

TRACKING_URI_ENV = "ASSETA_MLFLOW_TRACKING_URI"
DEFAULT_EXPERIMENT = "asseta-anomaly"
_MAX_PARAM_LEN = 500  # MLflow rejects longer param values


class TrackingError(RuntimeError):
    """MLflow was configured but the run could not be recorded."""


class ExperimentTracker(Protocol):
    def log_run(
        self,
        *,
        experiment: str,
        run_name: str,
        params: Mapping[str, str | int | float],
        metrics: Mapping[str, float],
        artifacts: Mapping[str, bytes],
        tags: Mapping[str, str],
    ) -> str | None:
        """Record one run; returns its id, or None when nothing is tracked."""
        ...


class NullTracker:
    """Used when no tracking URI is configured; training still produces a complete local outcome."""

    def log_run(
        self,
        *,
        experiment: str,
        run_name: str,
        params: Mapping[str, str | int | float],
        metrics: Mapping[str, float],
        artifacts: Mapping[str, bytes],
        tags: Mapping[str, str],
    ) -> str | None:
        return None


class MlflowTracker:
    def __init__(self, tracking_uri: str, client: MlflowClient | None = None) -> None:
        if client is None:
            from mlflow.tracking import MlflowClient

            client = MlflowClient(tracking_uri=tracking_uri)
        self.tracking_uri = tracking_uri
        self._client = client

    def _experiment_id(self, name: str) -> str:
        existing = self._client.get_experiment_by_name(name)
        return existing.experiment_id if existing is not None else self._client.create_experiment(name)

    def log_run(
        self,
        *,
        experiment: str,
        run_name: str,
        params: Mapping[str, str | int | float],
        metrics: Mapping[str, float],
        artifacts: Mapping[str, bytes],
        tags: Mapping[str, str],
    ) -> str | None:
        from mlflow.entities import Metric, Param, RunTag

        run_id: str | None = None
        try:
            run = self._client.create_run(self._experiment_id(experiment), tags=dict(tags), run_name=run_name)
            run_id = run.info.run_id
            ts = run.info.start_time or 0
            self._client.log_batch(
                run_id,
                metrics=[Metric(k, float(v), ts, 0) for k, v in sorted(metrics.items()) if math.isfinite(v)],
                params=[Param(k, str(v)[:_MAX_PARAM_LEN]) for k, v in sorted(params.items())],
                tags=[RunTag(k, v) for k, v in sorted(tags.items())],
            )
            with tempfile.TemporaryDirectory(prefix="asseta-mlflow-") as tmp:
                for name, data in sorted(artifacts.items()):
                    path = Path(tmp) / Path(name).name
                    path.write_bytes(data)
                    self._client.log_artifact(run_id, str(path))
            self._client.set_terminated(run_id, "FINISHED")
            return run_id
        except Exception as exc:
            if run_id is not None:
                with contextlib.suppress(Exception):  # best effort; the original error is what matters
                    self._client.set_terminated(run_id, "FAILED")
            raise TrackingError(f"MLflow run could not be recorded: {type(exc).__name__}") from exc


def tracker_from_env(env: Mapping[str, str] | None = None) -> ExperimentTracker:
    """`ASSETA_MLFLOW_TRACKING_URI` set -> MlflowTracker; unset/blank -> NullTracker."""
    uri = (os.environ if env is None else env).get(TRACKING_URI_ENV, "").strip()
    return MlflowTracker(uri) if uri else NullTracker()
