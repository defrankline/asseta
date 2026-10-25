package com.asseta.core.model.sync

import com.asseta.core.model.DecimalAmount
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/*
 * Accountability field operations (sync push) and the online reads behind them. Payload shapes follow
 * contracts/openapi.json (`HoursPurchaseIn`, `TransferIn`, `CashTransferIn`, `CashAcknowledgementIn`, `BaselineIn`,
 * `CorrectionIn`); evidence uploaded by resumable blob upload is named by upload id and filled in when the upload
 * completes, before the operation is ever sent. Amounts and hours are decimal strings, never binary floats.
 */

object AccountabilityOps {
    const val HOURS_PURCHASE = "HOURS_PURCHASE"
    const val HOURS_TRANSFER_REQUEST = "HOURS_TRANSFER_REQUEST"
    const val CASH_TRANSFER = "CASH_TRANSFER"
    const val CASH_TRANSFER_ACKNOWLEDGEMENT = "CASH_TRANSFER_ACKNOWLEDGEMENT"
    const val CASH_FLOAT_ACKNOWLEDGEMENT = "CASH_FLOAT_ACKNOWLEDGEMENT"

    /** Ask to keep cash (`CashRetentionIn` with `client_id`), when the server announces OP_CASH_RETENTION_REQUEST. */
    const val CASH_RETENTION_REQUEST = "CASH_RETENTION_REQUEST"
    const val METER_BASELINE = "METER_BASELINE"
    const val METER_CORRECTION = "METER_CORRECTION"

    /** Blob purpose of hours-sale payment evidence (receipt, mobile-money screenshot). */
    const val PAYMENT_EVIDENCE = "PAYMENT_EVIDENCE"

    const val DAILY = "DAILY"
}

/** `WalkInCustomerIn`: a walk-in needs only a name; [clientId] becomes the customer id (offline replays return it). */
@Serializable
data class WalkInCustomerPayload(
    @SerialName("client_id") val clientId: String? = null,
    val name: String,
    val phone: String? = null,
)

/**
 * `PurchasePaymentIn`: money taken with the purchase, recorded as a CLAIMED payment (hours activate only when someone
 * else verifies it). [staffMemberId] is the cash holder (null = the recorder, for CASH).
 */
@Serializable
data class PurchasePaymentPayload(
    val method: String,
    val amount: DecimalAmount? = null,
    @SerialName("received_at") val receivedAt: String,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("staff_member_id") val staffMemberId: String? = null,
    @SerialName("evidence_attachment_ids") val evidenceAttachmentIds: List<String> = emptyList(),
)

/**
 * `HOURS_PURCHASE` (`HoursPurchaseIn` + `evidence_upload_ids`): [clientId] is the purchase's idempotency key; give
 * [customerId] or [walkIn], not both. The price comes from the server's rate card.
 */
@Serializable
data class HoursPurchasePayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("walk_in") val walkIn: WalkInCustomerPayload? = null,
    @SerialName("machine_id") val machineId: String,
    val hours: String,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    val note: String? = null,
    val payment: PurchasePaymentPayload? = null,
    /** Completed blob upload ids (purpose PAYMENT_EVIDENCE), appended as each evidence photo finishes uploading. */
    @SerialName("evidence_upload_ids") val evidenceUploadIds: List<String> = emptyList(),
)

/** `HOURS_TRANSFER_REQUEST` (`TransferIn`): move remaining hours of a purchase to another machine. */
@Serializable
data class HoursTransferPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("from_machine_id") val fromMachineId: String? = null,
    @SerialName("to_machine_id") val toMachineId: String,
    val hours: String,
    val reason: String,
    @SerialName("reason_code_id") val reasonCodeId: String? = null,
)

/** `CASH_TRANSFER` (`CashTransferIn`): field-to-field cash, pending the receiver's acknowledgement per policy. */
@Serializable
data class CashTransferPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("from_staff_id") val fromStaffId: String? = null,
    @SerialName("to_staff_id") val toStaffId: String,
    val amount: DecimalAmount,
    /** Only when the recorder is the receiver and the tenant counts that as the acknowledgement. */
    @SerialName("amount_received") val amountReceived: DecimalAmount? = null,
    val currency: String,
    @SerialName("transferred_at") val transferredAt: String,
    val note: String? = null,
)

/** `CASH_TRANSFER_ACKNOWLEDGEMENT`: the receiver's answer (acknowledged with the amount received, or disputed). */
@Serializable
data class CashTransferAckPayload(
    @SerialName("transfer_id") val transferId: String,
    val acknowledged: Boolean,
    @SerialName("amount_received") val amountReceived: DecimalAmount? = null,
    val note: String? = null,
)

/** `CASH_FLOAT_ACKNOWLEDGEMENT`: the receiver's answer to a float the office issued. */
@Serializable
data class CashFloatAckPayload(
    @SerialName("entry_id") val entryId: String,
    val acknowledged: Boolean,
    @SerialName("amount_received") val amountReceived: DecimalAmount? = null,
    val note: String? = null,
)

/** `METER_BASELINE` (`BaselineIn`): a proposed initial reading of a machine with its evidence (a second person approves). */
@Serializable
data class BaselinePayload(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    val reading: String,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("device_id") val deviceId: String? = null,
    val gps: GpsIn? = null,
    val note: String? = null,
    /** Filled in when the meter photo upload completes. */
    @SerialName("photo_attachment_id") val photoAttachmentId: String? = null,
)

