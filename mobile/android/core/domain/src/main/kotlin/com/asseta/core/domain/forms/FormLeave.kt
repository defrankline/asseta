package com.asseta.core.domain.forms

import com.asseta.core.domain.accountability.HoursSaleDraft
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.reports.ReportLineDraft

/** What leaving a form (system Back, the bar's Back or Cancel, iOS swipe-back) does. */
enum class LeaveAction {
    /** Nothing entered, or already saved: leave. */
    LEAVE,

    /** Work was entered: ask "Discard …?" (Keep editing / Discard) before it is thrown away. */
    ASK,

    /** A save is under way: stay until it is queued. */
    STAY,
}

/**
 * Leaving a machine report or a sale with entered data never throws the work away silently (same rules as iOS
 * `FormLeave`).
 */
object FormLeave {
    const val REPORT_TITLE = "Discard this report?"
    const val REPORT_BODY = "The photo and readings you entered will be lost."
    const val SALE_TITLE = "Discard this sale?"
    const val SALE_BODY = "The customer, hours and payments you entered will be lost."
    const val KEEP_EDITING = "Keep editing"
    const val DISCARD = "Discard"

    fun decide(saving: Boolean, saved: Boolean, entered: Boolean): LeaveAction = when {
        saved -> LeaveAction.LEAVE
        saving -> LeaveAction.STAY
        entered -> LeaveAction.ASK
        else -> LeaveAction.LEAVE
    }

    /**
     * A machine report holds entered data once it has a photo, a typed reading, a note, or lines other than those it
     * opened with (a correction opens with the rejected report's lines and reading: those are not new input, so pass
     * an empty [typedReading] for a correction).
     */
    fun reportEntered(
        hasPhoto: Boolean,
        typedReading: String,
        lines: List<ReportLineDraft>,
        startingLines: List<ReportLineDraft>,
        note: String,
    ): Boolean = hasPhoto || typedReading.isNotBlank() || note.isNotBlank() || lines != startingLines

    /**
     * A sale holds entered data once a customer, walk-in name or phone, machine, hours, note, payment photo or cash
     * holder is set, or the payment lines differ from the opening one (one Cash line following the total, nothing
     * typed).
     */
    fun saleEntered(draft: HoursSaleDraft, photoCount: Int, holderChosen: Boolean): Boolean =
        draft.customerId != null || draft.walkInName.isNotBlank() || draft.walkInPhone.isNotBlank() ||
            draft.machineId != null || draft.hoursText.isNotBlank() || draft.note.isNotBlank() || photoCount > 0 ||
            holderChosen || draft.payments.size != 1 ||
            draft.payments.any { it.method != PaymentMethod.CASH || !it.followsTotal || it.reference.isNotBlank() }
}
