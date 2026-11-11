package com.asseta.core.domain.customers

import com.asseta.core.domain.finance.FormCheck
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Supervisor customers: who may edit, the form checks and payment terms kept with the office. */
class CustomerRulesTest {
    @Test
    fun `details or write may add and edit, only write changes payment terms`() {
        assertTrue(CustomerRules.canEdit(setOf("tenant.customer.details")))
        assertTrue(CustomerRules.canEdit(setOf("tenant.customer.write")))
        assertFalse(CustomerRules.canEdit(setOf("tenant.customer.read")))
        assertTrue(CustomerRules.termsEditable(setOf("tenant.customer.write")))
        assertFalse(CustomerRules.termsEditable(setOf("tenant.customer.details")))
    }

    @Test
    fun `blank optional fields are null and terms stay as they are without write`() {
        val v = (CustomerRules.check(CustomerDraft(" KIL ", " Kilimo ", "", " Asha ", "", "", termsText = "90"), termsEditable = false, currentTerms = 45)
            as FormCheck.Valid).value
        assertEquals(CustomerValues("KIL", "Kilimo", null, "Asha", null, null, 45), v)
        val office = CustomerRules.check(CustomerDraft("KIL", "Kilimo", termsText = "60"), termsEditable = true) as FormCheck.Valid
        assertEquals(60, office.value.paymentTermsDays)
        assertEquals(CustomerRules.DEFAULT_TERMS, (CustomerRules.check(CustomerDraft("K", "N"), termsEditable = false) as FormCheck.Valid).value.paymentTermsDays)
    }

    @Test
    fun `required fields, lengths, email and terms are checked`() {
        assertEquals(listOf(CustomerMessages.CODE, CustomerMessages.NAME), (CustomerRules.check(CustomerDraft(), false) as FormCheck.Invalid).messages)
        assertEquals(listOf(CustomerMessages.CODE), (CustomerRules.check(CustomerDraft("x".repeat(33), "N"), false) as FormCheck.Invalid).messages)
        assertEquals(listOf(CustomerMessages.EMAIL), (CustomerRules.check(CustomerDraft("K", "N", email = "asha.example"), false) as FormCheck.Invalid).messages)
        assertEquals(listOf(CustomerMessages.LONG), (CustomerRules.check(CustomerDraft("K", "N", phone = "1".repeat(41)), false) as FormCheck.Invalid).messages)
        assertEquals(listOf(CustomerMessages.TERMS), (CustomerRules.check(CustomerDraft("K", "N", termsText = "400"), true) as FormCheck.Invalid).messages)
        assertTrue(CustomerRules.validEmail("asha@kilimo.co.tz"))
        assertFalse(CustomerRules.validEmail("a@b@c"))
        assertNull((CustomerRules.check(CustomerDraft("K", "N", email = " "), false) as FormCheck.Valid).value.email)
    }
}
