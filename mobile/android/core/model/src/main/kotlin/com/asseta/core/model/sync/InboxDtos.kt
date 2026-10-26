package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/*
 * Supervisor inbox (capability SUPERVISOR_INBOX_V1): the caller's own field records as the server knows them, delivered
 * by bootstrap/changes in `SyncData.my_*` and upserted by (id, sync_revision). Shapes follow contracts/openapi.json
 * (`SyncMeterCaptureDto` ... `SyncCashHandoverDto`); every contract-required field is mapped (SyncContractTest), money,
 * litres and readings stay decimal strings, unknown enum values are kept as text.
 */

object SyncCapabilities {
    const val SUPERVISOR_INBOX_V1 = "SUPERVISOR_INBOX_V1"
    const val OP_METER_RESET_REQUEST = "OP_METER_RESET_REQUEST"
    const val OP_JOB_REQUEST = "OP_JOB_REQUEST"

    /** CASH_TRANSFER, CASH_TRANSFER_ACKNOWLEDGEMENT and CASH_FLOAT_ACKNOWLEDGEMENT. */
    const val OP_CASH_TRANSFER = "OP_CASH_TRANSFER"
    const val OP_HOURS_PURCHASE = "OP_HOURS_PURCHASE"

    /** CASH_RETENTION_REQUEST ("Ask to keep cash" offline). */
    const val OP_CASH_RETENTION_REQUEST = "OP_CASH_RETENTION_REQUEST"
    const val OP_HOURS_TRANSFER_REQUEST = "OP_HOURS_TRANSFER_REQUEST"

    /** METER_CAPTURE accepts kind DAILY (no job, machine_id instead). */
    const val METER_DAILY_READING = "METER_DAILY_READING"
    const val OP_METER_BASELINE = "OP_METER_BASELINE"
    const val OP_METER_CORRECTION = "OP_METER_CORRECTION"

    /**
     * DEC-031 D2: CASH_HANDOVER accepts method, deposit_account_id and evidence_upload_ids (blob purpose
     * REMITTANCE_EVIDENCE); SyncData carries deposit_accounts.
     */
    const val REMITTANCE_DETAILS_V1 = "REMITTANCE_DETAILS_V1"

    /** DEC-031 M3: SITE_CHECKIN; announced only while the tenant requires site check-ins. */
    const val OP_SITE_CHECKIN = "OP_SITE_CHECKIN"
}

/** `ExceptionDto`: a server finding on a reading (type, severity, blocking) and its review. */
@Serializable
data class FindingDto(
    val id: String,
    @SerialName("exception_type") val exceptionType: String,
    val severity: String,
    val blocking: Boolean,
    val status: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("meter_capture_id") val meterCaptureId: String? = null,
    @SerialName("policy_version") val policyVersion: String? = null,
    @SerialName("review_note") val reviewNote: String? = null,
    @SerialName("reviewed_at") val reviewedAt: String? = null,
    @SerialName("created_at") val createdAt: String,
    val evidence: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class SyncMeterCaptureDto(
    /** The device-generated capture id (also the local capture's id). */
    val id: String,
    /** Null for a DAILY reading taken outside a job (METER_DAILY_READING): it names only its machine. */
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("machine_id") val machineId: String,
    val kind: String,
    @SerialName("capture_mode") val captureMode: String,
    val reading: String,
    val state: String,
    @SerialName("gps_status") val gpsStatus: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("location_captured_at") val locationCapturedAt: String? = null,
    @SerialName("photo_attachment_id") val photoAttachmentId: String? = null,
    @SerialName("photo_sha256") val photoSha256: String? = null,
    @SerialName("ocr_value") val ocrValue: String? = null,
    @SerialName("ocr_confidence") val ocrConfidence: Double? = null,
    @SerialName("manually_corrected") val manuallyCorrected: Boolean,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("supersedes_id") val supersedesId: String? = null,
    @SerialName("tracker_comparison") val trackerComparison: JsonObject? = null,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("sync_revision") val syncRevision: Long,
    @SerialName("review_status") val reviewStatus: String = "NONE",
    val findings: List<FindingDto> = emptyList(),
)

@Serializable
data class SyncMeterResetDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("old_reading") val oldReading: String,
    @SerialName("new_reading") val newReading: String,
    @SerialName("effective_at") val effectiveAt: String,
    val reason: String,
    val status: String,
    @SerialName("evidence_attachment_id") val evidenceAttachmentId: String? = null,
    @SerialName("requested_by") val requestedBy: String? = null,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("sync_revision") val syncRevision: Long,
)

@Serializable
data class SyncJobActivityDto(
    val id: String,
    @SerialName("job_id") val jobId: String,
    @SerialName("client_id") val clientId: String,
    @SerialName("activity_type") val activityType: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String? = null,
    @SerialName("duration_minutes") val durationMinutes: Long? = null,
    val billable: Boolean,
    val note: String? = null,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("sync_revision") val syncRevision: Long,
)

