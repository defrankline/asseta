package com.asseta.supervisor.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.accountability.CustomerHoursPolicy
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.accountability.FuelSwitch
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.inbox.InboxLink
import com.asseta.core.domain.inbox.InboxLinks
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.sync.data.AttentionItem
import com.asseta.core.sync.data.CashView
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.data.MachineReportView
import com.asseta.core.sync.data.OnlineResult
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.ui.R as CoreR
import com.asseta.core.ui.components.AssetaTopBar
import com.asseta.core.ui.components.BarTextButton
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.core.ui.shell.DrawerEntry
import com.asseta.core.ui.shell.HomeTopRow
import com.asseta.core.ui.shell.ShellDrawer
import com.asseta.core.ui.shell.ShellText
import com.asseta.core.ui.shell.StatusChip
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.BuildConfig
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.push.NotificationPermission
import com.asseta.supervisor.push.PushTexts
import com.asseta.supervisor.push.SupervisorPush
import com.asseta.supervisor.ui.accountability.CashAckScreen
import com.asseta.supervisor.ui.accountability.CashAckViewModel
import com.asseta.supervisor.ui.accountability.CashTransferScreen
import com.asseta.supervisor.ui.accountability.CashTransferViewModel
import com.asseta.supervisor.ui.accountability.FieldAccountabilityTexts
import com.asseta.supervisor.ui.accountability.HoursSaleScreen
import com.asseta.supervisor.ui.accountability.HoursSaleViewModel
import com.asseta.supervisor.ui.accountability.HoursTransferScreen
import com.asseta.supervisor.ui.accountability.HoursTransferViewModel
import com.asseta.supervisor.ui.accountability.RemittanceOverdueScreen
import com.asseta.supervisor.ui.accountability.RemittanceOverdueViewModel
import com.asseta.supervisor.ui.accountability.RetentionScreen
import com.asseta.supervisor.ui.accountability.RetentionStatusScreen
import com.asseta.supervisor.ui.accountability.RetentionStatusViewModel
import com.asseta.supervisor.ui.accountability.RetentionViewModel
import com.asseta.supervisor.ui.finance.CashFormScreen
import com.asseta.supervisor.ui.finance.CashFormViewModel
import com.asseta.supervisor.ui.finance.ExpenseScreen
import com.asseta.supervisor.ui.finance.ExpenseViewModel
import com.asseta.supervisor.ui.home.CustomerBalancesScreen
import com.asseta.supervisor.ui.home.DashboardScreen
import com.asseta.supervisor.ui.home.HomeScreen
import com.asseta.supervisor.ui.home.HomeTexts
import com.asseta.supervisor.ui.home.InvoicePaymentScreen
import com.asseta.supervisor.ui.home.InvoicePaymentViewModel
import com.asseta.supervisor.ui.home.MenuFooter
import com.asseta.supervisor.ui.home.MenuItem
import com.asseta.supervisor.ui.home.MoneyHomeScreen
import com.asseta.supervisor.ui.home.MyReportsScreen
import com.asseta.supervisor.ui.home.MySalesScreen
import com.asseta.supervisor.ui.home.ShellData
import com.asseta.supervisor.ui.home.ShellModel
import com.asseta.supervisor.ui.home.SupervisorSettingsScreen
import com.asseta.supervisor.ui.report.MachineReportScreen
import com.asseta.supervisor.ui.report.MachineReportViewModel
import com.asseta.supervisor.ui.report.ReportTexts
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** In-app routes (state-based navigation; no extra navigation dependency). The stack always starts at Home. */
sealed interface Route {
    // ADR-008 shell (side menu)
    data object Home : Route
    data object Money : Route
    data object Dashboard : Route
    data object Inbox : Route
    /** Fuel events (only while the company uses fuel capture). */
    data object Fuel : Route
    /** A machine report; [machineId] preselects one of my machines. */
    data class MachineReport(val machineId: String? = null) : Route
    data object MyReports : Route
    data object MySales : Route
    data object CustomerBalances : Route
    /** My cash custody, today's figures and my money records (the former Money tab). */
    data object MoneyRecords : Route
    /** A payment on a customer's open credit invoice. */
    data class InvoicePayment(val invoiceId: String? = null) : Route
    data object Settings : Route

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

