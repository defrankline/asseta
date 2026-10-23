package com.asseta.supervisor.ui.finance

import com.asseta.core.domain.finance.ApprovalOutlook
import com.asseta.core.domain.finance.ExpenseCapturePolicy
import com.asseta.core.domain.finance.FuelEventType
import com.asseta.core.domain.finance.PendingCashKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.sync.data.FinanceRecord
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.math.BigDecimal

class FinanceTextsTest {
    private val policy = ExpenseCapturePolicy(BigDecimal("100.00"), true, 50.0, BigDecimal("500.00"))

    @Test
    fun rulesSummaryMatchesIos() {
        assertEquals(
            "Receipt photo required above 100 ZMW. GPS fix within ±50 m required. Up to 500 ZMW is approved automatically. (Rules v3.)",
            ExpenseTexts.rulesSummary(policy, "ZMW", "v3"),
        )
        val strict = policy.copy(receiptRequiredAbove = BigDecimal.ZERO, gpsRequired = false, autoApproveLimit = BigDecimal("0.00"))
        assertEquals(
            "Receipt photo required for every expense. Every expense needs a manager's approval. (Rules v3.)",
            ExpenseTexts.rulesSummary(strict, null, "v3"),
        )
    }

    @Test
    fun approvalNoteCoversAutoApproval() {
        assertEquals("Within the auto-approval limit: approved automatically once synced.", ExpenseTexts.approvalNote(ApprovalOutlook.AutoApproved))
        assertEquals("why", ExpenseTexts.approvalNote(ApprovalOutlook.NeedsApproval("why")))
        assertNull(ExpenseTexts.approvalNote(null))
    }

    @Test
    fun fuelCostOnlyForPricedEvents() {
        assertEquals("Cost: 125.5 TZS", CashTexts.fuelCost(FuelEventType.ISSUE, "50", "2.51", "TZS"))
        assertNull(CashTexts.fuelCost(FuelEventType.USAGE, "50", "2.51", "TZS"))
        assertNull(CashTexts.fuelCost(FuelEventType.PURCHASE, "50", "", "TZS"))
        assertNull(CashTexts.fuelCost(FuelEventType.PURCHASE, "50", "2", "TZ"))
        assertEquals("Fuel given to a machine from stock.", CashTexts.fuelExplanation(FuelEventType.ISSUE))
    }

    @Test
    fun myCashListsOnlyCashMovementsSplitByOutcome() {
        fun record(id: String, status: ClientOperationStatus, kind: PendingCashKind?) =
            FinanceRecord(id, "X", "t", BigDecimal.TEN, "TZS", status, null, null, 0, kind)
        val (pending, attention) = MyCashTexts.split(
            listOf(
                record("a", ClientOperationStatus.PENDING, PendingCashKind.COLLECTION),
                record("b", ClientOperationStatus.QUARANTINED, PendingCashKind.HANDOVER),
                record("c", ClientOperationStatus.FAILED, PendingCashKind.CASH_EXPENSE),
                record("d", ClientOperationStatus.ACKED, PendingCashKind.COLLECTION),
                record("e", ClientOperationStatus.PENDING, null), // fuel / company-paid expense: not a cash movement
            ),
        )
        assertEquals(listOf("a", "b"), pending.map { it.operationId })
        assertEquals(listOf("c"), attention.map { it.operationId })
        assertEquals("−10 TZS", MyCashTexts.signed(BigDecimal("10.00"), "TZS", -1))
        assertEquals("Held (read-only subscription) · unverified", MyCashTexts.status(record("b", ClientOperationStatus.QUARANTINED, null)))
    }
}
