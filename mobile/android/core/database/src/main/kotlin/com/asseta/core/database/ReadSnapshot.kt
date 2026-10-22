package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction

/**
 * Owner app offline cache: the last server response per (tenant, key) as JSON, with the time it was fetched.
 * Read-only snapshots (never edited locally, never pushed); bounded by age and count and wiped on sign-out.
 */
@Entity(tableName = "read_snapshot", primaryKeys = ["tenant_id", "cache_key"])
data class ReadSnapshotEntity(
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "cache_key") val cacheKey: String,
    @ColumnInfo(name = "payload_json") val payloadJson: String,
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long,
)

@Dao
abstract class ReadSnapshotDao {
    @Query("SELECT * FROM read_snapshot WHERE tenant_id = :tenantId AND cache_key = :key")
    abstract suspend fun get(tenantId: String, key: String): ReadSnapshotEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    protected abstract suspend fun put(snapshot: ReadSnapshotEntity)

    /** Keeps only the newest [keep] snapshots of the tenant (oldest evicted first). */
    @Query(
        """DELETE FROM read_snapshot WHERE tenant_id = :tenantId AND cache_key NOT IN
           (SELECT cache_key FROM read_snapshot WHERE tenant_id = :tenantId ORDER BY fetched_at DESC LIMIT :keep)""",
    )
    abstract suspend fun trim(tenantId: String, keep: Int): Int

    /** Writes a snapshot and enforces the per-tenant bound in the same transaction. */
    @Transaction
    open suspend fun putBounded(snapshot: ReadSnapshotEntity, maxPerTenant: Int) {
        put(snapshot)
        trim(snapshot.tenantId, maxPerTenant)
    }

    @Query("DELETE FROM read_snapshot WHERE fetched_at < :before")
    abstract suspend fun purgeOlderThan(before: Long): Int

    @Query("DELETE FROM read_snapshot WHERE tenant_id = :tenantId")
    abstract suspend fun deleteTenant(tenantId: String): Int

    @Query("DELETE FROM read_snapshot WHERE tenant_id NOT IN (:keep)")
    abstract suspend fun deleteTenantsExcept(keep: List<String>): Int

    @Query("DELETE FROM read_snapshot")
    abstract suspend fun deleteAll(): Int

    @Query("SELECT COUNT(*) FROM read_snapshot WHERE tenant_id = :tenantId")
    abstract suspend fun count(tenantId: String): Int
}
