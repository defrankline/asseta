package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.model.sync.CashTransferDto

/**
 * Wording of the accountability screens of the field app, shared with iOS word for word
 * (docs/requirements/accountability-mobile-strings.md, keys `field.*`).
 */
object FieldAccountabilityTexts {
    // Money "+" menu
    const val MENU_SELL_HOURS = "Sell customer hours"
    const val MENU_HOURS_TRANSFER = "Request hours transfer"
    const val MENU_TRANSFER_CASH = "Transfer cash to a colleague"
    const val MENU_KEEP_CASH = "Ask to keep cash"

    // Titles
    const val TITLE_HOURS_SALE = "Sell customer hours"
    const val TITLE_HOURS_TRANSFER = "Request hours transfer"
    const val TITLE_CASH_TRANSFER = "Transfer cash"
    const val TITLE_ACK_TRANSFER = "Cash transfer"
    const val TITLE_ACK_FLOAT = "Cash float"
    const val TITLE_RETENTION = "Ask to keep cash"
    const val TITLE_DAILY = "Daily reading"
    const val TITLE_BASELINE = "Propose meter baseline"
    const val TITLE_CORRECTION = "Propose reading correction"

    // Common
    const val CASH_HOLDER = "Cash held by"
    const val ME = "Me"
    const val REASON_CATEGORY = "Reason category"
    const val REASON_CATEGORY_OPTIONAL = "Reason category (optional)"
    const val NO_CATEGORY = "No category"
    const val REASON = "Reason"
    const val NOTE_OPTIONAL = "Note (optional)"
    const val AMOUNT = "Amount"
    const val CURRENCY = "Currency"
    const val NEEDS_RULES = "Connect once so this phone can load your company's rules for this."
    const val ONLINE_ONLY = "Connect to the internet to send this request."
    fun lastUpdated(time: String) = "Last updated $time."

    // Sell customer hours
    const val SECTION_CUSTOMER = "Customer"
    const val REGISTERED = "Registered"
    const val WALK_IN = "Walk-in"
    const val CUSTOMER = "Customer"
    const val CUSTOMER_EMPTY = "Customers appear here after a sync."
    const val WALK_IN_NAME = "Customer name"
    const val WALK_IN_PHONE = "Phone (optional)"
    const val WALK_IN_FOOTER = "The office gives a walk-in customer a code. A phone number helps find them again."
    const val SECTION_HOURS = "Hours"
    const val MACHINE = "Machine"
    const val HOURS = "Hours"
    const val HOURS_FOOTER = "The price comes from your company's rate card and any approved discount."
    const val SECTION_PAYMENT = "Payment"
    const val PAID_NOW = "Paid now"
    const val NOT_PAID = "Not paid yet"
    const val AMOUNT_RECEIVED = "Amount received"
    const val REFERENCE = "Reference (required for bank and mobile money)"
    const val RECEIVED = "Received"
    const val PAYMENT_FOOTER = "Hours become available only after someone else verifies this payment."
    const val NOT_PAID_FOOTER = "The hours stay inactive until a payment is verified or credit is approved by the office."
    const val EVIDENCE = "Payment evidence (optional)"
    const val EVIDENCE_FOOTER = "Receipt or mobile-money screenshot. Stored encrypted on this phone and uploaded before the sale is sent."
    const val PHOTOGRAPH = "Photograph evidence"
    const val ADD_PHOTO = "Add another photo"
    const val HOURS_OFF = "Customer hours are turned off for your company."

    fun method(m: PaymentMethod): String = when (m) {
        PaymentMethod.CASH -> "Cash"
        PaymentMethod.BANK -> "Bank"
        PaymentMethod.MOBILE_MONEY -> "Mobile money"
    }

    // Request hours transfer
    const val PURCHASE = "Purchase"
    fun purchaseOption(number: String, hours: String) = "$number · $hours h left"
    const val PURCHASES_EMPTY = "No purchases with hours left. Purchases appear here after you connect."
    const val FROM_MACHINE = "From machine"
    const val TO_MACHINE = "To machine"
    const val HOURS_TO_MOVE = "Hours to move"
    const val TRANSFER_FOOTER_APPROVAL = "Someone else approves the transfer before the hours move."
    const val TRANSFER_FOOTER_DIRECT = "The hours move when the server accepts the request."

    // Transfer cash
    const val FROM = "From"
    const val TO = "To"
    const val AMOUNT_HANDED = "Amount handed over"
    const val TRANSFERRED = "Transferred"
    const val AMOUNT_YOU_RECEIVED = "Amount you received"
    const val CASH_FOOTER_ACK = "The cash stays with the sender until the receiver acknowledges it."
    const val CASH_FOOTER_NO_ACK = "The cash moves to the receiver when the server accepts the transfer."
    const val CASH_FOOTER_SELF = "Recording a transfer you receive counts as your acknowledgement."
    const val CUSTODIANS_EMPTY = "Colleagues who hold cash appear here after you connect."

