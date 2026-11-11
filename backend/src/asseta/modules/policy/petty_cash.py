"""Petty cash funds policy (DEC-033, capability PETTY_CASH). Tenant configuration with safe platform defaults: the
whole module is OFF until a tenant switches it on; advances (phase 3) are off on their own switch. Amounts are in the
tenant's base currency (an expense in another currency always needs a human approval anyway)."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PettyCashPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Master switch (capability PETTY_CASH). Off: menus hidden, endpoints and sync operations refused.
    enabled: bool = False
    # An expense paid from a fund above this amount always needs a human approval. Null = no maximum.
    max_expense_amount: Decimal | None = Field(default=None, gt=0)
    # An offline expense above what the fund had available is accepted, kept PENDING_APPROVAL and flagged OVERSPEND
    # (the phone may be stale). Off: it is held as a sync conflict for review instead.
    overspend_allowed_offline: bool = True
    # A count of every active fund is due every this many days (tenant-local). Null = no count schedule.
    count_every_days: int | None = Field(default=None, ge=1, le=365)
    # A count by the holder alone is marked self-count when a witness is required.
    count_witness_required: bool = False
    # Evidence (photo of the slip or the cash) on returns and on issued fundings / top-ups.
    return_evidence_required: bool = False
    funding_evidence_required: bool = False
    # Phase 3: cash advances from a fund, cleared with expenses and the change within N days.
    advances_enabled: bool = False
    advance_clear_within_days: int = Field(default=7, ge=1, le=90)


PETTY_CASH_SEED: dict[str, object] = {
    "enabled": False,
    "max_expense_amount": None,
    "overspend_allowed_offline": True,
    "count_every_days": None,
    "count_witness_required": False,
    "return_evidence_required": False,
    "funding_evidence_required": False,
    "advances_enabled": False,
    "advance_clear_within_days": 7,
}
