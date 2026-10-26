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
    fun `routes are titled and presented as forms`() {
        assertEquals("Sell customer hours", Route.HoursSale.title("Acme"))
        assertEquals("Daily reading", Route.DailyReading("m1").title("Acme"))
        assertEquals("Cash float", Route.CashAck("f1", isFloat = true).title("Acme"))
        listOf(Route.HoursSale, Route.HoursTransfer, Route.CashTransfer, Route.Retention, Route.Baseline("m"), Route.Correction("r"))
            .forEach { assertTrue(it.isForm) }
    }
}
