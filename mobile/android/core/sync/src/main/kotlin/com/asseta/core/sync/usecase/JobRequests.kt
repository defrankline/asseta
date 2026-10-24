package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.jobs.JobRequestRules
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.SyncAccount
import com.asseta.core.model.sync.ContractDto
import com.asseta.core.model.sync.FieldContractDto
import com.asseta.core.model.sync.JobRequestPayload
import com.asseta.core.model.sync.MachineDto
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.network.TenantApi
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.data.ServerDataWriter
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject

/** A site the request can name (the contract's site is preselected). */
data class SiteChoice(val id: String, val name: String)

/** What the request form picks from: the field contracts, my machines and the known sites. */
data class JobRequestLookups(
    val contracts: List<FieldContractDto> = emptyList(),
    val machines: List<MachineDto> = emptyList(),
    val sites: List<SiteChoice> = emptyList(),
    /** When the lists were fetched from the server (null: built from synced data only). */
    val fetchedAtMs: Long? = null,
)

/** One form submission. [clientId] is generated once per form visit and becomes the server job id (exactly once). */
data class JobRequestInput(
    val tenantId: String,
    val clientId: String,
    val contractId: String?,
    val machineId: String?,
    val siteId: String?,
    val plannedStartMs: Long,
    val plannedEndMs: Long?,
    val note: String,
)

/** A request recorded on this phone, as the Jobs list shows it until the job itself is on the phone. */
data class JobRequestItem(
    /** = the server job id. */
    val clientId: String,
    val operationStatus: ClientOperationStatus,
    /** The server's job number once the request was accepted. */
    val jobNumber: String?,
    val payload: JobRequestPayload,
    val createdAtMs: Long,
    val errorMessage: String?,
)

/**
 * Supervisor job requests from the field (`JOB_REQUEST`, permission tenant.job.request). The form's lookups come from
 * `/tenant/field/contracts` and `/tenant/field/machines`, cached in the encrypted read-snapshot store for offline use
 * (falling back to the synced contracts and machines); the request itself is queued in the outbox and works offline.
 * The owner approves (and prices) or declines it; the job then arrives through sync.
 */
