package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.sync.SyncCapabilities
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDateTime
import java.time.ZoneId

/** "Book the job" with an hours sale (OP_HOURS_SALE_BOOKING); same cases as iOS `SaleBookingTests`. */
class SaleBookingTest {
    private val hours = CustomerHoursPolicy(enabled = true, walkInAllowed = true, transferRequiresApproval = true, reasonCodeRequired = false)
    private val caps = setOf(SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_HOURS_SALE_BOOKING)
    private val perms = setOf(FieldAccess.HOURS_PURCHASE, FieldAccess.JOB_REQUEST)
    private val start = 1_800_000_000_000L

    private fun sale(job: SaleJobDraft?) = HoursSaleDraft(false, "c1", "", "", "m1", "6", listOf(PaymentLine(PaymentMethod.CASH, "570000")), "", job)

    @Test
    fun `book the job needs the capability, the job request permission and hours sales`() {
        assertTrue(FieldAccess(caps, perms, hours = hours).bookSaleJob)
        assertFalse(FieldAccess(caps - SyncCapabilities.OP_HOURS_SALE_BOOKING, perms, hours = hours).bookSaleJob)
        assertFalse(FieldAccess(caps, perms - FieldAccess.JOB_REQUEST, hours = hours).bookSaleJob)
        assertFalse(FieldAccess(caps, perms - FieldAccess.HOURS_PURCHASE, hours = hours).bookSaleJob)
        assertFalse(FieldAccess(caps, perms, hours = hours, disabled = setOf("CUSTOMER_HOURS")).bookSaleJob)
        assertFalse(FieldAccess(null, perms, hours = hours).bookSaleJob)
    }

    @Test
    fun `the start opens tomorrow at 08 00 and the end offered is the sale hours later`() {
        val zone = ZoneId.of("Africa/Dar_es_Salaam")
        val now = LocalDateTime.of(2026, 11, 11, 21, 48).atZone(zone).toInstant().toEpochMilli()
        assertEquals(LocalDateTime.of(2026, 11, 12, 8, 0).atZone(zone).toInstant().toEpochMilli(), SaleBooking.defaultStartMs(now, zone))
        assertEquals(start + 6 * 3_600_000L, SaleBooking.endAfterHoursMs(start, "6"))
        assertEquals(start + 150 * 60_000L, SaleBooking.endAfterHoursMs(start, "2.5"))
        assertNull(SaleBooking.endAfterHoursMs(start, ""))
        assertNull(SaleBooking.endAfterHoursMs(start, "0"))
    }

    @Test
    fun `the end must be after the start and a contract is chosen when offered`() {
        val ok = AccountabilityRules.hoursSale(sale(SaleJobDraft(start, start + 1, "s1", null, "  dig the trench  ")), walkInAllowed = true)
        val job = (ok as FormCheck.Valid).value.job!!
        assertEquals(SaleJobValues(start, start + 1, "s1", null, "dig the trench"), job)
        assertNull((AccountabilityRules.hoursSale(sale(null), walkInAllowed = true) as FormCheck.Valid).value.job)
        assertTrue(AccountabilityRules.hoursSale(sale(SaleJobDraft(start)), walkInAllowed = true) is FormCheck.Valid)

        val same = AccountabilityRules.hoursSale(sale(SaleJobDraft(start, start)), walkInAllowed = true)
        assertEquals(listOf(AccountabilityMessages.JOB_END), (same as FormCheck.Invalid).messages)
        assertEquals("To save: set the job's end after its start.",
            AccountabilityRules.hoursSaleBlockers(sale(SaleJobDraft(start, start - 60_000)), walkInAllowed = true))

        val choose = sale(SaleJobDraft(start, contractRequired = true))
        assertEquals(listOf(AccountabilityMessages.JOB_CONTRACT), (AccountabilityRules.hoursSale(choose, true) as FormCheck.Invalid).messages)
        assertEquals("To save: choose the job's contract.", AccountabilityRules.hoursSaleBlockers(choose, true))
        assertTrue(AccountabilityRules.hoursSale(sale(SaleJobDraft(start, contractId = "k2", contractRequired = true)), true) is FormCheck.Valid)

        // The job's rules follow the sale's in the "To save" line.
        val both = sale(SaleJobDraft(start, start, contractRequired = true)).copy(machineId = null)
        assertEquals("To save: choose the machine, set the job's end after its start and choose the job's contract.",
            AccountabilityRules.hoursSaleBlockers(both, true))
    }
}
