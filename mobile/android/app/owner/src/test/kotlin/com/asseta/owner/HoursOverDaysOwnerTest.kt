package com.asseta.owner

import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.DailyMachineSheetDetailDto
import com.asseta.core.model.owner.HoursStatementDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.accountability.HoursPresentation
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts
import com.asseta.owner.ui.accountability.RevenuePresentation
import com.asseta.owner.ui.accountability.StatementPeriod
import com.asseta.owner.ui.moreEntries
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/** DEC-031 Phases 2 and 4 in the Owner app: fuel per engine hour, the machine-day investigation, customer hours. */
class HoursOverDaysOwnerTest {
    private val json = NetworkFactory.json
    private val p1 = "11111111-1111-4111-8111-111111111111"
    private val case1 = "44444444-4444-4444-8444-444444444444"

    private fun sheetDay(extra: String) = json.decodeFromString(
        DailyMachineSheetDetailDto.serializer(),
        """{"machine_id":"m","machine_code":"EX-01","day":"2026-10-25","first_reading":null,"last_reading":null,"reading_count":0,
           "engine_hours":"8.00","customer_work_hours":"0.00","non_revenue_hours":"0.00","revenue_hours":"0.00","approved_non_customer_hours":"0.00",
           "identified_variance_hours":"0.00","unexplained_hours":"8.00","pending_review_hours":"0.00","fuel_litres":"50.000",
           "flags":["ENGINE_ON_WITHOUT_JOB","FUEL_ABOVE_NORM"]$extra}""",
    )

    @Test
    fun `machine day shows litres per engine hour and links the investigation once`() {
        val d = sheetDay(
            ""","fuel_litres_per_engine_hour":"6.25","flag_records":[{"flag":"ENGINE_ON_WITHOUT_JOB","record_type":"anomaly_case","record_id":"$case1"},
               {"flag":"FUEL_ABOVE_NORM","record_type":"anomaly_case","record_id":"$case1"},{"flag":"REVENUE_DIFFERENCE","record_type":"revenue_difference","record_id":"x"}]""",
        )
        assertEquals(listOf("Fuel" to "50 L", "Litres per engine hour" to "6.25 L/h"), RevenuePresentation.fuelRows(d))
        assertEquals(listOf(case1), RevenuePresentation.caseIds(d))

        val older = sheetDay("")
        assertEquals(listOf("Fuel" to "50 L"), RevenuePresentation.fuelRows(older))
        assertTrue(RevenuePresentation.caseIds(older).isEmpty())
    }

    @Test
    fun `new risk rules are named, others humanized`() {
        assertEquals("Engine running without work during the day", OwnerAccountabilityTexts.signalName("ENGINE_RUNNING_WITHOUT_WORK"))
        assertEquals("Fuel above the norm for the engine hours", OwnerAccountabilityTexts.signalName("MACHINE_FUEL_ABOVE_NORM"))
        assertEquals("Meter decrease", OwnerAccountabilityTexts.signalName("METER_DECREASE"))
    }

    private fun purchase(id: String, remaining: String, provisional: String, createdAt: String, cancelled: Boolean = false, machines: String = "[]") =
        json.decodeFromString(
            OwnerHoursPurchaseDto.serializer(),
            """{"id":"$id","purchase_number":"HP-$id","customer_id":"c1","customer_name":"Acme","machine_id":"m1","machine_code":"EX-01",
               "hours":"20.00","status":"ACTIVE","created_at":"$createdAt","cancelled_at":${if (cancelled) "\"2026-10-20T00:00:00Z\"" else "null"},
               "totals":{"purchased":"20.00","activated":"20.00","activated_from_payments":"20.00","activated_on_credit":"0","awaiting_activation":"0.00",
                 "consumed":"6.00","transferred":"0.00","expired":"0.00","reversed":"0","remaining":"$remaining","provisional":"$provisional",
                 "amount_verified":"1","amount_claimed_unverified":"0","amount_outstanding":"0"},
               "machines":$machines}""",
        )

    @Test
    fun `customer hours list keeps open purchases with hours left or in use, newest first`() {
        val list = HoursPresentation.open(
            listOf(
                purchase("a", "10.00", "0.00", "2026-10-01T00:00:00Z"),
                purchase("b", "0.00", "4.00", "2026-10-10T00:00:00Z"),
                purchase("c", "0.00", "0.00", "2026-10-11T00:00:00Z"),
                purchase("d", "5.00", "0.00", "2026-10-12T00:00:00Z", cancelled = true),
            ),
        )
        assertEquals(listOf("b", "a"), list.map { it.id })
        assertEquals("10 h left", HoursPresentation.leftLine("10.00", "0.00"))
        assertEquals("0 h left · 4 h in use by running jobs", HoursPresentation.leftLine("0.00", "4.00"))
    }

