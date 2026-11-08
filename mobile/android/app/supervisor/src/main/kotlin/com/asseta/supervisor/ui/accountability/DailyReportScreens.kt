package com.asseta.supervisor.ui.accountability

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.sync.data.DailyReportRow
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.ui.ActionRow
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.EvidenceImage
import com.asseta.supervisor.ui.InboxRow
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.SyncStateLabel
import com.asseta.supervisor.ui.toneColor
import kotlinx.coroutines.launch

private val T = DailyReportTexts

private fun machineName(snapshot: InboxSnapshot, r: DailyReportRow): String =
    r.server?.machineCode ?: snapshot.machines[r.machineId]?.assetCode ?: DisplayNames.shortId(r.machineId).orEmpty()

/** My daily reports: those sent back to me first, then the rest (saved on the phone, refreshed when online). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DailyReportsScreen(field: FieldGraph, tenantId: String, userId: String?, snapshot: InboxSnapshot, onRoute: (Route) -> Unit) {
    val rows by produceState<List<DailyReportRow>?>(null, tenantId, userId) { field.dailyReports.observe(tenantId, userId).collect { value = it } }
    var refreshing by remember { mutableStateOf(false) }
    var offline by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun refresh() {
        scope.launch {
            refreshing = true
            offline = !field.dailyReports.refresh(tenantId)
            refreshing = false
        }
    }
    LaunchedEffect(tenantId) { refresh() }
    PullToRefreshBox(isRefreshing = refreshing, onRefresh = ::refresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            val list = rows
            if (list != null && list.isEmpty()) item(key = "empty") { EmptyState(T.EMPTY, T.EMPTY_HINT) }
            val (returned, others) = list.orEmpty().partition { it.returned }
            fun items(from: List<DailyReportRow>) = from.map { r -> GroupedItem(r.key, onClick = { onRoute(Route.DailyReportDetail(r.key)) }) { ReportRow(snapshot, r) } }
            groupedSection("returned", items(returned), header = if (returned.isEmpty()) null else T.SECTION_RETURNED)
            groupedSection("mine", items(others), header = if (others.isEmpty()) null else T.SECTION_MINE, footer = if (offline && list?.isNotEmpty() == true) T.STALE_FOOTER else null)
        }
    }
}

@Composable
private fun ReportRow(snapshot: InboxSnapshot, r: DailyReportRow) {
    val (label, tone) = T.status(r)
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        InboxRow("${machineName(snapshot, r)} · ${T.date(r.reportDate)}", null, r.server?.let { T.rowLine(it.totalHours, it.billableHours) })
        Pill(label, toneColor(tone))
    }
}

/** One report: figures, reasons, allocations, the office's note and sync state; "Correct and send again" while sent back. */
@Composable
fun DailyReportDetailScreen(field: FieldGraph, tenantId: String, key: String, snapshot: InboxSnapshot, access: FieldAccess?, onRoute: (Route) -> Unit) {
    val state by produceState<Pair<Boolean, DailyReportRow?>>(false to null, tenantId, key) {
        // The saved copy shows at once; the server's latest answer (a notification's "sent back") follows.
        launch { field.dailyReports.refresh(tenantId) }
        val fetched = field.dailyReports.report(tenantId, key)
        field.dailyReports.observe(tenantId, null).collect { rows ->
            value = true to (rows.firstOrNull { it.key == key } ?: fetched?.let { DailyReportRow(it.id, it, null, null) })
        }
    }
    val (loaded, row) = state
    if (row == null) {
        if (loaded) EmptyState(T.NOT_FOUND, T.NOT_FOUND_HINT)
        return
    }
    val s = row.server
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            val (label, tone) = T.status(row)
            LabeledRow(T.STATUS, "") { Pill(label, toneColor(tone)) }
            LabeledRow(T.MACHINE, machineName(snapshot, row))
            LabeledRow(T.DAY, T.date(row.reportDate))
            s?.let {
                LabeledRow(T.OPENING, T.hours(it.openingReading))
                LabeledRow(T.CLOSING, T.hours(it.closingReading))
                LabeledRow(T.TOTAL_HOURS, "${T.hours(it.totalHours)} h")
                LabeledRow(T.BILLABLE_HOURS, "${T.hours(it.billableHours)} h")
                LabeledRow(T.UNBILLABLE_HOURS, "${T.hours(it.unbillableHours)} h")
                if (it.differenceHours.toBigDecimalOrNull()?.signum() != 0) LabeledRow(T.NOT_ACCOUNTED, "${T.hours(it.differenceHours)} h")
                LabeledRow(T.SUBMITTED, LocalTime.formatIso(it.submittedAt))
                LabeledRow(T.SUBMITTED_BY, DisplayNames.of(it.submittedByName, it.submittedBy).orEmpty())
                if (it.isLate) Text(T.FLAG_LATE, color = palette.warning, style = AssetaType.footnote)
                if (it.isDuplicate) Text(T.FLAG_REPEAT, color = palette.warning, style = AssetaType.footnote)
            }
        }
        s?.takeIf { it.unbillable.isNotEmpty() }?.let { r ->
            Section(T.UNBILLABLE) { r.unbillable.forEach { LabeledRow(it.reasonName ?: DisplayNames.shortId(it.reasonId).orEmpty(), "${T.hours(it.hours)} h") } }
        }
        s?.takeIf { it.allocations.isNotEmpty() }?.let { r ->
            Section(T.ALLOCATIONS) {
                r.allocations.forEach { a -> LabeledRow(listOfNotNull(T.kind(a.kind), a.customerName, a.jobNumber).joinToString(" · "), "${T.hours(a.hours)} h") }
            }
        }
        (s?.note ?: row.local?.note)?.takeIf { it.isNotBlank() }?.let { Section(T.NOTE_LABEL) { Text(it, style = AssetaType.subheadline) } }
        s?.reviewNote?.takeIf { it.isNotBlank() }?.let { note ->
            Section(T.OFFICE_NOTE) {
                Text(note, style = AssetaType.subheadline)
                val by = if (s.status == DailyReportDto.RETURNED) T.RETURNED_BY else T.REVIEWED_BY
                DisplayNames.of(s.reviewedByName, s.reviewedBy)?.let { LabeledRow(by, it) }
            }
        }
        val op = row.op
        val photos = s?.evidenceAttachmentIds.orEmpty()
        if (photos.isNotEmpty()) {
            Section(T.PHOTOS) {
                photos.forEach { id -> EvidenceImage("daily report photo $id", null) { field.online.attachmentUrl(id) } }
            }
        } else if (op != null) {
            val local by produceState<List<String>>(emptyList(), op.id) { value = field.inbox.attachmentsOf(op.id) }
            if (local.isNotEmpty()) {
                Section(T.PHOTOS) { local.forEach { lid -> EvidenceImage("daily report photo $lid", { field.inbox.localEvidence(lid) }, null) } }
            }
        }
        if (op != null && s == null) {
            Section(T.SYNC) {
                LabeledRow(T.ON_THIS_PHONE, "") { SyncStateLabel(op.status) }
                op.errorCode?.let { code -> Text(FieldAccountabilityTexts.conflict(code) ?: "$code: ${op.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline) }
            }
        }
        if (row.returned && access?.dailyReport == true) {
            Section(null) { ActionRow(T.RESUBMIT, R.drawable.ic_clipboard) { onRoute(Route.DailyReportForm(row.machineId, row.key)) } }
        }
    }
}
