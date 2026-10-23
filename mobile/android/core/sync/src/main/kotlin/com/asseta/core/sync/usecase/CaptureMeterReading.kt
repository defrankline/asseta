package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.MeterCaptureEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.capture.CaptureDraft
import com.asseta.core.domain.capture.CaptureValidator
import com.asseta.core.domain.capture.CaptureViolation
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.JobStateRules
import com.asseta.core.domain.capture.ReadingInput
import com.asseta.core.domain.capture.ReadingValidator
import com.asseta.core.domain.ocr.MeterReadingParser
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.sync.JobOpKind
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.GpsIn
import com.asseta.core.model.sync.MeterCaptureIn
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.util.UUID

/** One capture as produced by the capture screen. [captureId] is generated once per capture (idempotency key). */
data class CaptureRequest(
    val tenantId: String,
    val jobId: String,
    val captureId: String,
    val kind: ReadingKind,
    val mode: CaptureMode,
    val readingText: String,
    /** Original JPEG bytes exactly as delivered by the camera (never re-encoded). */
    val photoJpeg: ByteArray?,
    val ocrAttempts: Int,
    val latestOcr: OcrReading?,
    val gps: GpsOutcome?,
    val capturedAtMs: Long,
)

sealed interface CaptureResult {
    data class Saved(val captureId: String, val operationId: String) : CaptureResult
    data class Blocked(val message: String) : CaptureResult
    data class Invalid(val violations: List<CaptureViolation>) : CaptureResult
    data object AlreadySaved : CaptureResult
}

/**
 * Validates a capture against the locally enforced policy snapshot (same rules as the UI), then atomically stores the
 * encrypted photo reference, the local evidence row and the METER_CAPTURE operation. The operation waits for the photo
 * upload (attachment gate) and for its workflow parents (dependency chain).
 */
class CaptureMeterReading(
    private val db: () -> AssetaDatabase,
    private val repository: FieldRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val deviceId: () -> String,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    suspend operator fun invoke(request: CaptureRequest): CaptureResult {
        val job = repository.job(request.jobId) ?: return CaptureResult.Blocked("This job is no longer assigned to you.")
        val machine = repository.machine(job.machineId)
            ?: return CaptureResult.Blocked("Machine details are missing. Connect to refresh.")
        val state = repository.fieldState(request.tenantId, job)
        if (!JobStateRules.readingAllowed(request.kind, state.effectiveStatus)) {
            return CaptureResult.Blocked("A ${request.kind.name.lowercase()} reading is not allowed while the job is ${state.effectiveStatus}.")
        }
        val decision = repository.capturePolicy(request.tenantId, machine.id)
        if (decision is CapturePolicyDecision.Blocked) return CaptureResult.Blocked(decision.message)
        decision as CapturePolicyDecision.Allowed
        val draft = CaptureDraft(
            request.kind, request.mode, request.readingText, request.photoJpeg != null,
            request.ocrAttempts, request.latestOcr, request.gps != null,
        )
        val violations = CaptureValidator.validate(draft, decision.policy, machine.meterDecimalPlaces)
        if (violations.isNotEmpty()) return CaptureResult.Invalid(violations)
        val reading = (ReadingValidator.validate(request.readingText, machine.meterDecimalPlaces) as ReadingInput.Valid).normalized
        val gps = request.gps!!

        val database = db()
        if (database.clientOperationDao().forJob(request.tenantId, repository.ownerSubject(), request.jobId).any { it.entityId == request.captureId }) {
            return CaptureResult.AlreadySaved
        }
        val photoFile = request.photoJpeg?.let { files.write(it) }
        val attachmentId = photoFile?.let { UUID.randomUUID().toString() }
        val ocr = request.latestOcr.takeIf { request.mode == CaptureMode.AUTOMATIC }
        val payload = MeterCaptureIn(
            id = request.captureId,
            jobId = request.jobId,
            kind = request.kind.name,
            captureMode = request.mode.name,
            reading = reading,
            ocrRawText = ocr?.rawText?.take(500),
            ocrValue = ocr?.value,
            ocrConfidence = ocr?.confidence,
            ocrEngine = ocr?.let { OCR_ENGINE },
            photoAttachmentId = null, // filled in when the upload completes, before the op is ever sent
            gps = gps.toWire(),
            deviceId = deviceId(),
            capturedAt = IsoTime.format(request.capturedAtMs),
            policyVersionIds = decision.snapshot.versionIds,
        )
        return database.inTransaction {
            if (photoFile != null && attachmentId != null) {
                val bytes = request.photoJpeg
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(attachmentId, request.tenantId, BlobPurpose.METER_PHOTO, photoFile, Sha256.hex(bytes),
                        bytes.size.toLong(), "image/jpeg", AttachmentEntity.PENDING, createdAt = request.capturedAtMs),
                )
            }
            val kind = if (request.kind == ReadingKind.OPENING) JobOpKind.OPENING_CAPTURE else JobOpKind.CLOSING_CAPTURE
            val opId = outbox.enqueue(
                request.tenantId, request.jobId, kind, FieldOps.captureEntityType(request.kind), request.captureId,
                json.encodeToJsonElement(MeterCaptureIn.serializer(), payload).jsonObject, attachmentId,
            )
            val fix = gps as? GpsOutcome.Fix
            database.evidenceDao().insertCapture(
                MeterCaptureEntity(
                    id = request.captureId, tenantId = request.tenantId, jobId = request.jobId, kind = request.kind.name,
                    captureMode = request.mode.name, reading = reading, ocrValue = ocr?.value, ocrRawText = ocr?.rawText,
                    ocrConfidence = ocr?.confidence, photoAttachmentLocalId = attachmentId, gpsStatus = gps.status,
                    latitude = fix?.latitude, longitude = fix?.longitude, accuracyM = fix?.accuracyM,
                    gpsCapturedAt = fix?.capturedAt?.toEpochMilli(), gpsProvider = fix?.provider,
                    capturedAt = request.capturedAtMs,
                    policyVersionIdsJson = json.encodeToString(ListSerializer(String.serializer()), decision.snapshot.versionIds),
                    operationId = opId,
                ),
            )
            CaptureResult.Saved(request.captureId, opId)
        }.also { onQueued() }
    }

    companion object {
        const val OCR_ENGINE = "mlkit-text-latin-16.0.1/spec-${MeterReadingParser.SPEC_VERSION}"
    }
}

/** Wire form of the GPS attempt: coordinates only for a real FIX. */
fun GpsOutcome.toWire(): GpsIn = when (this) {
    is GpsOutcome.Fix -> GpsIn(status, latitude, longitude, accuracyM, capturedAt.toString(), provider?.take(32))
    else -> GpsIn(status)
}
