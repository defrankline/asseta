package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * `CustomerDto` (listCustomers / getCustomer / createCustomer / updateCustomer) as the Supervisor app shows and edits it
 * (`tenant.customer.details`): details only; contracts, rates and deactivation stay with the office.
 */
@Serializable
data class FieldCustomerDto(
    val id: String,
    val code: String,
    val name: String,
    @SerialName("tax_id") val taxId: String? = null,
    @SerialName("contact_name") val contactName: String? = null,
    @SerialName("contact_phone") val contactPhone: String? = null,
    @SerialName("contact_email") val contactEmail: String? = null,
    @SerialName("payment_terms_days") val paymentTermsDays: Int = 30,
    @SerialName("is_active") val isActive: Boolean = true,
    val version: Int = 1,
) {
    /** The same customer as sync delivers it to the pickers. */
    fun synced() = CustomerDto(id, code, name, contactName, contactPhone, isActive)
}

/** `CustomerIn` (create) and `CustomerUpdateIn` (edit, with the [version] last read). */
@Serializable
data class CustomerWriteIn(
    val code: String,
    val name: String,
    @SerialName("tax_id") val taxId: String? = null,
    @SerialName("contact_name") val contactName: String? = null,
    @SerialName("contact_phone") val contactPhone: String? = null,
    @SerialName("contact_email") val contactEmail: String? = null,
    @SerialName("payment_terms_days") val paymentTermsDays: Int,
    val version: Int? = null,
)
