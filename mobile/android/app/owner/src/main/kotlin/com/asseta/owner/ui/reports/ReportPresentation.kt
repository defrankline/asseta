package com.asseta.owner.ui.reports

import com.asseta.core.domain.reports.MachineReportApproval
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportLineDto
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.model.sync.TrackerCheckDto
import com.asseta.owner.ui.common.Figures
import java.math.BigDecimal
import java.time.ZoneId

/** Machine-report wording of the Owner app (designs OwnerApprovals / OwnerReportApproval / OwnerHome; same as iOS). */
object ReportTexts {
    const val DETAIL_TITLE = "Approve a machine report"
    const val KIND = "MACHINE REPORT"
    const val CUSTOMERS = "CUSTOMERS"
    const val NON_PRODUCTIVE = "NON-PRODUCTIVE"
    const val REASON_LABEL = "Reason (needed to reject)"
    const val REASON_PLACEHOLDER = "e.g. Idle hours too high, explain"
    const val NOTE_LABEL = "Supervisor's note"
    const val APPROVE = "Approve"
    const val REJECT = "Reject"
    const val CONFIRM_REJECT = "Reject this report?"
    const val CONFIRM_REJECT_TEXT = "The supervisor is told your reason and corrects the split on the same reading."
    const val APPROVED = "Report approved. The customers' hours are used."
    const val REJECTED = "Report rejected. The supervisor will correct it."
    const val OWN_REPORT = "You submitted this report, so someone else must approve or reject it."
    const val NO_PERMISSION = "Only people allowed to approve machine reports can decide it."
    const val VIEW_PHOTO = "meter photo"
    const val NO_TRACKER = "No tracker data for this period."
    const val REVIEW = "Review"
    const val OVERDUE = "Overdue"
    const val STATUS_APPROVED = "Approved"
    const val STATUS_REJECTED = "Rejected"
    const val STATUS_WAITING = "Awaiting approval"
    const val NOT_FOUND_TITLE = "Report not found"
    const val NOT_FOUND_MESSAGE = "It may have been removed, or you can no longer see it."

    /** Plain sentences for the server's refusal codes on approve / reject (else the server's message). */
    fun refusal(code: String?, fallback: String): String = when (code) {
        "SEGREGATION_OF_DUTIES" -> "You submitted this report, so you can't decide it. Someone else with approval rights must."
        "REPORT_NOT_PENDING" -> "This report was already decided by someone else. It has been refreshed."
        "REPORT_READINGS_CHANGED" -> "The machine's previous reading changed after this report was sent (a baseline or meter reset). Reject it so the supervisor can send it again."
        "HOURS_NOT_AVAILABLE" -> "A customer no longer has these hours (cancelled or expired). Reject the report so the supervisor can correct it."
        "REPORT_NOT_FOUND" -> "This report no longer exists."
        else -> fallback
    }
}

/** Pure presentation of machine reports (unit-tested). */
object ReportPresentation {
    fun machine(r: MachineReportDto): String = r.machineCode ?: r.machineName ?: r.reportNumber

    fun customerLines(r: MachineReportDto): List<MachineReportLineDto> = r.lines.filter { it.kind == MachineReportLineDto.CUSTOMER }

    fun nonProductiveLines(r: MachineReportDto): List<MachineReportLineDto> = r.lines.filter { it.kind == MachineReportLineDto.NON_PRODUCTIVE }

    /** "EX-01 · 300 h · Daudi Mollel". */
    fun rowTitle(r: MachineReportDto): String =
        listOfNotNull(machine(r), Figures.hours(Figures.dec(r.hours)), r.submittedByName?.takeIf { it.isNotBlank() }).joinToString(" · ")

    /** Short reason ("transit", "breakdown"): the code in words, else the name. */
    fun reasonShort(l: MachineReportLineDto): String =
        l.reasonCode?.lowercase()?.replace('_', ' ') ?: l.reasonName?.lowercase() ?: "non-productive"

