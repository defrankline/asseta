package com.asseta.owner.ui.approvals

import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.owner.data.CreditSale
import com.asseta.owner.ui.common.Figures
import java.math.BigDecimal
import java.math.RoundingMode

/** The Approvals chips (design OwnerApprovals): All, then the three kinds the owner decides most. */
enum class ApprovalFilter(val label: String) {
    ALL("All"), MACHINE_REPORTS("Machine reports"), CREDIT("Credit"), EXPENSES("Expenses");

    /** Which kinds this chip shows: every kind under All. */
    fun shows(kind: ApprovalKind): Boolean = when (this) {
        ALL -> true
        MACHINE_REPORTS -> kind == ApprovalKind.MACHINE_REPORT
        CREDIT -> kind == ApprovalKind.CREDIT
        EXPENSES -> kind == ApprovalKind.EXPENSE
    }
}

/** What a waiting item is; OTHER = petty cash, payments, handovers, meter resets, exceptions, accountability decisions. */
enum class ApprovalKind { MACHINE_REPORT, CREDIT, EXPENSE, OTHER }

/** Waiting items per kind; the chips show "All 5", "Machine reports 2", ... and Home "5 waiting". */
data class ApprovalCounts(val reports: Int = 0, val credit: Int = 0, val expenses: Int = 0, val other: Int = 0) {
    val all: Int get() = reports + credit + expenses + other

    fun of(f: ApprovalFilter): Int = when (f) {
        ApprovalFilter.ALL -> all
        ApprovalFilter.MACHINE_REPORTS -> reports
        ApprovalFilter.CREDIT -> credit
        ApprovalFilter.EXPENSES -> expenses
    }

    /** "Machine reports 2". */
    fun chip(f: ApprovalFilter): String = "${f.label} ${of(f)}"

    /** Home tile badge: "5 waiting" (null when nothing waits). */
    val waiting: String? get() = all.takeIf { it > 0 }?.let { "$it waiting" }
}

/** Approvals wording added by ADR-008 (design OwnerApprovals; same as iOS). */
object ApprovalsTexts {
    const val CREDIT_KIND = "CREDIT SALE"
    const val EXPENSE_KIND = "EXPENSE"
    const val APPROVE_CREDIT = "Approve credit"
    const val REJECT = "Reject"
    const val RECEIPT_PHOTO = "receipt photo"
    const val EMPTY_TITLE = "Nothing waiting"
    const val EMPTY_MESSAGE = "Nothing here needs your decision."
    const val CREDIT_REASON_TITLE = "Approve credit"
    const val CREDIT_REASON_LABEL = "Reason (at least 3 characters)"
    const val CREDIT_REASON_DEFAULT = "Credit sale approved"
    const val TURN_DOWN_TITLE = "Reject this credit sale?"
    const val TURN_DOWN_TEXT = "This asks for the order to be cancelled. The customer's hours stay unusable meanwhile."
    const val TURN_DOWN_LABEL = "Reason (needed to reject)"
    const val CREDIT_APPROVED = "Credit approved. The customer can use these hours."
    const val CREDIT_TURNED_DOWN = "Cancellation requested for this order."
    const val OWN_SALE = "You recorded this sale, so someone else must approve its credit."
    const val CANCEL = "Cancel"

    /** "Hours approved on credit" etc.: refusals of a credit approval in plain words. */
    fun creditRefusal(code: String?, fallback: String): String = when (code) {
        "SEGREGATION_OF_DUTIES" -> "You recorded this sale, so you can't approve its credit. Someone else must."
        "NO_CREDIT_ARRANGEMENT" -> "This customer has no approved credit limit. Set one up on the web first."
        "CREDIT_LIMIT_EXCEEDED" -> "This would take the customer over their credit limit."
        "EXCEEDS_UNACTIVATED_HOURS" -> "Fewer hours are waiting than this; the list has been refreshed."
        "CREDIT_NOT_ALLOWED" -> "Credit is switched off for this company."
        "PURCHASE_CANCELLED" -> "This order was cancelled."
        "CANCELLATION_PENDING" -> "A cancellation is already waiting for this order."
        else -> fallback
    }
}

/** Credit sales: orders with a CREDIT part whose hours still wait to be made usable (pure, unit-tested). */
object CreditSales {
    /** Has a credit part and hours still waiting, not cancelled. */
    fun waiting(p: OwnerHoursPurchaseDto): Boolean =
        p.cancelledAt == null && Figures.dec(p.creditAmount).signum() > 0 && Figures.dec(p.totals.awaitingActivation).signum() > 0

    /**
     * Hours the credit part pays for: credit amount / the order's effective rate (rounded down to 0.01 h), never more
     * than the hours still waiting; the waiting hours when the rate is unknown.
     */
    fun creditHours(p: OwnerHoursPurchaseDto): BigDecimal {
        val waiting = Figures.dec(p.totals.awaitingActivation)
        val rate = Figures.dec(p.effectiveRate)
        if (rate.signum() <= 0) return waiting
        val hours = Figures.dec(p.creditAmount).divide(rate, 2, RoundingMode.DOWN)
        return hours.min(waiting).stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }
    }

    /** "Msasani Bay · 40 h on credit". */
    fun title(p: OwnerHoursPurchaseDto): String = "${p.customerName ?: p.purchaseNumber} · ${Figures.hours(creditHours(p))} on credit"

    /** "Invoice INV-0042 · TZS 3,800,000 · limit left 6.2M". */
    fun detail(s: CreditSale): String {
        val p = s.purchase
        val currency = p.currency ?: ""
        return listOfNotNull(
            p.creditInvoice?.let { "Invoice ${it.invoiceNumber}" },
            Figures.money(Figures.dec(p.creditAmount), currency).trim(),
            s.limitLeft?.let { "limit left ${Figures.compact(Figures.dec(it))}" },
        ).joinToString(" · ")
    }

    /** The person who recorded the sale may not approve its credit (the server refuses it too). */
    fun recordedBy(p: OwnerHoursPurchaseDto, me: String?): Boolean =
        me != null && p.createdBy != null && p.createdBy.equals(me, ignoreCase = true)

    /** The credit reason must be 3–1000 characters (contract). */
    fun reasonValid(reason: String): Boolean = reason.trim().length in 3..1000
}

/** Expense rows: "Hydraulic hose · TZS 185,000" over "receipt photo · Tabata Hydraulics" (pure). */
object ExpenseApprovals {
    fun title(a: ApprovalRequestDto, e: ExpenseDto?): String =
        "${e?.description ?: a.reason} · ${Figures.money(a.amount.value, a.currency)}"

    fun detail(a: ApprovalRequestDto, e: ExpenseDto?): String = listOfNotNull(
        ApprovalsTexts.RECEIPT_PHOTO.takeIf { e?.receiptAttachmentIds?.isNotEmpty() == true },
        e?.supplier?.takeIf { it.isNotBlank() },
        a.reason.takeIf { e == null || it != e.description },
    ).joinToString(" · ")
}
