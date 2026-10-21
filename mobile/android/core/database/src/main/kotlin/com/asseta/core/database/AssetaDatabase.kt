package com.asseta.core.database

import androidx.room.AutoMigration
import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(
    entities = [
        ClientOperationEntity::class,
        ClientOperationDependencyEntity::class,
        AttachmentEntity::class,
        JobEntity::class,
        MachineEntity::class,
        ReferenceRecordEntity::class,
        PolicySnapshotEntity::class,
        SyncStateEntity::class,
        MeterCaptureEntity::class,
        WorkLogEntryEntity::class,
        ExpenseCategoryEntity::class,
        CashCustodyBalanceEntity::class,
    ],
    version = AssetaDatabase.VERSION,
    exportSchema = true,
    autoMigrations = [
        AutoMigration(from = 1, to = 2, spec = AssetaMigrations.V1ToV2::class),
        AutoMigration(from = 2, to = 3),
    ],
)
@TypeConverters(Converters::class)
abstract class AssetaDatabase : RoomDatabase() {
    abstract fun clientOperationDao(): ClientOperationDao
    abstract fun fieldDataDao(): FieldDataDao
    abstract fun syncStateDao(): SyncStateDao
    abstract fun evidenceDao(): EvidenceDao
    abstract fun financeDataDao(): FinanceDataDao

    companion object {
        const val VERSION = 3
        const val FILE_NAME = "asseta.db"
    }
}
