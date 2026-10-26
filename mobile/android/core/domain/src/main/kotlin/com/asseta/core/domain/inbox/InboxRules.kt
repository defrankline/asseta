package com.asseta.core.domain.inbox

import com.asseta.core.model.ClientOperationStatus
import java.math.BigDecimal

/*
 * Supervisor inbox rules shared by every list and detail screen (the iOS app has the same rules in AssetaSync
 * `InboxRules.swift`, word for word): one combined status per record from the local outbox state and the server's
 * copy, matching local records to server records, and the small derived figures (meter hours, work-log totals).
 */

/** Colour family of a status pill (the screens map it onto the palette). */
enum class Tone { NEUTRAL, GOOD, WARNING, BAD, INFO }

/** The one status pill a record shows. [needsAttention] items are listed in the Inbox under "Needs attention". */
enum class InboxStatus(val label: String, val tone: Tone, val needsAttention: Boolean = false) {
    WAITING("Waiting to sync", Tone.NEUTRAL),
    NOT_SYNCED("Not synced", Tone.BAD, needsAttention = true),
    SYNCED("Synced", Tone.GOOD),
    ACCEPTED("Accepted", Tone.GOOD),
    PROVISIONAL("Provisional", Tone.WARNING),
    FLAGGED("Flagged", Tone.WARNING, needsAttention = true),
    REVIEWED("Reviewed", Tone.INFO),
    REJECTED("Rejected", Tone.BAD, needsAttention = true),
    SUPERSEDED("Superseded", Tone.NEUTRAL),
    PENDING_APPROVAL("Pending approval", Tone.WARNING),
    APPROVED("Approved", Tone.GOOD),
    CLAIMED("Awaiting verification", Tone.WARNING),
    VERIFIED("Verified", Tone.GOOD),
    PENDING("Pending", Tone.WARNING),
    RECORDED("Recorded", Tone.GOOD),
}

object InboxStatusRules {
    /** A record known only on this phone: waiting (pending, sending, held), refused, or acknowledged by the server. */
    fun local(status: ClientOperationStatus): InboxStatus = when (status) {
        ClientOperationStatus.PENDING, ClientOperationStatus.SENT, ClientOperationStatus.QUARANTINED -> InboxStatus.WAITING
        ClientOperationStatus.FAILED, ClientOperationStatus.CONFLICT -> InboxStatus.NOT_SYNCED
        ClientOperationStatus.ACKED -> InboxStatus.SYNCED
    }

    /**
     * A reading: rejected or superseded by the server first, then open findings (flagged), reviewed findings, then
     * the capture state (provisional / accepted).
     */
    fun reading(state: String, reviewStatus: String, findingStatuses: List<String>): InboxStatus = when {
        state == "REJECTED" -> InboxStatus.REJECTED
        state == "SUPERSEDED" -> InboxStatus.SUPERSEDED
        reviewStatus == "PENDING_REVIEW" || findingStatuses.any { it == "OPEN" } -> InboxStatus.FLAGGED
        reviewStatus == "REVIEWED" || findingStatuses.isNotEmpty() -> InboxStatus.REVIEWED
        state == "PROVISIONAL" -> InboxStatus.PROVISIONAL
        else -> InboxStatus.ACCEPTED
    }

    fun expense(status: String): InboxStatus = when (status) {
        "APPROVED" -> InboxStatus.APPROVED
        "REJECTED" -> InboxStatus.REJECTED
        else -> InboxStatus.PENDING_APPROVAL
    }

    /** Cash collections and handovers (CLAIMED until the office verifies or rejects them). */
    fun settlement(status: String): InboxStatus = when (status) {
        "VERIFIED" -> InboxStatus.VERIFIED
        "REJECTED" -> InboxStatus.REJECTED
        else -> InboxStatus.CLAIMED
    }

    fun reset(status: String): InboxStatus = when (status) {
        "APPROVED" -> InboxStatus.APPROVED
        "REJECTED" -> InboxStatus.REJECTED
        else -> InboxStatus.PENDING
    }

    /** The server's copy wins once it arrived; until then the local outbox state. */
    fun combined(local: ClientOperationStatus?, server: InboxStatus?): InboxStatus =
        server ?: local?.let(::local) ?: InboxStatus.WAITING
}

