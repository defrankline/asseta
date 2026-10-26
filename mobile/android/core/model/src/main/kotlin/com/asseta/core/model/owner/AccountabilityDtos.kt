package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/*
 * Accountability decisions the Owner app lists under Approvals and decides (contracts/openapi.json). Ids stay strings
 * and money/hours decimal strings; unknown enum values are kept as text so newer servers never break the app.
 */

/** `DecisionIn` (discounts, credit, hours transfers/cancellations, write-offs, retentions, custody adjustments). */
@Serializable
data class DecisionIn(val approve: Boolean, val note: String? = null)

/** `MeterDecisionIn` (baselines, classifications, corrections): APPROVE or REJECT with a 5..2000 character note. */
@Serializable
data class MeterDecisionIn(val decision: String, val note: String) {
    companion object {
        const val APPROVE = "APPROVE"
        const val REJECT = "REJECT"
    }
}

/** `DiscountDto` (listCustomerDiscounts / decideCustomerDiscount). */
@Serializable
data class DiscountDto(
    val id: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    val percent: String,
    @SerialName("effective_from") val effectiveFrom: String,
    @SerialName("effective_to") val effectiveTo: String? = null,
    val reason: String,
    @SerialName("reason_code_id") val reasonCodeId: String? = null,
    val status: String,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    @SerialName("revoked_by") val revokedBy: String? = null,
    @SerialName("revoked_by_name") val revokedByName: String? = null,
    @SerialName("revoked_at") val revokedAt: String? = null,
    @SerialName("revoke_reason") val revokeReason: String? = null,
    val version: Long,
)

/** `CreditArrangementDto`. */
@Serializable
data class CreditArrangementDto(
    val id: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("limit_amount") val limitAmount: String,
    val currency: String,
    @SerialName("effective_from") val effectiveFrom: String,
    @SerialName("effective_to") val effectiveTo: String? = null,
    val terms: String? = null,
    val reason: String,
    @SerialName("reason_code_id") val reasonCodeId: String? = null,
    val status: String,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    @SerialName("revoked_by") val revokedBy: String? = null,
    @SerialName("revoked_by_name") val revokedByName: String? = null,
    @SerialName("revoked_at") val revokedAt: String? = null,
    @SerialName("revoke_reason") val revokeReason: String? = null,
    val version: Long,
)

