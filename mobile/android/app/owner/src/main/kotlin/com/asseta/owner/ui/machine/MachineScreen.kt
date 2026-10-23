package com.asseta.owner.ui.machine

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.PageDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.StaleBanner
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.fleet.FleetRows
import com.asseta.owner.ui.map.MapMarker
import com.asseta.owner.ui.map.OwnerMap
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import java.time.ZoneId

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

@Composable
fun MachineScreen(vm: MachineViewModel, online: Boolean, now: () -> Long, onOpen: (OwnerDestination) -> Unit) {
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
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { StatusCard(m, row.connectivity.label, row.lastSeen, OwnerColors.connectivity(row.connectivity), info.data, zone) }
            item { CurrentJob(jobs, onOpen) }
            item { RecentAlerts(alerts, zone, onOpen) }
            item { Readings(vm.data, readings, online, zone) }
            item { Track(m, track, zone) }
        }
    }
}

@Composable
private fun StatusCard(m: MachineMapDto, connectivity: String, lastSeen: String, color: androidx.compose.ui.graphics.Color, info: MachineDto?, zone: ZoneId) {
    SectionCard("${m.name} · ${m.assetCode}") {
        StatusPill(connectivity, color)
        KeyValue("Last seen", lastSeen)
        KeyValue("Last position", OwnerFormat.dateTime(m.positionTime, zone))
        KeyValue("Engine (tracker)", OwnerFormat.humanize(m.observedEngine))
        KeyValue("Motion (tracker)", OwnerFormat.humanize(m.observedMotion))
        KeyValue("Reported work status", OwnerFormat.humanize(m.reportedWorkStatus))
        KeyValue("Location compliance", OwnerFormat.humanize(m.locationCompliance))
        KeyValue("Machine status", OwnerFormat.humanize(m.machineStatus))
        m.operator?.let { KeyValue("Operator", it) }
        m.supervisor?.let { KeyValue("Supervisor", it) }
        m.trackerState?.let { KeyValue("Tracker", OwnerFormat.humanize(it)) }
        info?.let { i ->
            listOfNotNull(i.manufacturer, i.model, i.yearOfManufacture?.toString()).takeIf { it.isNotEmpty() }?.let { KeyValue("Model", it.joinToString(" ")) }
            KeyValue("Ownership", OwnerFormat.humanize(i.ownership))
        }
    }
}

@Composable
private fun CurrentJob(state: ScreenState<PageDto<JobDto>>, onOpen: (OwnerDestination) -> Unit) {
    SectionCard("Current job") {
        StaleBanner(state.snapshot)
        val job = state.data?.items?.firstOrNull()
        when {
            job != null -> Text(
                "${job.jobNumber} · ${OwnerFormat.humanize(job.status)} — open",
                Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Job(job.id.toString())) },
                color = MaterialTheme.colorScheme.primary,
            )
            state.loading -> Text("Loading…")
            state.error != null -> Text(state.error!!.message, color = MaterialTheme.colorScheme.error)
            else -> Text("No job in progress.")
        }
    }
}

@Composable
private fun RecentAlerts(state: ScreenState<PageDto<AlertDto>>, zone: ZoneId, onOpen: (OwnerDestination) -> Unit) {
    SectionCard("Recent alerts") {
        StaleBanner(state.snapshot)
        val items = state.data?.items.orEmpty()
        if (items.isEmpty()) Text(state.error?.message ?: if (state.loading) "Loading…" else "No alerts.")
        items.forEach { a ->
            Text(
                "${OwnerFormat.humanize(a.severity)} · ${a.title} · ${OwnerFormat.humanize(a.status)} · ${OwnerFormat.dateTime(a.eventTime, zone)}",
                Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Alerts(a.id.toString())) },
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun Readings(data: OwnerData, state: ScreenState<PageDto<MeterCaptureDto>>, online: Boolean, zone: ZoneId) {
    SectionCard("Last meter readings") {
        StaleBanner(state.snapshot)
        val items = state.data?.items.orEmpty()
        if (items.isEmpty()) Text(state.error?.message ?: if (state.loading) "Loading…" else "No readings yet.")
        items.forEach { c ->
            Text(
                "${OwnerFormat.humanize(c.kind)} ${c.reading.toPlainString()} · ${OwnerFormat.dateTime(c.capturedAt, zone)} · " +
                    "${OwnerFormat.humanize(c.captureMode)}${if (c.manuallyCorrected) " (corrected)" else ""} · GPS ${OwnerFormat.humanize(c.gpsStatus).lowercase()}",
                style = MaterialTheme.typography.bodySmall,
            )
            c.photoAttachmentId?.let { id -> EvidencePhoto("meter photo", online && !state.stale) { data.attachmentUrl(id.toString()) } }
        }
    }
}

@Composable
private fun Track(m: MachineMapDto, state: ScreenState<HistoryDto>, zone: ZoneId) {
    SectionCard("Last 24 hours") {
        StaleBanner(state.snapshot)
        val h = state.data
        if (h == null) {
            Text(state.error?.message ?: "Loading track…")
            return@SectionCard
        }
        Text("${h.points.size} positions, ${"%.1f".format(java.util.Locale.ROOT, h.distanceKm)} km" + if (h.truncated) " (truncated)" else "")
        if (h.points.size >= 2) {
            OwnerMap(
                markers = if (m.hasPosition) listOf(MapMarker(m.machineId.toString(), m.latitude!!, m.longitude!!, OwnerColors.Recent, m.name, code = m.assetCode, live = m.isLive)) else emptyList(),
                description = "Track of ${m.name} over the last 24 hours. Stops are listed below.",
                modifier = Modifier.fillMaxWidth().height(240.dp),
                track = h.points.map { it.latitude to it.longitude },
            )
        }
        h.stops.takeLast(10).forEach { s ->
            Text("Stopped ${OwnerFormat.dateTime(s.start, zone)} for ${s.durationSeconds / 60} min", style = MaterialTheme.typography.bodySmall)
        }
        h.siteVisits.takeLast(10).forEach { v ->
            Text("At ${v.geofenceName}: ${OwnerFormat.dateTime(v.enteredAt, zone)} – ${OwnerFormat.dateTime(v.exitedAt, zone)}", style = MaterialTheme.typography.bodySmall)
        }
        if (h.points.isEmpty()) Text("No positions in the last 24 hours.")
    }
}
