package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.domain.inbox.Tone
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.sync.data.DailyReportRow
import java.math.BigDecimal
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Daily report and changeover wording (keys `field.report.*`, `field.changeover.*`, same on iOS). Pure, unit-tested. */
object DailyReportTexts {
    const val MENU = "Daily reports"
    const val ACTION = "Daily report for this machine"
    const val LIST_TITLE = "Daily reports"
    const val SECTION_RETURNED = "Sent back to you"
    const val SECTION_MINE = "My reports"
    const val EMPTY = "No daily reports yet"
    const val EMPTY_HINT = "Reports you send for your machines appear here."
    const val STALE_FOOTER = "Connect to see the office's latest answers."
    const val FORM_TITLE = "Daily report"
    const val RESUBMIT_TITLE = "Send report again"
    const val MACHINE = "Machine"
    const val DAY = "Day"
    const val READINGS = "Readings"
    const val OPENING = "Opening reading"
    const val CLOSING = "Closing reading"
    const val CHOOSE_READING = "Choose a reading"
    const val NO_READINGS = "No readings for this day on this phone. Capture a reading first."
    const val TOTAL = "Hours between the readings"
    const val READINGS_FOOTER = "Taken from your readings. You can choose others."
    const val BILLABLE = "Billable hours (optional)"
    const val BILLABLE_FOOTER = "Left empty, the billable hours are the total minus the unbillable hours."
    const val UNBILLABLE = "Unbillable hours"
    const val CHOOSE_REASON = "Choose a reason"
    const val REASON_HOURS = "Hours"
    const val ADD_REASON = "Add a reason"
    const val REMOVE = "Remove"
    const val REASONS_EMPTY = "Your company has no unbillable reasons yet. Ask the office."
    const val NOT_ACCOUNTED = "Not accounted for"
    const val NOTE = "Note (optional)"
    const val PHOTO_OPTIONAL = "Photo (optional)"
    const val PHOTO_REQUIRED = "Photo (required)"
    const val PHOTO_FOOTER = "Stored encrypted on this phone and uploaded before the report is sent."
    const val TAKE_PHOTO = "Take photo"
    const val ADD_PHOTO = "Add another photo"
    const val SEND = "Send report"
    const val REPEAT_WARNING = "A report for this machine and day was already sent. A repeat is kept and flagged for review."
    const val RESUBMIT_FOOTER = "This replaces the report that was sent back."
    const val OFFICE_NOTE = "The office's note"
    const val TOTAL_HOURS = "Total hours"
    const val BILLABLE_HOURS = "Billable hours"
    const val UNBILLABLE_HOURS = "Unbillable hours"
    const val SUBMITTED = "Sent"
    const val SUBMITTED_BY = "Sent by"
    const val REVIEWED_BY = "Reviewed by"
    const val RETURNED_BY = "Sent back by"
    const val FLAG_LATE = "Sent after the daily cut-off"
    const val FLAG_REPEAT = "Repeat report for this day"
    const val ALLOCATIONS = "Hours by customer"
    const val RESUBMIT = "Correct and send again"
    const val NOT_FOUND = "Report not available"
    const val NOT_FOUND_HINT = "Connect to load it, or it is no longer on this phone."
    const val OUTBOX = "Daily report"
    const val STATUS = "Status"
    const val NOTE_LABEL = "Note"
    const val PHOTOS = "Photos"
    const val SYNC = "Sync"
    const val ON_THIS_PHONE = "On this phone"

    const val CHANGEOVER_ACTION = "Record changeover"
    const val CHANGEOVER_TITLE = "Changeover reading"
    const val CHANGEOVER_FOOTER = "Take this reading when the machine moves to the next customer while this job is still running."
    const val NEXT_CUSTOMER = "Next customer"
    const val CHOOSE_CUSTOMER = "Choose the customer"
    const val NEXT_JOB = "Next job (optional)"
    const val NEXT_JOB_REQUIRED = "Next job (required)"
    const val CHOOSE_JOB = "Choose the job"
    const val NO_JOBS = "No job for this customer on this phone yet. Ask the office to create it."
    const val CHANGEOVER_OUTBOX = "Changeover reading"

    private val DATE = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.US)

    fun date(raw: String): String = runCatching { DATE.format(LocalDate.parse(raw.take(10))) }.getOrDefault(raw)

    fun hours(raw: String?): String = raw?.toBigDecimalOrNull()?.let(::hours) ?: raw.orEmpty()

    fun hours(value: BigDecimal): String = AccountabilityRules.plain(value.setScale(2, java.math.RoundingMode.HALF_EVEN))

    fun rowLine(total: String, billable: String) = "${hours(total)} h in total · ${hours(billable)} h billable"

    fun readingOption(reading: String, dateTime: String, synced: Boolean) = "$reading · $dateTime" + if (synced) "" else " · not synced yet"

    fun kind(wire: String): String = when (wire) {
        "CUSTOMER_WORK" -> "Customer work"
        "AUTHORIZED_ACTIVITY" -> "Authorized activity"
        "UNEXPLAINED" -> "Unexplained"
        else -> wire.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    /** The pill of a report: the server's status, else this phone's sync state. */
    fun status(r: DailyReportRow): Pair<String, Tone> {
        r.server?.let { s ->
            return when (s.status) {
                DailyReportDto.SUBMITTED -> "Sent" to Tone.INFO
                DailyReportDto.REVIEWED -> "Reviewed" to Tone.GOOD
                DailyReportDto.RETURNED -> "Sent back" to Tone.WARNING
                DailyReportDto.SUPERSEDED -> "Replaced" to Tone.NEUTRAL
                else -> s.status.lowercase().replaceFirstChar { it.uppercase() } to Tone.NEUTRAL
            }
        }
        return when (r.op?.status) {
            ClientOperationStatus.FAILED, ClientOperationStatus.CONFLICT -> "Not accepted" to Tone.BAD
            ClientOperationStatus.ACKED -> "Sent" to Tone.INFO
            else -> "Waiting to sync" to Tone.NEUTRAL
        }
    }

    /** Plain words for the DEC-032 conflict codes (null: not one of them). */
    fun conflict(code: String?): String? = when (code) {
        "REPORT_READINGS_INVALID" -> "The readings in this report are no longer valid or do not fit the day. Send the report again with other readings."
        "REPORT_HOURS_EXCEED_TOTAL" -> "Billable and unbillable hours are more than the hours between the readings. Send the report again."
        "REPORT_ID_CONFLICT" -> "This report could not be saved because its id is already used. Send the report again."
        "REPORT_NOT_SUPERSEDABLE" -> "That report can no longer be replaced. It may have been reviewed already."
        "REPORT_EVIDENCE_REQUIRED" -> "Your company requires a photo with this report. Send the report again with a photo."
        "REASON_NOT_ALLOWED" -> "One of the reasons is no longer in use. Send the report again with another reason."
        "CHANGEOVER_NOT_ALLOWED" -> "This job was no longer running, so the changeover was not accepted."
        "CHANGEOVER_SAME_CUSTOMER" -> "The machine is already working for this customer, so the changeover was not accepted."
        "CHANGEOVER_JOB_REQUIRED" -> "Your company bills the hours after a changeover to the next job. Record the changeover again and choose the job."
        "CHANGEOVER_JOB_INVALID" -> "That job can no longer follow this one. It must still be waiting for approval, on this machine, for that customer."
        else -> null
    }
}
