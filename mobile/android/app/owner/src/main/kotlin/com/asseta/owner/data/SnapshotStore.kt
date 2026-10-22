package com.asseta.owner.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.domain.owner.SnapshotPolicy

/** A cached server response (JSON) and when it was fetched. */
data class CachedSnapshot(val payloadJson: String, val fetchedAtMs: Long)

/** Offline read-only cache of server responses, per tenant. */
interface SnapshotStore {
    suspend fun read(tenantId: String, key: String): CachedSnapshot?
    suspend fun write(tenantId: String, key: String, payloadJson: String, fetchedAtMs: Long)
    suspend fun purgeExpired(nowMs: Long)
    suspend fun wipeTenant(tenantId: String)
    suspend fun keepOnlyTenants(tenantIds: List<String>)
    suspend fun wipeAll()
}

/**
 * Room (SQLCipher) implementation. The database is fetched per call (never cached) so a sign-out wipe that deletes
 * the database file is safe; expired rows are never returned even before the next purge.
 */
class RoomSnapshotStore(
    private val db: () -> AssetaDatabase,
    private val policy: SnapshotPolicy,
    private val clock: () -> Long = System::currentTimeMillis,
) : SnapshotStore {
    private val dao get() = db().readSnapshotDao()

    override suspend fun read(tenantId: String, key: String): CachedSnapshot? =
        dao.get(tenantId, key)?.takeUnless { policy.isExpired(it.fetchedAt, clock()) }?.let { CachedSnapshot(it.payloadJson, it.fetchedAt) }

    override suspend fun write(tenantId: String, key: String, payloadJson: String, fetchedAtMs: Long) {
        if (!policy.cacheable(payloadJson.length)) return
        dao.putBounded(ReadSnapshotEntity(tenantId, key, payloadJson, fetchedAtMs), policy.maxEntriesPerTenant)
    }

    override suspend fun purgeExpired(nowMs: Long) {
        dao.purgeOlderThan(policy.purgeBefore(nowMs))
    }

    override suspend fun wipeTenant(tenantId: String) {
        dao.deleteTenant(tenantId)
    }

    override suspend fun keepOnlyTenants(tenantIds: List<String>) {
        dao.deleteTenantsExcept(tenantIds)
    }

    override suspend fun wipeAll() {
        dao.deleteAll()
    }
}
