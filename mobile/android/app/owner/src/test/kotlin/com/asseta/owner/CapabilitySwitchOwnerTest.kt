package com.asseta.owner

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.accountability.DashboardPresentation
import com.asseta.owner.ui.accountability.DecisionKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Follow-up F1 on the Owner app: ENGINE_HOURS and CASH_CUSTODY switched off hide sections, tiles, rows and screens. */
class CapabilitySwitchOwnerTest {
    private val perms = setOf("tenant.finance.read", "tenant.meter.read", "tenant.hours.read", "tenant.approval.read")
    private val on = OwnerFeatures(perms)
    private val engineOff = OwnerFeatures(perms, setOf(TenantAccess.ENGINE_HOURS))
    private val cashOff = OwnerFeatures(perms, setOf(TenantAccess.CASH_CUSTODY))

    private fun summary(disabled: String = "[]") = NetworkFactory.json.decodeFromString(
        AccountabilitySummaryDto.serializer(),
        """{"as_of":"2026-10-25T08:00:00Z","policy_version":"v3","disabled_capabilities":$disabled,
        "outstanding_approvals":{"approval_requests":1,"payments_to_verify":0,"remittances_to_verify":2,"cash_retentions":1,
          "custody_adjustments":1,"write_offs":1,"total":6},
        "cash":{"custodians":[],"transfers_awaiting_acknowledgement":[],"floats_awaiting_acknowledgement":[],
          "remittances_awaiting_confirmation":[],"partial_remittances_in_window":1,"remittance_cutoff_hour":18,"remittances_overdue_today":2},
        "discrepancies":{"open_variances":[],"write_offs_proposed":1,"sync_conflicts_unresolved":3},
        "engine_hours":{"machines":2,"by_status":{}},"unexplained_hours":{"hours":"1","items":[]},"missing_daily_reports":{"items":[]}}""",
    )

    @Test
    fun `engine hours off hides the meter decision sections`() {
        val kinds = DecisionKind.visible(engineOff)
        assertFalse(DecisionKind.BASELINE in kinds)
        assertFalse(DecisionKind.CLASSIFICATION in kinds)
        assertFalse(DecisionKind.CORRECTION in kinds)
        assertTrue(DecisionKind.WRITE_OFF in kinds && DecisionKind.DISCOUNT in kinds)
        assertTrue(DecisionKind.BASELINE in DecisionKind.visible(on))
    }

    @Test
    fun `cash custody off hides write-offs, retentions and adjustments`() {
        val kinds = DecisionKind.visible(cashOff)
        assertFalse(DecisionKind.WRITE_OFF in kinds)
        assertFalse(DecisionKind.RETENTION in kinds)
        assertFalse(DecisionKind.ADJUSTMENT in kinds)
        assertTrue(DecisionKind.BASELINE in kinds)
    }

    @Test
    fun `deep links to hidden kinds fall back to the list`() {
        val baseline = OwnerDestination.Decision(DecisionKinds.BASELINE, ID1)
        assertEquals(OwnerDestination.Approvals(), engineOff.route(baseline))
        assertEquals(baseline, on.route(baseline))
        assertEquals(baseline, cashOff.route(baseline))
        assertEquals(OwnerDestination.Approvals(), cashOff.route(OwnerDestination.Decision(DecisionKinds.RETENTION, ID1)))
        assertEquals(OwnerDestination.Cash, cashOff.route(OwnerDestination.CashRecord(RecordKinds.CASH_TRANSFER, ID1)))
        assertEquals(OwnerDestination.Cash, cashOff.route(OwnerDestination.CashRecord(RecordKinds.CASH_FLOAT, ID1)))
        assertEquals(OwnerDestination.Cash, cashOff.route(OwnerDestination.RemittanceOverdue(ID1)))
        assertEquals(OwnerDestination.Cash, cashOff.route(OwnerDestination.RemittanceOverdue()))
        // The cash basics stay.
        assertEquals(OwnerDestination.Handover(ID1), cashOff.route(OwnerDestination.Handover(ID1)))
        val hoursOff = OwnerFeatures(perms, setOf(TenantAccess.CUSTOMER_HOURS))
        assertEquals(OwnerDestination.Approvals(), hoursOff.route(OwnerDestination.Decision(DecisionKinds.DISCOUNT, ID1)))
    }

    @Test
    fun `engine hours off (from me or from the summary) hides the engine-hour tiles`() {
        val all = DashboardPresentation.tiles(summary(), on).map { it.key }
        assertTrue(all.containsAll(listOf("engine_hours", "unexplained_hours", "missing_daily_reports")))
        listOf(DashboardPresentation.tiles(summary(), engineOff), DashboardPresentation.tiles(summary("""["ENGINE_HOURS"]"""), on)).forEach { tiles ->
            val keys = tiles.map { it.key }
            assertFalse("engine_hours" in keys)
            assertFalse("unexplained_hours" in keys)
            assertFalse("missing_daily_reports" in keys)
            assertTrue("cash" in keys)
        }
    }

    @Test
    fun `cash custody off keeps the cash basics and hides the custody additions`() {
        val full = DashboardPresentation.tiles(summary(), on).associateBy { it.key }
        assertTrue(full.getValue("cash").rows.any { it.first == "Remittances overdue today" })
        listOf(DashboardPresentation.tiles(summary(), cashOff), DashboardPresentation.tiles(summary("""["CASH_CUSTODY"]"""), on)).forEach { tiles ->
            val byKey = tiles.associateBy { it.key }
            val cash = byKey.getValue("cash")
            val labels = cash.rows.map { it.first }
            assertEquals(listOf("Remittances awaiting confirmation"), labels)
            assertTrue(cash.moreLinks.isEmpty())
            assertEquals(null, cash.footer)
            val approvals = byKey.getValue("approvals").rows.map { it.first }
            assertEquals(listOf("Total", "Approval requests", "Payments to verify", "Remittances to verify"), approvals)
            assertEquals(listOf("Sync conflicts to review"), byKey.getValue("discrepancies").rows.map { it.first })
        }
    }
}
