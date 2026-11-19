package com.asseta.core.domain.reports

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

/** Time since the last visit and where (same cases as iOS `VisitsTests` and web `visits.test.ts`). */
class VisitsTest {
    private val dar = ZoneId.of("Africa/Dar_es_Salaam")

    @Test
    fun `durations in whole units, truncated`() {
        assertEquals("First visit", Visits.duration(null))
        assertEquals("0 min", Visits.duration(0))
        assertEquals("0 min", Visits.duration(59))
        assertEquals("45 min", Visits.duration(45 * 60 + 59))
        assertEquals("59 min", Visits.duration(3599))
        assertEquals("1 h", Visits.duration(3600))
        assertEquals("5 h", Visits.duration(5 * 3600 + 59))
        assertEquals("5 h 20 min", Visits.duration(5 * 3600 + 20 * 60))
        assertEquals("23 h 59 min", Visits.duration(24 * 3600 - 1))
        assertEquals("1 day", Visits.duration(24 * 3600))
        assertEquals("1 day 3 h", Visits.duration(27 * 3600 + 59 * 60))
        assertEquals("2 days", Visits.duration(48 * 3600 + 30 * 60))
        assertEquals("10 days 1 h", Visits.duration(241 * 3600))
        assertEquals("0 min", Visits.duration(-5))
    }

    @Test
    fun `since last visit lines`() {
        assertEquals("Since last visit: 1 day 3 h", Visits.sinceLastVisit(27 * 3600))
        assertEquals("Since last visit: First visit", Visits.sinceLastVisit(null))
        val now = Instant.parse("2026-11-18T15:26:00Z").toEpochMilli()
        assertEquals(
            "Time since last visit: 1 day 3 h (last visit 17 Nov, 15:26)",
            Visits.timeSinceLastVisit("2026-11-17T12:26:00Z", now, dar),
        )
        assertEquals("Time since last visit: First visit", Visits.timeSinceLastVisit(null, now, dar))
        assertEquals(3600L, Visits.secondsBetween("2026-11-18T14:26:00Z", now))
        assertEquals(3600L, Visits.secondsBetween("2026-11-18T17:26:00+03:00", now))
        assertNull(Visits.secondsBetween(null, now))
    }

    @Test
    fun `visit date and time in local 24 h`() {
        assertEquals("17 Nov, 15:26", Visits.dateTime("2026-11-17T12:26:00Z", dar))
        assertEquals("1 Dec, 08:05", Visits.dateTime("2026-12-01T05:05:30.123456Z", dar))
    }

    @Test
    fun `where lines leave out what is missing`() {
        assertEquals(
            "Where: Mbezi Beach, Kinondoni, Dar es Salaam (at Mbezi yard) · -6.7924, 39.2083 (±5 m)",
            Visits.where(VisitPlace("Mbezi Beach, Kinondoni, Dar es Salaam", "Mbezi yard", -6.79241, 39.20834, 4.6)),
        )
        assertEquals("Where: at Mbezi yard · -6.7924, 39.2083 (±5 m)", Visits.where(VisitPlace(null, "Mbezi yard", -6.7924, 39.2083, 5.0)))
        assertEquals("Where: Mbezi Beach · -6.7924, 39.2083 (±5 m)", Visits.where(VisitPlace("Mbezi Beach", null, -6.7924, 39.2083, 5.0)))
        assertEquals("Where: -6.7924, 39.2083 (±5 m)", Visits.where(VisitPlace(null, null, -6.7924, 39.2083, 5.0)))
        assertEquals("Where: -6.7924, 39.2083", Visits.where(VisitPlace(" ", null, -6.7924, 39.2083, null)))
        assertEquals("Where: -6.8000, 39.2800 (±8 m)", Visits.where(VisitPlace(null, null, -6.8, 39.28, 8.0)))
        assertNull(Visits.where(VisitPlace("Mbezi Beach", "Mbezi yard", null, null, 5.0)))
        assertNull(Visits.where(VisitPlace("Mbezi Beach", null, -6.8, null, 5.0)))
    }

    @Test
    fun `the last visit line and the map link`() {
        assertEquals(
            "Last visit: 17 Nov, 15:26 · Where: Mbezi Beach · -6.8000, 39.2800 (±8 m)",
            Visits.lastVisit("2026-11-17T12:26:00Z", VisitPlace("Mbezi Beach", null, -6.8, 39.28, 8.0), dar),
        )
        assertEquals("Last visit: 17 Nov, 15:26", Visits.lastVisit("2026-11-17T12:26:00Z", VisitPlace(null, null, null, null, null), dar))
        assertNull(Visits.lastVisit(null, VisitPlace(null, null, -6.8, 39.28, 8.0), dar))
        assertEquals("geo:-6.7924,39.2083?q=-6.7924,39.2083", Visits.geoUri(-6.7924, 39.2083))
    }

    @Test
    fun `place labels from the geocoder parts, no street, no repeats`() {
        assertEquals("Mbezi Beach, Kinondoni, Dar es Salaam", Visits.placeLabel("Mbezi Beach", "Kinondoni", "Dar es Salaam"))
        assertEquals("Kinondoni, Dar es Salaam", Visits.placeLabel(null, " Kinondoni ", "Dar es Salaam"))
        assertEquals("Dar es Salaam", Visits.placeLabel("Dar es Salaam", "dar es salaam", "Dar es Salaam"))
        assertNull(Visits.placeLabel(null, " ", null))
        assertEquals(200, Visits.placeLabel("x".repeat(150), "y".repeat(150), null)!!.length)
    }

    @Test
    fun `the visit gap is flagged over the company's hours only`() {
        assertFalse(Visits.gapFlagged(24 * 3600, 24))
        assertTrue(Visits.gapFlagged(24 * 3600 + 1, 24))
        assertFalse(Visits.gapFlagged(999_999, null))
        assertFalse(Visits.gapFlagged(null, 24))
    }
}
