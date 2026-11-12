package com.asseta.core.sync

import com.asseta.core.sync.engine.SyncReport
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * "Delete my account" on the Supervisor: the phone's field data is erased only when no other account's unsent work is
 * held on it ([com.asseta.core.database.ClientOperationDao.countUnsyncedOfOthers]).
 */
@RunWith(RobolectricTestRunner::class)
class AccountDeletionLocalDataTest : SyncTestBase() {

    @Test
    fun `only another account's unsent work blocks erasing the phone after a deletion`() = runBlocking {
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        val dao = db.clientOperationDao()
        assertEquals(0, dao.countUnsyncedOfOthers(USER_A.subject))

        // A's own unsent reading does not block erasing after A deletes the account...
        saved(capture(captureRequest()))
        assertEquals(0, dao.countUnsyncedOfOthers(USER_A.subject))
        // ...but it is held for A if B deletes theirs on the same phone.
        assertEquals(1, dao.countUnsyncedOfOthers(USER_B.subject))

        // Once sent (ACKED), nothing is held for anyone.
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        assertEquals(0, dao.countUnsyncedOfOthers(USER_B.subject))
    }
}
