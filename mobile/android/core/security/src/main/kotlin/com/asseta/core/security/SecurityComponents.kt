package com.asseta.core.security

import android.content.Context
import java.io.File

/** Factory wiring the Keystore-backed stores. Separate keys per purpose limit blast radius. */
class SecurityComponents(context: Context) {
    private val dir = File(context.noBackupFilesDir, "asseta_secrets")

    val databasePassphraseProvider: DatabasePassphraseProvider by lazy {
        DatabasePassphraseProvider(SecretFileStore(dir, KeystoreSecretCipher("asseta.db.passphrase.v1")))
    }

    val tokenStore: SecureTokenStore by lazy {
        SecureTokenStore(SecretFileStore(dir, KeystoreSecretCipher("asseta.auth.session.v1")))
    }
}
