package com.asseta.supervisor.ui.accountability

import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.owner.CashRetentionDto
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.sync.data.FieldAccountabilityCache
import com.asseta.core.sync.data.RetentionStatus
import com.asseta.supervisor.ui.FieldTexts
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.isForm
import com.asseta.supervisor.ui.title
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

/** DEC-030 gap pass on the field app: names on transfers, offline retention rows, status and conflict wording. */
class GapPassPresentationTest {
    private fun op(entity: String, status: ClientOperationStatus, code: String? = null) =
        ClientOperationEntity("o-$entity", "t", AccountabilityOps.CASH_RETENTION_REQUEST, "cash_retention", entity, "{}", null, 1_000L, status, 0, null,
            null, null, errorCode = code)

    private fun retention(status: String) = CashRetentionDto(id = "r1", staffMemberId = "s1", amount = "20000", currency = "TZS", reason = "Fuel", status = status, createdAt = "2026-10-25T08:00:00Z",
        decidedByName = "Neema")

    @Test
    fun `transfers show the server's names, else saved names, else the short id`() {
        val t = CashTransferDto("t1", null, "op1-aaaaaaaa", "me", "5", null, "TZS", CashTransferDto.PENDING, "2026-10-25T08:00:00Z",
            "2026-10-25T08:00:00Z", source = "SYNC", fromStaffName = "Baraka")
        assertEquals(listOf("Transfer from Baraka"), MoneyAccountability.toAcknowledge(FieldAccountabilityCache(transfers = listOf(t)), "me", emptySet()).map { it.title })
        val noName = t.copy(fromStaffName = null)
        assertEquals(listOf("Transfer from op1-aaaa"), MoneyAccountability.toAcknowledge(FieldAccountabilityCache(transfers = listOf(noName)), "me", emptySet()).map { it.title })
    }

    @Test
    fun `retention requests made on this phone are listed with their sync state`() {
        val ops = listOf(op("c1", ClientOperationStatus.PENDING), op("c2", ClientOperationStatus.ACKED))
        val rows = MoneyAccountability.retentions(ops) { mapOf("amount" to "20000", "currency" to "TZS", "reason" to "Fuel") }
        assertEquals(listOf("c1", "c2"), rows.map { it.key })
        assertEquals(InboxStatus.WAITING, rows.first().status)
        assertEquals(InboxStatus.SYNCED, rows.last().status)
        assertEquals("Request to keep cash", FieldTexts.outboxTitle(AccountabilityOps.CASH_RETENTION_REQUEST, null))
        assertEquals("Request to keep cash", Route.RetentionStatus("c1").title("Acme"))
        assertFalse(Route.RetentionStatus("c1").isForm)
    }

    @Test
    fun `status line and conflicts in plain words`() {
        assertEquals("Waiting for approval", RetentionStatusText.line(RetentionStatus(null, "r1", retention("PENDING"), offline = false)))
        assertEquals("Approved", RetentionStatusText.line(RetentionStatus(null, "r1", retention("APPROVED"), offline = false)))
        assertEquals("This request has not reached the server yet.",
            RetentionStatusText.line(RetentionStatus(op("c1", ClientOperationStatus.PENDING), null, null, offline = false)))
        assertEquals("Your company does not allow keeping cash, so this request was not accepted.",
            RetentionStatusText.line(RetentionStatus(op("c1", ClientOperationStatus.CONFLICT, "RETENTION_NOT_ALLOWED"), null, null, offline = false)))
        assertEquals("Connect to the internet to see whether it was approved.",
            RetentionStatusText.line(RetentionStatus(op("c1", ClientOperationStatus.ACKED), "r1", null, offline = true)))
        assertEquals("This request to keep cash was already sent.", FieldAccountabilityTexts.conflict("DUPLICATE_RETENTION"))
        assertNull(FieldAccountabilityTexts.conflict("SOMETHING_ELSE"))
    }
}
