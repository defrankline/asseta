package com.asseta.owner.ui.machine

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.LinkRow
import com.asseta.core.ui.components.fullBleed
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.alerts.AlertRow
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.ReadingRow
import com.asseta.owner.ui.common.ReadingText
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.StaleBanner
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.fleet.FleetRow
import com.asseta.owner.ui.fleet.FleetRows
import com.asseta.owner.ui.jobs.JobRow
import com.asseta.owner.ui.map.MapMarker
import com.asseta.owner.ui.map.OwnerMap
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import java.time.ZoneId
import java.util.Locale

/** Machine drilldown: each part loads (and caches) independently, so one refusal never hides the rest. */
class MachineViewModel(val data: OwnerData, val machineId: String, refreshOn: Flow<Unit>) : ViewModel() {
    val status = Section(viewModelScope) { data.machineStatus(machineId) }
    val info = Section(viewModelScope) { data.machineInfo(machineId) }
    val alerts = Section(viewModelScope) { data.machineAlerts(machineId) }
    val readings = Section(viewModelScope) { data.machineReadings(machineId) }
    val jobs = Section(viewModelScope) { data.machineJobs(machineId) }
    val track = Section(viewModelScope) { data.machineTrack(machineId) }
    private val all = listOf(status, info, alerts, readings, jobs, track)

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { status.refresh(); alerts.refresh() } }
    }

    fun refresh() = all.forEach { it.refresh() }
}

/** Machine screen wording shared with iOS (`MachineDetailView`). */
object MachineText {
    const val STATUS_FOOTER = "Engine and motion are observed from tracker telemetry; reported work comes from the field team."
    const val NO_TRACK = "No positions in the last 24 hours."
    const val TRUNCATED = "Track shortened by the server; some points are not shown."

    /** Status rows in display order (label to value); optional rows only when known. */
    fun statusRows(row: FleetRow, info: MachineDto?, zone: ZoneId): List<Pair<String, String>> {
        val m = row.machine
        return listOfNotNull(
            "Machine" to FleetRows.title(m),
            "Last seen" to if (m.lastSeenAgeSeconds == null && m.lastMessageAt == null) "Never" else row.lastSeen.replaceFirstChar { it.uppercase() },
            "Position time" to OwnerFormat.dateTime(m.positionTime, zone),
            m.accuracyM?.let { "Accuracy" to "± ${Math.round(it)} m" },
            "Engine (tracker)" to OwnerFormat.humanize(m.observedEngine),
            "Motion (tracker)" to OwnerFormat.humanize(m.observedMotion),
            "Reported work status" to OwnerFormat.humanize(m.reportedWorkStatus),
            "Location compliance" to OwnerFormat.humanize(m.locationCompliance),
            "Machine status" to OwnerFormat.humanize(m.machineStatus),
            m.operator?.let { "Operator" to it },
            m.supervisor?.let { "Supervisor" to it },
            m.trackerState?.let { "Tracker" to OwnerFormat.humanize(it) },
            info?.let { i -> listOfNotNull(i.manufacturer, i.model, i.yearOfManufacture?.toString()).takeIf { it.isNotEmpty() }?.let { "Model" to it.joinToString(" ") } },
            info?.let { "Ownership" to OwnerFormat.humanize(it.ownership) },
        )
    }

    fun distance(km: Double): String = "${"%.1f".format(Locale.ROOT, km)} km"

    fun stopLine(startTime: String, durationSeconds: Long): String = "Stopped $startTime for ${durationSeconds / 60} min"

    fun visitLine(name: String, entered: String, exited: String): String = "At $name: $entered – $exited"
}

@Composable
fun MachineScreen(vm: MachineViewModel, features: OwnerFeatures, online: Boolean, now: () -> Long, onOpen: (OwnerDestination) -> Unit) {
    val status by vm.status.state.collectAsStateWithLifecycle()
    val info by vm.info.state.collectAsStateWithLifecycle()
    val alerts by vm.alerts.state.collectAsStateWithLifecycle()
    val readings by vm.readings.state.collectAsStateWithLifecycle()
    val jobs by vm.jobs.state.collectAsStateWithLifecycle()
    val track by vm.track.state.collectAsStateWithLifecycle()
    val zone = ZoneId.systemDefault()
    SnapshotScaffold(status, vm::refresh) { m ->
        val snap = status.snapshot!!
        val row = FleetRows.build(listOf(m), snap.source, snap.fetchedAtMs, now()).first()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item { StatusCard(row, info.data, zone) }
            item { Track(row, track, zone) }
            if (features.jobs) item { CurrentJob(jobs, zone, onOpen) }
            item { RecentAlerts(alerts, zone, onOpen) }
            if (features.meterEvidence) item { Readings(vm.data, readings, online, zone) }
        }
    }
}

