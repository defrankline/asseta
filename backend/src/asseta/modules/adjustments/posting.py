"""Posts one decided adjustment to Ledger 6. Called from every approval flow that changes an established balance,
inside the flow's own transaction: the entry exists exactly when the change does (idempotent on source + outcome)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentLedgerEntry,
    AdjustmentType,
    AdjustmentUnit,
)
from asseta.modules.finance.references import LEDGER_ENTRY, reference


@dataclass(frozen=True)
class AdjustmentPosting:
    adjustment_type: AdjustmentType
    status: AdjustmentEntryStatus
    original_type: str
    original_id: uuid.UUID
    original_reference: str | None
    source_type: str
    source_id: uuid.UUID
    unit: AdjustmentUnit
    original_value: Decimal | None = None
    new_value: Decimal | None = None
    amount: Decimal | None = None
    currency: str | None = None
    resulting_balance: Decimal | None = None
    reason_id: uuid.UUID | None = None
    reason_label: str | None = None
    reason: str | None = None
    evidence_attachment_ids: list[uuid.UUID] = field(default_factory=list)
    customer_id: uuid.UUID | None = None
    machine_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID | None = None
    requested_by: uuid.UUID | None = None
    requested_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    decision_note: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    policy_version: str | None = None


def post_adjustment(session: Session, tenant_id: uuid.UUID, now: datetime, p: AdjustmentPosting) -> None:
    """Append the entry. A retry of the same decided record (idempotent) leaves the existing entry untouched."""
    if (
        session.execute(
            select(AdjustmentLedgerEntry.id)
            .where(
                AdjustmentLedgerEntry.source_type == p.source_type,
                AdjustmentLedgerEntry.source_id == p.source_id,
                AdjustmentLedgerEntry.status == p.status,
            )
            .limit(1)
        ).first()
        is not None
    ):
        return  # no number is drawn for a retry
    session.execute(
        insert(AdjustmentLedgerEntry)
        .values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            adjustment_type=p.adjustment_type,
            status=p.status,
            original_type=p.original_type,
            original_id=p.original_id,
            original_reference=p.original_reference,
            source_type=p.source_type,
            source_id=p.source_id,
            unit=p.unit,
            original_value=p.original_value,
            new_value=p.new_value,
            amount=p.amount,
            currency=p.currency,
            resulting_balance=p.resulting_balance,
            reason_id=p.reason_id,
            reason_label=p.reason_label,
            reason=p.reason,
            evidence_attachment_ids=p.evidence_attachment_ids,
            customer_id=p.customer_id,
            machine_id=p.machine_id,
            staff_member_id=p.staff_member_id,
            requested_by=p.requested_by,
            requested_at=p.requested_at,
            approved_by=p.approved_by,
            approved_at=p.approved_at,
            decision_note=p.decision_note,
            details=p.details,
            policy_version=p.policy_version[:80] if p.policy_version else None,
            posted_at=now,
            created_at=now,
            entry_number=reference(session, tenant_id, LEDGER_ENTRY, now),
        )
        .on_conflict_do_nothing(constraint="uq_adjustment_entry_source")
    )
