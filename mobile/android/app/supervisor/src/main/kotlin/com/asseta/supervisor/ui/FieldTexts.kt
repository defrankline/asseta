package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.data.WaitingReason
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlin.math.abs

/**
 * User-facing wording of the Supervisor app, kept word-for-word identical to the iOS app (AssetaField). Pure functions
 * so the wording and the small display rules are unit-tested.
 */
object FieldTexts {
    fun jobStatus(status: String): String = when (status) {
        JobStatus.APPROVED -> "Approved"
        JobStatus.IN_PROGRESS -> "In progress"
        JobStatus.COMPLETED -> "Completed"
        JobStatus.CANCELLED -> "Cancelled"
        "DRAFT" -> "Draft"
        "PENDING_APPROVAL" -> "Pending approval"
        else -> status.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    /** Status badge text: the device's view, marked when it differs from the server's (local action not synced). */
    fun statusBadge(displayStatus: String, serverStatus: String): String =
        jobStatus(displayStatus) + if (displayStatus != serverStatus) " · not synced" else ""

    fun syncState(status: ClientOperationStatus): String = when (status) {
        ClientOperationStatus.PENDING -> "Waiting to sync"
        ClientOperationStatus.SENT -> "Sending"
        ClientOperationStatus.ACKED -> "Synced"
        ClientOperationStatus.FAILED -> "Rejected"
        ClientOperationStatus.CONFLICT -> "Conflict"
        ClientOperationStatus.QUARANTINED -> "Held"
    }

    fun meterPrecision(decimalPlaces: Int): String = if (decimalPlaces == 0) "Whole hours" else "$decimalPlaces decimal place(s)"

    fun machine(summary: JobSummary): String? = summary.machine?.let { "${it.assetCode} · ${it.name}" }

    /** Home list sections in display order; empty sections are dropped. */
    fun jobSections(jobs: List<JobSummary>, displayStatus: (JobSummary) -> String): List<Pair<String, List<JobSummary>>> {
        val inProgress = jobs.filter { displayStatus(it) == JobStatus.IN_PROGRESS }
        val ready = jobs.filter { displayStatus(it) == JobStatus.APPROVED }
        val other = jobs - (inProgress + ready).toSet()
        return listOf("In progress" to inProgress, "Ready to start" to ready, "Other" to other).filter { it.second.isNotEmpty() }
    }

    /** Title of an operation in a job's "Recorded on this phone" list. */
    fun operationTitle(opType: String, payload: JsonObject?): String {
        fun text(key: String) = (payload?.get(key) as? JsonPrimitive)?.contentOrNull.orEmpty()
        return when (opType) {
            OpTypes.METER_CAPTURE -> (if (text("kind") == "OPENING") "Opening" else "Closing") + " reading ${text("reading")}"
            OpTypes.JOB_ACTIVITY -> "Work log: ${activityType(text("activity_type"))}"
            OpTypes.JOB_ACKNOWLEDGEMENT -> "Acknowledged by ${text("signer_name")}"
            OpTypes.JOB_TRANSITION -> if (text("action") == "START") "Job started" else "Job completed"
            OpTypes.EXPENSE -> "Expense ${text("amount")}"
            OpTypes.FUEL_EVENT -> "Fuel ${text("event_type").lowercase()}: ${text("litres")} L"
            OpTypes.CASH_COLLECTION -> "Cash collection ${text("amount")}"
            OpTypes.CASH_HANDOVER -> "Cash handover ${text("amount")}"
            OpTypes.METER_RESET_REQUEST -> "Meter reset request"
            OpTypes.JOB_REQUEST -> JobRequestTexts.OPERATION
            else -> opType
        }
    }

    /** Title of an item on the sync status screen. */
    fun outboxTitle(opType: String, payload: JsonObject?): String = when (opType) {
        OpTypes.METER_CAPTURE -> "Meter reading"
        OpTypes.JOB_ACTIVITY -> "Work log entry"
        OpTypes.JOB_ACKNOWLEDGEMENT -> "Customer acknowledgement"
        OpTypes.JOB_TRANSITION ->
            if ((payload?.get("action") as? JsonPrimitive)?.contentOrNull == "COMPLETE") "Complete job" else "Start job"
        OpTypes.EXPENSE -> "Expense"
        OpTypes.CASH_COLLECTION -> "Cash collection"
        OpTypes.CASH_HANDOVER -> "Cash handover"
        OpTypes.FUEL_EVENT -> "Fuel event"
        OpTypes.METER_RESET_REQUEST -> "Meter reset request"
        OpTypes.JOB_REQUEST -> JobRequestTexts.OPERATION
        else -> opType
    }

    /** "WORK" -> "Work". */
    fun activityType(type: String): String = type.lowercase().replaceFirstChar { it.uppercase() }

    fun waiting(reason: WaitingReason): String = when (reason) {
        WaitingReason.EARLIER_ITEM -> "Waiting for an earlier item"
        WaitingReason.BLOCKED_BY_EARLIER -> "Blocked by an earlier item that needs attention"
        WaitingReason.UPLOAD -> "Waiting for its photo/receipt/signature upload"
    }

    fun signOutMessage(unsynced: Int): String =
        if (unsynced == 0) "You can sign in again at any time."
        else "$unsynced item(s) are not synced yet. They stay encrypted on this phone and sync after you sign in again."

    /** Another account's unsynced work on this phone (sync status); [label] null when that account is not known. */
    fun heldTitle(label: String?): String = "Waiting for ${label ?: "a previous account"} to sign in again"

    fun heldCount(count: Int): String = "$count item(s) not synced yet"

    const val HELD_FOOTER = "Saved on this phone by another account. They stay encrypted here and are sent only " +
        "when that account signs in again."

    /** Local clock check banner; [skewSeconds] > 0 means the phone is ahead of the server. */
    fun clockTamper(skewSeconds: Long): String =
        "This phone's clock is ${describeSkew(skewSeconds)} compared with Asseta's server. Set the date and time to " +
            "automatic. Readings still record the phone's own time."

    fun describeSkew(skewSeconds: Long): String {
        val minutes = abs(skewSeconds) / 60
        val amount = if (minutes >= 120) "${minutes / 60} hours" else "$minutes minutes"
        return if (skewSeconds > 0) "$amount fast" else "$amount slow"
    }

    const val SERVER_CLOCK = "The server reported that this phone's clock is wrong. Set the date and time to automatic."
    const val OFFLINE = "Offline. You can keep working; everything is saved on this phone and syncs when you are back online."

    /** Banner for the last failed sync run (null when it succeeded). `NETWORK` is the engine's offline code. */
    fun lastSyncProblem(lastError: String?): String? = when (lastError) {
        null -> null
        "NETWORK" -> "Sync failed: Offline or server unreachable. It will retry automatically."
        else -> "Server problem: $lastError. It will retry automatically."
    }

    /** GPS result line for a failed attempt (a fix shows coordinates and accuracy instead). */
    fun gpsFailure(outcome: GpsOutcome): String = when (outcome) {
        is GpsOutcome.Fix -> "Fix"
        GpsOutcome.NoFix -> "No GPS fix could be obtained"
        GpsOutcome.Timeout -> "No GPS fix within 20 seconds"
        GpsOutcome.PermissionDenied -> "Location permission denied"
        GpsOutcome.Disabled -> "Location services are turned off"
    }
}
