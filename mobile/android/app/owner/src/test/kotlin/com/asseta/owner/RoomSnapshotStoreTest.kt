package com.asseta.owner

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.asseta.core.database.AssetaDatabase
import com.asseta.core.domain.owner.SnapshotPolicy
import com.asseta.owner.data.RoomSnapshotStore
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** The Room-backed cache (Robolectric SQLite; SQLCipher at rest is covered by core:database's instrumented test). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class RoomSnapshotStoreTest {
    private var now = 10L * 86_400_000
    private val db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext<Context>(), AssetaDatabase::class.java)
        .allowMainThreadQueries().build()
    private val policy = SnapshotPolicy(maxEntriesPerTenant = 3, maxPayloadBytes = 100)
    private val store = RoomSnapshotStore({ db }, policy) { now }

    @After
    fun tearDown() = db.close()

    @Test
    fun `expired snapshots are hidden then purged`() = runBlocking {
        store.write(TENANT, "overview", "{}", now)
        now += 8L * 86_400_000
        assertNull(store.read(TENANT, "overview"))
        store.purgeExpired(now)
        assertEquals(0, db.readSnapshotDao().count(TENANT))
    }

    @Test
    fun `oversized payloads are not cached and count is bounded`() = runBlocking {
        store.write(TENANT, "big", "x".repeat(101), now)
        assertNull(store.read(TENANT, "big"))
        (1..5).forEach { store.write(TENANT, "k$it", "{}", now + it) }
        assertEquals(3, db.readSnapshotDao().count(TENANT))
        assertNotNull(store.read(TENANT, "k5"))
    }

    @Test
    fun `revoked tenants and sign out wipe`() = runBlocking {
        store.write(TENANT, "fleet", "[]", now)
        store.write("gone", "fleet", "[]", now)
        store.keepOnlyTenants(listOf(TENANT))
        assertNull(store.read("gone", "fleet"))
        store.wipeAll()
        assertNull(store.read(TENANT, "fleet"))
    }
}
