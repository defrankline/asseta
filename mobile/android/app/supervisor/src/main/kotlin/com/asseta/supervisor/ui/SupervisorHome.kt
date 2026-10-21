package com.asseta.supervisor.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.supervisor.FieldGraph
import kotlinx.coroutines.delay
import kotlin.math.abs

/** In-app routes (state-based navigation; no extra navigation dependency). */
sealed interface Route {
    data object Jobs : Route
    data class JobDetail(val jobId: String) : Route
    data class Capture(val jobId: String, val kind: ReadingKind) : Route
    data class Acknowledge(val jobId: String) : Route
    data object SyncStatus : Route
}

@Composable
fun SupervisorHome(field: FieldGraph, tenantId: String, onSwitchTenant: () -> Unit, modifier: Modifier = Modifier) {
    var stack by remember(tenantId) { mutableStateOf(listOf<Route>(Route.Jobs)) }
    val route = stack.last()
    fun push(r: Route) { stack = stack + r }
    fun pop() { if (stack.size > 1) stack = stack.dropLast(1) }
    BackHandler(enabled = stack.size > 1) { pop() }

    LaunchedEffect(tenantId) {
        // First login: register device + bootstrap; afterwards periodic delta pull and push in the background.
        field.scheduler.ensurePeriodic()
        field.scheduler.syncNow()
    }

    Column(modifier.fillMaxSize()) {
        ClockBanner(field, tenantId)
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            if (stack.size > 1) TextButton(onClick = ::pop) { Text("‹ Back") } else TextButton(onClick = onSwitchTenant) { Text("Switch tenant") }
            SyncChip(field, tenantId) { if (route != Route.SyncStatus) push(Route.SyncStatus) }
        }
        when (route) {
            Route.Jobs -> JobsScreen(field, tenantId, onOpen = { push(Route.JobDetail(it)) })
            is Route.JobDetail -> {
                val vm: JobDetailViewModel = viewModel(key = "job-$tenantId-${route.jobId}") { JobDetailViewModel(field, tenantId, route.jobId) }
                JobDetailScreen(vm, onCapture = { push(Route.Capture(route.jobId, it)) }, onAcknowledge = { push(Route.Acknowledge(route.jobId)) })
            }
            is Route.Capture -> {
                // A new key per visit: each capture gets its own id and fresh GPS attempt.
                val visit = remember(route) { System.nanoTime() }
                val vm: CaptureViewModel = viewModel(key = "capture-$visit") { CaptureViewModel(field, tenantId, route.jobId, route.kind) }
                CaptureScreen(vm, onDone = ::pop)
            }
            is Route.Acknowledge -> AcknowledgementScreen(field, tenantId, route.jobId, onDone = ::pop)
            Route.SyncStatus -> {
                val vm: SyncStatusViewModel = viewModel(key = "sync-$tenantId") { SyncStatusViewModel(field, tenantId) }
                SyncStatusScreen(vm)
            }
        }
    }
}

@Composable
private fun SyncChip(field: FieldGraph, tenantId: String, onClick: () -> Unit) {
    val unsynced by remember(tenantId) { field.repository.observeUnsynced(tenantId) }.collectAsStateWithLifecycle(emptyList())
    val label = if (unsynced.isEmpty()) "All synced" else "${unsynced.size} to sync"
    TextButton(onClick = onClick) { Text(label) }
}

/**
 * Local clock-tamper alert: compares the device clock with the last trusted server time plus monotonic elapsed time
 * (threshold 300 s), and shows the server's own skew verdict from the last push. Device time is still recorded as-is.
 */
@Composable
private fun ClockBanner(field: FieldGraph, tenantId: String) {
    val state by remember(tenantId) { field.repository.observeSyncState(tenantId) }.collectAsStateWithLifecycle(null)
    val status by produceState<ClockStatus>(ClockStatus.Unknown, state) {
        while (true) {
            value = field.repository.clockStatus(state)
            delay(30_000)
        }
    }
    val local = status as? ClockStatus.Checked
    if (local?.alert != true && state?.serverClockAlert != true) return
    val minutes = local?.let { abs(it.skewSeconds) / 60 }
    Card(
        Modifier.fillMaxWidth().padding(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Text(
            "Device clock warning: this phone's time differs from server time" + (minutes?.let { " by about $it min" } ?: "") +
                ". Readings record the time shown on this device and will be flagged; please correct the date/time settings.",
            modifier = Modifier.padding(12.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