/** A local record (outbox operation) for matching: its entity id (client id / capture id) and server id once acked. */
data class LocalKey(val entityId: String, val serverId: String?) {
    val keys: Set<String> get() = setOfNotNull(entityId, serverId)
}

/** One list row: the server's copy, the local one, or both once matched. */
data class Merged<S, L>(val server: S?, val local: L?)

object InboxMerge {
    /**
     * Pairs server records with local records: a local record matches the server record whose id or client id equals
     * the local entity id (client id / capture id) or the server id the acknowledgement returned. Every record appears
     * exactly once; local records without a server copy stay (waiting to sync, refused, or acked but not yet pulled).
     */
    fun <S, L> merge(
        server: List<S>,
        local: List<L>,
        serverKeys: (S) -> Set<String>,
        localKey: (L) -> LocalKey,
    ): List<Merged<S, L>> {
        val byKey = HashMap<String, Int>()
        server.forEachIndexed { i, s -> serverKeys(s).forEach { byKey.putIfAbsent(it, i) } }
        val matched = HashMap<Int, L>()
        val unmatched = ArrayList<L>()
        local.forEach { l ->
            val index = localKey(l).keys.firstNotNullOfOrNull { byKey[it] }
            if (index != null && index !in matched) matched[index] = l else unmatched += l
        }
        return server.mapIndexed { i, s -> Merged(s, matched[i]) } + unmatched.map { Merged<S, L>(null, it) }
    }
}

/** Work-log entry for totals (server activity or local entry); [endMs] null while running. */
data class WorkSpan(val activityType: String, val startMs: Long, val endMs: Long?)

object JobFigures {
    /** Total minutes per activity type of finished entries (running entries count up to [nowMs]), types in first-seen order. */
    fun minutesByType(spans: List<WorkSpan>, nowMs: Long): List<Pair<String, Long>> {
        val totals = LinkedHashMap<String, Long>()
        spans.sortedBy { it.startMs }.forEach { s ->
            if (s.activityType == "NOTE") return@forEach
            val end = s.endMs ?: nowMs
            totals[s.activityType] = (totals[s.activityType] ?: 0L) + ((end - s.startMs).coerceAtLeast(0) / 60_000)
        }
        return totals.toList()
    }

    /** Closing minus opening reading (meter hours), or null until both are known (or when the result is negative). */
    fun meterHours(opening: String?, closing: String?): BigDecimal? {
        val o = opening?.toBigDecimalOrNull() ?: return null
        val c = closing?.toBigDecimalOrNull() ?: return null
        return (c - o).takeIf { it.signum() >= 0 }
    }

    /** "2 h 05 min" / "45 min". */
    fun duration(minutes: Long): String = if (minutes >= 60) "${minutes / 60} h ${(minutes % 60).toString().padStart(2, '0')} min" else "$minutes min"
}

/** What tapping a server notification opens (from its `target`). */
sealed interface InboxLink {
    data class Job(val jobId: String) : InboxLink
    data class Expense(val expenseId: String) : InboxLink
    data object Money : InboxLink
    /** A cash transfer ([isFloat] false) or float sent to me: its acknowledge screen while it waits, else Money. */
    data class CashAck(val id: String, val isFloat: Boolean) : InboxLink
    /** My request to keep cash (status read online). */
    data class Retention(val id: String) : InboxLink
    /** My overdue remittance flag (read online; the Money tab when it cannot be read). */
    data class RemittanceOverdue(val id: String) : InboxLink
    /** A machine of mine (missing daily report, unexplained engine hours). */
    data class Machine(val machineId: String) : InboxLink
    data object None : InboxLink
}

object InboxLinks {
    /** [kind] / [recordId] (notification `data`, DEC-030 G5) name the exact record and win over the target. */
    fun from(entity: String?, id: String?, kind: String? = null, recordId: String? = null): InboxLink {
        if (recordId != null) {
            when (kind) {
                "CASH_TRANSFER" -> return InboxLink.CashAck(recordId, isFloat = false)
                "CASH_FLOAT" -> return InboxLink.CashAck(recordId, isFloat = true)
                "CASH_RETENTION" -> return InboxLink.Retention(recordId)
                "REMITTANCE_OVERDUE" -> return InboxLink.RemittanceOverdue(recordId)
                "JOB" -> return InboxLink.Job(recordId)
            }
        }
        return fromTarget(entity, id)
    }

