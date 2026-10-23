package com.asseta.owner.ui.cases

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
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
        FilterChipRow(CaseText.FILTERS, status, vm::filter)
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            val rows = buildList {
                add(GroupedItem("intro") { FootNote(CaseText.INTRO) })
                if (page.items.isEmpty()) add(GroupedItem("empty") { EmptyState(CaseText.EMPTY_TITLE, CaseText.EMPTY_MESSAGE, R.drawable.ic_investigation) })
                page.items.forEach { c -> add(GroupedItem(c.id.toString(), onClick = { onCase(c.id.toString()) }) { CaseRow(c, zone) }) }
            }
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) { groupedSection("cases", rows) }
        }
    }
}

@Composable
private fun CaseRow(c: AnomalyCaseDto, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(c.caseNumber, style = AssetaType.headline)
            StatusPill(OwnerFormat.humanize(c.severity), OwnerColors.severity(c.severity))
            Spacer(Modifier.weight(1f))
            Text(OwnerFormat.humanize(c.status), style = AssetaType.caption, color = palette.secondaryText)
        }
        Text(c.title, style = AssetaType.subheadline)
        Text(CaseText.summary(c, zone), style = AssetaType.caption, color = palette.secondaryText)
        c.latestOutcome?.let { Text("Outcome: ${OwnerFormat.humanize(it)}", style = AssetaType.caption, color = palette.secondaryText) }
    }
}

@Composable
fun CaseDetailScreen(vm: CaseDetailViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val c = d.case
        val zone = ZoneId.systemDefault()
        val secondary = palette.secondaryText
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(c.title, footer = CaseText.DETAIL_FOOTER) {
                    KeyValue("Case", c.caseNumber)
                    KeyValue("Status", OwnerFormat.humanize(c.status))
                    LabeledValue("Severity") { StatusPill(OwnerFormat.humanize(c.severity), OwnerColors.severity(c.severity)) }
                    KeyValue("Subject", OwnerFormat.humanize(c.subjectType))
                    KeyValue("Opened", OwnerFormat.dateTime(c.openedAt, zone))
                    KeyValue("Assigned to", c.assigneeName ?: "Unassigned")
                    if (features.fleet) c.machineId?.let { id -> NavigationRow("Open machine") { onOpen(OwnerDestination.Machine(id.toString())) } }
                    if (features.jobs) c.jobId?.let { id -> NavigationRow("Open job") { onOpen(OwnerDestination.Job(id.toString())) } }
                }
            }
            item {
                SectionCard("Signals (${d.signals.size})") {
                    d.signals.forEach { s ->
                        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text(OwnerFormat.humanize(s.code), style = AssetaType.subheadline, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                                StatusPill(OwnerFormat.humanize(s.severity), OwnerColors.severity(s.severity))
                            }
                            Text("Observed ${OwnerFormat.dateTime(s.observedAt, zone)}", style = AssetaType.caption, color = secondary)
                            s.evidence.toSortedMap().forEach { (k, v) -> Text("${OwnerFormat.humanize(k)}: ${AlertText.evidence(v)}", style = AssetaType.caption, color = secondary) }
                        }
                    }
                }
            }
            if (d.outcomes.isNotEmpty()) item {
                SectionCard("Outcomes") {
                    d.outcomes.sortedBy { it.sequence }.forEach { o ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(OwnerFormat.humanize(o.outcome), style = AssetaType.subheadline, fontWeight = FontWeight.Bold)
                            Text(o.explanation, style = AssetaType.subheadline)
                            Text("${o.decidedByName ?: "Reviewer"} · ${OwnerFormat.dateTime(o.decidedAt, zone)}", style = AssetaType.caption, color = secondary)
                        }
                    }
                }
            }
            if (d.notes.isNotEmpty()) item {
                SectionCard("Notes") {
                    d.notes.forEach { n ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(n.body, style = MaterialTheme.typography.bodyLarge)
                            Text("${n.authorName ?: "Team"} · ${OwnerFormat.dateTime(n.createdAt, zone)}", style = AssetaType.caption, color = secondary)
                        }
                    }
                }
            }
        }
    }
}
