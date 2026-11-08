package com.asseta.owner

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AdjustmentRequestDto
import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.model.owner.CashVarianceDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.model.owner.VarianceEventDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.OwnerTab
import com.asseta.owner.ui.accountability.AdjustmentPresentation
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionMapper
import com.asseta.owner.ui.cash.HandoverText
import com.asseta.owner.ui.home.OverviewPresentation
import com.asseta.owner.ui.moreEntries
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** DEC-032 Phase 3 on the Owner app: switches, partial remittance reasons, variance closures, numbers. */
class PhaseThreeOwnerTest {
    private val json = NetworkFactory.json
    private val all = setOf("tenant.fleet.read", "tenant.job.read", "tenant.finance.read", "tenant.case.read", "tenant.approval.read")
    private val on = OwnerFeatures(all)

    private val handover = json.decodeFromString(
        CashHandoverDto.serializer(),
        """{"id":"11111111-1111-4111-8111-111111111111","staff_member_id":"22222222-2222-4222-8222-222222222222","staff_member_name":"Juma",
           "amount":"50000","currency":"TZS","handed_at":"2026-11-09T08:00:00Z","status":"CLAIMED","source":"FIELD","recorded_at":"2026-11-09T08:01:00Z",
           "remittance_number":"RMT-12","evidence_status":"SUPPORTED","outstanding_difference":"300","partial_shortfall":"20000",
           "partial_approval":{"id":"a1","status":"PENDING","reason":"Kept for fuel","created_by":"u9","created_by_name":"Asha","created_at":"2026-11-09T08:01:00Z"}}""",
    )

    private fun variance(status: String, unit: String? = null, outcome: String? = null) = json.decodeFromString(
        CashVarianceDto.serializer(),
        """{"id":"v1","source_type":"CUSTOMER_HOUR","source_id":"s1","staff_member_id":null,"currency":"TZS","declared_amount":"12","received_amount":"10","amount":"2",
           "status":"$status","opened_at":"2026-11-09T07:00:00Z","proposed_by":"u9","proposed_by_name":"Asha","proposed_at":"2026-11-09T07:30:00Z",
           "proposal_note":"Corrected the entry"${unit?.let { ""","unit":"$it"""" } ?: ""}${outcome?.let { ""","proposed_outcome":"$it"""" } ?: ""},
           "assignee_user_id":"u2","assignee_user_name":"Baraka","explanation":"Meter typed twice","evidence_attachment_ids":["att1"],
           "check_code":"CONSUMPTION_MISMATCH","customer_name":"Acacia","machine_code":"EX-1"}""",
    )

    private val overview = json.decodeFromString(
        TenantOverviewDto.serializer(),
        """{"tenant_id":"11111111-1111-4111-8111-111111111111","as_of":"2026-11-09T08:00:00Z","timezone":"UTC","fleet":{"machines":5,"connectivity":{"live":2,"recent":1,"stale":1,"offline":1,"never":0,"no_tracker":0},
          "engine_on_verified":2,"open_alerts":{"critical":1,"warning":2,"info":0},"reported_work_state":{"WORKING":3},"latest_source_at":"2026-11-09T08:05:00Z"}}""",
    )

    @Test
    fun `switched-off tracking hides alerts and connectivity figures`() {
        val off = OwnerFeatures(all, setOf(TenantAccess.TRACKING))
        assertTrue(on.alerts)
        assertFalse(off.alerts)
        assertTrue(OwnerTab.ALERTS in OwnerNavigation.tabs(on))
        assertFalse(OwnerTab.ALERTS in OwnerNavigation.tabs(off))
        assertEquals(OwnerDestination.Home, off.route(OwnerDestination.Alerts("a1")))
        val rows = OverviewPresentation.sections(overview, cached = false, nowMs = 0, tracking = false).first().groups.single().rows.map { it.label }
        assertEquals(listOf("Machines", "Reported working"), rows)
        assertTrue(OverviewPresentation.sections(overview, cached = false, nowMs = 0).first().groups.single().rows.any { it.label == "Open alerts" })
    }

    @Test
    fun `Approvals opens for any role with a decision to see`() {
        assertTrue(OwnerFeatures(setOf("tenant.finance.read", "tenant.finance.writeoff")).approvalsScreen)
        assertTrue(OwnerFeatures(setOf("tenant.revenue.read"), emptySet()).approvalsScreen)
        assertFalse(OwnerFeatures(setOf("tenant.expense.read")).approvalsScreen)
    }

    @Test
    fun `switched-off investigations hide cases`() {
        val off = OwnerFeatures(all, setOf(TenantAccess.INVESTIGATIONS))
        assertTrue(moreEntries(on).any { it.second == OwnerDestination.Cases })
        assertFalse(off.cases)
        assertFalse(moreEntries(off).any { it.second == OwnerDestination.Cases })
        assertEquals(OwnerDestination.Home, off.route(OwnerDestination.Case("c1")))
        assertEquals(OwnerDestination.Case("c1"), on.route(OwnerDestination.Case("c1")))
    }

