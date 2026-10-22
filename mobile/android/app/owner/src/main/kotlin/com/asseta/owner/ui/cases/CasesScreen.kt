package com.asseta.owner.ui.cases

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.PageDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.ZoneId

/**
 * Investigations are read-only here and worded neutrally: a case is a set of signals to review, not a finding.
 * Outcomes are shown exactly as recorded (e.g. "Legitimate explanation").
 */
class CasesViewModel private constructor(data: OwnerData, private val selected: MutableStateFlow<String?>, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PageDto<AnomalyCaseDto>>({ data.cases(selected.value) }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>) : this(data, MutableStateFlow(null), refreshOn)

    val status: StateFlow<String?> get() = selected

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }
}

class CaseDetailViewModel(data: OwnerData, caseId: String, refreshOn: Flow<Unit>) : SnapshotViewModel<AnomalyCaseDetailDto>({ data.case(caseId) }, refreshOn)

@Composable
fun CasesScreen(vm: CasesViewModel, onCase: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf(null, "OPEN", "IN_REVIEW", "RESOLVED").forEach { s ->
                FilterChip(status == s, { vm.filter(s) }, label = { Text(s?.let(OwnerFormat::humanize) ?: "All") })
            }
        }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Text("Cases group signals for review. A case is not a conclusion about anyone.", style = MaterialTheme.typography.bodySmall) }
                if (page.items.isEmpty()) item { Text("No cases.") }
                items(page.items, key = { it.id.toString() }) { c ->
                    Card(Modifier.fillMaxWidth().clickable(role = Role.Button) { onCase(c.id.toString()) }) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                StatusPill(OwnerFormat.humanize(c.severity), OwnerColors.severity(c.severity))
                                StatusPill(OwnerFormat.humanize(c.status), OwnerColors.Neutral)
                            }
                            Text("${c.caseNumber} · ${c.title}", style = MaterialTheme.typography.titleSmall)
                            Text("${OwnerFormat.humanize(c.subjectType)} · ${c.signalCount ?: 0} signals · last ${OwnerFormat.dateTime(c.lastSignalAt, zone)}", style = MaterialTheme.typography.bodySmall)
                            c.latestOutcome?.let { Text("Outcome: ${OwnerFormat.humanize(it)}", style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun CaseDetailScreen(vm: CaseDetailViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val c = d.case
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                SectionCard("${c.caseNumber} · ${c.title}") {
                    KeyValue("Status", OwnerFormat.humanize(c.status))
                    KeyValue("Severity", OwnerFormat.humanize(c.severity))
                    KeyValue("About", OwnerFormat.humanize(c.subjectType))
                    KeyValue("Opened", OwnerFormat.dateTime(c.openedAt, zone))
                    c.assigneeName?.let { KeyValue("Reviewer", it) }
                    c.machineId?.let { id -> Text("Open machine", Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Machine(id.toString())) }, color = MaterialTheme.colorScheme.primary) }
                    c.jobId?.let { id -> Text("Open job", Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Job(id.toString())) }, color = MaterialTheme.colorScheme.primary) }
                }
            }
            item {
                SectionCard("Signals (${d.signals.size})") {
                    d.signals.forEach { s ->
                        Text("${OwnerFormat.humanize(s.code)} · ${OwnerFormat.humanize(s.severity)} · ${OwnerFormat.dateTime(s.observedAt, zone)}", style = MaterialTheme.typography.bodyMedium)
                        s.evidence.entries.take(6).forEach { (k, v) -> Text("  ${OwnerFormat.humanize(k)}: ${v.toString().trim('"')}", style = MaterialTheme.typography.bodySmall) }
                    }
                }
            }
            if (d.outcomes.isNotEmpty()) item {
                SectionCard("Outcomes") {
                    d.outcomes.sortedBy { it.sequence }.forEach { o ->
                        Text("${OwnerFormat.humanize(o.outcome)} · ${OwnerFormat.dateTime(o.decidedAt, zone)}" + (o.decidedByName?.let { " · $it" } ?: ""), style = MaterialTheme.typography.titleSmall)
                        Text(o.explanation, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (d.notes.isNotEmpty()) item {
                SectionCard("Notes") {
                    d.notes.forEach { n -> Text("${OwnerFormat.dateTime(n.createdAt, zone)}${n.authorName?.let { " · $it" } ?: ""}: ${n.body}", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
    }
}
