package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.WorkLogEntryEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.capture.JobStateRules
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.finance.AmountInput
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.sync.JobOpKind
import com.asseta.core.model.sync.AckMethod
import com.asseta.core.model.sync.AcknowledgementPayload
import com.asseta.core.model.sync.ActivityPayload
import com.asseta.core.model.sync.ActivityTypes
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.JobTransitionPayload
import com.asseta.core.sync.SyncClock
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.util.UUID

sealed interface WorkflowResult {
    data class Done(val id: String) : WorkflowResult
    data class Refused(val message: String) : WorkflowResult
}

/**
 * Work log (start/stop/downtime/standby/note), customer acknowledgement and job START/COMPLETE. Every action is
 * stored offline first and queued in the outbox with its dependency chain; the server re-validates on sync.
 */
class JobWorkflow(
    private val db: () -> AssetaDatabase,
    private val repository: FieldRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val deviceId: () -> String,
    private val clock: SyncClock,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    /**
     * Starts a timed WORK/STANDBY/DOWNTIME/MOBILIZATION entry (local until stopped). One open entry per job.
     * [startedAtMs] backdates the start (work log entry form); default now.
     */
    suspend fun startEntry(
        tenantId: String,
        jobId: String,
        activityType: String,
        note: String? = null,
        startedAtMs: Long? = null,
    ): WorkflowResult {
        require(activityType != ActivityTypes.NOTE) { "Notes are recorded with addNote" }
        refuseUnlessLoggable(tenantId, jobId)?.let { return it }
        val evidence = db().evidenceDao()
        if (evidence.observeWorkLog(jobId, repository.ownerSubject()).first().any { it.operationId == null }) {
            return WorkflowResult.Refused("Stop the running entry first.")
        }
        val startedAt = startedAtMs ?: clock.nowMs()
        val entry = WorkLogEntryEntity(UUID.randomUUID().toString(), tenantId, jobId, activityType, startedAt, null, note.clean(),
            null, ownerSub = repository.ownerSubject())
        evidence.insertWorkLog(entry)
        return WorkflowResult.Done(entry.clientId)
    }

    /** A finished entry entered after the fact (work log entry form), queued immediately. [billable] null = contract default. */
    suspend fun addEntry(
        tenantId: String,
        jobId: String,
        activityType: String,
        startedAtMs: Long,
        endedAtMs: Long,
        billable: Boolean?,
        note: String?,
    ): WorkflowResult {
        require(activityType != ActivityTypes.NOTE) { "Notes are recorded with addNote" }
        if (endedAtMs < startedAtMs) return WorkflowResult.Refused("The end time is before the start time.")
        refuseUnlessLoggable(tenantId, jobId)?.let { return it }
        val database = db()
        val entry = WorkLogEntryEntity(UUID.randomUUID().toString(), tenantId, jobId, activityType, startedAtMs, endedAtMs, note.clean(),
            null, ownerSub = repository.ownerSubject())
        return database.inTransaction {
            database.evidenceDao().insertWorkLog(entry)
            val opId = queueActivity(tenantId, entry, billable)
            database.evidenceDao().closeWorkLog(entry.clientId, endedAtMs, opId)
            WorkflowResult.Done(opId)
        }.also { onQueued() }
    }

    /** Stops an open entry and queues exactly one JOB_ACTIVITY operation for it. */
    suspend fun stopEntry(tenantId: String, clientId: String): WorkflowResult {
        val database = db()
        val entry = database.evidenceDao().workLog(clientId)?.takeIf { it.ownerSub == repository.ownerSubject() }
            ?: return WorkflowResult.Refused("Entry not found.")
        if (entry.operationId != null) return WorkflowResult.Refused("This entry is already stopped.")
        val endedAt = maxOf(clock.nowMs(), entry.startedAt)
        return database.inTransaction {
            val opId = queueActivity(tenantId, entry.copy(endedAt = endedAt))
            database.evidenceDao().closeWorkLog(clientId, endedAt, opId)
            WorkflowResult.Done(opId)
        }.also { onQueued() }
    }

    /** A free-text note (activity type NOTE), queued immediately. [atMs] backdates it (work log entry form). */
    suspend fun addNote(tenantId: String, jobId: String, text: String, atMs: Long? = null): WorkflowResult {
        val note = text.trim()
        if (note.isEmpty()) return WorkflowResult.Refused("Write a note first.")
        refuseUnlessLoggable(tenantId, jobId)?.let { return it }
        val database = db()
        val entry = WorkLogEntryEntity(UUID.randomUUID().toString(), tenantId, jobId, ActivityTypes.NOTE, atMs ?: clock.nowMs(), null, note.take(2000),
            null, ownerSub = repository.ownerSubject())
        return database.inTransaction {
            database.evidenceDao().insertWorkLog(entry)
            val opId = queueActivity(tenantId, entry)
            database.evidenceDao().closeWorkLog(entry.clientId, null, opId)
            WorkflowResult.Done(opId)
        }.also { onQueued() }
    }

    /** NAME_CONFIRMATION, or SIGNATURE with the signature pad PNG (uploaded as a SIGNATURE blob before the op is sent). */
    suspend fun acknowledge(
        tenantId: String,
        jobId: String,
        method: String,
        signerName: String,
        signerPhone: String?,
        signaturePng: ByteArray?,
        acknowledgedHours: String? = null,
    ): WorkflowResult {
        val job = repository.job(jobId) ?: return WorkflowResult.Refused("Job not found.")
        val state = repository.fieldState(tenantId, job)
        val name = signerName.trim()
        when {
            state.effectiveStatus != JobStatus.IN_PROGRESS -> return WorkflowResult.Refused("Acknowledgement is taken on a running job.")
            !state.hasClosing -> return WorkflowResult.Refused("Capture the closing reading first.")
            name.isEmpty() || name.length > 200 -> return WorkflowResult.Refused("Enter the customer's name.")
            method == AckMethod.SIGNATURE && (signaturePng == null || signaturePng.isEmpty()) ->
                return WorkflowResult.Refused("The customer must sign.")
            method != AckMethod.SIGNATURE && method != AckMethod.NAME_CONFIRMATION -> return WorkflowResult.Refused("Unknown method.")
        }
        val hours = acknowledgedHours?.trim()?.takeIf { it.isNotEmpty() }?.let {
            (AmountParser.parse(it, DecimalLimit.METER_READING, allowZero = true) as? AmountInput.Valid)?.value?.toPlainString()
                ?: return WorkflowResult.Refused("Hours must be a number with at most 2 decimals.")
        }
        val clientId = UUID.randomUUID().toString()
        val now = clock.nowMs()
        val png = signaturePng.takeIf { method == AckMethod.SIGNATURE }
        val file = png?.let { files.write(it) }
        val attachmentId = file?.let { UUID.randomUUID().toString() }
        val payload = AcknowledgementPayload(
            jobId = jobId, clientId = clientId, method = method, signerName = name,
            signerPhone = signerPhone?.trim()?.takeIf { it.isNotEmpty() }?.take(40), acknowledgedHours = hours,
            capturedAt = IsoTime.format(now),
        )
        val database = db()
        return database.inTransaction {
            if (png != null && file != null && attachmentId != null) {
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(attachmentId, tenantId, BlobPurpose.SIGNATURE, file, Sha256.hex(png), png.size.toLong(),
                        "image/png", AttachmentEntity.PENDING, createdAt = now),
                )
            }
            val opId = outbox.enqueue(
                tenantId, jobId, JobOpKind.ACKNOWLEDGEMENT, FieldOps.ACKNOWLEDGEMENT, clientId,
                json.encodeToJsonElement(AcknowledgementPayload.serializer(), payload).jsonObject, attachmentId,
            )
            WorkflowResult.Done(opId)
        }.also { onQueued() }
    }

    /** START needs the opening reading; COMPLETE needs closing reading, acknowledgement and no running entry. */
    suspend fun transition(tenantId: String, jobId: String, action: String): WorkflowResult {
        val job = repository.job(jobId) ?: return WorkflowResult.Refused("Job not found.")
        val state = repository.fieldState(tenantId, job)
        val kind = when (action) {
            START -> {
                if (state.effectiveStatus != JobStatus.APPROVED) return WorkflowResult.Refused("Only an approved job can be started.")
                if (!state.hasOpening) return WorkflowResult.Refused("Capture the opening reading first.")
                JobOpKind.START
            }
            COMPLETE -> {
                if (state.effectiveStatus != JobStatus.IN_PROGRESS) return WorkflowResult.Refused("Only a running job can be completed.")
                if (!state.hasClosing) return WorkflowResult.Refused("Capture the closing reading first.")
                if (!state.hasAcknowledgement) return WorkflowResult.Refused("Get the customer acknowledgement first.")
                if (db().evidenceDao().observeWorkLog(jobId, repository.ownerSubject()).first().any { it.operationId == null }) {
                    return WorkflowResult.Refused("Stop the running work-log entry first.")
                }
                JobOpKind.COMPLETE
            }
            else -> return WorkflowResult.Refused("Unsupported action.")
        }
        val database = db()
        return database.inTransaction {
            val opId = outbox.enqueue(
                tenantId, jobId, kind, FieldOps.transitionEntityType(action), jobId,
                json.encodeToJsonElement(JobTransitionPayload.serializer(), JobTransitionPayload(jobId, action)).jsonObject,
            )
            WorkflowResult.Done(opId)
        }.also { onQueued() }
    }

    private suspend fun queueActivity(tenantId: String, entry: WorkLogEntryEntity, billable: Boolean? = null): String {
        val payload = ActivityPayload(
            jobId = entry.jobId, clientId = entry.clientId, activityType = entry.activityType,
            startedAt = IsoTime.format(entry.startedAt), endedAt = entry.endedAt?.let(IsoTime::format),
            billable = billable, note = entry.note, deviceId = deviceId(),
        )
        return outbox.enqueue(
            tenantId, entry.jobId, JobOpKind.ACTIVITY, FieldOps.ACTIVITY, entry.clientId,
            json.encodeToJsonElement(ActivityPayload.serializer(), payload).jsonObject,
        )
    }

    private suspend fun refuseUnlessLoggable(tenantId: String, jobId: String): WorkflowResult? {
        val job = repository.job(jobId) ?: return WorkflowResult.Refused("Job not found.")
        val state = repository.fieldState(tenantId, job)
        return if (JobStateRules.canLogWork(state.effectiveStatus)) null
        else WorkflowResult.Refused("Work can only be logged on approved or running jobs.")
    }

    private fun String?.clean(): String? = this?.trim()?.takeIf { it.isNotEmpty() }?.take(2000)

    companion object {
        const val START = "START"
        const val COMPLETE = "COMPLETE"
    }
}
