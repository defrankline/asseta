package com.asseta.core.model.sync

import com.asseta.core.model.DecimalAmount
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * Server-owned entities delivered by bootstrap/changes. Only the fields the supervisor app uses are typed; unknown
 * fields are ignored (additive server changes never break the app). Money/hours stay decimal strings.
 */
@Serializable
data class JobDto(
    val id: String,
    @SerialName("job_number") val jobNumber: String,
    @SerialName("contract_id") val contractId: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    @SerialName("supervisor_id") val supervisorId: String? = null,
    val status: String,
    val version: Long,
    @SerialName("planned_start") val plannedStart: String,
    @SerialName("planned_end") val plannedEnd: String? = null,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("standby_treatment") val standbyTreatment: String? = null,
    /** Contract currency of the job (rates); a hint for the tenant currency on the device. */
    val currency: String? = null,
    /** Why the job was cancelled (a declined field request carries the owner's reason). */
    @SerialName("cancellation_reason") val cancellationReason: String? = null,
    /** Set when a supervisor requested the job from the field (`JOB_REQUEST`). */
    @SerialName("requested_by_staff_id") val requestedByStaffId: String? = null,
    @SerialName("request_note") val requestNote: String? = null,
)

/**
 * `FieldContractDto` (listFieldContracts, `GET /tenant/field/contracts`): an active contract a supervisor can request
 * a job under, with the customer and site names.
 */
@Serializable
data class FieldContractDto(
    val id: String,
    @SerialName("contract_number") val contractNumber: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    @SerialName("job_site_name") val jobSiteName: String? = null,
    val currency: String? = null,
    @SerialName("starts_on") val startsOn: String? = null,
    @SerialName("ends_on") val endsOn: String? = null,
    val reference: String? = null,
)

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
data class ContractDto(
    val id: String,
    @SerialName("contract_number") val contractNumber: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    val status: String,
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
