package com.asseta.core.security

import java.security.SecureRandom

/**
 * A random data key generated once and stored only Keystore-wrapped (e.g. the evidence-file key). Like the database
 * passphrase it is never silently regenerated while a wrapped copy exists, which would orphan encrypted evidence.
 */
class WrappedRandomKey(
    private val store: SecretFileStore,
    private val fileName: String,
    private val sizeBytes: Int = 32,
    private val random: SecureRandom = SecureRandom(),
) {
    @Synchronized
    fun getOrCreate(): ByteArray {
        store.read(fileName)?.let { return it }
        val key = ByteArray(sizeBytes).also(random::nextBytes)
        store.write(fileName, key)
        return key.copyOf()
    }

    @Synchronized
    fun destroy() = store.destroy(fileName)
}

/** Stable random device identity (UUID), Keystore-protected. Survives a revocation wipe so revocation sticks. */
class DeviceIdStore(private val store: SecretFileStore, private val newId: () -> String) {
    @Synchronized
    fun getOrCreate(): String {
        store.read(FILE_NAME)?.let { return it.toString(Charsets.UTF_8) }
        val id = newId()
        store.write(FILE_NAME, id.toByteArray(Charsets.UTF_8))
        return id
    }

    private companion object {
        const val FILE_NAME = "device_id.bin"
    }
}
