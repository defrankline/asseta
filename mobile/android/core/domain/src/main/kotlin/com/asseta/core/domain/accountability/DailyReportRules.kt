package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.finance.FormCheck
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import java.math.BigDecimal
import java.time.ZoneId

/** The ENGINE_HOURS switches the field forms follow. Missing keys read as off; the server applies them either way. */
data class EngineHoursPolicy(val changeoverSplitsBilling: Boolean, val dailyReportEvidenceRequired: Boolean) {
    companion object {
        const val TYPE = "ENGINE_HOURS"

        private fun JsonObject.on(key: String) = (this[key] as? JsonPrimitive)?.booleanOrNull ?: false

        fun fromValues(values: JsonObject) =
            EngineHoursPolicy(values.on("changeover_splits_billing"), values.on("daily_report_evidence_required"))
    }
}

/** A reading a report can name. [synced] false: the server does not have it yet (the report waits for it). */
data class ReportReading(val id: String, val reading: String, val atMs: Long, val synced: Boolean)

data class UnbillableDraft(val reasonId: String?, val hoursText: String)

data class DailyReportDraft(
    val openingRef: String?,
    val closingRef: String?,
    val openingReading: String?,
    val closingReading: String?,
    val billableText: String,
    val lines: List<UnbillableDraft>,
    val note: String,
    val photos: Int,
    val evidenceRequired: Boolean,
)

data class DailyReportValues(val billable: BigDecimal?, val lines: List<Pair<String, BigDecimal>>, val note: String?)

/** Wording shared with iOS (docs/requirements/accountability-mobile-strings.md, `field.report.error.*`). */
object DailyReportMessages {
    const val OPENING = "Choose the opening reading."
    const val CLOSING = "Choose the closing reading."
    const val SAME_READING = "Choose two different readings."
    const val BILLABLE = "Enter the billable hours as a number (0 or more, at most 2 decimal places)."
    const val REASON_MISSING = "Choose a reason for each line of unbillable hours."
    const val REASON_HOURS = "Enter the hours for each reason (more than 0, at most 2 decimal places)."
    const val REASON_REPEATED = "Each reason can be used once."
    const val PHOTO = "Your company requires a photo with this report."
    const val CHANGEOVER_CUSTOMER = "Choose the next customer."
    const val CHANGEOVER_JOB = "Choose the next job. Your company bills the hours after a changeover to that job."

    fun exceeds(total: BigDecimal) = "Billable and unbillable hours are more than the ${AccountabilityRules.plain(total)} h between the readings."
}

object ChangeoverRules {
    private const val PENDING_APPROVAL = "PENDING_APPROVAL"
    private const val APPROVED = "APPROVED"

    /**
     * Whether a job in [status] can be named as the next one. A job the hours are billed to ([required]) must be waiting
     * in the approval queue: the one-active-job rule keeps it from being approved while the running job continues.
     */
    fun jobOffered(status: String, required: Boolean): Boolean = status == PENDING_APPROVAL || (!required && status == APPROVED)

    /** Why this changeover cannot be saved, or null. */
    fun problem(customerId: String?, jobId: String?, jobRequired: Boolean): String? = when {
        customerId.isNullOrBlank() -> DailyReportMessages.CHANGEOVER_CUSTOMER
        jobRequired && jobId.isNullOrBlank() -> DailyReportMessages.CHANGEOVER_JOB
        else -> null
    }
}

/** The zone that decides which day a reading belongs to: the tenant's, as the server counts days. */
object TenantZone {
    /** The first valid zone id of [known] (best source first), else [device]. */
    fun resolve(known: List<String?>, device: ZoneId): ZoneId =
        known.firstNotNullOfOrNull { id -> id?.let { runCatching { ZoneId.of(it) }.getOrNull() } } ?: device
}

/** Offline checks of the daily report form; the server re-validates everything. */
object DailyReportRules {
    const val MAX_NOTE = 2000
    const val MAX_LINES = 20
    const val MAX_PHOTOS = 10
    private val HOURS = DecimalLimit.METER_READING

    /** Opening and closing as the server pre-fills them: the day's first when it has two or more, else the latest before it. */
    fun prefill(readings: List<ReportReading>, dayStartMs: Long, dayEndMs: Long): Pair<String?, String?> {
        val day = readings.filter { it.atMs in dayStartMs until dayEndMs }.sortedBy { it.atMs }
        val opening = if (day.size > 1) day.first() else readings.filter { it.atMs < dayStartMs }.maxByOrNull { it.atMs }
        return opening?.id to day.lastOrNull()?.id
    }

    /** Hours between the readings; null when unknown or going backwards (an approved meter reset is for the server to apply). */
    fun total(opening: String?, closing: String?): BigDecimal? {
        val from = opening?.toBigDecimalOrNull() ?: return null
        val to = closing?.toBigDecimalOrNull() ?: return null
        return (to - from).takeIf { it.signum() >= 0 }
    }

    private fun hours(text: String, allowZero: Boolean) = AmountParser.valueOrNull(text, HOURS, allowZero = allowZero)

    /** Total minus billable and unbillable hours, for display; null while it cannot be worked out. */
    fun notAccounted(total: BigDecimal?, billableText: String, lines: List<UnbillableDraft>): BigDecimal? {
        total ?: return null
        val unbillable = lines.sumOf { hours(it.hoursText, false) ?: BigDecimal.ZERO }
        val billable = if (billableText.isBlank()) (total - unbillable).max(BigDecimal.ZERO) else hours(billableText, true) ?: return null
        return total - billable - unbillable
    }

    fun check(d: DailyReportDraft): FormCheck<DailyReportValues> {
        val m = mutableListOf<String>()
        if (d.openingRef.isNullOrBlank()) m += DailyReportMessages.OPENING
        if (d.closingRef.isNullOrBlank()) m += DailyReportMessages.CLOSING
        if (!d.openingRef.isNullOrBlank() && d.openingRef == d.closingRef) m += DailyReportMessages.SAME_READING
        val billable = if (d.billableText.isBlank()) null else hours(d.billableText, true).also { if (it == null) m += DailyReportMessages.BILLABLE }
        val lines = d.lines.filterNot { it.reasonId == null && it.hoursText.isBlank() }
        if (lines.any { it.reasonId.isNullOrBlank() }) m += DailyReportMessages.REASON_MISSING
        if (lines.any { hours(it.hoursText, false) == null }) m += DailyReportMessages.REASON_HOURS
        val ids = lines.mapNotNull { it.reasonId }
        if (ids.size != ids.distinct().size) m += DailyReportMessages.REASON_REPEATED
        if (d.evidenceRequired && d.photos == 0) m += DailyReportMessages.PHOTO
        val total = total(d.openingReading, d.closingReading)
        if (m.isEmpty() && total != null) {
            val claimed = (billable ?: BigDecimal.ZERO) + lines.sumOf { hours(it.hoursText, false)!! }
            if (claimed > total) m += DailyReportMessages.exceeds(total)
        }
        if (m.isNotEmpty()) return FormCheck.Invalid(m)
        return FormCheck.Valid(DailyReportValues(billable, lines.map { it.reasonId!! to hours(it.hoursText, false)!! }, d.note.trim().take(MAX_NOTE).ifEmpty { null }))
    }
}
