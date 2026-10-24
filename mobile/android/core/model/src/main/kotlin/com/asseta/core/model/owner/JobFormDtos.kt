package com.asseta.core.model.owner

import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * `JobIn` (createJob, `POST /tenant/jobs`): the Owner app's "New job" form. Money, hours and percentages are exact
 * decimal strings. [hourlyRate] is null for the rate card (the server resolves the card in force at [plannedStart],
 * `422 NO_RATE` when none applies). The standby/fee/discount/tax terms take the web form's defaults.
 */
@Serializable
data class JobIn(
    @SerialName("contract_id") val contractId: String,
    @SerialName("job_number") val jobNumber: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("planned_start") val plannedStart: String,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    @SerialName("supervisor_id") val supervisorId: String? = null,
    @SerialName("planned_end") val plannedEnd: String? = null,
    @SerialName("hourly_rate") val hourlyRate: String? = null,
    @SerialName("minimum_hours") val minimumHours: String? = null,
    @SerialName("standby_treatment") val standbyTreatment: String = "EXCLUDED",
    @SerialName("mobilization_fee") val mobilizationFee: String = "0",
    @SerialName("discount_percent") val discountPercent: String = "0",
    @SerialName("tax_rate_percent") val taxRatePercent: String = "0",
)

/** `ContractDto` (listContracts): a customer contract to create a job under; [currency] prices its jobs. */
@Serializable
data class ContractDto(
    val id: SerializableUuid,
    @SerialName("contract_number") val contractNumber: String,
    @SerialName("customer_id") val customerId: SerializableUuid,
    val currency: String,
    val status: String,
    @SerialName("starts_on") val startsOn: String,
    @SerialName("job_site_id") val jobSiteId: SerializableUuid? = null,
    @SerialName("ends_on") val endsOn: String? = null,
    val reference: String? = null,
)

/** `StaffDto` (listStaff, `kind=SUPERVISOR`): a supervisor a job can be assigned to. */
@Serializable
data class StaffDto(
    val id: SerializableUuid,
    @SerialName("full_name") val fullName: String,
    val kind: String,
    @SerialName("is_active") val isActive: Boolean,
    val version: Long,
    @SerialName("employee_code") val employeeCode: String? = null,
    val phone: String? = null,
    @SerialName("keycloak_subject") val keycloakSubject: String? = null,
    @SerialName("deactivated_at") val deactivatedAt: String? = null,
    @SerialName("deactivation_reason") val deactivationReason: String? = null,
)

/** `JobSiteDto` (listJobSites): where a job runs (empty = the contract's default site). */
@Serializable
data class JobSiteDto(
    val id: SerializableUuid,
    val code: String,
    val name: String,
    @SerialName("is_active") val isActive: Boolean,
    val address: String? = null,
    val center: JsonObject? = null,
)
