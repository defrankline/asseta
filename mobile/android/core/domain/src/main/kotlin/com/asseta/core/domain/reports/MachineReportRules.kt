package com.asseta.core.domain.reports

import com.asseta.core.domain.finance.FormCheck
import java.math.BigDecimal
import java.math.RoundingMode

/*
 * ADR-008 machine reports, checked on the phone before queueing (the server is authoritative): the hours between the
 * previous reading and the new one are split across customers (from hours they bought) and non-productive reasons;
 * the lines must add up to the difference exactly. Same rules and wording as iOS `MachineReportRules`.
 */

/** One line of the split as typed. */
sealed interface ReportLineDraft {
    val hoursText: String

    data class Customer(val customerId: String, val customerName: String, override val hoursText: String) : ReportLineDraft

    data class NonProductive(val reasonId: String, val reasonName: String, override val hoursText: String, val note: String) : ReportLineDraft
}

/** A checked line. */
sealed interface ReportLine {
    val hours: BigDecimal

    data class Customer(val customerId: String, override val hours: BigDecimal) : ReportLine

    data class NonProductive(val reasonId: String, override val hours: BigDecimal, val note: String) : ReportLine
}

/** Where a machine stands for its next report (Dashboard, step 1 and the Home badge). */
enum class ReportState {
    /** No starting reading yet: the first report only records the reading (the opening report). */
    OPENING,

    /** A report waits for the owner or manager (on the server, or still on this phone). */
    AWAITING_APPROVAL,

    /** The last report was rejected: a corrected split on the same reading is needed. */
    REJECTED,

    /** No report for the company's reminder days (or never). */
    DUE,

    UP_TO_DATE,
    ;

    /** Counts towards "Hours to report" and the "n due" badge. */
    val needsReport: Boolean get() = this == OPENING || this == REJECTED || this == DUE
}

object MachineReportRules {
    const val MAX_NOTE = 1000
    const val MAX_LINES = 50

