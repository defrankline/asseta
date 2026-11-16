package com.asseta.supervisor.ui.report

import android.Manifest
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.OcrStep
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportLineDraft
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.sync.data.ReportMachine
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.PrimaryAction
import com.asseta.core.ui.shell.SecondaryAction
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.ShellProgress
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.shell.StepBars
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.capture.CameraCapture
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.capture.PermissionRationale
import com.asseta.supervisor.capture.hasAllPermissions
import com.asseta.supervisor.capture.hasAnyPermission
import com.asseta.supervisor.ui.Busy
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.FieldTexts
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SearchablePickerField
import java.math.BigDecimal
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val T = ReportTexts

/** Machine report in three steps; system back steps back before leaving. [onDone] after the report is queued. */
@Composable
fun MachineReportScreen(vm: MachineReportViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val view by vm.view.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    BackHandler(enabled = form.step != ReportStep.READING && !form.saving) { vm.back() }
    LaunchedEffect(form.saved) { if (form.saved) onDone() }
    val machines = vm.machines(view)
    val machine = machines.firstOrNull { it.id == form.machineId }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when {
            view.loaded && machines.isEmpty() -> Column(Modifier.padding(horizontal = 16.dp)) { EmptyState(T.TITLE, T.NO_MACHINES) }
            form.step == ReportStep.READING -> ReadingStep(vm, machines, machine)
            form.step == ReportStep.SPLIT && machine != null -> SplitStep(vm, machine, access?.reportCustomerLines != false)
            form.step == ReportStep.REVIEW && machine != null -> ReviewStep(vm, machine)
        }
        if (form.messages.isNotEmpty()) {
            Column(Modifier.padding(horizontal = 20.dp)) { form.messages.forEach { Text(it, color = palette.offline) } }
        }
    }
}

