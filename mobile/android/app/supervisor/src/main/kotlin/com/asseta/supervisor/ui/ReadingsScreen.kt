package com.asseta.supervisor.ui

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.inbox.FindingTexts
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.data.ReadingItem
import com.asseta.core.sync.data.ResetItem
import com.asseta.core.sync.usecase.MeterResetRequest
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.LinkRow
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.capture.CameraCapture
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.capture.PermissionRationale
import com.asseta.supervisor.capture.hasAllPermissions
import com.asseta.supervisor.ui.finance.DecimalField
import com.asseta.supervisor.ui.finance.SaveSection
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.TextInput
import com.asseta.supervisor.ui.finance.after
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

/** Readings tab: every reading of mine (newest first) with one combined status, and my meter reset requests. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReadingsScreen(snapshot: InboxSnapshot, syncing: Boolean, onRefresh: () -> Unit, onRoute: (Route) -> Unit) {
    var attentionOnly by rememberSaveable { mutableStateOf(false) }
    val readings = snapshot.readings.filter { !attentionOnly || it.status.needsAttention }
    val resets = snapshot.resets.filter { !attentionOnly || it.status.needsAttention }
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            item(key = "filter") {
                FilterChipRow(listOf(false to "All", true to "Needs attention"), attentionOnly, { attentionOnly = it }, Modifier.padding(bottom = 8.dp))
            }
            if (snapshot.loaded && readings.isEmpty() && resets.isEmpty()) {
                item(key = "empty") {
                    if (attentionOnly) EmptyState("Nothing needs attention", "Flagged or rejected readings appear here.")
                    else EmptyState("No readings yet", "Readings you capture on your jobs appear here with the office's review.")
                }
            }
            groupedSection(
                keyPrefix = "readings",
                header = if (readings.isEmpty()) null else "My readings",
                items = readings.map { r ->
                    GroupedItem(r.id, onClick = { onRoute(Route.ReadingDetail(r.id)) }) { ReadingRow(snapshot, r) }
                },
            )
            groupedSection(
                keyPrefix = "resets",
                header = if (resets.isEmpty()) null else "Meter reset requests",
                items = resets.map { r ->
                    GroupedItem(r.key, onClick = { onRoute(Route.ResetDetail(r.key)) }) { ResetRow(snapshot, r) }
                },
            )
        }
    }
}

@Composable
fun ReadingRow(snapshot: InboxSnapshot, r: ReadingItem) {
    val job = snapshot.jobs[r.jobId]?.jobNumber
    val machine = snapshot.machineOf(r)?.let(snapshot.machines::get)?.assetCode
    InboxRow(
        listOfNotNull(job, InboxTexts.readingKind(r.kind)).joinToString(" · "), r.status,
        listOfNotNull(r.reading, machine).joinToString(" · "),
        LocalTime.format(r.atMs) + if (r.openFindings > 0) " · ${r.openFindings} open finding(s)" else "",
    )
}

@Composable
fun ResetRow(snapshot: InboxSnapshot, r: ResetItem) {
    InboxRow(
        snapshot.machines[r.machineId]?.assetCode ?: "Meter reset", r.status,
        "${r.oldReading} → ${r.newReading}", LocalTime.format(r.atMs),
    )
}

/** One reading: photo, OCR vs entered, GPS, findings with review, sync state; "Request meter reset". */
@Composable
fun ReadingDetailScreen(field: FieldGraph, snapshot: InboxSnapshot, id: String, onRoute: (Route) -> Unit) {
    val r = snapshot.readings.firstOrNull { it.id == id }
    if (r == null) {
        if (snapshot.loaded) EmptyState("Reading not available", "It is no longer on this phone.")
        return
    }
    val s = r.server
    val c = r.local
    val machineId = snapshot.machineOf(r)
    val machine = machineId?.let(snapshot.machines::get)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            LabeledRow("Status", "") { StatusPill(r.status) }
            LabeledRow(InboxTexts.readingKind(r.kind), r.reading)
            snapshot.jobs[r.jobId]?.let { j -> LabeledRow("Job", j.jobNumber) }
            machine?.let { LabeledRow("Machine", InboxTexts.machine(it.assetCode, it.name)) }
            LabeledRow("Captured", LocalTime.format(r.atMs))
            LabeledRow("Capture mode", InboxTexts.captureMode(r.captureMode))
        }
        Section("Photo") {
            val localPhoto = c?.photoAttachmentLocalId
            val remote = s?.photoAttachmentId
            if (localPhoto == null && remote == null) {
                Text("No photo with this reading.", style = AssetaType.footnote, color = palette.secondaryText)
            } else {
                EvidenceImage(
                    "Meter photo",
                    local = localPhoto?.let { lid -> { field.inbox.localEvidence(lid) } },
                    remoteUrl = remote?.let { rid -> { field.online.attachmentUrl(rid) } },
                )
            }
        }
        val ocr = s?.ocrValue ?: c?.ocrValue
        Section("Camera reading", footer = if (ocr == null) "Typed in; the camera did not read this meter." else null) {
            LabeledRow("Read by camera", ocr ?: "—")
            InboxTexts.confidence(s?.ocrConfidence ?: c?.ocrConfidence)?.let { LabeledRow("Confidence", it) }
            LabeledRow("Entered", r.reading)
            if (s?.manuallyCorrected == true || (ocr != null && ocr != r.reading)) LabeledRow("Corrected by hand", "Yes", WarningColor)
        }
        Section("GPS") {
            val status = s?.gpsStatus ?: c?.gpsStatus
            if (status != null) {
                Text(InboxTexts.gps(status, s?.latitude ?: c?.latitude, s?.longitude ?: c?.longitude, s?.accuracyM ?: c?.accuracyM),
                    style = AssetaType.subheadline)
            }
        }
        Section("Review", footer = InboxTexts.reviewOutcome(s?.reviewStatus, r.findings.size)) {
            if (s == null) Text("The office's review appears here after the reading is synced.", style = AssetaType.footnote, color = palette.secondaryText)
            r.findings.forEach { f ->
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(FindingTexts.type(f.exceptionType), style = AssetaType.headline, modifier = Modifier.weight(1f))
                        com.asseta.core.ui.components.Pill(
                            FindingTexts.review(f.status),
                            if (f.status == "OPEN") WarningColor else palette.recent,
                        )
                    }
                    Text(
                        "Severity: ${FindingTexts.severity(f.severity)}" + if (f.blocking) " · Blocking" else "",
                        style = AssetaType.footnote, color = if (f.blocking) palette.offline else palette.secondaryText,
                    )
                    f.reviewNote?.let { Text("Office note: $it", style = AssetaType.subheadline) }
                    f.reviewedAt?.let { Text("Reviewed ${LocalTime.formatIso(it)}", style = AssetaType.caption, color = palette.secondaryText) }
                }
            }
        }
        r.op?.let { op ->
            Section("Sync") {
                LabeledRow("On this phone", "") { SyncStateLabel(op.status) }
                op.errorCode?.let { Text("$it: ${op.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline) }
            }
        }
        if (machine != null) {
            Section(null) {
                ActionRow("Request meter reset", R.drawable.ic_wrench) { onRoute(Route.ResetRequest(machine.id, r.reading)) }
                LinkActionRow("Machine ${machine.assetCode}", R.drawable.ic_gauge) { onRoute(Route.MachineDetail(machine.id, machine.assetCode)) }
            }
        }
    }
}