    /** Hours as typed in steps of the machine's meter precision ([decimals] places), more than 0; else null. */
    fun hours(text: String, decimals: Int): BigDecimal? {
        val t = text.trim().replace(',', '.')
        if (!Regex("^\\d+(\\.\\d+)?$").matches(t)) return null
        val v = BigDecimal(t).stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }
        if (v.signum() <= 0 || v.scale() > decimals.coerceAtLeast(0)) return null
        return v
    }

    /** A meter reading as typed (0 or more, the meter's precision), else null. */
    fun reading(text: String, decimals: Int): BigDecimal? {
        val t = text.trim().replace(',', '.')
        if (!Regex("^\\d+(\\.\\d+)?$").matches(t)) return null
        val v = BigDecimal(t).stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }
        return v.takeIf { it.scale() <= decimals.coerceAtLeast(0) }
    }

    /** Hours to account for: new − previous; null when there is no previous reading (an opening report). */
    fun difference(previous: BigDecimal?, reading: BigDecimal): BigDecimal? = previous?.let { reading - it }

    /** Why step 1 cannot go on, or null: the reading must be above the previous one (equal = nothing to report). */
    fun readingProblem(previous: BigDecimal?, reading: BigDecimal?): String? = when {
        reading == null -> MachineReportMessages.READING
        previous == null -> null
        reading < previous -> MachineReportMessages.READING_LOWER
        reading.compareTo(previous) == 0 -> MachineReportMessages.NOTHING_TO_REPORT
        else -> null
    }

    /** The lines' valid hours added up (a line without valid hours counts as nothing yet). */
    fun accounted(lines: List<ReportLineDraft>, decimals: Int): BigDecimal =
        lines.fold(BigDecimal.ZERO) { sum, l -> sum + (hours(l.hoursText, decimals) ?: BigDecimal.ZERO) }

    /** Hours still to account for (negative when the lines are over the difference). */
    fun left(difference: BigDecimal, lines: List<ReportLineDraft>, decimals: Int): BigDecimal = difference - accounted(lines, decimals)

    /** Share of the difference accounted for, 0..1, for the progress bar. */
    fun progress(difference: BigDecimal, lines: List<ReportLineDraft>, decimals: Int): Float {
        if (difference.signum() <= 0) return 0f
        return accounted(lines, decimals).divide(difference, 4, RoundingMode.HALF_UP).toFloat().coerceIn(0f, 1f)
    }

    /** A customer's hours left after this report ([available] − the hours given on its line). */
    fun afterThis(available: BigDecimal, line: ReportLineDraft.Customer, decimals: Int): BigDecimal =
        available - (hours(line.hoursText, decimals) ?: BigDecimal.ZERO)

    /**
     * The split: every line has hours > 0 in the meter's steps; a customer appears once and gets no more than its
     * [available] hours; a non-productive line has a note; and the lines add up to [difference] exactly.
     */
    fun check(difference: BigDecimal, lines: List<ReportLineDraft>, available: Map<String, BigDecimal>, decimals: Int): FormCheck<List<ReportLine>> {
        val m = linkedSetOf<String>()
        if (lines.isEmpty()) m += MachineReportMessages.NO_LINES
        if (lines.size > MAX_LINES) m += MachineReportMessages.TOO_MANY_LINES
        val customers = lines.filterIsInstance<ReportLineDraft.Customer>()
        if (customers.groupBy { it.customerId }.any { it.value.size > 1 }) m += MachineReportMessages.CUSTOMER_TWICE
        val checked = lines.mapNotNull { line ->
            val h = hours(line.hoursText, decimals)
            if (h == null) m += MachineReportMessages.hoursFormat(decimals)
            when (line) {
                is ReportLineDraft.Customer -> {
                    val cap = available[line.customerId] ?: BigDecimal.ZERO
                    if (h != null && h > cap) m += MachineReportMessages.overAvailable(line.customerName, cap)
                    h?.let { ReportLine.Customer(line.customerId, it) }
                }
                is ReportLineDraft.NonProductive -> {
                    val note = line.note.trim()
                    if (note.isEmpty()) m += MachineReportMessages.noteNeeded(line.reasonName)
                    h?.let { ReportLine.NonProductive(line.reasonId, it, note.take(MAX_NOTE)) }
                }
            }
        }
        val left = left(difference, lines, decimals)
        if (left.signum() > 0) m += MachineReportMessages.leftToAccount(left)
        if (left.signum() < 0) m += MachineReportMessages.overDifference(left.negate())
        return if (m.isEmpty()) FormCheck.Valid(checked) else FormCheck.Invalid(m.toList())
    }

    /** Review is offered only when the split is complete and valid (sum == difference). */
    fun canReview(difference: BigDecimal, lines: List<ReportLineDraft>, available: Map<String, BigDecimal>, decimals: Int): Boolean =
        check(difference, lines, available, decimals) is FormCheck.Valid

    /**
     * The machine's state. [previousReading] null = no starting reading (opening report). [pendingOnServer] /
     * [pendingOnPhone]: a report waits for approval; [rejected]: the last report was rejected; [daysSinceReport] null =
     * never reported; [reminderDays] null = the company does not remind (then only "never reported" is due).
     */
    fun state(
        previousReading: String?,
        pendingOnServer: Boolean,
        pendingOnPhone: Boolean,
        rejected: Boolean,
        daysSinceReport: Int?,
        reminderDays: Int?,
    ): ReportState = when {
        pendingOnServer || pendingOnPhone -> ReportState.AWAITING_APPROVAL
        rejected -> ReportState.REJECTED
        previousReading == null -> ReportState.OPENING
        daysSinceReport == null -> ReportState.DUE
        reminderDays != null && daysSinceReport >= reminderDays -> ReportState.DUE
        else -> ReportState.UP_TO_DATE
    }

    /** "1,210.0" with the meter's decimals. */
    fun formatReading(value: BigDecimal, decimals: Int): String {
        val d = decimals.coerceIn(0, 4)
        return java.text.DecimalFormat("#,##0" + (if (d > 0) "." + "0".repeat(d) else ""), java.text.DecimalFormatSymbols.getInstance(java.util.Locale.US))
            .format(value.setScale(d, RoundingMode.HALF_UP))
    }

    /** Hours without trailing zeros, grouped ("300", "12.5", "1,240"). */
    fun formatHours(value: BigDecimal): String =
        java.text.DecimalFormat("#,##0.##", java.text.DecimalFormatSymbols.getInstance(java.util.Locale.US)).format(value)
}

/** Approval of a report is by permission, never by role, and never by the person who submitted it. */
object MachineReportApproval {
    const val APPROVE = "tenant.machine_report.approve"

    fun canDecide(permissions: Set<String>, submittedBy: String?, me: String?): Boolean =
        APPROVE in permissions && (submittedBy == null || me == null || !submittedBy.equals(me, ignoreCase = true))

    /** Rejecting needs a reason. */
    fun rejectReasonValid(reason: String): Boolean = reason.trim().isNotEmpty()
}

/** Validation wording shared with iOS (docs/requirements/accountability-mobile-strings.md, "ADR-008 apps"). */
object MachineReportMessages {
    const val READING = "Enter the new reading."
    const val READING_LOWER = "The new reading is below the last reading. Check the number, or ask the office about a meter reset."
    const val NOTHING_TO_REPORT = "No difference since the last reading? Nothing to report."
    const val NO_LINES = "Add a customer or a non-productive line."
    const val TOO_MANY_LINES = "At most 50 lines per report."
    const val CUSTOMER_TWICE = "Each customer can appear only once."

    fun hoursFormat(decimals: Int) = if (decimals <= 0) "Enter whole hours (more than 0)." else "Enter the hours (more than 0, at most $decimals decimal${if (decimals == 1) "" else "s"})."
    fun overAvailable(customer: String, available: BigDecimal) = "$customer has only ${MachineReportRules.formatHours(available)} h available."
    fun noteNeeded(reason: String) = "Say what happened for “$reason”."
    fun leftToAccount(left: BigDecimal) = "${MachineReportRules.formatHours(left)} h still to account for"
    fun overDifference(over: BigDecimal) = "${MachineReportRules.formatHours(over)} h more than the meter shows"
}
