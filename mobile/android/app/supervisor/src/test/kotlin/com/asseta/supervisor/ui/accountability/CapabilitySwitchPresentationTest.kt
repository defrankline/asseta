package com.asseta.supervisor.ui.accountability

import com.asseta.core.model.owner.OverdueAmountDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.isForm
import com.asseta.supervisor.ui.title
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

/** Follow-up F1/F2 on the field app: switched-off conflict wording and the "Overdue remittance" screen. */
class CapabilitySwitchPresentationTest {
    @Test
    fun `switched-off conflicts are shown in plain words`() {
        assertEquals("Your company has switched off engine-hour controls, so this was not accepted.", FieldAccountabilityTexts.conflict("ENGINE_HOURS_DISABLED"))
        assertEquals("Your company has switched off cash custody controls, so this was not accepted.", FieldAccountabilityTexts.conflict("CASH_CUSTODY_DISABLED"))
    }

    private val flag = RemittanceOverdueDto(
        id = "o1", staffMemberId = "abcdefgh-1234", staffMemberName = "Baraka", localDay = "2026-10-24", cutoffHour = 7,
        amounts = listOf(OverdueAmountDto("TZS", "50000.00"), OverdueAmountDto("USD", "20")), flaggedAt = "2026-10-24T07:05:00Z", policyVersion = "v1",
    )

    @Test
    fun `overdue remittance shows name, amounts, day, cut-off and flagged time`() {
        assertEquals(
            listOf(
                "Cash held by" to "Baraka", "Not remitted" to "TZS 50,000.00, USD 20.00", "Day" to "2026-10-24", "Cut-off" to "07:00",
                "Flagged" to "2026-10-24T07:05:00Z",
            ),
            RemittanceOverdueText.rows(flag),
        )
        assertEquals("Still held after the 07:00 cut-off on 2026-10-24. Remit this cash to the office as soon as you can.", RemittanceOverdueText.footer(flag))
        assertEquals("abcdefgh", RemittanceOverdueText.name(flag.copy(staffMemberName = null)))
    }

    @Test
    fun `overdue remittance is a pushed screen with its own title`() {
        val r = Route.RemittanceOverdue("o1")
        assertEquals("Overdue remittance", r.title("Acme"))
        assertFalse(r.isForm)
    }
}
