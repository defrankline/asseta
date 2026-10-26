package com.asseta.supervisor.ui.accountability

import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.accountability.CheckinSummary
import com.asseta.core.domain.accountability.SlotState
import com.asseta.core.domain.inbox.Tone
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.owner.CheckinSlotDto
import com.asseta.core.model.owner.MySiteCheckinsDto
import com.asseta.core.model.owner.SiteCheckinDto
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.sync.data.FieldAccountabilityCache
import com.asseta.supervisor.ui.FieldTexts
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.isForm
import com.asseta.supervisor.ui.title
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

/** Site check-ins in the field app (DEC-031 M3): wording, slots with this phone's check-ins, my check-ins list. */
class SiteCheckinPresentationTest {
    private val zone = ZoneId.of("Africa/Dar_es_Salaam")

    private fun op(clientId: String, capturedAt: String, status: ClientOperationStatus, code: String? = null) = ClientOperationEntity(
        id = "op-$clientId", tenantId = "t", opType = AccountabilityOps.SITE_CHECKIN, entityType = "site_checkin", entityId = clientId,
        payloadJson = """{"client_id":"$clientId","captured_at":"$capturedAt","gps":{"status":"FIX"}}""", dependsOn = null,
        createdAtDevice = Instant.parse(capturedAt).toEpochMilli(), status = status, attemptCount = 0, lastError = null, serverRevision = null,
        errorCode = code,
    )

    private val payloadOf: (ClientOperationEntity) -> Map<String, String?> = { o ->
        Regex("\"captured_at\":\"([^\"]+)\"").find(o.payloadJson)?.groupValues?.get(1).let { mapOf("captured_at" to it) }
    }

    private fun checkin(clientId: String, at: String, gps: String = "FIX", distance: Double? = 42.4, within: Boolean? = true, site: String? = "Kigamboni") =
        SiteCheckinDto(
            id = "id-$clientId", clientId = clientId, staffMemberId = "s", recordedBy = "u", capturedAt = at, receivedAt = at, gpsStatus = gps,
            latitude = null, longitude = null, accuracyM = null, jobSiteId = null, jobSiteName = site, jobId = null, distanceM = distance,
            withinDistance = within, source = "SYNC",
        )

    private val saved = MySiteCheckinsDto(
        required = true, times = listOf("08:00"), windowMinutes = 60, maxDistanceM = 300, timezone = zone.id, dayFrom = "2026-10-20", dayTo = "2026-10-26",
        slots = listOf(CheckinSlotDto("2026-10-26T05:00:00Z", 60, "DUE")),
        checkins = listOf(checkin("a", "2026-10-25T05:10:00Z"), checkin("b", "2026-10-24T05:10:00Z", distance = 512.0, within = false),
            checkin("c", "2026-10-23T05:10:00Z", gps = "TIMEOUT", distance = null, within = null, site = null)),
    )

    @Test
    fun `a check-in saved on this phone covers the due slot until the server has it`() {
        val cache = FieldAccountabilityCache(siteCheckins = saved, siteCheckinsAtMs = 1)
        val now = Instant.parse("2026-10-26T05:30:00Z")
        assertEquals(SlotState.DUE, SiteCheckinPresentation.slots(cache, emptyList(), payloadOf, now).single().state)
        val pending = listOf(op("x", "2026-10-26T05:25:00Z", ClientOperationStatus.PENDING))
        assertEquals(SlotState.SAVED, SiteCheckinPresentation.slots(cache, pending, payloadOf, now).single().state)
        val acked = listOf(op("x", "2026-10-26T05:25:00Z", ClientOperationStatus.ACKED))
        assertEquals(SlotState.MADE, SiteCheckinPresentation.slots(cache, acked, payloadOf, now).single().state)
        // A refused check-in does not count.
        val refused = listOf(op("x", "2026-10-26T05:25:00Z", ClientOperationStatus.CONFLICT, "SITE_CHECKIN_DISABLED"))
        assertEquals(SlotState.DUE, SiteCheckinPresentation.slots(cache, refused, payloadOf, now).single().state)
        assertEquals("Check-in due now, until 09:00", SiteCheckinTexts.summary(CheckinSummary.Due(Instant.parse("2026-10-26T06:00:00Z")), zone))
        assertEquals("Next check-in at 14:00", SiteCheckinTexts.summary(CheckinSummary.Next(Instant.parse("2026-10-26T11:00:00Z")), zone))
        assertEquals("Due now", SiteCheckinTexts.status(SlotState.DUE))
        assertEquals("Saved on this phone", SiteCheckinTexts.status(SlotState.SAVED))
    }

    @Test
    fun `my check-ins list the server's and this phone's, newest first, in plain words`() {
        val ops = listOf(
            op("p", "2026-10-26T05:25:00Z", ClientOperationStatus.PENDING),
            op("r", "2026-10-22T05:25:00Z", ClientOperationStatus.CONFLICT, "CHECKIN_IN_FUTURE"),
            op("a", "2026-10-25T05:10:00Z", ClientOperationStatus.ACKED), // already on the server list: shown once
        )
        val rows = SiteCheckinPresentation.mine(saved, ops, payloadOf)
        assertEquals(listOf("p", "a", "b", "c", "r"), rows.map { it.key })
        assertEquals("26 Oct 2026, 08:25", rows[0].label)
        assertEquals("Waiting to sync", rows[0].caption)
        assertEquals(Tone.INFO, rows[0].tone)
        assertEquals("Kigamboni", rows[1].value)
        assertEquals("42 m from the site", rows[1].caption)
        assertEquals("512 m from the site · Further from the site than allowed", rows[2].caption)
        assertEquals(Tone.WARNING, rows[2].tone)
        assertEquals("No site", rows[3].value)
        assertEquals("Recorded without location", rows[3].caption)
        assertEquals("Not accepted · The phone's clock is ahead, so this check-in was not accepted. Correct the phone's time and check in again.", rows[4].caption)
        assertEquals(Tone.BAD, rows[4].tone)
    }

    @Test
    fun `refusals, outbox title, footer and route`() {
        listOf("SITE_CHECKIN_DISABLED", "CHECKIN_ID_CONFLICT", "STAFF_NOT_LINKED", "CHECKIN_IN_FUTURE", "JOB_SITE_NOT_FOUND").forEach { code ->
            assertTrue(code, FieldAccountabilityTexts.conflict(code)!!.endsWith("."))
        }
        assertEquals("Your company has switched off site check-ins, so this check-in was not accepted.", FieldAccountabilityTexts.conflict("SITE_CHECKIN_DISABLED"))
        assertEquals("Site check-in", FieldTexts.outboxTitle(AccountabilityOps.SITE_CHECKIN, null))
        assertEquals("Site check-ins", Route.SiteCheckins.title("Acme"))
        assertFalse(Route.SiteCheckins.isForm)
        val cache = FieldAccountabilityCache(siteCheckins = saved, siteCheckinsAtMs = Instant.parse("2026-10-26T04:00:00Z").toEpochMilli())
        val footer = SiteCheckinPresentation.footer(cache, online = false, zone = zone)
        assertTrue(footer.contains("Check in within 300 m of the site."))
        assertTrue(footer.endsWith("Schedule from 26 Oct 2026, 07:00. Connect to update it."))
        assertFalse(SiteCheckinPresentation.footer(cache, online = true, zone = zone).contains("Schedule from"))
    }
}
