package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** `MeterCaptureDto` (listMeterCaptures / getMeterCapture). The photo is fetched on demand via a presigned URL. */
@Serializable
data class MeterCaptureDto(
    val id: SerializableUuid,
    @SerialName("machine_id") val machineId: SerializableUuid,
    val kind: String,
    val reading: DecimalAmount,
    @SerialName("capture_mode") val captureMode: String,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("gps_status") val gpsStatus: String,
    val state: String,
    @SerialName("manually_corrected") val manuallyCorrected: Boolean,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("ocr_value") val ocrValue: String? = null,
    @SerialName("ocr_confidence") val ocrConfidence: Double? = null,
    @SerialName("photo_attachment_id") val photoAttachmentId: SerializableUuid? = null,
    @SerialName("photo_sha256") val photoSha256: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("location_captured_at") val locationCapturedAt: String? = null,
    @SerialName("supersedes_id") val supersedesId: SerializableUuid? = null,
    @SerialName("tracker_comparison") val trackerComparison: Map<String, kotlinx.serialization.json.JsonElement>? = null,
)

/** `ExceptionDto` (listMeterExceptions): a meter-evidence finding. [evidence] is server-defined and not shown. */
@Serializable
data class ExceptionDto(
    val id: SerializableUuid,
    @SerialName("machine_id") val machineId: SerializableUuid,
    @SerialName("exception_type") val exceptionType: String,
    val severity: String,
    val blocking: Boolean,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    val evidence: Map<String, kotlinx.serialization.json.JsonElement> = emptyMap(),
    @SerialName("meter_capture_id") val meterCaptureId: SerializableUuid? = null,
    @SerialName("policy_version") val policyVersion: String? = null,
    @SerialName("review_note") val reviewNote: String? = null,
    @SerialName("reviewed_at") val reviewedAt: String? = null,
)

/** `ResetDto` (listMeterResets / decideMeterReset): a requested meter reset; [status] PENDING, APPROVED or REJECTED. */
@Serializable
data class MeterResetDto(
    val id: SerializableUuid,
    @SerialName("machine_id") val machineId: SerializableUuid,
    @SerialName("old_reading") val oldReading: DecimalAmount,
    @SerialName("new_reading") val newReading: DecimalAmount,
    @SerialName("effective_at") val effectiveAt: String,
    val reason: String,
    val status: String,
    @SerialName("evidence_attachment_id") val evidenceAttachmentId: SerializableUuid? = null,
    @SerialName("requested_by") val requestedBy: SerializableUuid? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
)

/** `ReviewIn` for decideMeterReset: EXPLAINED approves, CONFIRMED rejects; [note] 5..2000 characters. */
@Serializable
data class MeterResetDecisionIn(val outcome: String, val note: String) {
    companion object {
        const val APPROVE = "EXPLAINED"
        const val REJECT = "CONFIRMED"
    }
}
