package com.asseta.owner

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.IdleMachineDto
import com.asseta.core.model.owner.ScorecardDetailDto
import com.asseta.core.model.owner.ScorecardRowDto
import com.asseta.core.model.owner.UnbilledJobDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.accountability.DashboardPresentation
import com.asseta.owner.ui.accountability.HoursPresentation
import com.asseta.owner.ui.accountability.OversightPresentation
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts
import com.asseta.owner.ui.accountability.ScorecardPeriod
import com.asseta.owner.ui.moreEntries
import kotlinx.serialization.builtins.ListSerializer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneId

/** DEC-031 Phase 5 in the Owner app: people scorecard, unbilled work, idle machines, REPEATED_PATTERN, hours format. */
class OversightOwnerTest {
    private val json = NetworkFactory.json
    private val zone = ZoneId.of("UTC")
    private val s1 = "11111111-1111-4111-8111-111111111111"
    private val s2 = "22222222-2222-4222-8222-222222222222"
    private val case1 = "44444444-4444-4444-8444-444444444444"
    private val all = OwnerFeatures(
        setOf(
            "tenant.oversight.scorecard.read", "tenant.oversight.read", "tenant.meter.read", "tenant.fleet.read", "tenant.finance.read",
            "tenant.case.read", "tenant.revenue.read", "tenant.job.read",
        ),
    )

    private fun row(id: String, name: String?, total: Int, extra: String = "") = """{"staff_member_id":"$id","staff_member_name":${name?.let { "\"$it\"" } ?: "null"},
        "staff_kind":"SUPERVISOR","employee_code":null,"is_active":true,"day_from":"2026-09-27","day_to":"2026-10-26","machines":2,
        "daily_reports_missing":2,"daily_reports_late":0,"unexplained_hours":"3.50","unexplained_items":1,"alerts":4,"alerts_open":1,
        "alerts_acknowledged":3,"avg_hours_to_acknowledge":"1.25","max_hours_to_acknowledge":"6.00","cash_held_too_long":0,"cash_differences":1,
        "cash_difference_totals":[{"currency":"TZS","count":1,"amount":"-5000.0000"}],"cash_differences_near_threshold":1,"revenue_differences":0,
        "revenue_difference_totals":[],"refused_attempts":0,"checkins_missed":null,"checkins_made":0,"pattern_signals":0,"items_total":$total,
        "cash_held":[{"currency":"TZS","amount":"120000.0000","held_since":"2026-10-24T09:00:00Z","held_days":2}]$extra}"""

    private fun rows(vararg r: String) = json.decodeFromString(ListSerializer(ScorecardRowDto.serializer()), "[${r.joinToString(",")}]")

    @Test
    fun `scorecard lists people with most items first and neutral wording`() {
        val list = rows(row(s1, "Baraka", 3), row(s2, null, 9), row("33333333-3333-4333-8333-333333333333", "Asha", 3))
        val from = LocalDate.parse("2026-09-27")
        val to = LocalDate.parse("2026-10-26")
        val out = OversightPresentation.rows(list, from, to)
        assertEquals(listOf("22222222", "Asha", "Baraka"), out.map { it.title })
        assertEquals("9 items to look at", out[0].subtitle)
        assertEquals("2 missing reports · 3.5 h unexplained · 1 open alerts", out[0].caption)
        assertEquals(OwnerDestination.ScorecardPerson(s2, null, "2026-09-27", "2026-10-26"), out[0].open)
        assertEquals("Nothing to look at", com.asseta.owner.ui.accountability.OversightTexts.items(0))
        assertEquals("1 item to look at", com.asseta.owner.ui.accountability.OversightTexts.items(1))
        val today = LocalDate.parse("2026-10-26")
        assertEquals(LocalDate.parse("2026-09-27") to today, ScorecardPeriod.LAST_30_DAYS.range(today))
        assertEquals(LocalDate.parse("2026-10-20") to today, ScorecardPeriod.LAST_7_DAYS.range(today))
        assertEquals(LocalDate.parse("2026-09-01") to LocalDate.parse("2026-09-30"), ScorecardPeriod.LAST_MONTH.range(today))
    }