/** `TransferDto` (hours transfer between machines). */
@Serializable
data class HoursTransferDto(
    val id: String,
    @SerialName("client_id") val clientId: String? = null,
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("from_machine_id") val fromMachineId: String,
    @SerialName("from_machine_code") val fromMachineCode: String? = null,
    @SerialName("from_machine_name") val fromMachineName: String? = null,
    @SerialName("to_machine_id") val toMachineId: String,
    @SerialName("to_machine_code") val toMachineCode: String? = null,
    @SerialName("to_machine_name") val toMachineName: String? = null,
    val hours: String,
    val reason: String,
    @SerialName("reason_code_id") val reasonCodeId: String? = null,
    val status: String,
    @SerialName("requested_by") val requestedBy: String? = null,
    @SerialName("requested_by_name") val requestedByName: String? = null,
    @SerialName("requested_at") val requestedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `CancellationDto` (hours purchase cancellation). */
@Serializable
data class HoursCancellationDto(
    val id: String,
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    val reason: String,
    @SerialName("reason_code_id") val reasonCodeId: String? = null,
    val status: String,
    @SerialName("requested_by") val requestedBy: String? = null,
    @SerialName("requested_by_name") val requestedByName: String? = null,
    @SerialName("requested_at") val requestedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `BaselineDto` (meter baseline proposal). */
@Serializable
data class BaselineDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val reading: String,
    val source: String,
    @SerialName("source_capture_id") val sourceCaptureId: String? = null,
    @SerialName("photo_attachment_id") val photoAttachmentId: String? = null,
    @SerialName("captured_at") val capturedAt: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    val note: String? = null,
    val status: String,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `ClassificationDto` (unallocated engine hours explained as non-customer work or an identified difference). */
@Serializable
data class ClassificationDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("start_at") val startAt: String,
    @SerialName("end_at") val endAt: String,
    @SerialName("start_ref") val startRef: String,
    @SerialName("end_ref") val endRef: String,
    val hours: String,
    val outcome: String,
    @SerialName("reason_id") val reasonId: String,
    @SerialName("reason_name") val reasonName: String? = null,
    val note: String,
    val status: String,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `CorrectionDto` (a reading correction awaiting a second person). */
@Serializable
data class CorrectionDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("superseded_capture_id") val supersededCaptureId: String,
    @SerialName("replacement_capture_id") val replacementCaptureId: String,
    @SerialName("old_reading") val oldReading: String,
    @SerialName("new_reading") val newReading: String,
    val reason: String,
    val status: String,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `CashVarianceDto` (declared vs received; a write-off is proposed then decided by another person). */
@Serializable
data class CashVarianceDto(
    val id: String,
    @SerialName("source_type") val sourceType: String,
    @SerialName("source_id") val sourceId: String,
    @SerialName("staff_member_id") val staffMemberId: String? = null,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    @SerialName("counterparty_staff_id") val counterpartyStaffId: String? = null,
    @SerialName("counterparty_staff_name") val counterpartyStaffName: String? = null,
    val currency: String,
    @SerialName("declared_amount") val declaredAmount: String,
    @SerialName("received_amount") val receivedAmount: String,
    val amount: String,
    val status: String,
    val outcome: String? = null,
    @SerialName("reason_id") val reasonId: String? = null,
    @SerialName("case_id") val caseId: String? = null,
    @SerialName("opened_at") val openedAt: String,
    @SerialName("opened_by") val openedBy: String? = null,
    @SerialName("opened_by_name") val openedByName: String? = null,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String? = null,
    @SerialName("proposal_note") val proposalNote: String? = null,
    @SerialName("resolved_by") val resolvedBy: String? = null,
    @SerialName("resolved_by_name") val resolvedByName: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("resolution_note") val resolutionNote: String? = null,
    /** SHORTFALL (less received than declared) or SURPLUS (more: "Surplus to explain"); null from older servers. */
    val kind: String? = null,
)

/** `CashRetentionDto` (a custodian may keep some cash instead of remitting it, once approved). */
@Serializable
data class CashRetentionDto(
    val id: String,
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    val amount: String,
    val currency: String,
    val reason: String,
    @SerialName("reason_id") val reasonId: String? = null,
    @SerialName("valid_until") val validUntil: String? = null,
    val status: String,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    /** The field form's id when the request came from the app (offline CASH_RETENTION_REQUEST). */
    @SerialName("client_id") val clientId: String? = null,
)

/** `CustodyAdjustmentDto` (a reversal or adjustment of a custodian's expected balance). */
@Serializable
data class CustodyAdjustmentDto(
    val id: String,
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    val kind: String,
    val amount: String,
    val currency: String,
    @SerialName("occurred_at") val occurredAt: String,
    val reason: String,
    @SerialName("reason_id") val reasonId: String? = null,
    @SerialName("reverses_entity_type") val reversesEntityType: String? = null,
    @SerialName("reverses_entity_id") val reversesEntityId: String? = null,
    val status: String,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `OverdueAmountDto`: cash still unremitted when the custodian was flagged. */
@Serializable
data class OverdueAmountDto(val currency: String, val amount: String)

/** `RemittanceOverdueDto` (REMITTANCE_OVERDUE): a custodian still holding unremitted cash past the daily cut-off. */
@Serializable
data class RemittanceOverdueDto(
    val id: String,
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    @SerialName("local_day") val localDay: String,
    @SerialName("cutoff_hour") val cutoffHour: Int,
    val amounts: List<OverdueAmountDto> = emptyList(),
    @SerialName("flagged_at") val flaggedAt: String,
    @SerialName("policy_version") val policyVersion: String,
    /** CUTOFF (daily cut-off, the default) or HELD_TOO_LONG (beyond the holding allowance, DEC-031 D3). */
    val reason: String = CUTOFF,
    /** When the oldest unremitted cash was received (HELD_TOO_LONG). */
    @SerialName("held_since") val heldSince: String? = null,
    /** The holding allowance that applied (HELD_TOO_LONG). */
    @SerialName("max_holding_days") val maxHoldingDays: Int? = null,
) {
    companion object {
        const val CUTOFF = "CUTOFF"
        const val HELD_TOO_LONG = "HELD_TOO_LONG"
    }
}

// --- accountability dashboard (getAccountabilitySummary) -------------------------------------------------------

@Serializable
data class CountAmountDto(val count: Int, val amount: String, val currency: String)

@Serializable
data class ApprovalsTileDto(
    @SerialName("approval_requests") val approvalRequests: Int,
    @SerialName("payments_to_verify") val paymentsToVerify: Int,
    @SerialName("remittances_to_verify") val remittancesToVerify: Int,
    @SerialName("cash_retentions") val cashRetentions: Int,
    @SerialName("custody_adjustments") val custodyAdjustments: Int,
    @SerialName("write_offs") val writeOffs: Int,
    val total: Int,
)

@Serializable
data class AttemptsTileDto(
    @SerialName("permission_denied") val permissionDenied: Int,
    @SerialName("segregation_of_duties") val segregationOfDuties: Int,
    @SerialName("window_days") val windowDays: Int,
)

@Serializable
data class CustodianCashDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_name") val staffName: String,
    val currency: String,
    val outstanding: String,
    @SerialName("in_transit_out") val inTransitOut: String,
    @SerialName("pending_floats") val pendingFloats: String,
    @SerialName("claimed_unverified_handovers") val claimedUnverifiedHandovers: String,
)

@Serializable
data class CashTileDto(
    val custodians: List<CustodianCashDto> = emptyList(),
    @SerialName("transfers_awaiting_acknowledgement") val transfersAwaitingAcknowledgement: List<CountAmountDto> = emptyList(),
    @SerialName("floats_awaiting_acknowledgement") val floatsAwaitingAcknowledgement: List<CountAmountDto> = emptyList(),
    @SerialName("remittances_awaiting_confirmation") val remittancesAwaitingConfirmation: List<CountAmountDto> = emptyList(),
    @SerialName("partial_remittances_in_window") val partialRemittancesInWindow: Int = 0,
    /** Tenant-local daily remittance cut-off hour; null = no cut-off. */
    @SerialName("remittance_cutoff_hour") val remittanceCutoffHour: Int? = null,
    /** Custodians flagged today for cash not remitted by the cut-off; null = no cut-off configured. */
    @SerialName("remittances_overdue_today") val remittancesOverdueToday: Int? = null,
)

@Serializable
data class PaymentsTileDto(@SerialName("awaiting_confirmation") val awaitingConfirmation: List<CountAmountDto> = emptyList())

@Serializable
data class DiscrepanciesTileDto(
    @SerialName("open_variances") val openVariances: List<CountAmountDto> = emptyList(),
    @SerialName("write_offs_proposed") val writeOffsProposed: Int = 0,
    @SerialName("sync_conflicts_unresolved") val syncConflictsUnresolved: Int = 0,
)

@Serializable
data class InvestigationsTileDto(val open: Int, @SerialName("in_review") val inReview: Int)

/**
 * `AccountabilitySummaryDto`. A tile is null when the tenant's OVERSIGHT policy hides it ([hiddenTiles]) or its module
 * is unavailable ([unavailableTiles]). The customer-hours and engine-hour tiles are server-defined objects.
 */
@Serializable
data class AccountabilitySummaryDto(
    @SerialName("as_of") val asOf: String,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("hidden_tiles") val hiddenTiles: List<String> = emptyList(),
    @SerialName("unavailable_tiles") val unavailableTiles: List<String> = emptyList(),
    /** Capabilities the tenant switched off (CUSTOMER_HOURS, ENGINE_HOURS, CASH_CUSTODY): their tiles/rows are hidden. */
    @SerialName("disabled_capabilities") val disabledCapabilities: List<String> = emptyList(),
    @SerialName("outstanding_approvals") val outstandingApprovals: ApprovalsTileDto? = null,
    val cash: CashTileDto? = null,
    val payments: PaymentsTileDto? = null,
    val discrepancies: DiscrepanciesTileDto? = null,
    val investigations: InvestigationsTileDto? = null,
    @SerialName("unauthorized_attempts") val unauthorizedAttempts: AttemptsTileDto? = null,
    @SerialName("customer_hours") val customerHours: JsonObject? = null,
    @SerialName("hours_awaiting_activation") val hoursAwaitingActivation: JsonObject? = null,
    @SerialName("engine_hours") val engineHours: JsonObject? = null,
    @SerialName("unexplained_hours") val unexplainedHours: JsonObject? = null,
    @SerialName("missing_daily_reports") val missingDailyReports: JsonObject? = null,
    /** DEC-031 R3: revenue differences to explain / decide (null while REVENUE_RECONCILIATION is off). */
    @SerialName("revenue_differences") val revenueDifferences: JsonObject? = null,
)
