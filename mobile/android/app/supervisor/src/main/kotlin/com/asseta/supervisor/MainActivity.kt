package com.asseta.supervisor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.asseta.core.ui.session.AssetaSessionApp
import com.asseta.core.ui.theme.AssetaTheme
import com.asseta.supervisor.ui.SupervisorHome

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as SupervisorApplication
        setContent {
            AssetaTheme {
                AssetaSessionApp(app.container) { ready, onSwitchTenant, modifier ->
                    SupervisorHome(app.field, ready.selectedTenantId!!, onSwitchTenant, modifier)
                }
            }
        }
    }
}