    // Accountability (each gated by server capability, permission and tenant policy)
    data object HoursSale : Route
    data object HoursTransfer : Route
    data object CashTransfer : Route
    data class CashAck(val id: String, val isFloat: Boolean) : Route
    data object Retention : Route
    /** A request to keep cash ([key]: this phone's form id or the server's request id). */
    data class RetentionStatus(val key: String) : Route
    /** My overdue remittance flag (read online). */
    data class RemittanceOverdue(val id: String) : Route
    data class Baseline(val machineId: String) : Route
    data class Correction(val readingId: String) : Route

    /** DEC-033 petty cash: my funds, and the offline forms on them. */
    data object PettyCash : Route
    data class PettyCashAck(val movementId: String) : Route
    data class PettyCashTopUp(val fundId: String) : Route
    data class PettyCashReturn(val fundId: String) : Route
    data class PettyCashCount(val fundId: String) : Route
    data class PettyCashHolderChange(val changeId: String) : Route
    data class PettyCashAdvance(val advanceId: String) : Route
    data class PettyCashGiveAdvance(val fundId: String) : Route

    /** Customers (online): list, one customer, add ([customerId] null) or edit its details. */
    data object Customers : Route
    data class CustomerDetail(val customerId: String) : Route
    data class CustomerForm(val customerId: String?) : Route
}

/** Screen titles (the iOS navigation titles). */
fun Route.title(companyName: String): String = when (this) {
    Route.Home -> companyName
    Route.Money -> "Money"
    Route.Dashboard -> "Dashboard"
    Route.Inbox -> "Inbox"
    Route.Fuel -> "Fuel"
    is Route.MachineReport -> ReportTexts.TITLE
    Route.MyReports -> HomeTexts.MY_REPORTS
    Route.MySales -> HomeTexts.MY_SALES
    Route.CustomerBalances -> HomeTexts.CUSTOMER_BALANCES
    Route.MoneyRecords -> HomeTexts.MY_CASH
    is Route.InvoicePayment -> HomeTexts.INVOICE_PAYMENT_TITLE
    Route.Settings -> HomeTexts.SETTINGS
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
    Route.HoursSale -> FieldAccountabilityTexts.TITLE_HOURS_SALE
    Route.HoursTransfer -> FieldAccountabilityTexts.TITLE_HOURS_TRANSFER
    Route.CashTransfer -> FieldAccountabilityTexts.TITLE_CASH_TRANSFER
    is Route.CashAck -> if (isFloat) FieldAccountabilityTexts.TITLE_ACK_FLOAT else FieldAccountabilityTexts.TITLE_ACK_TRANSFER
    Route.Retention -> FieldAccountabilityTexts.TITLE_RETENTION
    is Route.RetentionStatus -> FieldAccountabilityTexts.TITLE_RETENTION_STATUS
    is Route.RemittanceOverdue -> FieldAccountabilityTexts.TITLE_REMITTANCE_OVERDUE
    is Route.Baseline -> FieldAccountabilityTexts.TITLE_BASELINE
    is Route.Correction -> FieldAccountabilityTexts.TITLE_CORRECTION
    Route.PettyCash -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE
    is Route.PettyCashAck -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_ACK
    is Route.PettyCashTopUp -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_TOP_UP
    is Route.PettyCashReturn -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_RETURN
    is Route.PettyCashCount -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_COUNT
    is Route.PettyCashHolderChange -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_HOLDER_CHANGE
    is Route.PettyCashAdvance -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_ADVANCE
    is Route.PettyCashGiveAdvance -> com.asseta.supervisor.ui.pettycash.PettyCashTexts.TITLE_GIVE_ADVANCE
    Route.Customers -> com.asseta.supervisor.ui.customers.CustomerTexts.TITLE
    is Route.CustomerDetail -> com.asseta.supervisor.ui.customers.CustomerTexts.TITLE_DETAIL
    is Route.CustomerForm -> if (customerId == null) com.asseta.supervisor.ui.customers.CustomerTexts.TITLE_ADD else com.asseta.supervisor.ui.customers.CustomerTexts.TITLE_EDIT
}

/** Routes the iOS app presents as sheets (Cancel / Save in the navigation bar). */
val Route.isForm: Boolean
    get() = this == Route.RecordExpense || this is Route.CashForm || this is Route.ResetRequest || this == Route.HoursTransfer ||
        this == Route.CashTransfer || this is Route.CashAck || this == Route.Retention || this is Route.Baseline || this is Route.Correction ||
        this is Route.PettyCashAck || this is Route.PettyCashTopUp || this is Route.PettyCashReturn || this is Route.PettyCashCount ||
        this is Route.PettyCashHolderChange || this is Route.PettyCashAdvance || this is Route.PettyCashGiveAdvance || this is Route.CustomerForm