    @Test
    fun `person figures, cash held and records that open existing screens by permission`() {
        val d = json.decodeFromString(
            ScorecardDetailDto.serializer(),
            """{"row":${row(s1, "Baraka", 5)},"records":[
              {"item":"MISSING_DAILY_REPORT","record_type":"job_exception","record_id":"$case1","at":"2026-10-20T00:00:00Z","day":"2026-10-20","machine_code":"EX-01","status":"OPEN"},
              {"item":"CASH_DIFFERENCE","record_type":"cash_variance","record_id":"$s2","at":"2026-10-22T10:00:00Z","day":"2026-10-22","amount":"-5000.0000","currency":"TZS","near_threshold":true},
              {"item":"PATTERN_SIGNAL","record_type":"risk_signal","record_id":"$s1","at":"2026-10-23T10:00:00Z","day":"2026-10-23","detail":{"case_id":"$case1"}},
              {"item":"MISSED_CHECKIN","record_type":"site_checkin_slot","record_id":null,"at":"2026-10-24T05:00:00Z","day":"2026-10-24","detail":{"scheduled_at":"2026-10-24T05:00:00Z"}},
              {"item":"UNEXPLAINED_HOURS","record_type":"engine_interval","record_id":null,"at":"2026-10-21T05:00:00Z","day":"2026-10-21","machine_id":"$s2","hours":"3.50"}]}""",
        )
        val figures = OversightPresentation.figureRows(d.row).toMap()
        assertEquals("27 Sep 2026 – 26 Oct 2026", figures["Period"])
        assertEquals("3.5 h · 1 items", figures["Unexplained engine hours"])
        assertEquals("4 · 1 open", figures["Alerts"])
        assertEquals("average 1.25 h · longest 6 h", figures["Time to acknowledge"])
        assertEquals("1 · TZS -5,000.00", figures["Cash differences"])
        assertEquals("1", figures["Near the case threshold"])
        assertFalse("Site check-ins" in figures) // never required in the period
        assertEquals(listOf("TZS 120,000.00" to "since 24 Oct 2026 (2 days)"), OversightPresentation.cashHeld(d.row, zone))

        val records = OversightPresentation.records(d, all, zone)
        assertEquals(listOf("Missed site check-in", "Repeated pattern", "Cash difference", "Unexplained engine hours", "Daily report missing"), records.map { it.title })
        assertEquals("24 Oct 2026 · Scheduled 05:00", records[0].caption)
        assertNull(records[0].open)
        assertEquals(OwnerDestination.Case(case1), records[1].open)
        assertEquals("TZS -5,000.00", records[2].value)
        assertTrue(records[2].caption!!.endsWith("Near the case threshold"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, s2), records[2].open)
        assertEquals(OwnerDestination.Machine(s2), records[3].open)
        assertEquals("3.5 h", records[3].value)
        assertEquals(OwnerDestination.MeterException(case1), records[4].open)
        assertEquals("20 Oct 2026 · EX-01 · Open", records[4].caption)

        // Without the permissions, the records show their details and open nothing.
        val none = OwnerFeatures(setOf("tenant.oversight.scorecard.read"))
        assertTrue(OversightPresentation.records(d, none, zone).all { it.open == null })
    }

    @Test
    fun `unbilled work and idle machines lists`() {
        val jobs = json.decodeFromString(
            ListSerializer(UnbilledJobDto.serializer()),
            """[{"job_id":"$s1","job_number":"J-7","machine_id":"$s2","machine_code":"EX-01","customer_id":"$case1","customer_name":"Acme",
               "job_site_id":null,"supervisor_staff_id":null,"completed_at":"2026-10-10T10:00:00Z","days_unbilled":16,"billable_hours":"8.00",
               "currency":"TZS","total":"400000.0000","draft_invoice_id":"$case1"}]""",
        )
        val u = OversightPresentation.unbilled(jobs, all, zone).single()
        assertEquals("J-7 · Acme", u.title)
        assertEquals("EX-01", u.subtitle)
        assertEquals("Completed 10 Oct 2026 · 16 days unbilled · On a draft invoice", u.caption)
        assertEquals("TZS 400,000.00", u.value)
        assertEquals(OwnerDestination.Job(s1), u.open)
        assertNull(OversightPresentation.unbilled(jobs, OwnerFeatures(emptySet()), zone).single().open)

        val idle = json.decodeFromString(
            ListSerializer(IdleMachineDto.serializer()),
            """[{"machine_id":"$s2","machine_code":"EX-01","category_id":null,"idle_since":"2026-10-01T00:00:00Z","idle_days":25,"last_job_id":"$s1",
               "last_job_number":"J-3","last_job_completed_at":"2026-09-30T12:00:00Z","last_engine_activity_at":null,"planned_job_id":null}]""",
        )
        val m = OversightPresentation.idle(idle, all, zone).single()
        assertEquals("EX-01", m.title)
        assertEquals("Idle since 1 Oct 2026 (25 days)", m.subtitle)
        assertEquals("Last job J-3 completed 30 Sep 2026", m.caption)
        assertEquals(OwnerDestination.Machine(s2), m.open)
    }

