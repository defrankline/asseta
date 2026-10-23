package com.asseta.supervisor.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.TenantAccess
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.ui.components.AssetaTopBar
import com.asseta.core.ui.components.BarTextButton
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.core.ui.session.PasswordChangeText
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.ui.finance.CashFormScreen
import com.asseta.supervisor.ui.finance.CashFormViewModel
import com.asseta.supervisor.ui.finance.ExpenseScreen
import com.asseta.supervisor.ui.finance.ExpenseViewModel
import com.asseta.supervisor.ui.finance.MyCashScreen
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** In-app routes (state-based navigation; no extra navigation dependency). */
sealed interface Route {
    data object Jobs : Route
    data class JobDetail(val jobId: String, val jobNumber: String) : Route
    data class Capture(val jobId: String, val kind: ReadingKind) : Route
    data class Acknowledge(val jobId: String) : Route
    data class WorkLogEntry(val jobId: String) : Route
    data object SyncStatus : Route
    data object MyCash : Route
    data object RecordExpense : Route
    data class CashForm(val kind: String) : Route
}

/** Screen titles (the iOS navigation titles). */
fun Route.title(companyName: String): String = when (this) {
    Route.Jobs -> companyName
    is Route.JobDetail -> jobNumber
    is Route.Capture -> if (kind == ReadingKind.OPENING) "Opening reading" else "Closing reading"
    is Route.Acknowledge -> "Customer acknowledgement"
    is Route.WorkLogEntry -> "Work log entry"
    Route.SyncStatus -> "Sync status"
    Route.MyCash -> "My cash"
    Route.RecordExpense -> "Record expense"
    is Route.CashForm -> when (kind) {
        CashFormViewModel.COLLECTION -> "Cash collection"
        CashFormViewModel.HANDOVER -> "Hand over cash"
        else -> "Fuel event"
    }
}

/** Routes the iOS app presents as sheets (Cancel / Save in the navigation bar). */
val Route.isForm: Boolean
    get() = this is Route.Capture || this is Route.Acknowledge || this is Route.WorkLogEntry || this == Route.RecordExpense ||
        this is Route.CashForm

/** Foreground sync shared by the home list (pull to refresh) and the sync status screen ("Sync now"). */
class FieldSyncViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
    private val running = MutableStateFlow(false)

    /** A run started here or by WorkManager in the background. */
    val syncing: StateFlow<Boolean> = combine(running, field.scheduler.observeRunning()) { here, background -> here || background }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)

    fun syncNow() {
        if (running.value) return
        viewModelScope.launch {
            running.value = true
            when (val r = field.engine.sync(tenantId)) {
                is SyncReport.Retry -> field.scheduler.scheduleRetry(r.retryAfterMs)
                is SyncReport.Failed -> field.scheduler.scheduleRetry(r.retryAfterMs)
                else -> Unit
            }
            running.value = false
        }
    }
}

