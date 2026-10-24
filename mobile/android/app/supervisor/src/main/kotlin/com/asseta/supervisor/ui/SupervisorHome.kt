package com.asseta.supervisor.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.inbox.InboxLink
import com.asseta.core.domain.inbox.InboxLinks
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.sync.data.AttentionItem
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.data.OnlineResult
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.ui.components.AssetaTopBar
import com.asseta.core.ui.components.BarIconButton
import com.asseta.core.ui.components.BarTextButton
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.core.ui.session.PasswordChangeText
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.push.NotificationPermission
import com.asseta.supervisor.push.PhonePushStatus
import com.asseta.supervisor.push.PushTexts
import com.asseta.supervisor.push.SupervisorPush
import com.asseta.supervisor.ui.finance.CashFormScreen
import com.asseta.supervisor.ui.finance.CashFormViewModel
import com.asseta.supervisor.ui.finance.ExpenseScreen
import com.asseta.supervisor.ui.finance.ExpenseViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** In-app routes (state-based navigation; no extra navigation dependency). Each tab has its own back stack. */
sealed interface Route {
    data object Jobs : Route
    data object Readings : Route
    data object Fuel : Route
    data object Money : Route
    data object Inbox : Route
    data class JobDetail(val jobId: String, val jobNumber: String) : Route
    data class Capture(val jobId: String, val kind: ReadingKind) : Route
    data class Acknowledge(val jobId: String) : Route
    data class WorkLogEntry(val jobId: String) : Route
    data object SyncStatus : Route
    data object RecordExpense : Route
    data class CashForm(val kind: String) : Route
    data class ReadingDetail(val id: String) : Route
    data class MachineDetail(val machineId: String, val assetCode: String) : Route
    data class ResetRequest(val machineId: String, val oldReading: String?) : Route
    data class ResetDetail(val key: String) : Route
    data class FuelDetail(val key: String) : Route
    data class ExpenseDetail(val key: String) : Route
    data class CashDetail(val key: String, val collection: Boolean) : Route
    data class NotificationDetail(val id: String) : Route
}

val SupervisorTab.root: Route
    get() = when (this) {
        SupervisorTab.JOBS -> Route.Jobs
        SupervisorTab.READINGS -> Route.Readings
        SupervisorTab.FUEL -> Route.Fuel
        SupervisorTab.MONEY -> Route.Money
        SupervisorTab.INBOX -> Route.Inbox
    }

/** Screen titles (the iOS navigation titles). */
fun Route.title(companyName: String): String = when (this) {
    Route.Jobs -> companyName
    Route.Readings -> "Readings"
    Route.Fuel -> "Fuel"
    Route.Money -> "Money"
    Route.Inbox -> "Inbox"
    is Route.JobDetail -> jobNumber
    is Route.Capture -> if (kind == ReadingKind.OPENING) "Opening reading" else "Closing reading"
    is Route.Acknowledge -> "Customer acknowledgement"
    is Route.WorkLogEntry -> "Work log entry"
    Route.SyncStatus -> "Sync status"
    Route.RecordExpense -> "Record expense"
    is Route.CashForm -> when (kind) {
        CashFormViewModel.COLLECTION -> "Cash collection"
        CashFormViewModel.HANDOVER -> "Hand over cash"
        else -> "Fuel event"
    }
    is Route.ReadingDetail -> "Reading"
    is Route.MachineDetail -> assetCode
    is Route.ResetRequest -> "Request meter reset"
    is Route.ResetDetail -> "Meter reset"
    is Route.FuelDetail -> "Fuel event"
    is Route.ExpenseDetail -> "Expense"
    is Route.CashDetail -> if (collection) "Cash collection" else "Cash handover"
    is Route.NotificationDetail -> "Notification"
}

/** Routes the iOS app presents as sheets (Cancel / Save in the navigation bar, no tab bar). */
val Route.isForm: Boolean
    get() = this is Route.Capture || this is Route.Acknowledge || this is Route.WorkLogEntry || this == Route.RecordExpense ||
        this is Route.CashForm || this is Route.ResetRequest

/** Back stacks of the five tabs; selecting the current tab again returns to its first screen (as on iOS). */
data class TabStacks(val tab: SupervisorTab = SupervisorTab.JOBS, val stacks: Map<SupervisorTab, List<Route>> = SupervisorTab.entries.associateWith { listOf(it.root) }) {
    val stack: List<Route> get() = stacks.getValue(tab)
    val route: Route get() = stack.last()

