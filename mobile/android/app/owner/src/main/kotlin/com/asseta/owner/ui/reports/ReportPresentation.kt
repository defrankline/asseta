package com.asseta.owner.ui.reports

import com.asseta.core.domain.reports.MachineReportApproval
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.domain.reports.VisitPlace
import com.asseta.core.domain.reports.Visits
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
    const val CONFIRM_REJECT_TEXT = "The supervisor is told your reason. A rejected report is kept as a record; the supervisor sends a new report with a new reading."
    const val APPROVED = "Report approved. The customers' hours are used."
    const val REJECTED = "Report rejected. The supervisor will send a new report."
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
    const val FIRST_READING = "First reading — starting point"
    const val OPENING_NOTE = "The machine's first reading, so there are no hours to split. Approving it makes this reading the starting point; the next report counts hours from it."
    const val OPENING_APPROVED = "Reading approved. The next report counts hours from it."

    /** Plain sentences for the server's refusal codes on approve / reject (else the server's message). */
    fun refusal(code: String?, fallback: String): String = when (code) {
        "SEGREGATION_OF_DUTIES" -> "You submitted this report, so you can't decide it. Someone else with approval rights must."
        "REPORT_NOT_PENDING" -> "This report was already decided by someone else. It has been refreshed."
        "REPORT_READINGS_CHANGED" -> "The machine's previous reading changed after this report was sent (a baseline or meter reset). Reject it so the supervisor sends a new report."
        "HOURS_NOT_AVAILABLE" -> "A customer no longer has these hours (cancelled or expired). Reject the report so the supervisor sends a new report."
        "REPORT_NOT_FOUND" -> "This report no longer exists."
        else -> fallback
    }
}

/** Pure presentation of machine reports (unit-tested). */
object ReportPresentation {
    fun machine(r: MachineReportDto): String = r.machineCode ?: r.machineName ?: r.reportNumber

    fun customerLines(r: MachineReportDto): List<MachineReportLineDto> = r.lines.filter { it.kind == MachineReportLineDto.CUSTOMER }

    fun nonProductiveLines(r: MachineReportDto): List<MachineReportLineDto> = r.lines.filter { it.kind == MachineReportLineDto.NON_PRODUCTIVE }

    /** "EX-01 · 300 h · Daudi Mollel" (an opening report has no hours: "EX-01 · Daudi Mollel"). */
    fun rowTitle(r: MachineReportDto): String =
        listOfNotNull(machine(r), Figures.hours(Figures.dec(r.hours)).takeUnless { r.isOpening }, r.submittedByName?.takeIf { it.isNotBlank() }).joinToString(" · ")

    /** Short reason ("transit", "breakdown"): the code in words, else the name. */
    fun reasonShort(l: MachineReportLineDto): String =
        l.reasonCode?.lowercase()?.replace('_', ' ') ?: l.reasonName?.lowercase() ?: "non-productive"

