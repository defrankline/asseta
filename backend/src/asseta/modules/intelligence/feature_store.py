"""Feature catalog sync and weekly point-in-time snapshots in Postgres (ADR-007; no separate feature platform, BL-020).

* `sync_feature_definitions` mirrors the code registry (`asseta.ml.features.R1_FEATURES`) into `feature_definition`.
  A (code, version) already stored with different content is refused: changing a computation means a new version.
* `snapshot_tenant` computes every feature for every machine at each tenant-local week end in a range. Facts are
  loaded **per week end** in the tenant's own RLS scope with both clocks <= as_of (see `facts.py`), and rows are
  inserted append-only (`ON CONFLICT DO NOTHING`): a point that already exists is never rewritten. Week ends in the
  future are skipped — a snapshot for T must be computed at or after T.
* `load_snapshots` reads back one tenant's snapshots as `asseta.ml.features.FeatureSnapshot` for training.
"""

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.ml.features import (
    R1_FEATURES,
    FeatureDefinition,
    FeatureEntity,
    FeatureRegistry,
    FeatureSnapshot,
    compute_snapshots,
)
from asseta.modules.intelligence.facts import load_tenant_facts, week_ends
from asseta.modules.intelligence.ml_models import FeatureDefinitionRecord, FeatureEntityType, FeatureSnapshotRecord
from asseta.modules.tenancy.models import Tenant, TenantSettings

MAX_SNAPSHOT_WEEKS = 26  # bounded backfill per call (API and CLI); run again for older ranges
TRAINING_LOOKBACK_WEEKS = 52  # training reads at most this much recent history
_VALUE_PLACES = 9


class FeatureDefinitionDrift(BusinessRuleViolation):
    code = "FEATURE_DEFINITION_CHANGED"


@contextmanager
def scoped(session: Session, scope: DbScope, tenant_id: uuid.UUID | None) -> Iterator[None]:
    """Temporarily bind the transaction to another RLS scope, flushing pending writes before switching back.

    Lets one transaction read a tenant's facts in that tenant's own scope and then record governance rows in the
    platform/system scope, without ever widening what the tenant-scoped reads can see."""
    prev = session.execute(
        text(
            "SELECT current_setting('app.scope', true) AS s, current_setting('app.tenant_id', true) AS t,"
            " current_setting('app.actor_id', true) AS a"
        )
    ).one()
    session.flush()
    apply_scope(session, scope, tenant_id, None)
    yield
    session.flush()
    session.execute(
        text(
            "SELECT set_config('app.scope', :s, true), set_config('app.tenant_id', :t, true),"
            " set_config('app.actor_id', :a, true)"
        ),
        {"s": prev[0] or "", "t": prev[1] or "", "a": prev[2] or ""},
    )


def _definition_row(d: FeatureDefinition) -> dict[str, object]:
    return {
        "code": d.code,
        "version": d.version,
        "entity": FeatureEntityType(d.entity.value),
        "domain": d.domain.value,
        "window": d.window_label,
        "window_seconds": int(d.window.total_seconds()),
        "unit": d.unit,
        "description": d.description,
        "inputs": [i.value for i in d.inputs],
    }


def sync_feature_definitions(session: Session, registry: FeatureRegistry = R1_FEATURES) -> int:
    """Insert missing definitions (platform/system scope). Returns the number added."""
    existing = {(r.code, r.version): r for r in session.execute(select(FeatureDefinitionRecord)).scalars()}
    added = 0
    for d in registry.definitions:
        row = _definition_row(d)
        stored = existing.get((d.code, d.version))
        if stored is None:
            session.add(FeatureDefinitionRecord(id=uuid.uuid4(), **row))
            added += 1
            continue
        if any(getattr(stored, k) != v for k, v in row.items()):
            raise FeatureDefinitionDrift(
                f"Feature {d.key} changed without a version bump; bump its version in asseta.ml.features"
            )
    session.flush()
    return added


@dataclass(frozen=True)
class SnapshotRunResult:
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    week_ends: list[datetime]
    machines: int
    written: int
    skipped_existing: int
    skipped_future: int


