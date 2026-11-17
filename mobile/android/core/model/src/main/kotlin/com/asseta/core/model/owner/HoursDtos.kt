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
    val currency: String? = null,
    val allocations: List<PurchaseAllocationDto> = emptyList(),
    // ADR-008: the order's amount, its payment parts and its CREDIT part with the credit invoice it created.
    val amount: String? = null,
    @SerialName("effective_rate") val effectiveRate: String? = null,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    val payments: List<PurchasePaymentDto> = emptyList(),
    @SerialName("credit_amount") val creditAmount: String? = null,
    @SerialName("credit_invoice") val creditInvoice: com.asseta.core.model.sync.CreditInvoiceSummaryDto? = null,
    /** The CREDIT part: AWAITING_ACTIVATION, ACTIVATED or REJECTED (null without one). */
    @SerialName("credit_status") val creditStatus: String? = null,
)

/** `PurchaseAllocationDto`: money of one customer payment counted towards a purchase ([releasedAt]: no longer counted). */
@Serializable
data class PurchaseAllocationDto(
    val id: String,
    @SerialName("payment_id") val paymentId: String,
    val amount: String,
    @SerialName("released_at") val releasedAt: String? = null,
    @SerialName("payment_status") val paymentStatus: String? = null,
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
    @SerialName("awaiting_activation") val awaitingActivation: String,
    val refunded: String = "0",
    /** Net approved corrections, signed. */
    val corrected: String = "0",
)

/** `HoursStatementLineDto`: one ledger entry of the period ([hours] signed). */
@Serializable
data class HoursStatementLineDto(
    val day: String,
    @SerialName("occurred_at") val occurredAt: String,
    @SerialName("entry_type") val entryType: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    val hours: String,
    val reason: String? = null,
)

/** `HoursStatementUsageDto`: hours used on one day by one approved machine report. */
@Serializable
data class HoursStatementUsageDto(
    val day: String,
    @SerialName("machine_report_id") val machineReportId: String?,
    @SerialName("machine_report_number") val machineReportNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val hours: String,
)

/** `HoursStatementDto` (getCustomerHoursStatement), without the purchases the app does not show. */
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
    val lines: List<HoursStatementLineDto> = emptyList(),
    @SerialName("pdf_path") val pdfPath: String,
)
