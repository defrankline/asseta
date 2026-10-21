package com.asseta.supervisor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.asseta.core.ui.AssetaContainerOwner
import com.asseta.core.ui.session.AssetaSessionApp
import com.asseta.core.ui.theme.AssetaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as AssetaContainerOwner).container
        setContent { AssetaTheme { AssetaSessionApp(container) } }
    }
}