def tenant_zone(session: Session, tenant_id: uuid.UUID) -> ZoneInfo:
    if session.get(Tenant, tenant_id) is None:
        raise NotFound("Tenant not found")
    tz = session.execute(
        select(TenantSettings.timezone).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()
    return ZoneInfo(tz or "UTC")


def store_snapshots(
    session: Session,
    tenant_id: uuid.UUID,
    snapshots: Sequence[FeatureSnapshot],
    now: datetime,
    run_id: uuid.UUID | None,
    registry: FeatureRegistry = R1_FEATURES,
) -> int:
    """Append snapshots (call in the tenant's scope); existing points are left untouched. Returns rows inserted."""
    rows = []
    for s in snapshots:
        if s.tenant_id != str(tenant_id):
            raise ValueError("snapshot belongs to another tenant")
        window = registry.get(s.feature_code).window
        rows.append(
            {
                "id": uuid.uuid4(),
                "tenant_id": tenant_id,
                "entity_type": FeatureEntityType(s.entity.value),
                "entity_id": uuid.UUID(s.entity_id),
                "feature_code": s.feature_code,
                "feature_version": s.feature_version,
                "as_of": s.as_of,
                "window_start": s.as_of - window,
                "window_end": s.as_of,
                "value": None if s.value is None else round(Decimal(repr(s.value)), _VALUE_PLACES),
                "data_cutoff": s.data_cutoff,
                "n_inputs": s.n_inputs,
                "computed_at": now,
                "run_id": run_id,
            }
        )
    inserted = 0
    for start in range(0, len(rows), 1000):
        stmt = pg_insert(FeatureSnapshotRecord).values(rows[start : start + 1000])
        result = session.execute(
            stmt.on_conflict_do_nothing(constraint="uq_feature_snapshot_point").returning(FeatureSnapshotRecord.id)
        )
        inserted += len(result.all())
    return inserted


def snapshot_tenant(
    session: Session,
    tenant_id: uuid.UUID,
    start: datetime,
    end: datetime,
    now: datetime,
    registry: FeatureRegistry = R1_FEATURES,
    max_weeks: int = MAX_SNAPSHOT_WEEKS,
) -> SnapshotRunResult:
    """Weekly snapshots for tenant-local week ends in [start, end] that are not in the future (bounded)."""
    with scoped(session, DbScope.TENANT, tenant_id):
        tz = tenant_zone(session, tenant_id)
        all_ends = week_ends(start, end, tz)
        due = [w for w in all_ends if w <= now]
        if len(due) > max_weeks:
            raise BusinessRuleViolation(
                f"{len(due)} week ends requested; at most {max_weeks} per run", code="SNAPSHOT_RANGE_TOO_LARGE"
            )
        run_id, machines, written, skipped = uuid.uuid4(), set(), 0, 0
        for as_of in due:
            facts = load_tenant_facts(session, tenant_id, as_of, as_of - registry.max_window, tz)
            snaps = [s for f in facts for s in compute_snapshots(registry, f, as_of)]
            machines |= {f.machine_id for f in facts}
            added = store_snapshots(session, tenant_id, snaps, now, run_id, registry)
            written, skipped = written + added, skipped + len(snaps) - added
    return SnapshotRunResult(run_id, tenant_id, due, len(machines), written, skipped, len(all_ends) - len(due))


def load_snapshots(
    session: Session,
    tenant_id: uuid.UUID,
    now: datetime,
    registry: FeatureRegistry = R1_FEATURES,
    lookback_weeks: int = TRAINING_LOOKBACK_WEEKS,
) -> list[FeatureSnapshot]:
    """One tenant's snapshots for the registry's exact feature versions (read in that tenant's scope)."""
    versions = {d.code: d.version for d in registry.definitions}
    with scoped(session, DbScope.TENANT, tenant_id):
        rows = session.execute(
            select(FeatureSnapshotRecord)
            .where(
                FeatureSnapshotRecord.tenant_id == tenant_id,
                FeatureSnapshotRecord.feature_code.in_(list(versions)),
                FeatureSnapshotRecord.as_of > now - timedelta(weeks=lookback_weeks),
                FeatureSnapshotRecord.as_of <= now,
            )
            .order_by(FeatureSnapshotRecord.as_of, FeatureSnapshotRecord.entity_id, FeatureSnapshotRecord.feature_code)
        ).scalars()
        out = [
            FeatureSnapshot(
                tenant_id=str(r.tenant_id),
                entity=FeatureEntity(r.entity_type.value),
                entity_id=str(r.entity_id),
                feature_code=r.feature_code,
                feature_version=r.feature_version,
                as_of=r.as_of,
                window=registry.get(r.feature_code).window_label,
                value=None if r.value is None else float(r.value),
                data_cutoff=r.data_cutoff,
                n_inputs=r.n_inputs,
            )
            for r in rows
            if versions[r.feature_code] == r.feature_version
        ]
    return out
