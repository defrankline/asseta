package com.asseta.supervisor.ui

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.core.sync.data.JobSummary
import com.asseta.supervisor.FieldGraph
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
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { FieldBanners(field, tenantId) }
            item {
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
                item {
                    EmptyState("No assigned jobs", if (syncing) "Syncing…" else "Pull down to sync when you are online.")
                }
            }
            FieldTexts.jobSections(list.map { it.first }) { status[it] ?: it.job.status }.forEach { (title, jobs) ->
                item(key = "section-$title") { Text(title, style = MaterialTheme.typography.titleMedium) }
                items(jobs, key = { it.job.id }) { summary ->
                    JobRow(summary, status[summary] ?: summary.job.status) { onOpen(summary.job.id, summary.job.jobNumber) }
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
private fun JobRow(summary: JobSummary, displayStatus: String, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(summary.job.jobNumber, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                StatusBadge(displayStatus, summary.job.status)
            }
            val lines = listOfNotNull(FieldTexts.machine(summary), summary.siteName, summary.customerName)
            if (lines.isNotEmpty()) {
                Text(lines.joinToString("\n"), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** Status capsule (same colours as iOS: in progress blue, approved green, cancelled red, others grey). */
@Composable
fun StatusBadge(displayStatus: String, serverStatus: String) {
    val color = when (displayStatus) {
        JobStatus.IN_PROGRESS -> Color(0xFF1E6FD9)
        JobStatus.APPROVED -> Color(0xFF2E7D32)
        JobStatus.CANCELLED -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Text(
        FieldTexts.statusBadge(displayStatus, serverStatus),
        style = MaterialTheme.typography.labelMedium,
        color = color,
        modifier = Modifier.background(color.copy(alpha = 0.15f), RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

/** Entry points shown according to `/me` permissions; the server enforces them on every pushed operation. */
@Composable
private fun FinanceSection(permissions: Set<String>, onExpense: () -> Unit, onRoute: (Route) -> Unit) {
    val expenses = "tenant.expense.write" in permissions
    val cash = "tenant.collection.record" in permissions
    if (!expenses && !cash) return
    Section("Money & fuel") {
        if (expenses) ActionRow("Record expense", onClick = onExpense)
        if (cash) {
            ActionRow("Record cash collection") { onRoute(Route.CashForm(CashFormViewModel.COLLECTION)) }
            ActionRow("Hand over cash") { onRoute(Route.CashForm(CashFormViewModel.HANDOVER)) }
        }
        if (expenses) ActionRow("Fuel event") { onRoute(Route.CashForm(CashFormViewModel.FUEL)) }
        if (cash) ActionRow("My cash") { onRoute(Route.MyCash) }
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
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        val local = clock as? ClockStatus.Checked
        when {
            local?.alert == true -> Banner(FieldTexts.clockTamper(local.skewSeconds), warning = true)
            state?.serverClockAlert == true -> Banner(FieldTexts.SERVER_CLOCK, warning = true)
        }
        if (!online) Banner(FieldTexts.OFFLINE) else FieldTexts.lastSyncProblem(state?.lastError)?.let { Banner(it) }
    }
}

@Composable
private fun Banner(text: String, warning: Boolean = false) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = if (warning) Color(0xFFB25E00) else MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.fillMaxWidth(),
    )
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

@Composable
fun EmptyState(title: String, message: String) {
    Box(Modifier.fillMaxWidth().padding(vertical = 32.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
