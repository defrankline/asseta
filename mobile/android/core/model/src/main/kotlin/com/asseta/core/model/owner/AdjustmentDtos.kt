package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * `AdjustmentRequestDto` (DEC-032 Phase 2): a proposed correction, refund, reversal or invoice void. [effects] is open:
 * the forecast while PROPOSED (or `{refused: code}`), what the approval did once decided.
 */
@Serializable
data class AdjustmentRequestDto(
    val id: String,
    @SerialName("request_type") val requestType: String,
    val status: String,
    @SerialName("request_number") val requestNumber: String? = null,
    @SerialName("original_type") val originalType: String? = null,
    @SerialName("original_id") val originalId: String? = null,
    @SerialName("original_reference") val originalReference: String? = null,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("purchase_id") val purchaseId: String? = null,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    val hours: String? = null,
    val amount: String? = null,
    val currency: String? = null,
    val settlement: String? = null,
    val reason: String = "",
    @SerialName("reason_label") val reasonLabel: String? = null,
    @SerialName("evidence_attachment_ids") val evidenceAttachmentIds: List<String> = emptyList(),
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String? = null,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    val effects: JsonObject = JsonObject(emptyMap()),
) {
    companion object {
        const val PROPOSED = "PROPOSED"
        const val WITHDRAWN = "WITHDRAWN"
        const val ZERO_AMOUNT_ACTIVATION = "ZERO_AMOUNT_ACTIVATION"
        const val HOURS_CORRECTION = "HOURS_CORRECTION"
        const val HOURS_REFUND = "HOURS_REFUND"
        const val INVOICE_VOID = "INVOICE_VOID"
    }
}

/** `AdjustmentDecisionIn`: APPROVE or REJECT with an optional note. */
@Serializable
data class AdjustmentDecisionIn(val decision: String, val note: String? = null) {
    companion object {
        const val APPROVE = "APPROVE"
        const val REJECT = "REJECT"
    }
}

/** `AdjustmentWithdrawIn`: 3..1000 characters; proposer only. */
@Serializable
data class AdjustmentWithdrawIn(val reason: String)

/** `CustomerPaymentDto`, only what marks a payment as reversed. */
@Serializable
data class PaymentReversalDto(
    val id: String,
    @SerialName("reversed_at") val reversedAt: String? = null,
    @SerialName("reversal_id") val reversalId: String? = null,
)
