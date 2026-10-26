package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.NonRevenueActivityDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** DEC-031 R1 on the Supervisor work log: status wording, Explain gating and refusals in plain words. */
class NonRevenuePresentationTest {
    private val read = "tenant.revenue.read"
    private val explain = "tenant.revenue.explain"

    @Test
    fun `status wording and tone`() {
        assertEquals("Counted as revenue until explained", NonRevenueText.status("NONE"))
        assertEquals("Explained · waiting for approval", NonRevenueText.status("PROPOSED"))
        assertEquals("Approved as non-revenue time", NonRevenueText.status("APPROVED"))
        assertEquals("Not approved · counted as revenue", NonRevenueText.status("REJECTED"))
        assertEquals(NonRevenueTone.WARNING, NonRevenueText.tone("NONE"))
        assertEquals(NonRevenueTone.ACCENT, NonRevenueText.tone("PROPOSED"))
        assertEquals(NonRevenueTone.LIVE, NonRevenueText.tone("APPROVED"))
        assertTrue(NonRevenueText.canExplain("NONE"))
        assertTrue(NonRevenueText.canExplain("REJECTED"))
        assertFalse(NonRevenueText.canExplain("PROPOSED"))
        assertFalse(NonRevenueText.canExplain("APPROVED"))
    }

    @Test
    fun `access needs the capability and the permissions`() {
        val full = FieldAccess(emptySet(), setOf(read, explain))
        assertTrue(full.nonRevenueStatus)
        assertTrue(full.explainNonRevenue)
        val readOnly = FieldAccess(emptySet(), setOf(read))
        assertTrue(readOnly.nonRevenueStatus)
        assertFalse(readOnly.explainNonRevenue)
        assertFalse(FieldAccess(emptySet(), setOf(explain)).explainNonRevenue)
        val off = FieldAccess(emptySet(), setOf(read, explain), disabled = setOf(TenantAccess.REVENUE_RECONCILIATION))
        assertFalse(off.nonRevenueStatus)
        assertFalse(off.explainNonRevenue)
    }

    @Test
    fun `refusals and form rules`() {
        assertEquals("This time is already waiting for approval.", NonRevenueText.error("NON_REVENUE_PENDING", "x"))
        assertEquals("Your company does not need approval for this time.", NonRevenueText.error("NON_REVENUE_APPROVAL_NOT_REQUIRED", "x"))
        assertEquals("Your company has switched off revenue checks.", NonRevenueText.error("REVENUE_RECONCILIATION_DISABLED", "x"))
        assertEquals("server says no", NonRevenueText.error("OTHER", "server says no"))
        assertFalse(NonRevenueText.noteValid("  abc "))
        assertTrue(NonRevenueText.noteValid("moved"))
        assertEquals("Mobilization · 06:00 → 08:30 (2.5 h)", NonRevenueText.entryLine("Mobilization", "06:00", "08:30", "2.50"))
        val dto = NonRevenueActivityDto("a1", "j", null, "m", null, null, "MOBILIZATION", "s", "e", "1.00", null, null, "NONE")
        assertEquals(mapOf("a1" to dto), NonRevenueText.byActivity(listOf(dto)))
        assertTrue(NonRevenueText.byActivity(null).isEmpty())
    }
}