    @Test
    fun `partial remittance decision`() {
        val item = DecisionMapper.partialRemittance(handover)
        assertTrue(item.pending)
        assertEquals("TZS 20,000.00 not remitted · Juma", item.headline)
        assertEquals("Kept for fuel", item.reason)
        assertEquals("u9", item.proposedBy)
        val fields = item.fields.associate { it.label to it.value }
        assertEquals("RMT-12", fields["Number"])
        assertEquals("Juma", fields["Cash held by"])
        assertEquals("TZS 20,000.00", fields["Not remitted"])
        assertFalse(DecisionMapper.partialRemittance(handover.copy(partialApproval = null)).pending)
        assertEquals("tenant.finance.retention_approve", OwnerAction.DECIDE_PARTIAL_REMITTANCE.permission)
        assertTrue(DecisionKind.PARTIAL_REMITTANCE.visibleTo(on))
        assertFalse(DecisionKind.PARTIAL_REMITTANCE.visibleTo(OwnerFeatures(all, setOf(TenantAccess.CASH_CUSTODY))))
    }

    @Test
    fun `a proposed closure is decided as a closure, and shows the investigation`() {
        val v = variance("CLOSURE_PROPOSED", "HOURS", "EXPLAINED")
        val events = listOf(VarianceEventDto("e1", "ASSIGNED", "u1", "Mgr", null, "2026-11-09T07:10:00Z"), VarianceEventDto("e2", "CLOSURE_PROPOSED", "u9", "Asha", "Corrected the entry", "2026-11-09T07:30:00Z"))
        val item = DecisionMapper.variance(v, events, ZoneOffset.UTC)
        assertTrue(item.pending)
        assertEquals(DecisionKinds.VARIANCE_CLOSURE, item.decideAs)
        assertEquals("Close 2 h (Explained)", item.headline)
        val f = item.fields.associate { it.label to it.value }
        assertEquals("Baraka", f["Assigned to"])
        assertEquals("Meter typed twice", f["Explanation"])
        assertEquals("Usage does not match records", f["What was found"])
        assertEquals("EX-1", f["Machine"])
        assertEquals("12 h", f["Declared"])
        assertEquals("Explained", f["Proposed outcome"])
        assertEquals(listOf("att1"), item.photoAttachmentIds)
        assertEquals(2, item.history.size)
        assertTrue(item.history[0].label.endsWith("· Assigned · Mgr"))
        assertEquals("Corrected the entry", item.history[1].value)
        assertTrue(item.isOwn("u9"))
        assertEquals("Variance closure", DecisionMapper.varianceTitle("CLOSURE_PROPOSED"))
        assertEquals("Cash write-off", DecisionMapper.varianceTitle("WRITE_OFF_PROPOSED"))
        assertEquals("Variance", DecisionMapper.varianceTitle("RESOLVED"))
        assertEquals("Variance", com.asseta.owner.ui.OwnerNavigation.title(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, "v1")))
        // Opened from "Variance closures": still a closure once decided.
        assertEquals("Close 2 h (Explained)", DecisionMapper.variance(variance("RESOLVED", "HOURS", "EXPLAINED"), emptyList(), ZoneOffset.UTC, asClosure = true).headline)
        // An hours write-off reads in hours throughout.
        val hoursOff = DecisionMapper.variance(variance("WRITE_OFF_PROPOSED", "HOURS"), emptyList(), ZoneOffset.UTC)
        assertEquals("Write off 2 h", hoursOff.headline)
        assertEquals("2 h", hoursOff.fields.associate { it.label to it.value }["Difference"])
        assertTrue(DecisionMapper.variance(variance("WRITE_OFF_PROPOSED", "HOURS").copy(amount = "-2", kind = "SURPLUS"), emptyList(), ZoneOffset.UTC).headline.endsWith(": 2 h"))
        // A write-off stays decided as a write-off.
        val w = DecisionMapper.variance(variance("WRITE_OFF_PROPOSED"), emptyList(), ZoneOffset.UTC)
        assertNull(w.decideAs)
        assertTrue(w.pending)
        assertFalse(DecisionMapper.variance(variance("RESOLVED"), emptyList(), ZoneOffset.UTC).pending)
        assertEquals(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, "v1"), RecordKinds.destination(RecordKinds.CASH_VARIANCE, "v1"))
    }

    @Test
    fun `the remittance card shows its number, evidence and open difference`() {
        val rows = HandoverText.details(handover).toMap()
        assertEquals("RMT-12", rows["Remittance number"])
        assertEquals("Supported by evidence", rows["Evidence"])
        assertEquals("TZS 300.00", rows["Difference still open"])
        assertNull(HandoverText.details(json.decodeFromString(CashHandoverDto.serializer(), """{"id":"11111111-1111-4111-8111-111111111111","staff_member_id":"22222222-2222-4222-8222-222222222222","amount":"1","currency":"TZS","handed_at":"2026-11-09T08:00:00Z","status":"CLAIMED","source":"FIELD","recorded_at":"2026-11-09T08:01:00Z","outstanding_difference":"0"}""")).toMap()["Difference still open"])
    }

    @Test
    fun `a zero-amount purchase reads in plain words`() {
        val r = json.decodeFromString(
            AdjustmentRequestDto.serializer(),
            """{"id":"r1","request_type":"ZERO_AMOUNT_ACTIVATION","status":"PROPOSED","request_number":"ARQ-9","customer_name":"Acacia","hours":"4","proposed_at":"2026-11-09T07:00:00Z","reason":"Promotional hours"}""",
        )
        val item = AdjustmentPresentation.item(r)
        assertEquals("Purchase with nothing to pay · 4 h", item.headline)
        assertEquals("ARQ-9", item.fields.first { it.label == "Number" }.value)
        assertEquals("A request for this purchase already waits for a decision.", com.asseta.owner.ui.accountability.AdjustmentTexts.error("ZERO_AMOUNT_PENDING", "x"))
    }
}
