package com.asseta.supervisor.ui.pettycash

import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.model.sync.PettyCashAdvanceDto
import com.asseta.core.model.sync.PettyCashFundDto
import com.asseta.core.model.sync.PettyCashHolderChangeDto
import com.asseta.core.model.sync.PettyCashMovementDto
import com.asseta.core.model.sync.PettyCashOps
import com.asseta.core.sync.data.PettyCashRecord
import com.asseta.supervisor.ui.InboxTexts

/**
 * Wording of the field petty cash screens (DEC-033), word for word the iOS `PettyCashTexts`
 * (docs/requirements/accountability-mobile-strings.md, "DEC-033 — petty cash funds").
 */
object PettyCashTexts {
    const val SECTION = "Petty cash"
    const val ROW = "My petty cash"
    fun rowWaiting(n: Int) = "$n waiting for you"
    const val TITLE = "My petty cash"
    const val EMPTY_TITLE = "No petty cash fund"
    const val EMPTY_MESSAGE = "Petty cash funds you hold appear here after a sync."
    fun fundHeader(f: PettyCashFundDto) = "${f.code} · ${f.name}"
    const val BALANCE = "Balance"
    const val AVAILABLE = "Available to spend"
    const val PENDING_SPENDING = "Expenses awaiting approval"
    const val AWAITING_ACK = "Money on its way to you"
    const val RETURNS_CLAIMED = "Returns awaiting confirmation"
    const val LIMIT = "Approved limit"
    const val LOW = "Below the low-balance level"
    const val LAST_COUNT = "Last count"
    const val NOT_COUNTED = "Not counted yet"
    const val NEXT_COUNT = "Next count due"
    fun asOf(date: String) = "As of $date. Figures from the last sync."
    const val ACTION_TOP_UP = "Request a top-up"
    const val ACTION_RETURN = "Return money to the office"
    const val ACTION_COUNT = "Record a count"
    const val ACTION_GIVE_ADVANCE = "Give an advance"
    const val WAITING = "Waiting for you"
    const val SOMEONE = "someone"
    const val ADVANCES = "Advances"
    const val ADVANCE_OVERDUE = "Overdue"
    const val ADVANCE_TO_ME = "Given to you"
    fun advanceFromMe(name: String) = "Given to $name"
    const val ON_PHONE = "Recorded on this phone"

    const val OUTBOX_ACK = "Petty cash acknowledgement"
    const val OUTBOX_TOP_UP = "Petty cash top-up request"
    const val OUTBOX_RETURN = "Petty cash return"
    const val OUTBOX_COUNT = "Petty cash count"
    const val OUTBOX_HOLDER_CHANGE = "Petty cash fund take-over"
    const val OUTBOX_ADVANCE = "Petty cash advance cleared"
    const val OUTBOX_GIVE_ADVANCE = "Petty cash advance given"

    const val TITLE_ACK = "Acknowledge petty cash"
    const val TITLE_TOP_UP = "Request a top-up"
    const val TITLE_RETURN = "Return money"
    const val TITLE_COUNT = "Record a count"
    const val TITLE_HOLDER_CHANGE = "Take over a fund"
    const val TITLE_ADVANCE = "Clear an advance"
    const val TITLE_GIVE_ADVANCE = "Give an advance"
    const val GIVE_RECIPIENT = "Given to"
    const val GIVE_RECIPIENT_EMPTY = "No colleague is saved on this phone yet. Connect, then open this form again."
    const val GIVE_AMOUNT = "Amount"
    const val GIVE_PURPOSE = "Purpose"
    const val GIVE_FOOTER = "The advance leaves the fund now. The colleague clears it with receipts and the change."
    const val GIVE_SAVE = "Give advance"
    const val NOT_FOUND = "This is no longer waiting on this phone. Pull to sync."
    const val UNAVAILABLE = "Petty cash is not available on this phone. Sync, or ask your office."
    const val FUND = "Fund"
    const val NOTE = "Note (optional)"

