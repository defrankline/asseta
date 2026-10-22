package com.asseta.owner.ui.settings

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.NotificationMatrix
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard

@Composable
fun SettingsScreen(vm: SettingsViewModel, online: Boolean, tenantName: String) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val actions = LocalSessionActions.current
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) vm.enablePush() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ui.message?.let { item { Text(it, color = MaterialTheme.colorScheme.primary) } }
        ui.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item {
            SectionCard("Priority notifications (push)") {
                Text("Choose which notifications are pushed to your phone. In-app notifications are always kept; locked rows are required by your company.", style = MaterialTheme.typography.bodySmall)
                if (!online) Text("Connect to change these settings.", color = MaterialTheme.colorScheme.error)
                if (ui.loading) Text("Loading…")
                ui.cells.groupBy { it.category }.forEach { (category, cells) ->
                    Text(OwnerFormat.humanize(category), style = MaterialTheme.typography.titleSmall)
                    cells.forEach { c ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(OwnerFormat.humanize(c.severity) + if (c.locked) " (required)" else "", Modifier.weight(1f))
                            Switch(
                                checked = c.push,
                                onCheckedChange = { vm.toggle(c.category, c.severity, it) },
                                enabled = online && !c.locked,
                                modifier = Modifier.semantics { contentDescription = "Push for ${OwnerFormat.humanize(category)} ${OwnerFormat.humanize(c.severity)}" },
                            )
                        }
                    }
                }
                if (ui.cells.isNotEmpty() && ui.cells.none { it.severity in NotificationMatrix.SEVERITIES }) Text("No configurable rows.")
                Button(onClick = vm::save, enabled = online && ui.dirty && !ui.saving) { Text(if (ui.saving) "Saving…" else "Save") }
            }
        }
        item {
            SectionCard("Push on this device") {
                KeyValue("Provider", vm.pushProvider)
                if (vm.pushAvailable) {
                    OutlinedButton(enabled = online, onClick = {
                        if (Build.VERSION.SDK_INT >= 33) permission.launch(Manifest.permission.POST_NOTIFICATIONS) else vm.enablePush()
                    }) { Text("Enable push notifications") }
                } else {
                    Text("Push is not configured for this build. You still get notifications in the inbox and live while the app is open.", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        item {
            SectionCard("My devices") {
                if (ui.devices.isEmpty()) Text("No devices registered for push.")
                ui.devices.forEach { d ->
                    Column {
                        Text("${d.deviceLabel ?: d.platform} · ${OwnerFormat.humanize(d.app)} · …${d.tokenHint}", style = MaterialTheme.typography.bodyMedium)
                        Text("Registered ${OwnerFormat.dateTime(d.lastRegisteredAt, java.time.ZoneId.systemDefault())}", style = MaterialTheme.typography.bodySmall)
                        if (d.active) TextButton(onClick = { vm.deactivate(d.id.toString()) }, enabled = online) { Text("Stop push to this device") }
                    }
                }
            }
        }
        item {
            SectionCard("Account") {
                KeyValue("Company", tenantName)
                Text("Saved data for offline viewing is kept for up to 7 days and is deleted when you sign out.", style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = actions.switchTenant) { Text("Switch company") }
                Button(onClick = actions.signOut) { Text("Sign out") }
            }
        }
    }
}
