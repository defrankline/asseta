package com.asseta.core.database

import android.content.Context
import androidx.room.Room
import com.asseta.core.model.SyncAccount
import net.zetetic.database.sqlcipher.SupportOpenHelperFactory

/** Opens the SQLCipher-encrypted Room database. The passphrase comes from the Keystore-wrapped provider. */
object AssetaDatabaseFactory {
    @Volatile private var nativeLoaded = false

    /** [legacyOwner] owns rows written before v6 (the user signed in when the app started; see AssetaMigrations.V5ToV6). */
    fun create(
        context: Context,
        passphrase: ByteArray,
        fileName: String = AssetaDatabase.FILE_NAME,
        legacyOwner: SyncAccount? = null,
    ): AssetaDatabase {
        loadNative()
        return Room.databaseBuilder(context.applicationContext, AssetaDatabase::class.java, fileName)
            .openHelperFactory(SupportOpenHelperFactory(passphrase))
            .addMigrations(*AssetaMigrations.all(legacyOwner))
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
