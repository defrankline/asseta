package com.asseta.supervisor.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.supervisor.FieldGraph

@Composable
fun JobsScreen(field: FieldGraph, tenantId: String, onOpen: (String) -> Unit) {
    val jobs by remember(tenantId) { field.repository.observeJobs(tenantId) }.collectAsStateWithLifecycle(emptyList())
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { Text("Assigned jobs", style = MaterialTheme.typography.titleLarge) }
        if (jobs.isEmpty()) {
            item {
                Text("No jobs on this device yet. Jobs download automatically when you are online.",
                    style = MaterialTheme.typography.bodyMedium)
            }
        }
        items(jobs, key = { it.job.id }) { summary ->
            Card(Modifier.fillMaxWidth().clickable { onOpen(summary.job.id) }) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(summary.job.jobNumber, style = MaterialTheme.typography.titleMedium)
                    Text(summary.machine?.let { "${it.assetCode} · ${it.name}" } ?: "Machine ${summary.job.machineId.take(8)}")
                    Text("Status: ${summary.job.status} · Planned ${summary.job.plannedStart.take(16).replace('T', ' ')}",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
