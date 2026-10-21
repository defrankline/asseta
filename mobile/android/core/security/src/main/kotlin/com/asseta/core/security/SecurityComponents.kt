package com.asseta.core.security

import android.content.Context
import java.io.File
import java.util.UUID

/** Factory wiring the Keystore-backed stores. Separate keys per purpose limit blast radius. */
class SecurityComponents(context: Context) {
    private val dir = File(context.noBackupFilesDir, "asseta_secrets")

    val databasePassphraseProvider: DatabasePassphraseProvider by lazy {
        DatabasePassphraseProvider(SecretFileStore(dir, KeystoreSecretCipher("asseta.db.passphrase.v1")))
    }

    val tokenStore: SecureTokenStore by lazy { SecureTokenStore(SecretFileStore(dir, KeystoreSecretCipher("asseta.auth.session.v1"))) }

    /** AES-256 key for evidence files (photos, signatures) at rest, wrapped by its own Keystore key. */
    val evidenceKey: WrappedRandomKey by lazy {
        WrappedRandomKey(SecretFileStore(dir, KeystoreSecretCipher("asseta.evidence.key.v1")), "evidence_key.bin")
    }

    val deviceIdStore: DeviceIdStore by lazy {
        DeviceIdStore(SecretFileStore(dir, KeystoreSecretCipher("asseta.device.id.v1"))) { UUID.randomUUID().toString() }
    }

    /**
     * Device revocation wipe of secrets: database passphrase, evidence key and tokens (files and their Keystore keys).
     * The device id is kept on purpose so a revoked device stays revoked (the server refuses re-registration).
     */
    fun wipeLocalSecrets() {
        tokenStore.destroy()
        databasePassphraseProvider.destroy()
        evidenceKey.destroy()
    }
}