@Composable
private fun ReadingStep(vm: MachineReportViewModel, machines: List<ReportMachine>, machine: ReportMachine?) {
    val form by vm.form.collectAsStateWithLifecycle()
    val c = form.capture
    val context = LocalContext.current
    var cameraGranted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var cameraOpen by remember { mutableStateOf(false) }
    LaunchedEffect(form.machineId) { if (form.machineId != null && context.hasAnyPermission(GpsLocator.PERMISSIONS) && !c.locationDecided) vm.onLocationDecision(true) }
    StepBars(1, label = T.STEP_READING)
    ShellCard {
        SearchablePickerField(
            T.MACHINE, machines.map { PickerOption(it.id, it.label, T.state(it.state)) }, form.machineId, vm::select,
            emptyText = T.NO_MACHINES, enabled = !form.saving,
        )
    }
    machine ?: return
    if (machine.state == ReportState.AWAITING_APPROVAL) {
        ShellCard {
            StatusPill(T.state(machine.state), PillTone.WAITING)
            Text(machine.status.pendingReportNumber ?: machine.local?.let { T.QUEUED }.orEmpty(), color = palette.secondaryText, modifier = Modifier.padding(top = 8.dp))
        }
        return
    }
    val opening = machine.state == ReportState.OPENING
    if (opening) {
        ShellCard {
            Text(T.OPENING_TITLE, style = MaterialTheme.typography.titleMedium)
            Text(T.OPENING_BODY, color = palette.secondaryText, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp))
        }
    } else {
        LastReadingCard(machine, vm.previous(), vm.correcting())
    }
    if (vm.correcting()) {
        ShellCard {
            StatusPill(T.state(ReportState.REJECTED), PillTone.BAD)
            Text(T.rejected(machine.rejected?.decisionNote), color = palette.secondaryText, modifier = Modifier.padding(top = 8.dp))
            Text(T.NEW_READING, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(top = 12.dp))
            Text(MachineReportRules.formatReading(vm.reading() ?: BigDecimal.ZERO, machine.decimals), fontSize = 28.sp, fontWeight = FontWeight.Bold)
        }
    } else {
        c.blocked?.let { ShellCard { Text(it, color = palette.offline) } }
        if (c.blocked == null && c.mode != null) {
            // The meter photo: on-phone OCR fills the reading; the supervisor checks the number.
            ShellCard {
                c.photo?.let { photo ->
                    val preview = remember(photo) { MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)?.asImageBitmap() }
                    preview?.let { Image(it, T.photoCaption(false, null), Modifier.fillMaxWidth().heightIn(max = 220.dp), contentScale = ContentScale.Fit) }
                    Text(T.photoCaption(c.mode == CaptureMode.AUTOMATIC && c.ocr?.value != null, gpsLabel(c.gps)), style = MaterialTheme.typography.bodySmall,
                        color = palette.secondaryText, modifier = Modifier.padding(top = 8.dp))
                }
                when {
                    c.ocrBusy -> Busy(T.READING_PHONE)
                    cameraOpen && !cameraGranted -> PermissionRationale(
                        title = "Camera", rationale = "A photo of the hour meter is kept as evidence and the reading is recognized on this phone. Photos stay encrypted on this phone until uploaded.",
                        permissions = arrayOf(Manifest.permission.CAMERA), onResult = { cameraGranted = it; if (!it) cameraOpen = false },
                    )
                    cameraOpen -> CameraCapture(
                        buttonLabel = if (c.photo == null) T.TAKE_PHOTO else T.RETAKE_PHOTO,
                        onCaptured = { vm.onPhoto(it); cameraOpen = false }, onError = { vm.onPhotoError(it); cameraOpen = false },
                    )
                    else -> TextButton(onClick = { cameraOpen = true }) { Text(if (c.photo == null) T.TAKE_PHOTO else T.RETAKE_PHOTO, color = palette.accent) }
                }
                if (c.ocrStep == OcrStep.RECAPTURE && !c.ocrBusy) {
                    Text("The reading could not be recognized reliably. Retake the photo (${c.recapturesLeft} more after this).", color = palette.stale)
                }
            }
            if (!c.locationDecided) {
                Column(Modifier.padding(horizontal = 20.dp)) {
                    PermissionRationale(
                        title = "Location for this reading",
                        rationale = "Each reading records a fresh location fix while you use the app (never in the background). If you decline, the reading is saved without location and flagged for review.",
                        permissions = GpsLocator.PERMISSIONS, onResult = vm::onLocationDecision, declineLabel = "Continue without location",
                    )
                }
            } else if (c.gps != null && c.gps !is GpsOutcome.Fix) {
                Text(FieldTexts.gpsFailure(c.gps), color = palette.stale, modifier = Modifier.padding(horizontal = 20.dp))
            }
            if (c.readingEditable || c.photo != null || c.mode == CaptureMode.MANUAL) {
                Column(Modifier.padding(horizontal = 20.dp)) {
                    Text(T.NEW_READING, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
                    OutlinedTextField(
                        value = c.readingText, onValueChange = vm::onReadingChanged, enabled = c.readingEditable && !form.saving,
                        textStyle = MaterialTheme.typography.headlineSmall, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = if (c.decimals == 0) KeyboardType.Number else KeyboardType.Decimal),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }
    }
    val issues = vm.readingIssues()
    if (opening) {
        if (issues.isNotEmpty() && (c.photo != null || c.readingText.isNotEmpty())) IssueList(issues)
        PrimaryAction(if (form.saving) T.SUBMITTING else T.SUBMIT_OPENING, enabled = issues.isEmpty() && !form.saving, onClick = vm::submit)
        return
    }
    vm.difference()?.takeIf { it.signum() > 0 && issues.isEmpty() }?.let { d ->
        ShellCard {
            Text(T.HOURS_TO_ACCOUNT, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
            Text("${MachineReportRules.formatReading(d, machine.decimals)} h", fontSize = 28.sp, fontWeight = FontWeight.Bold, color = palette.accent)
        }
    }
    if (issues.isNotEmpty() && (c.photo != null || c.readingText.isNotEmpty() || vm.correcting())) IssueList(issues)
    PrimaryAction(vm.difference()?.takeIf { it.signum() > 0 }?.let(T::nextAccount) ?: T.NEXT, enabled = issues.isEmpty(), onClick = vm::next)
    Text(T.NOTHING_TO_REPORT, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(horizontal = 20.dp))
}

@Composable
private fun IssueList(issues: List<String>) {
    Column(Modifier.padding(horizontal = 20.dp)) { issues.forEach { Text(it, color = palette.stale, style = MaterialTheme.typography.bodyMedium) } }
}

private fun gpsLabel(gps: GpsOutcome?): String? = (gps as? GpsOutcome.Fix)?.let { ReportTexts.gpsAccuracy(it.accuracyM) }

/** "Last reading 1,210.0 h · 12 Nov, 17:30 · approved". */
@Composable
private fun LastReadingCard(machine: ReportMachine, previous: BigDecimal?, correcting: Boolean) {
    ShellCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(T.LAST_READING, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
                Text(previous?.let { "${MachineReportRules.formatReading(it, machine.decimals)} h" } ?: "—", fontSize = 22.sp, fontWeight = FontWeight.Bold)
            }
            Column(horizontalAlignment = Alignment.End) {
                val at = if (correcting) machine.rejected?.startAt else machine.status.previousAt
                at?.let { Text(dayTime(it), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText) }
                Text(source(machine.status.previousSource), style = MaterialTheme.typography.bodySmall, color = palette.live)
            }
        }
    }
}

private fun source(s: String?): String = when (s) {
    "BASELINE" -> "baseline"
    "RESET" -> "meter reset"
    else -> ReportTexts.APPROVED
}

