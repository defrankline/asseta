package com.asseta.core.domain.inbox

import com.asseta.core.model.ClientOperationStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal

class InboxRulesTest {
    @Test
    fun `local outbox states map to waiting, not synced and synced`() {
        assertEquals(InboxStatus.WAITING, InboxStatusRules.local(ClientOperationStatus.PENDING))
        assertEquals(InboxStatus.WAITING, InboxStatusRules.local(ClientOperationStatus.SENT))
        assertEquals(InboxStatus.WAITING, InboxStatusRules.local(ClientOperationStatus.QUARANTINED))
        assertEquals(InboxStatus.NOT_SYNCED, InboxStatusRules.local(ClientOperationStatus.FAILED))
        assertEquals(InboxStatus.NOT_SYNCED, InboxStatusRules.local(ClientOperationStatus.CONFLICT))
        assertEquals(InboxStatus.SYNCED, InboxStatusRules.local(ClientOperationStatus.ACKED))
        assertEquals("Waiting to sync", InboxStatus.WAITING.label)
    }

    @Test
    fun `reading status combines state, review and findings`() {
        assertEquals(InboxStatus.ACCEPTED, InboxStatusRules.reading("ACCEPTED", "NONE", emptyList()))
        assertEquals(InboxStatus.PROVISIONAL, InboxStatusRules.reading("PROVISIONAL", "NONE", emptyList()))
        assertEquals(InboxStatus.FLAGGED, InboxStatusRules.reading("PROVISIONAL", "PENDING_REVIEW", listOf("OPEN")))
        assertEquals(InboxStatus.FLAGGED, InboxStatusRules.reading("ACCEPTED", "NONE", listOf("EXPLAINED", "OPEN")))
        assertEquals(InboxStatus.REVIEWED, InboxStatusRules.reading("PROVISIONAL", "REVIEWED", listOf("CONFIRMED")))
        assertEquals(InboxStatus.REJECTED, InboxStatusRules.reading("REJECTED", "PENDING_REVIEW", listOf("OPEN")))
        assertEquals(InboxStatus.SUPERSEDED, InboxStatusRules.reading("SUPERSEDED", "NONE", emptyList()))
        assertTrue(InboxStatus.FLAGGED.needsAttention)
        assertFalse(InboxStatus.REVIEWED.needsAttention)
    }

    @Test
    fun `finance and reset statuses`() {
        assertEquals(InboxStatus.PENDING_APPROVAL, InboxStatusRules.expense("PENDING_APPROVAL"))
        assertEquals(InboxStatus.APPROVED, InboxStatusRules.expense("APPROVED"))
        assertEquals(InboxStatus.REJECTED, InboxStatusRules.expense("REJECTED"))
        assertEquals(InboxStatus.CLAIMED, InboxStatusRules.settlement("CLAIMED"))
        assertEquals(InboxStatus.VERIFIED, InboxStatusRules.settlement("VERIFIED"))
        assertEquals(InboxStatus.REJECTED, InboxStatusRules.settlement("REJECTED"))
        assertEquals(InboxStatus.PENDING, InboxStatusRules.reset("PENDING"))
        assertEquals(InboxStatus.APPROVED, InboxStatusRules.reset("APPROVED"))
        assertEquals("Awaiting verification", InboxStatus.CLAIMED.label)
    }

    @Test
    fun `server copy wins over the local state`() {
        assertEquals(InboxStatus.APPROVED, InboxStatusRules.combined(ClientOperationStatus.ACKED, InboxStatus.APPROVED))
        assertEquals(InboxStatus.WAITING, InboxStatusRules.combined(ClientOperationStatus.PENDING, null))
        assertEquals(InboxStatus.SYNCED, InboxStatusRules.combined(ClientOperationStatus.ACKED, null))
    }

    private data class S(val id: String, val clientId: String?)
    private data class L(val entityId: String, val serverId: String?)

    @Test
    fun `merges local and server records by client id or acknowledged server id`() {
        val server = listOf(S("s1", "c1"), S("s2", null), S("s3", "c3"))
        val local = listOf(L("c1", null), L("x2", "s2"), L("c9", null), L("c1", null))
        val merged = InboxMerge.merge(server, local, { setOfNotNull(it.id, it.clientId) }, { LocalKey(it.entityId, it.serverId) })
        assertEquals(5, merged.size)
        assertEquals(L("c1", null), merged[0].local)
        assertEquals(L("x2", "s2"), merged[1].local)
        assertNull(merged[2].local)
        assertEquals(listOf(L("c9", null), L("c1", null)), merged.drop(3).map { it.local })
        assertTrue(merged.drop(3).all { it.server == null })
    }

    @Test
    fun `work totals per type and meter hours`() {
        val h = 3_600_000L
        val totals = JobFigures.minutesByType(
            listOf(WorkSpan("WORK", 0, 2 * h), WorkSpan("STANDBY", 2 * h, 3 * h), WorkSpan("WORK", 3 * h, null), WorkSpan("NOTE", 0, null)),
            nowMs = 3 * h + 30 * 60_000,
        )
        assertEquals(listOf("WORK" to 150L, "STANDBY" to 60L), totals)
        assertEquals("2 h 30 min", JobFigures.duration(150))
        assertEquals("45 min", JobFigures.duration(45))
        assertEquals(0, BigDecimal("8.5").compareTo(JobFigures.meterHours("100.0", "108.5")))
        assertNull(JobFigures.meterHours("100", null))
        assertNull(JobFigures.meterHours("100", "90"))
    }

    @Test
    fun `notification targets open the related item`() {
        assertEquals(InboxLink.Job("j"), InboxLinks.from("job", "j"))
        assertEquals(InboxLink.Expense("e"), InboxLinks.from("expense", "e"))
        assertEquals(InboxLink.Money, InboxLinks.from("staff_member", "s"))
        assertEquals(InboxLink.None, InboxLinks.from("screen", null))
    }

    @Test
    fun `reset request checks`() {
        assertTrue(ResetRules.validate("9999.9", "0", "Meter replaced by workshop", true).isEmpty())
        val issues = ResetRules.validate("x", "", "short", false)
        assertEquals(4, issues.size)
        assertEquals("12.5", ResetRules.parse("12,5"))
    }

    @Test
    fun `finding wording`() {
        assertEquals("Reading lower than before", FindingTexts.type("METER_DECREASE"))
        assertEquals("Brand new", FindingTexts.type("BRAND_NEW"))
        assertEquals("Waiting for review", FindingTexts.review("OPEN"))
    }
}
