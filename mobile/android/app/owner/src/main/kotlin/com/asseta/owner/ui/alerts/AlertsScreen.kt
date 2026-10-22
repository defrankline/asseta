package com.asseta.owner.ui.alerts

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.PageDto
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.ErrorLine
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

class AlertsViewModel private constructor(
    private val data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    val highlight: String?,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<AlertDto>>({ data.alerts(selected.value) }, refreshOn) {
    constructor(data: OwnerData, highlight: String?, refreshOn: Flow<Unit>) :
        this(data, MutableStateFlow(if (highlight == null) "OPEN" else null), highlight, refreshOn)

    val status: StateFlow<String?> get() = selected
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow<String?>(null)
    val busy: StateFlow<String?> = _busy.asStateFlow()

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }

    fun acknowledge(id: String) = act(id) { data.acknowledgeAlert(id) }

    fun resolve(id: String, note: String) {
        if (!MutationGate.resolveNoteValid(note)) {
            _message.value = "Add a note explaining how the alert was resolved."
            return
        }
        act(id) { data.resolveAlert(id, note) }
    }

    fun clearMessage() { _message.value = null }

    private fun act(id: String, call: suspend () -> ActionResult<AlertDto>) {
        if (_busy.value != null) return
        _busy.value = id
        viewModelScope.launch {
            when (val r = call()) {
                is ActionResult.Done -> {
                    replaceData { page -> page.copy(items = page.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = "Alert ${OwnerFormat.humanize(r.value.status).lowercase()}."
                }
                is ActionResult.Refused -> {
                    _message.value = r.error.message
                    if (r.reload) refresh()
                }
            }
            _busy.value = null
        }
    }

    companion object {
        val FILTERS = listOf("OPEN", "ACKNOWLEDGED", "RESOLVED")
    }
}

@Composable
fun AlertsScreen(vm: AlertsViewModel, session: OwnerSession, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var resolving by remember { mutableStateOf<AlertDto?>(null) }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            FilterChip(status == null, { vm.filter(null) }, label = { Text("All") })
            AlertsViewModel.FILTERS.forEach { s -> FilterChip(status == s, { vm.filter(if (status == s) null else s) }, label = { Text(OwnerFormat.humanize(s)) }) }
        }
        message?.let { Text(it, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.primary) }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            val ack = session.can(OwnerAction.ACKNOWLEDGE_ALERT, online, state.snapshot?.source)
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (page.items.isEmpty()) item { Text("No alerts.") }
                if (ack is MutationCheck.Blocked && page.items.any { it.status == "OPEN" || it.status == "ACKNOWLEDGED" }) {
                    item { Text(ack.reason, style = MaterialTheme.typography.bodySmall) }
                }
                items(page.items, key = { it.id.toString() }) { a ->
                    AlertCard(a, a.id.toString() == vm.highlight, zone, ack is MutationCheck.Allowed, busy == a.id.toString(),
                        onAck = { vm.acknowledge(a.id.toString()) }, onResolve = { resolving = a },
                        onMachine = a.machineId?.let { id -> { onOpen(OwnerDestination.Machine(id.toString())) } })
                }
            }
        }
    }
    resolving?.let { a -> ResolveDialog(a, onDismiss = { resolving = null }) { note -> vm.resolve(a.id.toString(), note); resolving = null } }
}

@Composable
private fun AlertCard(
    a: AlertDto, highlighted: Boolean, zone: ZoneId, actionsEnabled: Boolean, busy: Boolean,
    onAck: () -> Unit, onResolve: () -> Unit, onMachine: (() -> Unit)?,
) {
    Card(Modifier.fillMaxWidth(), border = if (highlighted) BorderStroke(2.dp, MaterialTheme.colorScheme.secondary) else null) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(OwnerFormat.humanize(a.severity), OwnerColors.severity(a.severity))
                StatusPill(OwnerFormat.humanize(a.status), OwnerColors.Neutral)
            }
            Text(a.title, style = MaterialTheme.typography.titleSmall)
            Text("${OwnerFormat.humanize(a.alertType)} · ${OwnerFormat.dateTime(a.eventTime, zone)}", style = MaterialTheme.typography.bodySmall)
            a.evidence.entries.take(6).forEach { (k, v) -> Text("${OwnerFormat.humanize(k)}: ${v.toString().trim('"')}", style = MaterialTheme.typography.bodySmall) }
            a.resolutionNote?.let { Text("Resolution: $it", style = MaterialTheme.typography.bodySmall) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                onMachine?.let { TextButton(onClick = it) { Text("Machine") } }
                if (a.status == "OPEN") {
                    OutlinedButton(onAck, enabled = actionsEnabled && !busy, modifier = Modifier.testTag("ack-${a.id}")) { Text("Acknowledge") }
                }
                if (a.status == "OPEN" || a.status == "ACKNOWLEDGED") {
                    Button(onResolve, enabled = actionsEnabled && !busy, modifier = Modifier.testTag("resolve-${a.id}")) { Text("Resolve") }
                }
            }
        }
    }
}

@Composable
private fun ResolveDialog(a: AlertDto, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var note by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Resolve alert") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(a.title)
                OutlinedTextField(note, { note = it.take(1000) }, label = { Text("Resolution note (required)") }, minLines = 2)
                if (note.isBlank()) ErrorLine(com.asseta.core.ui.session.UiError("A note is required."))
            }
        },
        confirmButton = { Button({ onConfirm(note) }, enabled = MutationGate.resolveNoteValid(note)) { Text("Resolve") } },
        dismissButton = { TextButton(onDismiss) { Text("Cancel") } },
    )
}
