"""The finite, code-defined catalog of notification types: severity, default channels, which channels are
mandatory (cannot be disabled by preferences) and whether SMS is low priority (sent only when opted in).
WebSocket push accompanies every in-app notification. Mobile PUSH and EMAIL are routed per category x severity
(`routing.py`); a type may make either mandatory."""

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Channel(StrEnum):
    IN_APP = "IN_APP"  # inbox + real-time WebSocket push
    SMS = "SMS"
    PUSH = "PUSH"  # mobile push to the recipient's registered Owner/Supervisor app devices (FCM / APNs)
    EMAIL = "EMAIL"  # the recipient's login e-mail address (Keycloak)


class Category(StrEnum):
    ACTION = "ACTION"  # something to do (approve, verify, pay)
    REMINDER = "REMINDER"
    ANOMALY = "ANOMALY"
    BILLING = "BILLING"
    INFO = "INFO"


class Context(StrEnum):
    TENANT = "TENANT"
    PLATFORM = "PLATFORM"


@dataclass(frozen=True)
class NotificationType:
    code: str
    label: str
    category: Category
    severity: Severity
    contexts: frozenset[Context]
    sms_default: bool = False
    mandatory: frozenset[Channel] = frozenset()
    low_priority: bool = False  # SMS only when the user (or tenant default) explicitly opted in


T, P = frozenset({Context.TENANT}), frozenset({Context.PLATFORM})
BOTH = T | P
IN_APP = frozenset({Channel.IN_APP})
IN_APP_EMAIL = frozenset({Channel.IN_APP, Channel.EMAIL})