/** `METER_CORRECTION` (`CorrectionIn`): the corrected reading (its own evidence) replacing a live one once approved. */
@Serializable
data class CorrectionPayload(
    @SerialName("superseded_capture_id") val supersededCaptureId: String,
    val reason: String,
    val replacement: MeterCaptureIn,
)

// --- online reads of the field app (cached encrypted for offline use) ------------------------------------------

/** `EffectivePolicyDto` (getEffectivePolicy): a field user reads CASH_CUSTODY / CUSTOMER_HOURS with their capture permission. */
@Serializable
data class EffectivePolicyDto(
    @SerialName("policy_type") val policyType: String,
    @SerialName("version_stamp") val versionStamp: String,
    val values: JsonObject,
)

/** `CustodianDto` (listCashCustodians): a staff member who can hold company cash (a login is not required). */
@Serializable
data class CustodianDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("full_name") val fullName: String,
    @SerialName("employee_code") val employeeCode: String? = null,
    @SerialName("has_login") val hasLogin: Boolean,
    @SerialName("is_active") val isActive: Boolean,
    val kind: String,
)

/** `CashTransferDto` (listCashTransfers). */
@Serializable
data class CashTransferDto(
    val id: String,
    @SerialName("client_id") val clientId: String? = null,
    @SerialName("from_staff_id") val fromStaffId: String,
    @SerialName("to_staff_id") val toStaffId: String,
    @SerialName("amount_declared") val amountDeclared: String,
    @SerialName("amount_received") val amountReceived: String? = null,
    val currency: String,
    val status: String,
    @SerialName("transferred_at") val transferredAt: String,
    @SerialName("recorded_at") val recordedAt: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("acknowledged_at") val acknowledgedAt: String? = null,
    @SerialName("acknowledged_by") val acknowledgedBy: String? = null,
    @SerialName("ack_method") val ackMethod: String? = null,
    @SerialName("ack_note") val ackNote: String? = null,
    val note: String? = null,
    val source: String,
    @SerialName("variance_id") val varianceId: String? = null,
    // Display names (DEC-030 G2; null on older servers).
    @SerialName("from_staff_name") val fromStaffName: String? = null,
    @SerialName("to_staff_name") val toStaffName: String? = null,
    @SerialName("recorded_by_name") val recordedByName: String? = null,
    @SerialName("acknowledged_by_name") val acknowledgedByName: String? = null,
) {
    companion object {
        const val PENDING = "PENDING_ACKNOWLEDGEMENT"
        const val ACKNOWLEDGED = "ACKNOWLEDGED"
        const val DISPUTED = "DISPUTED"
    }
}

/** `CashCustodyEntryDto` (listCashFloats): a float (or opening balance) with its acknowledgement state. */
@Serializable
data class FloatEntryDto(
    val id: String,
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("entry_type") val entryType: String,
    val amount: String,
    val currency: String,
    @SerialName("occurred_at") val occurredAt: String,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("ack_required") val ackRequired: Boolean = false,
    @SerialName("ack_status") val ackStatus: String = "",
    @SerialName("acknowledged_at") val acknowledgedAt: String? = null,
    @SerialName("acknowledged_by") val acknowledgedBy: String? = null,
    @SerialName("amount_received") val amountReceived: String? = null,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @SerialName("acknowledged_by_name") val acknowledgedByName: String? = null,
)

/** `PurchaseTotalsDto` (the part the field app shows). */
@Serializable
data class PurchaseTotalsDto(
    val purchased: String,
    val activated: String,
    val consumed: String,
    val remaining: String,
    @SerialName("awaiting_activation") val awaitingActivation: String,
)

/** `MachineHoursDto`: a purchase's hours on one machine (after transfers). */
@Serializable
data class MachineHoursDto(
    @SerialName("machine_id") val machineId: String,
    val remaining: String,
)

/** `HoursPurchaseDto` (listHoursPurchases), the part the hours-transfer form needs. */
@Serializable
data class FieldHoursPurchaseDto(
    val id: String,
    @SerialName("purchase_number") val purchaseNumber: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String,
    val hours: String,
    val status: String,
    val totals: PurchaseTotalsDto,
    val machines: List<MachineHoursDto> = emptyList(),
)

/** `ReasonCodeDto` (listHoursReasonCodes): a tenant reason (kind DISCOUNT, CREDIT, TRANSFER, CANCELLATION). */
@Serializable
data class ReasonCodeDto(
    val id: String,
    val code: String,
    val label: String,
    val kind: String,
    @SerialName("is_active") val isActive: Boolean,
)

/** `CashReasonDto` (listCashReasons): a tenant cash reason (kind VARIANCE, WRITE_OFF, RETENTION, ADJUSTMENT). */
@Serializable
data class CashReasonDto(
    val id: String,
    val label: String,
    val kind: String,
    @SerialName("is_active") val isActive: Boolean,
    val description: String? = null,
)

/**
 * `CashRetentionIn`: the online request (requestCashRetention) and the offline `CASH_RETENTION_REQUEST` sync op, where
 * [clientId] (the form visit's id) is required and makes a replay return the original request.
 */
@Serializable
data class CashRetentionIn(
    val amount: DecimalAmount,
    val currency: String? = null,
    val reason: String,
    @SerialName("reason_id") val reasonId: String? = null,
    @SerialName("staff_member_id") val staffMemberId: String? = null,
    @SerialName("valid_until") val validUntil: String? = null,
    @SerialName("client_id") val clientId: String? = null,
)
