package com.asseta.supervisor.ui

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.annotation.DrawableRes
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.core.ui.R as CoreR
import com.asseta.supervisor.ui.finance.CashFormViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/** Supervisor home: warnings, money & fuel entry points and the assigned jobs (from the offline cache). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobsScreen(
    field: FieldGraph,
    tenantId: String,
    permissions: Set<String>,
    syncing: Boolean,
    onRefresh: () -> Unit,
    onOpen: (jobId: String, jobNumber: String) -> Unit,
    onRoute: (Route) -> Unit,
) {
    // null until the encrypted store has answered once ("Opening your jobs…").
    val rows by remember(tenantId) {
        combine(field.repository.observeJobs(tenantId), field.repository.observeOperationsByJob(tenantId)) { jobs, ops ->
            jobs.map { it to field.repository.fieldState(it.job, ops[it.job.id].orEmpty()).effectiveStatus }
        }
    }.collectAsStateWithLifecycle(null)
    val scope = rememberCoroutineScope()
    var blockedExpense by remember { mutableStateOf<String?>(null) }
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        val list = rows
        if (list == null) {
            Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
                Text("Opening your jobs…", Modifier.padding(top = 12.dp))
            }
            return@PullToRefreshBox
        }
        val status = list.toMap()
        // The iOS home `List`: warnings, "Money & fuel", then the jobs grouped by state, each row opening the job.
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            item(key = "banners") { FieldBanners(field, tenantId) }
            item(key = "finance") {
                FinanceSection(
                    permissions,
                    onExpense = {
                        scope.launch {
                            when (val gate = field.financeRepository.expensePolicy(tenantId)) {
                                is ExpensePolicyDecision.Blocked -> blockedExpense = gate.message
                                is ExpensePolicyDecision.Allowed -> onRoute(Route.RecordExpense)
                            }
                        }
                    },
                    onRoute = onRoute,
                )
            }
            if (list.isEmpty()) {
                item(key = "empty") {
                    EmptyState("No assigned jobs", if (syncing) "Syncing…" else "Pull down to sync when you are online.")
                }
            }
            FieldTexts.jobSections(list.map { it.first }) { status[it] ?: it.job.status }.forEach { (title, jobs) ->
                groupedSection(
                    keyPrefix = "section-$title",
                    header = title,
                    items = jobs.map { summary ->
                        GroupedItem(summary.job.id, onClick = { onOpen(summary.job.id, summary.job.jobNumber) }) {
                            JobRow(summary, status[summary] ?: summary.job.status)
                        }
                    },
                )
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
private fun JobRow(summary: JobSummary, displayStatus: String) {
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(summary.job.jobNumber, style = AssetaType.headline, modifier = Modifier.weight(1f))
            StatusBadge(displayStatus, summary.job.status)
        }
        val lines = listOfNotNull(FieldTexts.machine(summary), summary.siteName, summary.customerName)
        if (lines.isNotEmpty()) {
            Text(lines.joinToString("\n"), style = AssetaType.subheadline, color = palette.secondaryText)
        }
    }
}

/** Status capsule (same colours as iOS: in progress blue, approved green, cancelled red, others grey). */
@Composable
fun StatusBadge(displayStatus: String, serverStatus: String) {
    val p = palette
    val color = when (displayStatus) {
        JobStatus.IN_PROGRESS -> p.recent
        JobStatus.APPROVED -> p.live
        JobStatus.CANCELLED -> p.offline
        else -> p.neutral
    }
    Pill(FieldTexts.statusBadge(displayStatus, serverStatus), color)
}

/** Entry points shown according to `/me` permissions; the server enforces them on every pushed operation. */
@Composable
private fun FinanceSection(permissions: Set<String>, onExpense: () -> Unit, onRoute: (Route) -> Unit) {
    val expenses = "tenant.expense.write" in permissions
    val cash = "tenant.collection.record" in permissions
    if (!expenses && !cash) return
    GroupedSection(header = "Money & fuel") {
        if (expenses) ActionRow("Record expense", R.drawable.ic_receipt, onClick = onExpense)
        if (cash) {
            ActionRow("Record cash collection", R.drawable.ic_banknote) { onRoute(Route.CashForm(CashFormViewModel.COLLECTION)) }
            ActionRow("Hand over cash", R.drawable.ic_hand_over) { onRoute(Route.CashForm(CashFormViewModel.HANDOVER)) }
        }
        if (expenses) ActionRow("Fuel event", R.drawable.ic_fuel) { onRoute(Route.CashForm(CashFormViewModel.FUEL)) }
        if (cash) LinkActionRow("My cash", R.drawable.ic_wallet) { onRoute(Route.MyCash) }
    }
}

/** Warnings above the job list: clock tamper, server skew, offline state, last sync failure. */
@Composable
private fun FieldBanners(field: FieldGraph, tenantId: String) {
    val state by remember(tenantId) { field.repository.observeSyncState(tenantId) }.collectAsStateWithLifecycle(null)
    val clock by produceState<ClockStatus>(ClockStatus.Unknown, state) {
        while (true) {
            value = field.repository.clockStatus(state)
            delay(30_000)
        }
    }
    val online = rememberOnline()
    val local = clock as? ClockStatus.Checked
    val clockText = when {
        local?.alert == true -> FieldTexts.clockTamper(local.skewSeconds)
        state?.serverClockAlert == true -> FieldTexts.SERVER_CLOCK
        else -> null
    }
    val syncProblem = if (online) FieldTexts.lastSyncProblem(state?.lastError) else null
    if (clockText == null && online && syncProblem == null) return
    // The iOS `FieldBanners` rows: a symbol and a footnote, warnings in amber.
    GroupedSection {
        clockText?.let { Banner(CoreR.drawable.ic_clock_alert, it, WarningColor) }
        if (!online) Banner(CoreR.drawable.ic_wifi_off, FieldTexts.OFFLINE) else syncProblem?.let { Banner(R.drawable.ic_cloud_alert, it) }
    }
}

@Composable
private fun Banner(@DrawableRes icon: Int, text: String, tint: Color = palette.secondaryText) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(painterResource(icon), contentDescription = null, tint = tint, modifier = Modifier.size(22.dp))
        Text(text, style = AssetaType.footnote)
    }
}

/** Whether the phone currently has a validated internet connection (updates live). */
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
