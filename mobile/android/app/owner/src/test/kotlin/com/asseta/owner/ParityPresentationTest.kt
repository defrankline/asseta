package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.NotificationMatrix
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.OwnerTab
import com.asseta.owner.ui.alerts.AlertText
import com.asseta.owner.ui.approvals.ApprovalText
import com.asseta.owner.ui.fleet.FleetRows
import com.asseta.owner.ui.home.KpiTone
import com.asseta.owner.ui.home.OverviewPresentation
import com.asseta.owner.ui.jobs.JobsPresentation
import com.asseta.owner.ui.moreEntries
import com.asseta.owner.ui.settings.SettingsText
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/**
 * Wording and rules that must match the iOS Owner app exactly. The iOS `ParityPresentationTests` assert the same
 * strings for the same inputs; change both together.
 */
class ParityPresentationTest {
    private val json = NetworkFactory.json
    private val now = java.time.Instant.parse("2026-10-22T08:10:00Z").toEpochMilli()

    private val overview = json.decodeFromString(
        TenantOverviewDto.serializer(),
        """{"tenant_id":"$TENANT","as_of":"2026-10-22T08:00:00Z","timezone":"UTC",
        "fleet":{"machines":5,"connectivity":{"live":2,"recent":1,"stale":1,"offline":1,"never":0,"no_tracker":0},
          "engine_on_verified":2,"open_alerts":{"critical":1,"warning":2,"info":0},"reported_work_state":{"WORKING":3},
          "latest_source_at":"2026-10-22T08:05:00Z"},
        "work":{"jobs_by_status":{"APPROVED":1,"IN_PROGRESS":2},"pending_approvals":1,"open_exceptions":0,"readings_needing_review":2},
        "money":{"month_start":"2026-10-01","currencies":[]},
        "risk":{"open_cases":{"critical":0,"warning":1,"info":0},"signals_last_7_days":{"critical":0,"warning":0,"info":3}}}""",
    )

    @Test
    fun `overview sections, labels and links`() {
        val sections = OverviewPresentation.sections(overview, cached = false, nowMs = now)
        assertEquals(listOf("Fleet", "Jobs and work", "Money (month from 2026-10-01)", "Investigations and signals"), sections.map { it.title })
        val fleet = sections[0].groups.single().rows
        assertEquals(
            listOf("Machines", "Live now", "Recent", "Stale", "Offline", "Never reported", "No tracker", "Engine on (tracker verified)", "Reported working", "Open alerts"),
            fleet.map { it.label },
        )
        val alerts = fleet.last()
        assertEquals("3", alerts.value)
        assertEquals("1 critical · 2 warning · 0 info", alerts.detail)
        assertEquals(KpiTone.CRITICAL, alerts.tone)
        assertEquals(OwnerDestination.Alerts(), alerts.target)
        assertEquals("Source data updated 5 min ago", sections[0].freshness)
        assertEquals(listOf("In progress", "Approved", "Pending approvals", "Readings needing review", "Open meter exceptions"), sections[1].groups.single().rows.map { it.label })
        assertEquals("No financial activity this month.", sections[2].emptyText)
        assertEquals(listOf("Open investigations", "Signals (last 7 days)"), sections[3].groups.single().rows.map { it.label })
        assertEquals("No source data yet", sections[3].freshness)
        assertEquals("Figures as of 22 Oct 2026, 08:00 (UTC)", OverviewPresentation.asOf(overview))
        // Offline the live count is history, never "now".
        assertEquals("Live when saved", OverviewPresentation.sections(overview, cached = true, nowMs = now)[0].groups[0].rows[1].label)
    }

    private fun machine(alerts: Int, code: String, lastMessage: String?) = json.decodeFromString(
        MachineMapDto.serializer(),
        """{"machine_id":"$ID1","asset_code":"$code","name":"Excavator","machine_status":"ACTIVE","connectivity":"OFFLINE","is_live":false,
        "observed_engine":"OFF","observed_motion":"STATIONARY","reported_work_status":"IDLE","location_compliance":"UNKNOWN","open_alerts":$alerts,
        "policy_version":"p","operator":"Ali","supervisor":"Neema","last_message_at":${lastMessage?.let { "\"$it\"" } ?: "null"},
        "last_seen_age_seconds":${if (lastMessage == null) "null" else "120"}}""",
    )

