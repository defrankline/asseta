package com.asseta.core.database

import android.content.Context
import androidx.room.withTransaction

/**
 * Opens the encrypted database lazily and can close and delete it (device revocation wipe). Callers must fetch DAOs
 * through [get] each time instead of caching them, so a wiped database is never used again.
 */
class DatabaseHolder(
    context: Context,
    private val passphrase: () -> ByteArray,
    private val fileName: String = AssetaDatabase.FILE_NAME,
) {
    private val appContext = context.applicationContext

    @Volatile private var db: AssetaDatabase? = null

    fun get(): AssetaDatabase = db ?: synchronized(this) {
        db ?: AssetaDatabaseFactory.create(appContext, passphrase(), fileName).also { db = it }
    }

    /** Closes and deletes the database file (and its WAL/SHM journals). */
    @Synchronized
    fun closeAndDelete() {
        db?.close()
        db = null
        appContext.deleteDatabase(fileName)
    }
}

/** Runs [block] in one Room transaction (re-exported so feature modules need no direct room-ktx dependency). */
suspend fun <R> AssetaDatabase.inTransaction(block: suspend () -> R): R = withTransaction(block)
