package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.JobStatus

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.ActivityTypes
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.domain.inbox.JobFigures
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.supervisor.FieldGraph
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.R
import com.asseta.core.ui.R as CoreR
import kotlinx.serialization.json.Json
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.owner.NonRevenueActivityDto
import com.asseta.supervisor.ui.accountability.NonRevenueText
import com.asseta.supervisor.ui.accountability.nonRevenueColor
import kotlinx.serialization.json.jsonObject

/**
 * One job: details, a summary (readings, meter hours, work totals, findings), the next allowed actions, my readings,
 * the work log (server + this phone), the customer acknowledgement, expenses & fuel, and the local timeline.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobDetailScreen(
    vm: JobDetailViewModel,
    snapshot: InboxSnapshot,
    onCapture: (ReadingKind) -> Unit,
    onAcknowledge: () -> Unit,
    onWorkLogEntry: () -> Unit,
    onRoute: (Route) -> Unit,
    field: FieldGraph,
    access: FieldAccess? = null,
    online: Boolean = false,
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val nonRevenue by vm.nonRevenue.collectAsStateWithLifecycle()
    val showNonRevenue = access?.nonRevenueStatus == true
    // DEC-031 R1: statuses of the job's non-revenue entries, read online (again after an explanation was sent).
    LaunchedEffect(showNonRevenue, online) { if (showNonRevenue && online) vm.loadNonRevenue() }
    val error by vm.error.collectAsStateWithLifecycle()
    var confirm by remember { mutableStateOf<String?>(null) } // START | COMPLETE
    val job = ui.job
    if (!ui.loaded) return
    if (job == null) {
        EmptyState("Job not available", "It is no longer assigned to you on this device.")
        return
    }
    val actions = ui.actions
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    // Pull to refresh re-reads the non-revenue statuses (online; same as iOS).
    PullToRefreshBox(isRefreshing = refreshing, onRefresh = { if (showNonRevenue && online) vm.loadNonRevenue() }, modifier = Modifier.fillMaxSize()) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Section(null) {
            LabeledRow("Status", "") { StatusBadge(ui.state?.effectiveStatus ?: job.status, job.status) }
            ui.machine?.let { m ->
                LabeledRow("Machine", "${m.assetCode} · ${m.name}")
                LabeledRow("Meter precision", FieldTexts.meterPrecision(m.meterDecimalPlaces))
            }
            ui.summary?.siteName?.let { LabeledRow("Site", it) }
            ui.summary?.customerName?.let { LabeledRow("Customer", it) }
            LabeledRow("Planned start", LocalTime.formatIso(job.plannedStart))
            job.requestNote?.takeIf { it.isNotBlank() }?.let { LabeledRow(JobRequestTexts.NOTE, it) }
            if (job.status == JobStatus.CANCELLED) job.cancellationReason?.takeIf { it.isNotBlank() }?.let { LabeledRow("Reason", it) }
        }

        JobSummarySection(snapshot, job.id)

        Section("Next steps") {
            val blocked = ui.captureBlocked
            if (blocked != null && actions.showsCapture) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(R.drawable.ic_lock_warning), contentDescription = null, tint = WarningColor, modifier = Modifier.size(18.dp))
                    Text(blocked, color = WarningColor, style = AssetaType.footnote)
                }
            }
            if (actions.canOpening) ActionRow("Capture opening reading", R.drawable.ic_gauge, enabled = blocked == null) { onCapture(ReadingKind.OPENING) }
            if (actions.canStart) ActionRow("Start job", R.drawable.ic_play) { confirm = START }
            if (actions.canClosing) ActionRow("Capture closing reading", R.drawable.ic_gauge, enabled = blocked == null) { onCapture(ReadingKind.CLOSING) }
            if (actions.canAcknowledge) ActionRow("Customer acknowledgement", R.drawable.ic_signature, onClick = onAcknowledge)
            if (actions.canComplete) ActionRow("Complete job", R.drawable.ic_check_seal) { confirm = COMPLETE }
            if (actions.isClosed) Text("No further actions on this job.", color = palette.secondaryText)
        }

        JobReadingsSection(snapshot, job.id, onRoute)

        WorkLogSection(
            ui, vm, snapshot, job.id, actions.canLogWork, onWorkLogEntry,
            nonRevenue = if (showNonRevenue) nonRevenue else emptyMap(),
            canExplain = access?.explainNonRevenue == true, online = online,
            onExplain = { onRoute(Route.ExplainNonRevenue(it)) },
        )

        AcknowledgementSection(field, snapshot, job.id)

        JobMoneySection(snapshot, job.id, onRoute)

        if (ui.operations.isNotEmpty()) {
            Section("Recorded on this phone") {
                ui.operations.forEach { OperationRow(it) }
            }
        }
    }
    }
    confirm?.let { action ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text(if (action == START) "Start this job?" else "Complete this job?") },
            text = { Text("This is recorded now with the phone's time and synced when possible.") },
            confirmButton = {
                TextButton(onClick = { confirm = null; if (action == START) vm.start() else vm.complete() }) {
                    Text(if (action == START) "Start job" else "Complete job")
                }
            },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } },
        )
    }
    NotSavedAlert(error, vm::clearError)
}

@Composable
private fun WorkLogSection(
    ui: JobDetailUi,
    vm: JobDetailViewModel,
    snapshot: InboxSnapshot,
    jobId: String,
    canLog: Boolean,
    onWorkLogEntry: () -> Unit,
    nonRevenue: Map<String, NonRevenueActivityDto> = emptyMap(),
    canExplain: Boolean = false,
    online: Boolean = false,
    onExplain: (NonRevenueActivityDto) -> Unit = {},
) {
    val entries = snapshot.activities.filter { it.jobId == jobId }
    if (entries.isEmpty() && !canLog) return
    Section("Work log", footer = if (entries.isEmpty()) null else "Entries recorded on this phone and those the server has.") {
        entries.forEach { e ->
            val span = LocalTime.formatTime(e.startMs) + (e.endMs?.let { " → " + LocalTime.formatTime(it) } ?: if (e.running) " → running" else "")
            val duration = e.endMs?.let { JobFigures.duration((it - e.startMs) / 60_000) }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${FieldTexts.activityType(e.activityType)} $span" + (duration?.let { " ($it)" } ?: "") + (e.note?.let { " · $it" } ?: ""),
                    style = AssetaType.subheadline, modifier = Modifier.weight(1f),
                )
                if (!e.running) StatusPill(e.status)
            }
            // Non-revenue time (DEC-031 R1): its approval status and, for explain holders, "Explain" (online only).
            e.serverId?.let(nonRevenue::get)?.let { nr ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        NonRevenueText.status(nr.approvalStatus), style = AssetaType.caption,
                        color = nonRevenueColor(NonRevenueText.tone(nr.approvalStatus)), modifier = Modifier.weight(1f),
                    )
                    if (canExplain && NonRevenueText.canExplain(nr.approvalStatus)) {
                        TextButton(onClick = { onExplain(nr) }, enabled = online) { Text(NonRevenueText.EXPLAIN) }
                    }
                }
            }
        }
        if (canLog) {
            val running = ui.runningEntry
            if (running != null) {
                ActionRow("Stop ${running.activityType.lowercase()}", R.drawable.ic_stop_circle) { vm.stopEntry(running.clientId) }
            } else {
                ActionRow("Start work", R.drawable.ic_play_circle) { vm.startEntry(ActivityTypes.WORK) }
                ActionRow("Standby", R.drawable.ic_pause_circle) { vm.startEntry(ActivityTypes.STANDBY) }
                ActionRow("Downtime", R.drawable.ic_wrench) { vm.startEntry(ActivityTypes.DOWNTIME) }
            }
            ActionRow("Add work log entry", R.drawable.ic_clipboard, onClick = onWorkLogEntry)
        }
    }
}

/** A local operation with its sync state. */
@Composable
private fun OperationRow(op: ClientOperationEntity) {
    val payload = remember(op.payloadJson) { runCatching { Json.parseToJsonElement(op.payloadJson).jsonObject }.getOrNull() }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(FieldTexts.operationTitle(op.opType, payload), style = AssetaType.subheadline, modifier = Modifier.weight(1f))
            SyncStateLabel(op.status)
        }
        Text(LocalTime.formatSeconds(op.createdAtDevice), style = AssetaType.caption, color = palette.secondaryText)
        val code = op.errorCode
        if (code != null && op.status != ClientOperationStatus.PENDING) {
            Text("$code: ${op.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline)
        }
    }
}

/** Sync state of a local record: symbol and text in the state's colour (the iOS `SyncStateLabel`). */
@Composable
fun SyncStateLabel(status: ClientOperationStatus) {
    val p = palette
    val color = when (status) {
        ClientOperationStatus.ACKED -> p.live
        ClientOperationStatus.FAILED, ClientOperationStatus.CONFLICT -> p.offline
        ClientOperationStatus.QUARANTINED -> p.warning
        else -> p.secondaryText
    }
    val icon = when (status) {
        ClientOperationStatus.ACKED -> R.drawable.ic_check_circle
        ClientOperationStatus.FAILED -> R.drawable.ic_rejected
        ClientOperationStatus.CONFLICT -> R.drawable.ic_warning
        ClientOperationStatus.QUARANTINED -> R.drawable.ic_pause_circle
        else -> CoreR.drawable.ic_clock
    }
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(painterResource(icon), contentDescription = null, tint = color, modifier = Modifier.size(14.dp))
        Text(FieldTexts.syncState(status), style = MaterialTheme.typography.labelMedium, color = color)
    }
}

private const val START = "START"
private const val COMPLETE = "COMPLETE"
