package com.asseta.owner.ui.accountability

import com.asseta.core.domain.owner.OwnerFormat

/**
 * Wording of the Owner app's accountability screens, shared with iOS word for word
 * (docs/requirements/accountability-mobile-strings.md, keys `owner.*`).
 */
object OwnerAccountabilityTexts {
    const val MORE_ACCOUNTABILITY = "Accountability"

    // Approvals sections
    const val DISCOUNTS = "Customer discounts"
    const val DISCOUNTS_EMPTY = "No discounts waiting."
    const val CREDIT = "Credit arrangements"
    const val CREDIT_EMPTY = "No credit arrangements waiting."
    const val HOURS_TRANSFERS = "Hours transfers"
    const val HOURS_TRANSFERS_EMPTY = "No hours transfers waiting."
    const val CANCELLATIONS = "Hours cancellations"
    const val CANCELLATIONS_EMPTY = "No cancellations waiting."
    const val BASELINES = "Meter baselines"
    const val BASELINES_EMPTY = "No baselines waiting."
    const val CLASSIFICATIONS = "Engine-hour classifications"
    const val CLASSIFICATIONS_EMPTY = "No classifications waiting."
    const val CORRECTIONS = "Reading corrections"
    const val CORRECTIONS_EMPTY = "No corrections waiting."
    const val WRITE_OFFS = "Cash write-offs"
    const val WRITE_OFFS_EMPTY = "No write-offs waiting."
    const val RETENTIONS = "Cash retentions"
    const val RETENTIONS_EMPTY = "No retention requests waiting."
    const val ADJUSTMENTS = "Custody adjustments"
    const val ADJUSTMENTS_EMPTY = "No adjustments waiting."
    fun proposed(time: String) = "Proposed $time"

    // Row headlines
    fun rowDiscount(percent: String) = "$percent% discount"
    fun rowCredit(money: String) = "Credit limit $money"
    fun rowHoursTransfer(hours: String) = "Move $hours h to another machine"
    const val ROW_CANCELLATION = "Cancel an hours purchase"
    fun rowBaseline(reading: String, machine: String) = "Baseline $reading h · $machine"
    fun rowClassification(hours: String, category: String) = "$hours h · $category"
    fun rowCorrection(old: String, new: String, machine: String) = "$old → $new h · $machine"
    fun rowWriteOff(money: String) = "Write off $money"
    fun rowRetention(money: String) = "Keep $money"
    fun rowAdjustment(kind: String, money: String) = "$kind $money"

    // Decision screen
    const val TITLE_DISCOUNT = "Customer discount"
    const val TITLE_CREDIT = "Credit arrangement"
    const val TITLE_HOURS_TRANSFER = "Hours transfer"
    const val TITLE_CANCELLATION = "Hours cancellation"
    const val TITLE_BASELINE = "Meter baseline"
    const val TITLE_CLASSIFICATION = "Engine-hour classification"
    const val TITLE_CORRECTION = "Reading correction"
    const val TITLE_WRITE_OFF = "Cash write-off"
    const val TITLE_RETENTION = "Cash retention"
    const val TITLE_ADJUSTMENT = "Custody adjustment"
    const val REQUEST = "Request"
    const val DECISION = "Decision"
    const val APPROVE = "Approve"
    const val REJECT = "Reject"
    const val NOTE_OPTIONAL = "Note (optional to approve, required to reject)"
    const val NOTE_REQUIRED = "Note (at least 5 characters)"
    const val OWN_REQUEST = "Someone else must decide your own request"
    const val CONFIRM_REJECT = "Reject this request?"
    const val APPROVED = "Approved."
    const val REJECTED = "Rejected."
    const val NOT_FOUND_TITLE = "Request not found"
    const val NOT_FOUND_MESSAGE = "It may already be decided."
    const val FOOTER = "The person who proposed a request can't decide it."

