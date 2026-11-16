package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.OpTypes
import com.asseta.supervisor.ui.accountability.FieldAccountabilityTexts
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
    fun syncState(status: ClientOperationStatus): String = when (status) {
        ClientOperationStatus.PENDING -> "Waiting to sync"
        ClientOperationStatus.SENT -> "Sending"
        ClientOperationStatus.ACKED -> "Synced"
        ClientOperationStatus.FAILED -> "Rejected"
        ClientOperationStatus.CONFLICT -> "Conflict"
        ClientOperationStatus.QUARANTINED -> "Held"
    }

    fun meterPrecision(decimalPlaces: Int): String = if (decimalPlaces == 0) "Whole hours" else "$decimalPlaces decimal place(s)"

    /** Title of an item on the sync status screen. */
    fun outboxTitle(opType: String, payload: JsonObject?): String = when (opType) {
        OpTypes.METER_CAPTURE -> FieldAccountabilityTexts.OUTBOX_DAILY
        AccountabilityOps.HOURS_PURCHASE -> FieldAccountabilityTexts.outboxHoursSale(payload)
        AccountabilityOps.HOURS_TRANSFER_REQUEST -> FieldAccountabilityTexts.OUTBOX_HOURS_TRANSFER
        AccountabilityOps.CASH_TRANSFER -> FieldAccountabilityTexts.OUTBOX_CASH_TRANSFER
        AccountabilityOps.CASH_TRANSFER_ACKNOWLEDGEMENT -> FieldAccountabilityTexts.OUTBOX_TRANSFER_ACK
        AccountabilityOps.CASH_FLOAT_ACKNOWLEDGEMENT -> FieldAccountabilityTexts.OUTBOX_FLOAT_ACK
        AccountabilityOps.METER_BASELINE -> FieldAccountabilityTexts.OUTBOX_BASELINE
        AccountabilityOps.METER_CORRECTION -> FieldAccountabilityTexts.OUTBOX_CORRECTION
        AccountabilityOps.CASH_RETENTION_REQUEST -> FieldAccountabilityTexts.OUTBOX_RETENTION
        com.asseta.core.model.sync.MachineReportOps.MACHINE_REPORT -> com.asseta.supervisor.ui.report.ReportTexts.OUTBOX
        com.asseta.core.model.sync.MachineReportOps.CREDIT_INVOICE_PAYMENT -> com.asseta.supervisor.ui.report.ReportTexts.OUTBOX_INVOICE_PAYMENT
        OpTypes.EXPENSE -> "Expense"
        OpTypes.CASH_COLLECTION -> "Cash collection"
        OpTypes.CASH_HANDOVER -> "Cash handover"
        OpTypes.FUEL_EVENT -> "Fuel event"
        OpTypes.METER_RESET_REQUEST -> "Meter reset request"
        else -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.outboxTitle(opType) ?: opType
    }

    fun waiting(reason: WaitingReason, opType: String? = null): String = when (reason) {
        WaitingReason.EARLIER_ITEM -> "Waiting for an earlier item"
        WaitingReason.BLOCKED_BY_EARLIER -> "Blocked by an earlier item that needs attention"
        WaitingReason.UPLOAD -> if (opType == OpTypes.CASH_HANDOVER ||
            opType == com.asseta.core.model.sync.PettyCashOps.RETURN || opType == com.asseta.core.model.sync.PettyCashOps.COUNT) FieldAccountabilityTexts.OUTBOX_WAITING_PHOTOS else "Waiting for its photo/receipt upload"
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
