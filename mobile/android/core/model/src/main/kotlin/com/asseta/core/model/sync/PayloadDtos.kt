package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Outbox operation payloads. Shapes follow contracts/openapi.json `MeterCaptureIn`, `GpsIn`, `ActivityIn`,
 * `AcknowledgementIn`; activity/acknowledgement/transition payloads also carry `job_id` (read by the push dispatcher).
 * Readings are decimal strings (never binary floats). Timestamps are ISO-8601 UTC device time.
 */
@Serializable
data class GpsIn(
    val status: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("captured_at") val capturedAt: String? = null,
    val provider: String? = null,
)

@Serializable
data class MeterCaptureIn(
    val id: String,
    /** Required for OPENING/CLOSING; null for a DAILY reading outside a job (then [machineId] names the machine). */
    @SerialName("job_id") val jobId: String? = null,
    val kind: String,
    @SerialName("capture_mode") val captureMode: String,
    val reading: String,
    @SerialName("ocr_raw_text") val ocrRawText: String? = null,
    @SerialName("ocr_value") val ocrValue: String? = null,
    @SerialName("ocr_confidence") val ocrConfidence: Double? = null,
    @SerialName("ocr_engine") val ocrEngine: String? = null,
    @SerialName("photo_attachment_id") val photoAttachmentId: String? = null,
    val gps: GpsIn,
    @SerialName("device_id") val deviceId: String,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("policy_version_ids") val policyVersionIds: List<String> = emptyList(),
    /** The machine read: set for a DAILY reading outside a job (must match the job's machine when both are sent). */
    @SerialName("machine_id") val machineId: String? = null,
)

@Serializable
data class ActivityPayload(
    @SerialName("job_id") val jobId: String,
    @SerialName("client_id") val clientId: String,
    @SerialName("activity_type") val activityType: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String? = null,
    /** null = the contract default (ActivityIn.billable). */
    val billable: Boolean? = null,
    val note: String? = null,
    @SerialName("device_id") val deviceId: String? = null,
)

@Serializable
data class AcknowledgementPayload(
    @SerialName("job_id") val jobId: String,
    @SerialName("client_id") val clientId: String,
    val method: String,
    @SerialName("signer_name") val signerName: String,
    @SerialName("signer_phone") val signerPhone: String? = null,
    @SerialName("signature_attachment_id") val signatureAttachmentId: String? = null,
    /** Hours the customer confirmed (decimal string, at most 2 decimals), optional. */
    @SerialName("acknowledged_hours") val acknowledgedHours: String? = null,
    @SerialName("captured_at") val capturedAt: String,
)

@Serializable
data class JobTransitionPayload(
    @SerialName("job_id") val jobId: String,
    val action: String,
)

/**
 * `JOB_REQUEST` (`JobRequestIn`): a supervisor's job request from the field. [clientId] becomes the server job id (a
 * replay returns the same job); the server numbers and prices it and sends it to the owner for approval.
 */
@Serializable
data class JobRequestPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("contract_id") val contractId: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    @SerialName("planned_start") val plannedStart: String,
    @SerialName("planned_end") val plannedEnd: String? = null,
    /** What the customer asked for (at most 1000 characters). */
    val note: String? = null,
)

object AckMethod {
    const val SIGNATURE = "SIGNATURE"
    const val NAME_CONFIRMATION = "NAME_CONFIRMATION"
}

object ActivityTypes {
    const val WORK = "WORK"
    const val STANDBY = "STANDBY"
    const val DOWNTIME = "DOWNTIME"
    const val MOBILIZATION = "MOBILIZATION"
    const val NOTE = "NOTE"
}