    /**
     * "220 h to 2 customers · 80 h non-productive"; one customer is named ("38 h Mji Mpya Housing"), one reason too
     * ("4 h transit"). Without lines (a list row may carry none): the totals. An opening report: "First reading — starting
     * point".
     */
    fun split(r: MachineReportDto): String {
        if (r.isOpening) return ReportTexts.FIRST_READING
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

    /** "1,210 → 1,510 h"; an opening report has one reading: "1,520.4 h". */
    fun readings(r: MachineReportDto): String =
        if (r.isOpening) "${MachineReportRules.formatHours(Figures.dec(r.endReading))} h"
        else "${MachineReportRules.formatHours(Figures.dec(r.startReading))} → ${MachineReportRules.formatHours(Figures.dec(r.endReading))} h"

    /**
     * "300 h · read by phone 1510.0 ✓" (or "typed by hand"); just the hours without the reading. An opening report:
     * "First reading — starting point · typed by hand".
     */
    fun readLine(r: MachineReportDto, capture: MeterCaptureDto?): String {
        val hours = if (r.isOpening) ReportTexts.FIRST_READING else Figures.hours(Figures.dec(r.hours))
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

    /** The tracker cross-check sentence; an opening report has no period, so it says what approving it does. */
    fun tracker(t: TrackerCheckDto?, r: MachineReportDto): String {
        if (r.isOpening) return ReportTexts.OPENING_NOTE
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

    /** The message after a decision (an approved opening report sets the starting point; it uses no hours). */
    fun decided(r: MachineReportDto, approved: Boolean): String = when {
        !approved -> ReportTexts.REJECTED
        r.isOpening -> ReportTexts.OPENING_APPROVED
        else -> ReportTexts.APPROVED
    }

    fun statusLabel(status: String): String = when (status) {
        MachineReportDto.APPROVED -> ReportTexts.STATUS_APPROVED
        MachineReportDto.REJECTED -> ReportTexts.STATUS_REJECTED
        else -> ReportTexts.STATUS_WAITING
    }

    /**
     * Home attention row: "EX-01 report · 80 h non-productive" (or the hours when all are productive); an opening report:
     * "EX-01 first reading · 1,520.4 h".
     */
    fun attentionTitle(r: MachineReportDto): String {
        if (r.isOpening) return "${machine(r)} first reading · ${readings(r)}"
        val np = Figures.dec(r.nonProductiveHours)
        return "${machine(r)} report · " + if (np.signum() > 0) "${Figures.hours(np)} non-productive" else Figures.hours(Figures.dec(r.hours))
    }

    /** "Daudi Mollel · today 07:40". */
    fun attentionDetail(r: MachineReportDto, nowMs: Long, zone: ZoneId): String =
        listOfNotNull(r.submittedByName?.takeIf { it.isNotBlank() }, Figures.relative(r.submittedAt, nowMs, zone)).joinToString(" · ")

    /**
     * Where a machine stands for its next report, by the shared rule [MachineReportRules.state] (as the Supervisor app
     * and iOS): it is overdue exactly when that gives DUE or OPENING (a rejected report makes it DUE); a report waiting is never overdue.
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

    /** The visit-gap warning hours to apply: the company's once read (null = never flag), else 24. */
    fun visitGapHours(reminder: com.asseta.owner.data.ReportReminder?): Int? =
        if (reminder == null) com.asseta.core.domain.accountability.CustomerHoursPolicy.DEFAULT_VISIT_GAP_HOURS else reminder.visitGapHours

    /** "Since last visit: 1 day 3 h" / "Since last visit: First visit". */
    fun sinceLastVisit(r: MachineReportDto): String = Visits.sinceLastVisit(r.sincePreviousVisitSeconds)

    /** The gap is over the company's `visit_gap_warning_hours` (null = never flagged). */
    fun visitGapFlagged(r: MachineReportDto, warningHours: Int?): Boolean = Visits.gapFlagged(r.sincePreviousVisitSeconds, warningHours)

    /** Where this report's reading was taken; null without coordinates. */
    fun where(r: MachineReportDto): String? = Visits.where(visit(r))

    fun visit(r: MachineReportDto): VisitPlace = VisitPlace(r.visitPlace, r.visitSiteName, r.visitLat, r.visitLng, r.visitAccuracyM)

    fun previousVisit(r: MachineReportDto): VisitPlace =
        VisitPlace(r.previousVisitPlace, r.previousVisitSiteName, r.previousVisitLat, r.previousVisitLng, r.previousVisitAccuracyM)

    /** "Last visit: 17 Nov, 15:26 · Where: …"; null on a first visit. */
    fun lastVisit(r: MachineReportDto, zone: ZoneId = ZoneId.systemDefault()): String? = Visits.lastVisit(r.previousVisitAt, previousVisit(r), zone)

    /** The reminder days to apply: the company's setting once read (null = off), else 3 (loading, failed, refused). */
    fun reminderDays(reminder: com.asseta.owner.data.ReportReminder?): Int? =
        if (reminder == null) com.asseta.core.domain.accountability.CustomerHoursPolicy.DEFAULT_REMINDER_DAYS else reminder.days

    /**
     * "EX-02 · no report for 3 days"; "EX-02 · no report yet" (never reported, or no starting reading);
     * "EX-02 · report rejected, no new report yet".
     */
    fun overdueTitle(s: MachineReportStatusDto, reminderDays: Int?): String {
        val machine = s.machineCode ?: s.machineName ?: "Machine"
        val days = s.daysSinceReport
        return when {
            reportState(s, reminderDays) == ReportState.DUE && s.rejectedReportId != null -> "$machine · report rejected, no new report yet"
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
