package com.asseta.core.database

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.asseta.core.model.ClientOperationStatus
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/** On-device: the database file is SQLCipher-encrypted (no plaintext SQLite header) and readable with the key. */
@RunWith(AndroidJUnit4::class)
class EncryptedDatabaseTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val fileName = "encrypted-test-${UUID.randomUUID()}.db"

    @After
    fun cleanUp() {
        context.deleteDatabase(fileName)
    }

    @Test
    fun writesAreEncryptedAtRest() = runTest {
        val passphrase = ByteArray(32) { it.toByte() }
        val db = AssetaDatabaseFactory.create(context, passphrase, fileName)
        val id = UUID.randomUUID().toString()
        db.clientOperationDao().enqueue(
            ClientOperationEntity(id, "t", "CREATE", "e", "x", "{\"secret\":\"evidence\"}", null, 1L,
                ClientOperationStatus.PENDING, 0, null, null),
        )
        db.close()

        val header = context.getDatabasePath(fileName).readBytes().copyOfRange(0, 16)
        assertFalse(String(header, Charsets.US_ASCII).startsWith("SQLite format 3"))

        val reopened = AssetaDatabaseFactory.create(context, passphrase, fileName)
        assertEquals(id, reopened.clientOperationDao().findById(id)!!.id)
        reopened.close()
    }
}
