package com.asseta.supervisor

import android.app.Application
import com.asseta.core.model.MeResponse
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.work.SyncHost
import com.asseta.core.ui.AppRole
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.AssetaContainerOwner
import com.asseta.core.ui.session.SessionHooks
import com.asseta.supervisor.push.SupervisorMessagingService
import com.asseta.supervisor.ui.FieldTexts
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext

class SupervisorApplication : Application(), AssetaContainerOwner, SyncHost {
    override val container: AssetaAppContainer by lazy { AssetaAppContainer(this, AppRole.SUPERVISOR, BuildConfig.OIDC_REDIRECT_SCHEME) }

    val field: FieldGraph by lazy { FieldGraph(this, container) }

    override fun onCreate() {
        super.onCreate()
        // Sign-out keeps unsynced work encrypted on the phone; the confirmation says how much is waiting.
        container.sessionHooks = object : SessionHooks {
            // Another user's synced field data is reset before this user's home shows (their unsynced work is held).
            override suspend fun beforeHome(me: MeResponse) {
                val account = container.authManager.account() ?: return
                withContext(Dispatchers.IO) { field.accounts.claimAll(account) }
                field.online.reset() // the in-memory notification list belongs to whoever was signed in before
            }

            // Push: this phone stops receiving the user's notifications (best effort, bounded by the sign-out timeout).
            override suspend fun beforeSignOut() = field.push.unregister()

            override fun onSignedOut() {
                field.pushTap.value = null
                field.push.forget()
            }

            override suspend fun signOutConfirmation(): String {
                val tenantId = container.tenantStore.tenantId()
                val unsynced = tenantId?.let {
                    withContext(Dispatchers.IO) { runCatching { field.repository.observeUnsynced(it).first().size }.getOrDefault(0) }
                } ?: 0
                return FieldTexts.signOutMessage(unsynced)
            }
        }
        SupervisorMessagingService.notifier.ensureChannels(this)
    }

    override fun syncTenantId(): String? =
        if (container.authManager.signedIn.value) container.tenantStore.tenantId() else null

    override suspend fun runSync(tenantId: String): SyncReport = field.engine.sync(tenantId)
}
