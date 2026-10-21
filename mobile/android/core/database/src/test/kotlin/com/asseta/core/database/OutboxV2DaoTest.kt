package com.asseta.core.database

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.ClientOperationStatus.PENDING
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

@RunWith(RobolectricTestRunner::class)
class OutboxV2DaoTest {
    private lateinit var db: AssetaDatabase
    private lateinit var ops: ClientOperationDao
    private val tenant = "t1"

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, AssetaDatabase::class.java).allowMainThreadQueries().build()
        ops = db.clientOperationDao()
    }

    @After
    fun tearDown() = db.close()

    private fun op(t: Long, attachment: String? = null) = ClientOperationEntity(
        UUID.randomUUID().toString(), tenant, "METER_CAPTURE", "meter_capture", UUID.randomUUID().toString(), "{}",
        null, t, PENDING, 0, null, null, jobId = "job", attachmentLocalId = attachment,
    )

    private suspend fun ack(id: String) {
        assertEquals(1, ops.markSent(id))
        assertEquals(1, ops.ackWithResult(id, "{}", null))
    }

    @Test
    fun multiParentDependenciesBlockUntilAllAcked() = runTest {
        val a = op(1).also { ops.enqueue(it) }
        val b = op(2).also { ops.enqueue(it) }
        val child = op(3).also { ops.enqueueWithDependencies(it, listOf(a.id, b.id, a.id)) }
        assertEquals(listOf(a.id, b.id).sorted(), ops.dependenciesOf(child.id))
        assertEquals(listOf(a.id, b.id), ops.dispatchable(tenant, 10).map { it.id })
        ack(a.id)
        assertEquals(listOf(b.id), ops.dispatchable(tenant, 10).map { it.id })
        ack(b.id)
        assertEquals(listOf(child.id), ops.dispatchable(tenant, 10).map { it.id })
    }

    @Test
    fun conflictedParentKeepsChildBlocked() = runTest {
        val parent = op(1).also { ops.enqueue(it) }
        val child = op(2).also { ops.enqueueWithDependencies(it, listOf(parent.id)) }
        ops.markSent(parent.id)
        ops.markConflict(parent.id, "INVALID_JOB_TRANSITION", "cancelled", """{"server_state":{"job_status":"CANCELLED"}}""")
        assertEquals(CONFLICT, ops.findById(parent.id)!!.status)
        assertEquals(emptyList<String>(), ops.dispatchable(tenant, 10).map { it.id })
        assertEquals(0, ops.markSent(parent.id)) // conflicts are never resent automatically
        assertEquals(PENDING, ops.findById(child.id)!!.status)
    }

    @Test
    fun captureWaitsForItsPhotoAttachment() = runTest {
        val evidence = db.evidenceDao()
        evidence.insertAttachment(AttachmentEntity("att", tenant, "METER_PHOTO", "f", "a".repeat(64), 10, "image/jpeg", AttachmentEntity.PENDING, createdAt = 1))
        val capture = op(1, attachment = "att").also { ops.enqueue(it) }
        assertEquals(emptyList<String>(), ops.dispatchable(tenant, 10).map { it.id })
        evidence.markAttachmentComplete("att", "server-att")
        assertEquals(listOf(capture.id), ops.dispatchable(tenant, 10).map { it.id })
        assertEquals(listOf(capture.id), ops.forAttachment("att").map { it.id })
    }

    @Test
    fun sentOpsRecoverAfterProcessDeathAndPayloadFreezesAfterFirstSend() = runTest {
        val o = op(1).also { ops.enqueue(it) }
        assertEquals(1, ops.patchUnsentPayload(o.id, """{"photo_attachment_id":"x"}"""))
        ops.markSent(o.id)
        assertEquals(0, ops.patchUnsentPayload(o.id, """{"changed":true}"""))
        assertEquals(1, ops.recoverInFlight())
        val recovered = ops.findById(o.id)!!
        assertEquals(PENDING, recovered.status)
        assertEquals("""{"photo_attachment_id":"x"}""", recovered.payloadJson)
        assertEquals(0, ops.patchUnsentPayload(o.id, "{}")) // attempted once: never patched again
        ack(o.id)
        assertEquals(ACKED, ops.findById(o.id)!!.status)
        assertNull(ops.findById(o.id)!!.serverRevision)
        val unsynced = ops.observeUnsynced(tenant).first()
        assertEquals(emptyList<ClientOperationStatus>(), unsynced.map { it.status })
    }

    @Test
    fun serverDataUpsertKeepsNewerVersion() = runTest {
        val field = db.fieldDataDao()
        fun job(v: Long, status: String) = JobEntity("j1", tenant, "J-1", "m1", "c1", null, status, v, "2026-10-21T08:00:00Z", null, null)
        assertEquals(1, field.upsertJobs(listOf(job(3, "APPROVED"))))
        assertEquals(0, field.upsertJobs(listOf(job(2, "DRAFT")))) // older replay from the lookback window
        assertEquals("APPROVED", field.job("j1")!!.status)
        assertEquals(1, field.upsertJobs(listOf(job(4, "IN_PROGRESS"))))
        assertEquals("IN_PROGRESS", field.job("j1")!!.status)
        field.deleteJobsNotIn(tenant, listOf("other"))
        assertNull(field.job("j1"))
    }
}
