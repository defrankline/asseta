package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** `FuelEventDto` (listFuelEvents): a purchase, issue or usage; [attributedCost] is exact money in [currency]. */
@Serializable
data class FuelEventDto(
    val id: SerializableUuid,
    @SerialName("event_type") val eventType: String,
    val litres: DecimalAmount,
    @SerialName("attributed_cost") val attributedCost: DecimalAmount,
    val currency: String,
    @SerialName("occurred_at") val occurredAt: String,
    val source: String,
    @SerialName("client_id") val clientId: SerializableUuid? = null,
    @SerialName("unit_price") val unitPrice: DecimalAmount? = null,
    @SerialName("machine_id") val machineId: SerializableUuid? = null,
    @SerialName("job_id") val jobId: SerializableUuid? = null,
    @SerialName("expense_id") val expenseId: SerializableUuid? = null,
    @SerialName("meter_reading") val meterReading: DecimalAmount? = null,
    val supplier: String? = null,
    val note: String? = null,
    @SerialName("recorded_by") val recordedBy: SerializableUuid? = null,
)

/**
 * `CashSupervisorSummaryDto` (listCashSupervisorSummaries): one custodian x currency over a tenant-local period.
 * closing_outstanding = opening + floats_issued + collections - approved_spending - verified_handovers.
 */
@Serializable
data class CashSupervisorSummaryDto(
    @SerialName("staff_member_id") val staffMemberId: SerializableUuid,
    @SerialName("staff_name") val staffName: String,
    val currency: String,
    @SerialName("period_from") val periodFrom: String,
    @SerialName("period_to") val periodTo: String,
    val opening: DecimalAmount,
    @SerialName("floats_issued") val floatsIssued: DecimalAmount,
    val collections: DecimalAmount,
    @SerialName("approved_spending") val approvedSpending: DecimalAmount,
    @SerialName("verified_handovers") val verifiedHandovers: DecimalAmount,
    @SerialName("closing_outstanding") val closingOutstanding: DecimalAmount,
    @SerialName("claimed_unverified_handovers") val claimedUnverifiedHandovers: DecimalAmount,
    @SerialName("pending_spending") val pendingSpending: DecimalAmount,
    @SerialName("unverified_collections") val unverifiedCollections: DecimalAmount,
)

/**
 * `CashHandoverDto` (listCashHandovers / decideCashHandover): cash a supervisor handed to the office; [status] CLAIMED
 * until someone other than the recorder verifies (VERIFIED) or rejects (REJECTED) it.
 */
@Serializable
data class CashHandoverDto(
    val id: SerializableUuid,
    @SerialName("staff_member_id") val staffMemberId: SerializableUuid,
    val amount: DecimalAmount,
    val currency: String,
    @SerialName("handed_at") val handedAt: String,
    val status: String,
    val source: String,
    @SerialName("recorded_at") val recordedAt: String,
    @SerialName("client_id") val clientId: SerializableUuid? = null,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("recorded_by") val recordedBy: SerializableUuid? = null,
    @SerialName("verified_by") val verifiedBy: SerializableUuid? = null,
    @SerialName("verified_at") val verifiedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    /** What the office counted when verifying (null = the declared amount). */
    @SerialName("amount_received") val amountReceived: DecimalAmount? = null,
    /** The custodian's expected balance when the remittance was recorded. */
    @SerialName("expected_balance") val expectedBalance: DecimalAmount? = null,
    /** Unretained balance not remitted (PARTIAL_REMITTANCE); null = not flagged. */
    @SerialName("partial_shortfall") val partialShortfall: DecimalAmount? = null,
)

/**
 * `RemittanceDecisionIn` for decideCashHandover: [verified] true confirms the cash was received (with the
 * [amountReceived] actually counted; null = the declared amount), false disputes it.
 */
@Serializable
data class SettlementDecisionIn(
    val verified: Boolean,
    val note: String? = null,
    @SerialName("amount_received") val amountReceived: String? = null,
)

/** `CashFloatIn` for issueCashFloat: [amount] as an exact decimal string; the server stamps the time when absent. */
@Serializable
data class CashFloatIn(
    @SerialName("staff_member_id") val staffMemberId: String,
    val amount: String,
    val currency: String? = null,
    val note: String? = null,
    @SerialName("entry_type") val entryType: String = FLOAT_ISSUED,
) {
    companion object {
        const val FLOAT_ISSUED = "FLOAT_ISSUED"
    }
}

/** `CashCustodyEntryDto` (issueCashFloat). */
@Serializable
data class CashCustodyEntryDto(
    val id: SerializableUuid,
    @SerialName("staff_member_id") val staffMemberId: SerializableUuid,
    @SerialName("entry_type") val entryType: String,
    val amount: DecimalAmount,
    val currency: String,
    @SerialName("occurred_at") val occurredAt: String,
    val reference: String? = null,
    val note: String? = null,
)
