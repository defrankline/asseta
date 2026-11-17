package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * ADR-008: machine reports, credit invoices and their offline operations (docs/api-machine-reports.md). Shared by the
 * Supervisor app (sync snapshots, MACHINE_REPORT / CREDIT_INVOICE_PAYMENT operations) and the Owner app (online reads
 * and decisions). Hours and money are decimal strings, as on the wire.
 */

/** `MachineReportReasonDto`: a non-productive reason of the tenant's list. */
@Serializable
data class MachineReportReasonDto(
    val id: String,
    val code: String,
    val name: String,
    val description: String? = null,
    @SerialName("is_active") val isActive: Boolean = true,
    val version: Int = 0,
)

/** `MachineReportStatusDto`: where one machine stands for its next report. */
@Serializable
data class MachineReportStatusDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("meter_decimal_places") val meterDecimalPlaces: Int = 1,
    /** The reading the next report starts from (last approved report, else the approved baseline or a reset). */
    @SerialName("previous_reading") val previousReading: String? = null,
    @SerialName("previous_at") val previousAt: String? = null,
    /** REPORT, BASELINE or RESET; null when the machine has no starting reading yet. */
    @SerialName("previous_source") val previousSource: String? = null,
    @SerialName("last_approved_reading") val lastApprovedReading: String? = null,
    @SerialName("last_approved_at") val lastApprovedAt: String? = null,
    @SerialName("last_report_at") val lastReportAt: String? = null,
    @SerialName("days_since_report") val daysSinceReport: Int? = null,
    @SerialName("pending_report_id") val pendingReportId: String? = null,
    @SerialName("pending_report_number") val pendingReportNumber: String? = null,
    @SerialName("rejected_report_id") val rejectedReportId: String? = null,
)

/** `AvailableHoursDto`: hours a customer can still be given in a report (per machine when the scope is MACHINE). */
@Serializable
data class AvailableHoursDto(
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String? = null,
    val remaining: String,
    val reserved: String,
    val available: String,
)

/** `LotDto`: the order an approved customer line drew its hours from. */
@Serializable
data class ReportLotDto(
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    val hours: String,
)

/** `MachineReportLineDto`: CUSTOMER (customer + hours) or NON_PRODUCTIVE (reason + hours + note). */
@Serializable
data class MachineReportLineDto(
    val id: String,
    @SerialName("line_no") val lineNo: Int,
    val kind: String,
    @SerialName("customer_id") val customerId: String?,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("reason_id") val reasonId: String?,
    @SerialName("reason_code") val reasonCode: String? = null,
    @SerialName("reason_name") val reasonName: String? = null,
    val hours: String,
    val note: String?,
    /** SUBMITTED detail: the customer's available hours before this report. */
    @SerialName("available_hours") val availableHours: String? = null,
    val lots: List<ReportLotDto> = emptyList(),
) {
    companion object {
        const val CUSTOMER = "CUSTOMER"
        const val NON_PRODUCTIVE = "NON_PRODUCTIVE"
    }
}

/** `TrackerCheckDto`: tracker engine hours over the report period next to the meter's (approver aid). */
@Serializable
data class TrackerCheckDto(
    val available: Boolean,
    @SerialName("tracker_hours") val trackerHours: String?,
    @SerialName("meter_hours") val meterHours: String,
    /** Meter − tracker. */
    val difference: String?,
    @SerialName("tracker_from_at") val trackerFromAt: String? = null,
    @SerialName("tracker_to_at") val trackerToAt: String? = null,
)

/** `MachineReportDto`: one report (list rows and detail; [findings] and [tracker] only on the detail). */
@Serializable
data class MachineReportDto(
    val id: String,
    @SerialName("report_number") val reportNumber: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("capture_id") val captureId: String,
    @SerialName("start_source") val startSource: String,
    @SerialName("start_ref") val startRef: String,
    @SerialName("start_reading") val startReading: String,
    @SerialName("start_at") val startAt: String,
    @SerialName("end_reading") val endReading: String,
    @SerialName("end_at") val endAt: String,
    val hours: String,
    @SerialName("customer_hours") val customerHours: String,
    @SerialName("non_productive_hours") val nonProductiveHours: String,
    /** SUBMITTED, APPROVED or REJECTED. */
    val status: String,
    @SerialName("corrects_id") val correctsId: String?,
    @SerialName("corrected_by_id") val correctedById: String? = null,
    val note: String?,
    val source: String,
    @SerialName("submitted_by") val submittedBy: String?,
    @SerialName("submitted_by_name") val submittedByName: String? = null,
    @SerialName("submitted_at") val submittedAt: String,
    @SerialName("client_created_at") val clientCreatedAt: String?,
    @SerialName("decided_by") val decidedBy: String?,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String?,
    @SerialName("decision_note") val decisionNote: String?,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("photo_attachment_id") val photoAttachmentId: String? = null,
    @SerialName("capture_state") val captureState: String? = null,
    val findings: List<FindingDto> = emptyList(),
    val tracker: TrackerCheckDto? = null,
    val lines: List<MachineReportLineDto> = emptyList(),
) {
    companion object {
        const val SUBMITTED = "SUBMITTED"
        const val APPROVED = "APPROVED"
        const val REJECTED = "REJECTED"
    }
}