    fun push(r: Route) = copy(stacks = stacks + (tab to stack + r))
    fun pop() = if (stack.size > 1) copy(stacks = stacks + (tab to stack.dropLast(1))) else this
    fun select(t: SupervisorTab) = if (t == tab) copy(stacks = stacks + (t to listOf(t.root))) else copy(tab = t)

    /** A tab on its first screen (a notification tap opens the Inbox list); the other tabs keep their stacks. */
    fun showRoot(t: SupervisorTab) = copy(tab = t, stacks = stacks + (t to listOf(t.root)))
}

/** Foreground sync shared by every list (pull to refresh) and the sync status screen ("Sync now"). */
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

/** The merged records of every tab plus the server notifications (cached for offline use). */
class InboxViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
    val snapshot: StateFlow<InboxSnapshot> = field.inbox.observe(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), InboxSnapshot())

    val notifications: StateFlow<List<NotificationDto>> = field.online.inbox

    private val _offline = MutableStateFlow(false)

    /** The last refresh could not reach the server (the cached list is shown). */
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    init {
        viewModelScope.launch {
            field.online.loadCached(tenantId)
            refreshNotifications()
        }
    }

    fun refreshNotifications() {
        viewModelScope.launch { refreshNow() }
    }

    suspend fun refreshNow() {
        _offline.value = field.online.refreshNotifications(tenantId) !is OnlineResult.Fresh
    }

    fun markRead(id: String) = viewModelScope.launch { field.online.markRead(tenantId, listOf(id)) }
    fun markAllRead() = viewModelScope.launch { field.online.markAllRead(tenantId) }
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
    var nav by remember(tenantId) { mutableStateOf(TabStacks()) }
    val route = nav.route
    val stack = nav.stack
    fun push(r: Route) { nav = nav.push(r) }
    fun pop() { nav = nav.pop() }
    BackHandler(enabled = stack.size > 1) { pop() }
    val sync: FieldSyncViewModel = viewModel(key = "sync-$scope") { FieldSyncViewModel(field, tenantId) }
    val syncing by sync.syncing.collectAsStateWithLifecycle()
    val inbox: InboxViewModel = viewModel(key = "inbox-$scope") { InboxViewModel(field, tenantId) }
    val snapshot by inbox.snapshot.collectAsStateWithLifecycle()
    val notifications by inbox.notifications.collectAsStateWithLifecycle()
    val permissions = remember(tenant) { tenant.permissions.toSet() }
    val coroutines = rememberCoroutineScope()
    var blockedExpense by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(tenantId) {
        // First login: register device + bootstrap; afterwards periodic delta pull and push in the background.
        field.scheduler.ensurePeriodic()
        field.scheduler.syncNow()
        // Push is bound to the open company (in the background; never blocks sign-in or sync).
        if (NOTIFICATION_READ in permissions) field.push.registerInBackground() else field.push.unregisterInBackground()
    }

    // Back in the foreground with the permission granted meanwhile (e.g. in Settings): register this phone.
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(tenantId) {
        var granted = field.push.permission() == NotificationPermission.GRANTED
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            val now = field.push.permission() == NotificationPermission.GRANTED
            if (now && !granted && NOTIFICATION_READ in permissions && !field.push.registered.value) field.push.registerInBackground()
            granted = now
        }
    }

    // A tapped notification opens the Inbox (refreshed), then its own detail when the Inbox has it.
    val tap by field.pushTap.collectAsStateWithLifecycle()
    LaunchedEffect(tap) {
        val opened = tap ?: return@LaunchedEffect
        nav = nav.showRoot(SupervisorTab.INBOX)
        try {
            inbox.refreshNow()
            val id = opened.notificationId ?: return@LaunchedEffect
            inbox.notifications.value.firstOrNull { it.id.toString() == id }?.let { n ->
                if (n.readAt == null) inbox.markRead(id)
                push(Route.NotificationDetail(id))
            }
        } finally {
            // Consumed only now: clearing it earlier would restart (cancel) this effect.
            field.pushTap.compareAndSet(opened, null)
        }
    }

    fun refresh() {
        sync.syncNow()
        inbox.refreshNotifications()
    }

    fun recordExpense() {
        coroutines.launch {
            when (val gate = field.financeRepository.expensePolicy(tenantId)) {
                is ExpensePolicyDecision.Blocked -> blockedExpense = gate.message
                is ExpensePolicyDecision.Allowed -> push(Route.RecordExpense)
            }
        }
    }

    /** Opens what a notification is about (marking it read), or its own detail when it points nowhere on the phone. */
    fun openNotification(n: NotificationDto) {
        val id = n.id.toString()
        if (n.readAt == null) inbox.markRead(id)
        when (val link = InboxLinks.from(n.target?.entity, n.target?.id)) {
            is InboxLink.Job -> push(Route.JobDetail(link.jobId, snapshot.jobs[link.jobId]?.jobNumber ?: "Job"))
            is InboxLink.Expense -> push(Route.ExpenseDetail(snapshot.expenses.firstOrNull { it.serverId == link.expenseId }?.key ?: link.expenseId))
            InboxLink.Money -> if (nav.tab != SupervisorTab.MONEY) nav = nav.select(SupervisorTab.MONEY)
            InboxLink.None -> push(Route.NotificationDetail(id))
        }
    }

    fun openAttention(item: AttentionItem) {
        when (item.kind) {
            AttentionItem.Kind.READING -> push(Route.ReadingDetail(item.refId))
            AttentionItem.Kind.RESET -> push(Route.ResetDetail(item.refId))
            AttentionItem.Kind.EXPENSE -> push(Route.ExpenseDetail(item.refId))
            AttentionItem.Kind.FUEL -> push(Route.FuelDetail(item.refId))
            AttentionItem.Kind.COLLECTION -> push(Route.CashDetail(item.refId, collection = true))
            AttentionItem.Kind.HANDOVER -> push(Route.CashDetail(item.refId, collection = false))
            AttentionItem.Kind.OPERATION, AttentionItem.Kind.UPLOAD -> push(Route.SyncStatus)
        }
    }

    val unread = notifications.count { it.readAt == null }
    val inboxBadge = NavigationChrome.badge(InboxTexts.inboxBadge(unread, snapshot.attention.size))
    val formBar = remember(route) { FormBarState() }
    val p = palette
    // iOS navigation bar: each tab's first screen has a large title with the account menu, the sync badge (and "+" on
    // Fuel and Money); pushed screens have "‹ <previous title>" back; forms (iOS sheets) have Cancel and Save.
    Column(modifier.fillMaxSize().background(p.groupedBackground)) {
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
                leading = { AccountMenu(field.push, NOTIFICATION_READ in permissions, showSwitchCompany = companyCount > 1, onSwitchCompany = onSwitchTenant) },
                actions = {
                    when (route) {
                        Route.Fuel -> if ("tenant.expense.write" in permissions) {
                            BarIconButton(R.drawable.ic_add, "Record fuel event") { push(Route.CashForm(CashFormViewModel.FUEL)) }
                        }
                        Route.Money -> MoneyAddMenu(permissions, onExpense = ::recordExpense, onRoute = ::push)
                        else -> Unit
                    }
                    SyncBadge(field, tenantId, syncing) { push(Route.SyncStatus) }
                },
            )
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            CompositionLocalProvider(LocalFormBar provides formBar) {
                RouteContent(field, tenantId, scope, route, snapshot, syncing, ::refresh, ::push, ::pop, inbox, permissions,
                    onRecordExpense = ::recordExpense, onNotification = ::openNotification, onAttention = ::openAttention)
            }
        }
        if (!route.isForm) {
            NavigationBar(containerColor = p.chrome, tonalElevation = 0.dp) {
                SupervisorTab.entries.forEach { t ->
                    NavigationBarItem(
                        selected = t == nav.tab,
                        onClick = { nav = nav.select(t) },
                        icon = {
                            val badge = inboxBadge?.takeIf { t == SupervisorTab.INBOX }
                            BadgedBox(badge = { badge?.let { Badge { Text(it) } } }) {
                                Icon(painterResource(t.icon()), contentDescription = null)
                            }
                        },
                        label = { Text(t.label, style = MaterialTheme.typography.labelSmall) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = p.accent, selectedTextColor = p.accent, indicatorColor = Color.Transparent,
                            unselectedIconColor = p.secondaryText, unselectedTextColor = p.secondaryText,
                        ),
                    )
                }
            }
        }
    }
    blockedExpense?.let { message ->
        AlertDialog(
            onDismissRequest = { blockedExpense = null },
            title = { Text("Can't record an expense now") },
            text = { Text(message) },
            confirmButton = { TextButton(onClick = { blockedExpense = null }) { Text("OK") } },
        )
    }
}