    @Test
    fun `purchase rows show provisional beside what is left, never subtracted again`() {
        val p = purchase(
            p1, "10.00", "4.00", "2026-10-01T00:00:00Z",
            machines = """[{"machine_id":"m1","machine_code":"EX-01","activated":"20","transferred_in":"0","consumed":"6","transferred_out":"5","expired":"0","reversed":"0","remaining":"5.00","provisional":"4.00"},
                {"machine_id":"m2","machine_code":"EX-02","activated":"0","transferred_in":"5","consumed":"0","transferred_out":"0","expired":"0","reversed":"0","remaining":"5.00","provisional":"0"}]""",
        )
        assertEquals(
            listOf("Customer" to "Acme", "Machine" to "EX-01", "Status" to "Active", "Bought" to "20 h", "Activated" to "20 h", "Used" to "6 h",
                "In use by running jobs" to "4 h", "Left" to "10 h"),
            HoursPresentation.purchaseRows(p),
        )
        assertEquals(listOf("EX-01" to "5 h left · 4 h in use by running jobs", "EX-02" to "5 h left"), HoursPresentation.machineRows(p))
        assertTrue(HoursPresentation.machineRows(purchase(p1, "1", "0", "2026-10-01T00:00:00Z")).isEmpty())
        assertEquals("Used up", OwnerAccountabilityTexts.purchaseStatus("CONSUMED"))
    }

    @Test
    fun `statement totals, usage newest first and period chips`() {
        val s = json.decodeFromString(
            HoursStatementDto.serializer(),
            """{"customer_id":"c1","customer_name":"Acme","machine_id":null,"date_from":"2026-10-01","date_to":"2026-10-26","timezone":"Africa/Dar_es_Salaam",
               "generated_at":"2026-10-26T10:00:00Z","pdf_path":"/api/v1/tenant/customers/c1/hours-statement.pdf?date_from=2026-10-01&date_to=2026-10-26",
               "totals":{"opening_balance":"0","bought":"20","activated":"20","used":"10","transferred_in":"0","transferred_out":"0","expired":"0",
                 "cancelled":"0","closing_balance":"10","provisional_at_close":"4","awaiting_activation":"0"},
               "purchases":[],"lines":[],
               "usage":[{"day":"2026-10-20","job_id":"j","job_number":"J-7","machine_id":"m1","machine_code":"EX-01","hours":"6","basis":"FINAL","job_running":false},
                 {"day":"2026-10-25","job_id":"j2","job_number":"J-8","machine_id":"m1","machine_code":"EX-01","hours":"4","basis":"DAILY","job_running":true}]}""",
        )
        assertEquals("Acme · 1 Oct 2026 – 26 Oct 2026", HoursPresentation.header(s, null))
        assertEquals(
            listOf("Opening balance" to "0 h", "Bought" to "20 h", "Activated" to "20 h", "Used" to "10 h", "Of which in use by running jobs" to "4 h",
                "Closing balance" to "10 h"),
            HoursPresentation.totals(s),
        )
        val usage = HoursPresentation.usage(s)
        assertEquals("25 Oct 2026 · J-8", usage[0].label)
        assertEquals("4 h", usage[0].value)
        assertEquals("EX-01 · Drawn day by day · Job still running", usage[0].caption)
        assertEquals("EX-01 · Final", usage[1].caption)

        val today = LocalDate.of(2026, 3, 15)
        assertEquals(LocalDate.of(2026, 3, 1) to today, StatementPeriod.THIS_MONTH.range(today))
        assertEquals(LocalDate.of(2026, 2, 1) to LocalDate.of(2026, 2, 28), StatementPeriod.LAST_MONTH.range(today))
        assertEquals(LocalDate.of(2026, 1, 1) to today, StatementPeriod.LAST_3_MONTHS.range(today))
        assertEquals(LocalDate.of(2026, 1, 1) to today, StatementPeriod.THIS_YEAR.range(today))
        assertEquals(LocalDate.of(2025, 12, 1) to LocalDate.of(2025, 12, 31), StatementPeriod.LAST_MONTH.range(LocalDate.of(2026, 1, 5)))
    }

    @Test
    fun `hours notifications open the purchase, gated by customer hours`() {
        assertEquals(OwnerDestination.HoursPurchase(p1), DeepLinkRouter.fromTarget(null, null, null, kind = "HOURS_PURCHASE", recordId = p1))
        assertEquals(OwnerDestination.HoursPurchase(p1), DeepLinkRouter.fromPush(mapOf("kind" to "HOURS_PURCHASE", "record_id" to p1))!!.destination)
        assertEquals(OwnerDestination.CustomerHours, DeepLinkRouter.fromTarget("hours_purchase", null, null))
        assertEquals(OwnerDestination.CustomerHours, DeepLinkRouter.fromPath("/tenant/hours/purchases"))

        val on = OwnerFeatures(setOf("tenant.hours.read"))
        val off = OwnerFeatures(setOf("tenant.hours.read"), setOf(TenantAccess.CUSTOMER_HOURS))
        assertEquals(OwnerDestination.HoursPurchase(p1), on.route(OwnerDestination.HoursPurchase(p1)))
        assertEquals(OwnerDestination.Accountability, off.route(OwnerDestination.HoursPurchase(p1)))
        assertEquals(OwnerDestination.Accountability, OwnerFeatures(emptySet()).route(OwnerDestination.HoursStatement("c1")))
        assertTrue(moreEntries(on).any { it.second == OwnerDestination.CustomerHours })
        assertFalse(moreEntries(off).any { it.second == OwnerDestination.CustomerHours })
        assertEquals("Customer hours", OwnerNavigation.title(OwnerDestination.CustomerHours))
        assertEquals("Hours statement", OwnerNavigation.title(OwnerDestination.HoursStatement("c1")))
    }
}