/** "12 Nov, 17:30" in local time. */
fun dayTime(iso: String, zone: ZoneId = ZoneId.systemDefault()): String =
    runCatching { java.time.OffsetDateTime.parse(iso).toInstant() }.getOrNull()?.atZone(zone)
        ?.format(DateTimeFormatter.ofPattern("d MMM, HH:mm", Locale.ENGLISH)) ?: iso

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SplitStep(vm: MachineReportViewModel, machine: ReportMachine, customerLines: Boolean) {
    val form by vm.form.collectAsStateWithLifecycle()
    val view by vm.view.collectAsStateWithLifecycle()
    val difference = vm.difference() ?: return
    val previous = vm.previous() ?: return
    val available = vm.available()
    val decimals = machine.decimals
    val accounted = MachineReportRules.accounted(form.lines, decimals)
    val left = difference - accounted
    var picker by remember { mutableStateOf<String?>(null) }
    StepBars(2, label = T.splitHeader(machine.code, previous, previous + difference))
    ShellCard {
        Text(T.ACCOUNTED, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
        Row(verticalAlignment = Alignment.Bottom) {
            Text(MachineReportRules.formatHours(accounted), fontSize = 28.sp, fontWeight = FontWeight.Bold)
            Text(" " + T.ofTotal(difference), color = palette.secondaryText, modifier = Modifier.padding(bottom = 4.dp))
        }
        ShellProgress(MachineReportRules.progress(difference, form.lines, decimals), Modifier.padding(top = 8.dp))
        Text(
            when {
                left.signum() > 0 -> T.left(left)
                left.signum() < 0 -> T.over(left.negate())
                else -> T.ALL_ACCOUNTED
            },
            color = if (left.signum() == 0) palette.live else palette.accent, modifier = Modifier.padding(top = 8.dp),
        )
    }
    if (customerLines) {
        SectionLabel(T.CUSTOMERS)
        form.lines.withIndex().filter { it.value is ReportLineDraft.Customer }.forEach { (i, l) ->
            val line = l as ReportLineDraft.Customer
            val cap = available[line.customerId] ?: BigDecimal.ZERO
            LineCard(
                title = line.customerName, subtitle = T.available(cap, MachineReportRules.afterThis(cap, line, decimals)),
                hours = line.hoursText, onHours = { h -> vm.editLine(i) { (it as ReportLineDraft.Customer).copy(hoursText = h) } },
                onRemove = { vm.removeLine(i) }, decimals = decimals,
                error = (MachineReportRules.hours(line.hoursText, decimals)?.let { it > cap } == true),
            )
        }
    }
    SectionLabel(T.NON_PRODUCTIVE)
    form.lines.withIndex().filter { it.value is ReportLineDraft.NonProductive }.forEach { (i, l) ->
        val line = l as ReportLineDraft.NonProductive
        LineCard(
            title = line.reasonName, subtitle = null, hours = line.hoursText,
            onHours = { h -> vm.editLine(i) { (it as ReportLineDraft.NonProductive).copy(hoursText = h) } }, onRemove = { vm.removeLine(i) }, decimals = decimals,
            note = line.note, onNote = { n -> vm.editLine(i) { (it as ReportLineDraft.NonProductive).copy(note = n) } },
        )
    }
    Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        if (customerLines) SecondaryAction(T.ADD_CUSTOMER, modifier = Modifier.weight(1f)) { picker = "customer" }
        SecondaryAction(T.ADD_NON_PRODUCTIVE, modifier = Modifier.weight(1f)) { picker = "reason" }
    }
    val check = MachineReportRules.check(difference, form.lines, available, decimals)
    (check as? FormCheck.Invalid)?.messages?.filter { left.signum() == 0 || !it.endsWith("still to account for") }?.takeIf { form.lines.isNotEmpty() }?.let { IssueList(it) }
    PrimaryAction(T.reviewButton(left), enabled = vm.canReview(), onClick = vm::review)
    Text(T.CAP_FOOTER, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(horizontal = 20.dp))
    picker?.let { kind ->
        ModalBottomSheet(onDismissRequest = { picker = null }) {
            Column(Modifier.padding(bottom = 32.dp)) {
                if (kind == "customer") {
                    val options = available.filter { (id, h) -> h.signum() > 0 && form.lines.none { it is ReportLineDraft.Customer && it.customerId == id } }
                    if (options.isEmpty()) Text(T.NO_CUSTOMER_HOURS, color = palette.secondaryText, modifier = Modifier.padding(20.dp))
                    options.forEach { (id, h) ->
                        val name = view.customerName(id) ?: id.take(8)
                        PickRow(name, "${MachineReportRules.formatHours(h)} h") { vm.addCustomer(id, name); picker = null }
                    }
                } else {
                    view.reasons.forEach { r -> PickRow(r.name, r.description) { vm.addNonProductive(r.id, r.name); picker = null } }
                }
            }
        }
    }
}

