package com.asseta.core.sync

import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.sync.engine.AccountSwitch
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.WorkflowResult
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Several users on one phone: field data synced by one user is never shown to, bootstrapped over by, or pushed under
 * the token of the next. Unsynced work is held for its owner (not deleted) and sent when that owner signs in again.
 */
@RunWith(RobolectricTestRunner::class)
class AccountSwitchTest : SyncTestBase() {
    private val otherJob = "99999999-9999-4999-8999-999999999999"

    private fun success(report: SyncReport): SyncReport.Success {
        assertTrue("expected Success but was $report", report is SyncReport.Success)
        return report as SyncReport.Success
    }

    @Test
    fun anotherUserGetsAFreshBootstrapWhileThePreviousUsersWorkIsHeldUntilTheySignInAgain() = runBlocking {
        // User A bootstraps, then records an opening reading (with photo) that is not synced before signing out.
        success(engine().sync(tenant))
        assertEquals(10L, db.syncStateDao().get(tenant)!!.cursor)
        val aOp = saved(capture(captureRequest())).operationId
        assertEquals(USER_A.subject, op(aOp).ownerSub)
        assertEquals(USER_A.label, op(aOp).ownerLabel)
        assertEquals(USER_A.subject, db.evidenceDao().pendingAttachments(tenant, 10).single().ownerSub)

        // User B signs in on the same phone. Before B's home shows, A's synced data is reset; A's work is held.
        account = USER_B
        assertEquals(listOf(tenant), AccountSwitch { db }.claimAll(USER_B))
        val reset = db.syncStateDao().get(tenant)!!
        assertNull(reset.cursor)
        assertNull(reset.deviceSessionId)
        assertNull(reset.offlineGrantUntil)
        assertEquals(USER_B.subject, reset.ownerSub)
        assertTrue(repository.observeJobs(tenant).first().isEmpty())
        assertNull(db.fieldDataDao().job(fake.jobId))
        assertTrue(db.fieldDataDao().snapshots(tenant).isEmpty())
        assertTrue(db.financeDataDao().custody(tenant).isEmpty())
        assertTrue(repository.observeUnsynced(tenant).first().isEmpty())
        assertTrue(repository.observeCaptures(fake.jobId).first().isEmpty())
        assertTrue(repository.observeStatusCounts(tenant).first().isEmpty())
        assertEquals(0, repository.observePendingUploads(tenant).first())
        val held = repository.observeHeld(tenant).first().single()
        assertEquals(USER_A.subject to USER_A.label, held.ownerSub to held.ownerLabel)
        assertEquals(1, held.count)

        // B's first sync is a fresh bootstrap of B's own jobs (never `/changes` from A's cursor), and A's photo and
        // operation are neither uploaded nor pushed under B's token.
        fake.bootstrapJobs = listOf(fake.job("APPROVED", 1, id = otherJob))
        fake.requests.clear()
        success(engine().sync(tenant))
        assertTrue(fake.requests.contains("GET /api/v1/sync/bootstrap"))
        assertFalse(fake.requests.any { it.startsWith("GET /api/v1/sync/changes") })
        assertFalse(fake.requests.any { it.contains("/sync/blobs") || it.contains("/sync/push") })
        assertEquals(listOf(otherJob), repository.observeJobs(tenant).first().map { it.job.id })
        assertEquals(PENDING, status(aOp))
        assertTrue(fake.stored.isEmpty())

        // B's own work is sent under B's token; A's stays held.
        account = USER_B
        val bJob = workflow.addNote(tenant, otherJob, "B was here") as WorkflowResult.Done
        assertEquals(USER_B.subject, op(bJob.id).ownerSub)
        success(engine().sync(tenant))
        assertEquals(ACKED, status(bJob.id))
        assertEquals(PENDING, status(aOp))
        assertEquals(listOf(listOf(bJob.id)), fake.pushedBatches)
        assertEquals(listOf("Bearer token-${USER_B.subject}"), fake.pushAuthorizations)

        // A signs back in: A's tenant state is rebuilt from a fresh bootstrap and A's held work is finally sent, under
        // A's token. B's synced operation is now held from A's views.
        account = USER_A
        fake.bootstrapJobs = null
        fake.requests.clear()
        success(engine().sync(tenant))
        assertTrue(fake.requests.contains("GET /api/v1/sync/bootstrap"))
        assertEquals(ACKED, status(aOp))
        assertEquals(listOf(aOp), fake.pushedBatches.last())
        assertEquals("Bearer token-${USER_A.subject}", fake.pushAuthorizations.last())
        assertTrue(repository.observeHeld(tenant).first().isEmpty()) // B's only operation is synced
        assertEquals(listOf(fake.jobId), repository.observeJobs(tenant).first().map { it.job.id })
    }

    @Test
    fun theSameUserSigningInAgainKeepsCursorAndCachedData() = runBlocking {
        success(engine().sync(tenant))
        val aOp = saved(capture(captureRequest())).operationId
        assertEquals(PENDING, status(aOp))

        // Sign out and back in as the same user: nothing is reset.
        assertTrue(AccountSwitch { db }.claimAll(USER_A).isEmpty())
        assertEquals(10L, db.syncStateDao().get(tenant)!!.cursor)
        assertEquals(listOf(fake.jobId), repository.observeJobs(tenant).first().map { it.job.id })
        assertEquals(listOf(aOp), repository.observeUnsynced(tenant).first().map { it.id })

        fake.requests.clear()
        success(engine().sync(tenant))
        assertFalse(fake.requests.contains("GET /api/v1/sync/bootstrap"))
        assertTrue(fake.requests.contains("GET /api/v1/sync/changes?cursor=10"))
        assertEquals(ACKED, status(aOp))
    }

    @Test
    fun aRunningWorkLogEntryIsOnlyTheUsersWhoStartedIt() = runBlocking {
        success(engine().sync(tenant))
        val started = workflow.startEntry(tenant, fake.jobId, "WORK") as WorkflowResult.Done
        assertEquals(1, repository.observeWorkLog(fake.jobId).first().size)

        account = USER_B // B on the same (shared) job neither sees nor stops A's running entry
        assertTrue(repository.observeWorkLog(fake.jobId).first().isEmpty())
        assertTrue(workflow.stopEntry(tenant, started.id) is WorkflowResult.Refused)

        account = USER_A
        assertTrue(workflow.stopEntry(tenant, started.id) is WorkflowResult.Done)
        assertTrue(repository.observeWorkLog(fake.jobId).first().single().operationId != null)
    }

    @Test
    fun withoutASignedInUserNothingIsSynced() = runBlocking {
        account = null
        assertEquals(SyncReport.AuthRequired, engine().sync(tenant))
        assertTrue(fake.requests.isEmpty())
    }
}
