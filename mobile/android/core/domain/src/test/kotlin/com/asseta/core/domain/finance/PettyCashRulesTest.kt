package com.asseta.core.domain.finance

import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal

/** DEC-033 petty cash rules on the phone: policy, gating, form checks, expense checks and neutral flag wording. */
class PettyCashRulesTest {
    private val read = setOf(FieldAccess.PETTY_CASH_READ, FieldAccess.EXPENSE_WRITE)

    @Test
    fun `policy is lenient and missing keys read as off`() {
        val p = PettyCashPolicy.fromValues(Json.parseToJsonElement(
            """{"enabled":true,"count_witness_required":true,"return_evidence_required":true,"advances_enabled":false,"max_expense_amount":"250000.0000"}""",
        ).jsonObject)
        assertTrue(p.countWitnessRequired && p.returnEvidenceRequired)
        assertFalse(p.advancesEnabled)
        assertEquals(BigDecimal("250000.0000"), p.maxExpenseAmount)
        assertEquals(PettyCashPolicy(), PettyCashPolicy.fromValues(null))
        assertNull(PettyCashPolicy.fromValues(Json.parseToJsonElement("""{"max_expense_amount":null}""").jsonObject).maxExpenseAmount)
    }

    @Test
    fun `the feature needs the capability, the permission and the switch`() {
        val caps = setOf(SyncCapabilities.OP_PETTY_CASH)
        assertTrue(FieldAccess(caps, read).pettyCash)
        assertTrue(FieldAccess(caps, read).pettyCashExpense)
        assertFalse(FieldAccess(caps, read).pettyCashCount)
        assertTrue(FieldAccess(caps, read + FieldAccess.PETTY_CASH_COUNT).pettyCashCount)
        assertFalse(FieldAccess(emptySet(), read).pettyCash)
        assertFalse(FieldAccess(null, read).pettyCash)
        assertFalse(FieldAccess(caps, setOf(FieldAccess.EXPENSE_WRITE)).pettyCash)
        assertFalse(FieldAccess(caps, read, disabled = setOf(TenantAccess.PETTY_CASH)).pettyCash)
    }

    @Test
    fun `top-up amount is optional and above the cap needs a reason`() {
        val ok = PettyCashRules.topUp("", " ", "", BigDecimal("40000")) as FormCheck.Valid
        assertNull(ok.value.amount)
        assertNull(ok.value.note)
        assertEquals(listOf(PettyCashMessages.AMOUNT), (PettyCashRules.topUp("0", "", "", null) as FormCheck.Invalid).messages)
        assertEquals(listOf(PettyCashMessages.ABOVE_REASON), (PettyCashRules.topUp("50000", "", "ok", BigDecimal("40000")) as FormCheck.Invalid).messages)
        val above = PettyCashRules.topUp("50000", "", " Big week ", BigDecimal("40000")) as FormCheck.Valid
        assertEquals("Big week", above.value.aboveCapReason)
        assertNull((PettyCashRules.topUp("30000", "", "ignored", BigDecimal("40000")) as FormCheck.Valid).value.aboveCapReason)
        assertTrue(PettyCashRules.aboveCap("50000", BigDecimal("40000")))
        assertFalse(PettyCashRules.aboveCap("50000", null))
        assertEquals(BigDecimal.ZERO, PettyCashRules.headroom("100", "150"))
    }

    @Test
    fun `return, count, holder change and advance checks`() {
        assertEquals(listOf(PettyCashMessages.AMOUNT, PettyCashMessages.EVIDENCE), (PettyCashRules.returnFund("", "", "", 0, true) as FormCheck.Invalid).messages)
        assertTrue(PettyCashRules.returnFund("10", "", "", 0, false) is FormCheck.Valid)
        assertTrue(PettyCashRules.count("0") is FormCheck.Valid)
        assertTrue(PettyCashRules.count("") is FormCheck.Invalid)
        assertTrue(PettyCashRules.advanceClear("0") is FormCheck.Valid)
        assertTrue(PettyCashRules.holderDecision(true, "") is FormCheck.Valid)
        assertEquals(listOf(PettyCashMessages.REASON), (PettyCashRules.holderDecision(false, "no") as FormCheck.Invalid).messages)
        assertEquals(listOf(PettyCashMessages.DISPUTE_REASON), (PettyCashRules.acknowledgement(false, "5", "") as FormCheck.Invalid).messages)
        assertNull((PettyCashRules.acknowledgement(false, "5", "Missing") as FormCheck.Valid).value.amountReceived)
    }

    @Test
    fun `expense from a fund names it, matches its currency and notes overspend and maximum`() {
        val fund = FundChoice("f1", "TZS", BigDecimal("40000"), held = true)
        assertEquals(listOf(PettyCashMessages.FUND_REQUIRED), PettyCashRules.expenseIssues(null, null, "TZS"))
        assertEquals(listOf(PettyCashMessages.currency("TZS")), PettyCashRules.expenseIssues(fund, null, "USD"))
        assertTrue(PettyCashRules.expenseIssues(fund, null, "TZS").isEmpty())
        assertEquals(listOf(PettyCashMessages.ADVANCE_REQUIRED), PettyCashRules.expenseIssues(fund.copy(held = false), null, "TZS"))

        val policy = PettyCashPolicy(maxExpenseAmount = BigDecimal("30000"))
        assertTrue(PettyCashRules.expenseNotes(fund, null, BigDecimal("20000"), "TZS", policy).isEmpty())
        assertEquals(
            listOf(PettyCashMessages.overspend("40000 TZS"), PettyCashMessages.aboveMaximum("30000 TZS")),
            PettyCashRules.expenseNotes(fund, null, BigDecimal("50000"), "TZS", policy),
        )
        // The maximum is in the base currency only; an advance's remaining replaces the fund's available.
        assertEquals(listOf(PettyCashMessages.overspend("40000 TZS")), PettyCashRules.expenseNotes(fund, null, BigDecimal("50000"), "USD", policy))
        val advance = AdvanceChoice("a1", "f1", BigDecimal("5000"))
        assertEquals(listOf(PettyCashMessages.overspend("5000 TZS")), PettyCashRules.expenseNotes(fund, advance, BigDecimal("6000"), "TZS", PettyCashPolicy()))
    }

    @Test
    fun `flags are worded neutrally`() {
        assertEquals(
            listOf("Recorded above what the fund had available", "Paid from collected cash", "Above the petty cash maximum per expense", "New flag"),
            ExpenseFlags.labels(listOf("OVERSPEND", "SPENT_FROM_COLLECTIONS", "ABOVE_PETTY_CASH_MAXIMUM", "NEW_FLAG", "OVERSPEND")),
        )
        assertEquals("To check", ExpenseFlags.TITLE)
        assertFalse(ExpenseFlags.labels(listOf("OVERSPEND")).any { it.contains("fraud", ignoreCase = true) })
        assertEquals("Petty cash", PaidFrom.PETTY_CASH.label)
    }
}
