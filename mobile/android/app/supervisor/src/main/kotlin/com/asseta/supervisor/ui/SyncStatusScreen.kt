package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.ui.theme.palette
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.HeldOwner
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.sync.data.WaitingReason
import com.asseta.supervisor.FieldGraph
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

/** One unsynced operation as shown on the sync status screen. */
data class OutboxItem(
    val operation: ClientOperationEntity,
    val title: String,
    val jobNumber: String?,
    /** `server_state` returned with a conflict (e.g. the job's current status), if any. */
    val serverState: String?,
    val waiting: WaitingReason?,
)

data class SyncStatusUi(
    val items: List<OutboxItem> = emptyList(),
    val counts: Map<ClientOperationStatus, Int> = emptyMap(),
    val state: SyncStateEntity? = null,
    val pendingUploads: Int = 0,
    /** Evidence files that can never be uploaded (missing or changed on this phone, refused for good). */
    val failedUploads: List<AttachmentEntity> = emptyList(),
    /** Unsynced work of other accounts on this phone, held until they sign in again (never sent under this user). */
    val held: List<HeldOwner> = emptyList(),
) {
    val unsynced: Int get() = counts.filterKeys { it != ClientOperationStatus.ACKED }.values.sum()
}

class SyncStatusViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
    val deviceId: String by lazy { field.deviceId }

    val ui: StateFlow<SyncStatusUi> = combine(
        combine(field.repository.observeUnsynced(tenantId), field.repository.observeHeld(tenantId)) { o, h -> o to h },
        field.repository.observeStatusCounts(tenantId),
        field.repository.observeSyncState(tenantId),
        combine(field.repository.observePendingUploads(tenantId), field.repository.observeFailedUploads(tenantId)) { p, f -> p to f },
        field.repository.observeJobs(tenantId),
    ) { (ops, held), counts, state, (uploads, failed), jobs ->
        val byId = ops.associateBy { it.id }
        val numbers = jobs.associate { it.job.id to it.job.jobNumber }
        val items = ops.map { op ->
            val payload = payload(op)
            OutboxItem(op, FieldTexts.outboxTitle(op.opType, payload), op.jobId?.let(numbers::get), serverState(op),
                field.repository.waitingReason(op, byId))
        }
        SyncStatusUi(items, counts, state, uploads, failed, held)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SyncStatusUi())

    /** "Retry" on a rejected item: queued again and sent on the next sync. */
    fun retry(op: ClientOperationEntity) {
        viewModelScope.launch { if (field.repository.requeue(op.id)) field.scheduler.syncNow() }
    }

    private fun payload(op: ClientOperationEntity): JsonObject? = runCatching { Json.parseToJsonElement(op.payloadJson).jsonObject }.getOrNull()

    private fun serverState(op: ClientOperationEntity): String? = op.resultJson?.let { text ->
        runCatching { Json.parseToJsonElement(text).jsonObject["server_state"]?.toString() }.getOrNull()
    }
}

/**
 * Everything not yet synced: rejected (with error code), conflicts (with the server's state), items held because the
 * subscription is read-only, and what is still waiting or being sent.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SyncStatusScreen(vm: SyncStatusViewModel, syncing: Boolean, onRefresh: () -> Unit) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Section(null) {
                    if (syncing) Busy("Syncing…")
                    LabeledRow("Synced", "${ui.counts[ClientOperationStatus.ACKED] ?: 0}")
                    LabeledRow("Not yet synced", "${ui.unsynced}")
                    LabeledRow("Files waiting to upload", "${ui.pendingUploads}")
                    LabeledRow("Last successful sync", ui.state?.lastSyncAt?.let(LocalTime::format) ?: "Never")
                    ui.state?.nextSyncAt?.takeIf { it > System.currentTimeMillis() }?.let {
                        LabeledRow("Next automatic retry", LocalTime.formatTimeSeconds(it))
                    }
                    ui.state?.offlineGrantUntil?.let { LabeledRow("Offline use allowed until", LocalTime.format(it)) }
                }
            }
            GROUPS.forEach { (title, status, footer) ->
                val items = ui.items.filter { it.operation.status == status }
                if (items.isNotEmpty()) {
                    item(key = "group-$status") {
                        Section("$title (${items.size})", footer = footer) {
                            items.forEach { ItemRow(it, onRetry = vm::retry) }
                        }
                    }
                }
            }
            ui.held.forEach { held ->
                item(key = "held-${held.ownerSub}") {
                    Section(FieldTexts.heldTitle(held.ownerLabel), footer = FieldTexts.HELD_FOOTER) {
                        Text(FieldTexts.heldCount(held.count), style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            if (ui.failedUploads.isNotEmpty()) {
                item(key = "failed-uploads") {
                    Section("Evidence files that cannot be uploaded") {
                        ui.failedUploads.forEach { FailedUploadRow(it) }
                    }
                }
            }
            item {
                Section(null) {
                    Text(
                        "Asseta syncs when the app is open and when the connection comes back. Android also syncs in the " +
                            "background about every 15 minutes while a network is available.",
                        style = MaterialTheme.typography.bodySmall, color = palette.secondaryText,
                    )
                    LabeledRow("Device ID", vm.deviceId.take(8))
                }
            }
        }
    }
}

@Composable
private fun ItemRow(item: OutboxItem, onRetry: (ClientOperationEntity) -> Unit) {
    val op = item.operation
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(item.title, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            SyncStateLabel(op.status)
        }
        item.jobNumber?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        Text(LocalTime.formatSeconds(op.createdAtDevice), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
        val code = op.errorCode
        if (code != null && op.status != ClientOperationStatus.PENDING) {
            Text("$code: ${op.lastError.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = palette.offline)
        }
        item.serverState?.let { Text("Server state: $it", style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace)) }
        item.waiting?.let { Text(FieldTexts.waiting(it), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText) }
        if (op.status == ClientOperationStatus.FAILED) {
            TextButton(onClick = { onRetry(op) }, contentPadding = PaddingValues(0.dp)) { Text("Retry") }
        }
    }
}

@Composable
private fun FailedUploadRow(file: AttachmentEntity) {
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(evidenceLabel(file.purpose), style = MaterialTheme.typography.bodyMedium)
        Text(file.lastError.orEmpty(), style = MaterialTheme.typography.bodySmall, color = palette.offline)
    }
}

private fun evidenceLabel(purpose: String) = when (purpose) {
    BlobPurpose.SIGNATURE -> "Signature"
    BlobPurpose.EXPENSE_RECEIPT -> "Receipt photo"
    else -> "Meter photo"
}

private val GROUPS = listOf(
    Triple(
        "Needs attention: rejected", ClientOperationStatus.FAILED,
        "The server refused these. The original evidence stays on this phone. Retry after fixing the cause, or ask your administrator.",
    ),
    Triple(
        "Needs attention: conflicts", ClientOperationStatus.CONFLICT,
        "The job changed on the server (for example it was cancelled or reassigned). Nothing was overwritten; your record is kept for review.",
    ),
    Triple(
        "Held: subscription read-only", ClientOperationStatus.QUARANTINED,
        "Your company's subscription is read-only. These are kept by the server and re-sent automatically after reactivation.",
    ),
    Triple("Waiting to sync", ClientOperationStatus.PENDING, null),
    Triple("Sending", ClientOperationStatus.SENT, null),
)
