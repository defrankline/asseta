package com.asseta.core.domain.finance

import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.policy.BlockReason
import com.asseta.core.domain.policy.PolicySnapshot
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal
import java.time.Instant

class ExpenseRulesTest {
    private val now = Instant.parse("2026-10-21T08:00:00Z")
    private val policy = ExpenseCapturePolicy(BigDecimal("100"), gpsRequired = true, gpsMaxAccuracyM = 50.0, autoApproveLimit = BigDecimal("500"))
    private val fix = GpsOutcome.Fix(-15.4, 28.3, 8.0, now, "fused")

    private fun draft(
        amount: String = "80.00",
        currency: String = "ZMW",
        receipt: Boolean = false,
        gps: GpsOutcome? = fix,
        machine: String? = null,
        job: String? = null,
        jobMachine: String? = null,
    ) = ExpenseDraft("cat", "Hydraulic oil", "Fuel Depot", amount, currency, PaidFrom.CASH_CUSTODY, machine, job, jobMachine, receipt, gps)

    private fun codes(a: ExpenseAssessment) = a.issues.map { it.code }

    @Test
    fun belowThresholdNeedsNoReceiptAndIsAutoApproved() {
        val a = ExpenseRules.assess(draft(), policy, "ZMW")
        assertTrue(a.isValid)
        assertFalse(a.receiptRequired)
        assertEquals(ApprovalOutlook.AutoApproved, a.approval)
        assertEquals(BigDecimal("80"), a.amount)
    }

    @Test
    fun receiptIsRequiredStrictlyAboveTheThresholdComparedExactly() {
        assertTrue(ExpenseRules.assess(draft("100.0000"), policy, "ZMW").isValid) // equal: not above
        val above = ExpenseRules.assess(draft("100.0001"), policy, "ZMW")
        assertEquals(listOf(ExpenseViolation.RECEIPT_REQUIRED), codes(above))
        assertTrue(above.receiptReason!!.contains("100 ZMW"))
        assertTrue(ExpenseRules.assess(draft("100.0001", receipt = true), policy, "ZMW").isValid)
    }

    @Test
    fun aboveAutoApproveLimitExplainsWhyApprovalIsNeeded() {
        val a = ExpenseRules.assess(draft("500.01", receipt = true), policy, "ZMW")
        assertTrue(a.isValid)
        val outlook = a.approval as ApprovalOutlook.NeedsApproval
        assertTrue(outlook.reason.contains("500.01 ZMW is above the auto-approval limit of 500 ZMW"))
        assertEquals(ApprovalOutlook.AutoApproved, ExpenseRules.assess(draft("500", receipt = true), policy, "ZMW").approval)
    }

    @Test
    fun foreignOrUnknownBaseCurrencyNeedsReceiptAndApproval() {
        val foreign = ExpenseRules.assess(draft("5", currency = "usd"), policy, "ZMW")
        assertEquals(listOf(ExpenseViolation.RECEIPT_REQUIRED), codes(foreign))
        assertEquals("USD", foreign.currency)
        assertTrue(foreign.approval is ApprovalOutlook.NeedsApproval)
        val unknownBase = ExpenseRules.assess(draft("5", receipt = true), policy, null)
        assertTrue(unknownBase.receiptRequired)
        assertTrue(unknownBase.approval is ApprovalOutlook.NeedsApproval)
    }

