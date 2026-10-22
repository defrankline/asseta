package com.asseta.core.ui

import android.content.Context
import com.asseta.core.auth.AuthConfig
import com.asseta.core.auth.AuthManager
import com.asseta.core.auth.SelectedTenantStore
import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.DatabaseHolder
import com.asseta.core.network.AssetaApi
import com.asseta.core.network.NetworkFactory
import com.asseta.core.security.SecurityComponents
import com.asseta.core.ui.session.NoSessionHooks
import com.asseta.core.ui.session.SessionHooks
import com.asseta.core.ui.session.SessionNotice

/**
 * Manual dependency graph shared by both apps (one instance per process, created in Application).
 * Kept explicit instead of a DI framework while the graph is this small.
 *
 * [oidcRedirectScheme] comes from the app module's BuildConfig (`com.asseta.supervisor` / `com.asseta.owner`),
 * matching that app's AppAuth `appAuthRedirectScheme` manifest placeholder.
 */
class AssetaAppContainer(context: Context, val role: AppRole, private val oidcRedirectScheme: String) {
    private val appContext = context.applicationContext
    val security = SecurityComponents(appContext)

    /** Forced sign-out explanations (device revocation wipe) shown on the login screen. */
    val sessionNotice: SessionNotice by lazy { SessionNotice(appContext) }

    val authManager: AuthManager by lazy {
        AuthManager(appContext, AuthConfig.fromBuildConfig(oidcRedirectScheme), security.tokenStore)
    }

    /** App-specific session reactions (set once in Application.onCreate; default: none). */
    @Volatile var sessionHooks: SessionHooks = NoSessionHooks

    val tenantStore: SelectedTenantStore by lazy { SelectedTenantStore(appContext) }

    val api: AssetaApi by lazy {
        NetworkFactory.defaultApi(NetworkFactory.okHttpClient(authManager, tenantStore))
    }

    /** Encrypted local database holder; can be closed and deleted by the device-revocation wipe. */
    val databaseHolder: DatabaseHolder by lazy {
        DatabaseHolder(appContext, { security.databasePassphraseProvider.getOrCreatePassphrase() })
    }

    /** Encrypted local database; opened on first use (off the main thread). Fetch it per use, never cache it. */
    val database: AssetaDatabase get() = databaseHolder.get()
}

/** Implemented by each app's Application so shared UI can reach the container. */
interface AssetaContainerOwner {
    val container: AssetaAppContainer
}
