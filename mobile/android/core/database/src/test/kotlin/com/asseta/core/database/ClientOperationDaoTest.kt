package com.asseta.core.database

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.FAILED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.ClientOperationStatus.QUARANTINED
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.UUID

/**
 * DAO behaviour on Robolectric's SQLite (SQLCipher native libs are device-only; encryption is covered by
 * the instrumented test in src/androidTest).
 */
@RunWith(RobolectricTestRunner::class)
class ClientOperationDaoTest {
    private lateinit var db: AssetaDatabase
    private lateinit var dao: ClientOperationDao
    private val tenant = UUID.randomUUID().toString()

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, AssetaDatabase::class.java).allowMainThreadQueries().build()
        dao = db.clientOperationDao()
    }

    @After
    fun tearDown() = db.close()

    private fun op(createdAt: Long, dependsOn: String? = null, tenantId: String = tenant) = ClientOperationEntity(
        id = UUID.randomUUID().toString(), tenantId = tenantId, opType = "CREATE", entityType = "test_entity",
        entityId = UUID.randomUUID().toString(), payloadJson = "{}", dependsOn = dependsOn,
        createdAtDevice = createdAt, status = PENDING, attemptCount = 0, lastError = null, serverRevision = null,
    )

    @Test
    fun enqueueIsIdempotent() = runTest {
        val first = op(1)
        dao.enqueue(first)
        assertEquals(-1L, dao.enqueue(first.copy(payloadJson = "{\"changed\":true}")))
        assertEquals("{}", dao.findById(first.id)!!.payloadJson)
    }

    @Test
    fun dependencyBlocksUntilAcked() = runTest {
        val parent = op(1).also { dao.enqueue(it) }
        val child = op(2, dependsOn = parent.id).also { dao.enqueue(it) }
        assertEquals(listOf(parent.id), dao.dispatchable(tenant, 10).map { it.id })

        assertEquals(1, dao.markSent(parent.id))
        assertEquals(emptyList<String>(), dao.dispatchable(tenant, 10).map { it.id })
        assertEquals(1, dao.markAcked(parent.id, serverRevision = 42))

        assertEquals(listOf(child.id), dao.dispatchable(tenant, 10).map { it.id })
        assertEquals(42L, dao.findById(parent.id)!!.serverRevision)
    }

    @Test
    fun cannotAckWithoutSendAndAckedCannotBeQuarantined() = runTest {
        val o = op(1).also { dao.enqueue(it) }
        assertEquals(0, dao.markAcked(o.id, 1))
        dao.markSent(o.id)
        dao.markAcked(o.id, 1)
        assertEquals(0, dao.quarantine(o.id, "late conflict"))
        assertEquals(ACKED, dao.findById(o.id)!!.status)
    }

    @Test
    fun failureRetryAndQuarantineAreVisible() = runTest {
        val o = op(1).also { dao.enqueue(it) }
        dao.markSent(o.id)
        dao.markFailed(o.id, "timeout")
        assertEquals(FAILED, dao.findById(o.id)!!.status)
        assertEquals(listOf(o.id), dao.dispatchable(tenant, 10).map { it.id })
        dao.markSent(o.id)
        assertEquals(2, dao.findById(o.id)!!.attemptCount)
        dao.quarantine(o.id, "CONFLICT")
        val problems = dao.observeProblems(tenant).first()
        assertEquals(QUARANTINED, problems.single().status)
        assertEquals("CONFLICT", problems.single().lastError)
    }

    @Test
    fun batchIsBoundedOrderedAndTenantScoped() = runTest {
        val ops = (5 downTo 1).map { op(it.toLong()).also { o -> dao.enqueue(o) } }
        dao.enqueue(op(0, tenantId = UUID.randomUUID().toString()))
        val batch = dao.dispatchable(tenant, 3)
        assertEquals(ops.sortedBy { it.createdAtDevice }.take(3).map { it.id }, batch.map { it.id })
        val counts = dao.observeStatusCounts(tenant).first().associate { it.status to it.count }
        assertEquals(mapOf<ClientOperationStatus, Int>(PENDING to 5), counts)
        assertNull(dao.findById("missing"))
    }
}
