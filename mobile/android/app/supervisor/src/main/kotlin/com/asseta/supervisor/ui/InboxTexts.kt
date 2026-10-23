package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.sync.data.AttentionItem
import com.asseta.core.sync.data.JobSummary
import java.math.BigDecimal

/** The five bottom tabs, in order (same on iOS). */
enum class SupervisorTab(val label: String) {
    JOBS("Jobs"),
    READINGS("Readings"),
    FUEL("Fuel"),
    MONEY("Money"),
    INBOX("Inbox"),
}

/** Jobs tab segments. */
enum class JobSegment(val label: String) {
    IN_PROGRESS("In progress"),
    READY("Ready to start"),
    CLOSED("Recently closed"),
    MACHINES("My machines"),
}

enum class MoneySegment(val label: String) { EXPENSES("Expenses"), COLLECTIONS("Collections"), HANDOVERS("Handovers") }

enum class FuelSegment(val code: String, val label: String) { PURCHASE("PURCHASE", "Purchase"), ISSUE("ISSUE", "Issue"), USAGE("USAGE", "Usage") }

/**
 * Wording of the supervisor tabs (Readings, Fuel, Money, Inbox and the job summary), word for word the iOS
 * `InboxTexts`. Pure functions so wording and the small display rules are unit-tested.
 */
object InboxTexts {
    /** Jobs segment of a job by its status on this device. */
    fun segment(displayStatus: String): JobSegment = when (displayStatus) {
        JobStatus.IN_PROGRESS -> JobSegment.IN_PROGRESS
        JobStatus.COMPLETED, JobStatus.CANCELLED -> JobSegment.CLOSED
        else -> JobSegment.READY
    }

    fun jobsEmpty(segment: JobSegment): Pair<String, String> = when (segment) {
        JobSegment.IN_PROGRESS -> "No jobs in progress" to "Jobs you have started appear here."
        JobSegment.READY -> "No jobs ready to start" to "Approved jobs assigned to you appear here after a sync."
        JobSegment.CLOSED -> "No recently closed jobs" to "Jobs completed or cancelled in the last 14 days appear here."
        JobSegment.MACHINES -> "No machines" to "Machines of your jobs appear here after a sync."
    }

    fun readingKind(kind: String): String = if (kind == "OPENING") "Opening reading" else "Closing reading"

    fun captureMode(mode: String): String = when (mode) {
        "AUTOMATIC" -> "Camera (automatic)"
        "MANUAL" -> "Typed in"
        else -> sentence(mode)
    }

    /** GPS result of a reading. */
    fun gps(status: String, latitude: Double?, longitude: Double?, accuracyM: Double?): String = when (status) {
        "FIX" -> if (latitude != null && longitude != null) {
            "%.5f, %.5f".format(java.util.Locale.ROOT, latitude, longitude) + (accuracyM?.let { " (±${it.toInt()} m)" } ?: "")
        } else "Position recorded"
        "NO_FIX" -> "No GPS fix could be obtained"
        "TIMEOUT" -> "No GPS fix within 20 seconds"
        "PERMISSION_DENIED" -> "Location permission denied"
        "DISABLED" -> "Location services are turned off"
        else -> sentence(status)
    }

    /** "92 %" from an OCR confidence 0..1. */
    fun confidence(value: Double?): String? = value?.let { "${(it * 100).toInt()} %" }

    fun reviewOutcome(reviewStatus: String?, findings: Int): String = when {
        findings == 0 -> "No findings"
        reviewStatus == "PENDING_REVIEW" -> "Waiting for the office to review"
        reviewStatus == "REVIEWED" -> "Reviewed by the office"
        else -> "No review needed"
    }

    fun fuelType(code: String): String = FuelSegment.entries.firstOrNull { it.code == code }?.label ?: sentence(code)

    fun paidFrom(code: String): String = when (code) {
        "CASH_CUSTODY" -> "My cash"
        "COMPANY" -> "Company"
        else -> sentence(code)
    }

    fun ackMethod(code: String): String = when (code) {
        "SIGNATURE" -> "Signature"
        "NAME_CONFIRMATION" -> "Name confirmation"
        else -> sentence(code)
    }

    fun money(amount: String, currency: String?): String =
        (amount.toBigDecimalOrNull()?.stripTrailingZeros()?.let { if (it.scale() < 0) it.setScale(0) else it }?.toPlainString() ?: amount) +
            (currency?.let { " $it" } ?: "")

    fun litres(value: String): String = (value.toBigDecimalOrNull()?.stripTrailingZeros()?.toPlainString() ?: value) + " L"

    fun hours(value: BigDecimal): String = value.stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }.toPlainString() + " h"

    /** Money list section of a record: this phone's own (not confirmed yet) or the office's status. */
    fun moneyGroup(status: InboxStatus): String = when (status) {
        InboxStatus.WAITING, InboxStatus.SYNCED, InboxStatus.NOT_SYNCED -> ON_THIS_PHONE
        else -> status.label
    }

    /** Money list sections in display order: on this phone, waiting for the office, approved/verified, rejected. */
    fun <T> moneyGroups(items: List<T>, status: (T) -> InboxStatus): List<Pair<String, List<T>>> {
        val order = listOf(ON_THIS_PHONE, InboxStatus.PENDING_APPROVAL.label, InboxStatus.CLAIMED.label, InboxStatus.APPROVED.label,
            InboxStatus.VERIFIED.label, InboxStatus.REJECTED.label)
        return items.groupBy { moneyGroup(status(it)) }.toList().sortedBy { (title, _) -> order.indexOf(title).let { if (it < 0) order.size else it } }
    }

    const val ON_THIS_PHONE = "On this phone"

    /** Title of a "Needs attention" row. */
    fun attentionTitle(kind: AttentionItem.Kind): String = when (kind) {
        AttentionItem.Kind.READING -> "Meter reading"
        AttentionItem.Kind.RESET -> "Meter reset request"
        AttentionItem.Kind.EXPENSE -> "Expense"
        AttentionItem.Kind.FUEL -> "Fuel event"
        AttentionItem.Kind.COLLECTION -> "Cash collection"
        AttentionItem.Kind.HANDOVER -> "Cash handover"
        AttentionItem.Kind.OPERATION -> "Job step"
        AttentionItem.Kind.UPLOAD -> "Photo or signature upload"
    }

    fun attentionDetail(status: InboxStatus): String = when (status) {
        InboxStatus.REJECTED -> "Rejected by the office"
        InboxStatus.FLAGGED -> "Flagged: the office will review it"
        InboxStatus.NOT_SYNCED -> "Not accepted by the server. Open Sync status for details."
        else -> status.label
    }

    /** Inbox badge: unread notifications plus items that need attention. */
    fun inboxBadge(unread: Int, attention: Int): Int = unread + attention

    fun machine(assetCode: String?, name: String?): String = listOfNotNull(assetCode, name).joinToString(" · ").ifEmpty { "Machine" }

    fun jobLine(summary: JobSummary): String = listOfNotNull(FieldTexts.machine(summary), summary.siteName).joinToString(" · ")

    const val RECONCILIATION_FOOTER = "From the office's books today: opening balance, floats, collections, approved spending and " +
        "verified handovers."
    const val ESTIMATE_FOOTER = "Offline estimate from the last synced balance and what this phone has recorded since. " +
        "Connect to see today's figures from the office."
    const val NOTIFICATIONS_OFFLINE = "Showing the notifications saved on this phone. Connect to check for new ones."

    private fun sentence(code: String) = code.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
}
