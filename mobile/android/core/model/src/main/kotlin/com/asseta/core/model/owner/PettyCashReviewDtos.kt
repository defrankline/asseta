package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * `PettyCashMovementDto` (listPettyCashMovements / getPettyCashMovement / decidePettyCashMovement), the part the Owner
 * app reviews: a FUNDING or TOP_UP is PROPOSED until someone other than the proposer and the fund's holder approves it.
 */
@Serializable
data class PettyCashMovementReviewDto(
    val id: SerializableUuid,
    val number: String,
    @SerialName("fund_id") val fundId: SerializableUuid,
    @SerialName("petty_cash_fund_name") val fundName: String? = null,
    val kind: String,
    val status: String,
    @SerialName("holder_staff_id") val holderStaffId: SerializableUuid,
    @SerialName("holder_staff_name") val holderStaffName: String? = null,
    val amount: DecimalAmount,
    val currency: String,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("suggested_amount") val suggestedAmount: DecimalAmount? = null,
    @SerialName("cap_amount") val capAmount: DecimalAmount? = null,
    @SerialName("above_cap_reason") val aboveCapReason: String? = null,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `PettyCashAdjustmentDto`: a signed change to a fund balance, PENDING until someone else approves it. */
@Serializable
data class PettyCashAdjustmentReviewDto(
    val id: SerializableUuid,
    val number: String,
    @SerialName("fund_id") val fundId: SerializableUuid,
    @SerialName("petty_cash_fund_name") val fundName: String? = null,
    val amount: DecimalAmount,
    val currency: String,
    val reason: String,
    val status: String,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `TopUpExpenseDto`: an approved expense a top-up proposal was based on. */
@Serializable
data class TopUpExpenseDto(
    val id: SerializableUuid,
    val description: String,
    val amount: DecimalAmount,
    @SerialName("incurred_at") val incurredAt: String,
)

/** `PettyCashDecisionIn`: approve or reject (a rejection carries the reason). */
@Serializable
data class PettyCashDecisionIn(val approve: Boolean, val note: String? = null)

/** One movement with the expenses behind it ([expensesFailed] when they could not be read, not the same as none). */
@Serializable
data class PettyCashMovementReview(
    val movement: PettyCashMovementReviewDto,
    val expenses: List<TopUpExpenseDto> = emptyList(),
    val expensesFailed: Boolean = false,
)
