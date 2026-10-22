package com.asseta.owner

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.model.TenantAccessState
import com.asseta.core.ui.session.AssetaSessionApp
import com.asseta.core.ui.theme.AssetaTheme
import com.asseta.owner.push.PushNotifier
import com.asseta.owner.ui.OwnerHome
import com.asseta.owner.ui.OwnerSession

class MainActivity : ComponentActivity() {
    private val graph get() = (application as OwnerApplication).graph

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) handleNotificationTap(intent)
        val app = application as OwnerApplication
        setContent {
            AssetaTheme {
                AssetaSessionApp(app.container) { ready, _, modifier ->
                    val tenant = ready.selectedTenant!!
                    val session = OwnerSession(
                        tenantId = tenant.tenantId.toString(),
                        tenantName = tenant.name,
                        permissions = tenant.permissions.toSet(),
                        readOnly = tenant.accessState == TenantAccessState.READ_ONLY,
                    )
                    OwnerHome(app.graph, session, modifier)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleNotificationTap(intent)
    }

    /** Push taps (system tray or our own notification) carry the FCM data keys as extras. */
    private fun handleNotificationTap(intent: Intent?) {
        val extras = intent?.extras ?: return
        val data = PushNotifier.DATA_KEYS.associateWith { extras.getString(it) }
        DeepLinkRouter.fromPush(data)?.let { graph.pendingDeepLink.value = it }
    }
}