/** The menu entry a route belongs to (highlighted in the side menu). */
val Route.menu: MenuItem?
    get() = when (this) {
        Route.Home -> MenuItem.HOME
        Route.HoursSale -> MenuItem.SELL_HOURS
        is Route.MachineReport -> MenuItem.MACHINE_REPORT
        Route.Money -> MenuItem.MONEY
        Route.Fuel -> MenuItem.FUEL
        Route.Dashboard -> MenuItem.DASHBOARD
        Route.Inbox -> MenuItem.INBOX
        Route.Customers -> MenuItem.CUSTOMERS
        else -> null
    }

/** One back stack starting at Home; a side-menu entry opens on top of Home (back returns Home, as in the designs). */
data class NavStack(val stack: List<Route> = listOf(Route.Home)) {
    val route: Route get() = stack.last()

    fun push(r: Route) = copy(stack = stack + r)
    fun pop() = if (stack.size > 1) copy(stack = stack.dropLast(1)) else this

    /** A side-menu entry: Home itself, or Home then the entry. */
    fun open(item: MenuItem) = NavStack(if (item == MenuItem.HOME) listOf(Route.Home) else listOf(Route.Home, item.root))

    /** A notification tap opens the Inbox (on top of Home). */
    fun showInbox() = open(MenuItem.INBOX)

    /** The menu entry to highlight: the first entry on the stack after Home, else Home. */
    val menu: MenuItem get() = stack.drop(1).firstNotNullOfOrNull { it.menu } ?: MenuItem.HOME
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

/** The merged records of the Inbox plus the server notifications (cached for offline use). */
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

/** Machine reports, open credit invoices and this phone's queued reports (for the shell's figures and badges). */
class ReportsViewModel(field: FieldGraph, tenantId: String) : ViewModel() {
    val view: StateFlow<MachineReportView> = field.machineReports.observe(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), MachineReportView())
}

