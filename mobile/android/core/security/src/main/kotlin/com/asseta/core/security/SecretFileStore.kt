package com.asseta.core.security

import java.io.File

/**
 * Persists encrypted blobs as files (atomic replace). Lives in `noBackupFilesDir` so wrapped secrets are
 * never included in cloud/device backups (the Keystore key that unwraps them does not migrate anyway).
 */
class SecretFileStore(private val directory: File, private val cipher: SecretCipher) {

    fun read(name: String): ByteArray? {
        val file = File(directory, name)
        return if (file.exists()) cipher.decrypt(file.readBytes()) else null
    }

    fun write(name: String, plaintext: ByteArray) {
        directory.mkdirs()
        val target = File(directory, name)
        val tmp = File(directory, "$name.tmp")
        tmp.writeBytes(cipher.encrypt(plaintext))
        check(tmp.renameTo(target)) { "Could not persist secret '$name'" }
    }

    fun delete(name: String) {
        File(directory, name).delete()
    }

    /** Deletes the wrapped file and destroys the Keystore key that wraps it (device wipe). */
    fun destroy(name: String) {
        delete(name)
        cipher.destroyKey()
    }
}
