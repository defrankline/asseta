package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** `HireAllocationDto`: the part of a payment set against one invoice (released once the payment is rejected). */
@Serializable
data class PaymentAllocationDto(
    val id: SerializableUuid,
    @SerialName("invoice_id") val invoiceId: SerializableUuid,
    val amount: DecimalAmount,
    @SerialName("released_at") val releasedAt: String? = null,
)

/** `PurchaseLinkDto`: the hours purchase a customer payment is linked to. */
@Serializable
data class PaymentPurchaseLinkDto(
    @SerialName("purchase_id") val purchaseId: SerializableUuid,
    @SerialName("purchase_number") val purchaseNumber: String,
    val amount: DecimalAmount,
)

/**
 * `CustomerPaymentDto` (listCustomerPayments / getCustomerPayment / decideCustomerPayment): money a customer paid.
 * [status] CLAIMED until someone other than the recorder confirms (VERIFIED) or rejects (REJECTED) it.
 */
@Serializable
data class CustomerPaymentDto(
    val id: SerializableUuid,
    @SerialName("customer_id") val customerId: SerializableUuid,
    @SerialName("customer_name") val customerName: String? = null,
    val amount: DecimalAmount,
    val currency: String,
    val method: String,
    val status: String,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("recorded_at") val recordedAt: String,
    val reference: String? = null,
    val note: String? = null,
    @SerialName("collection_number") val collectionNumber: String? = null,
    @SerialName("received_by_staff_id") val receivedByStaffId: String? = null,
    @SerialName("received_by_staff_name") val receivedByStaffName: String? = null,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("recorded_by_name") val recordedByName: String? = null,
    @SerialName("verified_by") val verifiedBy: String? = null,
    @SerialName("verified_by_name") val verifiedByName: String? = null,
    @SerialName("verified_at") val verifiedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    @SerialName("reversed_at") val reversedAt: String? = null,
    val allocations: List<PaymentAllocationDto> = emptyList(),
    @SerialName("purchase_links") val purchaseLinks: List<PaymentPurchaseLinkDto>? = null,
)

/** `PaymentEvidenceDto`: one photo attached to a customer payment. */
@Serializable
data class PaymentEvidenceDto(@SerialName("attachment_id") val attachmentId: String)

/** `HireInvoiceDto`, only what names an invoice beside a payment. */
@Serializable
data class InvoiceNumberDto(val id: SerializableUuid, @SerialName("invoice_number") val invoiceNumber: String? = null)

/**
 * One payment with what the app reads beside it: its evidence photos ([evidenceFailed] when they could not be read, which
 * is not the same as having none) and the numbers of the invoices it is set against (best effort).
 */
@Serializable
data class PaymentReview(
    val payment: CustomerPaymentDto,
    val evidenceIds: List<String> = emptyList(),
    val evidenceFailed: Boolean = false,
    val invoiceNumbers: Map<String, String> = emptyMap(),
)