    const val ACK_FUNDING = "Funding from the office"
    const val ACK_TOP_UP = "Top-up from the office"
    const val ACK_NUMBER = "Number"
    const val ACK_ISSUED = "Issued"
    const val ACK_ISSUED_AT = "Issued at"
    const val ACK_ISSUED_BY = "Issued by"
    const val ACK_REFERENCE = "Reference"
    const val ACK_AMOUNT = "Amount received"
    const val ACK_FOOTER = "Count the money before you acknowledge. A different amount is recorded as a difference for the office to review."
    const val ACKNOWLEDGE = "Acknowledge"
    const val DISPUTE = "Dispute"
    const val DISPUTE_REASON = "To dispute, write in the note why."
    const val ACK_WAITING = "You already answered on this phone. It is sent when the phone syncs."

    const val TOP_UP_AMOUNT = "Amount (optional)"
    const val TOP_UP_AMOUNT_FOOTER = "Leave it empty to ask for the approved spending since the last top-up."
    const val TOP_UP_ABOVE_REASON = "Reason for going above the limit"
    fun topUpAboveFooter(amount: String) = "This is more than brings the fund to its limit ($amount); say why."
    const val TOP_UP_FOOTER = "Someone else approves the top-up. The money counts in your fund only after you acknowledge it."
    const val TOP_UP_SEND = "Send request"

    const val RETURN_AMOUNT = "Amount returned"
    const val RETURN_METHOD = "How"
    fun method(m: RemittanceMethod): String = when (m) {
        RemittanceMethod.CASH_TO_OFFICE -> "Cash to office"
        RemittanceMethod.BANK_DEPOSIT -> "Bank deposit"
        RemittanceMethod.MOBILE_MONEY -> "Mobile money"
    }
    const val RETURN_ACCOUNT = "Deposit account (optional)"
    const val RETURN_NO_ACCOUNT = "No account"
    const val RETURN_REFERENCE = "Reference (optional)"
    const val RETURN_FOOTER = "The fund goes down only when the office confirms what it received."
    const val RETURN_EVIDENCE_REQUIRED = "Your company requires a photo of the slip or the cash."

    const val COUNT_AMOUNT = "Cash counted"
    const val COUNT_FOOTER = "Count every note and coin in the fund. A difference from the expected amount goes to the office to review."
    const val WITNESS = "Witness"
    const val WITNESS_SEARCH = "Search a colleague by name"
    const val WITNESS_NONE = "No witness"
    const val WITNESS_FOOTER = "Your company asks for a witness: someone else who can count petty cash watches the count."
    const val WITNESS_OFFLINE = "Connect to choose a witness."
    const val WITNESS_NO_RESULTS = "No one found."
    const val NO_WITNESS = "Without a witness this count is recorded as counted by you alone."
    const val WITNESS_EMPTY = "No colleague who can witness a count is on this phone. Sync first."
    const val RECORDED_SELF = "Recorded as counted by you alone."
    const val WITNESS_DROPPED = "The witness could no longer witness counts, so this count was recorded without a witness."

    /** The line under a synced count: the witness was dropped, else a self-count; null otherwise. */
    fun countOutcome(r: PettyCashRecord): String? = when {
        r.witnessDropped -> WITNESS_DROPPED
        r.selfCount -> RECORDED_SELF
        else -> null
    }

    const val HOLDER_FROM = "From"
    const val HOLDER_REQUESTED_BY = "Requested by"
    const val HOLDER_REQUESTED_AT = "Requested"
    fun holderFooter(name: String) = "Until you accept, $name stays accountable for the fund. Count the cash before you accept."
    const val HOLDER_ACCEPT = "Take over the fund"
    const val HOLDER_DECLINE = "Decline"
    const val HOLDER_DECLINE_REASON = "To decline, write in the note why."

    const val ADVANCE_RECIPIENT = "Given to"
    const val ADVANCE_AMOUNT = "Advance"
    const val ADVANCE_PURPOSE = "Purpose"
    const val ADVANCE_APPROVED = "Approved spending"
    const val ADVANCE_PENDING = "Spending awaiting approval"
    const val ADVANCE_REMAINING = "Remaining"
    const val ADVANCE_DUE = "Due"
    const val ADVANCE_CHANGE = "Change handed back"
    const val ADVANCE_FOOTER = "Count the change you take back. A difference is recorded for the office to review."
    const val ADVANCE_PENDING_WARNING = "Expenses of this advance are still waiting for approval. It can be cleared once they are decided."
    const val ADVANCE_CLEAR = "Clear advance"

