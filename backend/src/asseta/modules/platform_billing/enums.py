from enum import StrEnum


class Cadence(StrEnum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class AgreementStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    TERMINATED = "TERMINATED"


class SubscriptionStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_ACTIVATION = "PENDING_ACTIVATION"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


ALLOWED_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    SubscriptionStatus.DRAFT: frozenset({SubscriptionStatus.PENDING_ACTIVATION, SubscriptionStatus.CANCELLED}),
    SubscriptionStatus.PENDING_ACTIVATION: frozenset({SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED}),
    SubscriptionStatus.ACTIVE: frozenset(
        {
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.SUSPENDED,
            SubscriptionStatus.CANCELLED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.PAST_DUE: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELLED}
    ),
    SubscriptionStatus.SUSPENDED: frozenset({SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED}),
    SubscriptionStatus.CANCELLED: frozenset(),
    SubscriptionStatus.EXPIRED: frozenset(),
}

BILLABLE_STATUSES = frozenset({SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED})


class MidCycleAddPolicy(StrEnum):
    PRORATE_DAILY = "PRORATE_DAILY"
    FULL_PERIOD = "FULL_PERIOD"
    NEXT_PERIOD = "NEXT_PERIOD"


class MidCycleRemovePolicy(StrEnum):
    PRORATE_CREDIT = "PRORATE_CREDIT"
    NO_CREDIT = "NO_CREDIT"


class EnrollmentEndReason(StrEnum):
    REMOVED_FROM_FLEET = "REMOVED_FROM_FLEET"
    DISPOSED = "DISPOSED"
    SUBSCRIPTION_ENDED = "SUBSCRIPTION_ENDED"
    CORRECTION = "CORRECTION"


class PendingChargeStatus(StrEnum):
    PENDING = "PENDING"
    INVOICED = "INVOICED"
    WAIVED = "WAIVED"


class InvoiceStatus(StrEnum):
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"


class InvoiceLineType(StrEnum):
    ASSET_SUBSCRIPTION = "ASSET_SUBSCRIPTION"
    MINIMUM_COMMITMENT = "MINIMUM_COMMITMENT"
    PRORATION_CHARGE = "PRORATION_CHARGE"
    PRORATION_CREDIT = "PRORATION_CREDIT"
    DISCOUNT = "DISCOUNT"
    TAX = "TAX"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    MOBILE_MONEY = "MOBILE_MONEY"


class PaymentStatus(StrEnum):
    RECORDED = "RECORDED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
