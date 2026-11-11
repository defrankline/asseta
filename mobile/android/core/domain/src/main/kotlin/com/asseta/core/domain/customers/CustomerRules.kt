package com.asseta.core.domain.customers

import com.asseta.core.domain.finance.FormCheck

/** A customer as typed in the Supervisor app's add / edit form. */
data class CustomerDraft(
    val code: String = "",
    val name: String = "",
    val taxId: String = "",
    val contactName: String = "",
    val phone: String = "",
    val email: String = "",
    /** Payment terms as typed (editable only with `tenant.customer.write`). */
    val termsText: String = CustomerRules.DEFAULT_TERMS.toString(),
)

/** The checked values sent to the server (blank optional fields are null). */
data class CustomerValues(
    val code: String,
    val name: String,
    val taxId: String?,
    val contactName: String?,
    val phone: String?,
    val email: String?,
    val paymentTermsDays: Int,
)

/** Validation wording of the customer form (docs/requirements/accountability-mobile-strings.md, Supervisor — customers). */
object CustomerMessages {
    const val CODE = "Enter a code (at most 32 characters)."
    const val NAME = "Enter the name (at most 200 characters)."
    const val EMAIL = "Enter a valid email address."
    const val TERMS = "Enter payment terms between 0 and 365 days."
    const val LONG = "Shorten the tax ID, contact name or phone."
}

/**
 * Offline checks of the customer form, mirroring the server (`CustomerIn`). Without `tenant.customer.write`
 * ([termsEditable] false) the payment terms are sent as they are ([currentTerms]; 30 for a new customer).
 */
object CustomerRules {
    const val DEFAULT_TERMS = 30
    const val MAX_CODE = 32
    const val MAX_NAME = 200
    const val MAX_TAX_ID = 64
    const val MAX_CONTACT = 200
    const val MAX_PHONE = 40
    const val MAX_EMAIL = 320
    const val MAX_TERMS = 365

    /** Field staff may add customers and edit their details; the office may also change payment terms. */
    fun canEdit(permissions: Set<String>): Boolean = DETAILS in permissions || WRITE in permissions
    fun termsEditable(permissions: Set<String>): Boolean = WRITE in permissions

    fun check(d: CustomerDraft, termsEditable: Boolean, currentTerms: Int = DEFAULT_TERMS): FormCheck<CustomerValues> {
        val m = mutableListOf<String>()
        val code = d.code.trim()
        if (code.isEmpty() || code.length > MAX_CODE) m += CustomerMessages.CODE
        val name = d.name.trim()
        if (name.isEmpty() || name.length > MAX_NAME) m += CustomerMessages.NAME
        fun opt(text: String) = text.trim().ifEmpty { null }
        val taxId = opt(d.taxId)
        val contact = opt(d.contactName)
        val phone = opt(d.phone)
        if ((taxId?.length ?: 0) > MAX_TAX_ID || (contact?.length ?: 0) > MAX_CONTACT || (phone?.length ?: 0) > MAX_PHONE) m += CustomerMessages.LONG
        val email = opt(d.email)
        if (email != null && !validEmail(email)) m += CustomerMessages.EMAIL
        val terms = if (termsEditable) d.termsText.trim().toIntOrNull()?.takeIf { it in 0..MAX_TERMS }.also { if (it == null) m += CustomerMessages.TERMS } else currentTerms
        return if (m.isEmpty()) FormCheck.Valid(CustomerValues(code, name, taxId, contact, phone, email, terms!!)) else FormCheck.Invalid(m)
    }

    /** One "@" with text on both sides, no spaces, at most 320 characters. */
    fun validEmail(email: String): Boolean {
        if (email.length > MAX_EMAIL || email.any { it.isWhitespace() }) return false
        val parts = email.split('@')
        return parts.size == 2 && parts[0].isNotEmpty() && parts[1].isNotEmpty()
    }

    const val DETAILS = "tenant.customer.details"
    const val WRITE = "tenant.customer.write"
}
