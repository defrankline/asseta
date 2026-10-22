"""Shadow-mode demonstration on synthetic data (prompt.md R1-J "ML shadow-mode demonstration"), development only.

`run_demo` loads the deterministic synthetic fleet (`asseta.ml.synthetic`) as machine-week feature snapshots marked
`source = 'synthetic'` for pseudo-machines of one tenant, trains the demo model on those snapshots only, deploys it
in SHADOW mode and runs inference, so the platform can show what shadow mode records without real history.

Safety rails:
* refused unless the environment is `development` or `local` (`ASSETA_ENVIRONMENT`);
* synthetic snapshots are excluded from real training, insights and inference of real models (all read `observed`);
* the demo model has its own name (`machine-week-anomaly-demo`), so it never replaces or retires a tenant's real
  deployment, and a model trained on synthetic data can never be approved or activated (`SYNTHETIC_MODEL`);
* pseudo-machine ids are UUIDv5 of the tenant + synthetic machine code, so they never collide with real machines,
  and shadow predictions are never linked to cases or shown to tenants.
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from asseta.core.audit import AuditActor
from asseta.core.db import DbScope, apply_scope
from asseta.core.storage import ObjectReader, ObjectStore
from asseta.ml.evaluation import PromotionCriteria
from asseta.ml.synthetic import fleet_snapshots, generate_fleet
from asseta.ml.tracking import ExperimentTracker
from asseta.modules.intelligence.facts import week_ends
from asseta.modules.intelligence.feature_store import store_snapshots, sync_feature_definitions, tenant_zone
from asseta.modules.intelligence.inference import run_inference_cycle
from asseta.modules.intelligence.ml_lifecycle import MlGovernanceService
from asseta.modules.intelligence.ml_models import SOURCE_SYNTHETIC, ModelAction
from asseta.modules.intelligence.ml_training import train_tenant

DEMO_ENVIRONMENTS = frozenset({"development", "local"})
DEMO_MODEL_NAME = "machine-week-anomaly-demo"
DEMO_ACTOR = AuditActor(user_id=None, roles=["system"], source="ml-demo")
DEMO_REASON = "Synthetic shadow-mode demonstration (asseta-ml demo); never shown to the tenant."


class DemoRefused(RuntimeError):
    """The demo only runs in development/local environments."""


class DemoStore(ObjectStore, ObjectReader, Protocol):
    """What the demo needs from object storage: write the trained bundle, read it back for inference."""


@dataclass(frozen=True)
class DemoResult:
    tenant_id: uuid.UUID
    snapshots_written: int
    readiness: str
    reasons: list[str]
    model_version_id: uuid.UUID | None
    model_status: str | None
    inference: list[dict[str, Any]]


def check_environment(environment: str) -> None:
    if environment.strip().lower() not in DEMO_ENVIRONMENTS:
        raise DemoRefused(
            f"asseta-ml demo loads synthetic data and only runs when ASSETA_ENVIRONMENT is development or local "
            f"(current: {environment!r})."
        )


def demo_machine_id(tenant_id: uuid.UUID, code: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"asseta-demo/{tenant_id}/{code}"))


def run_demo(
    sm: sessionmaker[Session],
    tenant_id: uuid.UUID,
    now: datetime,
    store: DemoStore,
    tracker: ExperimentTracker,
    *,
    environment: str,
    machines: int = 8,
    weeks: int = 14,
    seed: int = 3,
    promotion: PromotionCriteria | None = None,
) -> DemoResult:
    check_environment(environment)
    with sm.begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        tz = tenant_zone(s, tenant_id)
    last = week_ends(now - timedelta(days=8), now, tz)[-1]
    fleet = generate_fleet(str(tenant_id), machines, weeks, seed, start=last - timedelta(weeks=weeks))
    snaps = [dataclasses.replace(s, entity_id=demo_machine_id(tenant_id, s.entity_id)) for s in fleet_snapshots(fleet)]
    with sm.begin() as s:
        apply_scope(s, DbScope.TENANT, tenant_id, None)
        written = store_snapshots(s, tenant_id, snaps, now, uuid.uuid4(), source=SOURCE_SYNTHETIC)
    with sm.begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        sync_feature_definitions(s)
        trained = train_tenant(
            s,
            tenant_id,
            now,
            store,
            tracker,
            DEMO_ACTOR,
            seed=seed,
            name=DEMO_MODEL_NAME,
            promotion=promotion,
            source=SOURCE_SYNTHETIC,
        )
        model = trained.model
        if model is not None:
            MlGovernanceService(s, DEMO_ACTOR, now).act(model.id, ModelAction.DEPLOY_SHADOW, DEMO_REASON, None)
        readiness, reasons = trained.readiness.status.value, list(trained.readiness.reasons)
        model_id, status = (model.id, model.status.value) if model else (None, None)
    results = run_inference_cycle(sm, now, store, tenant_ids=[tenant_id]).results if model_id else []
    return DemoResult(
        tenant_id=tenant_id,
        snapshots_written=written,
        readiness=readiness,
        reasons=reasons,
        model_version_id=model_id,
        model_status=status,
        inference=[
            {
                "model_version_id": str(r.model_version_id),
                "outcome": r.outcome.value,
                "input_rows": r.input_rows,
                "predictions_written": r.written,
                "reason": r.reason,
            }
            for r in results
            if r.model_version_id == model_id
        ],
    )
