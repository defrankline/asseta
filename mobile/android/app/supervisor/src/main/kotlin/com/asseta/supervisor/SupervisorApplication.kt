package com.asseta.supervisor

import android.app.Application
import com.asseta.core.ui.AppRole
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.AssetaContainerOwner

class SupervisorApplication : Application(), AssetaContainerOwner {
    override val container: AssetaAppContainer by lazy { AssetaAppContainer(this, AppRole.SUPERVISOR, BuildConfig.OIDC_REDIRECT_SCHEME) }
}
