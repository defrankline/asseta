package com.asseta.core.model.owner

import com.asseta.core.model.sync.MachineHoursDto
import com.asseta.core.model.sync.PurchaseTotalsDto
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** `HoursPurchaseDto` (getHoursPurchase / listHoursPurchases), the part the Owner app shows (read-only). */
@Serializable
data class OwnerHoursPurchaseDto(
    val id: String,
    @SerialName("purchase_number") val purchaseNumber: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val hours: String,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("cancelled_at") val cancelledAt: String? = null,
    val totals: PurchaseTotalsDto,
    val machines: List<MachineHoursDto> = emptyList(),
)

/** `HoursStatementTotalsDto`: movements inside the period (hours). */
@Serializable
data class HoursStatementTotalsDto(
    @SerialName("opening_balance") val openingBalance: String,
    val bought: String,
    val activated: String,
    val used: String,
    @SerialName("transferred_in") val transferredIn: String,
    @SerialName("transferred_out") val transferredOut: String,
    val expired: String,
    val cancelled: String,
    @SerialName("closing_balance") val closingBalance: String,
    @SerialName("provisional_at_close") val provisionalAtClose: String,
    @SerialName("awaiting_activation") val awaitingActivation: String,
)

/** `HoursStatementUsageDto`: hours used on one day for one job (DAILY drawdown or the FINAL allocation). */
@Serializable
data class HoursStatementUsageDto(
    val day: String,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val hours: String,
    val basis: String,
    @SerialName("job_running") val jobRunning: Boolean,
) {
    companion object {
        const val DAILY = "DAILY"
        const val FINAL = "FINAL"
    }
}

/** `HoursStatementDto` (getCustomerHoursStatement), without the ledger lines and purchases the app does not show. */
@Serializable
data class HoursStatementDto(
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("date_from") val dateFrom: String,
    @SerialName("date_to") val dateTo: String,
    val timezone: String,
    @SerialName("generated_at") val generatedAt: String,
    val totals: HoursStatementTotalsDto,
    val usage: List<HoursStatementUsageDto> = emptyList(),
    @SerialName("pdf_path") val pdfPath: String,
)