    /**
     * "220 h to 2 customers · 80 h non-productive"; one customer is named ("38 h Mji Mpya Housing"), one reason too
     * ("4 h transit"). Without lines (a list row may carry none): the totals.
     */
    fun split(r: MachineReportDto): String {
        val customers = customerLines(r)
        val reasons = nonProductiveLines(r)
        val customerHours = Figures.dec(r.customerHours)
        val npHours = Figures.dec(r.nonProductiveHours)
        val parts = mutableListOf<String>()
        if (customerHours.signum() > 0) {
            parts += when (customers.size) {
                1 -> "${Figures.hours(customerHours)} ${customers[0].customerName ?: "a customer"}"
                0 -> "${Figures.hours(customerHours)} to customers"
                else -> "${Figures.hours(customerHours)} to ${customers.size} customers"
            }
        }
        if (npHours.signum() > 0) {
            parts += if (reasons.size == 1) "${Figures.hours(npHours)} ${reasonShort(reasons[0])}" else "${Figures.hours(npHours)} non-productive"
        }
        return parts.joinToString(" · ").ifEmpty { Figures.hours(Figures.dec(r.hours)) }
    }

    /** "1,210 → 1,510 h". */
    fun readings(r: MachineReportDto): String =
        "${MachineReportRules.formatHours(Figures.dec(r.startReading))} → ${MachineReportRules.formatHours(Figures.dec(r.endReading))} h"

    /** "300 h · read by phone 1510.0 ✓" (or "typed by hand"); just the hours without the reading. */
    fun readLine(r: MachineReportDto, capture: MeterCaptureDto?): String {
        val hours = Figures.hours(Figures.dec(r.hours))
        if (capture == null) return hours
        val ocr = capture.ocrValue?.takeIf { it.isNotBlank() }
        val how = when {
            ocr != null -> "read by phone $ocr" + if (Figures.dec(ocr).compareTo(capture.reading.value) == 0) " ✓" else " · typed ${MachineReportRules.formatHours(capture.reading.value)}"
            capture.captureMode == "MANUAL" -> "typed by hand"
            else -> null
        }
        return listOfNotNull(hours, how).joinToString(" · ")
    }

    /** "GPS: ±6 m" or "GPS: no fix"; null without the reading. */
    fun gpsLine(capture: MeterCaptureDto?): String? {
        capture ?: return null
        val accuracy = capture.accuracyM
        return when {
            capture.latitude != null && accuracy != null -> "GPS: ±${Math.round(accuracy)} m"
            capture.latitude != null -> "GPS: position recorded"
            else -> "GPS: ${capture.gpsStatus.lowercase().replace('_', ' ')}"
        }
    }

    /** "· 140 → 20 h left" from the customer's available hours before this report (submitted reports only). */
    fun beforeAfter(l: MachineReportLineDto): String? {
        val before = l.availableHours?.let(Figures::dec) ?: return null
        val after = before - Figures.dec(l.hours)
        return "· ${MachineReportRules.formatHours(before)} → ${MachineReportRules.formatHours(after.max(BigDecimal.ZERO))} h left"
    }

    /** “Hydraulic hose replaced on site” (curly quotes, as the design). */
    fun quoted(note: String?): String? = note?.trim()?.takeIf { it.isNotEmpty() }?.let { "“$it”" }

    /** The tracker cross-check sentence. */
    fun tracker(t: TrackerCheckDto?, r: MachineReportDto): String {
        val tracked = t?.trackerHours?.takeIf { t.available }?.let(Figures::dec) ?: return ReportTexts.NO_TRACKER
        val meter = Figures.dec(t.meterHours.ifBlank { r.hours })
        return "Tracker engine hours for the same period: ${Figures.hours(tracked)} (meter ${Figures.hours(meter)})."
    }

