package com.asseta.core.database

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** Owner offline cache bounds: per-tenant count, age purge, tenant revocation and sign-out wipe. */
@RunWith(RobolectricTestRunner::class)
class ReadSnapshotDaoTest {
    private lateinit var db: AssetaDatabase
    private val dao get() = db.readSnapshotDao()

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext<Context>(), AssetaDatabase::class.java)
            .allowMainThreadQueries().build()
    }

    @After
    fun tearDown() = db.close()

    private fun snap(tenant: String, key: String, at: Long) = ReadSnapshotEntity(tenant, key, """{"k":"$key"}""", at)

    @Test
    fun boundedWriteEvictsOldestOfThatTenantOnly() = runTest {
        dao.putBounded(snap("other", "overview", 1), 2)
        (1..4).forEach { dao.putBounded(snap("t", "k$it", it * 10L), 2) }
        assertEquals(2, dao.count("t"))
        assertNull(dao.get("t", "k1"))
        assertNotNull(dao.get("t", "k4"))
        assertEquals(1, dao.count("other"))
    }

    @Test
    fun replaceKeepsOneRowPerKeyWithNewestFetchTime() = runTest {
        dao.putBounded(snap("t", "fleet", 1), 10)
        dao.putBounded(snap("t", "fleet", 99), 10)
        assertEquals(1, dao.count("t"))
        assertEquals(99L, dao.get("t", "fleet")!!.fetchedAt)
    }

    @Test
    fun purgeAndWipes() = runTest {
        dao.putBounded(snap("t", "old", 5), 10)
        dao.putBounded(snap("t", "new", 50), 10)
        dao.putBounded(snap("gone", "overview", 50), 10)
        assertEquals(1, dao.purgeOlderThan(10))
        assertEquals(1, dao.deleteTenantsExcept(listOf("t")))
        assertEquals(1, dao.count("t"))
        assertEquals(1, dao.deleteAll())
        assertEquals(0, dao.count("t"))
    }
}
