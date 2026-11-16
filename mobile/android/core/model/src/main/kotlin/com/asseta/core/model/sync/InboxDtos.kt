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

    /** CASH_TRANSFER, CASH_TRANSFER_ACKNOWLEDGEMENT and CASH_FLOAT_ACKNOWLEDGEMENT. */
    const val OP_CASH_TRANSFER = "OP_CASH_TRANSFER"
    const val OP_HOURS_PURCHASE = "OP_HOURS_PURCHASE"

    /** CASH_RETENTION_REQUEST ("Ask to keep cash" offline). */
    const val OP_CASH_RETENTION_REQUEST = "OP_CASH_RETENTION_REQUEST"
    const val OP_HOURS_TRANSFER_REQUEST = "OP_HOURS_TRANSFER_REQUEST"

    /** METER_CAPTURE accepts kind DAILY with machine_id. */
    const val METER_DAILY_READING = "METER_DAILY_READING"
    const val OP_METER_BASELINE = "OP_METER_BASELINE"
    const val OP_METER_CORRECTION = "OP_METER_CORRECTION"

    /**
     * DEC-031 D2: CASH_HANDOVER accepts method, deposit_account_id and evidence_upload_ids (blob purpose
     * REMITTANCE_EVIDENCE); SyncData carries deposit_accounts.
     */
    const val REMITTANCE_DETAILS_V1 = "REMITTANCE_DETAILS_V1"

    /**
     * DEC-032 Phase 3: CASH_COLLECTION accepts `purchase_id`, CASH_HANDOVER `partial_reason` and `partial_reason_id`,
     * HOURS_TRANSFER_REQUEST `evidence_upload_ids` (blob ADJUSTMENT_EVIDENCE).
     */
    const val CASH_DETAILS_V2 = "CASH_DETAILS_V2"

    /**
     * DEC-033 petty cash: SyncData.petty_cash_* (full snapshots), EXPENSE paid_from PETTY_CASH, the PETTY_CASH_* operations
     * (blob PETTY_CASH_EVIDENCE). Announced only while the tenant uses petty cash.
     */
    const val OP_PETTY_CASH = "OP_PETTY_CASH"

    /** SyncData.petty_cash_witnesses: who may witness a count (never me), so a witnessed count is recorded offline. */
    const val SYNC_PETTY_CASH_WITNESSES = "SYNC_PETTY_CASH_WITNESSES"

    /**
     * SyncData.hours_prices and customer_discounts (full snapshots): the phone shows the total of an hours sale as the
     * hours are typed, offline, with the server's price rule.
     */
    const val SYNC_HOURS_PRICES = "SYNC_HOURS_PRICES"

    /** PETTY_CASH_ADVANCE: the fund's holder hands out an advance offline (policy advances_enabled). */
    const val OP_PETTY_CASH_ADVANCE = "OP_PETTY_CASH_ADVANCE"

    /** ADR-008: MACHINE_REPORT; SyncData.machine_report_* and my_machine_reports (always announced). */
    const val OP_MACHINE_REPORT = "OP_MACHINE_REPORT"

    /** ADR-008: CREDIT_INVOICE_PAYMENT; SyncData.open_credit_invoices (while customer hours are on). */
    const val OP_CREDIT_INVOICE_PAYMENT = "OP_CREDIT_INVOICE_PAYMENT"

    /** ADR-008: HOURS_PURCHASE accepts a CREDIT payment line (registered customers only). */
    const val OP_HOURS_SALE_CREDIT = "OP_HOURS_SALE_CREDIT"
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
    /** DEC-033: the fund (and advance) that paid, and why a human must look at it (OVERSPEND, ...). */
    @SerialName("petty_cash_fund_id") val pettyCashFundId: String? = null,
    @SerialName("petty_cash_advance_id") val pettyCashAdvanceId: String? = null,
    @SerialName("control_flags") val controlFlags: List<String> = emptyList(),
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
    @SerialName("expense_id") val expenseId: String? = null,
    @SerialName("meter_reading") val meterReading: String? = null,
    val supplier: String? = null,
    val note: String? = null,
    @SerialName("occurred_at") val occurredAt: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    val source: String,
    @SerialName("sync_revision") val syncRevision: Long,
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
    @SerialName("collection_number") val collectionNumber: String? = null,
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
    @SerialName("remittance_number") val remittanceNumber: String? = null,
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
