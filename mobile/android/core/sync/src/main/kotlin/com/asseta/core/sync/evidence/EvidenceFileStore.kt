package com.asseta.core.sync.evidence

import java.io.File
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/** Evidence bytes (original JPEG / signature PNG) encrypted at rest in app-private, non-backed-up storage. */
interface EvidenceFiles {
    /** Stores [plaintext] encrypted; returns the opaque file name. */
    fun write(plaintext: ByteArray): String
    fun read(fileName: String): ByteArray
    fun delete(fileName: String)
    fun wipeAll()
}

/**
 * AES-256-GCM with a random data key that exists only Keystore-wrapped (see `SecurityComponents.evidenceKey`).
 * Format: [1 byte version][12 byte IV][ciphertext+tag]. The original bytes are never modified, only encrypted.
 */
class EncryptedEvidenceStore(
    private val directory: File,
    private val key: () -> ByteArray,
    private val random: SecureRandom = SecureRandom(),
) : EvidenceFiles {

    override fun write(plaintext: ByteArray): String {
        directory.mkdirs()
        val iv = ByteArray(IV_BYTES).also(random::nextBytes)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key(), "AES"), GCMParameterSpec(TAG_BITS, iv))
        val sealed = cipher.doFinal(plaintext)
        val name = "${UUID.randomUUID()}.bin"
        val tmp = File(directory, "$name.tmp")
        tmp.writeBytes(byteArrayOf(VERSION) + iv + sealed)
        check(tmp.renameTo(File(directory, name))) { "Could not persist evidence" }
        return name
    }

    override fun read(fileName: String): ByteArray {
        val bytes = File(directory, fileName).readBytes()
        check(bytes.isNotEmpty() && bytes[0] == VERSION) { "Unsupported evidence format" }
        val iv = bytes.copyOfRange(1, 1 + IV_BYTES)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key(), "AES"), GCMParameterSpec(TAG_BITS, iv))
        return cipher.doFinal(bytes, 1 + IV_BYTES, bytes.size - 1 - IV_BYTES)
    }

    override fun delete(fileName: String) {
        File(directory, fileName).delete()
    }

    override fun wipeAll() {
        directory.deleteRecursively()
    }

    private companion object {
        const val VERSION: Byte = 1
        const val IV_BYTES = 12
        const val TAG_BITS = 128
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}

object Sha256 {
    private const val HEX = "0123456789abcdef"

    /** Lowercase hex SHA-256 (the server's `^[0-9a-f]{64}$`). */
    fun hex(bytes: ByteArray): String = buildString(64) {
        MessageDigest.getInstance("SHA-256").digest(bytes).forEach { b ->
            append(HEX[(b.toInt() shr 4) and 0xF]).append(HEX[b.toInt() and 0xF])
        }
    }
}