    @Test
    fun `dashboard tiles link to the lists only when allowed`() {
        val summary = json.decodeFromString(
            AccountabilitySummaryDto.serializer(),
            """{"as_of":"2026-10-26T08:00:00Z","policy_version":"v","unbilled_work":{"count":3,"after_days":7,"amounts":[{"currency":"TZS","count":3,"amount":"900000"}],
              "oldest_days":16,"items":[]},"idle_machines":{"count":2,"after_days":14,"longest_idle_days":25,"items":[]}}""",
        )
        val tiles = DashboardPresentation.tiles(summary, all).associateBy { it.key }
        val unbilled = tiles.getValue("unbilled_work")
        assertEquals(listOf("Jobs" to "3", "Value" to "TZS 900,000.00", "Oldest" to "16 days"), unbilled.rows)
        assertEquals("Completed jobs not on an issued invoice after 7 days.", unbilled.footer)
        assertEquals(OwnerDestination.UnbilledWork, unbilled.link)
        val idle = tiles.getValue("idle_machines")
        assertEquals(listOf("Machines" to "2", "Longest idle" to "25 days"), idle.rows)
        assertEquals(OwnerDestination.IdleMachines, idle.link)

        val noList = DashboardPresentation.tiles(summary, OwnerFeatures(emptySet())).associateBy { it.key }
        assertNull(noList.getValue("unbilled_work").link)
        val off = DashboardPresentation.tiles(summary, OwnerFeatures(all.permissions, setOf(TenantAccess.UNBILLED_WORK, TenantAccess.IDLE_MACHINES)))
        assertTrue(off.none { it.key == "unbilled_work" || it.key == "idle_machines" })
    }

    @Test
    fun `more entry, titles and fallbacks follow the gates`() {
        assertTrue(moreEntries(all).any { it.second == OwnerDestination.Scorecard })
        val off = OwnerFeatures(all.permissions, setOf(TenantAccess.SCORECARD, TenantAccess.UNBILLED_WORK, TenantAccess.IDLE_MACHINES))
        assertFalse(moreEntries(off).any { it.second == OwnerDestination.Scorecard })
        assertEquals(OwnerDestination.Accountability, off.route(OwnerDestination.Scorecard))
        assertEquals(OwnerDestination.Accountability, off.route(OwnerDestination.ScorecardPerson(s1)))
        assertEquals(OwnerDestination.Accountability, off.route(OwnerDestination.UnbilledWork))
        assertEquals(OwnerDestination.Accountability, off.route(OwnerDestination.IdleMachines))
        assertEquals(OwnerDestination.UnbilledWork, all.route(OwnerDestination.UnbilledWork))
        assertEquals("People scorecard", OwnerNavigation.title(OwnerDestination.Scorecard))
        assertEquals("Baraka", OwnerNavigation.title(OwnerDestination.ScorecardPerson(s1, "Baraka")))
        assertEquals("Unbilled work", OwnerNavigation.title(OwnerDestination.UnbilledWork))
        assertEquals("Idle machines", OwnerNavigation.title(OwnerDestination.IdleMachines))
        assertEquals("Repeated items to look at for one person", OwnerAccountabilityTexts.signalName("REPEATED_PATTERN"))
    }

    @Test
    fun `customer hours use the phone's number format without forced decimals`() {
        val before = java.util.Locale.getDefault()
        java.util.Locale.setDefault(java.util.Locale.US)
        try {
            assertEquals("1,234.5 h left", HoursPresentation.leftLine("1234.5000", "0.00"))
            assertEquals("12 h left · 4 h in use by running jobs", HoursPresentation.leftLine("12.00", "4.0000"))
        } finally {
            java.util.Locale.setDefault(before)
        }
    }
}
