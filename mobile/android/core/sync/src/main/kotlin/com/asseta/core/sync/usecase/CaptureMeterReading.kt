package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.InboxRecordEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.MeterCaptureEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.capture.CaptureDraft
import com.asseta.core.domain.capture.CaptureValidator
import com.asseta.core.domain.capture.CaptureViolation
import com.asseta.core.domain.accountability.AccountabilityMessages
import com.asseta.core.domain.accountability.AccountabilityRules
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
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.BaselinePayload
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.CorrectionPayload
import com.asseta.core.model.sync.GpsIn
import com.asseta.core.model.sync.MeterCaptureIn
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.SyncMeterCaptureDto
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

/**
 * What a capture is for. [Job] is an opening/closing reading of a job (the default); [Daily] a DAILY reading outside a
 * job (METER_DAILY_READING); [Baseline] a proposed initial reading (METER_BASELINE); [Correction] the corrected reading
 * replacing one of my live readings (METER_CORRECTION). All share the same evidence rules (photo, OCR, fresh GPS).
 */
sealed interface CaptureTarget {
    data object Job : CaptureTarget
    data class Daily(val machineId: String) : CaptureTarget
    data class Baseline(val machineId: String, val note: String) : CaptureTarget
    data class Correction(val readingId: String, val reason: String) : CaptureTarget
}

/** One capture as produced by the capture screen. [captureId] is generated once per capture (idempotency key). */
data class CaptureRequest(
    val tenantId: String,
    /** The job of an opening/closing reading; null for the other [target]s. */
    val jobId: String?,
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
    val target: CaptureTarget = CaptureTarget.Job,
)

sealed interface CaptureResult {
    data class Saved(val captureId: String, val operationId: String) : CaptureResult
    data class Blocked(val message: String) : CaptureResult
    data class Invalid(val violations: List<CaptureViolation>) : CaptureResult
    data object AlreadySaved : CaptureResult
}

/** The machine, kind and job a capture is validated against (resolved from its target). */
data class CaptureSubject(val machine: MachineEntity, val kind: ReadingKind, val jobId: String?)