@Composable
fun SupervisorHome(
    field: FieldGraph,
    tenant: TenantAccess,
    companyCount: Int,
    onSwitchTenant: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val tenantId = tenant.tenantId.toString()
    // View models outlive a sign-out (activity scope): key them by user too, so the next user never sees these flows.
    val scope = remember(tenantId) { "$tenantId-${field.repository.ownerSubject()}" }
    var stack by remember(tenantId) { mutableStateOf(listOf<Route>(Route.Jobs)) }
    val route = stack.last()
    fun push(r: Route) { stack = stack + r }
    fun pop() { if (stack.size > 1) stack = stack.dropLast(1) }
    BackHandler(enabled = stack.size > 1) { pop() }
    val sync: FieldSyncViewModel = viewModel(key = "sync-$scope") { FieldSyncViewModel(field, tenantId) }
    val syncing by sync.syncing.collectAsStateWithLifecycle()

    LaunchedEffect(tenantId) {
        // First login: register device + bootstrap; afterwards periodic delta pull and push in the background.
        field.scheduler.ensurePeriodic()
        field.scheduler.syncNow()
    }

    val formBar = remember(route) { FormBarState() }
    // iOS navigation bar: the home list has the company as large title, the account menu and the sync badge; pushed
    // screens have "‹ <previous title>" back and a centred title; forms (iOS sheets) have Cancel and Save.
    Column(modifier.fillMaxSize().background(palette.groupedBackground)) {
        val title = route.title(tenant.name)
        when {
            route.isForm -> AssetaTopBar(
                title, large = false,
                leading = { BarTextButton("Cancel", onClick = ::pop) },
                actions = {
                    val save = formBar.save
                    BarTextButton("Save", enabled = save?.enabled == true) { save?.onSave?.invoke() }
                },
            )
            stack.size > 1 -> AssetaTopBar(
                title, large = false, onBack = ::pop,
                backLabel = NavigationChrome.backLabel(stack.getOrNull(stack.size - 2)?.title(tenant.name)),
                actions = {
                    if (route == Route.SyncStatus) BarTextButton("Sync now", enabled = !syncing, onClick = sync::syncNow)
                },
            )
            else -> AssetaTopBar(
                title, large = true,
                leading = { AccountMenu(showSwitchCompany = companyCount > 1, onSwitchCompany = onSwitchTenant) },
                actions = { SyncBadge(field, tenantId, syncing) { push(Route.SyncStatus) } },
            )
        }
        CompositionLocalProvider(LocalFormBar provides formBar) {
        when (route) {
            Route.Jobs -> JobsScreen(
                field, tenantId, tenant.permissions.toSet(), syncing, onRefresh = sync::syncNow,
                onOpen = { id, number -> push(Route.JobDetail(id, number)) }, onRoute = ::push,
            )
            is Route.JobDetail -> {
                val vm: JobDetailViewModel = viewModel(key = "job-$scope-${route.jobId}") { JobDetailViewModel(field, tenantId, route.jobId) }
                JobDetailScreen(
                    vm,
                    onCapture = { push(Route.Capture(route.jobId, it)) },
                    onAcknowledge = { push(Route.Acknowledge(route.jobId)) },
                    onWorkLogEntry = { push(Route.WorkLogEntry(route.jobId)) },
                )
            }
            is Route.Capture -> {
                // A new key per visit: each capture gets its own id and fresh GPS attempt.
                val visit = remember(route) { System.nanoTime() }
                val vm: CaptureViewModel = viewModel(key = "capture-$visit") { CaptureViewModel(field, tenantId, route.jobId, route.kind) }
                CaptureScreen(vm, onDone = ::pop)
            }
            is Route.Acknowledge -> AcknowledgementScreen(field, tenantId, route.jobId, onDone = ::pop)
            is Route.WorkLogEntry -> WorkLogEntryScreen(field, tenantId, route.jobId, onDone = ::pop)
            Route.MyCash -> MyCashScreen(field, tenantId, syncing, onRefresh = sync::syncNow)
            Route.RecordExpense -> {
                // A new key per visit: each form gets its own client id (exactly-once) and fresh GPS attempt.
                val visit = remember(route, stack.size) { System.nanoTime() }
                val vm: ExpenseViewModel = viewModel(key = "expense-$visit") { ExpenseViewModel(field, tenantId) }
                ExpenseScreen(vm, onDone = ::pop)
            }
            is Route.CashForm -> {
                val visit = remember(route, stack.size) { System.nanoTime() }
                val vm: CashFormViewModel = viewModel(key = "cash-${route.kind}-$visit") { CashFormViewModel(field, tenantId, route.kind) }
                CashFormScreen(vm, onDone = ::pop)
            }
            Route.SyncStatus -> {
                val vm: SyncStatusViewModel = viewModel(key = "sync-status-$scope") { SyncStatusViewModel(field, tenantId) }
                SyncStatusScreen(vm, syncing, onRefresh = sync::syncNow)
            }
        }
        }
    }
}

/**
 * Account menu (leading, like the iOS toolbar): "Switch company" when the user has several, "Change password"
 * (Keycloak's page; disabled offline) and "Sign out".
 */
@Composable
private fun AccountMenu(showSwitchCompany: Boolean, onSwitchCompany: () -> Unit) {
    val actions = LocalSessionActions.current
    val online = rememberOnline()
    var open by remember { mutableStateOf(false) }
    IconButton(onClick = { open = true }) {
        Icon(painterResource(R.drawable.ic_account), contentDescription = "Account", tint = palette.accent)
    }
    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
        if (showSwitchCompany) DropdownMenuItem(text = { Text("Switch company") }, onClick = { open = false; onSwitchCompany() })
        DropdownMenuItem(
            text = {
                Column {
                    Text(PasswordChangeText.ACTION)
                    Text(
                        if (online) PasswordChangeText.FOOTER else PasswordChangeText.OFFLINE,
                        style = MaterialTheme.typography.bodySmall,
                        color = palette.secondaryText,
                    )
                }
            },
            enabled = online && !actions.changingPassword,
            onClick = { open = false; actions.changePassword() },
        )
        DropdownMenuItem(
            text = { Text("Sign out", color = MaterialTheme.colorScheme.error) },
            onClick = { open = false; actions.signOut() },
        )
    }
}

/** Sync state at a glance; opens the sync status screen. Red when anything was rejected or is in conflict. */
@Composable
private fun SyncBadge(field: FieldGraph, tenantId: String, syncing: Boolean, onClick: () -> Unit) {
    val unsynced by remember(tenantId) { field.repository.observeUnsynced(tenantId) }.collectAsStateWithLifecycle(emptyList())
    val attention = unsynced.count { it.status == ClientOperationStatus.FAILED || it.status == ClientOperationStatus.CONFLICT }
    val tint = if (attention > 0) palette.offline else palette.accent
    val label = if (unsynced.isEmpty()) "All synced" else "${unsynced.size} items not synced"
    TextButton(onClick = onClick, modifier = Modifier.semantics { contentDescription = label }) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
            if (syncing) {
                CircularProgressIndicator(Modifier.size(18.dp), color = palette.secondaryText, strokeWidth = 2.dp)
            } else {
                val icon = when {
                    attention > 0 -> R.drawable.ic_sync_problem
                    unsynced.isNotEmpty() -> R.drawable.ic_sync
                    else -> R.drawable.ic_cloud_done
                }
                Icon(painterResource(icon), contentDescription = null, tint = tint)
            }
            if (unsynced.isNotEmpty()) Text("${unsynced.size}", color = tint, style = MaterialTheme.typography.labelMedium)
        }
    }
}