    // Field labels
    const val F_DISCOUNT = "Discount"
    const val F_EFFECTIVE_FROM = "Effective from"
    const val F_EFFECTIVE_TO = "Effective to"
    const val F_CREDIT_LIMIT = "Credit limit"
    const val F_TERMS = "Terms"
    const val F_HOURS = "Hours"
    const val F_FROM_MACHINE = "From machine"
    const val F_TO_MACHINE = "To machine"
    const val F_MACHINE = "Machine"
    const val F_READING = "Reading"
    const val F_OLD_READING = "Old reading"
    const val F_NEW_READING = "New reading"
    const val F_PERIOD = "Period"
    const val F_CATEGORY = "Category"
    const val F_OUTCOME = "Outcome"
    const val OUTCOME_NON_CUSTOMER = "Approved non-customer work"
    const val OUTCOME_VARIANCE = "Identified difference"
    const val F_DECLARED = "Declared"
    const val F_RECEIVED = "Received"
    const val F_DIFFERENCE = "Difference"
    const val F_AMOUNT = "Amount"
    const val F_VALID_UNTIL = "Valid until"
    const val F_KIND = "Kind"
    const val F_REASON = "Reason"
    const val F_NOTE = "Note"
    const val F_PROPOSED_BY = "Proposed by"
    const val F_PROPOSED = "Proposed"
    const val F_STATUS = "Status"
    const val F_SOURCE = "Source"
    const val F_CAPTURED = "Captured"
    const val F_WHEN = "When"

    // Remittance confirm
    const val REMIT_AMOUNT_RECEIVED = "Amount received"
    const val REMIT_AMOUNT_FOOTER = "Count the cash. A different amount opens a cash difference for review."
    const val REMIT_EXPECTED = "Expected balance"
    const val REMIT_SHORTFALL = "Not covered by a retention"
    const val REMIT_RECEIVED = "Received"
    const val REMIT_ERR_AMOUNT = "Enter the amount received (0 or more)."

    // Dashboard
    const val DASH_TITLE = "Accountability"
    fun dashFooter(version: String, time: String) = "Policy $version · As of $time"
    const val DASH_HIDDEN = "Some tiles are hidden by your company's settings."
    const val DASH_EMPTY = "Nothing to show."
    const val DASH_APPROVALS = "Outstanding approvals"
    const val DASH_APPROVAL_REQUESTS = "Approval requests"
    const val DASH_PAYMENTS_TO_VERIFY = "Payments to verify"
    const val DASH_REMITTANCES_TO_VERIFY = "Remittances to verify"
    const val DASH_CASH_RETENTIONS = "Cash retentions"
    const val DASH_CUSTODY_ADJUSTMENTS = "Custody adjustments"
    const val DASH_WRITE_OFFS = "Write-offs"
    const val DASH_TOTAL = "Total"
    const val DASH_CASH = "Cash"
    const val DASH_TRANSFERS_AWAITING = "Transfers awaiting acknowledgement"
    const val DASH_FLOATS_AWAITING = "Floats awaiting acknowledgement"
    const val DASH_REMITTANCES_AWAITING = "Remittances awaiting confirmation"
    const val DASH_PARTIAL_REMITTANCES = "Partial remittances"
    const val DASH_CUSTODIANS = "Cash per custodian"
    fun custodianLine(money: String) = "$money outstanding"
    fun inTransit(money: String) = "$money in transit"
    const val DASH_PAYMENTS = "Payments awaiting confirmation"
    const val DASH_DISCREPANCIES = "Discrepancies"
    const val DASH_OPEN_VARIANCES = "Open cash differences"
    const val DASH_WRITE_OFFS_PROPOSED = "Write-offs proposed"
    const val DASH_SYNC_CONFLICTS = "Sync conflicts to review"
    const val DASH_INVESTIGATIONS = "Investigations"
    const val DASH_OPEN = "Open"
    const val DASH_IN_REVIEW = "In review"
    const val DASH_ATTEMPTS = "Refused attempts"
    const val DASH_PERMISSION_DENIED = "Permission refusals"
    const val DASH_SOD = "Own-request decisions refused"
    fun window(days: Int) = "Last $days days"
    const val DASH_CUSTOMER_HOURS = "Customer hours"
    const val DASH_HOURS_ACTIVATED = "Activated"
    const val DASH_HOURS_CONSUMED = "Consumed"
    const val DASH_HOURS_REMAINING = "Remaining"
    const val DASH_HOURS_AWAITING = "Awaiting activation"
    const val DASH_HOURS_EXPIRED = "Expired"
    const val DASH_OPEN_OVERRUNS = "Hours beyond purchase"
    const val DASH_HOURS_AWAITING_TILE = "Hours awaiting activation"
    const val DASH_PURCHASES_AWAITING_PAYMENT = "Purchases awaiting payment"
    const val DASH_PURCHASES_PARTLY_ACTIVE = "Purchases partly active"
    const val DASH_ENGINE_HOURS = "Engine hours"
    const val DASH_MACHINES = "Machines"
    const val DASH_UNEXPLAINED = "Unexplained engine hours"
    fun unexplainedLine(hours: String, days: Int?) = if (days == null) "$hours h" else "$hours h · oldest $days days"
    const val DASH_MISSING_REPORTS = "Missing daily reports"
    fun missingLine(machine: String, day: String) = "$machine · $day"
    fun count(count: Int, money: String) = "$count · $money"
    const val DASH_NONE = "None"

