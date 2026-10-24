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
