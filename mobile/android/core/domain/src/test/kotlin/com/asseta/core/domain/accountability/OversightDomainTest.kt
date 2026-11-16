package com.asseta.core.domain.accountability

import com.asseta.core.domain.inbox.InboxLink
import com.asseta.core.domain.inbox.InboxLinks
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.util.Locale

/** DEC-031 Phase 5 rules shared by both apps: deep links, hours format. */
class OversightDomainTest {
    private val id = "11111111-1111-4111-8111-111111111111"

    @Test
    fun `oversight paths open their screens and old job links no longer resolve to a job`() {
        assertEquals(OwnerDestination.Scorecard, DeepLinkRouter.fromPath("/tenant/scorecard"))
        assertEquals(OwnerDestination.ScorecardPerson(id), DeepLinkRouter.fromPath("/tenant/scorecard/$id"))
        assertEquals(OwnerDestination.IdleMachines, DeepLinkRouter.fromPath("/tenant/idle-machines"))
        // ADR-008: jobs, unbilled work and site check-ins are gone; their links fall back to the notification itself.
        assertNull(DeepLinkRouter.fromPath("/tenant/jobs/$id"))
        assertNull(DeepLinkRouter.fromPath("/tenant/unbilled-work"))
        assertNull(DeepLinkRouter.fromPush(mapOf("kind" to "JOB", "record_id" to id)))
        assertEquals(OwnerDestination.Notifications(null), DeepLinkRouter.fromTarget("job", id, "/tenant/jobs/$id", kind = "JOB", recordId = id))
        assertEquals(InboxLink.None, InboxLinks.from("job", id, "JOB", id))
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