@Composable
private fun RouteContent(
    field: FieldGraph,
    tenantId: String,
    scope: String,
    route: Route,
    snapshot: InboxSnapshot,
    syncing: Boolean,
    onRefresh: () -> Unit,
    push: (Route) -> Unit,
    pop: () -> Unit,
    inbox: InboxViewModel,
    permissions: Set<String>,
    onRecordExpense: () -> Unit,
    onNotification: (NotificationDto) -> Unit,
    onAttention: (AttentionItem) -> Unit,
) {
    when (route) {
        Route.Jobs -> JobsScreen(field, tenantId, snapshot, syncing, onRefresh, onOpen = { id, number -> push(Route.JobDetail(id, number)) }, onRoute = push)
        Route.Readings -> ReadingsScreen(snapshot, syncing, onRefresh, push)
        Route.Fuel -> FuelScreen(snapshot, syncing, onRefresh, push)
        Route.Money -> MoneyScreen(field, tenantId, snapshot, syncing, onRefresh, push)
        Route.Inbox -> {
            AskNotificationsOnce(field.push, NOTIFICATION_READ in permissions)
            val notifications by inbox.notifications.collectAsStateWithLifecycle()
            val offline by inbox.offline.collectAsStateWithLifecycle()
            InboxScreen(snapshot, notifications, offline, syncing, onRefresh, onNotification, onAttention, inbox::markAllRead)
        }
        is Route.JobDetail -> {
            val vm: JobDetailViewModel = viewModel(key = "job-$scope-${route.jobId}") { JobDetailViewModel(field, tenantId, route.jobId) }
            JobDetailScreen(
                vm, snapshot,
                onCapture = { push(Route.Capture(route.jobId, it)) },
                onAcknowledge = { push(Route.Acknowledge(route.jobId)) },
                onWorkLogEntry = { push(Route.WorkLogEntry(route.jobId)) },
                onRoute = push,
                field = field,
            )
        }
        is Route.Capture -> {
            // A new key per visit: each capture gets its own id and fresh GPS attempt.
            val visit = remember(route) { System.nanoTime() }
            val vm: CaptureViewModel = viewModel(key = "capture-$visit") { CaptureViewModel(field, tenantId, route.jobId, route.kind) }
            CaptureScreen(vm, onDone = pop)
        }
        is Route.Acknowledge -> AcknowledgementScreen(field, tenantId, route.jobId, onDone = pop)
        is Route.WorkLogEntry -> WorkLogEntryScreen(field, tenantId, route.jobId, onDone = pop)
        Route.RecordExpense -> {
            // A new key per visit: each form gets its own client id (exactly-once) and fresh GPS attempt.
            val visit = remember(route) { System.nanoTime() }
            val vm: ExpenseViewModel = viewModel(key = "expense-$visit") { ExpenseViewModel(field, tenantId) }
            ExpenseScreen(vm, onDone = pop)
        }
        is Route.CashForm -> {
            val visit = remember(route) { System.nanoTime() }
            val vm: CashFormViewModel = viewModel(key = "cash-${route.kind}-$visit") { CashFormViewModel(field, tenantId, route.kind) }
            CashFormScreen(vm, onDone = pop)
        }
        Route.SyncStatus -> {
            val vm: SyncStatusViewModel = viewModel(key = "sync-status-$scope") { SyncStatusViewModel(field, tenantId) }
            SyncStatusScreen(vm, syncing, onRefresh = onRefresh)
        }
        is Route.ReadingDetail -> ReadingDetailScreen(field, snapshot, route.id, push)
        is Route.MachineDetail -> MachineDetailScreen(snapshot, route.machineId, push)
        is Route.ResetRequest -> {
            val visit = remember(route) { System.nanoTime() }
            val vm: ResetRequestViewModel = viewModel(key = "reset-$visit") { ResetRequestViewModel(field, tenantId, route.machineId, route.oldReading) }
            ResetRequestScreen(vm, snapshot, onDone = pop)
        }
        is Route.ResetDetail -> ResetDetailScreen(field, snapshot, route.key, push)
        is Route.FuelDetail -> FuelDetailScreen(snapshot, route.key, push)
        is Route.ExpenseDetail -> ExpenseDetailScreen(field, snapshot, route.key, permissions, onRecordExpense, push)
        is Route.CashDetail -> CashDetailScreen(field, tenantId, snapshot, route.key, route.collection, permissions, push)
        is Route.NotificationDetail -> {
            val notifications by inbox.notifications.collectAsStateWithLifecycle()
            NotificationDetailScreen(notifications.firstOrNull { it.id.toString() == route.id })
        }
    }
}

