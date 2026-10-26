package com.asseta.core.domain.accountability

import com.asseta.core.domain.inbox.InboxLink
import com.asseta.core.domain.inbox.InboxLinks
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.CheckinSlotDto
import com.asseta.core.model.owner.MySiteCheckinsDto
import com.asseta.core.model.sync.SyncCapabilities
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/** DEC-031 Phase 5 rules shared by both apps: site check-in slots, gates, deep links, hours format. */
class OversightDomainTest {
    private val job = "11111111-1111-4111-8111-111111111111"

    private fun mine(vararg slots: Pair<String, String>) = MySiteCheckinsDto(
        required = true, times = listOf("08:00", "14:00"), windowMinutes = 60, maxDistanceM = null, timezone = "Africa/Dar_es_Salaam",
        dayFrom = "2026-10-20", dayTo = "2026-10-26",
        slots = slots.map { (at, status) -> CheckinSlotDto(at, 60, status) }, checkins = emptyList(),
    )

    // 08:00 and 14:00 in Dar es Salaam (UTC+3) on 26 Oct, and yesterday's 14:00.
    private val morning = "2026-10-26T05:00:00Z"
    private val afternoon = "2026-10-26T11:00:00Z"
    private val yesterday = "2026-10-25T11:00:00Z"

    @Test
    fun `slot states are recomputed from the clock and the check-ins known`() {
        val saved = mine(yesterday to "MISSED", morning to "UPCOMING", afternoon to "UPCOMING")
        // 08:30 local: the morning window (07:00–09:00) is open, the afternoon one not yet; yesterday is not today.
        val now = Instant.parse("2026-10-26T05:30:00Z")
        val slots = SiteCheckinRules.today(saved, emptyList(), emptyList(), now)
        assertEquals(listOf(SlotState.DUE, SlotState.UPCOMING), slots.map { it.state })
        assertEquals("07:00", SiteCheckinRules.time(slots[0].from, ZoneId.of("Africa/Dar_es_Salaam")))
        assertEquals(CheckinSummary.Due(Instant.parse("2026-10-26T06:00:00Z")), SiteCheckinRules.summary(slots))

        // Checked in on this phone (not synced): SAVED; once the server has it: MADE.
        val at = Instant.parse("2026-10-26T05:20:00Z")
        assertEquals(SlotState.SAVED, SiteCheckinRules.today(saved, emptyList(), listOf(at), now)[0].state)
        assertEquals(SlotState.MADE, SiteCheckinRules.today(saved, listOf(at), emptyList(), now)[0].state)

        // 10:00 local: the morning window has ended without a check-in; the next one is at 14:00.
        val later = SiteCheckinRules.today(saved, emptyList(), emptyList(), Instant.parse("2026-10-26T07:00:00Z"))
        assertEquals(listOf(SlotState.MISSED, SlotState.UPCOMING), later.map { it.state })
        assertEquals(CheckinSummary.Next(Instant.parse(afternoon)), SiteCheckinRules.summary(later))

        // The server's MADE wins; nothing left later in the day.
        val done = SiteCheckinRules.today(mine(morning to "MADE"), emptyList(), emptyList(), Instant.parse("2026-10-26T15:00:00Z"))
        assertEquals(SlotState.MADE, done.single().state)
        assertEquals(CheckinSummary.NoneLeft, SiteCheckinRules.summary(done))
        assertTrue(SiteCheckinRules.today(null, emptyList(), emptyList(), Instant.now()).isEmpty())
    }

    @Test
    fun `site check-in needs the capability, the permission and the switch on`() {
        val perms = setOf(FieldAccess.SITE_CHECKIN_RECORD)
        assertTrue(FieldAccess(setOf(SyncCapabilities.OP_SITE_CHECKIN), perms).siteCheckin)
        assertFalse(FieldAccess(emptySet(), perms).siteCheckin)
        assertFalse(FieldAccess(null, perms).siteCheckin)
        assertFalse(FieldAccess(setOf(SyncCapabilities.OP_SITE_CHECKIN), emptySet()).siteCheckin)
        assertFalse(FieldAccess(setOf(SyncCapabilities.OP_SITE_CHECKIN), perms, disabled = setOf(TenantAccess.SITE_CHECKIN)).siteCheckin)
    }

    @Test
    fun `unbilled work notification opens the job, oversight paths open their screens`() {
        assertEquals(OwnerDestination.Job(job), DeepLinkRouter.fromTarget("job", job, "/tenant/jobs/$job", kind = "JOB", recordId = job))
        assertEquals(OwnerDestination.Job(job), DeepLinkRouter.fromPush(mapOf("kind" to "JOB", "record_id" to job))!!.destination)
        assertEquals(OwnerDestination.Scorecard, DeepLinkRouter.fromPath("/tenant/scorecard"))
        assertEquals(OwnerDestination.ScorecardPerson(job), DeepLinkRouter.fromPath("/tenant/scorecard/$job"))
        assertEquals(OwnerDestination.UnbilledWork, DeepLinkRouter.fromPath("/tenant/unbilled-work"))
        assertEquals(OwnerDestination.IdleMachines, DeepLinkRouter.fromPath("/tenant/idle-machines"))
        assertEquals(InboxLink.Job(job), InboxLinks.from(null, null, "JOB", job))
    }

    @Test
    fun `hours use the phone's number format without forced decimals`() {
        assertEquals("12", OwnerFormat.hoursNumber("12.0000", Locale.US))
        assertEquals("1,234.5", OwnerFormat.hoursNumber("1234.50", Locale.US))
        assertEquals("0.12", OwnerFormat.hoursNumber("0.125", Locale.US)) // half-even, as iOS
        assertEquals("1.234,5", OwnerFormat.hoursNumber("1234.5", Locale.GERMANY))
        assertEquals("n/a", OwnerFormat.hoursNumber("n/a", Locale.US))
        assertEquals("0", OwnerFormat.hoursNumber(null, Locale.US))
    }
}
