"""The guideline section 8 dashboard groups. Every figure names the console route of the transactions behind it
(`route`, filters included). Flows (purchased, collected, operating hours...) follow the requested period. Balances
and open queues (remaining, held, outstanding, awaiting, pending, unresolved) are always the position now: an item
does not stop being outstanding because it is older than the period."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from asseta.modules.platform_billing.dto import Money


class HoursFigureDto(BaseModel):
    hours: Decimal
    count: int
    route: str


class CountFigureDto(BaseModel):
    count: int
    route: str


class MoneyLineDto(BaseModel):
    currency: str
    count: int
    amount: Money


class MoneyFigureDto(BaseModel):
    """Per currency, never mixed. `count` is the number of records across currencies."""

    lines: list[MoneyLineDto]
    count: int
    route: str


# --- customer hours ----------------------------------------------------------------------------------------------
class CustomerRemainingDto(BaseModel):
    customer_id: uuid.UUID
    customer_name: str | None = None
    remaining: Decimal
    activated: Decimal
    consumed: Decimal
    route: str


class PurchaseQueueItemDto(BaseModel):
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    customer_id: uuid.UUID
    customer_name: str | None = None
    hours_awaiting: Decimal
    amount_open: Money
    currency: str
    created_at: datetime
    route: str


class PurchaseQueueDto(BaseModel):
    count: int
    hours: Decimal
    amounts: list[MoneyLineDto]
    route: str
    items: list[PurchaseQueueItemDto]


class CustomerHoursSectionDto(BaseModel):
    purchased: HoursFigureDto
    purchased_value: MoneyFigureDto
    activated: HoursFigureDto
    consumed: HoursFigureDto
    remaining: HoursFigureDto
    remaining_by_customer: list[CustomerRemainingDto]
    remaining_customers_total: int
    unpaid_purchases: PurchaseQueueDto
    unconfirmed_purchases: PurchaseQueueDto
    awaiting_activation: PurchaseQueueDto


# --- excavator operations ----------------------------------------------------------------------------------------
class ExcavatorHoursDto(BaseModel):
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    operating_hours: Decimal
    customer_hours: Decimal
    authorized_hours: Decimal
    unexplained_hours: Decimal
    route: str


class TypeCountDto(BaseModel):
    type: str
    count: int
    route: str


class DiscrepanciesFigureDto(BaseModel):
    count: int
    by_type: list[TypeCountDto]
    route: str


class ExcavatorOperationsSectionDto(BaseModel):
    operating_hours: HoursFigureDto
    customer_hours: HoursFigureDto
    authorized_non_customer_hours: HoursFigureDto
    unexplained_hours: HoursFigureDto
    by_excavator: list[ExcavatorHoursDto]
    meter_discrepancies: DiscrepanciesFigureDto
    pending_reports: CountFigureDto
    returned_reports: CountFigureDto


# --- cash --------------------------------------------------------------------------------------------------------
class EmployeeCashDto(BaseModel):
    staff_member_id: uuid.UUID
    staff_member_name: str | None = None
    currency: str
    outstanding: Money
    in_transit_out: Money
    claimed_unverified_handovers: Money
    pending_floats: Money
    approved_retention: Money
    route: str


class CashSectionDto(BaseModel):
    collected: MoneyFigureDto
    held_by_employee: list[EmployeeCashDto]
    transferred: MoneyFigureDto
    in_transit: MoneyFigureDto
    declared_for_remittance: MoneyFigureDto
    confirmed_by_company: MoneyFigureDto
    outstanding: MoneyFigureDto
    unconfirmed_remittances: MoneyFigureDto
    disputed_remittances: MoneyFigureDto
    disputed_transfers: MoneyFigureDto


# --- exceptions --------------------------------------------------------------------------------------------------
class KindCountDto(BaseModel):
    kind: str
    count: int
    oldest_at: datetime | None
    route: str


class PendingItemDto(BaseModel):
    """One record waiting for a decision (the pending list and the dashboard's oldest items)."""

    kind: str
    record_type: str
    id: uuid.UUID
    reference: str | None
    status: str
    requested_by: uuid.UUID | None
    requested_by_name: str | None = None
    requested_at: datetime
    amount: Decimal | None
    unit: str | None
    currency: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    machine_id: uuid.UUID | None
    machine_code: str | None = None
    machine_name: str | None = None
    staff_member_id: uuid.UUID | None
    staff_member_name: str | None = None
    route: str | None


class PendingAdjustmentsDto(BaseModel):
    """Every adjustment proposed and not yet decided, across all flows."""

    total: int
    by_kind: list[KindCountDto]
    oldest: list[PendingItemDto]
    route: str


class AttemptsFigureDto(BaseModel):
    since: datetime
    permission_denied: int
    segregation_of_duties: int
    route: str


class OutstandingApprovalsDto(BaseModel):
    total: int
    by_kind: list[KindCountDto]


class OverdueReportsDto(BaseModel):
    missing_daily_reports: CountFigureDto
    remittances_overdue_today: CountFigureDto
    total: int


class VarianceSourceDto(BaseModel):
    source: str
    unit: str
    count: int
    amounts: list[MoneyLineDto]
    route: str


class UnresolvedVariancesDto(BaseModel):
    total: int
    by_source: list[VarianceSourceDto]


class ChangeoverJobDto(BaseModel):
    job_id: uuid.UUID
    job_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    customer_id: uuid.UUID
    customer_name: str | None = None
    changed_over_at: datetime
    days_waiting: int
    route: str


class ChangeoverJobsDto(BaseModel):
    """Follow-on jobs still unapproved: hours after the changeover are unbilled until they are."""

    count: int
    oldest_days: int | None
    items: list[ChangeoverJobDto]


class ExceptionsSectionDto(BaseModel):
    unexplained_engine_hours: HoursFigureDto
    shortages: MoneyFigureDto
    overages: MoneyFigureDto
    shortages_opened_in_period: MoneyFigureDto
    overages_opened_in_period: MoneyFigureDto
    pending_adjustments: PendingAdjustmentsDto
    unauthorized_attempts: AttemptsFigureDto
    unconfirmed_payments: MoneyFigureDto
    outstanding_approvals: OutstandingApprovalsDto
    overdue_reports: OverdueReportsDto
    unresolved_variances: UnresolvedVariancesDto
    changeover_jobs_awaiting_approval: ChangeoverJobsDto


class PeriodDto(BaseModel):
    date_from: date | None
    date_to: date | None
