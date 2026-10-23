package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.sync.data.AttentionItem
import org.junit.Assert.assertEquals
import org.junit.Test
import java.math.BigDecimal

/** Wording of the supervisor tabs, identical on iOS (`InboxTextsTests`). */
class InboxTextsTest {
    @Test
    fun `jobs fall into the three segments`() {
        assertEquals(JobSegment.IN_PROGRESS, InboxTexts.segment(JobStatus.IN_PROGRESS))
        assertEquals(JobSegment.READY, InboxTexts.segment(JobStatus.APPROVED))
        assertEquals(JobSegment.CLOSED, InboxTexts.segment(JobStatus.COMPLETED))
        assertEquals(JobSegment.CLOSED, InboxTexts.segment(JobStatus.CANCELLED))
        assertEquals(listOf("In progress", "Ready to start", "Recently closed", "My machines"), JobSegment.entries.map { it.label })
        assertEquals("No recently closed jobs", InboxTexts.jobsEmpty(JobSegment.CLOSED).first)
    }

    @Test
    fun `reading, gps and money wording`() {
        assertEquals("Opening reading", InboxTexts.readingKind("OPENING"))
        assertEquals("Closing reading", InboxTexts.readingKind("CLOSING"))
        assertEquals("-6.80000, 39.20000 (±12 m)", InboxTexts.gps("FIX", -6.8, 39.2, 12.4))
        assertEquals("No GPS fix within 20 seconds", InboxTexts.gps("TIMEOUT", null, null, null))
        assertEquals("92 %", InboxTexts.confidence(0.92))
        assertEquals("25000 TZS", InboxTexts.money("25000.0000", "TZS"))
        assertEquals("12.5 L", InboxTexts.litres("12.500"))
        assertEquals("8.5 h", InboxTexts.hours(BigDecimal("8.50")))
        assertEquals("My cash", InboxTexts.paidFrom("CASH_CUSTODY"))
        assertEquals("Issue", InboxTexts.fuelType("ISSUE"))
        assertEquals("Waiting for the office to review", InboxTexts.reviewOutcome("PENDING_REVIEW", 1))
        assertEquals("No findings", InboxTexts.reviewOutcome("NONE", 0))
    }

    @Test
    fun `money lists are grouped by who has the record`() {
        val statuses = listOf(InboxStatus.REJECTED, InboxStatus.WAITING, InboxStatus.APPROVED, InboxStatus.PENDING_APPROVAL, InboxStatus.SYNCED)
        val groups = InboxTexts.moneyGroups(statuses) { it }
        assertEquals(listOf("On this phone", "Pending approval", "Approved", "Rejected"), groups.map { it.first })
        assertEquals(listOf(InboxStatus.WAITING, InboxStatus.SYNCED), groups.first().second)
    }

    @Test
    fun `inbox badge and attention rows`() {
        assertEquals(5, InboxTexts.inboxBadge(unread = 3, attention = 2))
        assertEquals("Cash handover", InboxTexts.attentionTitle(AttentionItem.Kind.HANDOVER))
        assertEquals("Rejected by the office", InboxTexts.attentionDetail(InboxStatus.REJECTED))
    }
}
