package com.asseta.supervisor.ui.pettycash

import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.PettyCashAdvanceDto
import com.asseta.core.model.sync.PettyCashFundDto
import com.asseta.core.model.sync.PettyCashHolderChangeDto
import com.asseta.core.model.sync.PettyCashMovementDto
import com.asseta.core.model.sync.PettyCashOps
import com.asseta.core.sync.data.PettyCashRecord
import com.asseta.core.sync.data.PettyCashRepository
import com.asseta.supervisor.ui.FieldTexts
import com.asseta.supervisor.ui.InboxTexts
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.finance.ExpenseTexts
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** DEC-033 "My petty cash" on the Supervisor app: what waits, what is answered, wording and links. */
class PettyCashPresentationTest {
    private val me = "s-me"
    private val fund = PettyCashFundDto("f1", "PC-1", "Site box", me, currency = "TZS", approvedLimit = "100000")
    private val movement = PettyCashMovementDto("m1", "PC-0001", "f1", kind = PettyCashOps.TOP_UP, status = "ISSUED", amount = "30000", currency = "TZS", createdAt = "2026-10-20T08:00:00Z")
    private val change = PettyCashHolderChangeDto("h1", "f2", "Office box", "s-old", "Asha", me, "PENDING", requestedAt = "2026-10-20T08:00:00Z")
    private fun advance(id: String, fund: String, to: String) = PettyCashAdvanceDto(id, "ADV-$id", fund, recipientStaffId = to, recipientStaffName = "Juma",
        amount = "10000", currency = "TZS", purpose = "Spare parts", status = "OUTSTANDING", issuedAt = "2026-10-20T08:00:00Z", dueAt = "2026-10-27T08:00:00Z", remaining = "4000")

    private fun record(opType: String, entity: String, status: ClientOperationStatus = ClientOperationStatus.PENDING) =
        PettyCashRecord("op-$entity", opType, entity, null, "100", status, null, null, 1L)

    @Test
    fun `answered items leave the waiting lists unless the server refused them`() {
        val view = PettyCashRepository.build(
            listOf(fund), listOf(movement), listOf(change), listOf(advance("a1", "f1", "s-other")),
            listOf(record(PettyCashOps.ACKNOWLEDGEMENT, "m1"), record(PettyCashOps.ADVANCE_CLEARANCE, "a1")), me,
        )
        assertTrue(view.awaiting.isEmpty())
        assertTrue(view.advances.isEmpty())
        assertEquals(1, view.waitingCount)
        val refused = PettyCashRepository.build(listOf(fund), listOf(movement), emptyList(), emptyList(),
            listOf(record(PettyCashOps.ACKNOWLEDGEMENT, "m1", ClientOperationStatus.CONFLICT)), me)
        assertEquals(listOf("m1"), refused.awaiting.map { it.id })
    }

    @Test
    fun `funds and advances an expense can be paid from, and advances the holder clears`() {
        val view = PettyCashRepository.build(listOf(fund), emptyList(), emptyList(),
            listOf(advance("mine", "f9", me), advance("given", "f1", "s-other")), emptyList(), me)
        assertEquals(listOf("f1" to true, "f9" to false), PettyCashRepository.fundChoices(view, me).map { it.id to it.held })
        assertEquals(listOf("mine"), PettyCashRepository.advanceChoicesOf(view, me).map { it.id })
        assertEquals(listOf("given"), PettyCashRepository.clearable(view, me).map { it.id })
    }

    @Test
    fun `wording matches the strings doc`() {
        assertEquals("Top-up PC-0001 · 30000 TZS", PettyCashTexts.waitingMovement(movement))
        assertEquals("Funding PC-0001 · 30000 TZS", PettyCashTexts.waitingMovement(movement.copy(kind = PettyCashOps.FUNDING)))
        assertEquals("Take over Office box from Asha", PettyCashTexts.waitingHolderChange(change))
        assertEquals("Take over Office box from someone", PettyCashTexts.waitingHolderChange(change.copy(fromStaffName = " ")))
        assertEquals("PC-1 · Site box", PettyCashTexts.fundHeader(fund))
        assertEquals("2 waiting for you", PettyCashTexts.rowWaiting(2))
        assertEquals("Given to Juma", PettyCashTexts.advanceWho(advance("a", "f1", "x"), me))
        assertEquals("Given to you", PettyCashTexts.advanceWho(advance("a", "f1", me), me))
        assertEquals("Petty cash return", FieldTexts.outboxTitle(PettyCashOps.RETURN, null))
        assertEquals("Petty cash fund take-over", FieldTexts.outboxTitle(PettyCashOps.HOLDER_CHANGE_ACKNOWLEDGEMENT, null))
        assertEquals("This was already answered.", PettyCashTexts.conflict("PETTY_CASH_ALREADY_ACKNOWLEDGED"))
        assertNull(PettyCashTexts.conflict("SOMETHING_ELSE"))
        assertEquals("Petty cash", InboxTexts.paidFrom("PETTY_CASH"))
        assertEquals("Petty cash", ExpenseTexts.paidFrom(PaidFrom.PETTY_CASH))
    }

    @Test
    fun `petty cash is offered as paid-from only when there is a fund`() {
        assertEquals(listOf(PaidFrom.CASH_CUSTODY, PaidFrom.COMPANY), ExpenseTexts.paidFromOptions(false))
        assertEquals(PaidFrom.entries, ExpenseTexts.paidFromOptions(true))
    }

    @Test
    fun `notifications open the waiting record, else my petty cash`() {
        val view = PettyCashRepository.build(listOf(fund), listOf(movement), listOf(change), emptyList(), emptyList(), me)
        assertEquals(Route.PettyCashAck("m1"), PettyCashLinks.route("petty_cash_movement", "m1", view))
        assertEquals(Route.PettyCashHolderChange("h1"), PettyCashLinks.route("petty_cash_holder_change", "h1", view))
        assertEquals(Route.PettyCash, PettyCashLinks.route("petty_cash_movement", "other", view))
        assertEquals(Route.PettyCash, PettyCashLinks.route("petty_cash_count", "x", view))
        assertNull(PettyCashLinks.route("expense", "x", view))
    }
}
