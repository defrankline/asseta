package com.asseta.core.database

import androidx.room.AutoMigration
import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(
    entities = [
        ClientOperationEntity::class,
        ClientOperationDependencyEntity::class,
        ClientOperationAttachmentEntity::class,
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
        ReadSnapshotEntity::class,
        InboxRecordEntity::class,
    ],
    version = AssetaDatabase.VERSION,
    exportSchema = true,
    autoMigrations = [
        AutoMigration(from = 1, to = 2, spec = AssetaMigrations.V1ToV2::class),
        AutoMigration(from = 2, to = 3),
        AutoMigration(from = 3, to = 4),
        AutoMigration(from = 4, to = 5, spec = AssetaMigrations.V4ToV5::class),
        AutoMigration(from = 6, to = 7),
        AutoMigration(from = 7, to = 8),
    ],
)
@TypeConverters(Converters::class)
abstract class AssetaDatabase : RoomDatabase() {
    abstract fun clientOperationDao(): ClientOperationDao
    abstract fun fieldDataDao(): FieldDataDao
    abstract fun syncStateDao(): SyncStateDao
    abstract fun evidenceDao(): EvidenceDao
    abstract fun financeDataDao(): FinanceDataDao
    abstract fun readSnapshotDao(): ReadSnapshotDao
    abstract fun inboxDao(): InboxDao

    companion object {
        const val VERSION = 8
        const val FILE_NAME = "asseta.db"
    }
}