    const val EXPENSE_SECTION = "Petty cash fund"
    const val EXPENSE_FUND = "Fund"
    const val EXPENSE_FUND_EMPTY = "No petty cash fund on this phone. Sync first."
    fun expenseFundOption(amount: String) = "Available $amount"
    const val EXPENSE_ADVANCE = "Advance (optional)"
    const val EXPENSE_ADVANCE_REQUIRED_LABEL = "Advance"
    const val EXPENSE_NO_ADVANCE = "Not from an advance"
    fun expenseAdvanceOption(amount: String) = "Remaining $amount"
    fun expenseFooter(amount: String) = "Available to spend: $amount. The currency is the fund's."

    fun money(amount: String?, currency: String): String = InboxTexts.money(amount ?: "0", currency)

    fun waitingMovement(m: PettyCashMovementDto): String =
        (if (m.kind == PettyCashOps.FUNDING) "Funding" else "Top-up") + " ${m.number} · ${money(m.amount, m.currency)}"

    fun waitingHolderChange(c: PettyCashHolderChangeDto): String =
        "Take over ${c.fundName ?: FUND.lowercase()} from ${c.fromStaffName?.takeIf { it.isNotBlank() } ?: SOMEONE}"

    fun advanceRow(a: PettyCashAdvanceDto) = "${a.number} · ${money(a.amount, a.currency)}"
    fun advanceDetail(a: PettyCashAdvanceDto, due: String) = "Remaining ${money(a.remaining, a.currency)} · due $due"

    /** "Given to you" for my own advances, else who received it. */
    fun advanceWho(a: PettyCashAdvanceDto, me: String?) =
        if (a.recipientStaffId == me) ADVANCE_TO_ME else advanceFromMe(a.recipientStaffName?.takeIf { it.isNotBlank() } ?: SOMEONE)

    fun outboxTitle(opType: String): String? = when (opType) {
        PettyCashOps.ACKNOWLEDGEMENT -> OUTBOX_ACK
        PettyCashOps.TOP_UP_REQUEST -> OUTBOX_TOP_UP
        PettyCashOps.RETURN -> OUTBOX_RETURN
        PettyCashOps.COUNT -> OUTBOX_COUNT
        PettyCashOps.HOLDER_CHANGE_ACKNOWLEDGEMENT -> OUTBOX_HOLDER_CHANGE
        PettyCashOps.ADVANCE_CLEARANCE -> OUTBOX_ADVANCE
        PettyCashOps.ADVANCE -> OUTBOX_GIVE_ADVANCE
        else -> null
    }

    /** A record line: "Petty cash return · 50000 TZS". */
    fun recordTitle(r: PettyCashRecord, currency: String?): String =
        (outboxTitle(r.opType) ?: r.opType) + (r.amount?.let { " · " + InboxTexts.money(it, currency) } ?: "")

    /** Plain words for the petty cash conflicts; null keeps the server's message. */
    fun conflict(code: String?): String? = when (code) {
        "PETTY_CASH_INSUFFICIENT" -> "The fund did not have enough available. Check the fund and record the expense again if needed."
        "PETTY_CASH_FUND_INACTIVE" -> "This petty cash fund is no longer active."
        "PETTY_CASH_DISABLED" -> "Petty cash is switched off for your company."
        "PETTY_CASH_ALREADY_ACKNOWLEDGED" -> "This was already answered."
        "PETTY_CASH_ALREADY_DECIDED" -> "This was already decided."
        "PETTY_CASH_NOTHING_TO_TOP_UP" -> "Nothing to top up: no approved spending since the last top-up, or the fund is at its limit."
        "PETTY_CASH_ABOVE_CAP_REASON_REQUIRED" -> "The amount is above the fund's limit; send the request again with a reason."
        "PETTY_CASH_ADVANCE_EXPENSES_PENDING" -> "Expenses of this advance are still waiting for approval."
        "PETTY_CASH_ADVANCE_CLEARED" -> "This advance is already cleared."
        "PETTY_CASH_ADVANCES_DISABLED" -> "Advances are switched off for your company."
        "PETTY_CASH_ADVANCE_TO_HOLDER" -> "An advance goes to someone other than the fund's holder."
        else -> null
    }

    /** Non-zero amount text (hide figures that are 0). */
    fun nonZero(amount: String?): Boolean = amount?.toBigDecimalOrNull()?.signum()?.let { it != 0 } == true
}
