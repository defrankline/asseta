package com.asseta.core.security

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** JVM AES-GCM stand-in for the Keystore cipher (Keystore is unavailable off-device). */
private class SoftwareCipher(private val key: SecretKey = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()) : SecretCipher {
    override fun encrypt(plaintext: ByteArray): ByteArray {
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
        return c.iv + c.doFinal(plaintext)
    }

    override fun decrypt(ciphertext: ByteArray): ByteArray {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, ciphertext.copyOfRange(0, 12)))
        return c.doFinal(ciphertext.copyOfRange(12, ciphertext.size))
    }
}

class SecretStoresTest {
    @get:Rule val tmp = TemporaryFolder()

    @Test
    fun `passphrase is generated once and stable`() {
        val store = SecretFileStore(tmp.root, SoftwareCipher())
        val provider = DatabasePassphraseProvider(store)
        val first = provider.getOrCreatePassphrase()
        assertEquals(32, first.size)
        assertArrayEquals(first, provider.getOrCreatePassphrase())
        assertArrayEquals(first, DatabasePassphraseProvider(store).getOrCreatePassphrase())
    }

    @Test
    fun `passphrase is not stored in plaintext`() {
        val provider = DatabasePassphraseProvider(SecretFileStore(tmp.root, SoftwareCipher()))
        val pass = provider.getOrCreatePassphrase()
        val onDisk = File(tmp.root, "db_passphrase.bin").readBytes()
        assertFalse(onDisk.toList().windowed(pass.size).any { it == pass.toList() })
    }

    @Test
    fun `unwrap failure is surfaced, never silently regenerated`() {
        DatabasePassphraseProvider(SecretFileStore(tmp.root, SoftwareCipher())).getOrCreatePassphrase()
        val otherKey = DatabasePassphraseProvider(SecretFileStore(tmp.root, SoftwareCipher()))
        assertThrows(AEADBadTagException::class.java) { otherKey.getOrCreatePassphrase() }
    }

    @Test
    fun `token store round trip and clear`() {
        val tokens = SecureTokenStore(SecretFileStore(tmp.root, SoftwareCipher()))
        assertNull(tokens.read())
        tokens.write("{\"refresh_token\":\"r\"}")
        assertEquals("{\"refresh_token\":\"r\"}", tokens.read())
        tokens.clear()
        assertNull(tokens.read())
    }

    @Test
    fun `wipe destroys passphrase and evidence key but a new one can be created`() {
        val store = SecretFileStore(tmp.root, SoftwareCipher())
        val provider = DatabasePassphraseProvider(store)
        val before = provider.getOrCreatePassphrase()
        val evidence = WrappedRandomKey(store, "evidence_key.bin")
        val key = evidence.getOrCreate()
        assertArrayEquals(key, evidence.getOrCreate())
        provider.destroy()
        evidence.destroy()
        assertNull(store.read("db_passphrase.bin"))
        assertNull(store.read("evidence_key.bin"))
        assertFalse(provider.getOrCreatePassphrase().contentEquals(before))
        assertFalse(evidence.getOrCreate().contentEquals(key))
    }

    @Test
    fun `device id is generated once and stable`() {
        val store = SecretFileStore(tmp.root, SoftwareCipher())
        var n = 0
        val ids = DeviceIdStore(store) { "device-${++n}" }
        assertEquals("device-1", ids.getOrCreate())
        assertEquals("device-1", DeviceIdStore(store) { "other" }.getOrCreate())
    }
}
