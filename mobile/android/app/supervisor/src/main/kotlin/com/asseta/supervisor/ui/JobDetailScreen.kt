package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.ActivityTypes
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject

/** One job: details, the next allowed actions, the work log and the local timeline with sync states. */
@Composable
fun JobDetailScreen(
    vm: JobDetailViewModel,
    onCapture: (ReadingKind) -> Unit,
    onAcknowledge: () -> Unit,
    onWorkLogEntry: () -> Unit,
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    var confirm by remember { mutableStateOf<String?>(null) } // START | COMPLETE
    val job = ui.job
    if (!ui.loaded) return
    if (job == null) {
        EmptyState("Job not available", "It is no longer assigned to you on this device.")
        return
    }
    val actions = ui.actions
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
        }

        Section("Next steps") {
            val blocked = ui.captureBlocked
            if (blocked != null && actions.showsCapture) {
                Text(blocked, color = WarningColor, style = MaterialTheme.typography.bodySmall)
            }
            if (actions.canOpening) ActionRow("Capture opening reading", enabled = blocked == null) { onCapture(ReadingKind.OPENING) }
            if (actions.canStart) ActionRow("Start job") { confirm = START }
            if (actions.canClosing) ActionRow("Capture closing reading", enabled = blocked == null) { onCapture(ReadingKind.CLOSING) }
            if (actions.canAcknowledge) ActionRow("Customer acknowledgement", onClick = onAcknowledge)
            if (actions.canComplete) ActionRow("Complete job") { confirm = COMPLETE }
            if (actions.isClosed) Text("No further actions on this job.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        if (actions.canLogWork) WorkLogSection(ui, vm, onWorkLogEntry)

        if (ui.operations.isNotEmpty()) {
            Section("Recorded on this phone") {
                ui.operations.forEach { OperationRow(it) }
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
private fun WorkLogSection(ui: JobDetailUi, vm: JobDetailViewModel, onWorkLogEntry: () -> Unit) {
    Section("Work log") {
        ui.workLog.forEach { e ->
            val span = LocalTime.formatTime(e.startedAt) +
                (e.endedAt?.let { " → " + LocalTime.formatTime(it) } ?: if (e.operationId == null) " → running" else "")
            Text("${FieldTexts.activityType(e.activityType)} $span${e.note?.let { " · $it" } ?: ""}", style = MaterialTheme.typography.bodyMedium)
        }
        val running = ui.runningEntry
        if (running != null) {
            ActionRow("Stop ${running.activityType.lowercase()}") { vm.stopEntry(running.clientId) }
        } else {
            ActionRow("Start work") { vm.startEntry(ActivityTypes.WORK) }
            ActionRow("Standby") { vm.startEntry(ActivityTypes.STANDBY) }
            ActionRow("Downtime") { vm.startEntry(ActivityTypes.DOWNTIME) }
        }
        ActionRow("Add work log entry", onClick = onWorkLogEntry)
    }
}

/** A local operation with its sync state. */
@Composable
private fun OperationRow(op: ClientOperationEntity) {
    val payload = remember(op.payloadJson) { runCatching { Json.parseToJsonElement(op.payloadJson).jsonObject }.getOrNull() }
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(FieldTexts.operationTitle(op.opType, payload), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            SyncStateLabel(op.status)
        }
        Text(LocalTime.formatSeconds(op.createdAtDevice), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val code = op.errorCode
        if (code != null && op.status != ClientOperationStatus.PENDING) {
            Text("$code: ${op.lastError.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
fun SyncStateLabel(status: ClientOperationStatus) {
    val color = when (status) {
        ClientOperationStatus.ACKED -> androidx.compose.ui.graphics.Color(0xFF2E7D32)
        ClientOperationStatus.FAILED, ClientOperationStatus.CONFLICT -> MaterialTheme.colorScheme.error
        ClientOperationStatus.QUARANTINED -> WarningColor
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Text(FieldTexts.syncState(status), style = MaterialTheme.typography.labelMedium, color = color)
}

private const val START = "START"
private const val COMPLETE = "COMPLETE"
