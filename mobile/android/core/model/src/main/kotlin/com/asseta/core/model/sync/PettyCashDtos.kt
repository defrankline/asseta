package com.asseta.core.model.sync

import com.asseta.core.model.DecimalAmount
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * DEC-033 petty cash in the field app (sync capability OP_PETTY_CASH). The pull carries the caller's funds with the
 * server's ledger figures, money waiting for the caller's acknowledgement, holder changes handing the caller a fund and
 * the advances not cleared yet: full snapshots every pull (contracts/openapi.json `PettyCashFundDto`,
 * `PettyCashMovementDto`, `PettyCashHolderChangeDto`, `PettyCashAdvanceDto`). Money stays decimal text.
 */

object PettyCashOps {
    const val ACKNOWLEDGEMENT = "PETTY_CASH_ACKNOWLEDGEMENT"
    const val TOP_UP_REQUEST = "PETTY_CASH_TOP_UP_REQUEST"
    const val RETURN = "PETTY_CASH_RETURN"
    const val COUNT = "PETTY_CASH_COUNT"
    const val ADVANCE_CLEARANCE = "PETTY_CASH_ADVANCE_CLEARANCE"
    const val HOLDER_CHANGE_ACKNOWLEDGEMENT = "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT"

    val ALL = listOf(ACKNOWLEDGEMENT, TOP_UP_REQUEST, RETURN, COUNT, ADVANCE_CLEARANCE, HOLDER_CHANGE_ACKNOWLEDGEMENT)

    /** `EXPENSE.paid_from` of an expense paid from a fund. */
    const val PAID_FROM = "PETTY_CASH"

    const val FUNDING = "FUNDING"
    const val TOP_UP = "TOP_UP"
}

/** `PettyCashBalanceDto`: a fund's ledger now, as the server computed it (the phone never recomputes it). */
@Serializable
data class PettyCashBalanceDto(
    @SerialName("fund_id") val fundId: String,
    val currency: String,
    @SerialName("approved_limit") val approvedLimit: String,
    @SerialName("low_balance_level") val lowBalanceLevel: String? = null,
    val balance: String,
    @SerialName("available_to_spend") val availableToSpend: String,
    @SerialName("below_low_balance") val belowLowBalance: Boolean,
    @SerialName("pending_spending") val pendingSpending: String,
    @SerialName("awaiting_acknowledgement") val awaitingAcknowledgement: String,
    @SerialName("returns_claimed") val returnsClaimed: String,
    @SerialName("advances_outstanding") val advancesOutstanding: String = "0",
    @SerialName("last_count_at") val lastCountAt: String? = null,
    @SerialName("next_count_due_at") val nextCountDueAt: String? = null,
    @SerialName("as_of") val asOf: String,
)

/** `PettyCashFundDto`: an active fund the caller holds, with its balance. */
@Serializable
data class PettyCashFundDto(
    val id: String,
    val code: String,
    val name: String,
    @SerialName("holder_staff_id") val holderStaffId: String,
    @SerialName("holder_staff_name") val holderStaffName: String? = null,
    @SerialName("job_site_name") val jobSiteName: String? = null,
    val currency: String,
    @SerialName("approved_limit") val approvedLimit: String,
    @SerialName("is_active") val isActive: Boolean = true,
    val balance: PettyCashBalanceDto? = null,
)

/** `PettyCashMovementDto`: a funding or top-up issued to the caller, waiting for the acknowledgement. */
@Serializable
data class PettyCashMovementDto(
    val id: String,
    val number: String,
    @SerialName("fund_id") val fundId: String,
    @SerialName("petty_cash_fund_name") val fundName: String? = null,
    val kind: String,
    val status: String,
    val amount: String,
    val currency: String,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("issued_by") val issuedBy: String? = null,
    @SerialName("issued_by_name") val issuedByName: String? = null,
    @SerialName("issued_at") val issuedAt: String? = null,
    @SerialName("created_at") val createdAt: String,
)

