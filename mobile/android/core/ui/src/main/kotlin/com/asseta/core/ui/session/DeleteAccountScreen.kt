package com.asseta.core.ui.session

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.components.AssetaTopBar
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import kotlinx.coroutines.launch

/** Holds the [AccountDeletionFlow] across configuration changes; the call is not cancelled by a rotation. */
class AccountDeletionViewModel(val flow: AccountDeletionFlow) : ViewModel() {
    fun submit() { viewModelScope.launch { flow.submit() } }
    fun syncFirst() { viewModelScope.launch { flow.syncFirst() } }
    fun confirm() { viewModelScope.launch { flow.confirm() } }
}

/** The shell's "Delete my account" screen, wired to the session (call, wipe and sign-out) and the app's hooks. */
@Composable
internal fun DeleteAccountRoute(session: SessionViewModel, container: AssetaAppContainer, onClose: () -> Unit) {
    val context = LocalContext.current.applicationContext
    val vm: AccountDeletionViewModel = viewModel(key = "account-deletion") {
        AccountDeletionViewModel(
            AccountDeletionFlow(
                online = { isOnline(context) },
                unsyncedCount = { container.sessionHooks.unsyncedCount() },
                syncNow = { container.sessionHooks.syncNow() },
                delete = session::deleteAccount,
                onDeleted = { session.accountDeleted() },
            ),
        )
    }
    DeleteAccountScreen(vm, rememberIsOnline(), onClose)
}

@Composable
fun DeleteAccountScreen(vm: AccountDeletionViewModel, online: Boolean, onClose: () -> Unit) {
    val ui by vm.flow.ui.collectAsStateWithLifecycle()
    val busy = ui.step == DeletionStep.Deleting || ui.step == DeletionStep.Syncing || ui.step == DeletionStep.Done
    BackHandler(enabled = true) { if (!busy) onClose() }
    val p = palette
    Column(Modifier.fillMaxSize().background(p.groupedBackground).clickable(enabled = false) {}) {
        AssetaTopBar(AccountDeletionText.TITLE, large = false, onBack = { if (!busy) onClose() })
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).imePadding().padding(top = 16.dp)) {
            GroupedSection {
                Text(AccountDeletionText.EXPLAIN, style = MaterialTheme.typography.bodyLarge)
            }
            GroupedSection(footer = if (online) null else AccountDeletionText.OFFLINE) {
                OutlinedTextField(
                    ui.reason, vm.flow::setReason, Modifier.fillMaxWidth().testTag("deletion-reason"),
                    label = { Text(AccountDeletionText.REASON_LABEL) }, enabled = !busy, minLines = 2,
                )
                OutlinedTextField(
                    ui.typed, vm.flow::setTyped, Modifier.fillMaxWidth().testTag("deletion-confirm-word"),
                    label = { Text(AccountDeletionText.TYPE_LABEL) }, enabled = !busy, singleLine = true,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
                )
                ui.error?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                }
                if (busy) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        Text(if (ui.step == DeletionStep.Syncing) AccountDeletionText.SYNCING else AccountDeletionText.DELETING, style = AssetaType.subheadline)
                    }
                } else {
                    ButtonRow(AccountDeletionText.SUBMIT, Modifier.testTag("deletion-submit"), enabled = vm.flow.canSubmit(online), destructive = true, onClick = vm::submit)
                }
            }
            Spacer(Modifier.padding(bottom = 24.dp))
        }
    }
    when (val step = ui.step) {
        is DeletionStep.Unsynced -> AlertDialog(
            onDismissRequest = vm.flow::dismiss,
            title = { Text(AccountDeletionText.UNSYNCED_TITLE) },
            text = { Text(AccountDeletionText.unsyncedMessage(step.count)) },
            confirmButton = { TextButton(onClick = vm::syncFirst) { Text(AccountDeletionText.SYNC_FIRST) } },
            dismissButton = {
                Row {
                    TextButton(onClick = vm.flow::dismiss) { Text("Cancel") }
                    TextButton(onClick = vm.flow::deleteAnyway) { Text(AccountDeletionText.DELETE_ANYWAY, color = MaterialTheme.colorScheme.error) }
                }
            },
        )
        DeletionStep.Confirm -> AlertDialog(
            onDismissRequest = vm.flow::dismiss,
            title = { Text(AccountDeletionText.FINAL_TITLE) },
            text = { Text(AccountDeletionText.FINAL_MESSAGE) },
            confirmButton = {
                TextButton(onClick = vm::confirm, modifier = Modifier.testTag("deletion-final")) {
                    Text(AccountDeletionText.FINAL_ACTION, color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(onClick = vm.flow::dismiss) { Text("Cancel") } },
        )
        else -> Unit
    }
}

/**
 * Banner on the home screen of both apps while the company's access is limited ([CompanyNotice.banner], e.g. a
 * requested closure). [onOpen] (Owner app, closure permission) makes it open the closure request.
 */
@Composable
fun CompanyNoticeBanner(text: String, actionLabel: String? = null, onOpen: (() -> Unit)? = null, modifier: Modifier = Modifier) {
    val p = palette
    var base = modifier.fillMaxWidth().background(p.offline.copy(alpha = 0.12f), RoundedCornerShape(12.dp))
    if (onOpen != null) base = base.clickable(role = Role.Button, onClickLabel = actionLabel, onClick = onOpen)
    Column(
        base.padding(12.dp).testTag("company-notice-banner").semantics(mergeDescendants = true) {},
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(text, style = AssetaType.subheadline, color = p.offline)
        if (onOpen != null && actionLabel != null) Text(actionLabel, style = AssetaType.caption, color = p.accent)
    }
}

/** Whether the phone has a network with internet right now. */
fun isOnline(context: Context): Boolean {
    val cm = context.getSystemService(ConnectivityManager::class.java) ?: return false
    return cm.getNetworkCapabilities(cm.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
}

@Composable
private fun rememberIsOnline(): Boolean {
    val context = LocalContext.current
    val manager = remember { context.getSystemService(ConnectivityManager::class.java) }
    var online by remember { mutableStateOf(isOnline(context)) }
    DisposableEffect(manager) {
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { online = true }
            override fun onLost(network: Network) { online = isOnline(context) }
        }
        runCatching { manager?.registerDefaultNetworkCallback(callback) }
        onDispose { runCatching { manager?.unregisterNetworkCallback(callback) } }
    }
    return online
}
