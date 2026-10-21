package com.asseta.core.security

/** Authenticated encryption of small secrets (passphrases, token blobs). Output embeds IV/nonce. */
interface SecretCipher {
    fun encrypt(plaintext: ByteArray): ByteArray
    fun decrypt(ciphertext: ByteArray): ByteArray
}
