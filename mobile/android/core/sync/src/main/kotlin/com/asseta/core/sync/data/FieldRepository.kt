package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.HeldOwner
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.PolicySelector
import com.asseta.core.domain.policy.PolicySnapshot
import com.asseta.core.domain.sync.ClockAnchor
import com.asseta.core.domain.sync.ClockCheck
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.SyncAccount
import com.asseta.core.sync.SyncClock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.time.Instant

enum class WaitingReason { EARLIER_ITEM, BLOCKED_BY_EARLIER, UPLOAD }

/**
 * Read side for the UI (Flows over the encrypted DB). All derivations reuse the domain rules. Device-owned records
 * (operations, evidence) are the signed-in [account]'s only; another user's are held, see [observeHeld].
 */
class FieldRepository(
    private val db: () -> AssetaDatabase,
    private val json: Json,
    private val clock: SyncClock,
    private val account: () -> SyncAccount?,
) {
    /** The signed-in user's subject (local records are filtered by it; matches nothing when signed out). */
    fun ownerSubject(): String = ownerSubject(account)

    /** Status counts of the signed-in user's outbox for the tenant (the sync status summary). */
    fun observeStatusCounts(tenantId: String): Flow<Map<ClientOperationStatus, Int>> =
        db().clientOperationDao().observeStatusCounts(tenantId, ownerSubject()).map { rows -> rows.associate { it.status to it.count } }

    /** "Retry" on a rejected operation (same id and payload; see `ClientOperationDao.requeueFailed`). */
    suspend fun requeue(operationId: String): Boolean = db().clientOperationDao().requeueFailed(operationId) > 0

    /**
     * Why an unsynced operation is not sent yet: an earlier operation it depends on (blocked when that one needs
     * attention), or its photo/receipt upload. [byId] is the tenant's unsynced operations.
     */
    suspend fun waitingReason(op: ClientOperationEntity, byId: Map<String, ClientOperationEntity>): WaitingReason? {
        val parents = (db().clientOperationDao().dependenciesOf(op.id) + listOfNotNull(op.dependsOn)).mapNotNull(byId::get)
        if (parents.isNotEmpty()) {
            val blocked = parents.any { it.status == ClientOperationStatus.FAILED || it.status == ClientOperationStatus.CONFLICT }
            return if (blocked) WaitingReason.BLOCKED_BY_EARLIER else WaitingReason.EARLIER_ITEM
        }
        val uploading = db().clientOperationDao().attachmentsOf(op.id)
            .any { db().evidenceDao().attachment(it)?.status != AttachmentEntity.COMPLETE }
        return if (uploading) WaitingReason.UPLOAD else null
    }

    suspend fun machine(machineId: String): MachineEntity? = db().fieldDataDao().machine(machineId)

    fun observeUnsynced(tenantId: String): Flow<List<ClientOperationEntity>> =
        db().clientOperationDao().observeUnsynced(tenantId, ownerSubject())

    /** Unsynced work other accounts left on this phone, per account: held until that account signs in again. */
    fun observeHeld(tenantId: String): Flow<List<HeldOwner>> = db().clientOperationDao().observeHeld(tenantId, ownerSubject())

    fun observeSyncState(tenantId: String): Flow<SyncStateEntity?> = db().syncStateDao().observe(tenantId)

    fun observePendingUploads(tenantId: String): Flow<Int> =
        db().evidenceDao().observePendingAttachmentCount(tenantId, ownerSubject())

    /** Evidence files that can never be uploaded (missing or changed on the device, refused for good by the server). */
    fun observeFailedUploads(tenantId: String): Flow<List<AttachmentEntity>> = db().evidenceDao().observeFailedAttachments(tenantId, ownerSubject())

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

    /** The tenant's IANA zone as sync last sent it (null from older servers). */
    suspend fun tenantTimezone(tenantId: String): String? = db().syncStateDao().get(tenantId)?.tenantTimezone

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
