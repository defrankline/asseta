package com.asseta.core.sync.engine

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.model.SyncAccount

/**
 * Field data on a phone shared by several users. A tenant's sync state (cursor, device session, offline grant) and the
 * server data cached with it (jobs, machines, reference data, expense categories, cash custody, policy snapshots,
 * the supervisor inbox and cached notifications)
 * belong to the user who synced them. When another user signs in, that tenant is reset so the new user gets a fresh
 * bootstrap of their own data, never the previous user's cache or a cursor past their own bootstrap.
 *
 * Device-owned work (outbox operations, evidence files, work-log entries) is never deleted here: it keeps its owner and
 * is held -- not shown as the new user's, not sent under their token -- until its owner signs in again. The same user
 * signing in again changes nothing. The clock anchor (last trusted server time) is device-level and kept.
 */
class AccountSwitch(private val db: () -> AssetaDatabase) {

    /** Makes [account] the owner of [tenantId]'s sync state; true when another user's state and cache were reset. */
    suspend fun claim(tenantId: String, account: SyncAccount): Boolean {
        val database = db()
        return database.inTransaction {
            val states = database.syncStateDao()
            val current = states.get(tenantId)
            if (current?.ownerSub == account.subject) return@inTransaction false
            clearServerData(database, tenantId)
            states.put(
                SyncStateEntity(
                    tenantId = tenantId,
                    ownerSub = account.subject,
                    serverTime = current?.serverTime,
                    serverTimeElapsed = current?.serverTimeElapsed,
                    clockOffsetS = current?.clockOffsetS,
                    serverClockAlert = current?.serverClockAlert ?: false,
                ),
            )
            current != null
        }
    }

    /** On sign-in: claims every tenant whose state belongs to another user. Returns the tenants that were reset. */
    suspend fun claimAll(account: SyncAccount): List<String> =
        db().syncStateDao().tenantsNotOwnedBy(account.subject).filter { claim(it, account) }

    private suspend fun clearServerData(database: AssetaDatabase, tenantId: String) {
        val field = database.fieldDataDao()
        field.deleteAllJobs(tenantId)
        field.deleteAllMachines(tenantId)
        field.deleteAllReferences(tenantId)
        field.deleteAllSnapshots(tenantId)
        val finance = database.financeDataDao()
        finance.deleteAllCategories(tenantId)
        finance.clearCustody(tenantId)
        database.inboxDao().deleteTenant(tenantId)
        database.readSnapshotDao().deleteTenant(tenantId) // cached notifications of the previous user
    }
}
