package com.asseta.owner.ui.jobs

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
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.PageDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.ZoneId

class JobsViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<JobDto>>({ data.jobs(selected.value) }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>) : this(data, MutableStateFlow(JobsPresentation.DEFAULT_FILTER), refreshOn)

    val status: StateFlow<String?> get() = selected

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }
}

/** Jobs list wording and rules shared with iOS (`JobsView`). */
object JobsPresentation {
    /** Status chips in display order; null = all. The list opens on jobs in progress. */
    val FILTERS: List<Pair<String?, String>> = listOf(
        "IN_PROGRESS" to "In progress", "APPROVED" to "Approved", "PENDING_APPROVAL" to "Pending approval",
        "COMPLETED" to "Completed", "CANCELLED" to "Cancelled", null to "All",
    )
    val DEFAULT_FILTER: String? = "IN_PROGRESS"

    /** The most relevant date: "Completed …", else "Started …", else "Planned …". */
    fun datesLine(job: JobDto, zone: ZoneId): String = when {
        job.completedAt != null -> "Completed ${OwnerFormat.dateTime(job.completedAt, zone)}"
        job.startedAt != null -> "Started ${OwnerFormat.dateTime(job.startedAt, zone)}"
        else -> "Planned ${OwnerFormat.dateTime(job.plannedStart, zone)}"
    }

    fun countLine(shown: Int, total: Int): String = "$shown of $total jobs"

    const val MORE_IN_CONSOLE = "Use the web console for the full list."
    const val EMPTY_TITLE = "No jobs"
    const val EMPTY_MESSAGE = "Nothing matches this filter."

    fun statusColor(status: String): Color = when (status) {
        "IN_PROGRESS" -> OwnerColors.Recent
        "APPROVED" -> OwnerColors.Live
        "CANCELLED" -> OwnerColors.Critical
        "PENDING_APPROVAL" -> OwnerColors.Warning
        else -> OwnerColors.Neutral
    }
}

@Composable
fun JobsScreen(vm: JobsViewModel, onJob: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            JobsPresentation.FILTERS.forEach { (s, label) -> FilterChip(status == s, { vm.filter(s) }, label = { Text(label) }) }
        }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Text(JobsPresentation.countLine(page.items.size, page.total), style = MaterialTheme.typography.bodySmall) }
                if (page.items.isEmpty()) item { EmptyState(JobsPresentation.EMPTY_TITLE, JobsPresentation.EMPTY_MESSAGE) }
                items(page.items, key = { it.id.toString() }) { job ->
                    Card(Modifier.fillMaxWidth().clickable(role = Role.Button) { onJob(job.id.toString()) }) {
                        JobRow(job, zone, Modifier.padding(12.dp))
                    }
                }
                if (page.total > page.items.size) item { FootNote(JobsPresentation.MORE_IN_CONSOLE) }
            }
        }
    }
}

/** Job number with status pill, the most relevant date and the hourly rate (also used on the machine screen). */
@Composable
fun JobRow(job: JobDto, zone: ZoneId, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(job.jobNumber, style = MaterialTheme.typography.titleSmall)
            StatusPill(OwnerFormat.humanize(job.status), JobsPresentation.statusColor(job.status))
        }
        Text(JobsPresentation.datesLine(job, zone), style = MaterialTheme.typography.bodySmall)
        Text("Rate ${OwnerFormat.money(job.hourlyRate.value, job.currency)} / h", style = MaterialTheme.typography.bodySmall)
    }
}