    fun reconciliationStatus(status: String): String = when (status) {
        "NO_BASELINE" -> "No baseline"
        "RECONCILED" -> "Reconciled"
        "PENDING_REVIEW" -> "Pending review"
        "UNEXPLAINED" -> "Unexplained hours"
        else -> status.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    // --- Gap pass (DEC-030 G1-G5) ---------------------------------------------------------------------------------
    const val F_CUSTOMER = "Customer"
    const val F_PURCHASE = "Purchase"
    const val F_CUSTODIAN = "Cash held by"
    const val F_COUNTERPARTY = "Other custodian"
    const val F_REQUESTED_BY = "Requested by"
    const val F_DECIDED_BY = "Decided by"
    const val F_DECISION_NOTE = "Decision note"
    const val F_FROM = "From"
    const val F_TO = "To"
    const val F_RECORDED_BY = "Recorded by"
    const val F_ACKNOWLEDGED_BY = "Acknowledged by"
    const val F_TRANSFERRED = "Transferred"
    const val F_ISSUED = "Issued"
    const val F_DAY = "Day"
    const val F_CUTOFF = "Cut-off"
    const val F_NOT_REMITTED = "Not remitted"
    const val F_FLAGGED = "Flagged"
    fun proposedBy(time: String, name: String) = "Proposed $time by $name"
    const val RECORD_TRANSFER_TITLE = "Cash transfer"
    const val RECORD_FLOAT_TITLE = "Cash float"
    const val RECORD_NOT_FOUND_TITLE = "Record not found"
    const val RECORD_NOT_FOUND_MESSAGE = "It may have been removed, or you may not have access to it."
    const val DASH_REMITTANCES_OVERDUE = "Remittances overdue today"
    fun hour(h: Int) = "${h.toString().padStart(2, '0')}:00"
    fun dashCutoff(h: Int) = "Cut-off ${hour(h)}"
    const val OVERDUE_TITLE = "Overdue remittances"
    const val OVERDUE_DETAIL_TITLE = "Overdue remittance"
    const val OVERDUE_EMPTY = "No overdue remittances today."
    fun overdueLine(h: Int, day: String) = "Still held after the ${hour(h)} cut-off on $day."

    // --- DEC-032 Phase 3: independence and evidence (docs/requirements/accountability-mobile-strings.md) ------------
    const val PARTIAL_SECTION = "Partial remittance reasons"
    const val PARTIAL_EMPTY = "No partial remittance reasons waiting."
    const val PARTIAL_TITLE = "Partial remittance reason"
    fun rowPartial(amount: String, custodian: String) = "$amount not remitted · $custodian"
    const val PARTIAL_REMITTED = "Remitted"
    const val PARTIAL_NOT_REMITTED = "Not remitted"
    const val CLOSURE_SECTION = "Variance closures"
    const val CLOSURE_EMPTY = "No variance closures waiting."
    const val CLOSURE_TITLE = "Variance closure"
    fun rowClosure(difference: String, outcome: String) = "Close $difference ($outcome)"
    const val CLOSURE_OUTCOME = "Proposed outcome"
    const val VARIANCE_TITLE = "Variance"
    const val VARIANCE_ASSIGNEE = "Assigned to"
    const val VARIANCE_ASSIGNED_BY = "Assigned by"
    const val VARIANCE_EXPLANATION = "Explanation"
    const val VARIANCE_EXPLAINED_BY = "Explained by"
    const val VARIANCE_EVIDENCE = "Evidence"
    const val VARIANCE_HISTORY = "History"
    const val VARIANCE_CHECK = "What was found"
    fun varianceHistoryRow(time: String, action: String, who: String?) = listOfNotNull(time, action, who).joinToString(" · ")
    const val REMIT_NUMBER = "Remittance number"
    const val REMIT_EVIDENCE = "Evidence"
    const val REMIT_OUTSTANDING = "Difference still open"
    const val REMIT_PARTIAL_REASON = "Why part stayed with the custodian"
    const val REMIT_PARTIAL_STATUS = "Reason status"
    const val REMIT_PARTIAL_REVIEW = "Review the reason"
    const val NUMBER = "Number"

    fun remitEvidence(code: String?): String? = when (code) {
        "DECLARED" -> "Declared by the field"
        "SUPPORTED" -> "Supported by evidence"
        "CONFIRMED" -> "Confirmed by the company"
        null -> null
        else -> OwnerFormat.humanize(code)
    }

    fun varianceOutcome(code: String?): String? = when (code) {
        "RECOVERED" -> "Recovered"
        "CORRECTED_ERROR" -> "Corrected error"
        "EXPLAINED" -> "Explained"
        "WRITTEN_OFF" -> "Written off"
        null -> null
        else -> OwnerFormat.humanize(code)
    }

    fun varianceCheck(code: String?): String? = when (code) {
        "PURCHASE_OVER_ACTIVATED" -> "Purchase over-activated"
        "NEGATIVE_REMAINING" -> "Negative hours remaining"
        "CONSUMPTION_MISMATCH" -> "Usage does not match records"
        "ALLOCATION_MISMATCH" -> "Allocation does not match records"
        null -> null
        else -> OwnerFormat.humanize(code)
    }

    fun varianceAction(code: String): String = when (code) {
        "OPENED" -> "Opened"
        "ASSIGNED" -> "Assigned"
        "EXPLAINED" -> "Explained"
        "CLOSURE_PROPOSED" -> "Closure proposed"
        "CLOSURE_APPROVED" -> "Closure approved"
        "CLOSURE_REJECTED" -> "Closure rejected"
        "WRITE_OFF_PROPOSED" -> "Write-off proposed"
        "WRITE_OFF_APPROVED" -> "Write-off approved"
        "WRITE_OFF_REJECTED" -> "Write-off rejected"
        "RESOLVED" -> "Resolved"
        else -> OwnerFormat.humanize(code)
    }

    private val CLOSURE_ERRORS = mapOf(
        "SEGREGATION_OF_DUTIES" to "You proposed this closure, so someone else must decide it.",
        "CLOSURE_NOT_PROPOSED" to "This closure was already decided. Reload to see it.",
        "WRITEOFF_APPROVAL_REQUIRED" to "A write-off needs its own approval.",
        "VARIANCE_OUTCOME_NOT_ALLOWED" to "This outcome is not allowed for this variance.",
    )
    private val PARTIAL_ERRORS = mapOf(
        "SEGREGATION_OF_DUTIES" to "You recorded this remittance, so someone else must decide its reason.",
        "PARTIAL_APPROVAL_NOT_FOUND" to "This reason was already decided. Reload to see it.",
    )
    fun closureError(code: String?, fallback: String): String = CLOSURE_ERRORS[code] ?: fallback
    fun partialError(code: String?, fallback: String): String = PARTIAL_ERRORS[code] ?: fallback

    // --- DEC-031 Phase 3: remittance details, surplus, holding allowance ------------------------------------------
    const val REMIT_METHOD = "Method"
    const val REMIT_ACCOUNT = "Paid into"
    const val REMIT_REFERENCE = "Reference"
    const val REMIT_NO_PHOTO = "No deposit slip photo"
    fun remitPhoto(n: Int) = "deposit slip photo $n"
    fun remitMethod(wire: String?): String? = when (wire) {
        "CASH_TO_OFFICE" -> "Cash to the office"
        "BANK_DEPOSIT" -> "Bank deposit"
        "MOBILE_MONEY" -> "Mobile money"
        null -> null
        else -> OwnerFormat.humanize(wire)
    }
    const val VARIANCE_SURPLUS = "Surplus to explain"
    fun rowSurplus(money: String) = "Surplus to explain: $money"
    const val OVERDUE_REASON_CUTOFF = "Not remitted by the daily cut-off"
    const val OVERDUE_REASON_HELD = "Held longer than allowed"
    const val F_HELD_SINCE = "Held since"
    const val F_ALLOWED = "Allowed"
    const val OVERDUE_HELD_LINE_SHORT = "Held longer than allowed."
    fun days(n: Int) = if (n == 1) "1 day" else "$n days"
    fun overdueHeldLine(date: String, days: Int) = "Held since $date, longer than the allowed ${days(days)}."

    /** A machine's days of the work allocation ledger (opened from the machine and the management view; as iOS). */
    const val MACHINE_DAYS = "Machine days"

    /** Investigation signal names (owner.signal.*); other codes humanized. */
    fun signalName(code: String): String = when (code) {
        "ENGINE_RUNNING_WITHOUT_WORK" -> "Engine running without work during the day"
        "MACHINE_FUEL_ABOVE_NORM" -> "Fuel above the norm for the engine hours"
        "REPEATED_PATTERN" -> "Repeated items to look at for one person"
        else -> OwnerFormat.humanize(code)
    }

    const val HOURS_MORE = "Customer hours"
    const val HOURS_LIST_TITLE = "Customer hours"
    const val HOURS_EMPTY = "No prepaid hours with hours left."
    const val HOURS_LIST_FOOTER = "Prepaid hours with hours left. Selling and moving hours is done in the field app or on the web."
    fun hoursRow(purchase: String, customer: String) = "$purchase · $customer"
    fun hoursLeft(hours: String) = "$hours h left"
    const val HOURS_PURCHASE_TITLE = "Hours purchase"
    const val HOURS_HOURS = "Hours"
    const val HOURS_CUSTOMER = "Customer"
    const val HOURS_MACHINE = "Machine"
    const val HOURS_STATUS = "Status"
    const val HOURS_BOUGHT = "Bought"
    const val HOURS_ACTIVATED = "Activated"
    const val HOURS_USED = "Used"
    const val HOURS_TRANSFERRED = "Moved to other machines"
    const val HOURS_EXPIRED = "Expired"
    const val HOURS_REMAINING = "Left"
    const val HOURS_AWAITING = "Awaiting activation"
    const val HOURS_REFUNDED = "Refunded"
    const val HOURS_CORRECTED = "Corrected"
    const val HOURS_REVERSED = "Reversed"
    const val HOURS_PAYMENTS = "Payments"
    const val HOURS_PAYMENT_RELEASED = "No longer counted"
    fun hoursPaymentReversed(date: String) = "Reversed $date"
    const val HOURS_MACHINES = "Machines"
    const val HOURS_OPEN_STATEMENT = "Hours statement"
    fun purchaseStatus(wire: String): String = when (wire) {
        "AWAITING_PAYMENT" -> "Awaiting payment"
        "PARTLY_ACTIVE" -> "Partly active"
        "ACTIVE" -> "Active"
        "CONSUMED" -> "Used up"
        "EXPIRED" -> "Expired"
        "CANCELLED" -> "Cancelled"
        else -> OwnerFormat.humanize(wire)
    }

    const val STMT_TITLE = "Hours statement"
    fun stmtHeader(customer: String, period: String) = "$customer · $period"
    const val STMT_TOTALS = "Totals"
    const val STMT_OPENING = "Opening balance"
    const val STMT_BOUGHT = "Bought"
    const val STMT_ACTIVATED = "Activated"
    const val STMT_USED = "Used"
    const val STMT_TRANSFERRED_IN = "Moved in"
    const val STMT_TRANSFERRED_OUT = "Moved out"
    const val STMT_EXPIRED = "Expired"
    const val STMT_CANCELLED = "Cancelled"
    const val STMT_CLOSING = "Closing balance"
    const val STMT_AWAITING = "Awaiting activation (now)"
    const val STMT_REFUNDED = "Refunded"
    const val STMT_CORRECTED = "Corrected"
    const val STMT_ADJUSTMENTS = "Corrections, refunds and reversals"
    fun stmtLine(wire: String): String = when (wire) {
        "CORRECTION_ADD" -> "Hours added by correction"
        "CORRECTION_DEDUCT" -> "Hours removed by correction"
        "REFUNDED" -> "Hours refunded"
        "REVERSAL" -> "Hours reversed"
        else -> OwnerFormat.humanize(wire)
    }
    const val STMT_USAGE = "Hours used"
    const val STMT_USAGE_EMPTY = "No hours used in this period."
    fun stmtUsageRow(day: String, report: String) = "$day · $report"
    const val STMT_OPEN_PDF = "Open PDF"
    const val STMT_PDF_FAILED = "Could not get the PDF. Check your connection and try again."
    const val STMT_NO_PDF_APP = "No app on this phone can open PDFs."
    fun stmtFooter(timezone: String, time: String) = "Times are in $timezone. Generated $time."
}
