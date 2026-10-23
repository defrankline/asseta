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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.NotificationMatrix
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard

/** Settings wording shared with iOS (`SettingsView`). */
object SettingsText {
    const val MATRIX_TITLE = "Push priorities"
    const val MATRIX_FOOTER = "Choose which notifications reach this phone as push. Locked switches are required by Asseta. " +
        "Every notification stays in the in-app inbox."
    const val SAVED = "Notification settings saved."
    const val DEVICES_FOOTER = "Push notifications go to this phone for the company that is open. Signing out unregisters it."
    const val PUSH_UNAVAILABLE = "Push is not configured for this build. You still get notifications in the inbox and live while the app is open."
    const val OFFLINE_DATA = "Screens you have opened are kept encrypted on this phone for up to 7 days so you can look at them offline. " +
        "Saved data is clearly marked stale and can't be changed. Signing out erases it."
    const val SIGN_OUT_CONFIRM = "Sign out?"
    const val SIGN_OUT_ACTION = "Sign out and erase saved data"

    fun severityLabel(severity: String, locked: Boolean): String = OwnerFormat.humanize(severity) + if (locked) " (required)" else ""

    /** "This phone" status line. */
    fun pushStatus(available: Boolean, registered: Boolean, tenantName: String): String = when {
        !available -> "Not available in this build"
        registered -> "Registered for $tenantName"
        else -> "Not registered yet"
    }
}

@Composable
fun SettingsScreen(vm: SettingsViewModel, session: OwnerSession, online: Boolean) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val actions = LocalSessionActions.current
    var confirmSignOut by rememberSaveable { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) vm.enablePush() }
    // Routing is read live (never cached), so only connectivity and a read-only company block changes.
    val gate = MutationGate.check(online, DataSource.LIVE, permitted = true, tenantReadOnly = session.readOnly)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ui.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        if (session.features.notifications) item {
            SectionCard(SettingsText.MATRIX_TITLE) {
                if (ui.loading) Text("Loading…")
                ui.cells.groupBy { it.category }.forEach { (category, cells) ->
                    Text(NotificationMatrix.label(category), style = MaterialTheme.typography.titleSmall)
                    cells.forEach { c ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(SettingsText.severityLabel(c.severity, c.locked), Modifier.weight(1f))
                            Switch(
                                checked = c.push,
                                onCheckedChange = { vm.toggle(c.category, c.severity, it) },
                                enabled = gate is MutationCheck.Allowed && !c.locked,
                                modifier = Modifier.semantics { contentDescription = "Push for ${NotificationMatrix.label(category)}, ${OwnerFormat.humanize(c.severity)}" },
                            )
                        }
                    }
                }
                (gate as? MutationCheck.Blocked)?.let { FootNote(it.reason) }
                Button(onClick = vm::save, enabled = gate is MutationCheck.Allowed && ui.dirty && !ui.saving) { Text(if (ui.saving) "Saving…" else "Save") }
                ui.message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary) }
                FootNote(SettingsText.MATRIX_FOOTER)
            }
        }
        item {
            SectionCard("Push devices") {
                KeyValue("This phone", SettingsText.pushStatus(vm.pushAvailable, vm.pushRegistered, session.tenantName))
                KeyValue("Provider", vm.pushProvider)
                if (vm.pushAvailable) {
                    OutlinedButton(enabled = online, onClick = {
                        if (Build.VERSION.SDK_INT >= 33) permission.launch(Manifest.permission.POST_NOTIFICATIONS) else vm.enablePush()
                    }) { Text("Enable push notifications") }
                } else {
                    FootNote(SettingsText.PUSH_UNAVAILABLE)
                }
                if (ui.devices.isEmpty()) Text("No devices registered for push.", style = MaterialTheme.typography.bodySmall)
                ui.devices.forEach { d ->
                    Column {
                        Text("${d.deviceLabel ?: d.platform} · ${OwnerFormat.humanize(d.app)} · …${d.tokenHint}", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            (if (d.active) "Active" else "Inactive") + " · registered ${OwnerFormat.dateTime(d.lastRegisteredAt, java.time.ZoneId.systemDefault())}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        if (d.active) TextButton(onClick = { vm.deactivate(d.id.toString()) }, enabled = online) { Text("Stop push to this device") }
                    }
                }
                FootNote(SettingsText.DEVICES_FOOTER)
            }
        }
        item { SectionCard("Offline data") { FootNote(SettingsText.OFFLINE_DATA) } }
        item {
            SectionCard("Account") {
                KeyValue("Company", session.tenantName)
                if (session.userEmail.isNotEmpty()) KeyValue("Signed in as", session.userEmail)
                if (session.canSwitchTenant) OutlinedButton(onClick = actions.switchTenant) { Text("Switch company") }
                Button(
                    onClick = { confirmSignOut = true },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error, contentColor = MaterialTheme.colorScheme.onError),
                ) { Text("Sign out") }
            }
        }
    }
    if (confirmSignOut) {
        AlertDialog(
            onDismissRequest = { confirmSignOut = false },
            title = { Text(SettingsText.SIGN_OUT_CONFIRM) },
            confirmButton = {
                TextButton({ confirmSignOut = false; actions.signOut() }) { Text(SettingsText.SIGN_OUT_ACTION, color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton({ confirmSignOut = false }) { Text("Cancel") } },
        )
    }
}