    private fun fromTarget(entity: String?, id: String?): InboxLink = when {
        entity == "job" && id != null -> InboxLink.Job(id)
        entity == "expense" && id != null -> InboxLink.Expense(id)
        entity == "staff_member" || entity == "cash_custody" -> InboxLink.Money
        // Cash transfers and floats to acknowledge are answered on their own screen (else the Money tab).
        entity == "cash_transfer" && id != null -> InboxLink.CashAck(id, isFloat = false)
        entity == "supervisor_cash_custody" && id != null -> InboxLink.CashAck(id, isFloat = true)
        entity == "cash_remittance_overdue" && id != null -> InboxLink.RemittanceOverdue(id)
        entity == "cash_transfer" || entity == "supervisor_cash_custody" || entity == "cash_remittance_overdue" -> InboxLink.Money
        entity == "cash_retention" && id != null -> InboxLink.Retention(id)
        entity == "machine" && id != null -> InboxLink.Machine(id)
        else -> InboxLink.None
    }
}

/** Offline checks of a meter reset request (the server re-validates; reason 10..2000 characters, evidence photo). */
object ResetRules {
    const val MIN_REASON = 10
    const val MAX_REASON = 2000

    fun validate(oldReading: String, newReading: String, reason: String, hasPhoto: Boolean): List<String> {
        val issues = ArrayList<String>()
        if (parse(oldReading) == null) issues += "Enter the reading before the reset (a number)."
        if (parse(newReading) == null) issues += "Enter the reading after the reset (a number)."
        val r = reason.trim()
        if (r.length < MIN_REASON) issues += "Explain the reset in at least $MIN_REASON characters."
        if (r.length > MAX_REASON) issues += "The reason can be at most $MAX_REASON characters."
        if (!hasPhoto) issues += "Take a photo of the meter as evidence."
        return issues
    }

    /** A non-negative decimal ("," accepted), as the plain wire string, or null. */
    fun parse(text: String): String? {
        val t = text.trim().replace(',', '.')
        if (!Regex("^\\d+(\\.\\d+)?$").matches(t)) return null
        return BigDecimal(t).toPlainString()
    }
}

/** User-facing wording of server findings (same words on iOS). */
object FindingTexts {
    fun type(code: String): String = when (code) {
        "GPS_UNAVAILABLE" -> "No GPS position"
        "GPS_INACCURATE" -> "GPS position not accurate enough"
        "GPS_STALE" -> "GPS position too old"
        "LOCATION_MISMATCH" -> "Not at the job site"
        "MODE_POLICY_VIOLATION" -> "Capture mode not allowed"
        "PHOTO_MISSING" -> "Photo missing"
        "LOW_OCR_CONFIDENCE" -> "Meter photo hard to read"
        "MANUAL_CORRECTION" -> "Reading corrected by hand"
        "METER_DECREASE" -> "Reading lower than before"
        "IMPOSSIBLE_INCREMENT" -> "Reading increased too much"
        "CONTINUITY_GAP" -> "Gap since the last reading"
        "DUPLICATE_IMAGE" -> "Photo used before"
        "TELEMETRY_MISMATCH" -> "Does not match the tracker"
        "CLOCK_SKEW" -> "Phone clock was wrong"
        "POLICY_SNAPSHOT_UNVERIFIED" -> "Capture rules could not be verified"
        "HOURS_OVERRUN" -> "Hours beyond purchase"
        "UNEXPLAINED_HOURS" -> "Engine hours not yet explained"
        "MISSING_DAILY_REPORT" -> "Daily report missing"
        "OVERLAPPING_ALLOCATION" -> "Overlaps another job's hours"
        "OVERLAPPING_ACTIVITY" -> "Overlapping work log entries"
        else -> code.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    fun severity(code: String): String = code.lowercase().replaceFirstChar { it.uppercase() }

    fun review(status: String): String = when (status) {
        "OPEN" -> "Waiting for review"
        "EXPLAINED" -> "Explained"
        "CONFIRMED" -> "Confirmed"
        else -> severity(status)
    }
}