    /** Why the decision buttons are not offered, or null when this person may decide. */
    fun cannotDecide(permissions: Set<String>, r: MachineReportDto, me: String?): String? = when {
        MachineReportApproval.canDecide(permissions, r.submittedBy, me) -> null
        MachineReportApproval.APPROVE !in permissions -> ReportTexts.NO_PERMISSION
        else -> ReportTexts.OWN_REPORT
    }

    fun statusLabel(status: String): String = when (status) {
        MachineReportDto.APPROVED -> ReportTexts.STATUS_APPROVED
        MachineReportDto.REJECTED -> ReportTexts.STATUS_REJECTED
        else -> ReportTexts.STATUS_WAITING
    }

    /** Home attention row: "EX-01 report · 80 h non-productive" (or the hours when all are productive). */
    fun attentionTitle(r: MachineReportDto): String {
        val np = Figures.dec(r.nonProductiveHours)
        return "${machine(r)} report · " + if (np.signum() > 0) "${Figures.hours(np)} non-productive" else Figures.hours(Figures.dec(r.hours))
    }

    /** "Daudi Mollel · today 07:40". */
    fun attentionDetail(r: MachineReportDto, nowMs: Long, zone: ZoneId): String =
        listOfNotNull(r.submittedByName?.takeIf { it.isNotBlank() }, Figures.relative(r.submittedAt, nowMs, zone)).joinToString(" · ")

    /**
     * Where a machine stands for its next report, by the shared rule [MachineReportRules.state] (as the Supervisor app
     * and iOS): it is overdue exactly when that gives DUE, OPENING or REJECTED; a report waiting is never overdue.
     * [reminderDays] is the company's `CUSTOMER_HOURS.machine_report_reminder_days` (null = reminders off).
     */
    fun reportState(s: MachineReportStatusDto, reminderDays: Int?): ReportState = MachineReportRules.state(
        previousReading = s.previousReading,
        pendingOnServer = s.pendingReportId != null,
        pendingOnPhone = false,
        rejected = s.rejectedReportId != null,
        daysSinceReport = s.daysSinceReport,
        reminderDays = reminderDays,
    )

    fun isOverdue(s: MachineReportStatusDto, reminderDays: Int?): Boolean = reportState(s, reminderDays).needsReport

    /** The reminder days to apply: the company's setting once read (null = off), else 3 (loading, failed, refused). */
    fun reminderDays(reminder: com.asseta.owner.data.ReportReminder?): Int? =
        if (reminder == null) com.asseta.core.domain.accountability.CustomerHoursPolicy.DEFAULT_REMINDER_DAYS else reminder.days

    /**
     * "EX-02 · no report for 3 days"; "EX-02 · no report yet" (never reported, or no starting reading);
     * "EX-02 · report rejected, not yet redone".
     */
    fun overdueTitle(s: MachineReportStatusDto, reminderDays: Int?): String {
        val machine = s.machineCode ?: s.machineName ?: "Machine"
        val days = s.daysSinceReport
        return when {
            reportState(s, reminderDays) == ReportState.REJECTED -> "$machine · report rejected, not yet redone"
            reportState(s, reminderDays) == ReportState.OPENING || days == null || days <= 0 -> "$machine · no report yet"
            else -> "$machine · no report for ${Figures.days(days)}"
        }
    }

    /** "Last approved reading 1,510 h" or that there is none yet. */
    fun overdueDetail(s: MachineReportStatusDto): String =
        s.lastApprovedReading?.let { "Last approved reading ${MachineReportRules.formatHours(Figures.dec(it))} h" } ?: "No approved reading yet"

    /** Overdue machines (see [isOverdue]), longest without a report first (never reported first). */
    fun overdue(statuses: List<MachineReportStatusDto>, reminderDays: Int?): List<MachineReportStatusDto> =
        statuses.filter { isOverdue(it, reminderDays) }.sortedByDescending { it.daysSinceReport ?: Int.MAX_VALUE }
}
