package com.asseta.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

/** Server-owned data: upserts keep the newer server version; nothing here is ever pushed back. */
@Dao
abstract class FieldDataDao {
    @Query("SELECT version FROM job WHERE id = :id")
    protected abstract suspend fun jobVersion(id: String): Long?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    protected abstract suspend fun putJob(job: JobEntity)

    @Query("SELECT version FROM machine WHERE id = :id")
    protected abstract suspend fun machineVersion(id: String): Long?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    protected abstract suspend fun putMachine(machine: MachineEntity)

    /** Upsert by (id, version): an older or replayed (lookback) server version never overwrites a newer one. */
    @Transaction
    open suspend fun upsertJobs(jobs: List<JobEntity>): Int = jobs.count { job ->
        val current = jobVersion(job.id)
        (current == null || job.version >= current).also { if (it) putJob(job) }
    }

    @Transaction
    open suspend fun upsertMachines(machines: List<MachineEntity>): Int = machines.count { m ->
        val current = machineVersion(m.id)
        (current == null || m.version >= current).also { if (it) putMachine(m) }
    }

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertReferences(records: List<ReferenceRecordEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertSnapshots(snapshots: List<PolicySnapshotEntity>)

    /** Bootstrap is a full snapshot of open jobs: jobs no longer delivered are dropped from the local cache. */
    @Query("DELETE FROM job WHERE tenant_id = :tenantId AND id NOT IN (:keep)")
    abstract suspend fun deleteJobsNotIn(tenantId: String, keep: List<String>): Int

    @Query("DELETE FROM job WHERE tenant_id = :tenantId")
    abstract suspend fun deleteAllJobs(tenantId: String): Int

    @Query("DELETE FROM machine WHERE tenant_id = :tenantId")
    abstract suspend fun deleteAllMachines(tenantId: String): Int

    @Query("DELETE FROM reference_record WHERE tenant_id = :tenantId")
    abstract suspend fun deleteAllReferences(tenantId: String): Int

    @Query("DELETE FROM policy_snapshot WHERE tenant_id = :tenantId")
    abstract suspend fun deleteAllSnapshots(tenantId: String): Int

    @Query("SELECT * FROM job WHERE tenant_id = :tenantId ORDER BY planned_start ASC, job_number ASC")
    abstract fun observeJobs(tenantId: String): Flow<List<JobEntity>>

    @Query("SELECT * FROM job WHERE id = :id")
    abstract fun observeJob(id: String): Flow<JobEntity?>

    @Query("SELECT * FROM job WHERE id = :id")
    abstract suspend fun job(id: String): JobEntity?

    @Query("SELECT * FROM machine WHERE id = :id")
    abstract suspend fun machine(id: String): MachineEntity?

    @Query("SELECT * FROM machine WHERE tenant_id = :tenantId")
    abstract fun observeMachines(tenantId: String): Flow<List<MachineEntity>>

    @Query("SELECT * FROM reference_record WHERE kind = :kind AND id = :id")
    abstract suspend fun reference(kind: String, id: String): ReferenceRecordEntity?

    @Query("SELECT * FROM reference_record WHERE tenant_id = :tenantId AND kind = :kind ORDER BY title COLLATE NOCASE")
    abstract fun observeReferences(tenantId: String, kind: String): Flow<List<ReferenceRecordEntity>>

    @Query("SELECT DISTINCT currency FROM job WHERE tenant_id = :tenantId AND currency IS NOT NULL")
    abstract suspend fun jobCurrencies(tenantId: String): List<String>

    @Query("SELECT * FROM policy_snapshot WHERE tenant_id = :tenantId")
    abstract suspend fun snapshots(tenantId: String): List<PolicySnapshotEntity>
}

@Dao
interface SyncStateDao {
    @Query("SELECT * FROM sync_state WHERE tenant_id = :tenantId")
    suspend fun get(tenantId: String): SyncStateEntity?

    @Query("SELECT * FROM sync_state WHERE tenant_id = :tenantId")
    fun observe(tenantId: String): Flow<SyncStateEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun put(state: SyncStateEntity)

    /** Tenants whose sync state (cursor, device session, cached server data) belongs to another user than [ownerSub]. */
    @Query("SELECT tenant_id FROM sync_state WHERE owner_sub IS NULL OR owner_sub != :ownerSub")
    suspend fun tenantsNotOwnedBy(ownerSub: String): List<String>
}
