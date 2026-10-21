package com.asseta.core.security

/** Stores the serialized OIDC session (tokens) encrypted with a Keystore key. Never logged or backed up. */
class SecureTokenStore(private val store: SecretFileStore) {
    fun read(): String? = store.read(FILE_NAME)?.toString(Charsets.UTF_8)

    fun write(serializedSession: String) = store.write(FILE_NAME, serializedSession.toByteArray(Charsets.UTF_8))

    fun clear() = store.delete(FILE_NAME)

    /** Device wipe: deletes the session and destroys its Keystore key. */
    fun destroy() = store.destroy(FILE_NAME)

    private companion object {
        const val FILE_NAME = "auth_session.bin"
    }
}
