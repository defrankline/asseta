package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** ADR-008 sell hours: Cash / Bank / Mobile money / Credit, the fuel switch and the report entries (same cases as iOS). */
class SaleCreditTest {
    private val hours = CustomerHoursPolicy(enabled = true, walkInAllowed = true, transferRequiresApproval = true, reasonCodeRequired = false,
        fieldNoncashPayments = true, fieldCreditSales = true)
    private val caps = setOf(SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_HOURS_SALE_CREDIT)
    private val perms = setOf(FieldAccess.HOURS_PURCHASE)

    private fun sale(walkIn: Boolean, vararg lines: PaymentLine) =
        HoursSaleDraft(walkIn, if (walkIn) null else "c1", "Joe", "", "m1", "20", lines.toList(), "")

    @Test
    fun `credit is offered with the capability and field_credit_sales, or to credit approvers, never to walk-ins`() {
        val a = FieldAccess(caps, perms, hours = hours)
        assertTrue(a.creditSales)
        assertEquals(PaymentMethod.entries, a.saleMethods(walkIn = false))
        assertEquals(listOf(PaymentMethod.CASH, PaymentMethod.BANK, PaymentMethod.MOBILE_MONEY), a.saleMethods(walkIn = true))
        assertFalse(FieldAccess(caps - SyncCapabilities.OP_HOURS_SALE_CREDIT, perms, hours = hours).creditSales)
        val off = hours.copy(fieldCreditSales = false)
        assertFalse(FieldAccess(caps, perms, hours = off).creditSales)
        assertTrue(FieldAccess(caps, perms + FieldAccess.HOURS_CREDIT_ACTIVATE, hours = off).creditSales)
        assertFalse(FieldAccess(caps, perms, hours = hours, disabled = setOf(TenantAccess.CUSTOMER_HOURS)).creditSales)
        // Cash only when the company keeps bank, mobile money and credit with the office.
        assertEquals(listOf(PaymentMethod.CASH), FieldAccess(caps, perms, hours = off.copy(fieldNoncashPayments = false)).saleMethods(false))
    }

    @Test
    fun `a credit part is amount only, one per sale and registered customers only`() {
        val ok = AccountabilityRules.hoursSale(sale(false, PaymentLine(PaymentMethod.CASH, "1000000"), PaymentLine(PaymentMethod.CREDIT, "900000", "x")),
            walkInAllowed = true, noncashAllowed = true, creditAllowed = true)
        val parts = (ok as FormCheck.Valid).value.payments
        assertEquals(PaymentMethod.CREDIT, parts[1].method)
        assertNull(parts[1].reference)

        val walkIn = AccountabilityRules.hoursSale(sale(true, PaymentLine(PaymentMethod.CREDIT, "100")), true, true, creditAllowed = true)
        assertEquals(listOf(AccountabilityMessages.CREDIT_WALK_IN), (walkIn as FormCheck.Invalid).messages)
        val notAllowed = AccountabilityRules.hoursSale(sale(false, PaymentLine(PaymentMethod.CREDIT, "100")), true, true, creditAllowed = false)
        assertEquals(listOf(AccountabilityMessages.CREDIT_OFF), (notAllowed as FormCheck.Invalid).messages)
        val two = sale(false, PaymentLine(PaymentMethod.CREDIT, "100"), PaymentLine(PaymentMethod.CREDIT, "50"))
        assertEquals(listOf(AccountabilityMessages.ONE_CREDIT), (AccountabilityRules.hoursSale(two, true, true, creditAllowed = true) as FormCheck.Invalid).messages)
        assertEquals("To save: keep one credit part.", AccountabilityRules.hoursSaleBlockers(two, true, true, creditAllowed = true))
        assertEquals("To save: change payment 1 to cash.",
            AccountabilityRules.hoursSaleBlockers(sale(true, PaymentLine(PaymentMethod.CREDIT, "100")), true, true, creditAllowed = true))
        // Bank and mobile money still need their reference; credit never does.
        assertTrue(AccountabilityRules.referenceMissing(PaymentLine(PaymentMethod.BANK, "1")))
        assertFalse(AccountabilityRules.referenceMissing(PaymentLine(PaymentMethod.CREDIT, "1")))
    }

    @Test
    fun `the policy reads field_credit_sales and the reminder days`() {
        val base = mapOf("enabled" to JsonPrimitive(true), "walk_in_allowed" to JsonPrimitive(true),
            "transfer_requires_approval" to JsonPrimitive(true), "reason_code_required" to JsonPrimitive(false))
        val older = CustomerHoursPolicy.fromValues(JsonObject(base))!!
        assertFalse(older.fieldCreditSales)
        assertEquals(3, older.reportReminderDays)
        val newer = CustomerHoursPolicy.fromValues(JsonObject(base + mapOf("field_credit_sales" to JsonPrimitive(true), "machine_report_reminder_days" to JsonPrimitive(5))))!!
        assertTrue(newer.fieldCreditSales)
        assertEquals(5, newer.reportReminderDays)
        assertNull(CustomerHoursPolicy.fromValues(JsonObject(base + ("machine_report_reminder_days" to JsonNull)))!!.reportReminderDays)
        // Applied: the setting once known (explicit null = off), 3 while the policy is unknown (failed / refused load).
        assertEquals(3, CustomerHoursPolicy.reminderDays(null))
        assertEquals(5, CustomerHoursPolicy.reminderDays(newer))
        assertNull(CustomerHoursPolicy.reminderDays(CustomerHoursPolicy.fromValues(JsonObject(base + ("machine_report_reminder_days" to JsonNull)))))
    }

    @Test
    fun `fuel is hidden when the company switched it off`() {
        assertTrue(FuelSwitch.on(emptyList()))
        assertFalse(FuelSwitch.on(listOf(TenantAccess.FUEL)))
        assertFalse(FieldAccess(caps, perms, disabled = setOf(TenantAccess.FUEL)).fuel)
        assertTrue(FieldAccess(caps, perms).fuel)
    }

    @Test
    fun `machine reports and invoice payments follow capability and permission`() {
        val c = setOf(SyncCapabilities.OP_MACHINE_REPORT, SyncCapabilities.OP_CREDIT_INVOICE_PAYMENT)
        assertTrue(FieldAccess(c, setOf(FieldAccess.MACHINE_REPORT_SUBMIT)).machineReport)
        assertFalse(FieldAccess(c, emptySet()).machineReport)
        assertFalse(FieldAccess(emptySet(), setOf(FieldAccess.MACHINE_REPORT_SUBMIT)).machineReport)
        assertTrue(FieldAccess(c, setOf(FieldAccess.INVOICE_PAYMENT), hours = hours).creditInvoicePayment)
        assertFalse(FieldAccess(c, setOf(FieldAccess.INVOICE_PAYMENT), hours = hours, disabled = setOf(TenantAccess.CUSTOMER_HOURS)).creditInvoicePayment)
    }
}
