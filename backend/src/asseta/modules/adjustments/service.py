"""Reading Ledger 6: list and detail with the filters the guideline asks for (type, status, person, date range,
machine, customer, reference) and the same rows as CSV."""

import csv
import io
import uuid
from datetime import date

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from asseta.core.errors import NotFound
from asseta.core.search import ilike_any
from asseta.modules.adjustments.dto import AdjustmentEntryDto
from asseta.modules.adjustments.models import AdjustmentEntryStatus, AdjustmentLedgerEntry, AdjustmentType
from asseta.modules.finance.common import local_bounds, tenant_settings
from asseta.modules.reports.render import safe_csv_cell


class AdjustmentLedger:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tid = session, tenant_id

    def query(
        self,
        q: str | None,
        adjustment_type: AdjustmentType | None,
        status: AdjustmentEntryStatus | None,
        person_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        machine_id: uuid.UUID | None,
        customer_id: uuid.UUID | None,
        staff_member_id: uuid.UUID | None,
        reference: str | None,
        original_id: uuid.UUID | None,
    ) -> Select[AdjustmentLedgerEntry]:
        e = AdjustmentLedgerEntry
        stmt = select(e).order_by(e.posted_at.desc(), e.id)
        for column, value in (
            (e.adjustment_type, adjustment_type),
            (e.status, status),
            (e.machine_id, machine_id),
            (e.customer_id, customer_id),
            (e.staff_member_id, staff_member_id),
            (e.original_id, original_id),
        ):
            if value is not None:
                stmt = stmt.where(column == value)
        if person_id is not None:
            stmt = stmt.where(or_(e.requested_by == person_id, e.approved_by == person_id))
        if date_from is not None or date_to is not None:
            tz = tenant_settings(self._s, self._tid).timezone
            if date_from is not None:
                stmt = stmt.where(e.posted_at >= local_bounds(tz, date_from, date_from)[0])
            if date_to is not None:
                stmt = stmt.where(e.posted_at < local_bounds(tz, date_to, date_to)[1])
        if (ref := ilike_any(reference, e.original_reference)) is not None:
            stmt = stmt.where(ref)
        if (match := ilike_any(q, e.entry_number, e.original_reference, e.reason, e.reason_label)) is not None:
            stmt = stmt.where(match)
        return stmt

    def entry(self, entry_id: uuid.UUID) -> AdjustmentLedgerEntry:
        row = self._s.get(AdjustmentLedgerEntry, entry_id)
        if row is None:
            raise NotFound("Adjustment not found", code="ADJUSTMENT_NOT_FOUND")
        return row


COLUMNS = [
    "posted_at",
    "adjustment_type",
    "status",
    "original_type",
    "original_reference",
    "unit",
    "original_value",
    "new_value",
    "amount",
    "currency",
    "resulting_balance",
    "reason_label",
    "reason",
    "customer_name",
    "machine_code",
    "staff_member_name",
    "requested_by_name",
    "requested_at",
    "approved_by_name",
    "approved_at",
    "decision_note",
]


NUMERIC_COLUMNS = frozenset({"original_value", "new_value", "amount", "resulting_balance"})


def entries_csv(rows: list[AdjustmentEntryDto]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for row in rows:
        data = row.model_dump(mode="json")
        writer.writerow(
            ["" if data.get(c) is None else safe_csv_cell(str(data[c]), c in NUMERIC_COLUMNS) for c in COLUMNS]
        )
    return out.getvalue()
