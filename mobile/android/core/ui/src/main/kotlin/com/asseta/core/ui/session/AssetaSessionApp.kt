package com.asseta.core.ui.session

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.core.ui.R
import com.asseta.core.ui.theme.AssetaColors

/** Shared session shell: login -> `/me` -> tenant selection. Both apps render this. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AssetaSessionApp(container: AssetaAppContainer) {
    val vm: SessionViewModel = viewModel {
        SessionViewModel(container.authManager, container.api, container.tenantStore)
    }
    val state by vm.state.collectAsStateWithLifecycle()
    val loginLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        vm.onLoginResult(it.data)
    }
    val logoutLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {}

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
                        TextButton(onClick = { vm.logout()?.let(logoutLauncher::launch) }) {
                            Text(stringResource(R.string.sign_out), color = AssetaColors.Amber)
                        }
                    },
                )
            },
        ) { padding ->
            val modifier = Modifier.padding(padding)
            when (s) {
                is SessionState.Ready -> TenantPickerScreen(s, vm::selectTenant, modifier)
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
