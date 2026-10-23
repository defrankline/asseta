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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.sync.ClockStatus
import com.asseta.core.database.MachineEntity
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.data.ReadingItem
import androidx.compose.runtime.saveable.rememberSaveable
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.core.ui.R as CoreR
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine

/**
 * Jobs tab: warnings, then my jobs by segment (in progress, ready to start, recently closed) from the offline cache,
 * or my machines with their latest reading and active job.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobsScreen(
    field: FieldGraph,
    tenantId: String,
    snapshot: InboxSnapshot,
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
    var segment by rememberSaveable { mutableStateOf(JobSegment.IN_PROGRESS) }
    var chosen by rememberSaveable { mutableStateOf(false) } // the user picked a segment: stop auto-selecting
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        val list = rows
        if (list == null) {
            Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
                Text("Opening your jobs…", Modifier.padding(top = 12.dp))
            }
            return@PullToRefreshBox
        }
        LaunchedEffect(list.isEmpty()) { if (!chosen) segment = InboxTexts.defaultSegment(list.map { it.second }) }
        val status = list.toMap()
        val inSegment = list.filter { InboxTexts.segment(it.second) == segment }.map { it.first }
            .let { jobs -> if (segment == JobSegment.CLOSED) jobs.sortedByDescending { it.job.plannedStart } else jobs }
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            item(key = "banners") { FieldBanners(field, tenantId) }
            item(key = "segments") {
                FilterChipRow(JobSegment.entries.map { it to it.label }, segment, { segment = it; chosen = true }, Modifier.padding(bottom = 8.dp))
            }
            if (segment == JobSegment.MACHINES) {
                val machines = machineRows(snapshot, list.map { it.first }, status)
                if (machines.isEmpty()) {
                    item(key = "empty") { InboxTexts.jobsEmpty(segment).let { (t, m) -> EmptyState(t, if (syncing) "Syncing…" else m) } }
                }
                groupedSection(
                    keyPrefix = "machines",
                    items = machines.map { row ->
                        GroupedItem(row.machine.id, onClick = { onRoute(Route.MachineDetail(row.machine.id, row.machine.assetCode)) }) {
                            InboxRow(
                                InboxTexts.machine(row.machine.assetCode, row.machine.name), null,
                                row.latest?.let { "Latest reading ${it.reading} · ${LocalTime.format(it.atMs)}" } ?: "No readings yet",
                                row.activeJob?.let { "Active job ${it.job.jobNumber}" },
                            )
                        }
                    },
                )
            } else {
                if (inSegment.isEmpty()) {
                    item(key = "empty") { InboxTexts.jobsEmpty(segment).let { (t, m) -> EmptyState(t, if (syncing) "Syncing…" else m) } }
                }
                groupedSection(
                    keyPrefix = "jobs-${segment.name}",
                    items = inSegment.map { summary ->
                        GroupedItem(summary.job.id, onClick = { onOpen(summary.job.id, summary.job.jobNumber) }) {
                            JobRow(summary, status[summary] ?: summary.job.status)
                        }
                    },
                )
            }
        }
    }
}

/** A machine of mine: its latest reading from my captures and its active job. */
data class MachineRow(val machine: MachineEntity, val latest: ReadingItem?, val activeJob: JobSummary?)

fun machineRows(snapshot: InboxSnapshot, jobs: List<JobSummary>, status: Map<JobSummary, String>): List<MachineRow> {
    val latest = snapshot.latestReadingByMachine()
    val active = jobs.filter { (status[it] ?: it.job.status) in setOf(JobStatus.IN_PROGRESS, JobStatus.APPROVED) }
        .sortedBy { if ((status[it] ?: it.job.status) == JobStatus.IN_PROGRESS) 0 else 1 }
        .groupBy { it.job.machineId }.mapValues { it.value.first() }
    return snapshot.machines.values.sortedBy { it.assetCode }.map { MachineRow(it, latest[it.id], active[it.id]) }
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
