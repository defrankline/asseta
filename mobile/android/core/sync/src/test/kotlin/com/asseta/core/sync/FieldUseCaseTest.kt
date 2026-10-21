package com.asseta.core.sync

import com.asseta.core.domain.capture.CaptureViolation
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.evidence.Sha256
import com.asseta.core.sync.usecase.CaptureResult
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.usecase.WorkflowResult
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@RunWith(RobolectricTestRunner::class)
class FieldUseCaseTest : SyncTestBase() {

    private fun bootstrap() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    @Test
    fun noRulesYetBlocksCapture() = runBlocking {
        val result = capture(captureRequest())
        assertTrue(result is CaptureResult.Blocked) // no job/snapshot downloaded yet
    }

    @Test
    fun expiredSnapshotOrOfflineGrantBlocksNewCaptures() = runBlocking {
        fake.snapshotValidHours = 1
        bootstrap()
        clock.advance(2 * 3_600_000)
        val expired = capture(captureRequest()) as CaptureResult.Blocked
        assertTrue(expired.message.startsWith("Connect to refresh rules"))
        assertTrue(expired.message.contains("expired"))

        fake.snapshotValidHours = 500
        bootstrap()
        clock.advance(73 * 3_600_000L) // offline grant is 72 h
        val grant = capture(captureRequest()) as CaptureResult.Blocked
        assertTrue(grant.message.contains("offline longer than allowed"))
    }

    @Test
    fun requiredModeAndPhotoAreEnforced() = runBlocking {
        bootstrap()
        val manual = capture(captureRequest(mode = CaptureMode.MANUAL, ocr = null)) as CaptureResult.Invalid
        assertEquals(listOf(CaptureViolation.MODE_NOT_ALLOWED), manual.violations)
        val noPhoto = capture(captureRequest(photoBytes = null)) as CaptureResult.Invalid
        assertTrue(CaptureViolation.PHOTO_REQUIRED in noPhoto.violations)
        val lowConfidence = OcrReading("1234.5", 0.4, "1234.5", "OK", emptySet())
        val recapture = capture(captureRequest(ocr = lowConfidence, attempts = 1)) as CaptureResult.Invalid
        assertEquals(listOf(CaptureViolation.RECAPTURE_REQUIRED), recapture.violations)
        val closingTooEarly = capture(captureRequest(ReadingKind.CLOSING, CaptureMode.MANUAL, ocr = null))
        assertTrue(closingTooEarly is CaptureResult.Blocked)
    }

    @Test
    fun gpsFailureIsRecordedWithoutCoordinates() = runBlocking {
        bootstrap()
        val saved = saved(capture(captureRequest(gps = GpsOutcome.PermissionDenied)))
        val gps = json.parseToJsonElement(op(saved.operationId).payloadJson).jsonObject["gps"]!!.jsonObject
        assertEquals("PERMISSION_DENIED", gps["status"]!!.jsonPrimitive.content)
        assertEquals(setOf("status"), gps.keys)
        val missing = capture(captureRequest(gps = null)) as CaptureResult.Invalid
        assertEquals(listOf(CaptureViolation.GPS_NOT_ATTEMPTED), missing.violations)
    }

    @Test
    fun manualCorrectionKeepsOcrEvidenceAndPhotoIsEncryptedAtRest() = runBlocking {
        bootstrap()
        val ocr = OcrReading("1234.5", 0.93, "12:45 1234.5 HRS", "OK", emptySet())
        val saved = saved(capture(captureRequest(reading = "1284.5", ocr = ocr)))
        val payload = json.parseToJsonElement(op(saved.operationId).payloadJson).jsonObject
        assertEquals("1284.5", payload["reading"]!!.jsonPrimitive.content)
        assertEquals("1234.5", payload["ocr_value"]!!.jsonPrimitive.content)
        assertEquals("12:45 1234.5 HRS", payload["ocr_raw_text"]!!.jsonPrimitive.content)
        assertEquals(saved.captureId, payload["id"]!!.jsonPrimitive.content)
        assertEquals(DEVICE, payload["device_id"]!!.jsonPrimitive.content)
        assertNull(payload["photo_attachment_id"]) // set only once the upload completes

        val attachment = db.evidenceDao().pendingAttachments(tenant, 1).single()
        assertEquals(Sha256.hex(photo), attachment.sha256)
        val onDisk = File(tmp.root, "evidence/${attachment.fileName}").readBytes()
        assertFalse(onDisk.toList().windowed(photo.size).any { it == photo.toList() })
        assertArrayEquals(photo, files.read(attachment.fileName)) // original bytes, unmodified

        assertEquals(CaptureResult.AlreadySaved, capture(captureRequest().copy(captureId = saved.captureId)))
    }

    @Test
    fun workflowGuardsFollowLocalState() = runBlocking {
        bootstrap()
        assertTrue(workflow.transition(tenant, fake.jobId, JobWorkflow.START) is WorkflowResult.Refused)
        saved(capture(captureRequest()))
        assertTrue(workflow.transition(tenant, fake.jobId, JobWorkflow.START) is WorkflowResult.Done)
        assertTrue(workflow.transition(tenant, fake.jobId, JobWorkflow.START) is WorkflowResult.Refused)
        val entry = workflow.startEntry(tenant, fake.jobId, "DOWNTIME", "hydraulic leak") as WorkflowResult.Done
        assertTrue(workflow.startEntry(tenant, fake.jobId, "WORK") is WorkflowResult.Refused) // one running entry
        assertTrue(workflow.addNote(tenant, fake.jobId, "Waiting for fitter") is WorkflowResult.Done)
        saved(capture(captureRequest(ReadingKind.CLOSING, CaptureMode.MANUAL, "1240.0", photoBytes = null, ocr = null)))
        assertTrue(workflow.acknowledge(tenant, fake.jobId, "SIGNATURE", "Jane", null, null) is WorkflowResult.Refused)
        assertTrue(workflow.acknowledge(tenant, fake.jobId, "NAME_CONFIRMATION", "Jane", "+260", null) is WorkflowResult.Done)
        assertTrue(workflow.transition(tenant, fake.jobId, JobWorkflow.COMPLETE) is WorkflowResult.Refused) // entry running
        workflow.stopEntry(tenant, entry.id)
        assertTrue(workflow.transition(tenant, fake.jobId, JobWorkflow.COMPLETE) is WorkflowResult.Done)
    }

    @Test
    fun clockTamperIsDetectedAgainstLastServerTime() = runBlocking {
        bootstrap()
        val state = db.syncStateDao().get(tenant)
        assertEquals(ClockStatus.Checked(0, false), repository.clockStatus(state))
        clock.now += 10 * 60_000 // wall clock moved forward 10 min without monotonic time passing
        assertEquals(ClockStatus.Checked(600, true), repository.clockStatus(state))
        assertEquals(ClockStatus.Unknown, repository.clockStatus(null))
    }
}
