package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.JobEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.MeterCaptureEntity
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.database.WorkLogEntryEntity
import com.asseta.core.domain.capture.JobStateRules
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.PolicySelector
import com.asseta.core.domain.policy.PolicySnapshot
import com.asseta.core.domain.sync.ClockAnchor
import com.asseta.core.domain.sync.ClockCheck
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.core.domain.sync.JobOpKind
import com.asseta.core.domain.sync.JobOperationPlanner
import com.asseta.core.domain.sync.LocalJobOp
import com.asseta.core.sync.SyncClock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.time.Instant

data class JobSummary(val job: JobEntity, val machine: MachineEntity?)

/** What the job screen needs, derived once here (not per screen) from server state + local operations. */
data class JobFieldState(
    val effectiveStatus: String,
    val hasOpening: Boolean,
    val hasClosing: Boolean,
    val hasAcknowledgement: Boolean,
    val startQueued: Boolean,
    val completeQueued: Boolean,
)

/** Read side for the UI (Flows over the encrypted DB). All derivations reuse the domain rules. */
class FieldRepository(private val db: () -> AssetaDatabase, private val json: Json, private val clock: SyncClock) {

    fun observeJobs(tenantId: String): Flow<List<JobSummary>> {
        val field = db().fieldDataDao()
        return combine(field.observeJobs(tenantId), field.observeMachines(tenantId)) { jobs, machines ->
            val byId = machines.associateBy { it.id }
            jobs.map { JobSummary(it, byId[it.machineId]) }
        }
    }

    fun observeJob(jobId: String): Flow<JobEntity?> = db().fieldDataDao().observeJob(jobId)

    suspend fun machine(machineId: String): MachineEntity? = db().fieldDataDao().machine(machineId)

    suspend fun job(jobId: String): JobEntity? = db().fieldDataDao().job(jobId)

    fun observeJobOperations(tenantId: String, jobId: String): Flow<List<ClientOperationEntity>> =
        db().clientOperationDao().observeForJob(tenantId, jobId)

    fun observeCaptures(jobId: String): Flow<List<MeterCaptureEntity>> = db().evidenceDao().observeCaptures(jobId)

    fun observeWorkLog(jobId: String): Flow<List<WorkLogEntryEntity>> = db().evidenceDao().observeWorkLog(jobId)

    fun observeUnsynced(tenantId: String): Flow<List<ClientOperationEntity>> = db().clientOperationDao().observeUnsynced(tenantId)

    fun observeSyncState(tenantId: String): Flow<SyncStateEntity?> = db().syncStateDao().observe(tenantId)

    fun observePendingUploads(tenantId: String): Flow<Int> = db().evidenceDao().observePendingAttachmentCount(tenantId)

    fun fieldState(job: JobEntity, ops: List<ClientOperationEntity>): JobFieldState {
        val local = ops.mapNotNull { op -> FieldOps.kindOf(op)?.let { LocalJobOp(op.id, it, op.status, op.createdAtDevice) } }
        val start = JobOperationPlanner.hasLive(JobOpKind.START, local)
        val complete = JobOperationPlanner.hasLive(JobOpKind.COMPLETE, local)
        return JobFieldState(
            effectiveStatus = JobStateRules.effectiveStatus(job.status, start, complete),
            hasOpening = JobOperationPlanner.hasLive(JobOpKind.OPENING_CAPTURE, local),
            hasClosing = JobOperationPlanner.hasLive(JobOpKind.CLOSING_CAPTURE, local),
            hasAcknowledgement = JobOperationPlanner.hasLive(JobOpKind.ACKNOWLEDGEMENT, local),
            startQueued = start,
            completeQueued = complete,
        )
    }

    suspend fun fieldState(tenantId: String, job: JobEntity): JobFieldState =
        fieldState(job, db().clientOperationDao().forJob(tenantId, job.id))

    /** Machine snapshot, else tenant snapshot; blocked when expired or past the offline grant. */
    suspend fun capturePolicy(tenantId: String, machineId: String): CapturePolicyDecision {
        val snapshots = db().fieldDataDao().snapshots(tenantId).map {
            PolicySnapshot(
                policyType = it.policyType,
                scopeKey = it.scopeKey,
                versionIds = json.decodeFromString(ListSerializer(String.serializer()), it.versionIdsJson),
                versionStamp = it.versionStamp,
                values = json.parseToJsonElement(it.valuesJson).jsonObject,
                validUntil = Instant.ofEpochMilli(it.validUntil),
            )
        }
        val grant = db().syncStateDao().get(tenantId)?.offlineGrantUntil?.let(Instant::ofEpochMilli)
        return PolicySelector.select(snapshots, machineId, Instant.ofEpochMilli(clock.nowMs()), grant)
    }

    /** Local clock-tamper check against the last trusted server time (300 s threshold). */
    fun clockStatus(state: SyncStateEntity?): ClockStatus {
        val serverTime = state?.serverTime
        val elapsed = state?.serverTimeElapsed
        val anchor = if (serverTime != null && elapsed != null) ClockAnchor(serverTime, elapsed) else null
        return ClockCheck.evaluate(anchor, clock.nowMs(), clock.elapsedRealtimeMs())
    }
}
