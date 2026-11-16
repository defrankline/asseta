package com.asseta.core.model.sync

import com.asseta.core.model.DecimalAmount
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class MachineDto(
    val id: String,
    @SerialName("asset_code") val assetCode: String,
    val name: String,
    @SerialName("meter_decimal_places") val meterDecimalPlaces: Int,
    val status: String,
    val version: Long,
    val manufacturer: String? = null,
    val model: String? = null,
    @SerialName("serial_number") val serialNumber: String? = null,
)

@Serializable
data class JobSiteDto(
    val id: String,
    val code: String,
    val name: String,
    val address: String? = null,
    @SerialName("is_active") val isActive: Boolean = true,
    val center: JsonObject? = null,
)

@Serializable
data class CustomerDto(
    val id: String,
    val code: String,
    val name: String,
    @SerialName("contact_name") val contactName: String? = null,
    @SerialName("contact_phone") val contactPhone: String? = null,
    @SerialName("is_active") val isActive: Boolean = true,
)

@Serializable
data class StaffDto(
    val id: String,
    @SerialName("full_name") val fullName: String,
    val kind: String,
    @SerialName("is_active") val isActive: Boolean = true,
)

/** Expense category (bootstrap: active only; deltas carry deactivations as `is_active=false`). */
@Serializable
data class ExpenseCategoryDto(
    val id: String,
    val code: String,
    val name: String,
    @SerialName("is_active") val isActive: Boolean = true,
    @SerialName("sync_revision") val syncRevision: Long = 0,
    val version: Long = 1,
)

/**
 * The signed-in supervisor's server-computed cash custody per currency (always current, not a delta):
 * `outstanding` = floats + collections - approved spending - verified handovers; claimed handovers and expenses awaiting
 * approval are reported separately and are not deducted until the office verifies/approves them.
 */
@Serializable
data class CashCustodyBalanceDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    val currency: String,
    val outstanding: DecimalAmount,
    @SerialName("claimed_unverified_handovers") val claimedUnverifiedHandovers: DecimalAmount,
    @SerialName("pending_spending") val pendingSpending: DecimalAmount,
    @SerialName("as_of") val asOf: String,
)
