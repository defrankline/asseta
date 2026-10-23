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
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.PageDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.alerts.AlertText
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

/** Investigation wording shared with iOS (`CasesView` / `CaseDetailView`). */
object CaseText {
    val FILTERS: List<Pair<String?, String>> = listOf(null to "All", "OPEN" to "Open", "IN_REVIEW" to "In review", "RESOLVED" to "Resolved")
    const val INTRO = "Cases group signals for review. A case is not a conclusion about anyone."
    const val EMPTY_TITLE = "No investigations"
    const val EMPTY_MESSAGE = "Nothing needs review."
    const val DETAIL_FOOTER = "Signals are indicators that need review; they are not conclusions. Review and outcomes are recorded in the web console."

    /** "Machine · 3 signals · last signal 21 Oct 2026, 14:05" */
    fun summary(c: AnomalyCaseDto, zone: ZoneId): String {
        val n = c.signalCount ?: 0
        return "${OwnerFormat.humanize(c.subjectType)} · $n signal${if (n == 1) "" else "s"} · last signal ${OwnerFormat.dateTime(c.lastSignalAt, zone)}"
    }
}

@Composable
fun CasesScreen(vm: CasesViewModel, onCase: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            CaseText.FILTERS.forEach { (s, label) -> FilterChip(status == s, { vm.filter(s) }, label = { Text(label) }) }
        }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { FootNote(CaseText.INTRO) }
                if (page.items.isEmpty()) item { EmptyState(CaseText.EMPTY_TITLE, CaseText.EMPTY_MESSAGE) }
                items(page.items, key = { it.id.toString() }) { c ->
                    Card(Modifier.fillMaxWidth().clickable(role = Role.Button) { onCase(c.id.toString()) }) {
                        Column(Modifier.padding(12.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(c.caseNumber, style = MaterialTheme.typography.titleSmall)
                                StatusPill(OwnerFormat.humanize(c.severity), OwnerColors.severity(c.severity))
                                Text(OwnerFormat.humanize(c.status), style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                            }
                            Text(c.title, style = MaterialTheme.typography.bodyMedium)
                            Text(CaseText.summary(c, zone), style = MaterialTheme.typography.bodySmall)
                            c.latestOutcome?.let { Text("Outcome: ${OwnerFormat.humanize(it)}", style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun CaseDetailScreen(vm: CaseDetailViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val c = d.case
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                SectionCard(c.title) {
                    KeyValue("Case", c.caseNumber)
                    KeyValue("Status", OwnerFormat.humanize(c.status))
                    Row(Modifier.fillMaxWidth()) {
                        Text("Severity", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        StatusPill(OwnerFormat.humanize(c.severity), OwnerColors.severity(c.severity))
                    }
                    KeyValue("Subject", OwnerFormat.humanize(c.subjectType))
                    KeyValue("Opened", OwnerFormat.dateTime(c.openedAt, zone))
                    KeyValue("Assigned to", c.assigneeName ?: "Unassigned")
                    if (features.fleet) c.machineId?.let { id -> Text("Open machine", Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Machine(id.toString())) }, color = MaterialTheme.colorScheme.primary) }
                    if (features.jobs) c.jobId?.let { id -> Text("Open job", Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Job(id.toString())) }, color = MaterialTheme.colorScheme.primary) }
                    FootNote(CaseText.DETAIL_FOOTER)
                }
            }
            item {
                SectionCard("Signals (${d.signals.size})") {
                    d.signals.forEach { s ->
                        Column(Modifier.semantics(mergeDescendants = true) {}) {
                            Row(Modifier.fillMaxWidth()) {
                                Text(OwnerFormat.humanize(s.code), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                                StatusPill(OwnerFormat.humanize(s.severity), OwnerColors.severity(s.severity))
                            }
                            Text("Observed ${OwnerFormat.dateTime(s.observedAt, zone)}", style = MaterialTheme.typography.bodySmall)
                            s.evidence.toSortedMap().forEach { (k, v) -> Text("${OwnerFormat.humanize(k)}: ${AlertText.evidence(v)}", style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
            if (d.outcomes.isNotEmpty()) item {
                SectionCard("Outcomes") {
                    d.outcomes.sortedBy { it.sequence }.forEach { o ->
                        Text(OwnerFormat.humanize(o.outcome), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                        Text(o.explanation, style = MaterialTheme.typography.bodyMedium)
                        Text("${o.decidedByName ?: "Reviewer"} · ${OwnerFormat.dateTime(o.decidedAt, zone)}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (d.notes.isNotEmpty()) item {
                SectionCard("Notes") {
                    d.notes.forEach { n ->
                        Text(n.body, style = MaterialTheme.typography.bodyMedium)
                        Text("${n.authorName ?: "Team"} · ${OwnerFormat.dateTime(n.createdAt, zone)}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}