@Composable
private fun PickRow(title: String, subtitle: String?, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 20.dp, vertical = 14.dp)) {
        Text(title, fontWeight = FontWeight.SemiBold)
        subtitle?.let { Text(it, color = palette.secondaryText, style = MaterialTheme.typography.bodySmall) }
    }
    HorizontalDivider(color = palette.separator)
}

/** One line of the split: who / why, the hours on the right, a note for non-productive hours. */
@Composable
private fun LineCard(
    title: String,
    subtitle: String?,
    hours: String,
    onHours: (String) -> Unit,
    onRemove: () -> Unit,
    decimals: Int,
    note: String? = null,
    onNote: ((String) -> Unit)? = null,
    error: Boolean = false,
) {
    ShellCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = if (error) palette.offline else palette.secondaryText) }
            }
            OutlinedTextField(
                value = hours, onValueChange = { t -> onHours(t.filter { it.isDigit() || it == '.' || it == ',' }) }, singleLine = true,
                suffix = { Text("h") }, isError = error, modifier = Modifier.width(110.dp),
                keyboardOptions = KeyboardOptions(keyboardType = if (decimals == 0) KeyboardType.Number else KeyboardType.Decimal),
            )
        }
        if (onNote != null) {
            OutlinedTextField(note.orEmpty(), onNote, label = { Text(T.WHAT_HAPPENED) }, isError = note.isNullOrBlank(), modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
        }
        TextButton(onClick = onRemove) { Text(T.REMOVE, color = palette.offline) }
    }
}

@Composable
private fun ReviewStep(vm: MachineReportViewModel, machine: ReportMachine) {
    val form by vm.form.collectAsStateWithLifecycle()
    val difference = vm.difference() ?: return
    val previous = vm.previous() ?: return
    val reading = vm.reading() ?: return
    val decimals = machine.decimals
    val customers = form.lines.filterIsInstance<ReportLineDraft.Customer>()
    val non = form.lines.filterIsInstance<ReportLineDraft.NonProductive>()
    fun sum(lines: List<ReportLineDraft>) = lines.fold(BigDecimal.ZERO) { s, l -> s + (MachineReportRules.hours(l.hoursText, decimals) ?: BigDecimal.ZERO) }
    StepBars(3, label = T.STEP_REVIEW)
    ShellCard {
        Text(machine.label, fontWeight = FontWeight.Bold, fontSize = 17.sp)
        Text(T.readings(MachineReportRules.formatReading(previous, decimals), MachineReportRules.formatReading(reading, decimals)), modifier = Modifier.padding(top = 4.dp))
        val from = (if (vm.correcting()) machine.rejected?.startAt else machine.status.previousAt)?.let(::dayTime)
        val to = if (vm.correcting()) machine.rejected?.endAt?.let(::dayTime) else form.capture.photo?.takenAtMs?.let { dayTime(Instant.ofEpochMilli(it).toString()) }
        Text(T.period(from, to ?: dayTime(Instant.now().toString())), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
    }
    if (customers.isNotEmpty()) {
        SectionLabel(T.productive(sum(customers)))
        ShellCard { customers.forEach { ReviewRow(it.customerName, it.hoursText) } }
    }
    if (non.isNotEmpty()) {
        SectionLabel(T.nonProductive(sum(non)))
        ShellCard { non.forEach { ReviewRow(it.reasonName, it.hoursText, it.note) } }
    }
    ShellCard {
        Row {
            Text(T.TOTAL, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Text(T.matches(difference), color = palette.live, fontWeight = FontWeight.SemiBold)
        }
    }
    Text(T.approvalNote(sum(customers)), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(horizontal = 20.dp))
    Column(Modifier.padding(horizontal = 20.dp)) {
        OutlinedTextField(form.note, vm::onNote, label = { Text(T.NOTE) }, enabled = !form.saving, minLines = 2, modifier = Modifier.fillMaxWidth())
    }
    Spacer(Modifier.padding(4.dp))
    PrimaryAction(if (form.saving) T.SUBMITTING else T.SUBMIT, enabled = !form.saving && vm.canReview(), onClick = vm::submit)
}

@Composable
private fun ReviewRow(title: String, hours: String, note: String? = null) {
    Column(Modifier.padding(vertical = 6.dp)) {
        Row {
            Text(title, modifier = Modifier.weight(1f))
            Text("${MachineReportRules.formatHours(hours.replace(',', '.').toBigDecimalOrNull() ?: BigDecimal.ZERO)} h", fontWeight = FontWeight.SemiBold)
        }
        note?.takeIf { it.isNotBlank() }?.let { Text("“$it”", style = MaterialTheme.typography.bodySmall, color = palette.secondaryText) }
    }
}
