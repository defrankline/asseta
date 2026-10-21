package com.asseta.owner

import android.app.Application
import com.asseta.core.ui.AppRole
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.AssetaContainerOwner

class OwnerApplication : Application(), AssetaContainerOwner {
    override val container: AssetaAppContainer by lazy { AssetaAppContainer(this, AppRole.OWNER, BuildConfig.OIDC_REDIRECT_SCHEME) }
}
