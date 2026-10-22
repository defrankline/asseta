package com.asseta.owner.ui.fleet

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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.Freshness
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.domain.finance.SearchMatch
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.map.MapMarker
import com.asseta.owner.ui.map.OwnerMap
import kotlinx.coroutines.flow.Flow

class FleetViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<List<MachineMapDto>>({ data.fleet() }, refreshOn)

/** A machine row as displayed: connectivity is downgraded when the data is cached or old (never "live" when stale). */
data class FleetRow(val machine: MachineMapDto, val connectivity: Connectivity, val lastSeen: String)

object FleetRows {
    fun build(machines: List<MachineMapDto>, source: DataSource, fetchedAtMs: Long, nowMs: Long): List<FleetRow> = machines.map { m ->
        val c = Freshness.displayConnectivity(m.connectivity, m.isLive, source, fetchedAtMs, nowMs)
        // The server's age is relative to its response; add the time since that response was fetched.
        val age = m.lastSeenAgeSeconds?.let { it + ((nowMs - fetchedAtMs) / 1000).coerceAtLeast(0) }
        FleetRow(m, c, Freshness.ageLabel(age))
    }

    fun filter(rows: List<FleetRow>, query: String, connectivity: Connectivity?): List<FleetRow> = rows.filter {
        (connectivity == null || it.connectivity == connectivity) &&
            SearchMatch.matches(query, it.machine.name, it.machine.assetCode, it.machine.operator, it.machine.supervisor)
    }
}

@Composable
fun FleetScreen(vm: FleetViewModel, now: () -> Long, onMachine: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    var showMap by rememberSaveable { mutableStateOf(true) }
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf<String?>(null) }
    SnapshotScaffold(state, vm::refresh) { machines ->
        val snap = state.snapshot!!
        val rows = FleetRows.filter(FleetRows.build(machines, snap.source, snap.fetchedAtMs, now()), query, filter?.let { Connectivity.from(it) })
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    SegmentedButton(showMap, { showMap = true }, SegmentedButtonDefaults.itemShape(0, 2)) { Text("Map") }
                    SegmentedButton(!showMap, { showMap = false }, SegmentedButtonDefaults.itemShape(1, 2)) { Text("List") }
                }
                OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth(), label = { Text("Search machine, code, operator") }, singleLine = true)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf(Connectivity.LIVE, Connectivity.RECENT, Connectivity.STALE, Connectivity.OFFLINE).forEach { c ->
                        FilterChip(filter == c.wire, { filter = if (filter == c.wire) null else c.wire }, label = { Text(c.label) })
                    }
                }
                Text("${rows.size} of ${machines.size} machines", style = MaterialTheme.typography.bodySmall)
            }
            if (showMap) {
                val markers = rows.filter { it.machine.hasPosition }.map {
                    MapMarker(it.machine.machineId.toString(), it.machine.latitude!!, it.machine.longitude!!, OwnerColors.connectivity(it.connectivity), it.machine.name)
                }
                val noPosition = rows.size - markers.size
                if (noPosition > 0) Text("$noPosition machines have no known position (see List).", Modifier.padding(horizontal = 16.dp), style = MaterialTheme.typography.bodySmall)
                OwnerMap(
                    markers, "Fleet map with ${markers.size} machines. Use the List view for details.",
                    Modifier.fillMaxSize(), onMarker = onMachine,
                )
            } else {
                LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(rows, key = { it.machine.machineId.toString() }) { row -> MachineRow(row) { onMachine(row.machine.machineId.toString()) } }
                }
            }
        }
    }
}

@Composable
private fun MachineRow(row: FleetRow, onClick: () -> Unit) {
    val m = row.machine
    Card(
        Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onClick)
            .semantics { stateDescription = "${row.connectivity.label}, last seen ${row.lastSeen}" },
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("${m.name} · ${m.assetCode}", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                StatusPill(row.connectivity.label, OwnerColors.connectivity(row.connectivity))
            }
            Text("Last seen ${row.lastSeen} · engine ${OwnerFormat.humanize(m.observedEngine).lowercase()} · ${OwnerFormat.humanize(m.observedMotion).lowercase()}", style = MaterialTheme.typography.bodySmall)
            Text("Reported: ${OwnerFormat.humanize(m.reportedWorkStatus)}" + (m.operator?.let { " · operator $it" } ?: ""), style = MaterialTheme.typography.bodySmall)
            if (m.openAlerts > 0) Text("${m.openAlerts} open alerts", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}
