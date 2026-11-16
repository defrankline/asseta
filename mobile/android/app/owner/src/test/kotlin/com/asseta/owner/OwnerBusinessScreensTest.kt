package com.asseta.owner

import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CustomerHoursSummaryDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.network.NetworkFactory
import com.asseta.core.ui.shell.PillTone
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.customers.CustomersPresentation
import com.asseta.owner.ui.machines.MachinesPresentation
import com.asseta.owner.ui.machines.MachinesTexts
import com.asseta.owner.ui.money.MoneyPresentation
import com.asseta.owner.ui.money.PayMethod
import com.asseta.owner.ui.money.PaymentDraft
import com.asseta.owner.ui.money.PaymentRules
import com.asseta.owner.ui.money.PaymentTexts
import com.asseta.owner.ui.money.PaymentViewModel
import com.asseta.owner.ui.reports.OwnerReportsPresentation
import com.asseta.owner.ui.reports.OwnerReportsTexts
import com.asseta.owner.ui.common.Period
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.builtins.ListSerializer
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.util.Collections

/** ADR-008 Owner app: Customers & hours, Machines, Money, Record payment and Reports. */
@OptIn(ExperimentalCoroutinesApi::class)
class OwnerBusinessScreensTest {
    private val json = NetworkFactory.json
    private val reportsTest = MachineReportOwnerTest()

