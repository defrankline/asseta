"""Machine responses with their go-live setup state (billing enrollment, primary tracker), computed in batch."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.orm import Session

from asseta.modules.fleet.dto import MachineDto, MachineMissing, MachineRecordDto
from asseta.modules.fleet.models import Machine
from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment
from asseta.modules.tracker.models import Tracker, TrackerAssignment


def _primary_now(now: datetime) -> ColumnElement[bool]:
    return and_(
        TrackerAssignment.is_primary.is_(True),
        TrackerAssignment.effective_from <= now,
        or_(TrackerAssignment.effective_to.is_(None), TrackerAssignment.effective_to > now),
    )


def _enrolled_now(now: datetime) -> ColumnElement[bool]:
    today = now.date()
    return and_(
        SubscriptionAssetEnrollment.effective_from <= today,
        or_(SubscriptionAssetEnrollment.effective_to.is_(None), SubscriptionAssetEnrollment.effective_to > today),
    )


def missing_clause(missing: MachineMissing, now: datetime) -> ColumnElement[bool]:
    """Machines without a current primary tracker / without an enrollment covering today (same facts as the
    go-live checklist)."""
    if missing is MachineMissing.TRACKER:
        return ~exists().where(TrackerAssignment.machine_id == Machine.id, _primary_now(now))
    return ~exists().where(SubscriptionAssetEnrollment.machine_id == Machine.id, _enrolled_now(now))


def machine_dtos(session: Session, machines: Sequence[Machine | MachineRecordDto], now: datetime) -> list[MachineDto]:
    """Two queries for the whole batch, whatever its size."""
    records = [m if isinstance(m, MachineRecordDto) else MachineRecordDto.model_validate(m) for m in machines]
    ids = [r.id for r in records]
    trackers: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    enrolled: set[uuid.UUID] = set()
    if ids:
        for machine_id, tracker_id, label in session.execute(
            select(TrackerAssignment.machine_id, Tracker.id, Tracker.label)
            .join(Tracker, Tracker.id == TrackerAssignment.tracker_id)
            .where(TrackerAssignment.machine_id.in_(ids), _primary_now(now))
        ):
            trackers[machine_id] = (tracker_id, label)
        enrolled = set(
            session.execute(
                select(SubscriptionAssetEnrollment.machine_id).where(
                    SubscriptionAssetEnrollment.machine_id.in_(ids), _enrolled_now(now)
                )
            ).scalars()
        )
    out: list[MachineDto] = []
    for r in records:
        tracker = trackers.get(r.id)
        extra: dict[str, Any] = {
            "billing_enrolled": r.id in enrolled,
            "primary_tracker_id": tracker[0] if tracker else None,
            "primary_tracker_label": tracker[1] if tracker else None,
        }
        out.append(MachineDto(**r.model_dump(include=set(MachineRecordDto.model_fields)), **extra))
    return out


def machine_dto(session: Session, machine: Machine | MachineRecordDto, now: datetime) -> MachineDto:
    return machine_dtos(session, [machine], now)[0]
