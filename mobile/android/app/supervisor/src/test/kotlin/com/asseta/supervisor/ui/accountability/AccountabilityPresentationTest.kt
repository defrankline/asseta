package com.asseta.supervisor.ui.accountability

import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.model.sync.CustodianDto
import com.asseta.core.model.sync.FieldHoursPurchaseDto
import com.asseta.core.model.sync.FloatEntryDto
import com.asseta.core.model.sync.MachineHoursDto
import com.asseta.core.model.sync.PurchaseTotalsDto
import com.asseta.core.sync.data.FieldAccountabilityCache
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.isForm
import com.asseta.supervisor.ui.title
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AccountabilityPresentationTest {
    private fun custodian(id: String, name: String) = CustodianDto(id, name, null, hasLogin = false, isActive = true, kind = "OPERATOR")
    private fun transfer(id: String, from: String, to: String, status: String = CashTransferDto.PENDING, clientId: String? = null) =
        CashTransferDto(id, clientId, from, to, "50000", null, "TZS", status, "2026-10-25T08:00:00Z", "2026-10-25T08:00:00Z", source = "SYNC")
    private fun op(id: String, type: String, entity: String, status: ClientOperationStatus = ClientOperationStatus.PENDING) =
        ClientOperationEntity(id, "t", type, "x", entity, "{}", null, 1_000L, status, 0, null, null, null)

    private val cache = FieldAccountabilityCache(
        custodians = listOf(custodian("me", "Asha"), custodian("op1", "Baraka")),
        transfers = listOf(transfer("t1", "op1", "me"), transfer("t2", "me", "op1", CashTransferDto.ACKNOWLEDGED, clientId = "c2")),
        floats = listOf(FloatEntryDto("f1", "me", "FLOAT_ISSUED", "100000", "TZS", "2026-10-24T08:00:00Z", ackRequired = true, ackStatus = "PENDING")),
    )

    @Test
    fun `cash to acknowledge lists transfers to me and floats, minus answered ones`() {
        val rows = MoneyAccountability.toAcknowledge(cache, "me", emptySet())
        assertEquals(listOf("Transfer from Baraka", "Float from the office"), rows.map { it.title })
        val answered = MoneyAccountability.answeredIds(listOf(op("o1", AccountabilityOps.CASH_TRANSFER_ACKNOWLEDGEMENT, "t1")))
        assertEquals(listOf("f1"), MoneyAccountability.toAcknowledge(cache, "me", answered).map { it.id })
    }

    @Test
    fun `transfers merge my server transfers with unsynced ones`() {
        val local = op("o2", AccountabilityOps.CASH_TRANSFER, "c9")
        val already = op("o3", AccountabilityOps.CASH_TRANSFER, "c2", ClientOperationStatus.ACKED)
        val rows = MoneyAccountability.transfers(cache, "me", listOf(local, already)) { mapOf("to_staff_id" to "op1", "amount" to "7000", "currency" to "TZS") }
        assertEquals(3, rows.size) // c2 is the server's t2
        assertEquals(InboxStatus.WAITING, rows.first { it.key == "o2" }.status)
        assertEquals("To Baraka", rows.first { it.key == "t2" }.title)
        assertEquals("Acknowledged", rows.first { it.key == "t2" }.statusText)
        assertEquals("From Baraka", rows.first { it.key == "t1" }.title)
    }

    @Test
    fun `custodian options list me first and purchases show hours left`() {
        assertEquals(listOf("Me", "Baraka"), custodianOptions(cache.custodians, "me").map { it.title })
        val p = FieldHoursPurchaseDto("p1", "HP-2026-00001", "c1", "Joe", "m1", "20", "ACTIVE",
            PurchaseTotalsDto("20", "20", "8", "12", "0"), listOf(MachineHoursDto("m1", "0"), MachineHoursDto("m2", "12")))
        assertEquals("HP-2026-00001 · 12 h left", purchaseOptions(listOf(p)).single().title)
        assertEquals("m2", HoursTransferViewModel.defaultFrom(p))
    }

    @Test
    fun `purchases show hours in use by running jobs beside hours left`() {
        val p = FieldHoursPurchaseDto("p1", "HP-2026-00001", "c1", "Joe", "m1", "20", "ACTIVE",
            PurchaseTotalsDto("20", "20", "4", "12.00", "0", provisional = "4.00"),
            listOf(MachineHoursDto("m1", "8", provisional = "4.00"), MachineHoursDto("m2", "4")))
        assertEquals("HP-2026-00001 · 12 h left · 4 h in use by running jobs", purchaseOptions(listOf(p)).single().title)
        assertEquals("4", inUseOn(p, "m1"))
        assertEquals(null, inUseOn(p, "m2"))
        assertEquals("4", inUseOn(p, null))
        assertEquals("4 h in use by running jobs", FieldAccountabilityTexts.hoursInUse("4"))
        val none = p.copy(totals = p.totals.copy(provisional = "0"), machines = emptyList())
        assertEquals("HP-2026-00001 · 12 h left", purchaseOptions(listOf(none)).single().title)
        assertEquals(null, inUseOn(none, "m1"))
    }

    @Test
    fun `hours sale total wording`() {
        val book = com.asseta.core.domain.accountability.HoursPriceBook(
            prices = mapOf("ex01" to com.asseta.core.domain.accountability.HoursPrice("ex01", java.math.BigDecimal("95000.0000"), java.math.BigDecimal.ZERO, "TZS")),
            discounts = mapOf("acme" to java.math.BigDecimal("10.00")),
        )
        fun line(customer: String?, hours: String, walkIn: Boolean = false, machine: String? = "ex01") =
            FieldAccountabilityTexts.hoursPrice(com.asseta.core.domain.accountability.HoursPricing.price(book, machine, customer, walkIn, hours))
        assertEquals("Total: TZS 570,000 (6 h × 95,000/h)", line(null, "6"))
        assertEquals("Total: TZS 513,000 (6 h × 95,000/h less 10% discount)", line("acme", "6"))
        assertEquals("Total: TZS 570,000 (6 h × 95,000/h)", line("acme", "6", walkIn = true))
        assertEquals("Total: TZS 1,068,750 (12.5 h × 95,000/h less 10% discount)", line("acme", "12.5"))
        assertEquals("The price is set when the sale reaches the office.", line(null, "6", machine = "other"))
        assertEquals(null, line(null, "", machine = "ex01"))
        assertEquals(null, line(null, "6", machine = null))
    }

    @Test
    fun `hours sale payment wording`() {
        val book = com.asseta.core.domain.accountability.HoursPriceBook(
            prices = mapOf("ex01" to com.asseta.core.domain.accountability.HoursPrice("ex01", java.math.BigDecimal("95000"), java.math.BigDecimal.ZERO, "TZS", 2)),
        )
        val price = com.asseta.core.domain.accountability.HoursPricing.price(book, "ex01", null, false, "6")
        fun lines(vararg amounts: String, p: com.asseta.core.domain.accountability.HoursSalePrice = price) = FieldAccountabilityTexts.paymentSummary(
            com.asseta.core.domain.accountability.HoursPayments.summary(amounts.map { com.asseta.core.domain.accountability.PaymentLine(amountText = it) }, p),
        )
        assertEquals(listOf("Paid TZS 0 of TZS 570,000 · Balance TZS 570,000", "Not paid yet"), lines())
        assertEquals(listOf("Paid TZS 300,000 of TZS 570,000 · Balance TZS 270,000", "Part paid (balance TZS 270,000)"), lines("300000"))
        assertEquals(listOf("Paid TZS 570,000 of TZS 570,000 · Balance TZS 0", "Fully paid"), lines("300000", "270000"))
        assertEquals(
            listOf("Paid TZS 570,000.50 of TZS 570,000 · Balance TZS 0", "The payments add up to more than the total of TZS 570,000."),
            lines("300000", "270000.50"),
        )
        assertEquals(listOf("Paid 300,000"), lines("300000", p = com.asseta.core.domain.accountability.HoursSalePrice.Unpriced))
        assertEquals(listOf("Not paid yet"), lines(p = com.asseta.core.domain.accountability.HoursSalePrice.Unpriced))
        assertEquals("Bank and mobile-money payments are recorded by the office.", FieldAccountabilityTexts.NONCASH_BY_OFFICE)
        assertEquals("Add payment", FieldAccountabilityTexts.ADD_PAYMENT)
        assertEquals("Payment 2", FieldAccountabilityTexts.paymentNumber(2))
    }

    @Test
    fun `hours sale on the sync screen lists its payments`() {
        fun title(json: String?) = com.asseta.supervisor.ui.FieldTexts.outboxTitle(
            AccountabilityOps.HOURS_PURCHASE, json?.let { kotlinx.serialization.json.Json.parseToJsonElement(it) as kotlinx.serialization.json.JsonObject },
        )
        assertEquals("Hours sale", title(null))
        assertEquals("Hours sale · Not paid yet", title("""{"hours":"6"}"""))
        assertEquals("Hours sale · Cash 570,000", title("""{"payment":{"method":"CASH","amount":"570000"}}"""))
        assertEquals(
            "Hours sale · Cash 300,000 + Bank 200,000 + Mobile money 70,000.5",
            title("""{"payments":[{"method":"CASH","amount":"300000"},{"method":"BANK","amount":"200000"},{"method":"MOBILE_MONEY","amount":"70000.50"}]}"""),
        )
    }

    @Test
    fun `routes are titled and presented as forms`() {
        assertEquals("Sell customer hours", Route.HoursSale.title("Acme"))
        assertEquals("Daily reading", Route.DailyReading("m1").title("Acme"))
        assertEquals("Cash float", Route.CashAck("f1", isFloat = true).title("Acme"))
        listOf(Route.HoursSale, Route.HoursTransfer, Route.CashTransfer, Route.Retention, Route.Baseline("m"), Route.Correction("r"))
            .forEach { assertTrue(it.isForm) }
    }
}