    @Test
    fun `fleet rows read and sort like iOS`() {
        val rows = FleetRows.build(
            listOf(machine(0, "B-2", "2026-10-22T08:00:00Z"), machine(2, "C-3", "2026-10-01T00:00:00Z"), machine(0, "A-1", null)),
            DataSource.LIVE, now, now,
        )
        assertEquals(listOf("C-3", "B-2", "A-1"), FleetRows.sorted(rows).map { it.machine.assetCode })
        val b = rows[0]
        assertEquals("B-2 · Excavator", FleetRows.title(b.machine))
        assertEquals("Last seen 2 min ago · engine off · stationary", FleetRows.detailLine(b))
        assertEquals("Never seen · engine off · stationary", FleetRows.detailLine(rows[2]))
        assertEquals("Reported: Idle · operator Ali", FleetRows.reportedLine(b.machine))
        assertEquals("2 open alerts", FleetRows.alertsLine(2))
        assertNull(FleetRows.unplacedNote(0))
        assertEquals("1 machine has no known position (see List).", FleetRows.unplacedNote(1))
        assertEquals("3 machines have no known position (see List).", FleetRows.unplacedNote(3))
    }

    @Test
    fun `tabs, start screen and More follow the role`() {
        val fleetOnly = OwnerFeatures(setOf("tenant.fleet.read"))
        assertEquals(listOf(OwnerTab.HOME, OwnerTab.FLEET, OwnerTab.ALERTS, OwnerTab.MORE), OwnerNavigation.tabs(fleetOnly))
        val inboxOnly = OwnerFeatures(setOf("tenant.notification.read"))
        assertEquals(listOf(OwnerTab.MORE), OwnerNavigation.tabs(inboxOnly))
        assertEquals(OwnerDestination.More, OwnerNavigation.start(inboxOnly))
        assertEquals(listOf("Notifications", "Settings"), moreEntries(inboxOnly).map { it.first })
        assertEquals("Overview", OwnerTab.HOME.label)
        assertEquals("Acme", OwnerNavigation.title(OwnerDestination.Home, "Acme"))
        assertEquals("Alert", OwnerNavigation.title(OwnerDestination.Alerts(ID1)))
        assertEquals("Approval", OwnerNavigation.title(OwnerDestination.Approvals(ID1)))
        assertEquals("Notification", OwnerNavigation.title(OwnerDestination.Notifications(ID1)))
    }

    @Test
    fun `list filters, ordering and decision rules`() {
        assertEquals(listOf("In progress", "Approved", "Pending approval", "Completed", "Cancelled", "All"), JobsPresentation.FILTERS.map { it.second })
        assertEquals("IN_PROGRESS", JobsPresentation.DEFAULT_FILTER)
        assertEquals(listOf("Open", "Acknowledged", "Resolved", "All"), AlertText.FILTERS.map { it.second })
        val info = json.decodeFromString(AlertDto.serializer(), Samples.alert(ID1).replace("\"WARNING\"", "\"INFO\""))
        val critical = json.decodeFromString(AlertDto.serializer(), Samples.alert(ID2).replace("\"WARNING\"", "\"CRITICAL\""))
        assertEquals(listOf(ID2, ID1), AlertText.sorted(listOf(info, critical)).map { it.id.toString() })
        assertTrue(ApprovalText.canDecide(approve = true, note = ""))
        assertFalse(ApprovalText.canDecide(approve = false, note = "  "))
        assertEquals("Needs your action", NotificationMatrix.label("ACTION"))
        assertEquals("Critical (required)", SettingsText.severityLabel("CRITICAL", locked = true))
        assertEquals("Not registered yet", SettingsText.pushStatus(available = true, registered = false, tenantName = "Acme"))
        assertEquals(
            "Can't reach Asseta — data from 21 Oct 2026, 14:05 (stale)",
            OwnerFormat.staleBanner(java.time.Instant.parse("2026-10-21T14:05:00Z").toEpochMilli(), ZoneOffset.UTC, online = true),
        )
    }
}
