package com.asseta.owner

import android.content.Context
import com.asseta.core.domain.owner.DeepLink
import com.asseta.core.domain.owner.SnapshotPolicy
import com.asseta.core.model.MeResponse
import com.asseta.core.network.NetworkFactory
import com.asseta.core.network.RealtimeSocket
import com.asseta.core.network.TenantApi
import com.asseta.core.push.FcmPushTokenProvider
import com.asseta.core.push.NoOpPushTokenProvider
import com.asseta.core.push.PushRegistrar
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.session.SessionHooks
import com.asseta.owner.data.AndroidNetworkStatus
import com.asseta.owner.data.LiveUpdates
import com.asseta.owner.data.NetworkStatus
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.OwnerRepository
import com.asseta.owner.data.RoomSnapshotStore
import com.asseta.owner.data.SessionEvents
import com.asseta.owner.data.SnapshotStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch

/** Session-level signals raised by data loads, handled by the UI (which owns the session view model). */
enum class SessionSignal { TENANT_REVOKED, SESSION_ENDED }

/**
 * Owner app graph (manual DI) on top of the shared container. Read-mostly: online reads cached as bounded snapshots
 * in the SQLCipher database, live updates while foregrounded, optional FCM push. Sign-out wipes the cache.
 */
class OwnerGraph(context: Context, val container: AssetaAppContainer) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    val json = NetworkFactory.json
    val policy = SnapshotPolicy()

    val api: TenantApi by lazy {
        NetworkFactory.defaultTenantApi(NetworkFactory.okHttpClient(container.authManager, container.tenantStore))
    }

    val store: SnapshotStore = RoomSnapshotStore({ container.database }, policy)
    val network: NetworkStatus by lazy { AndroidNetworkStatus(appContext) }

    private val _signals = MutableSharedFlow<SessionSignal>(extraBufferCapacity = 4)
    val signals: SharedFlow<SessionSignal> = _signals.asSharedFlow()

    private val events = object : SessionEvents {
        override fun tenantRevoked(tenantId: String) { _signals.tryEmit(SessionSignal.TENANT_REVOKED) }
        override fun sessionEnded() { _signals.tryEmit(SessionSignal.SESSION_ENDED) }
    }

    val repository: OwnerRepository by lazy { OwnerRepository(api, store, json, policy, events) }

    fun data(tenantId: String) = OwnerData(repository, tenantId)

    val liveUpdates: LiveUpdates by lazy {
        LiveUpdates(RealtimeSocket(NetworkFactory.defaultBaseUrl, NetworkFactory.defaultAllowCleartext, container.authManager, json))
    }

    val push: PushRegistrar by lazy {
        val provider = if (FcmPushTokenProvider.isConfigured(appContext, BuildConfig.FCM_ENABLED)) FcmPushTokenProvider() else NoOpPushTokenProvider
        PushRegistrar(appContext, provider, { api }, BuildConfig.VERSION_NAME, PushRegistrar.APP_OWNER, "asseta_owner_push")
    }

    /** Pending deep link from a notification tap, consumed by the home once the tenant is ready. */
    val pendingDeepLink = MutableStateFlow<DeepLink?>(null)

    val sessionHooks = object : SessionHooks {
        override suspend fun beforeSignOut() = push.unregister()

        override fun onSignedOut() {
            pendingDeepLink.value = null
            push.forget()
            scope.launch { wipeLocalData() }
        }

        override fun onProfile(me: MeResponse) {
            val enterable = me.tenants.filter { it.accessState.canEnter }.map { it.tenantId.toString() }
            scope.launch {
                runCatching { store.keepOnlyTenants(enterable) }
                repository.purgeExpired()
            }
        }
    }

    /** Sign-out wipe: the encrypted database file (all snapshots) and cached files (e.g. map tiles). */
    private fun wipeLocalData() {
        runCatching { container.databaseHolder.closeAndDelete() }
        runCatching { appContext.cacheDir.listFiles()?.forEach { it.deleteRecursively() } }
    }

    fun onPushTokenRefreshed() {
        if (!container.authManager.signedIn.value || container.tenantStore.tenantId() == null) return
        scope.launch { runCatching { push.register() } }
    }
}
