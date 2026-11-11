package com.asseta.supervisor.ui.customers

import com.asseta.core.domain.customers.CustomerDraft
import com.asseta.core.model.sync.FieldCustomerDto
import org.junit.Assert.assertEquals
import org.junit.Test

/** Supervisor customers wording (strings doc "Supervisor — customers"). */
class CustomerTextsTest {
    private val c = FieldCustomerDto("c1", "KIL", "Kilimo Ltd", taxId = "TIN-1", contactName = "Asha", contactPhone = "0700", paymentTermsDays = 45, version = 3)

    @Test
    fun `rows and details read the customer`() {
        assertEquals("KIL · Asha", CustomerTexts.rowDetail(c))
        assertEquals("KIL", CustomerTexts.rowDetail(c.copy(contactName = " ")))
        assertEquals(
            listOf("Code" to "KIL", "Tax ID" to "TIN-1", "Contact" to "Asha", "Phone" to "0700", "Payment terms" to "45 days · Set by the office"),
            CustomerTexts.fields(c, termsEditable = false),
        )
        assertEquals("Payment terms" to "45 days", CustomerTexts.fields(c, termsEditable = true).last())
        assertEquals(CustomerDraft("KIL", "Kilimo Ltd", "TIN-1", "Asha", "0700", "", "45"), CustomerTexts.draft(c))
        assertEquals("Customers need a connection. Connect to see, add or edit them.", CustomerTexts.OFFLINE)
        assertEquals("Someone else changed this customer. Reload to see it.", CustomerTexts.STALE)
    }
}
