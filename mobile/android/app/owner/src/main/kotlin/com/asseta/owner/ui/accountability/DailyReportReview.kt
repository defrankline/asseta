package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.model.owner.DailyReportReviewIn
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

private val T = AllocationTexts
private val R = RevenuePresentation

/** Pure rows of the review screen (unit-tested). */
object DailyReportPresentation {
    fun figures(r: DailyReportDto, zone: ZoneId): List<Pair<String, String>> = buildList {
        add(T.MACHINE to R.machine(r.machineCode, r.machineName, r.machineId))
        add(T.DAY to R.day(r.reportDate))
        add(T.OPENING to R.num(r.openingReading))
        add(T.CLOSING to R.num(r.closingReading))
        add(T.TOTAL to R.hours(r.totalHours))
        add(T.BILLABLE to R.hours(r.billableHours))
        add(T.UNBILLABLE to R.hours(r.unbillableHours))
        if (R.nonZero(r.differenceHours)) add(T.NOT_ACCOUNTED to R.hours(r.differenceHours))
        add(T.SUBMITTED_BY to DisplayNames.of(r.submittedByName, r.submittedBy).orEmpty())
        add(T.SUBMITTED to OwnerFormat.dateTime(r.submittedAt, zone))
    }

    fun flags(r: DailyReportDto): List<String> = listOfNotNull(
        T.FLAG_LATE.takeIf { r.isLate }, T.FLAG_REPEAT.takeIf { r.isDuplicate }, T.REPLACES.takeIf { r.supersedesId != null },
    )

    fun canReview(r: DailyReportDto) = r.status == DailyReportDto.SUBMITTED

    fun isOwn(r: DailyReportDto, userId: String?) = userId != null && r.submittedBy == userId
}

class DailyReportReviewViewModel(val data: OwnerData, val id: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<DailyReportDto>({ data.dailyReport(id) }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun review(decision: String, note: String) {
        if (_busy.value || !R.noteValid(note)) return
        _busy.value = true
        _error.value = null
        _message.value = null
        viewModelScope.launch {
            when (val r = data.reviewDailyReport(id, decision, note)) {
                is ActionResult.Done -> {
                    replaceData { r.value }
                    _message.value = if (decision == DailyReportReviewIn.REVIEWED) T.REVIEWED else T.SENT_BACK
                }
                is ActionResult.Refused -> {
                    _error.value = T.error(r.code, r.error.message)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun DailyReportReviewScreen(vm: DailyReportReviewViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var note by rememberSaveable { mutableStateOf("") }
    SnapshotScaffold(state, vm::refresh) { r ->
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(T.FIGURES) {
                    DailyReportPresentation.figures(r, zone).forEach { (l, v) -> KeyValue(l, v) }
                    LabeledValue(T.STATUS) { StatusPill(T.status(r.status), if (r.status == DailyReportDto.RETURNED) OwnerColors.Warning else OwnerColors.Live) }
                    DailyReportPresentation.flags(r).forEach { Text(it, color = OwnerColors.Warning, style = MaterialTheme.typography.bodySmall) }
                }
            }
            if (r.unbillable.isNotEmpty()) item {
                SectionCard(T.REASONS) { r.unbillable.forEach { KeyValue(it.reasonName ?: DisplayNames.shortId(it.reasonId).orEmpty(), R.hours(it.hours)) } }
            }
            if (r.allocations.isNotEmpty()) item {
                SectionCard(T.ALLOCATIONS) {
                    r.allocations.forEach { a -> KeyValue(listOfNotNull(T.kind(a.kind), AllocationPresentation.who(a)).joinToString(" · "), R.hours(a.hours)) }
                }
            }
            r.note?.takeIf { it.isNotBlank() }?.let { n -> item { SectionCard(T.NOTE) { Text(n) } } }
            if (r.evidenceAttachmentIds.isNotEmpty()) item {
                SectionCard(T.EVIDENCE) {
                    r.evidenceAttachmentIds.forEach { id -> EvidencePhoto("evidence photo", online && !state.stale) { vm.data.attachmentUrl(id) } }
                }
            }
            if (r.reviewedBy != null) item {
                SectionCard(T.REVIEW) {
                    KeyValue(T.REVIEWED_BY, DisplayNames.of(r.reviewedByName, r.reviewedBy).orEmpty())
                    r.reviewNote?.let { KeyValue(T.REVIEW_NOTE, it) }
                }
            }
            if (DailyReportPresentation.canReview(r) && session.features.reviewExceptions) item {
                SectionCard(T.REVIEW, footer = T.REVIEW_FOOTER) {
                    val gate = session.can(OwnerAction.REVIEW_DAILY_REPORT, online, state.snapshot?.source)
                    val own = DailyReportPresentation.isOwn(r, session.userId)
                    when {
                        gate is MutationCheck.Blocked -> BlockedNote(gate.reason)
                        own -> BlockedNote(T.OWN)
                        else -> {
                            OutlinedTextField(note, { note = it.take(2000) }, Modifier.fillMaxWidth().testTag("report-note"), label = { Text(T.NOTE_LABEL) }, minLines = 2)
                            val ready = !busy && R.noteValid(note)
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Button(
                                    { vm.review(DailyReportReviewIn.REVIEWED, note) }, enabled = ready, modifier = Modifier.testTag("report-reviewed"),
                                    colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White), shape = RoundedCornerShape(8.dp),
                                ) { Text(T.MARK_REVIEWED) }
                                Spacer(Modifier.weight(1f))
                                Button(
                                    { vm.review(DailyReportReviewIn.RETURNED, note) }, enabled = ready, modifier = Modifier.testTag("report-return"),
                                    colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Warning.copy(alpha = 0.15f), contentColor = OwnerColors.Warning), shape = RoundedCornerShape(8.dp),
                                ) { Text(T.SEND_BACK) }
                            }
                            error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Assertive }) }
                        }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}