@Composable
fun SupervisorHome(
    field: FieldGraph,
    tenant: TenantAccess,
    companyCount: Int,
    onSwitchTenant: () -> Unit,
    modifier: Modifier = Modifier,
    /** The signed-in user (`/me`). */
    userId: String? = null,
    /** The signed-in user's name (`/me` display name), for the greeting and the side menu. */
    displayName: String? = null,
) {
    val tenantId = tenant.tenantId.toString()
    // View models outlive a sign-out (activity scope): key them by user too, so the next user never sees these flows.
    val scope = remember(tenantId) { "$tenantId-${field.repository.ownerSubject()}" }
    var nav by remember(tenantId) { mutableStateOf(NavStack()) }
    val route = nav.route
    val stack = nav.stack
    // The open screen's own title (null = the route's title); cleared whenever another screen opens.
    var screenTitle by remember(route) { mutableStateOf<String?>(null) }
    fun push(r: Route) { nav = nav.push(r) }
    fun pop() { nav = nav.pop() }
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val coroutines = rememberCoroutineScope()
    BackHandler(enabled = drawer.isOpen) { coroutines.launch { drawer.close() } }
    BackHandler(enabled = !drawer.isOpen && stack.size > 1 && route !is Route.MachineReport) { pop() }
    val sync: FieldSyncViewModel = viewModel(key = "sync-$scope") { FieldSyncViewModel(field, tenantId) }
    val syncing by sync.syncing.collectAsStateWithLifecycle()
    val inbox: InboxViewModel = viewModel(key = "inbox-$scope") { InboxViewModel(field, tenantId) }
    val snapshot by inbox.snapshot.collectAsStateWithLifecycle()
    val notifications by inbox.notifications.collectAsStateWithLifecycle()
    val reportsVm: ReportsViewModel = viewModel(key = "reports-$scope") { ReportsViewModel(field, tenantId) }
    val reports by reportsVm.view.collectAsStateWithLifecycle()
    val permissions = remember(tenant) {
        // Capabilities the tenant switched off (CUSTOMER_HOURS) hide their entries and are not read (DEC-030 G1).
        field.accountability.setDisabledCapabilities(tenantId, tenant.disabledCapabilities)
        tenant.permissions.toSet()
    }
    // ADR-008 §3: the fuel switch comes with `/me`, so Fuel is never shown and then hidden.
    val fuelOn = remember(tenant) { FuelSwitch.on(tenant.disabledCapabilities) }
    var blockedExpense by remember { mutableStateOf<String?>(null) }
    // What the entries need: server capabilities, permissions and the saved tenant policies.
    val accountabilityCache by field.accountability.cache.collectAsStateWithLifecycle()
    val access by produceState<FieldAccess?>(null, tenantId, syncing, accountabilityCache) {
        value = field.accountability.access(tenantId, permissions)
    }
    val cashView by remember(tenantId) { field.financeRepository.observeCashView(tenantId) }.collectAsStateWithLifecycle(CashView(emptyList(), emptyList(), null))
    val customers by remember(tenantId) { field.financeRepository.observeCustomers(tenantId) }.collectAsStateWithLifecycle(emptyList())
    val reminderDays = CustomerHoursPolicy.reminderDays(access?.hours)
    val data = remember(snapshot, reports, reminderDays, cashView, customers) {
        ShellData.of(snapshot, reports, reminderDays, cashView, customers.associate { it.id to it.name }, com.asseta.core.network.NetworkFactory.json)
    }

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

    /** Opens what a link points at; [notificationId] is shown when the phone has nothing for it. */
    fun openLink(link: InboxLink, notificationId: String?) {
        val id = notificationId
        fun money() { push(Route.Money) }
        fun fallback() { if (id != null) push(Route.NotificationDetail(id)) else money() }
        // CASH_CUSTODY switched off: its records are hidden, so their taps open Money (follow-up F1).
        val cashOff = TenantAccess.CASH_CUSTODY in tenant.disabledCapabilities
        when (link) {
            is InboxLink.Machine -> snapshot.machines[link.machineId]?.let { push(Route.MachineDetail(it.id, it.assetCode)) } ?: fallback()
            is InboxLink.Expense -> push(Route.ExpenseDetail(snapshot.expenses.firstOrNull { it.serverId == link.expenseId }?.key ?: link.expenseId))
            InboxLink.Money -> money()
            // The exact transfer / float while it still waits for my answer, else Money.
            is InboxLink.CashAck -> {
                val waiting = if (link.isFloat) accountabilityCache.floats.any { it.id == link.id } else accountabilityCache.transfers.any { it.id == link.id && it.status == com.asseta.core.model.sync.CashTransferDto.PENDING }
                if (waiting && access?.acknowledgeCash == true) push(Route.CashAck(link.id, link.isFloat)) else money()
            }
            is InboxLink.Retention -> if (cashOff) money() else push(Route.RetentionStatus(link.id))
            // Read online first: a flag the server does not show me (404), offline or switched off opens Money.
            is InboxLink.RemittanceOverdue -> if (cashOff) {
                money()
            } else {
                coroutines.launch { if (field.accountability.remittanceOverdue(link.id) != null) push(Route.RemittanceOverdue(link.id)) else money() }
            }
            // One of my remittances: its detail once it is on the phone, else Money.
            is InboxLink.Handover -> snapshot.handovers.firstOrNull { it.key == link.id }?.let { push(Route.CashDetail(it.key, collection = false)) } ?: money()
            // ADR-008: a report decided (or waiting) opens its machine's report screen; else my reports.
            is InboxLink.MachineReport -> (reports.myReports.firstOrNull { it.id == link.id }?.machineId ?: reports.local.firstOrNull { it.operationId == link.id }?.machineId)
                ?.let { push(Route.MachineReport(it)) } ?: push(Route.MyReports)
            is InboxLink.CreditInvoice -> if (access?.creditInvoicePayment == true && reports.invoices.any { it.id == link.id }) push(Route.InvoicePayment(link.id)) else money()
            InboxLink.None -> fallback()
        }
    }

    /** A petty cash record (DEC-033): the waiting form, else My petty cash; false when not petty cash or the feature is off. */
    fun openPettyCash(entity: String?, id: String?): Boolean {
        if (entity?.startsWith("petty_cash") != true || access?.pettyCash != true) return false
        coroutines.launch {
            val me = field.accountability.myStaffId(tenantId)
            val view = field.pettyCash.observe(tenantId, me).first()
            com.asseta.supervisor.ui.pettycash.PettyCashLinks.route(entity, id, view)?.let { push(it) }
        }
        return true
    }

    /** Opens what a notification is about (marking it read), or its own detail when it points nowhere on the phone. */
    fun openNotification(n: NotificationDto) {
        val id = n.id.toString()
        if (n.readAt == null) inbox.markRead(id)
        if (openPettyCash(n.target?.entity, n.target?.id)) return
        openLink(InboxLinks.from(n.target?.entity, n.target?.id, n.recordKind, n.recordId), id)
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

    // A tapped notification opens the Inbox (refreshed), then its own detail when the Inbox has it.
    val tap by field.pushTap.collectAsStateWithLifecycle()
    LaunchedEffect(tap) {
        val opened = tap ?: return@LaunchedEffect
        nav = nav.showInbox()
        try {
            inbox.refreshNow()
            val id = opened.notificationId
            val n = inbox.notifications.value.firstOrNull { it.id.toString() == id }
            if (n != null) {
                openNotification(n)
            } else if (openPettyCash(opened.entity, opened.entityId)) {
                // A petty cash record named by the push.
            } else if (opened.recordId != null || opened.entityId != null) {
                openLink(InboxLinks.from(opened.entity, opened.entityId, opened.kind, opened.recordId), null)
            }
        } finally {
            // Consumed only now: clearing it earlier would restart (cancel) this effect.
            field.pushTap.compareAndSet(opened, null)
        }
    }

    val unread = notifications.count { it.readAt == null }
    val inboxBadge = NavigationChrome.badge(InboxTexts.inboxBadge(unread, snapshot.attention.size))
    val unsynced by remember(tenantId) { field.repository.observeUnsynced(tenantId) }.collectAsStateWithLifecycle(emptyList())
    val problems = unsynced.count { it.status == ClientOperationStatus.FAILED || it.status == ClientOperationStatus.CONFLICT }
    val formBar = remember(route) { FormBarState() }
    val actions = LocalSessionActions.current
    val p = palette

    fun select(key: String) {
        coroutines.launch { drawer.close() }
        MenuItem.entries.firstOrNull { it.name == key }?.let { nav = nav.open(it); return }
        when (MenuFooter.valueOf(key)) {
            MenuFooter.SYNC -> nav = nav.open(MenuItem.HOME).push(Route.SyncStatus)
            MenuFooter.SWITCH_COMPANY -> onSwitchTenant()
            MenuFooter.SETTINGS -> nav = nav.open(MenuItem.HOME).push(Route.Settings)
            MenuFooter.SIGN_OUT -> actions.signOut()
        }
    }

    val menu = ShellModel.menu(access, permissions, fuelOn)
    ModalNavigationDrawer(
        drawerState = drawer,
        gesturesEnabled = route == Route.Home || drawer.isOpen,
        modifier = modifier,
        drawerContent = {
            ShellDrawer(
                name = displayName?.takeIf { it.isNotBlank() } ?: tenant.name,
                subtitle = HomeTexts.role(tenant.name),
                entries = menu.map { item ->
                    when (item) {
                        MenuItem.HOME -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_home)
                        MenuItem.SELL_HOURS -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_sell_hours)
                        MenuItem.MACHINE_REPORT -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_machine_report, ShellText.badge(data.due))
                        MenuItem.MONEY -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_money)
                        MenuItem.FUEL -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_fuel)
                        MenuItem.DASHBOARD -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_dashboard)
                        MenuItem.INBOX -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_inbox, inboxBadge, alert = true)
                        MenuItem.CUSTOMERS -> DrawerEntry(item.name, item.label, CoreR.drawable.ic_shell_customer_add)
                    }
                },
                footer = listOfNotNull(
                    DrawerEntry(MenuFooter.SYNC.name, HomeTexts.syncRow(unsynced.size, null), if (problems > 0) CoreR.drawable.ic_cloud_off else CoreR.drawable.ic_shell_check),
                    DrawerEntry(MenuFooter.SWITCH_COMPANY.name, MenuFooter.SWITCH_COMPANY.label, CoreR.drawable.ic_shell_switch).takeIf { companyCount > 1 },
                    DrawerEntry(MenuFooter.SETTINGS.name, MenuFooter.SETTINGS.label, CoreR.drawable.ic_shell_settings),
                    DrawerEntry(MenuFooter.SIGN_OUT.name, MenuFooter.SIGN_OUT.label, CoreR.drawable.ic_shell_sign_out),
                ),
                selected = nav.menu.name,
                caption = HomeTexts.caption(BuildConfig.VERSION_NAME),
                onSelect = ::select,
                footerTint = mapOf(MenuFooter.SYNC.name to if (problems > 0) p.offline else if (unsynced.isEmpty()) p.live else p.secondaryText),
            )
        },
    ) {
        Column(Modifier.fillMaxSize().background(p.groupedBackground)) {
            // A screen may name itself per step (the machine report's split header); else the route's title.
            val title = screenTitle ?: route.title(tenant.name)
            when {
                route == Route.Home -> Unit
                route.isForm -> AssetaTopBar(
                    title, large = false,
                    leading = { BarTextButton("Cancel", onClick = ::pop) },
                    actions = {
                        val save = formBar.save
                        BarTextButton(save?.label ?: "Save", enabled = save?.enabled == true) { save?.onSave?.invoke() }
                    },
                )
                else -> AssetaTopBar(
                    title, large = false, onBack = ::pop,
                    backLabel = NavigationChrome.backLabel(stack.getOrNull(stack.size - 2)?.title(tenant.name)),
                    actions = {
                        if (route == Route.SyncStatus) BarTextButton("Sync now", enabled = !syncing, onClick = sync::syncNow)
                        if (route == Route.Fuel && ShellModel.EXPENSE_WRITE in permissions) {
                            BarTextButton("Record") { push(Route.CashForm(CashFormViewModel.FUEL)) }
                        }
                    },
                )
            }
            Box(Modifier.weight(1f).fillMaxWidth()) {
                CompositionLocalProvider(LocalFormBar provides formBar) {
                    when (route) {
                        Route.Home -> HomeScreen(
                            displayName, tenant.name, access, data, syncing, ::refresh, com.asseta.core.ui.session.CompanyNotice.banner(tenant), ::push,
                        ) {
                            Box(Modifier.statusBarsPadding()) {
                                HomeTopRow(onMenu = { coroutines.launch { drawer.open() } }) {
                                    StatusChip(
                                        if (unsynced.isEmpty()) HomeTexts.ALL_SYNCED else HomeTexts.notSynced(unsynced.size),
                                        if (problems > 0) CoreR.drawable.ic_cloud_off else CoreR.drawable.ic_shell_check,
                                        if (problems > 0) p.offline else if (unsynced.isEmpty()) p.live else p.secondaryText,
                                    ) { push(Route.SyncStatus) }
                                }
                            }
                        }
                        else -> RouteContent(field, tenantId, scope, route, snapshot, syncing, ::refresh, ::push, ::pop, inbox, permissions, access, data, fuelOn,
                            onRecordExpense = ::recordExpense, onNotification = ::openNotification, onAttention = ::openAttention, onTitle = { screenTitle = it })
                    }
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
    access: FieldAccess?,
    data: ShellData,
    fuelOn: Boolean,
    onRecordExpense: () -> Unit,
    onNotification: (NotificationDto) -> Unit,
    onAttention: (AttentionItem) -> Unit,
    onTitle: (String) -> Unit,
) {
    when (route) {
        Route.Home -> Unit
        Route.Money -> MoneyHomeScreen(data, access, permissions, push, onRecordExpense)
        Route.MoneyRecords -> MoneyScreen(field, tenantId, snapshot, syncing, onRefresh, push, permissions, access)
        Route.Dashboard -> DashboardScreen(field, tenantId, data, permissions, push)
        Route.MyReports -> MyReportsScreen(data, push)
        Route.MySales -> MySalesScreen(data)
        Route.CustomerBalances -> CustomerBalancesScreen(data)
        // Fuel only while the company uses it (ADR-008 §3); a stale route shows nothing.
        Route.Fuel -> if (fuelOn) FuelScreen(snapshot, syncing, onRefresh, push)
        is Route.MachineReport -> {
            val visit = remember(route) { System.nanoTime() }
            val vm: MachineReportViewModel = viewModel(key = "machine-report-$visit") { MachineReportViewModel(field, tenantId, permissions, route.machineId) }
            BackHandler { if (!vm.back()) pop() }
            MachineReportScreen(vm, onDone = pop, onTitle = onTitle)
        }
        is Route.InvoicePayment -> {
            val visit = remember(route) { System.nanoTime() }
            InvoicePaymentScreen(viewModel(key = "invoice-payment-$visit") { InvoicePaymentViewModel(field, tenantId, permissions, route.invoiceId) }, onDone = pop)
        }
        Route.Settings -> SupervisorSettingsScreen(field.push, NOTIFICATION_READ in permissions, BuildConfig.VERSION_NAME)
        Route.Inbox -> {
            AskNotificationsOnce(field.push, NOTIFICATION_READ in permissions)
            val notifications by inbox.notifications.collectAsStateWithLifecycle()
            val offline by inbox.offline.collectAsStateWithLifecycle()
            InboxScreen(snapshot, notifications, offline, syncing, onRefresh, onNotification, onAttention, inbox::markAllRead)
        }
        is Route.Baseline, is Route.Correction -> {
            // The capture screen with its evidence rules, for a baseline or a correction.
            val visit = remember(route) { System.nanoTime() }
            val target = if (route is Route.Baseline) {
                com.asseta.core.sync.usecase.CaptureTarget.Baseline(route.machineId, "")
            } else {
                com.asseta.core.sync.usecase.CaptureTarget.Correction((route as Route.Correction).readingId, "")
            }
            val vm: CaptureViewModel = viewModel(key = "capture-$visit") { CaptureViewModel(field, tenantId, com.asseta.core.domain.policy.ReadingKind.DAILY, target) }
            CaptureScreen(vm, onDone = pop)
        }
        Route.HoursSale -> {
            val visit = remember(route) { System.nanoTime() }
            HoursSaleScreen(viewModel(key = "hours-sale-$visit") { HoursSaleViewModel(field, tenantId, permissions) }, onDone = pop)
        }
        Route.HoursTransfer -> {
            val visit = remember(route) { System.nanoTime() }
            HoursTransferScreen(viewModel(key = "hours-transfer-$visit") { HoursTransferViewModel(field, tenantId, permissions) }, onDone = pop)
        }
        Route.CashTransfer -> {
            val visit = remember(route) { System.nanoTime() }
            CashTransferScreen(viewModel(key = "cash-transfer-$visit") { CashTransferViewModel(field, tenantId, permissions) }, onDone = pop)
        }
        is Route.CashAck -> {
            val visit = remember(route) { System.nanoTime() }
            CashAckScreen(viewModel(key = "cash-ack-$visit") { CashAckViewModel(field, tenantId, permissions, route.id, route.isFloat) }, onDone = pop)
        }
        Route.Retention -> {
            val visit = remember(route) { System.nanoTime() }
            RetentionScreen(viewModel(key = "retention-$visit") { RetentionViewModel(field, tenantId, permissions) }, onDone = pop,
                onStatus = { key -> pop(); push(Route.RetentionStatus(key)) })
        }
        is Route.RemittanceOverdue -> RemittanceOverdueScreen(viewModel(key = "remittance-overdue-$scope-${route.id}") { RemittanceOverdueViewModel(field, route.id) })
        is Route.RetentionStatus -> RetentionStatusScreen(viewModel(key = "retention-status-$scope-${route.key}") { RetentionStatusViewModel(field, tenantId, route.key) })
        Route.RecordExpense -> {
            // A new key per visit: each form gets its own client id (exactly-once) and fresh GPS attempt.
            val visit = remember(route) { System.nanoTime() }
            val pettyCash = access?.pettyCashExpense == true
            val vm: ExpenseViewModel = viewModel(key = "expense-$visit") { ExpenseViewModel(field, tenantId, pettyCash) }
            ExpenseScreen(vm, onDone = pop)
        }
        is Route.CashForm -> {
            // Fuel events only while the company uses fuel capture.
            if (route.kind == CashFormViewModel.FUEL && !fuelOn) return
            val visit = remember(route) { System.nanoTime() }
            val vm: CashFormViewModel = viewModel(key = "cash-${route.kind}-$visit") { CashFormViewModel(field, tenantId, route.kind, permissions) }
            CashFormScreen(vm, onDone = pop)
        }
        Route.SyncStatus -> {
            val vm: SyncStatusViewModel = viewModel(key = "sync-status-$scope") { SyncStatusViewModel(field, tenantId) }
            SyncStatusScreen(vm, syncing, onRefresh = onRefresh)
        }
        is Route.ReadingDetail -> ReadingDetailScreen(field, snapshot, route.id, push, access)
        is Route.MachineDetail -> MachineDetailScreen(snapshot, route.machineId, push, access)
        is Route.ResetRequest -> {
            val visit = remember(route) { System.nanoTime() }
            val vm: ResetRequestViewModel = viewModel(key = "reset-$visit") { ResetRequestViewModel(field, tenantId, route.machineId, route.oldReading) }
            ResetRequestScreen(vm, snapshot, onDone = pop)
        }
        is Route.ResetDetail -> ResetDetailScreen(field, snapshot, route.key, push)
        is Route.FuelDetail -> if (fuelOn) FuelDetailScreen(snapshot, route.key, push)
        is Route.ExpenseDetail -> ExpenseDetailScreen(field, snapshot, route.key, permissions, onRecordExpense, push)
        is Route.CashDetail -> CashDetailScreen(field, tenantId, snapshot, route.key, route.collection, permissions, push)
        Route.PettyCash -> com.asseta.supervisor.ui.pettycash.MyPettyCashScreen(
            viewModel(key = "petty-cash-$scope") { com.asseta.supervisor.ui.pettycash.PettyCashViewModel(field, tenantId) }, access, syncing, onRefresh, push,
        )
        is Route.PettyCashAck -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.pettycash.PettyCashAckScreen(viewModel(key = "petty-ack-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashAckViewModel(field, tenantId, route.movementId) }, access, onDone = pop)
        }
        is Route.PettyCashTopUp -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.pettycash.PettyCashTopUpScreen(viewModel(key = "petty-topup-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashTopUpViewModel(field, tenantId, route.fundId) }, access, onDone = pop)
        }
        is Route.PettyCashReturn -> {
            val visit = remember(route) { System.nanoTime() }
            val accountsOn = access?.depositAccounts == true
            com.asseta.supervisor.ui.pettycash.PettyCashReturnScreen(viewModel(key = "petty-return-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashReturnViewModel(field, tenantId, route.fundId, accountsOn) }, access, onDone = pop)
        }
        is Route.PettyCashCount -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.pettycash.PettyCashCountScreen(viewModel(key = "petty-count-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashCountViewModel(field, tenantId, route.fundId) }, access, rememberOnline(), onDone = pop)
        }
        is Route.PettyCashHolderChange -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.pettycash.PettyCashHolderChangeScreen(viewModel(key = "petty-holder-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashHolderChangeViewModel(field, tenantId, route.changeId) }, access, onDone = pop)
        }
        is Route.PettyCashAdvance -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.pettycash.PettyCashAdvanceScreen(viewModel(key = "petty-advance-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashAdvanceViewModel(field, tenantId, route.advanceId) }, access, onDone = pop)
        }
        is Route.PettyCashGiveAdvance -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.pettycash.PettyCashGiveAdvanceScreen(
                viewModel(key = "petty-give-advance-$visit") { com.asseta.supervisor.ui.pettycash.PettyCashGiveAdvanceViewModel(field, tenantId, route.fundId, permissions) },
                access, onDone = pop,
            )
        }
        Route.Customers -> com.asseta.supervisor.ui.customers.CustomersScreen(
            viewModel(key = "customers-$scope") { com.asseta.supervisor.ui.customers.CustomersViewModel(field, tenantId) },
            canEdit = com.asseta.core.domain.customers.CustomerRules.canEdit(permissions), onRoute = push,
        )
        is Route.CustomerDetail -> com.asseta.supervisor.ui.customers.CustomerDetailScreen(
            viewModel(key = "customer-$scope-${route.customerId}") { com.asseta.supervisor.ui.customers.CustomerDetailViewModel(field, tenantId, route.customerId) },
            permissions, onRoute = push,
        )
        is Route.CustomerForm -> {
            val visit = remember(route) { System.nanoTime() }
            com.asseta.supervisor.ui.customers.CustomerFormScreen(
                viewModel(key = "customer-form-$visit") { com.asseta.supervisor.ui.customers.CustomerFormViewModel(field, tenantId, route.customerId, permissions) },
                onDone = pop,
            )
        }
        is Route.NotificationDetail -> {
            val notifications by inbox.notifications.collectAsStateWithLifecycle()
            NotificationDetailScreen(notifications.firstOrNull { it.id.toString() == route.id })
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
