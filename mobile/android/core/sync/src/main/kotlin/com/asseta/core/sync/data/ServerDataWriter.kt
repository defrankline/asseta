package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.CashCustodyBalanceEntity
import com.asseta.core.database.ExpenseCategoryEntity
import com.asseta.core.database.JobEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.PolicySnapshotEntity
import com.asseta.core.database.ReferenceRecordEntity
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.model.sync.BootstrapDto
import com.asseta.core.model.sync.ChangesDto
import com.asseta.core.model.sync.DeviceSessionDto
import com.asseta.core.model.sync.PolicySnapshotDto
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.SyncData
import com.asseta.core.model.sync.SyncDepositAccountDto
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

/** ISO-8601 parsing tolerant of `Z`, numeric offsets and (defensively) naive UTC timestamps. */
object IsoTime {
    fun parse(raw: String): Instant = runCatching { OffsetDateTime.parse(raw).toInstant() }
        .getOrElse { LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC) }

    fun format(epochMs: Long): String = Instant.ofEpochMilli(epochMs).toString()
}

/**
 * Applies server snapshots/deltas to the local cache in one transaction per page, together with the cursor, so a crash
 * can never persist a cursor without its data. Server-owned rows are upserted by (id, version): newer wins.
 */
class ServerDataWriter(private val db: () -> AssetaDatabase, private val json: Json) {