/** `PettyCashHolderChangeDto`: a fund being handed to the caller (the old holder stays accountable until accepted). */
@Serializable
data class PettyCashHolderChangeDto(
    val id: String,
    @SerialName("fund_id") val fundId: String,
    @SerialName("petty_cash_fund_name") val fundName: String? = null,
    @SerialName("from_staff_id") val fromStaffId: String,
    @SerialName("from_staff_name") val fromStaffName: String? = null,
    @SerialName("to_staff_id") val toStaffId: String,
    val status: String,
    val note: String? = null,
    @SerialName("requested_by_name") val requestedByName: String? = null,
    @SerialName("requested_at") val requestedAt: String,
)

/** `PettyCashAdvanceDto`: cash out of a fund before a purchase, cleared with expenses and the change. */
@Serializable
data class PettyCashAdvanceDto(
    val id: String,
    val number: String,
    @SerialName("fund_id") val fundId: String,
    @SerialName("petty_cash_fund_name") val fundName: String? = null,
    @SerialName("recipient_staff_id") val recipientStaffId: String,
    @SerialName("recipient_staff_name") val recipientStaffName: String? = null,
    val amount: String,
    val currency: String,
    val purpose: String,
    val status: String,
    @SerialName("issued_at") val issuedAt: String,
    @SerialName("due_at") val dueAt: String,
    val overdue: Boolean = false,
    @SerialName("approved_spending") val approvedSpending: String = "0",
    @SerialName("pending_spending") val pendingSpending: String = "0",
    val remaining: String = "0",
)

/** `PETTY_CASH_ACKNOWLEDGEMENT`: the holder's answer to a funding or top-up (a dispute carries no amount). */
@Serializable
data class PettyCashAckPayload(
    @SerialName("movement_id") val movementId: String,
    val acknowledged: Boolean,
    @SerialName("amount_received") val amountReceived: DecimalAmount? = null,
    val note: String? = null,
)

/** `PETTY_CASH_TOP_UP_REQUEST`: no amount = the server's imprest suggestion; above the cap needs the reason. */
@Serializable
data class PettyCashTopUpPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("fund_id") val fundId: String,
    val amount: DecimalAmount? = null,
    val note: String? = null,
    @SerialName("above_cap_reason") val aboveCapReason: String? = null,
)

/** `PETTY_CASH_RETURN` (`PettyCashReturnIn` + `evidence_upload_ids`, filled in as each photo upload completes). */
@Serializable
data class PettyCashReturnPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("fund_id") val fundId: String,
    val amount: DecimalAmount,
    @SerialName("deposit_account_id") val depositAccountId: String? = null,
    val method: String? = null,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("evidence_upload_ids") val evidenceUploadIds: List<String> = emptyList(),
)

/** `PETTY_CASH_COUNT` (`PettyCashCountIn` + `evidence_upload_ids`); [witnessUserId] is a login, not a staff record. */
@Serializable
data class PettyCashCountPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("fund_id") val fundId: String,
    @SerialName("counted_amount") val countedAmount: DecimalAmount,
    @SerialName("witness_user_id") val witnessUserId: String? = null,
    val note: String? = null,
    @SerialName("evidence_upload_ids") val evidenceUploadIds: List<String> = emptyList(),
)

/** `PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT`: the new holder accepts or declines the fund. */
@Serializable
data class PettyCashHolderChangePayload(
    @SerialName("holder_change_id") val holderChangeId: String,
    val accept: Boolean,
    val note: String? = null,
)

/** `PETTY_CASH_ADVANCE_CLEARANCE`: the fund's holder takes the change back. */
@Serializable
data class PettyCashAdvanceClearPayload(
    @SerialName("advance_id") val advanceId: String,
    @SerialName("change_returned") val changeReturned: DecimalAmount,
    val note: String? = null,
)

/** `PersonDto` (listTenantPeople): a colleague's login and display name (the count witness search). */
@Serializable
data class PersonDto(@SerialName("user_id") val userId: String, @SerialName("display_name") val displayName: String)
