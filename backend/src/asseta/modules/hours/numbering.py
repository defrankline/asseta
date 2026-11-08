"""Gap-free per-tenant counters (hours_sequence): `next_number` for a tenant, series and year (row lock until the
transaction ends). Separate from the hours service so other modules can number their records without importing it."""

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.modules.hours.models import HoursSequence


def next_number(session: Session, tenant_id: uuid.UUID, series: str, year: int) -> int:
    """Gap-free per tenant/series/year: the counter row is locked by the upsert until the transaction ends."""
    value: int = session.execute(
        pg_insert(HoursSequence)
        .values(tenant_id=tenant_id, series=series, year=year, last_number=1)
        .on_conflict_do_update(
            index_elements=["tenant_id", "series", "year"], set_={"last_number": HoursSequence.last_number + 1}
        )
        .returning(HoursSequence.last_number)
    ).scalar_one()
    return value