/**
 * Validates a capture against the locally enforced policy snapshot (same rules as the UI), then atomically stores the
 * encrypted photo reference, the local evidence row and the operation. A job reading waits for the photo upload
 * (attachment gate) and for its workflow parents (dependency chain); daily readings, baselines and corrections wait
 * only for their photo. The server applies every control (second person, baseline gate, overlaps).
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
    /** The machine/kind/job the capture is for, or why it cannot be recorded (also used by the screen when it opens). */
    suspend fun subject(tenantId: String, request: CaptureTargetRef): Pair<CaptureSubject?, String?> {
        val target = request.target
        val capability = when (target) {
            CaptureTarget.Job -> null
            is CaptureTarget.Daily -> SyncCapabilities.METER_DAILY_READING
            is CaptureTarget.Baseline -> SyncCapabilities.OP_METER_BASELINE
            is CaptureTarget.Correction -> SyncCapabilities.OP_METER_CORRECTION
        }
        if (capability != null) {
            val state = db().syncStateDao().get(tenantId)
            if (state?.capabilities == null) return null to NEEDS_SYNC
            if (!state.supports(capability)) return null to SERVER_TOO_OLD
        }
        return when (target) {
            CaptureTarget.Job -> {
                val job = request.jobId?.let { repository.job(it) } ?: return null to JOB_GONE
                val machine = repository.machine(job.machineId) ?: return null to MACHINE_DETAILS_MISSING
                val state = repository.fieldState(tenantId, job)
                if (!JobStateRules.readingAllowed(request.kind, state.effectiveStatus)) {
                    return null to "A ${request.kind.name.lowercase()} reading is not allowed while the job is ${state.effectiveStatus}."
                }
                CaptureSubject(machine, request.kind, job.id) to null
            }
            is CaptureTarget.Daily -> machineOnly(target.machineId)?.let { CaptureSubject(it, ReadingKind.DAILY, null) to null }
                ?: (null to MACHINE_MISSING)
            is CaptureTarget.Baseline -> machineOnly(target.machineId)?.let { CaptureSubject(it, ReadingKind.DAILY, null) to null }
                ?: (null to MACHINE_MISSING)
            is CaptureTarget.Correction -> {
                val old = serverReading(tenantId, target.readingId) ?: return null to CORRECTION_NOT_SYNCED
                if (old.state !in LIVE_STATES) return null to CORRECTION_NOT_LIVE
                val machine = repository.machine(old.machineId) ?: return null to MACHINE_MISSING
                val kind = runCatching { ReadingKind.valueOf(old.kind) }.getOrNull() ?: return null to CORRECTION_NOT_LIVE
                CaptureSubject(machine, kind, old.jobId) to null
            }
        }
    }

    suspend operator fun invoke(request: CaptureRequest): CaptureResult {
        val (subject, refusal) = subject(request.tenantId, CaptureTargetRef(request.jobId, request.kind, request.target))
        if (subject == null) return CaptureResult.Blocked(refusal ?: MACHINE_MISSING)
        val machine = subject.machine
        val target = request.target
        if (target is CaptureTarget.Correction && !AccountabilityRules.correctionReasonValid(target.reason)) {
            return CaptureResult.Blocked(AccountabilityMessages.CORRECTION_REASON)
        }
        val decision = repository.capturePolicy(request.tenantId, machine.id)
        if (decision is CapturePolicyDecision.Blocked) return CaptureResult.Blocked(decision.message)
        decision as CapturePolicyDecision.Allowed
        val draft = CaptureDraft(
            subject.kind, request.mode, request.readingText, request.photoJpeg != null,
            request.ocrAttempts, request.latestOcr, request.gps != null,
        )
        val violations = CaptureValidator.validate(draft, decision.policy, machine.meterDecimalPlaces)
        if (violations.isNotEmpty()) return CaptureResult.Invalid(violations)
        val reading = (ReadingValidator.validate(request.readingText, machine.meterDecimalPlaces) as ReadingInput.Valid).normalized
        val gps = request.gps!!

        val database = db()
        if (alreadySaved(request, target)) return CaptureResult.AlreadySaved
        val photoFile = request.photoJpeg?.let { files.write(it) }
        val attachmentId = photoFile?.let { UUID.randomUUID().toString() }
        val ocr = request.latestOcr.takeIf { request.mode == CaptureMode.AUTOMATIC }
        val payload = MeterCaptureIn(
            id = request.captureId,
            jobId = subject.jobId,
            kind = subject.kind.name,
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
            machineId = if (subject.jobId == null) machine.id else null,
        )
        return database.inTransaction {
            if (photoFile != null && attachmentId != null) {
                val bytes = request.photoJpeg
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(attachmentId, request.tenantId, BlobPurpose.METER_PHOTO, photoFile, Sha256.hex(bytes),
                        bytes.size.toLong(), "image/jpeg", AttachmentEntity.PENDING, createdAt = request.capturedAtMs),
                )
            }
            val attachments = listOfNotNull(attachmentId)
            val opId = when (target) {
                CaptureTarget.Job -> {
                    val jobId = subject.jobId!!
                    val kind = if (subject.kind == ReadingKind.OPENING) JobOpKind.OPENING_CAPTURE else JobOpKind.CLOSING_CAPTURE
                    val id = outbox.enqueue(
                        request.tenantId, jobId, kind, FieldOps.captureEntityType(subject.kind), request.captureId,
                        json.encodeToJsonElement(MeterCaptureIn.serializer(), payload).jsonObject, attachmentId,
                    )
                    val fix = gps as? GpsOutcome.Fix
                    database.evidenceDao().insertCapture(
                        MeterCaptureEntity(
                            id = request.captureId, tenantId = request.tenantId, jobId = jobId, kind = subject.kind.name,
                            captureMode = request.mode.name, reading = reading, ocrValue = ocr?.value, ocrRawText = ocr?.rawText,
                            ocrConfidence = ocr?.confidence, photoAttachmentLocalId = attachmentId, gpsStatus = gps.status,
                            latitude = fix?.latitude, longitude = fix?.longitude, accuracyM = fix?.accuracyM,
                            gpsCapturedAt = fix?.capturedAt?.toEpochMilli(), gpsProvider = fix?.provider,
                            capturedAt = request.capturedAtMs,
                            policyVersionIdsJson = json.encodeToString(ListSerializer(String.serializer()), decision.snapshot.versionIds),
                            operationId = id,
                        ),
                    )
                    id
                }
                is CaptureTarget.Daily -> outbox.enqueueOperation(
                    request.tenantId, OpTypes.METER_CAPTURE, FieldOps.captureEntityType(ReadingKind.DAILY), request.captureId,
                    json.encodeToJsonElement(MeterCaptureIn.serializer(), payload).jsonObject, attachments,
                )
                is CaptureTarget.Baseline -> outbox.enqueueOperation(
                    request.tenantId, AccountabilityOps.METER_BASELINE, FieldOps.BASELINE, request.captureId,
                    json.encodeToJsonElement(
                        BaselinePayload.serializer(),
                        BaselinePayload(
                            id = request.captureId, machineId = machine.id, reading = reading, capturedAt = payload.capturedAt,
                            deviceId = payload.deviceId, gps = payload.gps, note = target.note.trim().take(NOTE_MAX).ifEmpty { null },
                        ),
                    ).jsonObject,
                    attachments,
                )
                is CaptureTarget.Correction -> outbox.enqueueOperation(
                    request.tenantId, AccountabilityOps.METER_CORRECTION, FieldOps.CORRECTION, request.captureId,
                    json.encodeToJsonElement(
                        CorrectionPayload.serializer(),
                        CorrectionPayload(target.readingId, target.reason.trim().take(REASON_MAX), payload),
                    ).jsonObject,
                    attachments,
                )
            }
            CaptureResult.Saved(request.captureId, opId)
        }.also { onQueued() }
    }

    private suspend fun alreadySaved(request: CaptureRequest, target: CaptureTarget): Boolean {
        val dao = db().clientOperationDao()
        return when (target) {
            CaptureTarget.Job -> dao.forJob(request.tenantId, repository.ownerSubject(), request.jobId!!).any { it.entityId == request.captureId }
            is CaptureTarget.Daily -> dao.findByEntity(request.tenantId, FieldOps.captureEntityType(ReadingKind.DAILY), request.captureId) != null
            is CaptureTarget.Baseline -> dao.findByEntity(request.tenantId, FieldOps.BASELINE, request.captureId) != null
            is CaptureTarget.Correction -> dao.findByEntity(request.tenantId, FieldOps.CORRECTION, request.captureId) != null
        }
    }

    private suspend fun machineOnly(machineId: String): MachineEntity? = repository.machine(machineId)

    /** My reading as the server has it (supervisor inbox), needed to correct it. */
    private suspend fun serverReading(tenantId: String, id: String): SyncMeterCaptureDto? =
        db().inboxDao().kind(tenantId, InboxRecordEntity.METER_CAPTURE).firstOrNull { it.id == id }
            ?.let { runCatching { json.decodeFromString(SyncMeterCaptureDto.serializer(), it.json) }.getOrNull() }

    companion object {
        const val OCR_ENGINE = "mlkit-text-latin-16.0.1/spec-${MeterReadingParser.SPEC_VERSION}"
        const val JOB_GONE = "This job is no longer assigned to you."
        const val MACHINE_DETAILS_MISSING = "Machine details are missing. Connect to refresh."
        const val NEEDS_SYNC = "Sync once while online before recording this."
        const val SERVER_TOO_OLD = "Your company's server does not accept this from the app yet."
        const val MACHINE_MISSING = "This machine is not on this device."
        const val CORRECTION_NOT_SYNCED = "A reading can be corrected once the server has it."
        const val CORRECTION_NOT_LIVE = "Only a reading the server still counts can be corrected."
        private const val NOTE_MAX = 2000
        private const val REASON_MAX = 2000

        /** Server capture states a correction may replace (`LIVE`). */
        val LIVE_STATES = setOf("PROVISIONAL", "ACCEPTED")
    }
}

/** The part of a [CaptureRequest] that decides what is being read (the screen resolves it when it opens). */
data class CaptureTargetRef(val jobId: String?, val kind: ReadingKind, val target: CaptureTarget)

/** Wire form of the GPS attempt: coordinates only for a real FIX. */
fun GpsOutcome.toWire(): GpsIn = when (this) {
    is GpsOutcome.Fix -> GpsIn(status, latitude, longitude, accuracyM, capturedAt.toString(), provider?.take(32))
    else -> GpsIn(status)
}
