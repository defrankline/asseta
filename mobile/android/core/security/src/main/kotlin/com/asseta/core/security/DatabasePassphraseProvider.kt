package com.asseta.core.security

import java.security.SecureRandom

/**
 * Provides the SQLCipher passphrase: 32 random bytes generated once, stored only in Keystore-wrapped form.
 * If the wrapped passphrase exists but cannot be unwrapped (key invalidated, device restore), this throws
 * instead of silently creating a new key, because that would orphan unsynced outbox data.
 */
class DatabasePassphraseProvider(
    private val store: SecretFileStore,
    private val random: SecureRandom = SecureRandom(),
) {
    @Synchronized
    fun getOrCreatePassphrase(): ByteArray {
        store.read(FILE_NAME)?.let { return it }
        val passphrase = ByteArray(PASSPHRASE_BYTES).also(random::nextBytes)
        store.write(FILE_NAME, passphrase)
        return passphrase.copyOf()
    }

    private companion object {
        const val FILE_NAME = "db_passphrase.bin"
        const val PASSPHRASE_BYTES = 32
    }
}
