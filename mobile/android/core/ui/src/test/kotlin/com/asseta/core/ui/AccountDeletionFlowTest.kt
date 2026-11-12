package com.asseta.core.ui

import com.asseta.core.model.TenantAccess
import com.asseta.core.model.TenantAccessState
import com.asseta.core.network.ApiException
import com.asseta.core.ui.session.AccountDeletionFlow
import com.asseta.core.ui.session.AccountDeletionText
import com.asseta.core.ui.session.CompanyNotice
import com.asseta.core.ui.session.DeletionStep
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.util.UUID

/** "Delete my account" (same steps as iOS `AccountDeletionFlowTests`) and the company-closure banner rule. */
class AccountDeletionFlowTest {
    private var online = true
    private var unsynced = 0
    private var syncs = 0
    private val sent = mutableListOf<String?>()
    private var deleted = 0
    private var failure: Throwable? = null

    private val flow = AccountDeletionFlow(
        online = { online },
        unsyncedCount = { unsynced },
        syncNow = { syncs++; unsynced = 0 },
        delete = { reason -> sent += reason; failure?.let { throw it } },
        onDeleted = { deleted++ },
    )

    private fun typed() { flow.setTyped("DELETE") }

    @Test
    fun `success sends the reason, then wipes and signs out once`() = runTest {
        flow.setReason("  Leaving the company  ")
        assertFalse(flow.canSubmit(true)) // DELETE not typed yet
        flow.setTyped("delete")
        assertFalse(flow.canSubmit(true))
        typed()
        assertTrue(flow.canSubmit(true))
        flow.submit()
        assertEquals(DeletionStep.Confirm, flow.ui.value.step)
        assertTrue(sent.isEmpty()) // nothing is sent before the final confirmation
        flow.confirm()
        assertEquals(listOf<String?>("Leaving the company"), sent)
        assertEquals(1, deleted)
        assertEquals(DeletionStep.Done, flow.ui.value.step)
        assertEquals("Your account was deleted.", AccountDeletionText.DELETED)
    }

    @Test
    fun `an empty reason is sent as none`() = runTest {
        typed(); flow.submit(); flow.confirm()
        assertEquals(listOf<String?>(null), sent)
    }

    @Test
    fun `last owner shows the server message and keeps the user signed in`() = runTest {
        failure = ApiException(422, "LAST_OWNER", "You are the last owner of Acme Hire. Give someone else the owner role first.", "c1")
        typed(); flow.submit(); flow.confirm()
        assertEquals(DeletionStep.Form, flow.ui.value.step)
        assertEquals("You are the last owner of Acme Hire. Give someone else the owner role first.", flow.ui.value.error)
        assertEquals(0, deleted)
    }

    @Test
    fun `platform account gets its own explanation`() = runTest {
        failure = ApiException(422, "PLATFORM_ACCOUNT", "Platform accounts are closed through the platform's own process", "c2")
        typed(); flow.submit(); flow.confirm()
        assertEquals("Platform accounts are removed by the platform owner.", flow.ui.value.error)
        assertEquals(0, deleted)
    }

    @Test
    fun `offline nothing is sent and the connection message is shown`() = runTest {
        online = false
        typed()
        assertFalse(flow.canSubmit(false))
        flow.submit()
        assertEquals(AccountDeletionText.OFFLINE, flow.ui.value.error)
        assertEquals(DeletionStep.Form, flow.ui.value.step)
        // Connection lost between the question and the answer: still nothing sent.
        online = true; flow.submit(); online = false; flow.confirm()
        assertEquals(AccountDeletionText.OFFLINE, flow.ui.value.error)
        assertTrue(sent.isEmpty())
        // A dropped request reads as a connection problem.
        online = true; failure = IOException("reset")
        flow.submit(); flow.confirm()
        assertEquals(AccountDeletionText.NETWORK, flow.ui.value.error)
        assertEquals(0, deleted)
    }

    @Test
    fun `unsynced work is warned about first and can be synced before deleting`() = runTest {
        unsynced = 3
        typed(); flow.submit()
        assertEquals(DeletionStep.Unsynced(3), flow.ui.value.step)
        assertEquals("Records not yet sent will be lost", AccountDeletionText.UNSYNCED_TITLE)
        assertTrue(AccountDeletionText.unsyncedMessage(3).startsWith("3 item(s) on this phone are not synced yet."))
        flow.syncFirst()
        assertEquals(1, syncs)
        assertEquals(DeletionStep.Confirm, flow.ui.value.step)
        flow.dismiss()
        assertEquals(DeletionStep.Form, flow.ui.value.step)
        assertTrue(sent.isEmpty())
    }

    @Test
    fun `delete anyway goes to the final question and still-unsent work warns again after a sync`() = runTest {
        unsynced = 2
        val stuck = AccountDeletionFlow({ true }, { unsynced }, { syncs++ }, { sent += it }, { deleted++ })
        stuck.setTyped("DELETE"); stuck.submit()
        stuck.syncFirst()
        assertEquals(DeletionStep.Unsynced(2), stuck.ui.value.step)
        stuck.deleteAnyway()
        assertEquals(DeletionStep.Confirm, stuck.ui.value.step)
        stuck.confirm()
        assertEquals(1, deleted)
    }

    @Test
    fun `closure banner shows the access reason and opens the request only with the close permission`() {
        val reason = "Company closure requested: all its data will be deleted on 2026-12-12"
        val t = TenantAccess(UUID.randomUUID(), "Acme", "ACTIVE", TenantAccessState.READ_ONLY, accessStateReason = reason)
        assertEquals(reason, CompanyNotice.banner(t))
        assertFalse(CompanyNotice.opensClosure(t))
        assertTrue(CompanyNotice.opensClosure(t.copy(permissions = listOf("tenant.company.close"))))
        assertNull(CompanyNotice.banner(t.copy(accessStateReason = null)))
        assertNull(CompanyNotice.banner(t.copy(accessStateReason = "  ")))
        assertFalse(CompanyNotice.opensClosure(t.copy(accessStateReason = null, permissions = listOf("tenant.company.close"))))
        assertNull(CompanyNotice.banner(null))
        assertNull(CompanyNotice.banner(t.copy(accessState = TenantAccessState.FULL, accessStateReason = "Company closure cancelled")))
    }
}