private fun SupervisorTab.icon(): Int = when (this) {
    SupervisorTab.JOBS -> R.drawable.ic_nav_jobs
    SupervisorTab.READINGS -> R.drawable.ic_gauge
    SupervisorTab.FUEL -> R.drawable.ic_fuel
    SupervisorTab.MONEY -> R.drawable.ic_wallet
    SupervisorTab.INBOX -> R.drawable.ic_inbox
}

/** "+" on the Money tab: the existing expense, collection and handover forms, by permission. */
@Composable
private fun MoneyAddMenu(permissions: Set<String>, onExpense: () -> Unit, onRoute: (Route) -> Unit) {
    val expenses = "tenant.expense.write" in permissions
    val cash = "tenant.collection.record" in permissions
    if (!expenses && !cash) return
    var open by remember { mutableStateOf(false) }
    Box {
        BarIconButton(R.drawable.ic_add, "Record") { open = true }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            if (expenses) DropdownMenuItem(text = { Text("Record expense") }, onClick = { open = false; onExpense() })
            if (cash) {
                DropdownMenuItem(text = { Text("Record cash collection") }, onClick = { open = false; onRoute(Route.CashForm(CashFormViewModel.COLLECTION)) })
                DropdownMenuItem(text = { Text("Hand over cash") }, onClick = { open = false; onRoute(Route.CashForm(CashFormViewModel.HANDOVER)) })
            }
        }
    }
}