/** A machine of mine: latest reading, active job, my readings and reset requests; "Request meter reset". */
@Composable
fun MachineDetailScreen(snapshot: InboxSnapshot, machineId: String, onRoute: (Route) -> Unit) {
    val machine = snapshot.machines[machineId]
    if (machine == null) {
        if (snapshot.loaded) EmptyState("Machine not available", "It is no longer assigned to you on this device.")
        return
    }
    val readings = snapshot.readings.filter { snapshot.machineOf(it) == machineId }
    val latest = snapshot.latestReadingByMachine()[machineId]
    val jobs = snapshot.jobs.values.filter { it.machineId == machineId && it.status in setOf("IN_PROGRESS", "APPROVED") }
    val resets = snapshot.resets.filter { it.machineId == machineId }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            LabeledRow("Machine", InboxTexts.machine(machine.assetCode, machine.name))
            LabeledRow("Latest reading", latest?.let { "${it.reading} · ${LocalTime.format(it.atMs)}" } ?: "No readings yet")
            LabeledRow("Meter precision", FieldTexts.meterPrecision(machine.meterDecimalPlaces))
        }
        if (jobs.isNotEmpty()) {
            Section("Active job") {
                jobs.forEach { j -> NavigationRowCompat(j.jobNumber, FieldTexts.jobStatus(j.status)) { onRoute(Route.JobDetail(j.id, j.jobNumber)) } }
            }
        }
        Section(null) {
            ActionRow("Request meter reset", R.drawable.ic_wrench) { onRoute(Route.ResetRequest(machineId, latest?.reading)) }
        }
        if (readings.isNotEmpty()) {
            Section("My readings") {
                readings.forEach { r -> LinkRow(onClick = { onRoute(Route.ReadingDetail(r.id)) }) { ReadingRow(snapshot, r) } }
            }
        }
        if (resets.isNotEmpty()) {
            Section("Meter reset requests") {
                resets.forEach { r -> LinkRow(onClick = { onRoute(Route.ResetDetail(r.key)) }) { ResetRow(snapshot, r) } }
            }
        }
    }
}

