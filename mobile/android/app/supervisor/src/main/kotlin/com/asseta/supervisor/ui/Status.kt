package com.asseta.supervisor.ui

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.R
import com.asseta.core.ui.R as CoreR

/** Whether the phone has a network with internet right now (updates as it changes). */
@Composable
fun rememberOnline(): Boolean {
    val context = LocalContext.current
    val manager = remember { context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager }
    var online by remember {
        mutableStateOf(manager.getNetworkCapabilities(manager.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true)
    }
    DisposableEffect(manager) {
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { online = true }
            override fun onLost(network: Network) { online = manager.activeNetwork != null && manager.activeNetwork != network }
        }
        manager.registerDefaultNetworkCallback(callback)
        onDispose { manager.unregisterNetworkCallback(callback) }
    }
    return online
}

/** Sync state of a local record: symbol and text in the state's colour (the iOS `SyncStateLabel`). */
@Composable
fun SyncStateLabel(status: ClientOperationStatus) {
    val p = palette
    val color = when (status) {
        ClientOperationStatus.ACKED -> p.live
        ClientOperationStatus.FAILED, ClientOperationStatus.CONFLICT -> p.offline
        ClientOperationStatus.QUARANTINED -> p.warning
        else -> p.secondaryText
    }
    val icon = when (status) {
        ClientOperationStatus.ACKED -> R.drawable.ic_check_circle
        ClientOperationStatus.FAILED -> R.drawable.ic_rejected
        ClientOperationStatus.CONFLICT -> R.drawable.ic_warning
        ClientOperationStatus.QUARANTINED -> R.drawable.ic_pause_circle
        else -> CoreR.drawable.ic_clock
    }
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(painterResource(icon), contentDescription = null, tint = color, modifier = Modifier.size(14.dp))
        Text(FieldTexts.syncState(status), style = MaterialTheme.typography.labelMedium, color = color)
    }
}
