package com.asseta.core.sync

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.DatabaseHolder
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.security.SecurityComponents
import com.asseta.core.sync.engine.DeviceWipe
import com.asseta.core.sync.evidence.EncryptedEvidenceStore
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.UUID

/** On device (real Keystore + SQLCipher): evidence is encrypted at rest and the revocation wipe removes everything. */
@RunWith(AndroidJUnit4::class)
class DeviceWipeTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()

    @Test
    fun evidenceEncryptedAndWipeRemovesDatabaseKeysAndFiles() = runBlocking {
        val security = SecurityComponents(context)
        val dbName = "wipe-test-${UUID.randomUUID()}.db"
        val holder = DatabaseHolder(context, { security.databasePassphraseProvider.getOrCreatePassphrase() }, dbName)
        val dir = File(context.noBackupFilesDir, "evidence-test-${UUID.randomUUID()}")
        val evidence = EncryptedEvidenceStore(dir, { security.evidenceKey.getOrCreate() })

        val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte()) + ByteArray(2048) { it.toByte() }
        val name = evidence.write(jpeg)
        val onDisk = File(dir, name).readBytes()
        assertFalse(onDisk.toList().windowed(16).any { it == jpeg.copyOfRange(0, 16).toList() })
        assertArrayEquals(jpeg, evidence.read(name))

        val id = UUID.randomUUID().toString()
        holder.get().clientOperationDao().enqueue(
            ClientOperationEntity(id, "t", "METER_CAPTURE", "e", "x", "{}", null, 1, ClientOperationStatus.PENDING, 0, null, null),
        )
        val deviceId = security.deviceIdStore.getOrCreate()

        DeviceWipe(listOf({ _ -> holder.closeAndDelete() }, { _ -> evidence.wipeAll() }, { _ -> security.wipeLocalSecrets() })).wipe("revoked")

        assertFalse(context.getDatabasePath(dbName).exists())
        assertFalse(dir.exists())
        assertNull(security.tokenStore.read())
        assertEquals(deviceId, security.deviceIdStore.getOrCreate()) // device identity survives so revocation sticks
        assertNull(holder.get().clientOperationDao().findById(id)) // a fresh, empty database with a new key
        holder.closeAndDelete()
    }
}
