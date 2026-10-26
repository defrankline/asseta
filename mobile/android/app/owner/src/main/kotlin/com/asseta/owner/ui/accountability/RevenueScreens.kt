package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.DailyMachineSheetDetailDto
import com.asseta.core.model.owner.DailyMachineSheetRowDto
import com.asseta.core.model.owner.RevenueDecisionIn
import com.asseta.core.model.owner.RevenueDifferenceDto
import com.asseta.core.model.owner.RevenueReasonDto
import com.asseta.core.model.owner.SheetMoneyDto
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.approvals.DecisionError
import com.asseta.owner.ui.approvals.SegregationNotice
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val T = OwnerAccountabilityTexts

/** What the signed-in user may do on a revenue difference now (the server re-checks everything). */
data class RevenueActions(
    /** Explain form (OPEN, explain holder). */
    val explain: Boolean,
    /** Approve / reject the proposed explanation (decide holder). */
    val approveReject: Boolean,
    /** Confirm the difference as real (decide holder, OPEN or proposed). */
    val confirm: Boolean,
    /** The user explained it, so someone else decides (decision buttons disabled). */
    val own: Boolean,
) {
    val decide: Boolean get() = approveReject || confirm
}

/** Pure presentation of revenue differences, the dashboard tile and the daily machine sheet (unit-tested). */
object RevenuePresentation {
    private val DAY = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.US)

    /** "2026-10-26" -> "26 Oct 2026" (unparseable input as is). */
    fun day(raw: String): String = runCatching { DAY.format(LocalDate.parse(raw.take(10))) }.getOrDefault(raw)

    fun money(amount: String?, currency: String): String =
        amount?.toBigDecimalOrNull()?.let { OwnerFormat.money(it, currency) } ?: "${amount.orEmpty()} $currency"

    /** "2.5" (no unit; the texts add " h"). */
    fun num(raw: String?): String = raw?.toBigDecimalOrNull()?.let { OwnerFormat.decimal(it.setScale(2, java.math.RoundingMode.HALF_EVEN)) } ?: (raw ?: "0")

    fun hours(raw: String?): String = "${num(raw)} h"

    fun nonZero(raw: String?): Boolean = (raw?.toBigDecimalOrNull() ?: BigDecimal.ZERO).signum() != 0

    fun machine(code: String?, name: String?, id: String): String = DisplayNames.machine(code, name, id).orEmpty()

    fun actions(d: RevenueDifferenceDto, features: OwnerFeatures, userId: String?): RevenueActions {
        val proposed = d.status == RevenueDifferenceDto.EXPLANATION_PROPOSED
        val open = d.status == RevenueDifferenceDto.OPEN
        return RevenueActions(
            explain = open && features.revenueExplain,
            approveReject = proposed && features.revenueDecide,
            confirm = (open || proposed) && features.revenueDecide,
            own = userId != null && d.explainedBy == userId,
        )
    }

    /** A note of at least 5 characters (server `Note`) for every explanation and decision. */
    fun noteValid(note: String): Boolean = note.trim().length >= DecisionMapper.METER_NOTE_MIN

    /** Figures card rows, in the documented order (zero-only rows left out). */
    fun figures(d: RevenueDifferenceDto): List<Pair<String, String>> = buildList {
        val c = d.currency
        add(T.REV_MACHINE to machine(d.machineCode, d.machineName, d.machineId))
        add(T.REV_PERIOD to DecisionMapper.period(d.localFrom, d.localTo))
        d.jobId?.let { add(T.REV_JOB to DisplayNames.of(d.jobNumber, it).orEmpty()) }
        add(T.REV_EXPECTED to money(d.expectedAmount, c))
        if (nonZero(d.inProgressAmount)) add(T.REV_IN_PROGRESS to money(d.inProgressAmount, c))
        add(T.REV_ATTRIBUTED to money(d.attributedAmount, c))
        add(T.REV_DIFFERENCE to money(d.difference, c))
        d.adjustedDifference?.let { add(T.REV_ADJUSTED_DIFFERENCE to money(it, c)) }
        add(T.REV_CUSTOMER_WORK to hours(d.customerWorkHours))
        add(T.REV_NON_REVENUE_HOURS to hours(d.nonRevenueHours))
        if (nonZero(d.unexplainedHours)) add(T.REV_UNEXPLAINED_HOURS to hours(d.unexplainedHours))
        if (nonZero(d.unexplainedExpectedAmount)) add(T.REV_UNEXPLAINED_EXPECTED to money(d.unexplainedExpectedAmount, c))
        if (d.caseId != null) add(T.REV_CASE to DisplayNames.of(d.caseNumber, d.caseId).orEmpty())
    }

    private fun JsonObject.text(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull
    private fun JsonObject.flag(key: String): Boolean? = (this[key] as? JsonPrimitive)?.booleanOrNull
    private fun JsonObject.list(key: String): List<JsonObject> = (this[key] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }

    /** Jobs of the difference's currency: (job number, "Expected … · Attributed …[ · In progress …]"). */
    fun jobs(d: RevenueDifferenceDto): List<Pair<String, String>> = d.detail.list("jobs").filter { (it.text("currency") ?: d.currency) == d.currency }.map { j ->
        val c = d.currency
        val line = T.revJobLine(money(j.text("expected"), c), money(j.text("attributed"), c)) +
            (j.text("in_progress")?.takeIf(::nonZero)?.let { " · " + T.revJobInProgress(money(it, c)) } ?: "")
        DisplayNames.of(j.text("job_number"), j.text("job_id")).orEmpty() to line
    }

    /** Explanation rows (empty when nobody explained it). */
    fun explanation(d: RevenueDifferenceDto, zone: ZoneId): List<Pair<String, String>> {
        if (d.reasonId == null && d.explainedBy == null) return emptyList()
        return listOfNotNull(
            d.reasonName?.let { T.REV_REASON to it },
            d.explanationNote?.takeIf { it.isNotBlank() }?.let { T.REV_NOTE to it },
            d.explainedBy?.let { T.REV_EXPLAINED_BY to DisplayNames.of(d.explainedByName, it).orEmpty() },
            d.explainedAt?.let { T.REV_EXPLAINED to OwnerFormat.dateTime(it, zone) },
        )
    }

    fun decided(d: RevenueDifferenceDto): List<Pair<String, String>> = listOfNotNull(
        d.decidedBy?.let { T.REV_DECIDED_BY to DisplayNames.of(d.decidedByName, it).orEmpty() },
        d.decisionNote?.takeIf { it.isNotBlank() && d.decidedBy != null }?.let { T.REV_DECISION_NOTE to it },
    )

    /** Adjustment lines, newest first. */
    fun adjustments(d: RevenueDifferenceDto, zone: ZoneId): List<String> = d.adjustments.sortedByDescending { it.createdAt }.map {
        T.revAdjustmentLine(OwnerFormat.date(it.createdAt, zone), money(it.previousDifference, d.currency), money(it.newDifference, d.currency))
    }

    /** The dashboard tile `revenue_differences` (server-defined object) as rows, or null when absent. */
    fun tile(t: JsonObject?): DashboardTile? {
        t ?: return null
        val amounts = t.list("amounts").mapNotNull { a ->
            val currency = a.text("currency") ?: return@mapNotNull null
            T.count(a.text("count")?.toIntOrNull() ?: 0, money(a.text("amount"), currency))
        }
        val rows = buildList {
            add(T.DASH_REV_TO_EXPLAIN to (t.text("open") ?: "0"))
            add(T.DASH_REV_AWAITING to (t.text("awaiting_decision") ?: "0"))
            add(T.DASH_REV_AMOUNTS to (amounts.joinToString(", ").ifEmpty { T.DASH_NONE }))
            t.text("oldest_open_days")?.toIntOrNull()?.let { add(T.DASH_REV_OLDEST to T.days(it)) }
            add(T.DASH_REV_EXPLAINED to (t.text("explained_in_window") ?: "0"))
            add(T.DASH_REV_CONFIRMED to (t.text("confirmed_in_window") ?: "0"))
            add(T.DASH_REV_CLEARED to (t.text("cleared_in_window") ?: "0"))
            t.list("items").forEach { i ->
                val from = i.text("local_from").orEmpty()
                val to = i.text("local_to") ?: from
                add(T.dashRevItem(i.text("machine_code").orEmpty(), DecisionMapper.period(from, to)) to money(i.text("difference"), i.text("currency").orEmpty()))
            }
        }
        val window = t.text("window_days")?.toIntOrNull()
        return DashboardTile("revenue_differences", T.DASH_REVENUE, rows, OwnerDestination.Approvals(), footer = window?.let(T::window))
    }

    // --- daily machine sheet ---------------------------------------------------------------------------------------
    /** Days of the list: the last [days] local days up to [today] (today included). */
    fun window(today: LocalDate, days: Long = SHEET_DAYS): Pair<LocalDate, LocalDate> = today.minusDays(days - 1) to today

    const val SHEET_DAYS = 14L

    /** List row lines under the day: hours, differences per currency, flags. */
    fun rowLines(r: DailyMachineSheetRowDto): List<String> = listOf(T.sheetRowHours(num(r.engineHours), num(r.revenueHours))) +
        r.money.filter { nonZero(it.difference) }.map { T.sheetRowDifference(money(it.difference, it.currency)) }

    fun flags(flags: List<String>): String? = flags.takeIf { it.isNotEmpty() }?.joinToString(" · ", transform = T::sheetFlag)

    /** Hours card rows: Engine and Revenue always, the others when non-zero; each non-revenue type on its own row. */
    fun hoursRows(d: DailyMachineSheetDetailDto): List<Pair<String, String>> = buildList {
        add(T.SHEET_ENGINE to hours(d.engineHours))
        if (nonZero(d.customerWorkHours)) add(T.SHEET_CUSTOMER_WORK to hours(d.customerWorkHours))
        if (nonZero(d.nonRevenueHours)) add(T.SHEET_NON_REVENUE to hours(d.nonRevenueHours))
        d.nonRevenueByType.toSortedMap().forEach { (type, h) -> if (nonZero(h)) add("${T.SHEET_NON_REVENUE} · ${OwnerFormat.humanize(type)}" to hours(h)) }
        if (nonZero(d.nonRevenuePendingHours)) add(T.SHEET_NON_REVENUE_PENDING to hours(d.nonRevenuePendingHours))
        add(T.SHEET_REVENUE to hours(d.revenueHours))
        if (nonZero(d.approvedNonCustomerHours)) add(T.SHEET_APPROVED_NON_CUSTOMER to hours(d.approvedNonCustomerHours))
        if (nonZero(d.identifiedVarianceHours)) add(T.SHEET_IDENTIFIED_VARIANCE to hours(d.identifiedVarianceHours))
        if (nonZero(d.unexplainedHours)) add(T.SHEET_UNEXPLAINED to hours(d.unexplainedHours))
        if (nonZero(d.pendingReviewHours)) add(T.SHEET_PENDING_REVIEW to hours(d.pendingReviewHours))
    }

    fun moneyRows(m: SheetMoneyDto): List<Pair<String, String>> = buildList {
        add(T.REV_EXPECTED to money(m.expected, m.currency))
        if (nonZero(m.inProgress)) add(T.REV_IN_PROGRESS to money(m.inProgress, m.currency))
        add(T.REV_ATTRIBUTED to money(m.attributed, m.currency))
        add(T.REV_DIFFERENCE to money(m.difference, m.currency))
        if (nonZero(m.unexplainedExpected)) add(T.REV_UNEXPLAINED_EXPECTED to money(m.unexplainedExpected, m.currency))
    }

    fun readingRows(d: DailyMachineSheetDetailDto, zone: ZoneId): List<Pair<String, String>> = buildList {
        d.firstReading?.let { add(T.SHEET_FIRST_READING to num(it)) }
        d.lastReading?.let { add(T.SHEET_LAST_READING to num(it)) }
        add(T.SHEET_READING_COUNT to "${d.readingCount}")
        d.readings.sortedBy { it.capturedAt }.forEach { r ->
            val at = OwnerFormat.parseInstant(r.capturedAt)?.let { OwnerFormat.time(it, zone) } ?: r.capturedAt
            add("$at · ${num(r.reading)}" to OwnerFormat.humanize(r.kind))
        }
    }

    fun jobRows(d: DailyMachineSheetDetailDto): List<Pair<String, String>> = d.jobs.map { j ->
        listOfNotNull(DisplayNames.of(j.jobNumber, j.jobId), j.customerName).joinToString(" · ") to hours(j.customerWorkHours)
    }
}