    // Acknowledge
    const val ACK_SECTION = "Cash to acknowledge"
    fun transferFrom(name: String?) = "Transfer from ${name ?: SOMEONE}"
    const val FLOAT_FROM_OFFICE = "Float from the office"
    const val SOMEONE = "A colleague"
    const val DECLARED = "Declared amount"
    const val SENT = "Sent"
    const val ISSUED = "Issued"
    const val ACK_AMOUNT = "Amount received"
    const val ACKNOWLEDGE = "Acknowledge"
    const val DISPUTE = "Dispute"
    const val DISPUTE_REASON = "Why you dispute it"
    const val ACK_FOOTER = "A different amount opens a cash difference for the office to review."
    const val ACK_WAITING = "Your answer is waiting to sync."
    const val ACK_NOT_FOUND = "This item is no longer waiting for you."

    // Money "Transfers"
    const val TRANSFERS = "Transfers"
    const val TRANSFERS_EMPTY_TITLE = "No cash transfers"
    const val TRANSFERS_EMPTY_MESSAGE = "Cash moved between you and colleagues appears here."
    fun transferTo(name: String?) = "To ${name ?: SOMEONE}"
    fun transferFromRow(name: String?) = "From ${name ?: SOMEONE}"

    fun transferStatus(status: String): String = when (status) {
        CashTransferDto.PENDING -> "Awaiting acknowledgement"
        CashTransferDto.ACKNOWLEDGED -> "Acknowledged"
        CashTransferDto.DISPUTED -> "Disputed"
        else -> status.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    // Ask to keep cash
    const val RETENTION_AMOUNT = "Amount to keep"
    const val RETENTION_FOOTER = "Someone else approves this. Until then the full balance is expected when you remit."
    const val RETENTION_SENT = "Request sent for approval."
    const val SEND = "Send"
    const val RETENTION_OFF = "Your company does not allow keeping cash."

    // Readings
    const val RECORD_DAILY = "Record daily reading"
    const val PROPOSE_BASELINE = "Propose meter baseline"
    const val PROPOSE_CORRECTION = "Propose a correction"
    const val DAILY_FOOTER = "A daily reading outside a job keeps the machine's engine hours accounted for."
    const val BASELINE_FOOTER = "Someone else approves the baseline before it counts."
    const val BASELINE_NOTE = "Note (optional)"
    const val CORRECTION_OF = "Reading to correct"
    const val CORRECTION_REASON = "Reason for the correction"
    const val CORRECTION_FOOTER = "The corrected reading replaces the old one only after someone else approves it."

    // Sync status titles
    const val OUTBOX_HOURS_SALE = "Hours sale"
    const val OUTBOX_HOURS_TRANSFER = "Hours transfer request"
    const val OUTBOX_CASH_TRANSFER = "Cash transfer"
    const val OUTBOX_TRANSFER_ACK = "Transfer acknowledgement"
    const val OUTBOX_FLOAT_ACK = "Float acknowledgement"
    const val OUTBOX_BASELINE = "Meter baseline proposal"
    const val OUTBOX_CORRECTION = "Reading correction proposal"
    const val OUTBOX_DAILY = "Daily reading"

    // --- Gap pass (DEC-030 G2/G3) ------------------------------------------------------------------------------------
    const val RETENTION_SAVED = "Saved. It is sent when the phone syncs."
    const val RETENTION_VIEW_STATUS = "View request status"
    const val TITLE_RETENTION_STATUS = "Request to keep cash"
    const val RETENTION_NOT_SYNCED = "This request has not reached the server yet."
    const val RETENTION_OFFLINE = "Connect to the internet to see whether it was approved."
    const val RETENTION_NOT_FOUND = "This request is not on this phone."
    const val RETENTION_REQUESTED = "Requested"
    const val RETENTION_DECIDED_BY = "Decided by"
    const val RETENTION_DECISION_NOTE = "Decision note"
    const val RETENTION_STATUS = "Status"
    const val MONEY_RETENTIONS = "Requests to keep cash"
    const val OUTBOX_RETENTION = "Request to keep cash"

    fun retentionStatus(status: String): String = when (status) {
        "PENDING" -> "Waiting for approval"
        "APPROVED" -> "Approved"
        "REJECTED" -> "Rejected"
        else -> status.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    // --- Follow-up F2: overdue remittance -------------------------------------------------------------------------
    const val TITLE_REMITTANCE_OVERDUE = "Overdue remittance"
    const val OVERDUE_CUSTODIAN = "Cash held by"
    const val OVERDUE_NOT_REMITTED = "Not remitted"
    const val OVERDUE_DAY = "Day"
    const val OVERDUE_CUTOFF = "Cut-off"
    const val OVERDUE_FLAGGED = "Flagged"
    const val OVERDUE_HINT = "Remit this cash to the office as soon as you can."

    /** "07:00" (two-digit hour). */
    fun hour(h: Int): String = "${h.toString().padStart(2, '0')}:00"

    fun overdueLine(cutoffHour: Int, day: String): String = "Still held after the ${hour(cutoffHour)} cut-off on $day."

    // --- DEC-031 Phase 3: remittance details and holding allowance -----------------------------------------------
    const val REMIT_METHOD = "How was it handed over?"
    const val REMIT_ACCOUNT = "Paid into"
    const val REMIT_ACCOUNT_OPTIONAL = "Paid into (optional)"
    const val REMIT_ACCOUNT_NONE = "No account"
    const val REMIT_ACCOUNTS_EMPTY = "Your company's accounts for this currency appear here after a sync."
    const val REMIT_REFERENCE = "Transaction reference"
    const val REMIT_REFERENCE_OPTIONAL = "Reference (deposit slip, transaction no.) (optional)"
    const val REMIT_PHOTOS = "Deposit slip or payment confirmation"
    const val REMIT_PHOTOS_OPTIONAL = "Deposit slip or payment confirmation (optional)"
    const val REMIT_PHOTOS_FOOTER = "Stored encrypted on this phone and uploaded before the handover is sent."
    const val REMIT_PHOTOGRAPH = "Photograph the slip"
    const val REMIT_ADD_PHOTO = "Add another photo"
    const val REMIT_REMOVE_PHOTO = "Remove"
    const val OUTBOX_WAITING_PHOTOS = "Waiting for its photos to upload"

    fun remitMethod(method: com.asseta.core.domain.accountability.RemittanceMethod): String = when (method) {
        com.asseta.core.domain.accountability.RemittanceMethod.CASH_TO_OFFICE -> "Cash to the office"
        com.asseta.core.domain.accountability.RemittanceMethod.BANK_DEPOSIT -> "Bank deposit"
        com.asseta.core.domain.accountability.RemittanceMethod.MOBILE_MONEY -> "Mobile money"
    }

    const val OVERDUE_REASON = "Reason"
    const val OVERDUE_REASON_CUTOFF = "Not remitted by the daily cut-off"
    const val OVERDUE_REASON_HELD = "Held longer than allowed"
    const val OVERDUE_HELD_SINCE = "Held since"
    const val OVERDUE_ALLOWED = "Allowed"
    const val OVERDUE_HELD_LINE_SHORT = "Held longer than allowed."

    fun days(n: Int): String = if (n == 1) "1 day" else "$n days"

    fun overdueHeldLine(date: String, days: Int): String = "Held since $date, longer than the allowed ${days(days)}."

    /** Plain words for the server's conflict codes on accountability operations (null: show the server's message). */
    fun conflict(code: String?): String? = when (code) {
        "RETENTION_NOT_ALLOWED" -> "Your company does not allow keeping cash, so this request was not accepted."
        "DUPLICATE_RETENTION" -> "This request to keep cash was already sent."
        "ENGINE_HOURS_DISABLED" -> "Your company has switched off engine-hour controls, so this was not accepted."
        "CASH_CUSTODY_DISABLED" -> "Your company has switched off cash custody controls, so this was not accepted."
        "REMITTANCE_REFERENCE_REQUIRED" ->
            "Your company requires the transaction reference for bank and mobile-money remittances. Record the handover again with the reference."
        "REMITTANCE_EVIDENCE_REQUIRED" ->
            "Your company requires a photo of the deposit slip or payment confirmation. Record the handover again with a photo."
        "REMITTANCE_ACCOUNT_REQUIRED" ->
            "Your company requires the account the money was paid into. Record the handover again and choose the account."
        "DEPOSIT_ACCOUNT_INACTIVE" -> "The account you chose is no longer in use. Record the handover again with another account."
        "REMITTANCE_ACCOUNT_MISMATCH" -> "The account you chose does not match how the money was handed over. Record the handover again."
        "DEPOSIT_ACCOUNT_CURRENCY_MISMATCH" -> "The account you chose holds a different currency. Record the handover again with another account."
        else -> null
    }

    /** A colleague's name from the server, else from the saved cash holders, else the short id (DEC-030 G2). */
    fun colleague(name: String?, savedName: String?, id: String?): String? =
        com.asseta.core.domain.accountability.DisplayNames.of(name ?: savedName, id)
}
