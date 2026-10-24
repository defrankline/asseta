package com.asseta.core.model.sync

import com.asseta.core.model.DecimalAmount
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Gate 5 field-finance operation payloads (backend sync push `ExpenseOp`, `CashCollectionOp`, `CashHandoverOp`,
 * `FuelEventOp`). `client_id` is generated once per form visit and is the business idempotency key (the server returns
 * the existing record for a known client id). Amounts are [DecimalAmount] decimal strings, never binary floats.
 * The currency is always sent explicitly so local tallies and the server agree on it.
 */
@Serializable
data class ExpensePayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("category_id") val categoryId: String,
    val supplier: String? = null,
    val description: String,
    val amount: DecimalAmount,
    val currency: String,
    @SerialName("incurred_at") val incurredAt: String,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("paid_from") val paidFrom: String,
    /** Blob upload (session) ids of the receipts; written when the upload completes, before the op is ever sent. */
    @SerialName("receipt_upload_ids") val receiptUploadIds: List<String> = emptyList(),
    val gps: GpsIn? = null,
    @SerialName("device_id") val deviceId: String? = null,
)

@Serializable
data class CashCollectionPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("customer_id") val customerId: String,
    val amount: DecimalAmount,
    val currency: String,
    @SerialName("received_at") val receivedAt: String,
    val reference: String? = null,
    val note: String? = null,
    /** The cash holder when a recorder records for another custodian (tenant policy); null = the recorder. */
    @SerialName("staff_member_id") val staffMemberId: String? = null,
)

@Serializable
data class CashHandoverPayload(
    @SerialName("client_id") val clientId: String,
    val amount: DecimalAmount,
    val currency: String,
    @SerialName("handed_at") val handedAt: String,
    val reference: String? = null,
    val note: String? = null,
    /** The remitting custodian when a recorder records for another custodian (tenant policy); null = the recorder. */
    @SerialName("staff_member_id") val staffMemberId: String? = null,
)

@Serializable
data class FuelEventPayload(
    @SerialName("client_id") val clientId: String,
    @SerialName("event_type") val eventType: String,
    val litres: DecimalAmount,
    @SerialName("unit_price") val unitPrice: DecimalAmount? = null,
    val currency: String? = null,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("meter_reading") val meterReading: DecimalAmount? = null,
    val supplier: String? = null,
    @SerialName("occurred_at") val occurredAt: String,
    val note: String? = null,
)
