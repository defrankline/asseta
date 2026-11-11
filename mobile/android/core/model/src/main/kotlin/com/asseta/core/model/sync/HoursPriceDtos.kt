package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** `HoursPriceDto` (SYNC_HOURS_PRICES): a machine's current hourly rate (its type's rate card), for pricing a sale offline. */
@Serializable
data class HoursPriceDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("rate_card_id") val rateCardId: String,
    @SerialName("hourly_rate") val hourlyRate: String,
    @SerialName("minimum_hours") val minimumHours: String,
    val currency: String,
    /** Decimal places the server rounds the total to; null from a server before it was sent (ISO fallback). */
    @SerialName("minor_units") val minorUnits: Int? = null,
    @SerialName("effective_from") val effectiveFrom: String,
)

/** `CustomerDiscountRateDto` (SYNC_HOURS_PRICES): a customer's approved discount in force today, percent off the hourly rate. */
@Serializable
data class CustomerDiscountRateDto(
    @SerialName("customer_id") val customerId: String,
    val percent: String,
)
