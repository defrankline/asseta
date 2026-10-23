package com.asseta.core.ui.session

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.R
import com.asseta.core.ui.components.AssetaTopBar
import com.asseta.core.ui.components.BarTextButton
import com.asseta.core.ui.components.EmptyState
import kotlinx.coroutines.launch

/** What an app shows once a tenant is selected; [onSwitchTenant] returns to the tenant list. */
typealias TenantHome = @Composable (ready: SessionState.Ready, onSwitchTenant: () -> Unit, modifier: Modifier) -> Unit

/**
 * Shared session shell: login -> `/me` -> tenant selection -> optional app [home] (the Supervisor field app).
 * Without a [home] the tenant picker stays the landing screen. Inside [home], [LocalSessionActions] offers sign-out etc.
 */
@Composable
fun AssetaSessionApp(container: AssetaAppContainer, home: TenantHome? = null) {
    val vm: SessionViewModel = viewModel {
        SessionViewModel(container.authManager, container.api, container.tenantStore, container.sessionNotice, container.sessionHooks)
    }
    val state by vm.state.collectAsStateWithLifecycle()
    val loginLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        vm.onLoginResult(it.data)
    }
    val logoutLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {}
    val passwordChange by vm.passwordChange.collectAsStateWithLifecycle()
    val passwordLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        vm.onPasswordChangeResult(it.data)
    }
    PasswordChangeDialog(passwordChange, vm::dismissPasswordChange)
    // A user sign-out asks first when the app's hooks provide a confirmation text (Supervisor: unsynced items).
    val scope = rememberCoroutineScope()
    var signOutQuestion by remember { mutableStateOf<String?>(null) }
    val requestSignOut: () -> Unit = {
        scope.launch {
            val question = container.sessionHooks.signOutConfirmation()
            if (question == null) vm.signOut(logoutLauncher::launch) else signOutQuestion = question
        }
    }
    signOutQuestion?.let { question ->
        AlertDialog(
            onDismissRequest = { signOutQuestion = null },
            title = { Text(stringResource(R.string.sign_out_title)) },
            text = { Text(question) },
            confirmButton = {
                TextButton(onClick = { signOutQuestion = null; vm.signOut(logoutLauncher::launch) }) {
                    Text(stringResource(R.string.sign_out), color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(onClick = { signOutQuestion = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }

    when (val s = state) {
        is SessionState.SignedOut -> LoginScreen(container.role, s) { vm.startLogin(loginLauncher::launch) }
        // The app home draws its own navigation bar (company title, account actions), as the iOS apps do.
        is SessionState.Ready -> if (home != null && s.selectedTenant != null) {
            val actions = SessionActions(
                signOut = requestSignOut,
                switchTenant = vm::showTenantPicker,
                sessionExpired = { vm.endSession() },
                refreshProfile = vm::loadProfile,
                selectTenant = vm::selectTenant,
                changePassword = { vm.startPasswordChange(passwordLauncher::launch) },
                changingPassword = passwordChange == PasswordChangeState.InProgress,
            )
            CompositionLocalProvider(LocalSessionActions provides actions) { home(s, vm::showTenantPicker, Modifier) }
        } else {
            Scaffold(topBar = {
                AssetaTopBar(stringResource(R.string.hello_user, s.me.displayName), large = true, actions = {
                    BarTextButton(stringResource(R.string.sign_out), onClick = requestSignOut)
                })
            }) { padding -> TenantPickerScreen(s, vm::selectTenant, Modifier.padding(padding)) }
        }
        // Same as iOS `ProfileUnavailableView`: no navigation bar, retry or sign out.
        is SessionState.ProfileError -> Scaffold { padding ->
            Column(Modifier.padding(padding).fillMaxSize(), verticalArrangement = Arrangement.Center) {
                EmptyState(
                    stringResource(R.string.profile_unavailable_title),
                    listOfNotNull(s.error.message, s.error.reference?.let { stringResource(R.string.error_reference, it) }).joinToString("\n"),
                    icon = R.drawable.ic_cloud_off,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = vm::loadProfile) { Text(stringResource(R.string.retry)) }
                        TextButton(onClick = requestSignOut) { Text(stringResource(R.string.sign_out), color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }
        else -> Scaffold { padding ->
            CenteredColumn(Modifier.padding(padding)) {
                CircularProgressIndicator()
                Text(stringResource(R.string.loading_profile), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** "Password changed." on success, a short error on failure; a cancel shows nothing (same as iOS). */
@Composable
private fun PasswordChangeDialog(state: PasswordChangeState, onDismiss: () -> Unit) {
    val (title, message) = when (state) {
        PasswordChangeState.Changed -> PasswordChangeText.CHANGED to null
        is PasswordChangeState.Failed -> PasswordChangeText.FAILED_TITLE to state.message
        else -> return
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } },
        title = { Text(title) },
        text = message?.let { { Text(it) } },
    )
}

@Composable
private fun CenteredColumn(modifier: Modifier, content: @Composable () -> Unit) {
    Column(
        modifier = modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) { content() }
}
