package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.sync.JobOpKind
import com.asseta.core.domain.sync.JobOperationPlanner
import com.asseta.core.domain.sync.LocalJobOp
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.SyncClock
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import java.util.UUID

/** Outbox entity-type tags; they let the planner recover each operation's place in the job workflow. */
object FieldOps {
    fun captureEntityType(kind: ReadingKind) = "meter_capture.${kind.name}"
    fun transitionEntityType(action: String) = "job_transition.$action"
    const val ACTIVITY = "job_activity"
    const val ACKNOWLEDGEMENT = "job_acknowledgement"
    const val EXPENSE = "expense"
    const val CASH_COLLECTION = "cash_collection"
    const val CASH_HANDOVER = "cash_handover"
    const val FUEL_EVENT = "fuel_event"

    /** Field-finance op types (not part of a job workflow chain). */
    val FINANCE_OP_TYPES = listOf(OpTypes.EXPENSE, OpTypes.CASH_COLLECTION, OpTypes.CASH_HANDOVER, OpTypes.FUEL_EVENT)

    fun kindOf(op: ClientOperationEntity): JobOpKind? = when (op.entityType) {
        captureEntityType(ReadingKind.OPENING) -> JobOpKind.OPENING_CAPTURE
        captureEntityType(ReadingKind.CLOSING) -> JobOpKind.CLOSING_CAPTURE
        transitionEntityType("START") -> JobOpKind.START
        transitionEntityType("COMPLETE") -> JobOpKind.COMPLETE
        ACTIVITY -> JobOpKind.ACTIVITY
        ACKNOWLEDGEMENT -> JobOpKind.ACKNOWLEDGEMENT
        else -> null
    }

    fun opTypeOf(kind: JobOpKind): String = when (kind) {
        JobOpKind.OPENING_CAPTURE, JobOpKind.CLOSING_CAPTURE -> OpTypes.METER_CAPTURE
        JobOpKind.START, JobOpKind.COMPLETE -> OpTypes.JOB_TRANSITION
        JobOpKind.ACTIVITY -> OpTypes.JOB_ACTIVITY
        JobOpKind.ACKNOWLEDGEMENT -> OpTypes.JOB_ACKNOWLEDGEMENT
    }
}

/**
 * The single place that turns a field action into an outbox operation with its dependency chain
 * (opening capture -> START -> activities/closing -> acknowledgement -> COMPLETE), or a field-finance operation with
 * its explicit dependencies and evidence gate (an expense waits for its receipt upload). Must be called inside the
 * caller's transaction so the domain record and its operation are written atomically.
 */
class FieldOutbox(private val db: () -> AssetaDatabase, private val json: Json, private val clock: SyncClock) {

    suspend fun localJobOps(tenantId: String, jobId: String): List<LocalJobOp> =
        db().clientOperationDao().forJob(tenantId, jobId).mapNotNull { op ->
            FieldOps.kindOf(op)?.let { LocalJobOp(op.id, it, op.status, op.createdAtDevice) }
        }

    suspend fun enqueue(
        tenantId: String,
        jobId: String,
        kind: JobOpKind,
        entityType: String,
        entityId: String,
        payload: JsonObject,
        attachmentLocalId: String? = null,
    ): String {
        val deps = JobOperationPlanner.dependenciesFor(kind, localJobOps(tenantId, jobId))
        return enqueueOperation(tenantId, FieldOps.opTypeOf(kind), entityType, entityId, payload, attachmentLocalId, deps, jobId)
    }

    /**
     * Enqueues one operation. [attachmentLocalId] gates dispatch until that evidence upload completed (its server ids
     * are then written into the never-sent payload); [dependsOn] are parent operations that must be ACKED first.
     */
    suspend fun enqueueOperation(
        tenantId: String,
        opType: String,
        entityType: String,
        entityId: String,
        payload: JsonObject,
        attachmentLocalId: String? = null,
        dependsOn: List<String> = emptyList(),
        jobId: String? = null,
    ): String {
        require(dependsOn.size <= JobOperationPlanner.MAX_DEPENDENCIES) { "Too many dependencies" }
        val op = ClientOperationEntity(
            id = UUID.randomUUID().toString(),
            tenantId = tenantId,
            opType = opType,
            entityType = entityType,
            entityId = entityId,
            payloadJson = json.encodeToString(payload),
            dependsOn = null,
            createdAtDevice = clock.nowMs(),
            status = ClientOperationStatus.PENDING,
            attemptCount = 0,
            lastError = null,
            serverRevision = null,
            jobId = jobId,
            attachmentLocalId = attachmentLocalId,
        )
        check(db().clientOperationDao().enqueueWithDependencies(op, dependsOn) != -1L) { "Operation id collision" }
        return op.id
    }
}
