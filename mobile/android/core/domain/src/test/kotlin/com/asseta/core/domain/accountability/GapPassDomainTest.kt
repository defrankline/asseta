package com.asseta.core.domain.accountability

import com.asseta.core.domain.inbox.InboxLink
import com.asseta.core.domain.inbox.InboxLinks
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** DEC-030 gap pass: capability switch, display names and the field app's exact-record notification taps. */
class GapPassDomainTest {
    private val hours = CustomerHoursPolicy(enabled = true, walkInAllowed = true, transferRequiresApproval = true, reasonCodeRequired = false)
    private val caps = setOf(SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_HOURS_TRANSFER_REQUEST, SyncCapabilities.OP_CASH_RETENTION_REQUEST)
    private val perms = setOf(FieldAccess.HOURS_PURCHASE, FieldAccess.HOURS_TRANSFER, FieldAccess.COLLECTION_RECORD)

    @Test
    fun `customer hours switched off in me hides the hours entries`() {
        val on = FieldAccess(caps, perms, hours = hours)
        assertTrue(on.sellHours)
        assertTrue(on.requestHoursTransfer)
        val off = on.copy(disabled = setOf(TenantAccess.CUSTOMER_HOURS))
        assertFalse(off.sellHours)
        assertFalse(off.walkIn)
        assertFalse(off.requestHoursTransfer)
        assertTrue(off.retentionOffline) // other entries are unaffected
        assertFalse(FieldAccess(caps - SyncCapabilities.OP_CASH_RETENTION_REQUEST, perms).retentionOffline)
    }

    @Test
    fun `names first, short id only when the name is missing`() {
        assertEquals("Asha", DisplayNames.of("Asha", "11111111-2222"))
        assertEquals("11111111", DisplayNames.of(null, "11111111-2222"))
        assertEquals("11111111", DisplayNames.of("  ", "11111111-2222"))
        assertNull(DisplayNames.of(null, null))
        assertEquals("EX-01 · Excavator", DisplayNames.machine("EX-01", "Excavator", "m"))
        assertEquals("EX-01", DisplayNames.machine("EX-01", null, "m"))
        assertEquals("abcdefgh", DisplayNames.machine(null, null, "abcdefghij"))
    }

    @Test
    fun `field notification taps open the exact record`() {
        assertEquals(InboxLink.CashAck("t1", isFloat = false), InboxLinks.from(null, null, "CASH_TRANSFER", "t1"))
        assertEquals(InboxLink.CashAck("f1", isFloat = true), InboxLinks.from(null, null, "CASH_FLOAT", "f1"))
        assertEquals(InboxLink.Retention("r1"), InboxLinks.from(null, null, "CASH_RETENTION", "r1"))
        assertEquals(InboxLink.RemittanceOverdue("o1"), InboxLinks.from(null, null, "REMITTANCE_OVERDUE", "o1"))
        // Older notifications: the target entity.
        assertEquals(InboxLink.CashAck("t1", isFloat = false), InboxLinks.from("cash_transfer", "t1"))
        assertEquals(InboxLink.CashAck("f1", isFloat = true), InboxLinks.from("supervisor_cash_custody", "f1"))
        assertEquals(InboxLink.Money, InboxLinks.from("cash_transfer", null))
        assertEquals(InboxLink.RemittanceOverdue("o1"), InboxLinks.from("cash_remittance_overdue", "o1"))
        assertEquals(InboxLink.Money, InboxLinks.from("cash_remittance_overdue", null))
        assertEquals(InboxLink.Retention("r1"), InboxLinks.from("cash_retention", "r1"))
        // Unknown kinds fall back to the target.
        assertEquals(InboxLink.Job("j"), InboxLinks.from("job", "j", "SOMETHING_NEW", "x"))
        assertEquals(InboxLink.None, InboxLinks.from(null, null, "SOMETHING_NEW", "x"))
    }
}