    @Test
    fun gpsRequiredAndAccuracyAreEnforcedOffline() {
        assertEquals(listOf(ExpenseViolation.GPS_NOT_ATTEMPTED), codes(ExpenseRules.assess(draft(gps = null), policy, "ZMW")))
        assertEquals(listOf(ExpenseViolation.GPS_REQUIRED), codes(ExpenseRules.assess(draft(gps = GpsOutcome.Timeout), policy, "ZMW")))
        val coarse = GpsOutcome.Fix(-15.4, 28.3, 50.5, now, "fused")
        assertEquals(listOf(ExpenseViolation.GPS_TOO_INACCURATE), codes(ExpenseRules.assess(draft(gps = coarse), policy, "ZMW")))
        val noAccuracy = GpsOutcome.Fix(-15.4, 28.3, null, now, "fused")
        assertEquals(listOf(ExpenseViolation.GPS_TOO_INACCURATE), codes(ExpenseRules.assess(draft(gps = noAccuracy), policy, "ZMW")))
        val relaxed = policy.copy(gpsRequired = false)
        assertTrue(ExpenseRules.assess(draft(gps = GpsOutcome.PermissionDenied), relaxed, "ZMW").isValid)
        assertEquals(listOf(ExpenseViolation.GPS_NOT_ATTEMPTED), codes(ExpenseRules.assess(draft(gps = null), relaxed, "ZMW")))
    }

    @Test
    fun formFieldsAndAttributionAreValidated() {
        val bad = ExpenseRules.assess(
            ExpenseDraft(null, " ", "", "12.34567", "ZM", null, "m2", "j1", "m1", false, fix), policy, "ZMW",
        )
        assertEquals(
            listOf(
                ExpenseViolation.CATEGORY_REQUIRED, ExpenseViolation.DESCRIPTION_REQUIRED, ExpenseViolation.AMOUNT_INVALID,
                ExpenseViolation.CURRENCY_INVALID, ExpenseViolation.PAID_FROM_REQUIRED, ExpenseViolation.ATTRIBUTION_MISMATCH,
            ),
            codes(bad),
        )
        assertNull(bad.approval)
        assertTrue(ExpenseRules.assess(draft(machine = "m1", job = "j1", jobMachine = "m1"), policy, "ZMW").isValid)
    }

    @Test
    fun policyIsParsedFromSnapshotStringsWithoutFloatsAndFailsClosed() {
        val values = buildJsonObject {
            put("receipt_required_above", "250.10"); put("gps_required", true); put("gps_max_accuracy_m", 100.0)
            put("auto_approve_limit", JsonPrimitive(BigDecimal("1000.30")))
        }
        val parsed = ExpenseCapturePolicy.fromValues(values)!!
        assertEquals(BigDecimal("250.10"), parsed.receiptRequiredAbove)
        assertEquals(BigDecimal("1000.30"), parsed.autoApproveLimit)
        assertNull(ExpenseCapturePolicy.fromValues(buildJsonObject { put("gps_required", true) }))

        fun snap(validUntil: Instant, v: kotlinx.serialization.json.JsonObject = values) =
            PolicySnapshot(ExpensePolicySelector.EXPENSE_CAPTURE, "tenant", listOf("v"), "s1", v, validUntil)
        val grant = now.plusSeconds(3600)
        assertTrue(ExpensePolicySelector.select(listOf(snap(now.plusSeconds(60))), now, grant) is ExpensePolicyDecision.Allowed)
        fun reason(d: ExpensePolicyDecision) = (d as ExpensePolicyDecision.Blocked).reason
        assertEquals(BlockReason.NO_SNAPSHOT, reason(ExpensePolicySelector.select(emptyList(), now, grant)))
        assertEquals(BlockReason.SNAPSHOT_EXPIRED, reason(ExpensePolicySelector.select(listOf(snap(now.minusSeconds(1))), now, grant)))
        assertEquals(BlockReason.OFFLINE_GRANT_EXPIRED, reason(ExpensePolicySelector.select(listOf(snap(now.plusSeconds(60))), now, now.minusSeconds(1))))
        val unreadable = snap(now.plusSeconds(60), buildJsonObject { put("receipt_required_above", "abc") })
        assertEquals(BlockReason.POLICY_UNREADABLE, reason(ExpensePolicySelector.select(listOf(unreadable), now, grant)))
        val blocked = ExpensePolicySelector.select(emptyList(), now, grant) as ExpensePolicyDecision.Blocked
        assertTrue(blocked.message.startsWith("Connect to refresh rules."))
    }
}
