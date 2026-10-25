package com.asseta.supervisor

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.asseta.core.push.PushNotifier
import com.asseta.core.ui.session.AssetaSessionApp
import com.asseta.core.ui.theme.AssetaTheme
import com.asseta.supervisor.ui.SupervisorHome

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) handleNotificationTap(intent)
        val app = application as SupervisorApplication
        setContent {
            AssetaTheme {
                AssetaSessionApp(app.container) { ready, onSwitchTenant, modifier ->
                    SupervisorHome(app.field, ready.selectedTenant!!, ready.me.tenants.size, onSwitchTenant, modifier)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleNotificationTap(intent)
    }

    /** Push taps (system tray or our own notification) carry the FCM data keys as extras; the home opens the Inbox. */
    private fun handleNotificationTap(intent: Intent?) {
        val extras = intent?.extras ?: return
        if (PushNotifier.DATA_KEYS.none { extras.getString(it) != null }) return
        fun extra(key: String) = extras.getString(key)?.takeIf { it.isNotBlank() }
        (application as SupervisorApplication).field.pushTap.value =
            PushTap(extra("notification_id"), extra("kind"), extra("record_id"), extra("entity"), extra("entity_id"))
    }
}
