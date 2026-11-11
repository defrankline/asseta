"""Result types of a balance verification: which check, the recomputed (ledger) figure and the stored one."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from asseta.core.db import DbScope
from asseta.modules.identity.principal import RequestContext

ZERO = Decimal(0)
TOLERANCE = Decimal("0.01")
NEW_ALLOCATION_LAG_DAYS = 3  # a recent day with no allocation yet is the sweep still catching up, not a mismatch


class CheckKind(StrEnum):
    CUSTOMER_HOURS_LOT = "CUSTOMER_HOURS_LOT"
    ENGINE_HOURS = "ENGINE_HOURS"
    DAILY_REPORT = "DAILY_REPORT"
    CASH_CUSTODY = "CASH_CUSTODY"
    CUSTOMER_RECEIVABLE = "CUSTOMER_RECEIVABLE"
    INVOICE_TOTAL = "INVOICE_TOTAL"
    PETTY_CASH_FUND = "PETTY_CASH_FUND"  # DEC-033: fund balances vs counts and adjustment snapshots


@dataclass(frozen=True)
class Finding:
    check: CheckKind
    subject_type: str
    subject_id: str
    label: str
    ledger_value: Decimal
    stored_value: Decimal
    currency: str | None
    source: str  # which stored figure disagrees
    details: dict[str, Any]

    @property
    def difference(self) -> Decimal:
        return self.stored_value - self.ledger_value

    def to_json(self) -> dict[str, Any]:
        return {
            "check": self.check.value,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "label": self.label,
            "currency": self.currency,
            "ledger_value": str(self.ledger_value),
            "stored_value": str(self.stored_value),
            "difference": str(self.difference),
            "source": self.source,
            "details": self.details,
        }


@dataclass
class Report:
    tenant_id: uuid.UUID
    as_of: datetime
    checked: dict[CheckKind, int] = field(default_factory=lambda: defaultdict(int))
    findings: list[Finding] = field(default_factory=list)

    @property
    def checked_total(self) -> int:
        return sum(self.checked.values())

    @property
    def mismatches(self) -> dict[CheckKind, int]:
        out: dict[CheckKind, int] = defaultdict(int)
        for f in self.findings:
            out[f.check] += 1
        return out

    def summary(self) -> list[dict[str, Any]]:
        by = self.mismatches
        return [{"check": c.value, "checked": self.checked.get(c, 0), "mismatches": by.get(c, 0)} for c in CheckKind]


def differs(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) >= TOLERANCE


def system_ctx(tenant_id: uuid.UUID) -> RequestContext:
    return RequestContext(uuid.UUID(int=0), "balance-verification", DbScope.TENANT, tenant_id, frozenset(), frozenset())
