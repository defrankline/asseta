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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import com.asseta.core.ui.theme.AssetaColors
import kotlinx.coroutines.launch

/** What an app shows once a tenant is selected; [onSwitchTenant] returns to the tenant list. */
typealias TenantHome = @Composable (ready: SessionState.Ready, onSwitchTenant: () -> Unit, modifier: Modifier) -> Unit

/**
 * Shared session shell: login -> `/me` -> tenant selection -> optional app [home] (the Supervisor field app).
 * Without a [home] the tenant picker stays the landing screen. Inside [home], [LocalSessionActions] offers sign-out etc.
 */
@OptIn(ExperimentalMaterial3Api::class)
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
        else -> Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("${stringResource(R.string.asseta_brand)} ${stringResource(container.role.label)}") },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = AssetaColors.Slate, titleContentColor = AssetaColors.Amber,
                        actionIconContentColor = AssetaColors.Amber,
                    ),
                    actions = {
                        TextButton(onClick = requestSignOut) {
                            Text(stringResource(R.string.sign_out), color = AssetaColors.Amber)
                        }
                    },
                )
            },
        ) { padding ->
            val modifier = Modifier.padding(padding)
            when (s) {
                is SessionState.Ready -> if (home != null && s.selectedTenant != null) {
                    val actions = SessionActions(
                        signOut = requestSignOut,
                        switchTenant = vm::showTenantPicker,
                        sessionExpired = { vm.endSession() },
                        refreshProfile = vm::loadProfile,
                        selectTenant = vm::selectTenant,
                    )
                    CompositionLocalProvider(LocalSessionActions provides actions) { home(s, vm::showTenantPicker, modifier) }
                } else {
                    TenantPickerScreen(s, vm::selectTenant, modifier)
                }
                is SessionState.ProfileError -> CenteredColumn(modifier) {
                    ErrorText(s.error)
                    Button(onClick = vm::loadProfile) { Text(stringResource(R.string.retry)) }
                }
                else -> CenteredColumn(modifier) {
                    CircularProgressIndicator()
                    Text(stringResource(R.string.loading_profile))
                }
            }
        }
    }
}

@Composable
private fun CenteredColumn(modifier: Modifier, content: @Composable () -> Unit) {
    Column(
        modifier = modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) { content() }
}
