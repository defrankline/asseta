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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.PageDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.ZoneId

class JobsViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<JobDto>>({ data.jobs(selected.value) }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>) : this(data, MutableStateFlow(null), refreshOn)

    val status: StateFlow<String?> get() = selected

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }

    companion object {
        val FILTERS = listOf("IN_PROGRESS", "APPROVED", "PENDING_APPROVAL", "COMPLETED", "CANCELLED")
    }
}

@Composable
fun JobsScreen(vm: JobsViewModel, onJob: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            FilterChip(status == null, { vm.filter(null) }, label = { Text("All") })
            JobsViewModel.FILTERS.forEach { s -> FilterChip(status == s, { vm.filter(if (status == s) null else s) }, label = { Text(OwnerFormat.humanize(s)) }) }
        }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Text("${page.items.size} of ${page.total} jobs", style = MaterialTheme.typography.bodySmall) }
                if (page.items.isEmpty()) item { Text("No jobs match this filter.") }
                items(page.items, key = { it.id.toString() }) { job ->
                    Card(Modifier.fillMaxWidth().clickable(role = Role.Button) { onJob(job.id.toString()) }) {
                        Column(Modifier.padding(12.dp)) {
                            Text("${job.jobNumber} · ${OwnerFormat.humanize(job.status)}", style = MaterialTheme.typography.titleSmall)
                            Text("Planned ${OwnerFormat.dateTime(job.plannedStart, zone)}" + (job.startedAt?.let { " · started ${OwnerFormat.dateTime(it, zone)}" } ?: ""), style = MaterialTheme.typography.bodySmall)
                            Text("Rate ${OwnerFormat.money(job.hourlyRate.value, job.currency)} / h", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