    @Before
    fun setUp() = Dispatchers.setMain(Dispatchers.Unconfined)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }

    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    private fun invoice(
        id: String = ID1, number: String = "INV-0042", amount: String = "3800000", paid: String = "1800000", balance: String = "2000000",
        status: String = "PART_PAID", overdue: Boolean = false, customer: String = ID2, due: String = "2026-11-30",
    ) = """{"id":"$id","invoice_number":"$number","purchase_id":"$ID2","customer_id":"$customer","customer_name":"Msasani Bay","machine_id":"$ID2",
        "currency":"TZS","hours":"40","unit_price":"95000","amount":"$amount","paid":"$paid","paid_verified":"0","balance":"$balance",
        "payment_terms_days":14,"issued_at":"2026-11-16T15:20:00Z","due_date":"$due","status":"$status","overdue":$overdue,"days_overdue":0,
        "created_by":null}"""

    private fun inv(s: String = invoice()) = json.decodeFromString(CreditInvoiceDto.serializer(), s)

    // --- Customers & hours ------------------------------------------------------------------------------------------

    @Test
    fun `customers show totals, hours left and their open invoices`() {
        val list = json.decodeFromString(
            ListSerializer(CustomerHoursSummaryDto.serializer()),
            """[{"customer_id":"c1","customer_name":"Pwani Road Contractors","bought":"160","activated":"160","used":"140","left":"20","awaiting_activation":"0","credit_owed":"0"},
                {"customer_id":"$ID2","customer_name":"Msasani Bay Developers","bought":"140","activated":"140","used":"140","left":"0","awaiting_activation":"0","credit_owed":"2000000"},
                {"customer_id":"c3","customer_name":"Mji Mpya Housing","bought":"100","activated":"62","used":"38","left":"62","awaiting_activation":"38","credit_owed":"3600000"}]""",
        )
        val t = CustomersPresentation.totals(list)
        assertEquals(listOf("400 h", "318 h", "5.6M"), CustomersPresentation.figures(t).map { it.value })
        assertEquals(listOf("Bought", "Used", "Credit owed"), CustomersPresentation.figures(t).map { it.label })
        assertEquals("Bought 160 h · used 140 h · all paid", CustomersPresentation.detail(list[0]))
        assertEquals("Bought 140 h · used 140 h", CustomersPresentation.detail(list[1]))
        assertEquals("Bought 100 h · used 38 h · 3.6M on credit, awaiting approval", CustomersPresentation.detail(list[2]))
        assertEquals(listOf("Mji Mpya Housing"), CustomersPresentation.filter(list, "mji").map { it.customerName })
        assertEquals(3, CustomersPresentation.filter(list, "  ").size)
        val invoices = listOf(inv(), inv(invoice(id = "x", status = "PAID", balance = "0")), inv(invoice(id = "y", customer = "c1")))
        assertEquals(listOf(ID1), CustomersPresentation.openInvoices(list[1], invoices).map { it.id })
        assertEquals("3,800,000 · paid 1,800,000 · due 30 Nov", CustomersPresentation.invoiceLine(inv()))
    }

    // --- Machines ---------------------------------------------------------------------------------------------------

    @Test
    fun `machines add up the week's reports per machine and flag those without a report`() {
        val reports = listOf(
            json.decodeFromString(MachineReportDto.serializer(), reportsTest.report(ID1)),
            json.decodeFromString(MachineReportDto.serializer(), reportsTest.report("r2", status = "REJECTED", hours = "50", customerHours = "50", npHours = "0")),
        )
        val statuses = json.decodeFromString(
            ListSerializer(MachineReportStatusDto.serializer()),
            """[{"machine_id":"$ID2","machine_code":"EX-01","machine_name":"CAT 320D2","days_since_report":0,"pending_report_id":"$ID1"},
                {"machine_id":"m2","machine_code":"EX-02","machine_name":"Komatsu PC210","days_since_report":3,"last_approved_reading":"812.5"}]""",
        )
        val fleet = listOf(
            json.decodeFromString(MachineMapDto.serializer(), Samples.machine().replace("\"$ID1\"", "\"$ID2\"").replace("\"open_alerts\":1", "\"open_alerts\":1,\"supervisor\":\"Daudi\"")),
            json.decodeFromString(MachineMapDto.serializer(), Samples.machine().replace("\"$ID1\"", "\"00000000-0000-4000-8000-0000000000m2\"".replace("m2", "02"))),
        )
        val f = OwnerFeatures(setOf("tenant.fleet.read", "tenant.machine_report.read"))
        val rows = MachinesPresentation.rows(statuses, reports, fleet, f)
        assertEquals(listOf("EX-02 · Komatsu PC210", "EX-01 · CAT 320D2"), rows.map { it.title })
        val ex01 = rows[1]
        assertEquals("300 h · 220 productive · last reading 1,510 h (pending)", ex01.detail)
        assertEquals("Daudi", ex01.subtitle)
        assertEquals(0, BigDecimal("300").compareTo(ex01.hours))
        assertEquals(OwnerDestination.Machine(ID2), ex01.open)
        val ex02 = rows[0]
        assertTrue(ex02.overdue)
        assertEquals(MachinesTexts.noReport(3), ex02.subtitle)
        assertEquals("No report 3 days", ex02.subtitle)
        // Without the fleet: no tracker line, the last approved reading; a tap opens the report waiting, if any.
        val noFleet = MachinesPresentation.rows(statuses, reports, emptyList(), OwnerFeatures(setOf("tenant.machine_report.read")))
        assertEquals("last reading 812.5 h", noFleet.first { it.machineId == "m2" }.detail)
        assertEquals(OwnerDestination.MachineReport(ID1), noFleet.first { it.machineId == ID2 }.open)
        assertNull(noFleet.first { it.machineId == "m2" }.open)
    }

    // --- Money ------------------------------------------------------------------------------------------------------

    private fun order(payments: String, credit: String?, amount: String, cancelled: Boolean = false) = json.decodeFromString(
        OwnerHoursPurchaseDto.serializer(),
        """{"id":"$ID1","purchase_number":"HP-1","customer_id":"$ID2","machine_id":"$ID2","hours":"10","status":"ACTIVE",
        "created_at":"2026-11-16T15:20:00Z","cancelled_at":${if (cancelled) "\"2026-11-16T16:00:00Z\"" else "null"},"currency":"TZS","amount":"$amount",
        "payments":[$payments],"credit_amount":${credit?.let { "\"$it\"" } ?: "null"},
        "totals":{"purchased":"10","activated":"10","consumed":"0","remaining":"10","awaiting_activation":"0"}}""",
    )

    @Test
    fun `money sums the period's sales by method, credit from the credit parts`() {
        val orders = listOf(
            order("""{"id":"p1","amount":"5400000","method":"CASH","status":"VERIFIED"},{"id":"p2","amount":"2000000","method":"BANK","status":"CLAIMED"}""", null, "7400000"),
            order("""{"id":"p3","amount":"1400000","method":"MOBILE_MONEY","status":"VERIFIED"},{"id":"p4","amount":"999","method":"CASH","status":"REJECTED"}""", "3800000", "5200000"),
            order("""{"id":"p5","amount":"700000","method":"CASH","status":"VERIFIED"}""", null, "700000", cancelled = true),
        )
        val sold = MoneyPresentation.sold(orders).single()
        assertEquals("TZS 12,600,000", sold.totalText)
        assertEquals("Cash 5.4M · Bank 2.0M · Mobile 1.4M · Credit 3.8M", sold.methodsText)
        assertTrue(MoneyPresentation.sold(emptyList()).isEmpty())
    }

    @Test
    fun `credit invoice pills and lines`() {
        assertEquals("Part paid" to PillTone.WAITING, MoneyPresentation.pill(inv()))
        assertEquals("Unpaid" to PillTone.WAITING, MoneyPresentation.pill(inv(invoice(status = "UNPAID", paid = "0"))))
        assertEquals("Paid" to PillTone.GOOD, MoneyPresentation.pill(inv(invoice(status = "PAID", balance = "0"))))
        assertEquals("Overdue" to PillTone.BAD, MoneyPresentation.pill(inv(invoice(overdue = true))))
        assertEquals("INV-0042 · Msasani Bay", MoneyPresentation.invoiceTitle(inv()))
        assertEquals("3.8M · paid 1.8M · due 30 Nov", MoneyPresentation.invoiceDetail(inv()))
        assertEquals("3.6M · due 30 Nov", MoneyPresentation.invoiceDetail(inv(invoice(amount = "3600000", paid = "0", status = "UNPAID"))))
        val ordered = MoneyPresentation.invoices(listOf(inv(invoice(id = "paid", status = "PAID", balance = "0")), inv(invoice(id = "late", overdue = true)), inv()))
        assertEquals(listOf("late", ID1, "paid"), ordered.map { it.id })
    }

    @Test
    fun `cash with supervisors says handed over awaiting check or overdue`() {
        val s = json.decodeFromString(
            CashSupervisorSummaryDto.serializer(),
            """{"staff_member_id":"$ID1","staff_name":"Daudi Mollel","currency":"TZS","period_from":"2026-11-17","period_to":"2026-11-17","opening":"0",
            "floats_issued":"0","collections":"0","approved_spending":"0","verified_handovers":"0","closing_outstanding":"3850000",
            "claimed_unverified_handovers":"1200000","pending_spending":"0","unverified_collections":"0"}""",
        )
        val today = LocalDate.parse("2026-11-17")
        assertEquals("Handed over 1.2M · awaiting your check", MoneyPresentation.cashDetail(s, null, today))
        val flag = json.decodeFromString(
            RemittanceOverdueDto.serializer(),
            """{"id":"f","staff_member_id":"$ID1","local_day":"2026-11-17","cutoff_hour":18,"flagged_at":"2026-11-17T15:00:00Z","policy_version":"p","held_since":"2026-11-15T10:00:00Z"}""",
        )
        assertEquals("Overdue to hand over · 2 days", MoneyPresentation.cashDetail(s, flag, today))
    }

    // --- Record payment ---------------------------------------------------------------------------------------------

    @Test
    fun `payment form rules`() {
        val i = inv()
        assertEquals(PaymentTexts.CHOOSE_INVOICE, PaymentRules.problem(PaymentDraft(), null))
        assertEquals(PaymentTexts.AMOUNT_NEEDED, PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "0"), i))
        assertEquals(PaymentTexts.AMOUNT_NEEDED, PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "12.345"), i))
        assertEquals(PaymentTexts.overBalance(BigDecimal("2000000")), PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "2000001"), i))
        assertNull(PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "2,000,000"), i))
        assertEquals(PaymentTexts.REFERENCE_NEEDED, PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "170000", method = PayMethod.BANK), i))
        assertEquals(PaymentTexts.REFERENCE_NEEDED, PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "170000", method = PayMethod.MOBILE_MONEY, reference = " "), i))
        assertNull(PaymentRules.problem(PaymentDraft(invoiceId = ID1, amount = "170000", method = PayMethod.MOBILE_MONEY, reference = "QK12AB34"), i))
        // Open invoices only: balance left, not paid or cancelled; overdue first.
        val open = PaymentRules.open(listOf(inv(invoice(id = "p", status = "PAID", balance = "0")), inv(invoice(id = "c", status = "CANCELLED")), inv(), inv(invoice(id = "late", overdue = true))))
        assertEquals(listOf("late", ID1), open.map { it.id })
        // The body: cash has no reference; received yesterday is noon local time; client_id is the form key.
        val now = Instant.parse("2026-11-17T09:00:00Z")
        val cash = PaymentRules.body(PaymentDraft(invoiceId = ID1, amount = "170000.00", reference = "ignored", key = "k1"), now, ZoneOffset.UTC)
        assertEquals("170000", cash.amount)
        assertEquals("CASH", cash.method)
        assertNull(cash.reference)
        assertEquals("k1", cash.clientId)
        assertEquals("2026-11-17T09:00:00Z", cash.receivedAt)
        val bank = PaymentRules.body(PaymentDraft(invoiceId = ID1, amount = "5", method = PayMethod.BANK, reference = " TX1 ", yesterday = true), now, ZoneOffset.UTC)
        assertEquals("TX1", bank.reference)
        assertEquals("2026-11-16T12:00:00Z", bank.receivedAt)
    }

    @Test
    fun `recording a payment sends the form key and maps invoice refusals`() {
        val h = OwnerHarness()
        val posts = Collections.synchronizedList(mutableListOf<Triple<String, String, String?>>())
        val refuse = java.util.concurrent.atomic.AtomicReference<String?>("INVOICE_OVERPAYMENT")
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.method == "POST") {
                    posts += Triple(request.url.encodedPath, request.body!!.utf8(), request.headers["Idempotency-Key"])
                    refuse.get()?.let { return MockResponse.Builder().code(422).body("""{"error":{"code":"$it","message":"refused","correlation_id":"c"}}""").build() }
                    return MockResponse.Builder().code(201).body(invoice(balance = "1830000", paid = "1970000")).build()
                }
                return MockResponse.Builder().code(200).body(Samples.page(invoice())).build()
            }
        }
        try {
            val vm = PaymentViewModel(h.data, ID1, clock = { Instant.parse("2026-11-17T09:00:00Z") }, zone = ZoneOffset.UTC)
            vm.invoices.state.settled()
            vm.submit()
            assertTrue(posts.isEmpty())
            vm.edit { it.copy(amount = "170000") }
            val key = vm.draft.value.key
            vm.submit()
            assertEquals(PaymentTexts.refusal("INVOICE_OVERPAYMENT", "x"), vm.error.await { it != null })
            vm.busy.await { !it }
            assertEquals("/api/v1/tenant/credit-invoices/$ID1/payments", posts[0].first)
            assertEquals(key, posts[0].third)
            assertTrue(posts[0].second.contains("\"client_id\":\"$key\""))
            refuse.set(null)
            vm.submit()
            assertEquals("Payment recorded. INV-0042: TZS 1,830,000 left.", vm.done.await { it != null })
            // The retry after the refusal reused the visit's key; the next payment gets a new one.
            assertEquals(key, posts[1].third)
            assertFalse(vm.draft.value.key == key)
        } finally {
            h.close()
        }
        assertTrue(PaymentTexts.refusal("INVOICE_PAID", "x").contains("already paid"))
        assertTrue(PaymentTexts.refusal("INVOICE_CANCELLED", "x").contains("cancelled"))
        assertTrue(PaymentTexts.refusal("PAYMENT_NOT_PERMITTED", "x").contains("bank or mobile money"))
    }

    // --- Reports ----------------------------------------------------------------------------------------------------

    @Test
    fun `reports split machine hours by customers and reasons and link to screens`() {
        val r = json.decodeFromString(MachineReportDto.serializer(), reportsTest.report())
        val noLines = json.decodeFromString(MachineReportDto.serializer(), reportsTest.report("r2", hours = "10", customerHours = "6", npHours = "4", lines = ""))
        val rejected = json.decodeFromString(MachineReportDto.serializer(), reportsTest.report("r3", status = "REJECTED"))
        val split = OwnerReportsPresentation.split(listOf(r, noLines, rejected))
        assertEquals(0, BigDecimal("226").compareTo(split.customers))
        assertEquals(listOf("Breakdown", "Transit", "Idle", "Non-productive"), split.reasons.map { it.first })
        assertEquals(0, BigDecimal("310").compareTo(split.total))
        assertEquals("Machine hours, November", OwnerReportsTexts.title(Period.MONTH, LocalDate.parse("2026-11-17")))
        assertEquals("80 h still with customers", OwnerReportsTexts.stillWithCustomers(BigDecimal("80")))
        val all = OwnerFeatures(setOf("tenant.machine_report.read", "tenant.hours.read", "tenant.finance.read"))
        assertEquals(
            listOf(
                OwnerReportsTexts.ROW_CUSTOMER_HOURS, OwnerReportsTexts.ROW_BY_MACHINE, OwnerReportsTexts.ROW_BY_REASON,
                OwnerReportsTexts.ROW_SALES, OwnerReportsTexts.ROW_CREDIT, OwnerReportsTexts.ROW_CASH,
            ),
            OwnerReportsPresentation.links(all).map { it.label },
        )
        assertEquals(
            listOf(OwnerDestination.Customers, OwnerDestination.Machines, OwnerDestination.HoursByReason, OwnerDestination.Money, OwnerDestination.Money, OwnerDestination.Cash),
            OwnerReportsPresentation.links(all).map { it.open },
        )
        assertEquals(listOf(OwnerReportsTexts.ROW_CASH), OwnerReportsPresentation.links(OwnerFeatures(setOf("tenant.finance.read"))).map { it.label })
        val (hours, amount) = OwnerReportsPresentation.sold(listOf(order("", null, "91200000").copy(hours = "960")))
        assertEquals(0, BigDecimal("960").compareTo(hours))
        assertEquals("TZS 91.2M", amount)
    }
}
