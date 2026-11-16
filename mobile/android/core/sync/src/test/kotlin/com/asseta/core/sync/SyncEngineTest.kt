package com.asseta.core.sync

import com.asseta.core.database.AttachmentEntity
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.ClientOperationStatus.FAILED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.ClientOperationStatus.QUARANTINED
import com.asseta.core.model.sync.MachineReportOps
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.engine.SyncReport
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class SyncEngineTest : SyncTestBase() {

    /** A machine report queued after (and depending on) the reading [captureOp]; its operation id. */
    private fun report(captureOp: String): String = runBlocking {
        FieldOutbox({ db }, json, clock, { account }).enqueueOperation(
            tenant, MachineReportOps.MACHINE_REPORT, FieldOps.MACHINE_REPORT, "r-$captureOp", JsonObject(emptyMap()), dependsOn = listOf(captureOp),
        )
    }

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
        assertEquals("ACTIVE", db.fieldDataDao().machine(fake.machineId)!!.status)
        assertEquals(setOf("METER_CAPTURE", "EXPENSE_CAPTURE"), db.fieldDataDao().snapshots(tenant).map { it.policyType }.toSet())

        fake.cursor = 25
        fake.changesMachines = listOf(fake.machine("UNDER_MAINTENANCE", 3))
        success(engine().sync(tenant))
        assertTrue(fake.requests.contains("GET /api/v1/sync/changes?cursor=10"))
        assertEquals(25L, db.syncStateDao().get(tenant)!!.cursor)
        assertEquals("UNDER_MAINTENANCE", db.fieldDataDao().machine(fake.machineId)!!.status)

        fake.changesMachines = listOf(fake.machine("ACTIVE", 2)) // lookback replay of an older revision
        success(engine().sync(tenant))
        assertTrue(fake.requests.contains("GET /api/v1/sync/changes?cursor=25"))
        assertEquals("UNDER_MAINTENANCE", db.fieldDataDao().machine(fake.machineId)!!.status)
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
        val report = report(captureOp)
        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == MachineReportOps.MACHINE_REPORT) {
                "CONFLICT" to buildJsonObject {
                    put("error", fake.err("REPORT_PENDING"))
                    putJsonObject("server_state") { put("machine_id", fake.machineId); put("pending_report_number", "MR-2026-00009") }
                }
            } else null
        }
        success(engine().sync(tenant))
        assertEquals(ACKED, status(captureOp))
        val conflict = op(report)
        assertEquals(CONFLICT, conflict.status)
        assertEquals("REPORT_PENDING", conflict.errorCode)
        assertTrue(conflict.resultJson!!.contains("MR-2026-00009"))
        val pushes = fake.pushedBatches.count { report in it }
        success(engine().sync(tenant))
        assertEquals(pushes, fake.pushedBatches.count { report in it }) // no automatic overwrite/resend
    }

    @Test
    fun rejectedIsFailedWithErrorCodeVisible() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        fake.handler = { "REJECTED" to buildJsonObject { put("error", fake.err("VALIDATION_FAILED")) } }
        success(engine().sync(tenant))
        assertEquals(FAILED, status(saved.operationId))
        assertEquals("VALIDATION_FAILED", op(saved.operationId).errorCode)
        val problems = db.clientOperationDao().observeProblems(tenant, USER_A.subject).first()
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
        val second = saved(capture(captureRequest(reading = "1240.0", ocr = OcrReading("1240.0", 0.95, "1240.0", "OK", emptySet()))))
        success(engine().sync(tenant))
        assertEquals(putsBefore, fake.chunkPuts.size) // same photo bytes: server dedupe returned COMPLETE
        assertEquals(ACKED, status(second.operationId))
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
    fun aReportIsSentAfterItsReadingAndItsPhoto() = runBlocking {
        success(engine().sync(tenant))
        val reading = saved(capture(captureRequest())).operationId
        val report = report(reading)
        assertEquals(listOf(reading), db.clientOperationDao().dependenciesOf(report))

        success(engine().sync(tenant))
        assertEquals(ACKED, status(reading))
        assertEquals(ACKED, status(report))
        val order = fake.applied.filter { it == reading || it == report }
        assertEquals(listOf(reading, report), order)
        assertNotNull(json.parseToJsonElement(op(reading).payloadJson).jsonObject["photo_attachment_id"]) // photo before the reading
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

    @Test
    fun nextAutomaticRetryIsTheBackoffTimeAndClearedBySuccess() = runBlocking {
        val failed = engine(online = false).sync(tenant) as SyncReport.Retry
        assertEquals(clock.now + failed.retryAfterMs, db.syncStateDao().get(tenant)!!.nextSyncAt)
        val again = engine(online = false).sync(tenant) as SyncReport.Retry
        assertEquals(clock.now + again.retryAfterMs, repository.observeSyncState(tenant).first()!!.nextSyncAt)
        success(engine().sync(tenant))
        assertNull(db.syncStateDao().get(tenant)!!.nextSyncAt)
    }

    @Test
    fun missingEvidenceIsMarkedFailedForGoodAndItsCaptureIsNeverSent() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(capture(captureRequest()))
        val attachment = db.evidenceDao().pendingAttachments(tenant, 10).single()
        files.delete(attachment.fileName)
        success(engine().sync(tenant)) // the rest of the sync goes on
        val failed = db.evidenceDao().attachment(attachment.id)!!
        assertEquals(AttachmentEntity.FAILED, failed.status)
        assertEquals("LOCAL_EVIDENCE_UNAVAILABLE: file missing", failed.lastError)
        assertEquals(listOf(attachment.id), repository.observeFailedUploads(tenant).first().map { it.id })
        assertEquals(0, repository.observePendingUploads(tenant).first())
        success(engine().sync(tenant))
        assertEquals(PENDING, status(saved.operationId))
        assertTrue(fake.pushedBatches.none { saved.operationId in it })
        assertTrue(fake.requests.none { it == "POST /api/v1/sync/blobs" }) // never retried
    }

    @Test
    fun changedEvidenceAndFileTooLargeAreMarkedFailed() = runBlocking {
        success(engine().sync(tenant))
        saved(capture(captureRequest()))
        val changed = db.evidenceDao().pendingAttachments(tenant, 10).single()
        db.evidenceDao().insertAttachment(changed.copy(id = "copy", fileName = files.write(byteArrayOf(9, 9, 9))))
        fake.startBlobErrors += 413 to "FILE_TOO_LARGE"
        success(engine().sync(tenant))
        assertEquals("FILE_TOO_LARGE", db.evidenceDao().attachment(changed.id)!!.lastError)
        assertEquals("LOCAL_EVIDENCE_UNAVAILABLE: file changed", db.evidenceDao().attachment("copy")!!.lastError)
        assertEquals(setOf(AttachmentEntity.FAILED), repository.observeFailedUploads(tenant).first().map { it.status }.toSet())
        assertEquals(2, repository.observeFailedUploads(tenant).first().size)
    }
}
