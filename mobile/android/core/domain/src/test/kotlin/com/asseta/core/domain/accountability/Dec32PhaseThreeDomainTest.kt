package com.asseta.core.domain.accountability

import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal

/** DEC-032 Phase 3 rules shared with iOS: collection links, partial remittance reasons, transfer evidence, switches, links. */
class Dec32PhaseThreeDomainTest {
    private val caps = setOf(SyncCapabilities.CASH_DETAILS_V2, SyncCapabilities.REMITTANCE_DETAILS_V1, SyncCapabilities.OP_HOURS_TRANSFER_REQUEST)
    private val perms = setOf("tenant.collection.record", "tenant.hours.transfer", "tenant.hours.read")
    private val cashValues = buildJsonObject {
        listOf("recorders_may_record_for_others", "transfer_ack_required", "recorder_receiver_counts_as_ack", "float_ack_required", "retention_allowed").forEach { put(it, false) }
        put("remit_full_balance", true)
        put("remittance_account_required", true)
        put("collection_link_required", true)
    }
    private val cash = CashCustodyPolicy.fromValues(cashValues)!!
    private val hours = CustomerHoursPolicy.fromValues(buildJsonObject {
        put("enabled", true); put("walk_in_allowed", true); put("transfer_requires_approval", true); put("reason_code_required", false)
        put("transfer_evidence_required", true)
    })!!

    @Test
    fun `policy flags are read and off when missing`() {
        assertTrue(cash.collectionLinkRequired)
        assertTrue(cash.remitFullBalance)
        assertTrue(hours.transferEvidenceRequired)
        val old = CashCustodyPolicy.fromValues(buildJsonObject {
            listOf("recorders_may_record_for_others", "transfer_ack_required", "recorder_receiver_counts_as_ack", "float_ack_required", "retention_allowed", "remit_full_balance").forEach { put(it, JsonPrimitive(false)) }
        })!!
        assertFalse(old.collectionLinkRequired)
    }

    @Test
    fun `the new form fields need CASH_DETAILS_V2 and the policy`() {
        val a = FieldAccess(caps, perms, cash, hours)
        assertTrue(a.collectionLink)
        assertTrue(a.collectionLinkRequired)
        assertTrue(a.partialReason)
        assertTrue(a.transferEvidence)
        assertTrue(a.transferEvidenceRequired)
        val old = FieldAccess(caps - SyncCapabilities.CASH_DETAILS_V2, perms, cash, hours)
        assertFalse(old.collectionLink)
        assertFalse(old.partialReason)
        assertFalse(old.transferEvidence)
        assertFalse(FieldAccess(caps, perms, cash, hours, disabled = setOf(TenantAccess.CASH_CUSTODY)).partialReason)
    }

    @Test
    fun `deposit accounts off hides the picker and drops the account requirement`() {
        val on = FieldAccess(caps, perms, cash, hours)
        assertTrue(on.depositAccounts)
        assertTrue(on.remittanceRequirements.accountRequired)
        val off = FieldAccess(caps, perms, cash, hours, disabled = setOf(TenantAccess.DEPOSIT_ACCOUNTS))
        assertFalse(off.depositAccounts)
        assertFalse(off.remittanceRequirements.accountRequired)
    }

    @Test
    fun `partial reason mode compares the amount with the estimate`() {
        val r = RemittanceRules
        assertEquals(PartialReasonMode.NONE, r.partialReasonMode(false, false, BigDecimal(1000), BigDecimal(500)))
        assertEquals(PartialReasonMode.REQUIRED, r.partialReasonMode(true, false, BigDecimal(1000), BigDecimal(500)))
        assertEquals(PartialReasonMode.NONE, r.partialReasonMode(true, false, BigDecimal(1000), BigDecimal(1000)))
        assertEquals(PartialReasonMode.NONE, r.partialReasonMode(true, false, null, BigDecimal(500)))
        assertEquals(PartialReasonMode.OPTIONAL, r.partialReasonMode(true, true, null, BigDecimal(500)))
        assertTrue(r.partialReasonValid(" abc "))
        assertFalse(r.partialReasonValid(" ab "))
    }

    @Test
    fun `collection links are the customers open purchases and this phones unsynced ones`() {
        val purchases = listOf(
            LinkablePurchase("p1", "HP-1", "c1", "ACTIVE", "5.50"),
            LinkablePurchase("p2", "HP-2", "c1", "CANCELLED", "1"),
            LinkablePurchase("p3", "HP-3", "c2", "ACTIVE", "1"),
        )
        val unsynced = listOf(UnsyncedPurchase("client-1", "c1", "2.5", "op-1"), UnsyncedPurchase("client-2", "c2", "1", "op-2"))
        val options = CollectionLinks.options("c1", purchases, unsynced)
        assertEquals(listOf("p1", "client-1"), options.map { it.id })
        assertEquals("HP-1", options[0].title)
        assertEquals("5.5 h left", options[0].subtitle)
        assertEquals("Not synced yet · 2.5 h", options[1].title)
        assertEquals("op-1", options[1].operationId)
        assertTrue(CollectionLinks.options(null, purchases, unsynced).isEmpty())
        // One row per client id, and none once the purchase has synced.
        val twice = unsynced + UnsyncedPurchase("client-1", "c1", "2.5", "op-3")
        assertEquals(listOf("p1", "client-1"), CollectionLinks.options("c1", purchases, twice).map { it.id })
        val accepted = purchases + LinkablePurchase("p4", "HP-4", "c1", "ACTIVE", "2.5", clientId = "client-1")
        assertEquals(listOf("p1", "p4"), CollectionLinks.options("c1", accepted, twice).map { it.id })
    }

    @Test
    fun `a supervisor opens the remittance a decision is about`() {
        val id = "11111111-1111-4111-8111-111111111111"
        assertEquals(com.asseta.core.domain.inbox.InboxLink.Handover(id), com.asseta.core.domain.inbox.InboxLinks.from("cash_handover", id, "CASH_REMITTANCE", id))
        assertEquals(com.asseta.core.domain.inbox.InboxLink.Handover(id), com.asseta.core.domain.inbox.InboxLinks.from("cash_handover", id))
    }

    @Test
    fun `a variance or remittance notification opens its screen`() {
        val id = "11111111-1111-4111-8111-111111111111"
        assertEquals(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, id), DeepLinkRouter.fromTarget("cash_variance", id, null, kind = RecordKinds.CASH_VARIANCE, recordId = id, type = "VARIANCE_ASSIGNED"))
        assertEquals(OwnerDestination.Handover(id), DeepLinkRouter.fromTarget("cash_handover", id, null, kind = RecordKinds.CASH_REMITTANCE, recordId = id))
        assertEquals(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, id), DeepLinkRouter.fromPath("/tenant/finance/cash/variances/$id"))
        assertEquals(OwnerDestination.Handover(id), DeepLinkRouter.fromPath("/tenant/finance/cash/remittances/$id"))
    }
}