    suspend fun applyRegistration(tenantId: String, session: DeviceSessionDto) {
        val database = db()
        database.inTransaction {
            val states = database.syncStateDao()
            val current = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                current.copy(
                    deviceSessionId = session.id,
                    offlineGrantUntil = IsoTime.parse(session.offlineGrantUntil).toEpochMilli(),
                ),
            )
        }
    }

    suspend fun applyBootstrap(tenantId: String, dto: BootstrapDto, receivedElapsedMs: Long) {
        val database = db()
        database.inTransaction {
            val field = database.fieldDataDao()
            val keep = dto.data.jobs.map { it.id }
            if (keep.isEmpty()) field.deleteAllJobs(tenantId) else field.deleteJobsNotIn(tenantId, keep)
            val categories = dto.data.expenseCategories.map { it.id }
            val finance = database.financeDataDao()
            if (categories.isEmpty()) finance.deleteAllCategories(tenantId) else finance.deleteCategoriesNotIn(tenantId, categories)
            // The bootstrap inbox is the server's full window: start it afresh (later pages arrive as changes).
            if (SyncCapabilities.SUPERVISOR_INBOX_V1 in dto.capabilities) database.inboxDao().deleteTenant(tenantId)
            // Deposit accounts in the bootstrap are the full list: accounts no longer delivered leave the picker.
            dto.data.depositAccounts?.let { accounts ->
                val keepAccounts = accounts.map { it.id }
                if (keepAccounts.isEmpty()) field.deleteReferencesOfKind(tenantId, KIND_DEPOSIT_ACCOUNT)
                else field.deleteReferencesNotIn(tenantId, KIND_DEPOSIT_ACCOUNT, keepAccounts)
            }
            applyData(database, tenantId, dto.data)
            applySnapshots(database, tenantId, dto.policySnapshots)
            val states = database.syncStateDao()
            val current = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                current.copy(
                    capabilities = dto.capabilities.joinToString(","),
                    deviceSessionId = dto.deviceSession.id,
                    offlineGrantUntil = IsoTime.parse(dto.deviceSession.offlineGrantUntil).toEpochMilli(),
                    cursor = dto.cursor,
                    serverTime = IsoTime.parse(dto.serverTime).toEpochMilli(),
                    serverTimeElapsed = receivedElapsedMs,
                ),
            )
        }
    }

    suspend fun applyChanges(tenantId: String, dto: ChangesDto, receivedElapsedMs: Long) {
        val database = db()
        database.inTransaction {
            applyData(database, tenantId, dto.data)
            applySnapshots(database, tenantId, dto.policySnapshots)
            val states = database.syncStateDao()
            val current = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                current.copy(
                    capabilities = dto.capabilities.joinToString(","),
                    cursor = maxOf(dto.cursor, current.cursor ?: 0),
                    serverTime = IsoTime.parse(dto.serverTime).toEpochMilli(),
                    serverTimeElapsed = receivedElapsedMs,
                ),
            )
        }
    }

    private suspend fun applyData(database: AssetaDatabase, tenantId: String, data: SyncData) {
        val field = database.fieldDataDao()
        field.upsertJobs(
            data.jobs.map {
                JobEntity(it.id, tenantId, it.jobNumber, it.machineId, it.contractId, it.jobSiteId, it.status, it.version,
                    it.plannedStart, it.plannedEnd, it.standbyTreatment, it.currency, it.cancellationReason, it.requestedByStaffId,
                    it.requestNote)
            },
        )
        field.upsertMachines(
            data.machines.map { MachineEntity(it.id, tenantId, it.assetCode, it.name, it.meterDecimalPlaces, it.status, it.version) },
        )
        val refs = data.sites.map { ref(KIND_SITE, it.id, tenantId, it.name, json.encodeToString(it)) } +
            data.customers.map { ref(KIND_CUSTOMER, it.id, tenantId, it.name, json.encodeToString(it)) } +
            data.contracts.map { ref(KIND_CONTRACT, it.id, tenantId, it.contractNumber, json.encodeToString(it)) } +
            data.staff.map { ref(KIND_STAFF, it.id, tenantId, it.fullName, json.encodeToString(it)) }
        if (refs.isNotEmpty()) field.upsertReferences(refs)
        applyDepositAccounts(database, tenantId, data.depositAccounts.orEmpty())
        applyFinance(database, tenantId, data)
        InboxWriter(json).apply(database, tenantId, data)
    }

    /** Deposit accounts upsert by sync revision (an older revision never replaces a newer one; deactivations kept). */
    private suspend fun applyDepositAccounts(database: AssetaDatabase, tenantId: String, accounts: List<SyncDepositAccountDto>) {
        if (accounts.isEmpty()) return
        val field = database.fieldDataDao()
        val newer = accounts.filter { incoming ->
            val stored = field.reference(KIND_DEPOSIT_ACCOUNT, incoming.id)?.let {
                runCatching { json.decodeFromString(SyncDepositAccountDto.serializer(), it.json) }.getOrNull()
            }
            stored == null || incoming.syncRevision >= stored.syncRevision
        }
        if (newer.isNotEmpty()) field.upsertReferences(newer.map { ref(KIND_DEPOSIT_ACCOUNT, it.id, tenantId, it.name, json.encodeToString(it)) })
    }

    /** Expense categories upsert by sync revision (deactivations arrive as is_active=false); custody is replaced. */
    private suspend fun applyFinance(database: AssetaDatabase, tenantId: String, data: SyncData) {
        val finance = database.financeDataDao()
        if (data.expenseCategories.isNotEmpty()) {
            finance.upsertCategories(
                data.expenseCategories.map {
                    ExpenseCategoryEntity(it.id, tenantId, it.code, it.name, it.isActive, it.syncRevision, it.version)
                },
            )
        }
        val custody = data.cashCustody ?: return // field absent: keep what we have
        val now = System.currentTimeMillis()
        finance.replaceCustody(
            tenantId,
            custody.map {
                CashCustodyBalanceEntity(
                    tenantId = tenantId, currency = it.currency, staffMemberId = it.staffMemberId,
                    outstanding = it.outstanding.toPlainString(),
                    claimedUnverifiedHandovers = it.claimedUnverifiedHandovers.toPlainString(),
                    pendingSpending = it.pendingSpending.toPlainString(),
                    asOf = IsoTime.parse(it.asOf).toEpochMilli(), receivedAt = now,
                )
            },
        )
    }

    private suspend fun applySnapshots(database: AssetaDatabase, tenantId: String, snapshots: List<PolicySnapshotDto>) {
        if (snapshots.isEmpty()) return
        val now = System.currentTimeMillis()
        database.fieldDataDao().upsertSnapshots(
            snapshots.map {
                PolicySnapshotEntity(
                    tenantId = tenantId,
                    policyType = it.policyType,
                    scopeKey = it.scopeKey,
                    versionIdsJson = json.encodeToString(ListSerializer(String.serializer()), it.versionIds),
                    versionStamp = it.versionStamp,
                    valuesJson = json.encodeToString(it.values),
                    validUntil = IsoTime.parse(it.validUntil).toEpochMilli(),
                    receivedAt = now,
                )
            },
        )
    }

    private fun ref(kind: String, id: String, tenantId: String, title: String, body: String) =
        ReferenceRecordEntity(kind, id, tenantId, title, body)

    companion object {
        const val KIND_SITE = "site"
        const val KIND_CUSTOMER = "customer"
        const val KIND_CONTRACT = "contract"
        const val KIND_STAFF = "staff"
        const val KIND_DEPOSIT_ACCOUNT = "deposit_account"
    }
}
