package com.asseta.core.domain.owner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.math.BigDecimal
import java.time.ZoneId

class DeepLinkRouterTest {
    private val id = "3f2c1d1e-1111-4222-8333-944455556666"

    @Test
    fun `targets map to owner screens`() {
        assertEquals(OwnerDestination.Alerts(id), DeepLinkRouter.fromTarget("alert", id, "/tenant/alerts"))
        assertEquals(OwnerDestination.Approvals(id), DeepLinkRouter.fromTarget("approval", id, null))
        assertEquals(OwnerDestination.Job(id), DeepLinkRouter.fromTarget("job", id, null))
        assertEquals(OwnerDestination.Case(id), DeepLinkRouter.fromTarget("case", id, null))
        assertEquals(OwnerDestination.Machine(id), DeepLinkRouter.fromTarget("fleet.position", id, null))
    }

    @Test
    fun `console only targets open the inbox and bad ids are dropped`() {
        assertEquals(OwnerDestination.Notifications(id), DeepLinkRouter.fromTarget("customer_payment", "x", "/tenant/customer-payments", id))
        assertEquals(OwnerDestination.Jobs, DeepLinkRouter.fromTarget("job", "../../etc", null))
    }

    @Test
    fun `meter reset and exception targets`() {
        assertEquals(OwnerDestination.MeterReset(id), DeepLinkRouter.fromTarget("meter_reset", id, null))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromTarget("meter_reset", null, null))
        assertEquals(OwnerDestination.Exceptions(), DeepLinkRouter.fromTarget("exception", id, null))
        assertEquals(OwnerDestination.MeterReset(id), DeepLinkRouter.fromPath("/tenant/meter-resets/$id"))
        assertEquals(OwnerDestination.Exceptions(), DeepLinkRouter.fromPath("/tenant/exceptions"))
    }

    @Test
    fun `console paths`() {
        assertEquals(OwnerDestination.Job(id), DeepLinkRouter.fromPath("/tenant/jobs/$id"))
        assertEquals(OwnerDestination.Machine(id), DeepLinkRouter.fromPath("/tenant/fleet/machines/$id"))
        assertEquals(OwnerDestination.Approvals(null), DeepLinkRouter.fromPath("/tenant/approvals?x=1"))
        assertNull(DeepLinkRouter.fromPath("/platform/models/$id"))
        assertNull(DeepLinkRouter.fromPath("https://evil.example/tenant/jobs"))
    }

    @Test
    fun `push data carries tenant and notification`() {
        val link = DeepLinkRouter.fromPush(mapOf("notification_id" to id, "tenant_id" to id, "link" to "/tenant/alerts", "type" to "TRACKING_ALERT"))!!
        assertEquals(OwnerDestination.Alerts(null), link.destination)
        assertEquals(id, link.tenantId)
        assertEquals(id, link.notificationId)
        assertNull(DeepLinkRouter.fromPush(mapOf("type" to "X")))
        assertEquals(OwnerDestination.Notifications(id), DeepLinkRouter.fromPush(mapOf("notification_id" to id, "link" to ""))!!.destination)
    }
}

class OwnerFormatTest {
    @Test
    fun `money uses currency minor units and grouping`() {
        assertEquals("TZS 1,092,500.00", OwnerFormat.money(BigDecimal("1092500.0000"), "TZS"))
        assertEquals("JPY 1,234", OwnerFormat.money(BigDecimal("1234.5000"), "JPY")) // half-even, 0 minor units
        assertEquals("BHD 1.234", OwnerFormat.money(BigDecimal("1.2345"), "BHD")) // 3 minor units
        assertEquals("USD -0.12", OwnerFormat.money(BigDecimal("-0.125"), "USD")) // half-even
        assertEquals("XYZ 5.00", OwnerFormat.money(BigDecimal("5"), "XYZ")) // unknown code: 2 dp
    }

    @Test
    fun `dates and plain decimals`() {
        assertEquals("21 Oct 2026", OwnerFormat.date("2026-10-21T23:30:00Z", java.time.ZoneOffset.UTC))
        assertEquals("22 Oct 2026", OwnerFormat.date("2026-10-21T23:30:00Z", java.time.ZoneId.of("Africa/Dar_es_Salaam")))
        assertEquals("—", OwnerFormat.date(null, java.time.ZoneOffset.UTC))
        assertEquals("12.5", OwnerFormat.decimal(BigDecimal("12.500")))
        assertEquals("40", OwnerFormat.decimal(BigDecimal("40.000")))
        assertEquals("100", OwnerFormat.decimal(BigDecimal("100")))
    }

    @Test
    fun `hours and humanize`() {
        assertEquals("12.5 h", OwnerFormat.hours(BigDecimal("12.5000")))
        assertEquals("8 h", OwnerFormat.hours(BigDecimal("8.0000")))
        assertEquals("—", OwnerFormat.hours(null))
        assertEquals("Tracker offline", OwnerFormat.humanize("TRACKER_OFFLINE"))
    }

    @Test
    fun `instants in the tenant zone and stale banner`() {
        val zone = ZoneId.of("Africa/Dar_es_Salaam")
        assertEquals("21 Oct 2026, 17:05", OwnerFormat.dateTime("2026-10-21T14:05:00Z", zone))
        assertEquals("21 Oct 2026, 17:05", OwnerFormat.dateTime("2026-10-21T14:05:00.123456+00:00", zone))
        assertEquals("—", OwnerFormat.dateTime("not a date", zone))
        val ms = OwnerFormat.parseInstant("2026-10-21T14:05:00Z")!!.toEpochMilli()
        assertEquals("Offline — data from 21 Oct 2026, 17:05 (stale)", OwnerFormat.staleBanner(ms, zone))
        assertEquals(ZoneId.systemDefault(), OwnerFormat.zone("Not/AZone"))
    }
}

class NotificationMatrixTest {
    private val cells = listOf(
        PushCell("INFO", "INFO", false, false, false),
        PushCell("ACTION", "WARNING", true, true, false),
        PushCell("ACTION", "CRITICAL", true, true, true),
    )

    @Test
    fun `sorted by category priority then severity`() {
        assertEquals(listOf("ACTION/CRITICAL", "ACTION/WARNING", "INFO/INFO"), NotificationMatrix.sorted(cells).map { "${it.category}/${it.severity}" })
    }

    @Test
    fun `locked cells never change and only diffs are sent`() {
        var edited = NotificationMatrix.toggle(cells, "ACTION", "CRITICAL", false)
        assertEquals(cells, edited)
        edited = NotificationMatrix.toggle(edited, "INFO", "INFO", true)
        edited = NotificationMatrix.toggle(edited, "ACTION", "WARNING", false)
        assertEquals(setOf("INFO", "ACTION"), NotificationMatrix.changes(cells, edited).map { it.category }.toSet())
        assertEquals(0, NotificationMatrix.changes(cells, NotificationMatrix.toggle(edited, "INFO", "INFO", false).let { NotificationMatrix.toggle(it, "ACTION", "WARNING", true) }).size)
    }
}