@Composable
private fun StatusCard(row: FleetRow, info: MachineDto?, zone: ZoneId) {
    SectionCard("Status", footer = MachineText.STATUS_FOOTER) {
        LabeledValue("Connectivity") { StatusPill(row.connectivity.label, OwnerColors.connectivity(row.connectivity)) }
        MachineText.statusRows(row, info, zone).forEach { (k, v) -> KeyValue(k, v) }
    }
}

@Composable
private fun CurrentJob(state: ScreenState<PageDto<JobDto>>, zone: ZoneId, onOpen: (OwnerDestination) -> Unit) {
    SectionCard("Current job") {
        StaleBanner(state.snapshot)
        val job = state.data?.items?.firstOrNull()
        when {
            job != null -> LinkRow({ onOpen(OwnerDestination.Job(job.id.toString())) }) { JobRow(job, zone) }
            state.loading -> SecondaryText("Loading…")
            state.error != null -> Text(state.error!!.message, color = MaterialTheme.colorScheme.error)
            else -> SecondaryText("No job in progress.")
        }
    }
}

@Composable
private fun RecentAlerts(state: ScreenState<PageDto<AlertDto>>, zone: ZoneId, onOpen: (OwnerDestination) -> Unit) {
    SectionCard("Recent alerts") {
        StaleBanner(state.snapshot)
        val items = state.data?.items.orEmpty()
        if (items.isEmpty()) SecondaryText(state.error?.message ?: if (state.loading) "Loading…" else "No alerts.")
        items.forEach { a -> LinkRow({ onOpen(OwnerDestination.Alerts(a.id.toString())) }) { AlertRow(a, zone) } }
    }
}

@Composable
private fun Readings(data: OwnerData, state: ScreenState<PageDto<MeterCaptureDto>>, online: Boolean, zone: ZoneId) {
    SectionCard("Recent meter readings", footer = ReadingText.PHOTO_FOOTER) {
        StaleBanner(state.snapshot)
        val items = state.data?.items.orEmpty()
        if (items.isEmpty()) SecondaryText(state.error?.message ?: if (state.loading) "Loading…" else "No readings yet.")
        items.forEach { c -> ReadingRow(c, zone, online && !state.stale) { data.attachmentUrl(it) } }
    }
}

@Composable
private fun Track(row: FleetRow, state: ScreenState<HistoryDto>, zone: ZoneId) {
    val m = row.machine
    SectionCard("Last 24 hours") {
        StaleBanner(state.snapshot)
        val h = state.data
        if (h == null) {
            state.error?.let { Text(it.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } ?: SecondaryText("Loading track…")
            return@SectionCard
        }
        if (h.points.isEmpty() && !m.hasPosition) {
            SecondaryText(MachineText.NO_TRACK)
        } else {
            OwnerMap(
                markers = if (m.hasPosition) {
                    listOf(MapMarker(m.machineId.toString(), m.latitude!!, m.longitude!!, OwnerColors.connectivity(row.connectivity), m.name, code = m.assetCode, live = row.connectivity == Connectivity.LIVE))
                } else {
                    emptyList()
                },
                description = "Map of the last 24 hours: ${h.points.size} positions",
                modifier = Modifier.fillMaxWidth().height(240.dp).fullBleed(),
                track = h.points.map { it.latitude to it.longitude },
            )
        }
        KeyValue("Positions", "${h.points.size}")
        KeyValue("Distance (24 h)", MachineText.distance(h.distanceKm))
        KeyValue("Stops", "${h.stops.size}")
        if (h.truncated) FootNote(MachineText.TRUNCATED)
        h.stops.takeLast(10).forEach { s -> Text(MachineText.stopLine(OwnerFormat.dateTime(s.start, zone), s.durationSeconds), style = AssetaType.caption) }
        h.siteVisits.takeLast(10).forEach { v ->
            Text(MachineText.visitLine(v.geofenceName, OwnerFormat.dateTime(v.enteredAt, zone), OwnerFormat.dateTime(v.exitedAt, zone)), style = AssetaType.caption)
        }
    }
}

@Composable
private fun SecondaryText(text: String) = Text(text, style = MaterialTheme.typography.bodyLarge, color = palette.secondaryText)
