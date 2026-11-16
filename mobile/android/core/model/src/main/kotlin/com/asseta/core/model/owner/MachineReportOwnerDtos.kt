package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * ADR-008 additions the Owner app reads or sends next to the shared machine-report / credit-invoice DTOs
 * (core/model sync/MachineReportDtos.kt). Optional fields default so older snapshots still decode.
 */

/** One payment part of an order as the Owner app sums it (`CustomerPaymentDto`, the fields "sold by method" needs). */
@Serializable
data class PurchasePaymentDto(
    val id: String,
    val amount: String,
    /** CASH, BANK or MOBILE_MONEY (a CREDIT part is the order's `credit_amount`, not a payment). */
    val method: String,
    /** CLAIMED, VERIFIED or REJECTED. */
    val status: String? = null,
    @SerialName("received_at") val receivedAt: String? = null,
    @SerialName("reversed_at") val reversedAt: String? = null,
)

/** `CreditExposureDto` (getCustomerCreditExposure): the customer's credit limit and what is left of it. */
@Serializable
data class CreditExposureDto(
    @SerialName("customer_id") val customerId: String,
    val currency: String,
    @SerialName("arrangement_id") val arrangementId: String? = null,
    @SerialName("limit_amount") val limitAmount: String? = null,
    val exposure: String,
    val available: String? = null,
)
