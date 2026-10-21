package com.asseta.core.database

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(entities = [ClientOperationEntity::class], version = AssetaDatabase.VERSION, exportSchema = true)
@TypeConverters(Converters::class)
abstract class AssetaDatabase : RoomDatabase() {
    abstract fun clientOperationDao(): ClientOperationDao

    companion object {
        const val VERSION = 1
        const val FILE_NAME = "asseta.db"
    }
}
