"""Generated, human-readable references (DEC-032, guideline 6.4): the same counter pattern as HP-/HINV- numbers, one
series per tenant and tenant-local year. COL-2026-00001 cash collections, PAY- other customer payments, RMT- company
remittances, CTR- field cash transfers, HTR- hours transfers, RET- retentions, CADJ- custody adjustments, ADJ-
Ledger 6 entries, ARQ- adjustment requests. These are the system's references: a remittance's `reference` stays the
bank or mobile-money transaction reference, which only the outside system can issue."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.models import HirePaymentMethod
from asseta.modules.hours.numbering import next_number

COLLECTION = "COL"
PAYMENT = "PAY"
REMITTANCE = "RMT"
CASH_TRANSFER = "CTR"
HOURS_TRANSFER = "HTR"
RETENTION = "RET"
CUSTODY_ADJUSTMENT = "CADJ"
LEDGER_ENTRY = "ADJ"
ADJUSTMENT_REQUEST = "ARQ"


def reference(session: Session, tenant_id: uuid.UUID, series: str, at: datetime) -> str:
    year = at.astimezone(ZoneInfo(tenant_settings(session, tenant_id).timezone)).year
    return f"{series}-{year}-{next_number(session, tenant_id, series, year):05d}"


def payment_series(method: HirePaymentMethod) -> str:
    return COLLECTION if method is HirePaymentMethod.CASH else PAYMENT
