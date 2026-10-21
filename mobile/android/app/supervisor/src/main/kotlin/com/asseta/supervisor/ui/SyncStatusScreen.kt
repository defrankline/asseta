package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.sync.engine.SyncReport
import com.asseta.supervisor.FieldGraph
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class SyncStatusUi(
    val operations: List<ClientOperationEntity> = emptyList(),
    val state: SyncStateEntity? = null,
    val pendingUploads: Int = 0,
    val running: Boolean = false,
    val lastReport: String? = null,
)

class SyncStatusViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
    private val running = MutableStateFlow(false)
    private val report = MutableStateFlow<String?>(null)

    val ui: StateFlow<SyncStatusUi> = combine(
        field.repository.observeUnsynced(tenantId), field.repository.observeSyncState(tenantId),
        field.repository.observePendingUploads(tenantId), running, report,
    ) { ops, state, uploads, r, last -> SyncStatusUi(ops, state, uploads, r, last) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SyncStatusUi())

    fun syncNow() {
        if (running.value) return
        viewModelScope.launch {
            running.value = true
            report.value = when (val r = field.engine.sync(tenantId)) {
                is SyncReport.Success -> "Synced: ${r.push.acked} confirmed, ${r.push.deferred} waiting, ${r.push.problems} need attention."
                is SyncReport.Retry -> "Offline or server busy; will retry automatically.".also { field.scheduler.scheduleRetry(r.retryAfterMs) }
                is SyncReport.Failed -> "Sync error ${r.code}: ${r.message}".also { field.scheduler.scheduleRetry(r.retryAfterMs) }
                SyncReport.AuthRequired -> "Sign in again to sync. Your data stays on this device."
                is SyncReport.Revoked -> r.message
            }
            running.value = false
        }
    }
}

/** Everything not yet durably acknowledged by the server, with the reason it is waiting. */
@Composable
fun SyncStatusScreen(vm: SyncStatusViewModel) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Text("Sync status", style = MaterialTheme.typography.headlineSmall)
            val last = ui.state?.lastSyncAt?.let { "Last sync ${LocalTime.format(it)}" } ?: "Not synced yet"
            Text("$last · ${ui.pendingUploads} photo/signature/receipt upload(s) waiting" + (ui.state?.lastError?.let { " · last error $it" } ?: ""))
            Button(onClick = vm::syncNow, enabled = !ui.running, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text(if (ui.running) "Syncing…" else "Sync now")
            }
            ui.lastReport?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
        }
        if (ui.operations.isEmpty()) item { Text("Everything recorded on this device has been confirmed by the server.") }
        items(ui.operations, key = { it.id }) { op -> OperationCard(op) }
    }
}

@Composable
private fun OperationCard(op: ClientOperationEntity) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("${op.opType} · ${statusLabel(op.status)}", style = MaterialTheme.typography.titleSmall,
                color = if (op.status in PROBLEMS) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            Text("Recorded ${LocalTime.format(op.createdAtDevice)} · attempts ${op.attemptCount}", style = MaterialTheme.typography.bodySmall)
            op.errorCode?.let { Text("Code: $it${op.lastError?.let { m -> " — $m" } ?: ""}", style = MaterialTheme.typography.bodySmall) }
            if (op.status == ClientOperationStatus.CONFLICT) {
                Text("Server state: ${op.resultJson?.let(::serverState) ?: "unknown"}. Your original record is kept; ask the office to review.",
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private val PROBLEMS = setOf(ClientOperationStatus.FAILED, ClientOperationStatus.CONFLICT, ClientOperationStatus.QUARANTINED)

private fun statusLabel(status: ClientOperationStatus) = when (status) {
    ClientOperationStatus.PENDING -> "waiting to send"
    ClientOperationStatus.SENT -> "sending"
    ClientOperationStatus.ACKED -> "confirmed"
    ClientOperationStatus.FAILED -> "rejected by server"
    ClientOperationStatus.CONFLICT -> "conflict"
    ClientOperationStatus.QUARANTINED -> "held: subscription read-only (will resend)"
}

private fun serverState(resultJson: String): String = Regex("\"server_state\"\\s*:\\s*(\\{[^}]*\\})").find(resultJson)?.groupValues?.get(1) ?: "not provided"
