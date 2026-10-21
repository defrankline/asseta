package com.asseta.core.sync

import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.ClientOperationStatus.FAILED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.ClientOperationStatus.QUARANTINED
import com.asseta.core.model.sync.AckMethod
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.usecase.WorkflowResult
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class SyncEngineTest : SyncTestBase() {

    private fun success(report: SyncReport): SyncReport.Success {
        assertTrue("expected Success but was $report", report is SyncReport.Success)
        return report as SyncReport.Success
    }

    @Test
    fun firstRunRegistersBootstrapsThenPullsByCursorWithNewerVersionWinning() = runBlocking {
        success(engine().sync(tenant))
        assertEquals(listOf("POST /api/v1/sync/devices", "GET /api/v1/sync/bootstrap"), fake.requests.take(2))
        assertTrue(fake.deviceHeaders.all { it == DEVICE }) // X-Device-Id on every /sync call
        val state = db.syncStateDao().get(tenant)!!
        assertEquals(10L, state.cursor)
        assertNotNull(state.offlineGrantUntil)
        assertEquals("APPROVED", db.fieldDataDao().job(fake.jobId)!!.status)
        assertEquals(1, db.fieldDataDao().snapshots(tenant).size)

        fake.cursor = 25
        fake.changesJobs = listOf(fake.job("IN_PROGRESS", 3))
        success(engine().sync(tenant))
        assertTrue(fake.requests.contains("GET /api/v1/sync/changes?cursor=10"))
        assertEquals(25L, db.syncStateDao().get(tenant)!!.cursor)
        assertEquals("IN_PROGRESS", db.fieldDataDao().job(fake.jobId)!!.status)

        fake.changesJobs = listOf(fake.job("APPROVED", 2)) // lookback replay of an older revision
        success(engine().sync(tenant))
        assertTrue(fake.requests.contains("GET /api/v1/sync/changes?cursor=25"))
        assertEquals("IN_PROGRESS", db.fieldDataDao().job(fake.jobId)!!.status)
    }

    @Test
    fun offlineCaptureIsQueuedThenPhotoUploadsBeforeTheCaptureIsAcked() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        assertEquals(PENDING, status(saved.operationId))

        val offline = engine(online = false).sync(tenant)
        assertTrue(offline is SyncReport.Retry)
        assertEquals(PENDING, status(saved.operationId)) // never marked synced without an ACK
        assertEquals(1, db.syncStateDao().get(tenant)!!.failureStreak)

        success(engine().sync(tenant))
        val acked = op(saved.operationId)
        assertEquals(ACKED, acked.status)
        assertEquals(0, db.syncStateDao().get(tenant)!!.failureStreak)
        val payload = json.parseToJsonElement(acked.payloadJson).jsonObject
        val attachmentId = payload["photo_attachment_id"]!!.jsonPrimitive.content
        assertEquals(fake.blobs.values.single().attachmentId, attachmentId)
        assertEquals(fake.tenantVersionId, payload["policy_version_ids"].toString().trim('[', ']', '"'))
        assertEquals("FIX", payload["gps"]!!.jsonObject["status"]!!.jsonPrimitive.content)
        assertEquals(listOf(0, 1, 2), fake.chunkPuts.map { it.second })
        val completeIndex = fake.requests.indexOfFirst { it.endsWith("/complete") }
        assertTrue(completeIndex < fake.requests.indexOf("POST /api/v1/sync/push"))
    }

    @Test
    fun lostResponseIsResolvedAsDuplicateWithExactlyOneEffect() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.failNextPushAfterApply = true
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        assertEquals(PENDING, status(saved.operationId))
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        assertEquals(1, fake.applied.count { it == saved.operationId })
        assertEquals(2, fake.pushedBatches.count { saved.operationId in it })
    }

    @Test
    fun deferredStaysPendingThenAcks() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.deferOnce += saved.operationId
        success(engine().sync(tenant))
        assertEquals(PENDING, status(saved.operationId))
        assertEquals("DEPENDENCY_PENDING", op(saved.operationId).errorCode)
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
    }

    @Test
    fun conflictIsSurfacedWithServerStateKeptAndNeverResent() = runBlocking {
        success(engine().sync(tenant))
        val captureOp = saved(capture(captureRequest())).operationId
        val start = workflow.transition(tenant, fake.jobId, JobWorkflow.START) as WorkflowResult.Done
        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == "JOB_TRANSITION") {
                "CONFLICT" to buildJsonObject {
                    put("error", fake.err("INVALID_JOB_TRANSITION"))
                    putJsonObject("server_state") { put("job_id", fake.jobId); put("job_status", "CANCELLED"); put("job_version", 4) }
                }
            } else null
        }
        success(engine().sync(tenant))
        assertEquals(ACKED, status(captureOp))
        val conflict = op(start.id)
        assertEquals(CONFLICT, conflict.status)
        assertEquals("INVALID_JOB_TRANSITION", conflict.errorCode)
        assertTrue(conflict.resultJson!!.contains("CANCELLED"))
        assertEquals(1, repository.observeCaptures(fake.jobId).first().size)
        val pushes = fake.pushedBatches.count { start.id in it }
        success(engine().sync(tenant))
        assertEquals(pushes, fake.pushedBatches.count { start.id in it }) // no automatic overwrite/resend
    }

    @Test
    fun rejectedIsFailedWithErrorCodeVisible() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.handler = { "REJECTED" to buildJsonObject { put("error", fake.err("VALIDATION_FAILED")) } }
        success(engine().sync(tenant))
        assertEquals(FAILED, status(saved.operationId))
        assertEquals("VALIDATION_FAILED", op(saved.operationId).errorCode)
        val problems = db.clientOperationDao().observeProblems(tenant).first()
        assertEquals(listOf(saved.operationId), problems.map { it.id })
    }

    @Test
    fun quarantinedWhileReadOnlyThenAppliedAfterReactivation() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.readOnly = true
        success(engine().sync(tenant))
        assertEquals(QUARANTINED, status(saved.operationId))
        assertEquals("SUBSCRIPTION_READ_ONLY", op(saved.operationId).errorCode)
        success(engine().sync(tenant)) // resent while still read-only: server replays DUPLICATE + read-only error
        assertEquals(QUARANTINED, status(saved.operationId))
        fake.readOnly = false
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        assertEquals(listOf(saved.operationId), fake.applied)
    }

    @Test
    fun deviceRevokedWipesLocalData() = runBlocking {
        success(engine().sync(tenant))
        saved(capture(captureRequest()))
        fake.revoked = true
        val report = engine().sync(tenant)
        assertTrue(report is SyncReport.Revoked)
        assertEquals(1, wipes.size)
        assertTrue(wipes.single().contains("revoked"))
    }

    @Test
    fun blobUploadResumesMissingChunksAndRestartsOnChecksumMismatch() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.failChunkOnce = 1
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        val attachment = db.evidenceDao().pendingAttachments(tenant, 10).single()
        assertEquals("0", attachment.receivedChunks)
        val firstSession = attachment.sessionId!!

        fake.checksumMismatchOnce = true
        success(engine().sync(tenant))
        val puts = fake.chunkPuts.map { it.first to it.second }
        // Resume sent only the missing chunks of the first session, then a fresh session re-sent all three.
        assertEquals(listOf(firstSession to 0, firstSession to 1, firstSession to 1, firstSession to 2), puts.take(4))
        val secondSession = puts.drop(4).map { it.first }.distinct().single()
        assertFalse(secondSession == firstSession)
        assertEquals(listOf(0, 1, 2), puts.drop(4).map { it.second })
        assertEquals(ACKED, status(saved.operationId))
    }

    @Test
    fun knownContentCompletesWithoutUploadingChunks() = runBlocking {
        success(engine().sync(tenant))
        saved(capture(captureRequest()))
        success(engine().sync(tenant))
        val putsBefore = fake.chunkPuts.size
        fake.changesJobs = listOf(fake.job("IN_PROGRESS", 3))
        success(engine().sync(tenant))
        val closing = saved(capture(captureRequest(ReadingKind.CLOSING, CaptureMode.MANUAL, "1240.0", ocr = null)))
        success(engine().sync(tenant))
        assertEquals(putsBefore, fake.chunkPuts.size) // same photo bytes: server dedupe returned COMPLETE
        assertEquals(ACKED, status(closing.operationId))
    }

    @Test
    fun inFlightOperationsRecoverAfterProcessDeath() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.deferOnce += saved.operationId
        success(engine().sync(tenant)) // photo uploaded, capture deferred
        assertEquals(1, db.clientOperationDao().markSent(saved.operationId)) // then the process is killed mid-push
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
    }

    @Test
    fun offlineWorkflowIsSentInDependencyOrder() = runBlocking {
        success(engine().sync(tenant))
        val opening = saved(capture(captureRequest())).operationId
        val start = (workflow.transition(tenant, fake.jobId, JobWorkflow.START) as WorkflowResult.Done).id
        val entry = (workflow.startEntry(tenant, fake.jobId, "WORK") as WorkflowResult.Done).id
        clock.advance(3_600_000)
        val activity = (workflow.stopEntry(tenant, entry) as WorkflowResult.Done).id
        val closing = saved(capture(captureRequest(ReadingKind.CLOSING, CaptureMode.MANUAL, "1236.0", photoBytes = null, ocr = null))).operationId
        val ack = (workflow.acknowledge(tenant, fake.jobId, AckMethod.SIGNATURE, "Jane Customer", null, byteArrayOf(1, 2, 3)) as WorkflowResult.Done).id
        val complete = (workflow.transition(tenant, fake.jobId, JobWorkflow.COMPLETE) as WorkflowResult.Done).id
        assertEquals(setOf(closing, ack, activity), db.clientOperationDao().dependenciesOf(complete).toSet())

        success(engine().sync(tenant))
        val all = listOf(opening, start, activity, closing, ack, complete)
        all.forEach { assertEquals(ACKED, status(it)) }
        val order = fake.applied.filter { it in all }
        fun before(a: String, b: String) = assertTrue("$a before $b", order.indexOf(a) < order.indexOf(b))
        // Server applied in workflow order: opening -> START -> {activity, closing} -> ack (after closing) -> COMPLETE.
        before(opening, start); before(start, activity); before(start, closing); before(closing, ack)
        before(ack, complete); before(activity, complete)
        val ackPayload = json.parseToJsonElement(op(ack).payloadJson).jsonObject
        assertNotNull(ackPayload["signature_attachment_id"]) // signature uploaded before the acknowledgement
        assertEquals(0, fake.stored.values.count { it.status == "DEFERRED" })
    }

    @Test
    fun consecutiveFailuresBackOffExponentially() = runBlocking {
        val first = engine(online = false).sync(tenant) as SyncReport.Retry
        val second = engine(online = false).sync(tenant) as SyncReport.Retry
        val third = engine(online = false).sync(tenant) as SyncReport.Retry
        assertTrue(first.retryAfterMs < second.retryAfterMs && second.retryAfterMs < third.retryAfterMs)
        assertEquals(3, db.syncStateDao().get(tenant)!!.failureStreak)
    }
}
