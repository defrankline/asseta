package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.accountability.DepositAccountOption
import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.accountability.RemittanceRequirements
import com.asseta.core.domain.accountability.RemittanceRules
import com.asseta.core.model.owner.OverdueAmountDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.data.WaitingReason
import com.asseta.supervisor.ui.FieldTexts
import com.asseta.supervisor.ui.finance.CashForm
import com.asseta.supervisor.ui.finance.RemittanceForm
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** DEC-031 Phase 3 on the field app: the handover form's remittance details, conflicts and held-too-long flags. */
class RemittanceDetailsPresentationTest {
    private val bank = DepositAccountOption("a1", "CRDB main", "BANK", "CRDB", "•••• 4821", "TZS", true)
    private val bankUsd = DepositAccountOption("a2", "CRDB dollar", "BANK", "CRDB", null, "USD", true)
    private val till = DepositAccountOption("a3", "M-Pesa till", "MOBILE_MONEY", null, "•••• 0099", "TZS", true)
    private val closed = DepositAccountOption("a4", "Old account", "BANK", null, null, "TZS", false)
    private val accounts = listOf(bank, bankUsd, till, closed)

    @Test
    fun `picker lists active accounts of the method and currency with institution and masked number`() {
        val options = RemittanceForm.accountOptions(accounts, RemittanceMethod.BANK_DEPOSIT, "tzs")
        assertEquals(listOf("a1"), options.map { it.id })
        assertEquals("CRDB · •••• 4821", options.single().subtitle)
        assertEquals(listOf("a3"), RemittanceForm.accountOptions(accounts, RemittanceMethod.MOBILE_MONEY, "TZS").map { it.id })
        assertTrue(RemittanceForm.accountOptions(accounts, RemittanceMethod.CASH_TO_OFFICE, "TZS").isEmpty())
    }

    @Test
    fun `choosing an account sets the method and a new method drops an account of another type`() {
        val chosen = RemittanceForm.selectAccount(CashForm(kind = "HANDOVER", currency = "TZS"), "a3", accounts)
        assertEquals(RemittanceMethod.MOBILE_MONEY, chosen.method)
        assertEquals("a3", chosen.depositAccountId)
        assertNull(RemittanceForm.selectMethod(chosen, RemittanceMethod.BANK_DEPOSIT, accounts).depositAccountId)
        assertEquals("a3", RemittanceForm.selectMethod(chosen, RemittanceMethod.MOBILE_MONEY, accounts).depositAccountId)
    }

    @Test
    fun `requirements change the labels and block saving until met`() {
        val none = RemittanceRequirements()
        val all = RemittanceRequirements(accountRequired = true, referenceRequired = true, evidenceRequired = true)
        assertEquals("Paid into (optional)", RemittanceForm.accountLabel(none))
        assertEquals("Paid into", RemittanceForm.accountLabel(all))
        assertEquals("Transaction reference", RemittanceForm.referenceLabel(all, RemittanceMethod.BANK_DEPOSIT))
        assertEquals("Reference (deposit slip, transaction no.) (optional)", RemittanceForm.referenceLabel(all, RemittanceMethod.CASH_TO_OFFICE))
        assertEquals("Deposit slip or payment confirmation", RemittanceForm.photosLabel(all))
        assertEquals("Deposit slip or payment confirmation (optional)", RemittanceForm.photosLabel(none))

        val form = CashForm(kind = "HANDOVER", currency = "TZS", amount = "1000", method = RemittanceMethod.BANK_DEPOSIT)
        assertEquals(
            listOf(RemittanceRules.ERR_ACCOUNT, RemittanceRules.ERR_REFERENCE, RemittanceRules.ERR_EVIDENCE),
            RemittanceForm.issues(form, all, accounts),
        )
        assertTrue(RemittanceForm.issues(form, none, accounts).isEmpty())
        assertEquals(listOf(RemittanceRules.ERR_ACCOUNT_GONE), RemittanceForm.issues(form.copy(depositAccountId = "a4"), none, accounts))
        assertEquals(listOf(RemittanceRules.ERR_ACCOUNT_CURRENCY), RemittanceForm.issues(form.copy(depositAccountId = "a2"), none, accounts))
    }

    @Test
    fun `method names and remittance conflicts are plain words`() {
        assertEquals("Cash to the office", FieldAccountabilityTexts.remitMethod(RemittanceMethod.CASH_TO_OFFICE))
        assertEquals("Bank deposit", FieldAccountabilityTexts.remitMethod(RemittanceMethod.BANK_DEPOSIT))
        assertEquals("Mobile money", FieldAccountabilityTexts.remitMethod(RemittanceMethod.MOBILE_MONEY))
        listOf(
            "REMITTANCE_REFERENCE_REQUIRED", "REMITTANCE_EVIDENCE_REQUIRED", "REMITTANCE_ACCOUNT_REQUIRED", "DEPOSIT_ACCOUNT_INACTIVE",
            "REMITTANCE_ACCOUNT_MISMATCH", "DEPOSIT_ACCOUNT_CURRENCY_MISMATCH",
        ).forEach { code -> assertTrue(code, FieldAccountabilityTexts.conflict(code)!!.endsWith(".")) }
        assertEquals(
            "The account you chose is no longer in use. Record the handover again with another account.",
            FieldAccountabilityTexts.conflict("DEPOSIT_ACCOUNT_INACTIVE"),
        )
        assertEquals("Waiting for its photos to upload", FieldTexts.waiting(WaitingReason.UPLOAD, OpTypes.CASH_HANDOVER))
        assertEquals("Waiting for its photo/receipt/signature upload", FieldTexts.waiting(WaitingReason.UPLOAD, OpTypes.EXPENSE))
    }

    private val held = RemittanceOverdueDto(
        id = "o2", staffMemberId = "s1", staffMemberName = "Baraka", localDay = "2026-10-26", cutoffHour = 9,
        amounts = listOf(OverdueAmountDto("TZS", "80000")), flaggedAt = "2026-10-26T09:00:00Z", policyVersion = "v2",
        reason = RemittanceOverdueDto.HELD_TOO_LONG, heldSince = "2026-10-22T10:15:00Z", maxHoldingDays = 3,
    )

    @Test
    fun `held too long shows since when and the allowance instead of the cut-off`() {
        val rows = RemittanceOverdueText.rows(held, zone = ZoneOffset.UTC)
        assertEquals(
            listOf("Cash held by", "Not remitted", "Reason", "Day", "Held since", "Allowed", "Flagged"),
            rows.map { it.first },
        )
        assertEquals("Held longer than allowed", rows.toMap()["Reason"])
        assertEquals("3 days", rows.toMap()["Allowed"])
        assertEquals(
            "Held since ${rows.toMap()["Held since"]}, longer than the allowed 3 days. Remit this cash to the office as soon as you can.",
            RemittanceOverdueText.footer(held, ZoneOffset.UTC),
        )
        assertEquals("1 day", FieldAccountabilityTexts.days(1))
        assertEquals(
            "Held longer than allowed. Remit this cash to the office as soon as you can.",
            RemittanceOverdueText.footer(held.copy(heldSince = null), ZoneOffset.UTC),
        )
    }
}