private const val NOTIFICATION_READ = "tenant.notification.read"

/** Asks for the notification permission (Android 13+) the first time the Inbox is shown; a refusal is not asked again. */
@Composable
private fun AskNotificationsOnce(push: SupervisorPush, canRead: Boolean) {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        push.asked = true
        push.registerInBackground()
    }
    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 33 && PushTexts.askOnInbox(push.available, canRead, push.permission())) {
            launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}

/**
 * Account menu (leading, like the iOS toolbar): "Switch company" when the user has several, "Notifications on this
 * phone" (push status; "Turn on" asks for the permission and registers), "Change password" (Keycloak's page; disabled
 * offline) and "Sign out".
 */
@Composable
private fun AccountMenu(push: SupervisorPush, canReadNotifications: Boolean, showSwitchCompany: Boolean, onSwitchCompany: () -> Unit) {
    val actions = LocalSessionActions.current
    val online = rememberOnline()
    val coroutines = rememberCoroutineScope()
    var open by remember { mutableStateOf(false) }
    val registered by push.registered.collectAsStateWithLifecycle()
    var checks by remember { mutableIntStateOf(0) }
    // Re-read when the menu opens: the permission may have changed in Settings meanwhile.
    val pushStatus = remember(open, registered, checks) { push.status() }
    fun turnOn() {
        coroutines.launch { push.register(); checks++ }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        push.asked = true
        turnOn()
    }
    IconButton(onClick = { open = true }) {
        Icon(painterResource(R.drawable.ic_account), contentDescription = "Account", tint = palette.accent)
    }
    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
        if (showSwitchCompany) DropdownMenuItem(text = { Text("Switch company") }, onClick = { open = false; onSwitchCompany() })
        if (canReadNotifications) {
            // Its own group, like the iOS section "Notifications on this phone".
            HorizontalDivider()
            val canTurnOn = pushStatus == PhonePushStatus.NOT_REGISTERED
            DropdownMenuItem(
                text = {
                    Column {
                        Text(PushTexts.ROW)
                        Text(pushStatus.label, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
                    }
                },
                trailingIcon = if (canTurnOn) {
                    { Text(PushTexts.TURN_ON, color = palette.accent, style = MaterialTheme.typography.labelLarge) }
                } else null,
                onClick = {
                    open = false
                    when {
                        !canTurnOn -> Unit
                        Build.VERSION.SDK_INT >= 33 && push.permission() == NotificationPermission.NOT_ASKED ->
                            permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        else -> turnOn()
                    }
                },
            )
            HorizontalDivider()
        }
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
