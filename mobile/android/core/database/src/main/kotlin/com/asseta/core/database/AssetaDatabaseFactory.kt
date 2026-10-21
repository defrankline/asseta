package com.asseta.core.database

import android.content.Context
import androidx.room.Room
import net.zetetic.database.sqlcipher.SupportOpenHelperFactory

/** Opens the SQLCipher-encrypted Room database. The passphrase comes from the Keystore-wrapped provider. */
object AssetaDatabaseFactory {
    @Volatile private var nativeLoaded = false

    fun create(context: Context, passphrase: ByteArray, fileName: String = AssetaDatabase.FILE_NAME): AssetaDatabase {
        loadNative()
        return Room.databaseBuilder(context.applicationContext, AssetaDatabase::class.java, fileName)
            .openHelperFactory(SupportOpenHelperFactory(passphrase))
            .addMigrations(*AssetaMigrations.ALL)
            .build()
    }

    @Synchronized
    private fun loadNative() {
        if (!nativeLoaded) {
            System.loadLibrary("sqlcipher")
            nativeLoaded = true
        }
    }
}
