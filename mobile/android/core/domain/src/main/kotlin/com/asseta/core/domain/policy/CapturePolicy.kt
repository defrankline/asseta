package com.asseta.core.domain.policy

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import java.time.Instant

enum class CaptureMode { AUTOMATIC, MANUAL }

/** DAILY: a reading outside a job (machine only; server capability METER_DAILY_READING). */
enum class ReadingKind { OPENING, CLOSING, DAILY }

/** The part of the server `MeterCapturePolicy` a device enforces offline (server re-validates every capture). */
data class MeterCapturePolicy(
    val openingMode: CaptureMode,
    val closingMode: CaptureMode,
    val manualPhotoRequired: Boolean,
    val minOcrConfidence: Double,
    val maxRecaptureAttempts: Int,
    val manualCorrectionRequiresReview: Boolean,
    val gpsEnforcement: String,
) {
    /** A DAILY reading (and a baseline) carries the same evidence rules as a closing reading (server rule). */
    fun requiredMode(kind: ReadingKind): CaptureMode = if (kind == ReadingKind.OPENING) openingMode else closingMode

    companion object {
        /** Strict: a snapshot missing a required value is unusable (fail closed), never defaulted locally. */
        fun fromValues(values: JsonObject): MeterCapturePolicy? = runCatching {
            MeterCapturePolicy(
                openingMode = CaptureMode.valueOf(values.string("opening_mode")),
                closingMode = CaptureMode.valueOf(values.string("closing_mode")),
                manualPhotoRequired = values.prim("manual_photo_required").booleanOrNull!!,
                minOcrConfidence = values.prim("min_ocr_confidence").doubleOrNull!!.also { require(it in 0.0..1.0) },
                maxRecaptureAttempts = values.prim("max_recapture_attempts").intOrNull!!.also { require(it in 0..10) },
                manualCorrectionRequiresReview = values.prim("manual_correction_requires_review").booleanOrNull!!,
                gpsEnforcement = values.string("gps_enforcement"),
            )
        }.getOrNull()

        private fun JsonObject.prim(key: String): JsonPrimitive = this[key] as JsonPrimitive
        private fun JsonObject.string(key: String): String = prim(key).also { require(it.isString) }.content
    }
}

/** Locally stored policy snapshot as delivered by `/sync/bootstrap` or `/sync/changes`. */
data class PolicySnapshot(
    val policyType: String,
    val scopeKey: String,
    val versionIds: List<String>,
    val versionStamp: String,
    val values: JsonObject,
    val validUntil: Instant,
) {
    companion object {
        const val METER_CAPTURE = "METER_CAPTURE"
        const val TENANT_SCOPE = "tenant"
        fun machineScope(machineId: String) = "machine:$machineId"
    }
}

sealed interface CapturePolicyDecision {
    data class Allowed(val snapshot: PolicySnapshot, val policy: MeterCapturePolicy) : CapturePolicyDecision

    /** New captures are blocked until the device reconnects and refreshes its rules (bounded offline operation). */
    data class Blocked(val reason: BlockReason) : CapturePolicyDecision {
        val message: String get() = "Connect to refresh rules. ${reason.detail}"
    }
}

enum class BlockReason(val detail: String) {
    NO_SNAPSHOT("No capture rules have been downloaded for this machine yet."),
    SNAPSHOT_EXPIRED("The downloaded capture rules have expired."),
    OFFLINE_GRANT_EXPIRED("This device has been offline longer than allowed."),
    POLICY_UNREADABLE("The downloaded capture rules could not be read."),
}

/** Machine snapshot wins over the tenant default; expiry and the device offline grant bound offline operation. */
object PolicySelector {
    fun select(
        snapshots: List<PolicySnapshot>,
        machineId: String,
        now: Instant,
        offlineGrantUntil: Instant?,
    ): CapturePolicyDecision {
        val meter = snapshots.filter { it.policyType == PolicySnapshot.METER_CAPTURE }
        val snapshot = meter.firstOrNull { it.scopeKey == PolicySnapshot.machineScope(machineId) }
            ?: meter.firstOrNull { it.scopeKey == PolicySnapshot.TENANT_SCOPE }
            ?: return CapturePolicyDecision.Blocked(BlockReason.NO_SNAPSHOT)
        if (offlineGrantUntil == null || now.isAfter(offlineGrantUntil)) {
            return CapturePolicyDecision.Blocked(BlockReason.OFFLINE_GRANT_EXPIRED)
        }
        if (now.isAfter(snapshot.validUntil)) return CapturePolicyDecision.Blocked(BlockReason.SNAPSHOT_EXPIRED)
        val policy = MeterCapturePolicy.fromValues(snapshot.values)
            ?: return CapturePolicyDecision.Blocked(BlockReason.POLICY_UNREADABLE)
        return CapturePolicyDecision.Allowed(snapshot, policy)
    }
}
