package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.accountability.PartialReasonMode
import com.asseta.core.domain.accountability.RemittanceRequirements
import com.asseta.supervisor.ui.finance.CashForm
import com.asseta.supervisor.ui.finance.RemittanceAccess
import com.asseta.supervisor.ui.finance.RemittanceForm
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** DEC-032 Phase 3: wording and form rules of the collection link, the partial reason and the conflicts. */
class CashDetailsPresentationTest {
    @Test
    fun `new conflicts are shown in plain words`() {
        val t = FieldAccountabilityTexts
        assertEquals("Your company requires every collection to name its purchase or invoice. Record it again and choose one.", t.conflict("COLLECTION_LINK_REQUIRED"))
        assertEquals("Part of this cash is still with you and your company requires the reason. Record the handover again with the reason.", t.conflict("PARTIAL_REMITTANCE_REASON_REQUIRED"))
        assertEquals("The purchase you chose is cancelled. Record it again and choose another.", t.conflict("PURCHASE_CANCELLED"))
        listOf("EVIDENCE_REQUIRED", "PURCHASE_NOT_FOUND", "OVER_ALLOCATION", "ALLOCATION_MISMATCH").forEach { assertTrue(t.conflict(it) != null) }
    }

    @Test
    fun `a required link stops saving until a purchase is chosen`() {
        val required = RemittanceAccess(true, RemittanceRequirements(), linkOffered = true, linkRequired = true)
        assertEquals(FieldAccountabilityTexts.COLLECTION_LINK_REQUIRED, RemittanceForm.linkIssue(required, CashForm(customerId = "c1", purchaseId = null)))
        assertNull(RemittanceForm.linkIssue(required, CashForm(customerId = "c1", purchaseId = "p1")))
        assertNull(RemittanceForm.linkIssue(required.copy(linkRequired = false), CashForm()))
    }

    @Test
    fun `an optional reason may stay empty but not be too short`() {
        assertTrue(RemittanceForm.partialReasonOk(PartialReasonMode.NONE, ""))
        assertTrue(RemittanceForm.partialReasonOk(PartialReasonMode.OPTIONAL, ""))
        assertFalse(RemittanceForm.partialReasonOk(PartialReasonMode.OPTIONAL, "ab"))
        assertFalse(RemittanceForm.partialReasonOk(PartialReasonMode.REQUIRED, ""))
        assertTrue(RemittanceForm.partialReasonOk(PartialReasonMode.REQUIRED, "Kept for fuel"))
    }
}