// --- revenue difference ----------------------------------------------------------------------------------------------

/** One revenue difference (by id: the exact record a notification names) with explain and decide. */
class RevenueDifferenceViewModel(
    val data: OwnerData,
    val id: String,
    loadReasons: Boolean,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<RevenueDifferenceDto>({ data.revenueDifference(id) }, refreshOn) {
    /** Active reasons for the explain picker (only loaded for explain holders). */
    val reasons: Section<List<RevenueReasonDto>>? = if (loadReasons) Section(viewModelScope) { data.revenueReasons() } else null
    private val _error = MutableStateFlow<DecisionError?>(null)
    val error: StateFlow<DecisionError?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    init {
        reasons?.refresh()
    }

    fun explain(reasonId: String?, note: String) {
        if (_busy.value || reasonId == null || !RevenuePresentation.noteValid(note)) return
        send(T.REV_EXPLANATION_SENT) { data.explainRevenue(id, reasonId, note) }
    }

    fun decide(decision: String, note: String) {
        if (_busy.value || !RevenuePresentation.noteValid(note)) return
        val done = when (decision) {
            RevenueDecisionIn.APPROVE -> T.REV_APPROVED
            RevenueDecisionIn.REJECT -> T.REV_REJECTED
            else -> T.REV_CONFIRMED
        }
        send(done) { data.decideRevenue(id, decision, note) }
    }

    private fun send(done: String, call: suspend () -> ActionResult<RevenueDifferenceDto>) {
        _busy.value = true
        _error.value = null
        _message.value = null
        viewModelScope.launch {
            when (val r = call()) {
                is ActionResult.Done -> {
                    replaceData { r.value }
                    _message.value = done
                }
                is ActionResult.Refused -> {
                    _error.value = DecisionError(id, r.error, r.code)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun RevenueDifferenceScreen(vm: RevenueDifferenceViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val reasons = vm.reasons?.state?.collectAsStateWithLifecycle()?.value
    var note by rememberSaveable { mutableStateOf("") }
    var reasonId by rememberSaveable { mutableStateOf<String?>(null) }
    var confirm by rememberSaveable { mutableStateOf<String?>(null) }
    SnapshotScaffold(state, vm::refresh) { d ->
        val zone = ZoneId.systemDefault()
        val actions = RevenuePresentation.actions(d, session.features, session.userId)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(T.REV_FIGURES) {
                    RevenuePresentation.figures(d).forEach { (l, v) -> KeyValue(l, v) }
                    LabeledValue(T.REV_STATUS) { StatusPill(T.revStatus(d.status), revenueColor(d.status)) }
                }
            }
            item {
                SectionCard(T.REV_JOBS) {
                    val jobs = RevenuePresentation.jobs(d)
                    if (jobs.isEmpty()) FootNote(T.REV_NO_JOBS)
                    jobs.forEach { (job, line) -> KeyValue(job, line) }
                }
            }
            val explanation = RevenuePresentation.explanation(d, zone) + RevenuePresentation.decided(d)
            if (explanation.isNotEmpty()) item { SectionCard(T.REV_EXPLANATION) { explanation.forEach { (l, v) -> KeyValue(l, v) } } }
            val adjustments = RevenuePresentation.adjustments(d, zone)
            if (adjustments.isNotEmpty()) item { SectionCard(T.REV_ADJUSTMENTS) { adjustments.forEach { Text(it, style = AssetaType.subheadline) } } }
            if (actions.explain) item {
                SectionCard(T.REV_EXPLAIN, footer = T.REV_EXPLAIN_FOOTER) {
                    val gate = session.can(OwnerAction.EXPLAIN_REVENUE, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        BlockedNote(gate.reason)
                    } else {
                        val list = reasons?.data.orEmpty()
                        Text(T.REV_CHOOSE_REASON, style = MaterialTheme.typography.titleSmall)
                        if (list.isEmpty() && reasons?.loading == false) FootNote(T.REV_REASONS_EMPTY)
                        list.forEach { r -> ReasonOption(r.name, r.id == reasonId) { reasonId = r.id } }
                        OutlinedTextField(
                            note, { note = it.take(2000) }, Modifier.fillMaxWidth().testTag("revenue-note"),
                            label = { Text(T.REV_NOTE_LABEL) }, minLines = 2,
                        )
                        Button(
                            { vm.explain(reasonId, note) },
                            enabled = !busy && reasonId != null && RevenuePresentation.noteValid(note),
                            modifier = Modifier.testTag("revenue-explain"), shape = RoundedCornerShape(8.dp),
                        ) { Text(T.REV_SEND_EXPLANATION) }
                        error?.let { SegregationNotice(it) }
                    }
                }
            }
            if (actions.decide) item {
                SectionCard(T.REV_DECIDE, footer = T.REV_DECIDE_FOOTER) {
                    val gate = session.can(OwnerAction.DECIDE_REVENUE, online, state.snapshot?.source)
                    when {
                        gate is MutationCheck.Blocked -> BlockedNote(gate.reason)
                        actions.own -> BlockedNote(T.REV_OWN_EXPLANATION)
                    }
                    if (gate !is MutationCheck.Blocked) {
                        val ok = !busy && !actions.own && RevenuePresentation.noteValid(note)
                        if (!actions.explain) {
                            OutlinedTextField(
                                note, { note = it.take(2000) }, Modifier.fillMaxWidth().testTag("revenue-decision-note"),
                                label = { Text(T.REV_NOTE_LABEL) }, minLines = 2, enabled = !actions.own,
                            )
                        }
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (actions.approveReject) {
                                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                    Button(
                                        { vm.decide(RevenueDecisionIn.APPROVE, note) }, enabled = ok, modifier = Modifier.testTag("revenue-approve"),
                                        colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                        shape = RoundedCornerShape(8.dp),
                                    ) { Text(T.REV_APPROVE) }
                                    Spacer(Modifier.weight(1f))
                                    Button(
                                        { confirm = RevenueDecisionIn.REJECT }, enabled = ok, modifier = Modifier.testTag("revenue-reject"),
                                        colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                        shape = RoundedCornerShape(8.dp),
                                    ) { Text(T.REV_REJECT) }
                                }
                            }
                            if (actions.confirm) {
                                Button(
                                    { confirm = RevenueDecisionIn.CONFIRM }, enabled = ok, modifier = Modifier.testTag("revenue-confirm"),
                                    colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Warning.copy(alpha = 0.15f), contentColor = OwnerColors.Warning),
                                    shape = RoundedCornerShape(8.dp),
                                ) { Text(T.REV_CONFIRM) }
                            }
                        }
                        if (!actions.explain) error?.let { SegregationNotice(it) }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    confirm?.let { decision ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text(if (decision == RevenueDecisionIn.REJECT) T.REV_CONFIRM_REJECT else T.REV_CONFIRM_CONFIRM) },
            confirmButton = {
                TextButton({ confirm = null; vm.decide(decision, note) }) {
                    Text(if (decision == RevenueDecisionIn.REJECT) T.REV_REJECT else T.REV_CONFIRM, color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton({ confirm = null }) { Text("Cancel") } },
        )
    }
    LaunchedEffect(message) { if (message != null) { note = ""; reasonId = null } }
}

@Composable
private fun ReasonOption(label: String, selected: Boolean, onSelect: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().selectable(selected, role = Role.RadioButton, onClick = onSelect),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null)
        Text(label, style = AssetaType.subheadline, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun revenueColor(status: String): Color = when (status) {
    RevenueDifferenceDto.EXPLAINED, RevenueDifferenceDto.CLEARED -> OwnerColors.Live
    RevenueDifferenceDto.CONFIRMED -> OwnerColors.Critical
    else -> OwnerColors.Warning
}

// --- daily machine sheet -----------------------------------------------------------------------------------------------

/** The last 14 local days of one machine (read-only). */
class DailySheetViewModel(data: OwnerData, val machineId: String, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) :
    SnapshotViewModel<List<DailyMachineSheetRowDto>>({
        val (from, to) = RevenuePresentation.window(today())
        data.dailySheet(machineId, from, to)
    }, refreshOn)

class SheetDayViewModel(data: OwnerData, machineId: String, day: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<DailyMachineSheetDetailDto>({ data.sheetDay(machineId, day) }, refreshOn)

@Composable
fun DailySheetScreen(vm: DailySheetViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { rows ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (rows.isEmpty()) {
                item { EmptyState(T.SHEET_EMPTY) }
                return@LazyColumn
            }
            groupedSection(
                keyPrefix = "sheet", header = null, footer = T.SHEET_FOOTER,
                items = rows.map { r ->
                    GroupedItem(r.day, onClick = { onOpen(OwnerDestination.SheetDay(r.machineId, r.day)) }) {
                        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(RevenuePresentation.day(r.day), style = AssetaType.headline)
                            RevenuePresentation.rowLines(r).forEach { Text(it, style = AssetaType.subheadline, color = palette.secondaryText) }
                            RevenuePresentation.flags(r.flags)?.let { Text(it, style = AssetaType.caption, color = OwnerColors.Warning) }
                        }
                    }
                },
            )
        }
    }
}

@Composable
fun SheetDayScreen(vm: SheetDayViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(T.SHEET_HOURS) {
                    Text(T.sheetDayTitle(RevenuePresentation.machine(d.machineCode, d.machineName, d.machineId), RevenuePresentation.day(d.day)), style = AssetaType.headline)
                    RevenuePresentation.hoursRows(d).forEach { (l, v) -> KeyValue(l, v) }
                }
            }
            item { SectionCard(T.SHEET_READINGS) { RevenuePresentation.readingRows(d, zone).forEach { (l, v) -> KeyValue(l, v) } } }
            if (d.jobs.isNotEmpty()) item { SectionCard(T.REV_JOBS) { RevenuePresentation.jobRows(d).forEach { (l, v) -> KeyValue(l, v) } } }
            d.money.forEach { m ->
                item(key = "money-${m.currency}") { SectionCard(T.sheetMoney(m.currency)) { RevenuePresentation.moneyRows(m).forEach { (l, v) -> KeyValue(l, v) } } }
            }
            item { SectionCard(T.SHEET_FUEL) { KeyValue(T.SHEET_FUEL, T.sheetLitres(RevenuePresentation.num(d.fuelLitres))) } }
            item {
                SectionCard(T.SHEET_FLAGS, footer = T.SHEET_FOOTER) {
                    if (d.flags.isEmpty()) FootNote(T.SHEET_NO_FLAGS)
                    d.flags.forEach { Text(T.sheetFlag(it), style = AssetaType.subheadline, color = OwnerColors.Warning) }
                    Spacer(Modifier.height(2.dp))
                }
            }
        }
    }
}
