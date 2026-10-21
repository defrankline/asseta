package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

/** Server-owned expense category (v3). Deactivated categories are kept with `is_active = 0` and hidden from pickers. */
@Entity(tableName = "expense_category", indices = [Index(value = ["tenant_id", "is_active"])])
data class ExpenseCategoryEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "code") val code: String,
    @ColumnInfo(name = "name") val name: String,
    @ColumnInfo(name = "is_active") val isActive: Boolean,
    @ColumnInfo(name = "sync_revision") val syncRevision: Long,
    @ColumnInfo(name = "version") val version: Long,
)

/**
 * The supervisor's server-computed cash custody per currency (v3), replaced as a whole on every pull. Amounts are
 * exact decimal strings (never REAL columns).
 */
@Entity(tableName = "cash_custody_balance", primaryKeys = ["tenant_id", "currency"])
data class CashCustodyBalanceEntity(
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "currency") val currency: String,
    @ColumnInfo(name = "staff_member_id") val staffMemberId: String,
    @ColumnInfo(name = "outstanding") val outstanding: String,
    @ColumnInfo(name = "claimed_unverified_handovers") val claimedUnverifiedHandovers: String,
    @ColumnInfo(name = "pending_spending") val pendingSpending: String,
    @ColumnInfo(name = "as_of") val asOf: Long,
    @ColumnInfo(name = "received_at") val receivedAt: Long,
)

/** Server-owned finance reference data; nothing here is ever pushed back. */
@Dao
abstract class FinanceDataDao {
    @Query("SELECT sync_revision FROM expense_category WHERE id = :id")
    protected abstract suspend fun categoryRevision(id: String): Long?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    protected abstract suspend fun putCategory(category: ExpenseCategoryEntity)

    /** Upsert by sync revision: an older (lookback replay) revision never overwrites a newer one. */
    @Transaction
    open suspend fun upsertCategories(categories: List<ExpenseCategoryEntity>): Int = categories.count { c ->
        val current = categoryRevision(c.id)
        (current == null || c.syncRevision >= current).also { if (it) putCategory(c) }
    }

    /** Bootstrap ships the full active set: categories no longer delivered are dropped. */
    @Query("DELETE FROM expense_category WHERE tenant_id = :tenantId AND id NOT IN (:keep)")
    abstract suspend fun deleteCategoriesNotIn(tenantId: String, keep: List<String>): Int

    @Query("DELETE FROM expense_category WHERE tenant_id = :tenantId")
    abstract suspend fun deleteAllCategories(tenantId: String): Int

    @Query("SELECT * FROM expense_category WHERE tenant_id = :tenantId AND is_active = 1 ORDER BY name COLLATE NOCASE, code")
    abstract fun observeActiveCategories(tenantId: String): Flow<List<ExpenseCategoryEntity>>

    @Query("SELECT * FROM expense_category WHERE id = :id")
    abstract suspend fun category(id: String): ExpenseCategoryEntity?

    @Query("DELETE FROM cash_custody_balance WHERE tenant_id = :tenantId")
    protected abstract suspend fun clearCustody(tenantId: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    protected abstract suspend fun insertCustody(rows: List<CashCustodyBalanceEntity>)

    /** The server sends the current custody (not a delta): replace the tenant's rows atomically. */
    @Transaction
    open suspend fun replaceCustody(tenantId: String, rows: List<CashCustodyBalanceEntity>) {
        clearCustody(tenantId)
        if (rows.isNotEmpty()) insertCustody(rows)
    }

    @Query("SELECT * FROM cash_custody_balance WHERE tenant_id = :tenantId ORDER BY currency")
    abstract fun observeCustody(tenantId: String): Flow<List<CashCustodyBalanceEntity>>

    @Query("SELECT * FROM cash_custody_balance WHERE tenant_id = :tenantId ORDER BY currency")
    abstract suspend fun custody(tenantId: String): List<CashCustodyBalanceEntity>
}
