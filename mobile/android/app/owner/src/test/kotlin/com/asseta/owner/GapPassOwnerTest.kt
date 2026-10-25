package com.asseta.owner

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.data.Load
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.accountability.CashRecords
import com.asseta.owner.ui.accountability.DashboardPresentation
import com.asseta.owner.ui.accountability.DecisionKind
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneOffset

/** DEC-030 gap pass on the Owner app: capabilities, names, exact-record deep links, overdue remittances. */
class GapPassOwnerTest {
    private val h = OwnerHarness()

    @After fun tearDown() = h.close()

    private fun discount(customerName: String?, proposedByName: String?) = """{"id":"$ID1","customer_id":"$ID2",
        "customer_name":${customerName?.let { "\"$it\"" } ?: "null"},"percent":"10.00","effective_from":"2026-10-25T00:00:00Z",
        "effective_to":null,"reason":"Loyal","reason_code_id":null,"status":"APPROVED","proposed_by":"$ID2",
        "proposed_by_name":${proposedByName?.let { "\"$it\"" } ?: "null"},"proposed_at":"2026-10-25T08:00:00Z","decided_by":"$ID1",
        "decided_by_name":"Neema","decided_at":"2026-10-25T09:00:00Z","decision_note":"Fine","revoked_by":null,"revoked_at":null,
        "revoke_reason":null,"version":2,"some_future_field":{"x":1}}"""

    @Test
    fun `a decision opens by id and shows names (short id only when null)`() = runBlocking {
        h.ok(discount("Kilimo Ltd", "Asha"))
        val item = (h.data.decision(DecisionKind.DISCOUNT, ID1) as Load.Ok).snapshot.data.single()
        assertTrue(h.server.takeRequest().url.toString().endsWith("/customer-discounts/$ID1"))
        assertFalse(item.pending) // decided: shown with its status, no decision buttons
        val fields = item.fields.associate { it.label to it.value }
        assertEquals("Kilimo Ltd", fields["Customer"])
        assertEquals("Asha", fields["Proposed by"])
        assertEquals("Neema", fields["Decided by"])
        assertEquals("Fine", fields["Decision note"])
        assertEquals("Asha", item.proposedByName)

        h.ok(discount(null, null))
        val bare = (h.data.decision(DecisionKind.DISCOUNT, ID1) as Load.Ok).snapshot.data.single()
        assertEquals(ID2.take(8), bare.fields.first { it.label == "Customer" }.value)
        assertEquals(ID2.take(8), bare.proposedByName)
    }