/** `CreditInvoicePaymentDto`: one recorded part payment of a credit invoice. */
@Serializable
data class CreditInvoicePaymentDto(
    val id: String,
    @SerialName("payment_id") val paymentId: String,
    val amount: String,
    val method: String,
    val reference: String?,
    @SerialName("collection_number") val collectionNumber: String? = null,
    @SerialName("payment_status") val paymentStatus: String,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("received_by_staff_id") val receivedByStaffId: String?,
    @SerialName("received_by_staff_name") val receivedByStaffName: String? = null,
    @SerialName("recorded_by") val recordedBy: String?,
    @SerialName("recorded_by_name") val recordedByName: String? = null,
    @SerialName("created_at") val createdAt: String,
    val counts: Boolean,
)

/** `CreditInvoiceDto`: the invoice of an order's CREDIT part (UNPAID, PART_PAID, PAID, CANCELLED). */
@Serializable
data class CreditInvoiceDto(
    val id: String,
    @SerialName("invoice_number") val invoiceNumber: String,
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val currency: String,
    val hours: String,
    @SerialName("unit_price") val unitPrice: String,
    val amount: String,
    val paid: String,
    @SerialName("paid_verified") val paidVerified: String,
    val balance: String,
    @SerialName("payment_terms_days") val paymentTermsDays: Int,
    @SerialName("issued_at") val issuedAt: String,
    @SerialName("due_date") val dueDate: String,
    val status: String,
    val overdue: Boolean,
    @SerialName("days_overdue") val daysOverdue: Int,
    @SerialName("created_by") val createdBy: String?,
    @SerialName("created_by_name") val createdByName: String? = null,
    val payments: List<CreditInvoicePaymentDto> = emptyList(),
) {
    companion object {
        const val UNPAID = "UNPAID"
        const val PART_PAID = "PART_PAID"
        const val PAID = "PAID"
        const val CANCELLED = "CANCELLED"
    }
}

/** `CreditInvoiceSummaryDto`: the invoice a sale's CREDIT part created (on the acked order). */
@Serializable
data class CreditInvoiceSummaryDto(
    val id: String,
    @SerialName("invoice_number") val invoiceNumber: String,
    val amount: String,
    val paid: String,
    val balance: String,
    @SerialName("due_date") val dueDate: String,
    val status: String,
    val overdue: Boolean,
)

/** `CustomerHoursSummaryDto`: hours bought / activated / used / left and credit owed per customer. */
@Serializable
data class CustomerHoursSummaryDto(
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    val bought: String,
    val activated: String,
    val used: String,
    val left: String,
    @SerialName("awaiting_activation") val awaitingActivation: String,
    @SerialName("credit_owed") val creditOwed: String,
)

/** `MachineReportLineIn`. */
@Serializable
data class MachineReportLinePayload(
    val kind: String,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("reason_id") val reasonId: String? = null,
    val hours: String,
    val note: String? = null,
)

/**
 * `MACHINE_REPORT` sync operation (`MachineReportIn` without `id`: the operation id is the report id). [captureId] names
 * the reading: the DAILY `METER_CAPTURE` queued just before it (the report depends on that operation), or the reading of
 * a rejected report being corrected, with [correctsReportId]. [opening]: the machine's first reading, no lines (the
 * server takes it as the starting reading).
 */
@Serializable
data class MachineReportPayload(
    @SerialName("machine_id") val machineId: String,
    @SerialName("capture_id") val captureId: String? = null,
    @SerialName("corrects_report_id") val correctsReportId: String? = null,
    val lines: List<MachineReportLinePayload> = emptyList(),
    val note: String? = null,
    @SerialName("client_created_at") val clientCreatedAt: String? = null,
    val opening: Boolean? = null,
)

/** `CREDIT_INVOICE_PAYMENT` sync operation (the operation id is the payment's client id). */
@Serializable
data class CreditInvoicePaymentPayload(
    @SerialName("invoice_id") val invoiceId: String,
    val amount: String,
    val method: String,
    val reference: String? = null,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("staff_member_id") val staffMemberId: String? = null,
    val note: String? = null,
    @SerialName("evidence_attachment_ids") val evidenceAttachmentIds: List<String> = emptyList(),
    @SerialName("evidence_upload_ids") val evidenceUploadIds: List<String> = emptyList(),
)

/** `CreditInvoicePaymentIn` (online, office). */
@Serializable
data class CreditInvoicePaymentIn(
    @SerialName("client_id") val clientId: String? = null,
    val amount: String,
    val method: String,
    val reference: String? = null,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("staff_member_id") val staffMemberId: String? = null,
    val note: String? = null,
    @SerialName("evidence_attachment_ids") val evidenceAttachmentIds: List<String> = emptyList(),
)

/** `MachineReportDecisionIn` (approve). */
@Serializable
data class MachineReportDecisionIn(val note: String? = null)

/** `MachineReportRejectIn` (reject; the reason is required). */
@Serializable
data class MachineReportRejectIn(val reason: String)

/** `CreditActivationIn`: make [hours] of an order's credit part usable (within the customer's credit arrangement). */
@Serializable
data class CreditActivationIn(val hours: String, val reason: String)

/** `CreditRejectionIn` (rejectHoursCredit): why the credit part of an order is not approved (at least 3 characters). */
@Serializable
data class CreditRejectionIn(val reason: String)

/** ADR-008 sync operation types. */
object MachineReportOps {
    const val MACHINE_REPORT = "MACHINE_REPORT"
    const val CREDIT_INVOICE_PAYMENT = "CREDIT_INVOICE_PAYMENT"
}
