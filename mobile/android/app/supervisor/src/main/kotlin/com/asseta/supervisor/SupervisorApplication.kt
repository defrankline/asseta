package com.asseta.supervisor

import android.app.Application
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.work.SyncHost
import com.asseta.core.ui.AppRole
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.AssetaContainerOwner

class SupervisorApplication : Application(), AssetaContainerOwner, SyncHost {
    override val container: AssetaAppContainer by lazy { AssetaAppContainer(this, AppRole.SUPERVISOR, BuildConfig.OIDC_REDIRECT_SCHEME) }

    val field: FieldGraph by lazy { FieldGraph(this, container) }

    override fun syncTenantId(): String? =
        if (container.authManager.signedIn.value) container.tenantStore.tenantId() else null

    override suspend fun runSync(tenantId: String): SyncReport = field.engine.sync(tenantId)
}