    @Test
    fun `notification kinds open the exact record`() {
        fun kind(k: String) = DeepLinkRouter.fromTarget(null, null, null, kind = k, recordId = ID1)
        assertEquals(OwnerDestination.CashRecord(RecordKinds.CASH_TRANSFER, ID1), kind("CASH_TRANSFER"))
        assertEquals(OwnerDestination.CashRecord(RecordKinds.CASH_FLOAT, ID1), kind("CASH_FLOAT"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, ID1), kind("CASH_VARIANCE"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.RETENTION, ID1), kind("CASH_RETENTION"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.ADJUSTMENT, ID1), kind("CUSTODY_ADJUSTMENT"))
        assertEquals(OwnerDestination.Handover(ID1), kind("CASH_REMITTANCE"))
        assertEquals(OwnerDestination.RemittanceOverdue(ID1), kind("REMITTANCE_OVERDUE"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.DISCOUNT, ID1), kind("HOURS_DISCOUNT"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CREDIT, ID1), kind("HOURS_CREDIT"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.HOURS_TRANSFER, ID1), kind("HOURS_TRANSFER"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CANCELLATION, ID1), kind("HOURS_CANCELLATION"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.BASELINE, ID1), kind("METER_BASELINE"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CORRECTION, ID1), kind("METER_CORRECTION"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CLASSIFICATION, ID1), kind("ENGINE_HOURS_CLASSIFICATION"))
        // Unknown kinds (or a bad id) fall back to the target / link / notification as before.
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromTarget(null, null, "/tenant/approvals", kind = "SOMETHING_NEW", recordId = ID1))
        assertEquals(OwnerDestination.Notifications(ID2), DeepLinkRouter.fromTarget(null, null, null, ID2, kind = "CASH_TRANSFER", recordId = "nope"))
    }

    @Test
    fun `push data and web links name the exact record`() {
        val push = DeepLinkRouter.fromPush(
            mapOf("notification_id" to ID2, "tenant_id" to TENANT, "link" to "/tenant/finance/cash/floats/$ID1", "kind" to "CASH_FLOAT", "record_id" to ID1),
        )!!
        assertEquals(OwnerDestination.CashRecord(RecordKinds.CASH_FLOAT, ID1), push.destination)
        // Only the link (older payload): the web detail route still resolves.
        assertEquals(OwnerDestination.RemittanceOverdue(ID1), DeepLinkRouter.fromPath("/tenant/finance/cash/remittance-overdue/$ID1"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.RETENTION, ID1), DeepLinkRouter.fromPath("/tenant/finance/cash/retentions/$ID1"))
        assertEquals(OwnerDestination.Handover(ID1), DeepLinkRouter.fromPath("/tenant/finance/cash/remittances/$ID1"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CREDIT, ID1), DeepLinkRouter.fromPath("/tenant/hours/credit/$ID1"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CORRECTION, ID1), DeepLinkRouter.fromPath("/tenant/meter-corrections/$ID1"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.CLASSIFICATION, ID1), DeepLinkRouter.fromPath("/tenant/engine-hours/classifications/$ID1"))
        assertEquals(OwnerDestination.Cash, DeepLinkRouter.fromPath("/tenant/finance/cash/transfers"))
        assertEquals(OwnerDestination.RemittanceOverdue(), DeepLinkRouter.fromPath("/tenant/finance/cash/remittance-overdue"))
        // A push with only a record is still ours.
        assertEquals(OwnerDestination.Handover(ID1), DeepLinkRouter.fromPush(mapOf("kind" to "CASH_REMITTANCE", "record_id" to ID1))!!.destination)
    }

    private fun summary(cash: String) = NetworkFactory.json.decodeFromString(
        AccountabilitySummaryDto.serializer(),
        """{"as_of":"2026-10-25T08:00:00Z","policy_version":"v3","cash":$cash,
        "customer_hours":{"activated":"1","consumed":"0","remaining":"1","awaiting_activation":"0","expired":"0","open_overruns":0},
        "hours_awaiting_activation":{"hours":"2","purchases_awaiting_payment":1,"purchases_partly_active":0}}""",
    )

    @Test
    fun `cash tile shows overdue remittances only when the cut-off is on`() {
        val finance = OwnerFeatures(setOf("tenant.finance.read", "tenant.hours.read"))
        val on = DashboardPresentation.tiles(
            summary("""{"custodians":[],"remittance_cutoff_hour":7,"remittances_overdue_today":2}"""), finance,
        ).first { it.key == "cash" }
        assertEquals("2", on.rows.first { it.first == "Remittances overdue today" }.second)
        assertEquals("Cut-off 07:00", on.footer)
        assertEquals(listOf("Remittances overdue today" to OwnerDestination.RemittanceOverdue()), on.moreLinks)
        val off = DashboardPresentation.tiles(summary("""{"custodians":[]}"""), finance).first { it.key == "cash" }
        assertTrue(off.rows.none { it.first == "Remittances overdue today" })
        assertTrue(off.moreLinks.isEmpty())
        assertNull(off.footer)
    }

    @Test
    fun `customer hours switched off hides its sections and tiles`() {
        val perms = setOf("tenant.hours.read", "tenant.meter.read")
        val off = OwnerSession(TENANT, "Acme", perms, readOnly = false, disabledCapabilities = setOf(TenantAccess.CUSTOMER_HOURS)).features
        assertEquals(listOf(DecisionKind.BASELINE, DecisionKind.CLASSIFICATION, DecisionKind.CORRECTION), DecisionKind.visible(off))
        val keys = DashboardPresentation.tiles(summary("""{"custodians":[]}"""), off).map { it.key }
        assertFalse("customer_hours" in keys)
        assertFalse("hours_awaiting_activation" in keys)
        val on = OwnerFeatures(perms)
        assertTrue(DecisionKind.DISCOUNT in DecisionKind.visible(on))
        assertTrue("customer_hours" in DashboardPresentation.tiles(summary("""{"custodians":[]}"""), on).map { it.key })
    }

    @Test
    fun `me lists disabled capabilities (missing = none)`() {
        val me = """{"user_id":"$ID1","email":"a@b.c","display_name":"A","tenants":[{"tenant_id":"$TENANT","name":"Acme","status":"ACTIVE",
            "disabled_capabilities":["CUSTOMER_HOURS"]},{"tenant_id":"$ID2","name":"Old","status":"ACTIVE"}]}"""
        val parsed = NetworkFactory.json.decodeFromString(com.asseta.core.model.MeResponse.serializer(), me)
        assertEquals(listOf("CUSTOMER_HOURS"), parsed.tenants[0].disabledCapabilities)
        assertTrue(parsed.tenants[1].disabledCapabilities.isEmpty())
    }

    @Test
    fun `cash transfer record shows names and overdue flags read by day`() = runBlocking {
        val t = CashTransferDto(ID1, null, ID2, "s-2", "50000", null, "TZS", CashTransferDto.PENDING, "2026-10-25T08:00:00Z",
            "2026-10-25T08:00:00Z", source = "SYNC", fromStaffName = "Juma")
        val record = CashRecords.transfer(t, ZoneOffset.UTC)
        val fields = record.fields.associate { it.label to it.value }
        assertEquals("Juma", fields["From"])
        assertEquals("s-2", fields["To"]) // no name: the short id
        h.ok("""{"items":[{"id":"$ID1","staff_member_id":"$ID2","staff_member_name":"Juma","local_day":"2026-10-25","cutoff_hour":18,
            "amounts":[{"currency":"TZS","amount":"30000"}],"flagged_at":"2026-10-25T15:05:00Z","policy_version":"v4"}],"total":1,"page":1,"page_size":100}""")
        val list = (h.data.remittanceOverdue(LocalDate.of(2026, 10, 25)) as Load.Ok).snapshot.data
        assertTrue(h.server.takeRequest().url.toString().contains("remittance-overdue?day_from=2026-10-25&day_to=2026-10-25"))
        assertEquals("Juma", CashRecords.overdueName(list.single()))
        val o = CashRecords.overdueFields(list.single(), ZoneOffset.UTC).associate { it.label to it.value }
        assertEquals("18:00", o["Cut-off"])
        assertTrue(o["Not remitted"]!!.contains("30,000"))
    }
}
