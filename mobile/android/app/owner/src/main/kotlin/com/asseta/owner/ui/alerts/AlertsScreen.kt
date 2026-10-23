package com.asseta.owner.ui.alerts

import androidx.compose.foundation.clickable
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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
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
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import java.time.ZoneId

/** Alert wording and ordering shared with iOS (`AlertsView` / `AlertDetailView`). */
object AlertText {
    /** Status chips in display order; null = all. The list opens on open alerts. */
    val FILTERS: List<Pair<String?, String>> = listOf("OPEN" to "Open", "ACKNOWLEDGED" to "Acknowledged", "RESOLVED" to "Resolved", null to "All")
    const val DEFAULT_FILTER = "OPEN"
    const val EMPTY_TITLE = "No alerts"
    const val EMPTY_MESSAGE = "Nothing needs attention here."
    const val NOT_FOUND_TITLE = "Alert not found"
    const val NOT_FOUND_MESSAGE = "It may be older than the latest 200 alerts. Open it in the web console."
    const val NOTE_LABEL = "Note (required to resolve)"

    fun rank(severity: String): Int = when (severity) {
        "CRITICAL" -> 3
        "INFO" -> 1
        else -> 2
    }

    /** Most severe first, then newest. */
    fun sorted(items: List<AlertDto>): List<AlertDto> =
        items.sortedWith(compareByDescending<AlertDto> { rank(it.severity) }.thenByDescending { OwnerFormat.parseInstant(it.eventTime) })

    fun isClosed(status: String): Boolean = status == "RESOLVED" || status == "SUPERSEDED"

    fun done(status: String): String = "Alert ${OwnerFormat.humanize(status).lowercase()}."

    /** Evidence value as text ("Yes"/"No" for booleans, "—" for null). */
    fun evidence(value: JsonElement): String = when {
        value is JsonNull -> "—"
        value is JsonPrimitive && value.isString -> value.content
        value is JsonPrimitive && value.booleanOrNull != null -> if (value.booleanOrNull == true) "Yes" else "No"
        value is JsonPrimitive -> value.content
        else -> value.toString()
    }
}

class AlertsViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<AlertDto>>({ data.alerts(selected.value) }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>) : this(data, MutableStateFlow(AlertText.DEFAULT_FILTER), refreshOn)

    val status: StateFlow<String?> get() = selected

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }
}

/** One alert (there is no single-alert endpoint, so it is found in the latest 200) with acknowledge / resolve. */
class AlertDetailViewModel(private val data: OwnerData, val alertId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PageDto<AlertDto>>({ data.recentAlerts() }, refreshOn) {
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun alert(page: PageDto<AlertDto>): AlertDto? = page.items.firstOrNull { it.id.toString() == alertId }

    fun acknowledge() = act { data.acknowledgeAlert(alertId) }

    fun resolve(note: String) {
        if (!MutationGate.resolveNoteValid(note)) {
            _error.value = "Add a note explaining how the alert was resolved."
            return
        }
        act { data.resolveAlert(alertId, note) }
    }

    private fun act(call: suspend () -> ActionResult<AlertDto>) {
        if (_busy.value) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = call()) {
                is ActionResult.Done -> {
                    replaceData { page -> page.copy(items = page.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = AlertText.done(r.value.status)
                }
                is ActionResult.Refused -> {
                    _error.value = r.error.message
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun AlertsScreen(vm: AlertsViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            AlertText.FILTERS.forEach { (s, label) -> FilterChip(status == s, { vm.filter(s) }, label = { Text(label) }) }
        }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (page.items.isEmpty()) item { EmptyState(AlertText.EMPTY_TITLE, AlertText.EMPTY_MESSAGE) }
                items(AlertText.sorted(page.items), key = { it.id.toString() }) { a ->
                    Card(Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(OwnerDestination.Alerts(a.id.toString())) }) {
                        AlertRow(a, zone, Modifier.padding(12.dp))
                    }
                }
            }
        }
    }
}

/** Severity, status and time; title; type (also used on the machine screen). */
@Composable
fun AlertRow(a: AlertDto, zone: ZoneId, modifier: Modifier = Modifier) {
    Column(modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusPill(OwnerFormat.humanize(a.severity), OwnerColors.severity(a.severity))
            Text(OwnerFormat.humanize(a.status), style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
            Text(OwnerFormat.dateTime(a.eventTime, zone), style = MaterialTheme.typography.labelMedium)
        }
        Text(a.title, style = MaterialTheme.typography.titleSmall)
        Text(OwnerFormat.humanize(a.alertType), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
fun AlertDetailScreen(vm: AlertDetailViewModel, session: OwnerSession, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var note by rememberSaveable { mutableStateOf("") }
    LaunchedEffect(message) { if (message != null) note = "" }
    SnapshotScaffold(state, vm::refresh) { page ->
        val a = vm.alert(page)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (a == null) {
                item { EmptyState(AlertText.NOT_FOUND_TITLE, AlertText.NOT_FOUND_MESSAGE) }
                return@LazyColumn
            }
            item {
                SectionCard(a.title) {
                    Row(Modifier.fillMaxWidth()) {
                        Text("Severity", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        StatusPill(OwnerFormat.humanize(a.severity), OwnerColors.severity(a.severity))
                    }
                    KeyValue("Status", OwnerFormat.humanize(a.status))
                    KeyValue("Type", OwnerFormat.humanize(a.alertType))
                    KeyValue("Happened", OwnerFormat.dateTime(a.eventTime, zone))
                    a.acknowledgedAt?.let { KeyValue("Acknowledged", OwnerFormat.dateTime(it, zone)) }
                    a.resolvedAt?.let { KeyValue("Resolved", OwnerFormat.dateTime(it, zone)) }
                    a.resolutionNote?.let { KeyValue("Resolution", it) }
                    if (a.machineId != null && session.features.fleet) {
                        Text("Open machine", Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Machine(a.machineId.toString())) }, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
            if (a.evidence.isNotEmpty()) item {
                SectionCard("Evidence") { a.evidence.toSortedMap().forEach { (k, v) -> KeyValue(OwnerFormat.humanize(k), AlertText.evidence(v)) } }
            }
            if (!AlertText.isClosed(a.status)) item {
                SectionCard("Action") {
                    val gate = session.can(OwnerAction.RESOLVE_ALERT, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        FootNote(gate.reason)
                    } else {
                        OutlinedTextField(note, { note = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text(AlertText.NOTE_LABEL) }, minLines = 2)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (a.status == "OPEN") {
                                OutlinedButton({ vm.acknowledge() }, enabled = !busy, modifier = Modifier.testTag("ack-${a.id}")) { Text("Acknowledge") }
                            }
                            Button({ vm.resolve(note) }, enabled = !busy && MutationGate.resolveNoteValid(note), modifier = Modifier.testTag("resolve-${a.id}")) { Text("Resolve") }
                        }
                        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
                    }
                }
            }
            message?.let { item { Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } }
        }
    }
}
