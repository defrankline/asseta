package com.asseta.core.model.sync

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
