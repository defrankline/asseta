package com.asseta.owner.ui.reports

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.reports.MachineReportApproval
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.MachineReportDetail
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.ShellButton
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

/** One machine report (design OwnerReportApproval) with approve / reject while it waits. */
class ReportApprovalViewModel(val data: OwnerData, val reportId: String, reading: Boolean, refreshOn: Flow<Unit>) :
    SnapshotViewModel<MachineReportDetail>({ data.machineReport(reportId, reading) }, refreshOn) {
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    /** Approve (the reason is an optional note) or reject (the reason is required). */
    fun decide(approve: Boolean, reason: String) {
        if (_busy.value || (!approve && !MachineReportApproval.rejectReasonValid(reason))) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            val r = if (approve) data.approveMachineReport(reportId, reason) else data.rejectMachineReport(reportId, reason)
            when (r) {
                is ActionResult.Done -> {
                    replaceData { it.copy(report = r.value.copy(lines = r.value.lines.ifEmpty { it.report.lines }, tracker = r.value.tracker ?: it.report.tracker)) }
                    _message.value = ReportPresentation.decided(r.value, approve)
                }
                is ActionResult.Refused -> {
                    _error.value = ReportTexts.refusal(r.code, r.error.message)
                    if (r.reload || r.code == "REPORT_NOT_PENDING") refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun ReportApprovalScreen(vm: ReportApprovalViewModel, session: OwnerSession, online: Boolean, nowMs: () -> Long) {
    val state by vm.state.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    var reason by rememberSaveable { mutableStateOf("") }
    var confirmReject by rememberSaveable { mutableStateOf(false) }
    val zone = ZoneId.systemDefault()
    SnapshotScaffold(state, vm::refresh) { detail ->
        val r = detail.report
        val customers = ReportPresentation.customerLines(r)
        val reasons = ReportPresentation.nonProductiveLines(r)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 12.dp, bottom = 24.dp)) {
            item {
                ShellCard {
                    Row(Modifier.fillMaxWidth()) {
                        Column(Modifier.weight(1f)) {
                            Text("${ReportPresentation.machine(r)} machine report", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                            Text(ReportPresentation.attentionDetail(r, nowMs(), zone), fontSize = 13.sp, color = palette.secondaryText)
                        }
                        if (r.status != MachineReportDto.SUBMITTED) {
                            StatusPill(ReportPresentation.statusLabel(r.status), if (r.status == MachineReportDto.APPROVED) PillTone.GOOD else PillTone.BAD)
                        }
                    }
                    (r.photoAttachmentId ?: detail.capture?.photoAttachmentId?.toString())?.let { photo ->
                        Column(Modifier.padding(top = 8.dp)) { EvidencePhoto(ReportTexts.VIEW_PHOTO, online && !state.stale) { vm.data.attachmentUrl(photo) } }
                    }
                    Text(ReportPresentation.readings(r), fontSize = 24.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 10.dp))
                    Text(ReportPresentation.readLine(r, detail.capture), fontSize = 14.sp, color = palette.accent)
                    ReportPresentation.gpsLine(detail.capture)?.let { Text(it, fontSize = 13.sp, color = palette.secondaryText) }
                }
            }
            if (customers.isNotEmpty()) {
                item { SectionLabel("${ReportTexts.CUSTOMERS} · ${Figures.hours(Figures.dec(r.customerHours))}") }
                item {
                    ShellCard(padding = false) {
                        customers.forEachIndexed { i, l ->
                            CardRow(
                                l.customerName ?: "Customer", subtitle = ReportPresentation.beforeAfter(l), last = i == customers.lastIndex,
                                trailing = { Text(Figures.hours(Figures.dec(l.hours)), fontWeight = FontWeight.Bold) },
                            )
                        }
                    }
                }
            }
            if (reasons.isNotEmpty()) {
                item { SectionLabel("${ReportTexts.NON_PRODUCTIVE} · ${Figures.hours(Figures.dec(r.nonProductiveHours))}") }
                item {
                    ShellCard(padding = false) {
                        reasons.forEachIndexed { i, l ->
                            CardRow(
                                l.reasonName ?: ReportPresentation.reasonShort(l), subtitle = ReportPresentation.quoted(l.note), last = i == reasons.lastIndex,
                                trailing = { Text(Figures.hours(Figures.dec(l.hours)), fontWeight = FontWeight.Bold) },
                            )
                        }
                    }
                }
            }
            item {
                Text(
                    ReportPresentation.tracker(r.tracker, r), fontSize = 14.sp, color = palette.secondaryText,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 16.dp),
                )
            }
            r.note?.takeIf { it.isNotBlank() }?.let { note ->
                item { SectionLabel(ReportTexts.NOTE_LABEL) }
                item { ShellCard { Text(note, fontSize = 15.sp) } }
            }
            if (r.status != MachineReportDto.SUBMITTED) {
                r.decisionNote?.takeIf { it.isNotBlank() }?.let { note ->
                    item { ShellCard(Modifier.padding(top = 12.dp)) { Text(listOfNotNull(r.decidedByName, note).joinToString(": "), fontSize = 14.sp, color = palette.secondaryText) } }
                }
            } else {
                item {
                    val why = ReportPresentation.cannotDecide(session.permissions, r, session.userId)
                    val gate = session.can(OwnerAction.DECIDE_MACHINE_REPORT, online, state.snapshot?.source)
                    Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        when {
                            why != null -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(why) }
                            gate is MutationCheck.Blocked -> Column(Modifier.padding(horizontal = 20.dp)) { BlockedNote(gate.reason) }
                            else -> {
                                OutlinedTextField(
                                    reason, { reason = it.take(1000) }, Modifier.padding(horizontal = 20.dp).fillMaxWidth().testTag("report-reason"),
                                    label = { Text(ReportTexts.REASON_LABEL) }, placeholder = { Text(ReportTexts.REASON_PLACEHOLDER) }, minLines = 2,
                                )
                                Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    ShellButton(
                                        ReportTexts.REJECT, primary = false, enabled = !busy && MachineReportApproval.rejectReasonValid(reason),
                                        modifier = Modifier.weight(1f).testTag("report-reject"),
                                    ) { confirmReject = true }
                                    ShellButton(ReportTexts.APPROVE, primary = true, enabled = !busy, modifier = Modifier.weight(1f).testTag("report-approve")) {
                                        vm.decide(true, reason)
                                    }
                                }
                            }
                        }
                        error?.let {
                            Text(
                                it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.padding(horizontal = 20.dp).semantics { liveRegion = LiveRegionMode.Assertive },
                            )
                        }
                    }
                }
            }
            message?.let { m ->
                item {
                    Text(m, color = palette.accent, modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp).semantics { liveRegion = LiveRegionMode.Polite })
                }
            }
        }
    }
    if (confirmReject) {
        AlertDialog(
            onDismissRequest = { confirmReject = false },
            title = { Text(ReportTexts.CONFIRM_REJECT) },
            text = { Text(ReportTexts.CONFIRM_REJECT_TEXT) },
            confirmButton = { TextButton({ confirmReject = false; vm.decide(false, reason) }) { Text(ReportTexts.REJECT, color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ confirmReject = false }) { Text("Cancel") } },
        )
    }
    LaunchedEffect(message) { if (message != null) reason = "" }
}
