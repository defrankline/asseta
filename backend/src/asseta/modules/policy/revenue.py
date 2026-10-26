"""Revenue reconciliation policy (DEC-031 Phase 1: R1 revenue-hour basis, R2 daily machine sheet, R3 hours-to-money
reconciliation).

Every rule is tenant configuration with a safe platform default; the capability is OFF by default, which keeps
today's behaviour for every tenant: movement inside a job counts as customer work, billable hours and prepaid
drawdown are unchanged, and no reconciliation runs. Segregation of duties (the person who explains a revenue
difference never approves that explanation) is always enforced and is not a switch. Amounts are in the currency of
the jobs being reconciled (no implicit FX)."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Work-log types that may be declared non-revenue inside a job (WORK is revenue by definition; NOTE has no time).
NON_REVENUE_CANDIDATES = ("MOBILIZATION", "STANDBY", "DOWNTIME")


class ReconciliationPeriod(StrEnum):
    DAY = "DAY"  # tenant-local calendar day
    WEEK = "WEEK"  # tenant-local ISO week (Monday 00:00 -> next Monday 00:00)
    JOB = "JOB"  # one reconciliation per completed job (its whole engine window)


class ReconciliationBasis(StrEnum):
    # Money attributed = prepaid hours consumed x purchase effective rate + issued invoice lines of the jobs.
    INVOICED_OR_PREPAID = "INVOICED_OR_PREPAID"


class UnexplainedHoursTreatment(StrEnum):
    EXPECT_REVENUE = "EXPECT_REVENUE"  # unexplained engine hours outside jobs are expected to earn money
    EXCLUDE = "EXCLUDE"  # they are shown but not counted as expected revenue


class UnexplainedHoursRateSource(StrEnum):
    MACHINE_RATE_CARD = "MACHINE_RATE_CARD"  # the machine category's rate card in force (its currency)
    TENANT_RATE = "TENANT_RATE"  # `unexplained_hours_rate` in the tenant's base currency


class RevenueReconciliationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Master switch (capability REVENUE_RECONCILIATION). Off: every rule below reads as off (today's behaviour).
    enabled: bool = False
    # [R1] Work-log types that are not revenue when logged as non-billable time inside a job window.
    non_revenue_activity_types: list[str] = Field(default_factory=lambda: ["MOBILIZATION"], max_length=3)
    # [R1] On: that time is its own bucket in the engine-hour ledger and daily sheet (not customer work), and it is
    # deducted from an INVOICE job's billable hours through the existing billable-hours computation.
    deduct_non_revenue_from_working_hours: bool = False
    # [R1] On: that time is not drawn from the customer's prepaid hours (PREPAID_HOURS jobs).
    deduct_non_revenue_from_prepaid_hours: bool = False
    # [R1, owner 2026-10-26] Non-revenue time counts as non-revenue only once one person explained it and another
    # (holding `tenant.revenue.decide`) approved it; until then it counts as revenue. Off: deducted on logging.
    non_revenue_requires_approval: bool = True
    # [R3, owner 2026-10-26] Engine hours outside jobs not (yet) approved as non-customer activity are expected
    # revenue at the chosen rate; only an approved non-customer classification removes them.
    unexplained_hours_treatment: UnexplainedHoursTreatment = UnexplainedHoursTreatment.EXPECT_REVENUE
    unexplained_hours_rate_source: UnexplainedHoursRateSource = UnexplainedHoursRateSource.MACHINE_RATE_CARD
    unexplained_hours_rate: Decimal | None = Field(default=None, ge=0)  # TENANT_RATE only
    # [R3] Reconciliation period, tolerances and case threshold.
    period: ReconciliationPeriod = ReconciliationPeriod.WEEK
    tolerance_percent: Decimal = Field(default=Decimal(5), ge=0, le=Decimal(100))
    tolerance_amount: Decimal | None = Field(default=None, ge=0)  # null: the percentage alone decides
    case_threshold_amount: Decimal | None = Field(default=None, ge=0)  # |difference| above -> case; null = never
    basis: ReconciliationBasis = ReconciliationBasis.INVOICED_OR_PREPAID
    # Closed periods ending within this many days are re-examined on every sweep (late invoices clear differences).
    recheck_days: int = Field(default=28, ge=1, le=366)

    @model_validator(mode="after")
    def _known_types(self) -> "RevenueReconciliationPolicy":
        unknown = set(self.non_revenue_activity_types) - set(NON_REVENUE_CANDIDATES)
        if unknown:
            raise ValueError(f"non_revenue_activity_types must be among {list(NON_REVENUE_CANDIDATES)}")
        if len(set(self.non_revenue_activity_types)) != len(self.non_revenue_activity_types):
            raise ValueError("non_revenue_activity_types must not repeat")
        if self.unexplained_hours_rate_source is UnexplainedHoursRateSource.TENANT_RATE and (
            self.unexplained_hours_rate is None
        ):
            raise ValueError("unexplained_hours_rate is required when the rate source is TENANT_RATE")
        return self

    def in_force(self) -> "RevenueReconciliationPolicy":
        """The rules actually enforced: as configured when enabled; switched off as a whole otherwise."""
        if self.enabled:
            return self
        return self.model_copy(
            update={"deduct_non_revenue_from_working_hours": False, "deduct_non_revenue_from_prepaid_hours": False}
        )

    def billing_deductions(self, prepaid: bool) -> tuple[list[str], list[str]]:
        """Non-billable work-log types subtracted from a job's meter hours for billing, as (always, once approved):
        DOWNTIME and STANDBY always (today's billing), plus the declared non-revenue types when this policy (in force)
        deducts them for the job's billing mode — each entry only once approved when approval is required."""
        always = ["DOWNTIME", "STANDBY"]
        deduct = self.deduct_non_revenue_from_prepaid_hours if prepaid else self.deduct_non_revenue_from_working_hours
        extra = [t for t in self.non_revenue_activity_types if t not in always] if self.enabled and deduct else []
        return (always, extra) if self.non_revenue_requires_approval else (always + extra, [])

    def exceeds_tolerance(self, expected: Decimal, shortfall: Decimal) -> bool:
        """A shortfall is a difference to explain when it exceeds either tolerance (percent of expected, or the
        tenant amount when set)."""
        if shortfall <= 0:
            return False
        if self.tolerance_amount is not None and shortfall > self.tolerance_amount:
            return True
        return shortfall > expected * self.tolerance_percent / Decimal(100)


REVENUE_RECONCILIATION_SEED: dict[str, object] = {
    "enabled": False,  # off: today's behaviour until a tenant switches revenue reconciliation on
    "non_revenue_activity_types": ["MOBILIZATION"],
    "deduct_non_revenue_from_working_hours": False,
    "deduct_non_revenue_from_prepaid_hours": False,
    "non_revenue_requires_approval": True,
    "unexplained_hours_treatment": "EXPECT_REVENUE",
    "unexplained_hours_rate_source": "MACHINE_RATE_CARD",
    "unexplained_hours_rate": None,
    "period": "WEEK",
    "tolerance_percent": "5",
    "tolerance_amount": None,
    "case_threshold_amount": None,
    "basis": "INVOICED_OR_PREPAID",
    "recheck_days": 28,
}