_TYPES = (
    # Platform commerce
    NotificationType("PLATFORM_INVOICE_ISSUED", "New Asseta invoice", Category.BILLING, Severity.INFO, T, True),
    NotificationType("PLATFORM_INVOICE_DUE_SOON", "Asseta invoice due soon", Category.REMINDER, Severity.INFO, T, True),
    NotificationType(
        "PLATFORM_INVOICE_OVERDUE", "Asseta invoice overdue", Category.REMINDER, Severity.WARNING, BOTH, True, IN_APP
    ),
    NotificationType("PLATFORM_INVOICE_VOIDED", "Asseta invoice voided", Category.BILLING, Severity.WARNING, T, True),
    NotificationType("PLATFORM_PAYMENT_AWAITING_VERIFICATION", "Payment to verify", Category.ACTION, Severity.INFO, P),
    NotificationType("PLATFORM_PAYMENT_VERIFIED", "Payment received", Category.BILLING, Severity.INFO, T, True),
    NotificationType(
        "INVOICE_LINE_FULFILLED", "Purchase delivered", Category.BILLING, Severity.INFO, T, low_priority=True
    ),
    NotificationType(
        "FULFILMENT_REVERSAL_FLAGGED", "Reversal needs review", Category.ACTION, Severity.WARNING, P, mandatory=IN_APP
    ),
    NotificationType(
        "SUBSCRIPTION_STATUS_CHANGED", "Subscription status", Category.BILLING, Severity.WARNING, BOTH, True, IN_APP
    ),
    NotificationType(  # access-affecting notice: always also e-mailed
        "SUBSCRIPTION_RESTRICTION_UPCOMING",
        "Access restriction upcoming",
        Category.REMINDER,
        Severity.WARNING,
        T,
        True,
        IN_APP_EMAIL,
    ),
    NotificationType("SMS_WALLET_LOW", "SMS credits low", Category.BILLING, Severity.WARNING, T, mandatory=IN_APP),
    NotificationType(
        "SMS_WALLET_EMPTY", "SMS credits used up", Category.BILLING, Severity.CRITICAL, T, mandatory=IN_APP
    ),
    # Operations: actions
    NotificationType("APPROVAL_REQUESTED", "Approval requested", Category.ACTION, Severity.INFO, T),
    NotificationType("APPROVAL_PENDING_AGING", "Approval waiting", Category.REMINDER, Severity.WARNING, T, True),
    NotificationType("EXPENSE_DECIDED", "Expense decision", Category.INFO, Severity.INFO, T, low_priority=True),
    NotificationType("JOB_AWAITING_APPROVAL", "Job awaiting approval", Category.ACTION, Severity.INFO, T),
    NotificationType("JOB_ASSIGNED", "Job assigned to you", Category.ACTION, Severity.INFO, T),
    NotificationType("JOB_REQUEST_APPROVED", "Job request approved", Category.ACTION, Severity.INFO, T),
    NotificationType("JOB_CANCELLED", "Job declined or cancelled", Category.INFO, Severity.WARNING, T),
    NotificationType("CUSTOMER_PAYMENT_TO_VERIFY", "Customer payment to verify", Category.ACTION, Severity.INFO, T),
    NotificationType("CASH_HANDOVER_TO_VERIFY", "Cash handover to verify", Category.ACTION, Severity.INFO, T),
    # Cash custody chain (accountability design C)
    NotificationType("CASH_TRANSFER_TO_ACKNOWLEDGE", "Cash transfer to acknowledge", Category.ACTION, Severity.INFO, T),
    NotificationType("CASH_FLOAT_TO_ACKNOWLEDGE", "Cash float to acknowledge", Category.ACTION, Severity.INFO, T),
    NotificationType("CASH_APPROVAL_REQUESTED", "Cash approval requested", Category.ACTION, Severity.INFO, T),
    NotificationType("CASH_VARIANCE_OPENED", "Cash difference to review", Category.ANOMALY, Severity.WARNING, T, True),
    NotificationType("PARTIAL_REMITTANCE", "Partial remittance", Category.ANOMALY, Severity.WARNING, T, True),
    NotificationType("HOURS_APPROVAL_REQUESTED", "Customer hours approval", Category.ACTION, Severity.INFO, T),
    NotificationType(
        "HOURS_APPROVAL_DECIDED", "Customer hours decision", Category.INFO, Severity.INFO, T, low_priority=True
    ),
    NotificationType("HOURS_EXPIRING", "Customer hours expiring", Category.REMINDER, Severity.WARNING, T),
    NotificationType("HOURS_EXPIRED", "Customer hours expired", Category.INFO, Severity.INFO, T, low_priority=True),
    # Operations: reminders
    NotificationType("CASH_NOT_HANDED_OVER", "Cash not handed over", Category.REMINDER, Severity.WARNING, T, True),
    NotificationType(
        "HIRE_INVOICE_OVERDUE", "Customer invoice overdue", Category.REMINDER, Severity.INFO, T, low_priority=True
    ),
    NotificationType(
        "TRACKERS_STALE", "Trackers not reporting", Category.REMINDER, Severity.WARNING, T, low_priority=True
    ),
    NotificationType("JOB_MISSING_READINGS", "Job missing readings", Category.REMINDER, Severity.WARNING, T, True),
    NotificationType("MISSING_DAILY_REPORT", "Daily report missing", Category.REMINDER, Severity.WARNING, T, True),
    NotificationType("METER_APPROVAL_REQUESTED", "Meter approval requested", Category.ACTION, Severity.INFO, T),
    # Anomalies
    NotificationType("TRACKING_ALERT", "Tracking alert", Category.ANOMALY, Severity.WARNING, T, True),
    NotificationType(
        "METER_EXCEPTION", "Meter reading exception", Category.ANOMALY, Severity.WARNING, T, low_priority=True
    ),
    NotificationType("HOURS_OVERRUN", "Hours used beyond purchase", Category.ANOMALY, Severity.WARNING, T, True),
    NotificationType(
        "UNEXPLAINED_ENGINE_HOURS", "Engine hours to explain", Category.ANOMALY, Severity.WARNING, T, low_priority=True
    ),
    NotificationType("SYNC_ANOMALY", "Device sync anomaly", Category.ANOMALY, Severity.WARNING, T, low_priority=True),
    NotificationType(
        "SOD_VIOLATION_ATTEMPT", "Segregation-of-duties attempt", Category.ANOMALY, Severity.WARNING, T, True, IN_APP
    ),
    NotificationType("ANOMALY_DETECTED", "Anomaly detected", Category.ANOMALY, Severity.WARNING, T, True),
    NotificationType("ML_MODEL_DRIFT", "Model feature drift", Category.ANOMALY, Severity.WARNING, P),
    NotificationType("SYSTEM_TEST", "Test notification", Category.INFO, Severity.INFO, P, True),
)
TYPES: dict[str, NotificationType] = {t.code: t for t in _TYPES}
