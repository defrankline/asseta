package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.accountability.HoursPricing
import com.asseta.core.domain.accountability.HoursSalePrice
import com.asseta.core.domain.accountability.HoursSaleQuote
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.accountability.PaymentStatus
import com.asseta.core.domain.accountability.PaymentSummary
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
    const val HOURS_PRICE_LATER = "The price is set when the sale reaches the office."

    /** "Total: TZS 570,000 (6 h × 95,000/h)", with " less 10% discount" inside the brackets when the customer has one. */
    fun hoursTotal(q: HoursSaleQuote): String {
        val discount = if (q.discountPercent.signum() > 0) " less ${HoursPricing.figure(q.discountPercent)}% discount" else ""
        return "Total: ${money(q.amount, q)} (${HoursPricing.figure(q.hours)} h × ${HoursPricing.rate(q.hourlyRate)}/h$discount)"
    }

    private fun money(amount: java.math.BigDecimal, q: HoursSaleQuote) = HoursPricing.money(amount, q.currency, q.minorUnits)

    // Payment lines
    const val ADD_PAYMENT = "Add payment"
    const val REMOVE_PAYMENT = "Remove payment"
    const val METHOD = "Method"
    const val NONCASH_BY_OFFICE = "Bank and mobile-money payments are recorded by the office."
    const val PHOTOS_ONE_PAYMENT = "Payment photos go with a single payment."
    const val FULLY_PAID = "Fully paid"
    fun paymentNumber(n: Int) = "Payment $n"
    fun partPaid(balance: String) = "Part paid (balance $balance)"

    /** The lines under the payments: "Paid TZS 300,000 of TZS 570,000 · Balance TZS 270,000", then the status. */
    fun paymentSummary(s: PaymentSummary): List<String> {
        val q = s.quote
        val amounts = when {
            q != null -> "Paid ${money(s.paid, q)} of ${money(q.amount, q)} · Balance ${money(s.balance!!, q)}"
            s.paid.signum() > 0 -> "Paid ${HoursPricing.rate(s.paid)}"
            else -> null
        }
        val status = when (val st = s.status) {
            PaymentStatus.NotPaid -> NOT_PAID
            PaymentStatus.FullyPaid -> FULLY_PAID
            is PaymentStatus.PartPaid -> partPaid(money(st.balance, q!!))
            PaymentStatus.OverTotal -> com.asseta.core.domain.accountability.AccountabilityMessages.paymentsExceed(money(q!!.amount, q))
            PaymentStatus.NoTotal -> null
        }
        return listOfNotNull(amounts, status)
    }

    /** The sale on the sync status screen: "Hours sale · Cash 300,000 + Bank 270,000" (or "· Not paid yet"). */
    fun outboxHoursSale(payload: kotlinx.serialization.json.JsonObject?): String {
        if (payload == null) return OUTBOX_HOURS_SALE
        val parts = (payload["payments"] as? kotlinx.serialization.json.JsonArray)?.mapNotNull { it as? kotlinx.serialization.json.JsonObject }
            ?: listOfNotNull(payload["payment"] as? kotlinx.serialization.json.JsonObject)
        if (parts.isEmpty()) return "$OUTBOX_HOURS_SALE · $NOT_PAID"
        return "$OUTBOX_HOURS_SALE · " + parts.joinToString(" + ") { p ->
            fun text(key: String) = (p[key] as? kotlinx.serialization.json.JsonPrimitive)?.content
            val method = PaymentMethod.entries.firstOrNull { it.wire == text("method") }?.let(::method) ?: text("method").orEmpty()
            method + (text("amount")?.toBigDecimalOrNull()?.let { " " + HoursPricing.rate(it) } ?: "")
        }
    }

    /** The line under Hours: the total, the "priced at the office" notice, or nothing yet. */
    fun hoursPrice(price: HoursSalePrice): String? = when (price) {
        HoursSalePrice.Hidden -> null
        HoursSalePrice.Unpriced -> HOURS_PRICE_LATER
        is HoursSalePrice.Priced -> hoursTotal(price.quote)
    }
    const val SECTION_PAYMENT = "Payment"
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
    /** [hours] is shown in the phone's number format, 0–2 decimals ("12", "1,234.5"; never "12.0000"). */
    fun purchaseOption(number: String, hours: String) = "$number · ${hoursNumber(hours)} h left"
    fun hoursInUse(hours: String) = "${hoursNumber(hours)} h in use by running jobs"

    /** An hours figure as every customer-hours screen shows it (same as iOS). */
    fun hoursNumber(raw: String): String = com.asseta.core.domain.owner.OwnerFormat.hoursNumber(raw)

    /** Picker row: "{purchase} · {left} h left[ · {n} h in use by running jobs]" (provisional already out of left). */
    fun purchaseOption(number: String, hours: String, provisional: String?): String {
        val inUse = provisional?.toBigDecimalOrNull()?.takeIf { it.signum() > 0 }
        return purchaseOption(number, hours) + (inUse?.let { " · " + hoursInUse(it.toPlainString()) } ?: "")
    }
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

    // DEC-032 Phase 3 (docs/requirements/accountability-mobile-strings.md).
    const val COLLECTION_LINK = "Pays for"
    const val COLLECTION_LINK_OPTIONAL = "Pays for (optional)"
    const val COLLECTION_LINK_NONE = "Not linked"
    const val COLLECTION_LINK_EMPTY = "No open purchases for this customer on this phone."
    const val COLLECTION_LINK_EMPTY_ALL = "No open purchases or invoices for this customer on this phone."
    const val COLLECTION_INVOICE_FOOTER = "The cash pays this invoice up to what it still owes; anything above stays as customer credit."
    const val COLLECTION_LINK_REQUIRED = "Your company requires every collection to name its purchase or invoice."
    const val COLLECTION_LINK_FOOTER = "The cash pays this purchase up to what it still owes; anything above stays as customer credit."
    const val HANDOVER_PARTIAL_TITLE = "Part of your cash stays with you"
    const val HANDOVER_PARTIAL_FOOTER_OTHER = "If this is less than this person holds, your company requires the reason."
    const val HANDOVER_PARTIAL_REASON = "Why part of the cash stays (required)"
    const val HANDOVER_PARTIAL_REASON_OPTIONAL = "Why part of the cash stays (optional)"
    const val HANDOVER_PARTIAL_CATEGORY = "Reason category (optional)"
    const val HANDOVER_PARTIAL_CATEGORY_NONE = "No category"
    const val HANDOVER_PARTIAL_ERROR = "Enter why part of the cash stays with you (at least 3 characters)."
    const val TRANSFER_EVIDENCE_TITLE = "Evidence photos"
    const val TRANSFER_EVIDENCE_TITLE_REQUIRED = "Evidence photos (required)"
    const val TRANSFER_EVIDENCE_FOOTER = "Photographs are kept with the request and sent when there is a connection."
    const val TRANSFER_EVIDENCE_REQUIRED = "Photograph the evidence for this transfer."
    const val TRANSFER_PHOTOGRAPH = "Photograph evidence"
    const val TRANSFER_ADD_PHOTO = "Add another photo"
    const val TRANSFER_REMOVE_PHOTO = "Remove photo"
    const val MONEY_COLLECTION_NUMBER = "Collection number"
    const val MONEY_REMITTANCE_NUMBER = "Remittance number"
    const val RETENTION_NUMBER = "Number"

    fun handoverPartialFooter(balance: String, currency: String): String =
        "$balance $currency is your cash. Your company requires the full balance to be remitted, so say why part of it stays with you."

    /** Plain words for the server's conflict codes on accountability operations (null: show the server's message). */
    fun conflict(code: String?): String? = when (code) {
        "COLLECTION_LINK_REQUIRED" -> "Your company requires every collection to name its purchase or invoice. Record it again and choose one."
        "PARTIAL_REMITTANCE_REASON_REQUIRED" -> "Part of this cash is still with you and your company requires the reason. Record the handover again with the reason."
        "EVIDENCE_REQUIRED" -> "Your company requires evidence for this. Record it again with a photo."
        "PURCHASE_NOT_FOUND" -> "The purchase you chose is no longer on record. Record it again and choose another."
        "PURCHASE_CANCELLED" -> "The purchase you chose is cancelled. Record it again and choose another."
        "OVER_ALLOCATION" -> "This is more than the purchase or invoice still owes. Record it again with the right amount."
        "ALLOCATION_MISMATCH" -> "What you chose is for another customer or currency. Record it again and choose another."
        "INVOICE_NOT_OPEN" -> "This invoice is no longer open. Record it again and choose another."
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
        else -> DailyReportTexts.conflict(code) ?: SiteCheckinTexts.conflict(code)
    }

    /** A colleague's name from the server, else from the saved cash holders, else the short id (DEC-030 G2). */
    fun colleague(name: String?, savedName: String?, id: String?): String? =
        com.asseta.core.domain.accountability.DisplayNames.of(name ?: savedName, id)
}
