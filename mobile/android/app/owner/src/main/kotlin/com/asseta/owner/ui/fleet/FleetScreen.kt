package com.asseta.owner.ui.fleet

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
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
import com.asseta.core.ui.components.FilterChipButton
import com.asseta.core.ui.components.SearchField
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.map.MapMarker
import com.asseta.owner.ui.map.OwnerMap
import kotlinx.coroutines.flow.Flow
import com.asseta.core.ui.R as CoreR

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

    /** List order (same as iOS): machines with open alerts first, then most recently seen, then asset code. */
    fun sorted(rows: List<FleetRow>): List<FleetRow> = rows.sortedWith(
        compareByDescending<FleetRow> { it.machine.openAlerts > 0 }
            .thenByDescending { OwnerFormat.parseInstant(it.machine.lastMessageAt)?.toEpochMilli() ?: Long.MIN_VALUE }
            .thenBy { it.machine.assetCode },
    )

    fun title(m: MachineMapDto): String = "${m.assetCode} · ${m.name}"

    /** "Last seen 5 min ago · engine on · moving" ("Never seen · …" without any message). */
    fun detailLine(row: FleetRow): String {
        val seen = if (row.machine.lastSeenAgeSeconds == null && row.machine.lastMessageAt == null) "Never seen" else "Last seen ${row.lastSeen}"
        return "$seen · engine ${OwnerFormat.humanize(row.machine.observedEngine).lowercase()} · ${OwnerFormat.humanize(row.machine.observedMotion).lowercase()}"
    }

    /** "Reported: Working · operator Ali" */
    fun reportedLine(m: MachineMapDto): String = "Reported: ${OwnerFormat.humanize(m.reportedWorkStatus)}" + (m.operator?.let { " · operator $it" } ?: "")

    fun alertsLine(count: Int): String = if (count == 1) "1 open alert" else "$count open alerts"

    /** Shown over the map when filtered machines have no fix. */
    fun unplacedNote(count: Int): String? = when {
        count <= 0 -> null
        count == 1 -> "1 machine has no known position (see List)."
        else -> "$count machines have no known position (see List)."
    }

    const val EMPTY_TITLE = "No machines"
    const val EMPTY_MESSAGE = "Nothing matches this search or filter."
}

@Composable
fun FleetScreen(vm: FleetViewModel, now: () -> Long, onMachine: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    var showMap by rememberSaveable { mutableStateOf(true) }
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf<String?>(null) }
    val machines = state.data
    val snap = state.snapshot
    val rows = if (machines != null && snap != null) {
        FleetRows.sorted(FleetRows.filter(FleetRows.build(machines, snap.source, snap.fetchedAtMs, now()), query, filter?.let { Connectivity.from(it) }))
    } else {
        emptyList()
    }
    // Same order as iOS: search field, Map/List control, status filters with the count, then the map or list.
    Column(Modifier.fillMaxSize()) {
        SearchField(query, { query = it }, "Search machine, code, operator")
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 8.dp)) {
            SegmentedButton(showMap, { showMap = true }, SegmentedButtonDefaults.itemShape(0, 2)) { Text("Map") }
            SegmentedButton(!showMap, { showMap = false }, SegmentedButtonDefaults.itemShape(1, 2)) { Text("List") }
        }
        Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(Connectivity.LIVE, Connectivity.RECENT, Connectivity.STALE, Connectivity.OFFLINE).forEach { c ->
                    FilterChipButton(c.label, filter == c.wire) { filter = if (filter == c.wire) null else c.wire }
                }
            }
            machines?.let { Text("${rows.size} of ${it.size} machines", style = AssetaType.caption, color = palette.secondaryText) }
        }
        SnapshotScaffold(state, vm::refresh) {
            if (showMap) {
                val markers = rows.filter { it.machine.hasPosition }.map {
                    MapMarker(
                        it.machine.machineId.toString(), it.machine.latitude!!, it.machine.longitude!!,
                        OwnerColors.connectivity(it.connectivity), it.machine.name,
                        code = it.machine.assetCode, alerts = it.machine.openAlerts, live = it.connectivity == Connectivity.LIVE,
                    )
                }
                Box(Modifier.fillMaxSize()) {
                    OwnerMap(
                        markers, "Fleet map with ${markers.size} machines. Use the List view for details.",
                        Modifier.fillMaxSize(), onMarker = onMachine,
                    )
                    FleetRows.unplacedNote(rows.size - markers.size)?.let {
                        Text(
                            it, style = AssetaType.caption,
                            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 8.dp)
                                .background(palette.cell.copy(alpha = 0.92f), RoundedCornerShape(50)).padding(8.dp),
                        )
                    }
                }
            } else if (rows.isEmpty()) {
                EmptyState(FleetRows.EMPTY_TITLE, FleetRows.EMPTY_MESSAGE, CoreR.drawable.ic_search)
            } else {
                // Plain list (iOS `.listStyle(.plain)`): full-width rows with inset separators.
                LazyColumn(Modifier.fillMaxSize().background(palette.cell)) {
                    itemsIndexed(rows, key = { _, r -> r.machine.machineId.toString() }) { i, row ->
                        if (i > 0) HorizontalDivider(Modifier.padding(start = 56.dp), thickness = 0.5.dp, color = palette.separator)
                        MachineRow(row) { onMachine(row.machine.machineId.toString()) }
                    }
                }
            }
        }
    }
}

@Composable
private fun MachineRow(row: FleetRow, onClick: () -> Unit) {
    val m = row.machine
    val secondary = palette.secondaryText
    val tone = OwnerColors.connectivity(row.connectivity)
    // Same layout as the iOS `MachineRow`: a connectivity symbol on the left, then the lines.
    Row(
        Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onClick).padding(horizontal = 16.dp, vertical = 10.dp)
            .semantics(mergeDescendants = true) { stateDescription = "${row.connectivity.label}, ${FleetRows.detailLine(row)}" },
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.width(28.dp).padding(top = 1.dp), contentAlignment = Alignment.TopCenter) {
            Icon(painterResource(connectivityIcon(row.connectivity)), contentDescription = null, tint = tone, modifier = Modifier.size(22.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(FleetRows.title(m), style = AssetaType.headline, modifier = Modifier.weight(1f))
                StatusPill(row.connectivity.label, tone)
            }
            Text(FleetRows.detailLine(row), style = AssetaType.caption, color = secondary)
            Text(FleetRows.reportedLine(m), style = AssetaType.caption, color = secondary)
            m.supervisor?.let { Text("Supervisor: $it", style = AssetaType.caption, color = secondary) }
            if (m.openAlerts > 0) Text(FleetRows.alertsLine(m.openAlerts), color = OwnerColors.Critical, style = AssetaType.caption)
        }
    }
}

/** Same symbol concept per connectivity as iOS `FleetPresentation.style` (radio waves, clock, clock with alert, …). */
private fun connectivityIcon(c: Connectivity): Int = when (c) {
    Connectivity.LIVE -> CoreR.drawable.ic_live
    Connectivity.RECENT -> CoreR.drawable.ic_clock
    Connectivity.STALE -> CoreR.drawable.ic_clock_alert
    Connectivity.OFFLINE -> CoreR.drawable.ic_wifi_off
    Connectivity.NO_TRACKER -> CoreR.drawable.ic_no_tracker
    else -> CoreR.drawable.ic_help
}
