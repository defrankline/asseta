package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.sync.ActivityTypes
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
fun JobDetailScreen(vm: JobDetailViewModel, onCapture: (ReadingKind) -> Unit, onAcknowledge: () -> Unit) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val job = ui.job
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (job == null) {
            Text("This job is no longer on this device.")
            return
        }
        Text(job.jobNumber, style = MaterialTheme.typography.headlineSmall)
        Text(ui.machine?.let { "${it.assetCode} · ${it.name} · meter ${it.meterDecimalPlaces} dp" } ?: "")
        Text("Server status: ${job.status}" + (ui.state?.effectiveStatus?.takeIf { it != job.status }?.let { " · on this device: $it (pending sync)" } ?: ""))
        message?.let { NoticeCard("Job", it) }

        Section("Readings") {
            ui.captures.forEach { c ->
                Text("${c.kind}: ${c.reading} (${c.captureMode}${if (c.ocrValue != null && c.ocrValue != c.reading) ", corrected from ${c.ocrValue}" else ""}) · GPS ${c.gpsStatus}",
                    style = MaterialTheme.typography.bodyMedium)
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (ui.canOpening) Button(onClick = { onCapture(ReadingKind.OPENING) }) { Text("Opening reading") }
                if (ui.canStart) Button(onClick = vm::start) { Text("Start job") }
                if (ui.canClosing) Button(onClick = { onCapture(ReadingKind.CLOSING) }) { Text("Closing reading") }
                if (ui.canAcknowledge) Button(onClick = onAcknowledge) { Text("Customer acknowledgement") }
                if (ui.canComplete && ui.state?.completeQueued == false) Button(onClick = vm::complete) { Text("Complete job") }
            }
        }

        if (ui.canLogWork) WorkLogSection(ui, vm)

        Section("Sync for this job") {
            if (ui.operations.isEmpty()) Text("Nothing recorded yet.")
            ui.operations.forEach { op ->
                Text("${op.opType} · ${op.status}${op.errorCode?.let { " · $it" } ?: ""}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun WorkLogSection(ui: JobDetailUi, vm: JobDetailViewModel) {
    var note by remember { mutableStateOf("") }
    Section("Work log") {
        ui.workLog.forEach { e ->
            val span = LocalTime.format(e.startedAt) +
                (e.endedAt?.let { " → " + LocalTime.formatTime(it) } ?: if (e.operationId == null) " → running" else "")
            Text("${e.activityType} $span${e.note?.let { " · $it" } ?: ""}", style = MaterialTheme.typography.bodyMedium)
        }
        val running = ui.runningEntry
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (running != null) {
                Button(onClick = { vm.stopEntry(running.clientId) }) { Text("Stop ${running.activityType.lowercase()}") }
            } else {
                OutlinedButton(onClick = { vm.startEntry(ActivityTypes.WORK) }) { Text("Start work") }
                OutlinedButton(onClick = { vm.startEntry(ActivityTypes.STANDBY) }) { Text("Standby") }
                OutlinedButton(onClick = { vm.startEntry(ActivityTypes.DOWNTIME) }) { Text("Downtime") }
            }
        }
        OutlinedTextField(note, { note = it }, label = { Text("Note") }, modifier = Modifier.fillMaxWidth())
        OutlinedButton(onClick = { vm.addNote(note); note = "" }, enabled = note.isNotBlank()) { Text("Add note") }
    }
}

@Composable
fun Section(title: String, content: @Composable () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            HorizontalDivider()
            content()
        }
    }
}

/** Device-local display of device timestamps (stored and sent as UTC ISO-8601). */
object LocalTime {
    private val dateTime = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm").withZone(ZoneId.systemDefault())
    private val time = DateTimeFormatter.ofPattern("HH:mm").withZone(ZoneId.systemDefault())
    fun format(epochMs: Long): String = dateTime.format(Instant.ofEpochMilli(epochMs))
    fun formatTime(epochMs: Long): String = time.format(Instant.ofEpochMilli(epochMs))
}
