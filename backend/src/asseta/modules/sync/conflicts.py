"""Which refusals of a queued offline operation are held for review (CONFLICT) instead of rejected.

A CONFLICT is kept and reviewed, never applied: the right outcome whenever the record is real and only the server's
state moved on while the device was offline. REJECTED is for payloads that could never have been valid."""

CONFLICT_CODES = {
    "INVALID_JOB_TRANSITION",
    "READING_NOT_ALLOWED",
    "MACHINE_BUSY",
    "CAPTURE_ID_CONFLICT",
    "JOB_NOT_ACTIVE",
    "STALE_VERSION",
    "DUPLICATE_PAYMENT_REFERENCE",
    "TRANSFER_ALREADY_DECIDED",  # cash custody: a second acknowledgement of the same transfer/float
    "FLOAT_ALREADY_ACKNOWLEDGED",
    # customer hours: two field users drawing on the same remaining hours are serialised; the loser sees a conflict
    "NO_AVAILABLE_HOURS",
    "EXCEEDS_REMAINING_HOURS",
    # engine-hour controls: resolvable later (a baseline approved, the other job corrected), never silently applied
    "BASELINE_REQUIRED",
    "OVERLAPPING_ALLOCATION",
    "OVERLAPPING_ACTIVITY",
    "BASELINE_PENDING",
    "CORRECTION_PENDING",
    # cash retention: the tenant switched retention off after the device's snapshot, or a concurrent duplicate
    "RETENTION_NOT_ALLOWED",
    "DUPLICATE_RETENTION",
    # the tenant switched a capability off after the device queued the operation (kept for review, never applied)
    "ENGINE_HOURS_DISABLED",
    "CASH_CUSTODY_DISABLED",
    # stronger remittances (DEC-031 D2): the tenant switched a requirement on, or deactivated the chosen deposit
    # account, after the device queued the remittance (kept for review, never applied)
    "REMITTANCE_REFERENCE_REQUIRED",
    "REMITTANCE_EVIDENCE_REQUIRED",
    "REMITTANCE_ACCOUNT_REQUIRED",
    "DEPOSIT_ACCOUNT_INACTIVE",
    # site check-ins (DEC-031 M3): switched off after the device queued it, or the same client id reused by another
    # person (kept for review, never applied)
    "SITE_CHECKIN_DISABLED",
    "CHECKIN_ID_CONFLICT",
    # DEC-032: a daily report whose readings changed or arrived differently, a repeat of its id, a report replaced
    # already, evidence newly required, or a changeover the job's state no longer allows (kept for review)
    "REPORT_READINGS_INVALID",
    "REPORT_HOURS_EXCEED_TOTAL",
    "REPORT_ID_CONFLICT",
    "REPORT_NOT_SUPERSEDABLE",
    "REPORT_EVIDENCE_REQUIRED",
    "CHANGEOVER_NOT_ALLOWED",
    "CHANGEOVER_SAME_CUSTOMER",
    "CHANGEOVER_JOB_REQUIRED",  # billing split switched on after the device queued the changeover
    "CHANGEOVER_JOB_INVALID",  # the follow-on job was approved, cancelled or changed since
    # DEC-032 Phase 3: the tenant now requires a collection link or supporting evidence, the balance left a partial
    # remittance without a reason, or the purchase a collection names changed (kept for review, never applied)
    "COLLECTION_LINK_REQUIRED",
    "PARTIAL_REMITTANCE_REASON_REQUIRED",
    "EVIDENCE_REQUIRED",
    "PURCHASE_NOT_FOUND",
    "PURCHASE_CANCELLED",
    "OVER_ALLOCATION",
    "ALLOCATION_MISMATCH",
    "INVOICE_NOT_OPEN",  # the invoice a collection names was voided or paid off before the upload
    # DEC-033 petty cash: switched off, the fund changed hands or was deactivated, the offline expense went above what
    # was available (with overspend offline not allowed), the office decided first, or evidence became required
    # after the device queued the operation (kept for review, never applied)
    "PETTY_CASH_DISABLED",
    "PETTY_CASH_INSUFFICIENT",
    "PETTY_CASH_FUND_INACTIVE",
    "PETTY_CASH_CURRENCY_MISMATCH",
    "PETTY_CASH_ADVANCES_DISABLED",
    "PETTY_CASH_ADVANCE_CLEARED",
    "PETTY_CASH_ADVANCE_EXPENSES_PENDING",
    "PETTY_CASH_ALREADY_ACKNOWLEDGED",
    "PETTY_CASH_ALREADY_DECIDED",
    "PETTY_CASH_NOTHING_TO_TOP_UP",
    "PETTY_CASH_ABOVE_CAP_REASON_REQUIRED",
    "NOT_FUND_HOLDER",
}

# Money already changed hands in the field when these three were queued, so a refusal caused by anything that changed
# since (a person, customer, machine, account, reason or switch), or by a slip in the device's own figures, must not
# lose the record. Scoped to these operations: elsewhere the same codes keep their meaning.
MONEY_OPERATIONS = frozenset({"CASH_COLLECTION", "CASH_HANDOVER", "HOURS_PURCHASE"})
MONEY_CONFLICT_CODES = frozenset(
    {
        # who holds the cash
        "STAFF_INACTIVE",
        "STAFF_NOT_LINKED",
        "NOT_CUSTODIAN",  # the tenant stopped recorders recording for someone else
        # what the cash pays for
        "ALLOCATION_EXCEEDS_PAYMENT",
        # where the cash went
        "DUPLICATE_HANDOVER",
        "DEPOSIT_ACCOUNT_NOT_FOUND",
        "DEPOSIT_ACCOUNT_CURRENCY_MISMATCH",
        "REMITTANCE_ACCOUNT_MISMATCH",
        "REASON_REQUIRED",
        "REASON_INVALID",
        "REASON_NOT_FOUND",
        "ATTACHMENT_NOT_FOUND",
        # the hours sold
        "HOURS_DISABLED",
        "WALK_IN_NOT_ALLOWED",
        "DUPLICATE_CUSTOMER",
        "CUSTOMER_INACTIVE",
        "MACHINE_INACTIVE",
        "SITE_INACTIVE",
        "NO_RATE",
        "DISCOUNT_ABOVE_MAXIMUM",
        "NOTHING_TO_PAY",
        # the job booked with the sale (OP_HOURS_SALE_BOOKING)
        "CONTRACT_REQUIRED",
        "CONTRACT_CHOICE_REQUIRED",
        "CONTRACT_NOT_ACTIVE",
        "CONTRACT_CUSTOMER_MISMATCH",
        "JOB_REQUEST_NOT_PERMITTED",
        "NO_STAFF_RECORD",
        "BILLING_MODE_NOT_ALLOWED",
        "DUPLICATE_JOB",
    }
)


def is_conflict(op_type: str, code: str) -> bool:
    return code in CONFLICT_CODES or (op_type in MONEY_OPERATIONS and code in MONEY_CONFLICT_CODES)
