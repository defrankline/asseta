package com.asseta.core.ui

import android.content.Context
import com.asseta.core.auth.AuthConfig
import com.asseta.core.auth.AuthManager
import com.asseta.core.auth.SelectedTenantStore
import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AssetaDatabaseFactory
import com.asseta.core.network.AssetaApi
import com.asseta.core.network.NetworkFactory
import com.asseta.core.security.SecurityComponents

/**
 * Manual dependency graph shared by both apps (one instance per process, created in Application).
 * Kept explicit instead of a DI framework while the graph is this small.
 *
 * [oidcRedirectScheme] comes from the app module's BuildConfig (`com.asseta.supervisor` / `com.asseta.owner`),
 * matching that app's AppAuth `appAuthRedirectScheme` manifest placeholder.
 */
class AssetaAppContainer(context: Context, val role: AppRole, private val oidcRedirectScheme: String) {
    private val appContext = context.applicationContext
    private val security = SecurityComponents(appContext)

    val authManager: AuthManager by lazy {
        AuthManager(appContext, AuthConfig.fromBuildConfig(oidcRedirectScheme), security.tokenStore)
    }

    val tenantStore: SelectedTenantStore by lazy { SelectedTenantStore(appContext) }

    val api: AssetaApi by lazy {
        NetworkFactory.defaultApi(NetworkFactory.okHttpClient(authManager, tenantStore))
    }

    /** Encrypted local database; opened on first use (off the main thread) by later-gate features. */
    val database: AssetaDatabase by lazy {
        AssetaDatabaseFactory.create(appContext, security.databasePassphraseProvider.getOrCreatePassphrase())
    }
}

/** Implemented by each app's Application so shared UI can reach the container. */
interface AssetaContainerOwner {
    val container: AssetaAppContainer
}
