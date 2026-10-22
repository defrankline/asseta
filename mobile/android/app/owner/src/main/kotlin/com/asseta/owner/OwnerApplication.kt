package com.asseta.owner

import android.app.Application
import com.asseta.core.ui.AppRole
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.AssetaContainerOwner
import com.asseta.owner.push.PushNotifier
import com.asseta.owner.ui.map.MapSetup

class OwnerApplication : Application(), AssetaContainerOwner {
    override val container: AssetaAppContainer by lazy { AssetaAppContainer(this, AppRole.OWNER, BuildConfig.OIDC_REDIRECT_SCHEME) }

    val graph: OwnerGraph by lazy { OwnerGraph(this, container) }

    override fun onCreate() {
        super.onCreate()
        container.sessionHooks = graph.sessionHooks
        PushNotifier.ensureChannels(this)
        MapSetup.init(this)
    }
}