@Serializable
data class SyncAcknowledgementDto(
    val id: String,
    @SerialName("job_id") val jobId: String,
    @SerialName("client_id") val clientId: String,
    val method: String,
    @SerialName("signer_name") val signerName: String,
    @SerialName("signer_phone") val signerPhone: String? = null,
    @SerialName("acknowledged_hours") val acknowledgedHours: String? = null,
    @SerialName("signature_attachment_id") val signatureAttachmentId: String? = null,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("sync_revision") val syncRevision: Long,
)

@Serializable
data class SyncExpenseDto(
    val id: String,
    @SerialName("client_id") val clientId: String? = null,
    @SerialName("category_id") val categoryId: String,
    val description: String,
    val supplier: String? = null,
    val amount: String,
    val currency: String,
    @SerialName("paid_from") val paidFrom: String,
    val status: String,
    @SerialName("decision_note") val decisionNote: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("incurred_at") val incurredAt: String,
    @SerialName("submitted_at") val submittedAt: String,
    @SerialName("submitted_by") val submittedBy: String? = null,
    @SerialName("custodian_staff_id") val custodianStaffId: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("gps_status") val gpsStatus: String? = null,
    @SerialName("gps_accuracy_m") val gpsAccuracyM: Double? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("receipt_required") val receiptRequired: Boolean,
    val source: String,
    @SerialName("receipt_attachment_ids") val receiptAttachmentIds: List<String> = emptyList(),
    @SerialName("approval_request_id") val approvalRequestId: String? = null,
    @SerialName("sync_revision") val syncRevision: Long,
)

@Serializable
data class SyncFuelEventDto(
    val id: String,
    @SerialName("client_id") val clientId: String? = null,
    @SerialName("event_type") val eventType: String,
    val litres: String,
    @SerialName("unit_price") val unitPrice: String? = null,
    @SerialName("attributed_cost") val attributedCost: String,
    val currency: String,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("expense_id") val expenseId: String? = null,
    @SerialName("meter_reading") val meterReading: String? = null,
    val supplier: String? = null,
    val note: String? = null,
    @SerialName("occurred_at") val occurredAt: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    val source: String,
    @SerialName("sync_revision") val syncRevision: Long,
)

/** `HireAllocationDto`: the part of a collection the office allocated to an invoice. */
@Serializable
data class HireAllocationDto(
    val id: String,
    @SerialName("invoice_id") val invoiceId: String,
    val amount: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("released_at") val releasedAt: String? = null,
    @SerialName("release_reason") val releaseReason: String? = null,
)

@Serializable
data class SyncCashCollectionDto(
    val id: String,
    @SerialName("client_id") val clientId: String? = null,
    @SerialName("customer_id") val customerId: String,
    val amount: String,
    val currency: String,
    val method: String,
    val status: String,
    @SerialName("decision_note") val decisionNote: String? = null,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("received_by_staff_id") val receivedByStaffId: String? = null,
    @SerialName("recorded_at") val recordedAt: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("verified_at") val verifiedAt: String? = null,
    @SerialName("verified_by") val verifiedBy: String? = null,
    val source: String,
    val allocations: List<HireAllocationDto> = emptyList(),
    @SerialName("sync_revision") val syncRevision: Long,
)

@Serializable
data class SyncCashHandoverDto(
    val id: String,
    @SerialName("client_id") val clientId: String? = null,
    @SerialName("staff_member_id") val staffMemberId: String,
    val amount: String,
    val currency: String,
    val status: String,
    @SerialName("decision_note") val decisionNote: String? = null,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("handed_at") val handedAt: String,
    @SerialName("recorded_at") val recordedAt: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("verified_at") val verifiedAt: String? = null,
    @SerialName("verified_by") val verifiedBy: String? = null,
    val source: String,
    @SerialName("sync_revision") val syncRevision: Long,
)

/** `CashReconciliationDto` (`GET /tenant/cash/custody/me/reconciliation`, online only). */
@Serializable
data class CashReconciliationDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    val currency: String,
    val timezone: String,
    val days: List<CashReconciliationDayDto> = emptyList(),
)

/** One day: outstanding = opening + floats_issued + collections - approved_spending - verified_handovers. */
@Serializable
data class CashReconciliationDayDto(
    val day: String,
    val opening: String,
    @SerialName("floats_issued") val floatsIssued: String,
    val collections: String,
    @SerialName("approved_spending") val approvedSpending: String,
    @SerialName("verified_handovers") val verifiedHandovers: String,
    val outstanding: String,
    @SerialName("claimed_unverified_handovers") val claimedUnverifiedHandovers: String,
    @SerialName("pending_spending") val pendingSpending: String,
    @SerialName("unverified_collections") val unverifiedCollections: String,
    @SerialName("outstanding_if_claims_verified") val outstandingIfClaimsVerified: String,
)

/** Offline `METER_RESET_REQUEST` payload (`ResetIn` + `evidence_upload_id`, filled in when the photo upload completes). */
@Serializable
data class MeterResetPayload(
    @SerialName("machine_id") val machineId: String,
    @SerialName("old_reading") val oldReading: String,
    @SerialName("new_reading") val newReading: String,
    @SerialName("effective_at") val effectiveAt: String,
    val reason: String,
    @SerialName("evidence_upload_id") val evidenceUploadId: String? = null,
    @SerialName("evidence_attachment_id") val evidenceAttachmentId: String? = null,
)
