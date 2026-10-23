package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
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
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.ContractDto
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.SyncClock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.time.Instant

/** A job with the cached entities the job list shows (site and customer from the synced reference data). */
data class JobSummary(
    val job: JobEntity,
    val machine: MachineEntity?,
    val siteName: String? = null,
    val customerName: String? = null,
)

enum class WaitingReason { EARLIER_ITEM, BLOCKED_BY_EARLIER, UPLOAD }

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
        return combine(
            field.observeJobs(tenantId),
            field.observeMachines(tenantId),
            field.observeReferences(tenantId, ServerDataWriter.KIND_SITE),
            field.observeReferences(tenantId, ServerDataWriter.KIND_CUSTOMER),
            field.observeReferences(tenantId, ServerDataWriter.KIND_CONTRACT),
        ) { jobs, machines, sites, customers, contracts ->
            val byId = machines.associateBy { it.id }
            val siteNames = sites.associate { it.id to it.title }
            val customerNames = customers.associate { it.id to it.title }
            val contractCustomer = contracts.associate { it.id to contractCustomerId(it.json) }
            jobs.map { job ->
                JobSummary(job, byId[job.machineId], job.jobSiteId?.let(siteNames::get), contractCustomer[job.contractId]?.let(customerNames::get))
            }
        }
    }

    private fun contractCustomerId(contractJson: String): String? =
        runCatching { json.decodeFromString(ContractDto.serializer(), contractJson).customerId }.getOrNull()

    /** Status counts of the tenant's whole outbox (the sync status summary). */
    fun observeStatusCounts(tenantId: String): Flow<Map<ClientOperationStatus, Int>> =
        db().clientOperationDao().observeStatusCounts(tenantId).map { rows -> rows.associate { it.status to it.count } }

    /** "Retry" on a rejected operation (same id and payload; see `ClientOperationDao.requeueFailed`). */
    suspend fun requeue(operationId: String): Boolean = db().clientOperationDao().requeueFailed(operationId) > 0

    /**
     * Why an unsynced operation is not sent yet: an earlier operation it depends on (blocked when that one needs
     * attention), or its photo/receipt/signature upload. [byId] is the tenant's unsynced operations.
     */
    suspend fun waitingReason(op: ClientOperationEntity, byId: Map<String, ClientOperationEntity>): WaitingReason? {
        val parents = (db().clientOperationDao().dependenciesOf(op.id) + listOfNotNull(op.dependsOn)).mapNotNull(byId::get)
        if (parents.isNotEmpty()) {
            val blocked = parents.any { it.status == ClientOperationStatus.FAILED || it.status == ClientOperationStatus.CONFLICT }
            return if (blocked) WaitingReason.BLOCKED_BY_EARLIER else WaitingReason.EARLIER_ITEM
        }
        val attachment = op.attachmentLocalId?.let { db().evidenceDao().attachment(it) }
        return if (attachment != null && attachment.status != AttachmentEntity.COMPLETE) WaitingReason.UPLOAD else null
    }

    fun observeJob(jobId: String): Flow<JobEntity?> = db().fieldDataDao().observeJob(jobId)

    suspend fun machine(machineId: String): MachineEntity? = db().fieldDataDao().machine(machineId)

    suspend fun job(jobId: String): JobEntity? = db().fieldDataDao().job(jobId)

    fun observeJobOperations(tenantId: String, jobId: String): Flow<List<ClientOperationEntity>> =
        db().clientOperationDao().observeForJob(tenantId, jobId)

    /** The tenant's job operations grouped by job (the job list derives each job's status on this device). */
    fun observeOperationsByJob(tenantId: String): Flow<Map<String, List<ClientOperationEntity>>> =
        db().clientOperationDao().observeByOpTypes(tenantId, JOB_OP_TYPES)
            .map { ops -> ops.filter { it.jobId != null }.sortedBy { it.createdAtDevice }.groupBy { it.jobId!! } }

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
    suspend fun capturePolicy(tenantId: String, machineId: String): CapturePolicyDecision =
        PolicySelector.select(policySnapshots(tenantId), machineId, Instant.ofEpochMilli(clock.nowMs()), offlineGrant(tenantId))

    /** Every stored policy snapshot of the tenant (meter capture, expense capture, ...). */
    suspend fun policySnapshots(tenantId: String): List<PolicySnapshot> =
        db().fieldDataDao().snapshots(tenantId).map {
            PolicySnapshot(
                policyType = it.policyType,
                scopeKey = it.scopeKey,
                versionIds = json.decodeFromString(ListSerializer(String.serializer()), it.versionIdsJson),
                versionStamp = it.versionStamp,
                values = json.parseToJsonElement(it.valuesJson).jsonObject,
                validUntil = Instant.ofEpochMilli(it.validUntil),
            )
        }

    suspend fun offlineGrant(tenantId: String): Instant? =
        db().syncStateDao().get(tenantId)?.offlineGrantUntil?.let(Instant::ofEpochMilli)

    /** Local clock-tamper check against the last trusted server time (300 s threshold). */
    fun clockStatus(state: SyncStateEntity?): ClockStatus {
        val serverTime = state?.serverTime
        val elapsed = state?.serverTimeElapsed
        val anchor = if (serverTime != null && elapsed != null) ClockAnchor(serverTime, elapsed) else null
        return ClockCheck.evaluate(anchor, clock.nowMs(), clock.elapsedRealtimeMs())
    }
}

private val JOB_OP_TYPES = listOf(OpTypes.METER_CAPTURE, OpTypes.JOB_ACTIVITY, OpTypes.JOB_ACKNOWLEDGEMENT, OpTypes.JOB_TRANSITION)