@Composable
private fun NavigationRowCompat(title: String, badge: String, onClick: () -> Unit) =
    com.asseta.core.ui.components.NavigationRow(title, badge = badge, onClick = onClick)

/** One meter reset request: readings, reason, evidence, the office's decision and sync state. */
@Composable
fun ResetDetailScreen(field: FieldGraph, snapshot: InboxSnapshot, key: String, onRoute: (Route) -> Unit) {
    val r = snapshot.resets.firstOrNull { it.key == key }
    if (r == null) {
        if (snapshot.loaded) EmptyState("Reset request not available", "It is no longer on this phone.")
        return
    }
    val machine = snapshot.machines[r.machineId]
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            LabeledRow("Status", "") { StatusPill(r.status) }
            LabeledRow("Machine", machine?.let { InboxTexts.machine(it.assetCode, it.name) } ?: "Machine")
            LabeledRow("Reading before", r.oldReading)
            LabeledRow("Reading after", r.newReading)
            LabeledRow("Effective", LocalTime.format(r.effectiveAtMs))
            r.decidedAtMs?.let { LabeledRow("Decided", LocalTime.format(it)) }
        }
        Section("Reason") { Text(r.reason, style = AssetaType.subheadline) }
        if (r.hasEvidence) {
            Section("Evidence photo") {
                val op = r.op
                EvidenceImage(
                    "Meter reset evidence",
                    local = op?.let { o -> { field.inbox.attachmentsOf(o.id).firstNotNullOfOrNull { field.inbox.localEvidence(it) } } },
                    remoteUrl = r.server?.evidenceAttachmentId?.let { id -> { field.online.attachmentUrl(id) } },
                )
            }
        }
        r.op?.let { op ->
            Section("Sync") {
                LabeledRow("On this phone", "") { SyncStateLabel(op.status) }
                op.errorCode?.let { Text("$it: ${op.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline) }
            }
        }
        if (machine != null) {
            Section(null) { LinkActionRow("Machine ${machine.assetCode}", R.drawable.ic_gauge) { onRoute(Route.MachineDetail(machine.id, machine.assetCode)) } }
        }
    }
}

/** Fields of the reset request form. */
data class ResetForm(
    val oldReading: String = "",
    val newReading: String = "",
    val reason: String = "",
    val photo: CapturedPhoto? = null,
)