class JobRequests(
    private val api: () -> TenantApi,
    private val db: () -> AssetaDatabase,
    private val outbox: FieldOutbox,
    private val json: Json,
    private val account: () -> SyncAccount?,
    private val nowMs: () -> Long = System::currentTimeMillis,
    private val onQueued: () -> Unit = {},
) {
    /** The lookups saved on this phone (server lists, else synced reference data); never touches the network. */
    suspend fun savedLookups(tenantId: String): JobRequestLookups {
        val contracts = cached(tenantId, CONTRACTS_KEY, ListSerializer(FieldContractDto.serializer()))
        val machines = cached(tenantId, MACHINES_KEY, ListSerializer(MachineDto.serializer()))
        val synced = syncedLookups(tenantId)
        return JobRequestLookups(
            contracts = contracts?.first ?: synced.contracts,
            machines = machines?.first ?: synced.machines,
            sites = sites(tenantId, contracts?.first ?: synced.contracts),
            fetchedAtMs = contracts?.second,
        )
    }

    /** Fresh lists from the server (saved for offline use); the saved ones when offline or refused. */
    suspend fun refreshLookups(tenantId: String): JobRequestLookups {
        val contracts = fetch(tenantId, CONTRACTS_KEY, ListSerializer(FieldContractDto.serializer())) { fieldContracts() }
        val machines = fetch(tenantId, MACHINES_KEY, ListSerializer(MachineDto.serializer())) { fieldMachines() }
        val saved = savedLookups(tenantId)
        val list = contracts ?: saved.contracts
        return JobRequestLookups(list, machines ?: saved.machines, sites(tenantId, list), if (contracts != null) nowMs() else saved.fetchedAtMs)
    }

    /** Null when job requests can be recorded, else why not (never synced, or a server without OP_JOB_REQUEST). */
    suspend fun unavailable(tenantId: String): String? {
        val state = db().syncStateDao().get(tenantId)
        return when {
            state?.capabilities == null -> "Sync once while online before requesting a job."
            !state.supports(SyncCapabilities.OP_JOB_REQUEST) -> "Your company's server does not accept job requests yet."
            else -> null
        }
    }

    /** Validates and queues the request; replaying the same [JobRequestInput.clientId] never queues it twice. */
    suspend fun request(r: JobRequestInput): FinanceResult {
        unavailable(r.tenantId)?.let { return FinanceResult.Blocked(it) }
        val issues = JobRequestRules.validate(r.contractId, r.machineId, r.plannedStartMs, r.plannedEndMs, r.note)
        if (issues.isNotEmpty()) return FinanceResult.Invalid(issues)
        val payload = JobRequestPayload(
            clientId = r.clientId,
            contractId = r.contractId!!,
            machineId = r.machineId!!,
            jobSiteId = r.siteId?.takeIf { it.isNotBlank() },
            plannedStart = IsoTime.format(r.plannedStartMs),
            plannedEnd = r.plannedEndMs?.let(IsoTime::format),
            note = r.note.trim().takeIf { it.isNotEmpty() },
        )
        val database = db()
        return database.inTransaction {
            if (database.clientOperationDao().findByEntity(r.tenantId, ENTITY, r.clientId) != null) return@inTransaction FinanceResult.AlreadySaved
            val opId = outbox.enqueueOperation(
                r.tenantId, OpTypes.JOB_REQUEST, ENTITY, r.clientId,
                json.encodeToJsonElement(JobRequestPayload.serializer(), payload).jsonObject, jobId = r.clientId,
            )
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    /** The signed-in user's requests of the tenant, newest first. */
    fun observe(tenantId: String): Flow<List<JobRequestItem>> =
        db().clientOperationDao().observeByOpTypes(tenantId, com.asseta.core.sync.data.ownerSubject(account), listOf(OpTypes.JOB_REQUEST))
            .map { ops -> ops.mapNotNull(::item) }

    private fun item(op: ClientOperationEntity): JobRequestItem? {
        val payload = runCatching { json.decodeFromString(JobRequestPayload.serializer(), op.payloadJson) }.getOrNull() ?: return null
        return JobRequestItem(op.entityId, op.status, jobNumber(op.resultJson), payload, op.createdAtDevice, op.lastError)
    }

    /** The job number in the server's result (`job_number` at the top, or in `entity`/`job`). */
    private fun jobNumber(resultJson: String?): String? {
        val result = resultJson?.let { runCatching { json.parseToJsonElement(it).jsonObject }.getOrNull() } ?: return null
        fun of(o: JsonObject?) = (o?.get("job_number") as? JsonPrimitive)?.contentOrNull
        return of(result) ?: of(result["entity"] as? JsonObject) ?: of(result["job"] as? JsonObject)
    }

    private suspend fun <T> fetch(tenantId: String, key: String, serializer: KSerializer<T>, call: suspend TenantApi.() -> T): T? = try {
        val value = api().call()
        runCatching {
            db().readSnapshotDao().putBounded(ReadSnapshotEntity(tenantId, key, json.encodeToString(serializer, value), nowMs()), MAX_SNAPSHOTS)
        }
        value
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        null
    }

    private suspend fun <T> cached(tenantId: String, key: String, serializer: KSerializer<T>): Pair<T, Long>? = runCatching {
        db().readSnapshotDao().get(tenantId, key)?.let { json.decodeFromString(serializer, it.payloadJson) to it.fetchedAt }
    }.getOrNull()

    /** Contracts and machines this phone already has from sync (before the first online visit of the form). */
    private suspend fun syncedLookups(tenantId: String): JobRequestLookups {
        val field = db().fieldDataDao()
        val customers = field.observeReferences(tenantId, ServerDataWriter.KIND_CUSTOMER).first().associate { it.id to it.title }
        val siteNames = field.observeReferences(tenantId, ServerDataWriter.KIND_SITE).first().associate { it.id to it.title }
        val contracts = field.observeReferences(tenantId, ServerDataWriter.KIND_CONTRACT).first().mapNotNull { ref ->
            runCatching { json.decodeFromString(ContractDto.serializer(), ref.json) }.getOrNull()
                ?.takeIf { it.status == "ACTIVE" }
                ?.let {
                    FieldContractDto(it.id, it.contractNumber, it.customerId, customers[it.customerId] ?: it.contractNumber, it.jobSiteId,
                        it.jobSiteId?.let(siteNames::get))
                }
        }
        val machines = field.observeMachines(tenantId).first().map { MachineDto(it.id, it.assetCode, it.name, it.meterDecimalPlaces, it.status, it.version) }
        return JobRequestLookups(contracts, machines)
    }

    private suspend fun sites(tenantId: String, contracts: List<FieldContractDto>): List<SiteChoice> {
        val synced = db().fieldDataDao().observeReferences(tenantId, ServerDataWriter.KIND_SITE).first().map { SiteChoice(it.id, it.title) }
        val fromContracts = contracts.mapNotNull { c -> c.jobSiteId?.let { SiteChoice(it, c.jobSiteName ?: it) } }
        return (synced + fromContracts).distinctBy { it.id }.sortedBy { it.name.lowercase() }
    }

    companion object {
        const val ENTITY = "job_request"
        const val CONTRACTS_KEY = "supervisor.field_contracts"
        const val MACHINES_KEY = "supervisor.field_machines"
        const val MAX_SNAPSHOTS = 20
    }
}
