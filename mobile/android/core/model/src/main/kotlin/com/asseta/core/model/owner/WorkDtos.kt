package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** `JobDto` (listJobs / inside JobSummaryDto). Money and hours are exact decimal strings. */
@Serializable
data class JobDto(
    val id: SerializableUuid,
    @SerialName("job_number") val jobNumber: String,
    val status: String,
    @SerialName("machine_id") val machineId: SerializableUuid,
    @SerialName("contract_id") val contractId: SerializableUuid,
    val currency: String,
    @SerialName("hourly_rate") val hourlyRate: DecimalAmount,
    @SerialName("minimum_hours") val minimumHours: DecimalAmount,
    @SerialName("mobilization_fee") val mobilizationFee: DecimalAmount,
    @SerialName("discount_percent") val discountPercent: DecimalAmount,
    @SerialName("tax_rate_percent") val taxRatePercent: DecimalAmount,
    @SerialName("rate_source") val rateSource: String,
    @SerialName("standby_treatment") val standbyTreatment: String,
    @SerialName("planned_start") val plannedStart: String,
    val version: Long,
    @SerialName("standby_rate") val standbyRate: DecimalAmount? = null,
    @SerialName("planned_end") val plannedEnd: String? = null,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("approved_at") val approvedAt: String? = null,
    @SerialName("job_site_id") val jobSiteId: SerializableUuid? = null,
    @SerialName("supervisor_id") val supervisorId: SerializableUuid? = null,
    @SerialName("cancellation_reason") val cancellationReason: String? = null,
    /** Set when a supervisor requested the job from the field; [requestedByName] is their name. */
    @SerialName("requested_by_staff_id") val requestedByStaffId: SerializableUuid? = null,
    @SerialName("requested_by_name") val requestedByName: String? = null,
    /** What the customer asked for, as the supervisor wrote it. */
    @SerialName("request_note") val requestNote: String? = null,
) {
    /** A field request without a rate card: approving it needs an hourly rate. */
    val pendingPrice: Boolean get() = rateSource == RATE_PENDING_PRICE

    companion object {
        const val RATE_PENDING_PRICE = "PENDING_PRICE"
    }
}

/**
 * `JobTransitionIn` (transitionJob). [hourlyRate] only with APPROVE (required when the job's rate source is
 * PENDING_PRICE, `422 PRICE_REQUIRED`); CANCEL takes a [reason] (a declined field request).
 */
@Serializable
data class JobTransitionIn(
    val action: String,
    val reason: String? = null,
    @SerialName("hourly_rate") val hourlyRate: String? = null,
) {
    companion object {
        const val APPROVE = "APPROVE"
        const val CANCEL = "CANCEL"
    }
}

/** `JobSummaryDto` (getJobSummary): meter vs billable hours and charges, computed by the server (single source). */
@Serializable
data class JobSummaryDto(
    val job: JobDto,
    @SerialName("opening_reading") val openingReading: DecimalAmount? = null,
    @SerialName("closing_reading") val closingReading: DecimalAmount? = null,
    @SerialName("meter_hours") val meterHours: DecimalAmount? = null,
    @SerialName("billable_hours") val billableHours: DecimalAmount? = null,
    @SerialName("nonbillable_hours") val nonbillableHours: DecimalAmount,
    @SerialName("standby_hours") val standbyHours: DecimalAmount? = null,
    @SerialName("billing_ready") val billingReady: Boolean,
    @SerialName("open_exceptions") val openExceptions: Int,
    @SerialName("blocking_exceptions") val blockingExceptions: Int,
    @SerialName("policy_version") val policyVersion: String,
    val charges: JobChargesDto? = null,
)

@Serializable
data class JobChargesDto(
    val currency: String,
    val lines: List<JobChargeLineDto> = emptyList(),
    val subtotal: DecimalAmount,
    @SerialName("discount_total") val discountTotal: DecimalAmount,
    @SerialName("tax_total") val taxTotal: DecimalAmount,
    val total: DecimalAmount,
)

@Serializable
data class JobChargeLineDto(
    val kind: String,
    val description: String,
    val quantity: DecimalAmount,
    @SerialName("unit_price") val unitPrice: DecimalAmount,
    val amount: DecimalAmount,
)

/** `MeterCaptureDto` (listJobCaptures / listMeterCaptures). The photo is fetched on demand via a presigned URL. */
@Serializable
data class MeterCaptureDto(
    val id: SerializableUuid,
    @SerialName("job_id") val jobId: SerializableUuid,
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

/** `AcknowledgementDto` (listJobAcknowledgements): customer sign-off of the hours. */
@Serializable
data class AcknowledgementDto(
    val id: SerializableUuid,
    val method: String,
    @SerialName("signer_name") val signerName: String,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("acknowledged_hours") val acknowledgedHours: DecimalAmount? = null,
    @SerialName("signer_phone") val signerPhone: String? = null,
    @SerialName("signature_attachment_id") val signatureAttachmentId: SerializableUuid? = null,
)

/** `ActivityDto` (listJobActivities): one work-log entry of a job; [endedAt] is null while it is still going on. */
@Serializable
data class ActivityDto(
    val id: SerializableUuid,
    @SerialName("client_id") val clientId: SerializableUuid,
    @SerialName("activity_type") val activityType: String,
    @SerialName("started_at") val startedAt: String,
    val billable: Boolean,
    @SerialName("ended_at") val endedAt: String? = null,
    val note: String? = null,
)

/** `ExceptionDto` (listJobExceptions): a meter-evidence finding. [evidence] is server-defined and not shown. */
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
    @SerialName("job_id") val jobId: SerializableUuid? = null,
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