class ResetRequestViewModel(private val field: FieldGraph, private val tenantId: String, val machineId: String, oldReading: String?) : ViewModel() {
    private val clientId = UUID.randomUUID().toString()
    private val _form = MutableStateFlow(ResetForm(oldReading = oldReading.orEmpty()))
    val form: StateFlow<ResetForm> = _form.asStateFlow()
    private val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()
    private val _unavailable = MutableStateFlow<String?>(null)

    /** Why reset requests cannot be recorded (server without the capability, never synced), or null. */
    val unavailable: StateFlow<String?> = _unavailable.asStateFlow()

    init {
        viewModelScope.launch { _unavailable.value = field.meterReset.unavailable(tenantId) }
    }

    fun edit(change: (ResetForm) -> ResetForm) = _form.update(change)

    fun onPhotoError(message: String) = _save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    fun save() {
        if (_save.value.saving) return
        val f = _form.value
        _save.update { it.copy(saving = true, messages = emptyList()) }
        viewModelScope.launch {
            val result = field.meterReset(
                MeterResetRequest(tenantId, clientId, machineId, f.oldReading, f.newReading, f.reason, f.photo?.jpeg,
                    f.photo?.takenAtMs ?: field.clock.nowMs()),
            )
            _save.update { it.after(result) }
        }
    }
}

/** Request a meter reset (`METER_RESET_REQUEST`): readings before/after, reason and an evidence photo. */
@Composable
fun ResetRequestScreen(vm: ResetRequestViewModel, snapshot: InboxSnapshot, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val unavailable by vm.unavailable.collectAsStateWithLifecycle()
    val editable = !save.saving && !save.saved && unavailable == null
    val machine = snapshot.machines[vm.machineId]
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        unavailable?.let { NoticeCard("Meter reset not available", it, isError = true) }
        Section(null, footer = "The office approves or rejects the reset. Until then readings continue from the old meter.") {
            LabeledRow("Machine", machine?.let { InboxTexts.machine(it.assetCode, it.name) } ?: "Machine")
        }
        Section("Readings") {
            DecimalField("Reading before the reset", form.oldReading, { v -> vm.edit { it.copy(oldReading = v) } }, editable)
            DecimalField("Reading after the reset", form.newReading, { v -> vm.edit { it.copy(newReading = v) } }, editable)
        }
        Section("Reason", footer = "At least 10 characters, e.g. \"Meter replaced by the workshop\".") {
            TextInput("Reason", form.reason, { v -> vm.edit { it.copy(reason = v) } }, editable, singleLine = false)
        }
        EvidencePhotoSection(form.photo, { p -> vm.edit { it.copy(photo = p) } }, vm::onPhotoError, editable)
        SaveSection(save, vm::save, onDone, enabled = editable)
    }
}

@Composable
private fun EvidencePhotoSection(photo: CapturedPhoto?, onPhoto: (CapturedPhoto?) -> Unit, onError: (String) -> Unit, enabled: Boolean) {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var open by remember { mutableStateOf(false) }
    Section("Evidence photo (required)", footer = "Stored encrypted on this phone and uploaded before the request is sent.") {
        photo?.let { p ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                val preview = remember(p) { MeterOcr.decodeForOcr(p.jpeg, p.rotationDegrees)?.asImageBitmap() }
                preview?.let { Image(it, "Meter photo", Modifier.weight(1f).heightIn(max = 160.dp), contentScale = ContentScale.Fit, alignment = Alignment.CenterStart) }
                if (enabled) TextButton(onClick = { onPhoto(null) }) { Text("Remove", color = palette.offline) }
            }
        }
        when {
            !enabled -> Unit
            open && !granted -> PermissionRationale(
                title = "Camera",
                rationale = "A photo of the meter is kept as evidence for the office. It stays encrypted on this phone until uploaded.",
                permissions = arrayOf(Manifest.permission.CAMERA),
                onResult = { granted = it; if (!it) open = false },
            )
            open -> CameraCapture(
                buttonLabel = "Photograph meter",
                onCaptured = { onPhoto(it); open = false },
                onError = { onError(it); open = false },
            )
            photo == null -> OutlinedButton(onClick = { open = true }) { Text("Photograph meter") }
        }
    }
}
