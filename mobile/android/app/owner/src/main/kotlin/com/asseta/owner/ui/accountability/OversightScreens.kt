package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AmountByCurrencyDto
import com.asseta.core.model.owner.IdleMachineDto
import com.asseta.core.model.owner.ScorecardDetailDto
import com.asseta.core.model.owner.ScorecardRecordDto
import com.asseta.core.model.owner.ScorecardRowDto
import com.asseta.core.model.owner.UnbilledJobDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import java.time.LocalDate
import java.time.ZoneId

/** Wording of the oversight screens (DEC-031 Phase 5; keys `owner.score.*`, `owner.dash.*`, `owner.unbilled.*`, `owner.idle.*`). */
object OversightTexts {
    const val SCORE_MORE = "People scorecard"
    const val SCORE_TITLE = "People scorecard"
    const val SCORE_EMPTY = "No one to show for this period."
    const val SCORE_FOOTER = "Counts of items to look at for each person, most first. A count is not a verdict: open the person to see each record."
    const val SCORE_INACTIVE = "Inactive"
    const val SCORE_FIGURES = "Figures"
    const val SCORE_PERIOD = "Period"
    const val SCORE_MACHINES = "Machines responsible for"
    const val SCORE_REPORTS_MISSING = "Daily reports missing"
    const val SCORE_REPORTS_LATE = "Daily reports late"
    const val SCORE_UNEXPLAINED = "Unexplained engine hours"
    const val SCORE_ALERTS = "Alerts"
    const val SCORE_ACK_TIME = "Time to acknowledge"
    const val SCORE_CASH_HELD_TOO_LONG = "Cash held too long"
    const val SCORE_CASH_DIFFERENCES = "Cash differences"
    const val SCORE_NEAR_THRESHOLD = "Near the case threshold"
    const val SCORE_REVENUE_DIFFERENCES = "Revenue differences"
    const val SCORE_REFUSED = "Refused attempts"
    const val SCORE_CHECKINS = "Site check-ins"
    const val SCORE_PATTERNS = "Repeated patterns"
    const val SCORE_CASH_HELD = "Cash held now"
    const val SCORE_RECORDS = "Records"
    const val SCORE_RECORDS_EMPTY = "No records in this period."

    const val DASH_UNBILLED = "Unbilled work"
    const val DASH_UNBILLED_JOBS = "Jobs"
    const val DASH_UNBILLED_VALUE = "Value"
    const val DASH_OLDEST = "Oldest"
    const val DASH_IDLE = "Idle machines"
    const val DASH_IDLE_MACHINES = "Machines"
    const val DASH_LONGEST_IDLE = "Longest idle"
    const val DASH_NONE = "None"

    const val UNBILLED_TITLE = "Unbilled work"
    const val UNBILLED_EMPTY = "No completed jobs waiting for an invoice."
    const val UNBILLED_DRAFT = "On a draft invoice"
    const val UNBILLED_FOOTER = "Completed jobs not on an issued invoice yet. Invoices are made on the web."
    const val IDLE_TITLE = "Idle machines"
    const val IDLE_EMPTY = "No idle machines."
    const val IDLE_FOOTER = "Machines with no running job and no engine hours for a while."

    fun days(n: Int): String = if (n == 1) "1 day" else "$n days"

    fun items(n: Int): String = when (n) {
        0 -> "Nothing to look at"
        1 -> "1 item to look at"
        else -> "$n items to look at"
    }

    fun unexplainedValue(hours: String, n: Int) = "$hours h · $n items"
    fun alertsValue(n: Int, open: Int) = "$n · $open open"
    fun ackTimeValue(avg: String, max: String) = "average $avg h · longest $max h"
    fun checkinsValue(made: Int, missed: Int) = "$made made · $missed missed"
    fun heldSince(date: String, days: Int?) = "since $date" + (days?.let { " (${days(it)})" } ?: "")
    fun scheduled(time: String) = "Scheduled $time"
    fun unbilledFooter(days: Int) = "Completed jobs not on an issued invoice after ${days(days)}."
    fun idleFooter(days: Int) = "Machines with no running job and no engine hours for ${days(days)}."
    fun unbilledRow(job: String, customer: String) = "$job · $customer"
    fun unbilledCompleted(date: String, days: Int) = "Completed $date · ${days(days)} unbilled"
    fun idleSince(date: String, days: Int) = "Idle since $date (${days(days)})"
    fun idleLastJob(job: String, date: String) = "Last job $job completed $date"
    fun idlePlanned(job: String) = "Planned job $job"

    fun item(code: String): String = when (code) {
        "MISSING_DAILY_REPORT" -> "Daily report missing"
        "LATE_DAILY_REPORT" -> "Daily report late"
        "UNEXPLAINED_HOURS" -> "Unexplained engine hours"
        "ALERT" -> "Alert"
        "CASH_HELD_TOO_LONG" -> "Cash held too long"
        "CASH_DIFFERENCE" -> "Cash difference"
        "REVENUE_DIFFERENCE" -> "Revenue difference"
        "REFUSED_ATTEMPT" -> "Refused attempt"
        "MISSED_CHECKIN" -> "Missed site check-in"
        "PATTERN_SIGNAL" -> "Repeated pattern"
        else -> OwnerFormat.humanize(code)
    }
}

/** Scorecard period chips (owner.score.period.*): local days, at most 93. */
enum class ScorecardPeriod(val label: String) {
    LAST_7_DAYS("Last 7 days"),
    LAST_30_DAYS("Last 30 days"),
    THIS_MONTH("This month"),
    LAST_MONTH("Last month"),
    ;

    fun range(today: LocalDate): Pair<LocalDate, LocalDate> = when (this) {
        LAST_7_DAYS -> today.minusDays(6) to today
        LAST_30_DAYS -> today.minusDays(29) to today
        THIS_MONTH -> today.withDayOfMonth(1) to today
        LAST_MONTH -> today.withDayOfMonth(1).minusMonths(1).let { it to it.withDayOfMonth(it.lengthOfMonth()) }
    }
}

/** One list row: headline, subtitle, caption, trailing value, and what it opens (null: nothing). */
data class OversightRow(val key: String, val title: String, val subtitle: String?, val caption: String?, val value: String?, val open: OwnerDestination?)

/** Pure presentation of the scorecard, unbilled work, idle machines and their dashboard tiles (unit-tested; same rules as iOS). */
object OversightPresentation {
    private val T = OversightTexts

    private fun hours(raw: String?) = OwnerFormat.hoursNumber(raw)
    private fun money(amount: String?, currency: String?) = RevenuePresentation.money(amount, currency.orEmpty())
    private fun totals(list: List<AmountByCurrencyDto>) = list.joinToString(", ") { money(it.amount, it.currency) }

    fun name(r: ScorecardRowDto): String = DisplayNames.of(r.staffMemberName, r.staffMemberId).orEmpty()

    /** Most items first, then by name. */
    fun sorted(rows: List<ScorecardRowDto>): List<ScorecardRowDto> =
        rows.sortedWith(compareByDescending<ScorecardRowDto> { it.itemsTotal }.thenBy { name(it).lowercase() })

    /** The first three non-zero figures of a person, for the list row. */
    fun figures(r: ScorecardRowDto): String? = listOfNotNull(
        "${r.dailyReportsMissing} missing reports".takeIf { r.dailyReportsMissing > 0 },
        "${r.dailyReportsLate} late reports".takeIf { r.dailyReportsLate > 0 },
        "${hours(r.unexplainedHours)} h unexplained".takeIf { RevenuePresentation.nonZero(r.unexplainedHours) },
        "${r.alertsOpen} open alerts".takeIf { r.alertsOpen > 0 },
        "${r.cashHeldTooLong} cash held too long".takeIf { r.cashHeldTooLong > 0 },
        "${r.cashDifferences} cash differences".takeIf { r.cashDifferences > 0 },
        "${r.revenueDifferences} revenue differences".takeIf { r.revenueDifferences > 0 },
        "${r.refusedAttempts} refused attempts".takeIf { r.refusedAttempts > 0 },
        "${r.checkinsMissed} missed check-ins".takeIf { (r.checkinsMissed ?: 0) > 0 },
        "${r.patternSignals} repeated patterns".takeIf { r.patternSignals > 0 },
    ).take(3).joinToString(" · ").ifEmpty { null }

    fun rows(list: List<ScorecardRowDto>, from: LocalDate, to: LocalDate): List<OversightRow> = sorted(list).map { r ->
        OversightRow(
            r.staffMemberId, name(r),
            listOfNotNull(T.items(r.itemsTotal), T.SCORE_INACTIVE.takeIf { !r.isActive }).joinToString(" · "),
            figures(r), null, OwnerDestination.ScorecardPerson(r.staffMemberId, r.staffMemberName, from.toString(), to.toString()),
        )
    }

    /** Figures card rows in the documented order. */
    fun figureRows(r: ScorecardRowDto): List<Pair<String, String>> = buildList {
        add(T.SCORE_PERIOD to HoursPresentation.period(r.dayFrom, r.dayTo))
        add(T.SCORE_MACHINES to "${r.machines}")
        add(T.SCORE_REPORTS_MISSING to "${r.dailyReportsMissing}")
        add(T.SCORE_REPORTS_LATE to "${r.dailyReportsLate}")
        add(T.SCORE_UNEXPLAINED to T.unexplainedValue(hours(r.unexplainedHours), r.unexplainedItems))
        add(T.SCORE_ALERTS to T.alertsValue(r.alerts, r.alertsOpen))
        r.avgHoursToAcknowledge?.let { add(T.SCORE_ACK_TIME to T.ackTimeValue(hours(it), hours(r.maxHoursToAcknowledge ?: it))) }
        add(T.SCORE_CASH_HELD_TOO_LONG to "${r.cashHeldTooLong}")
        add(T.SCORE_CASH_DIFFERENCES to (listOf("${r.cashDifferences}") + listOfNotNull(totals(r.cashDifferenceTotals).ifEmpty { null })).joinToString(" · "))
        if (r.cashDifferencesNearThreshold > 0) add(T.SCORE_NEAR_THRESHOLD to "${r.cashDifferencesNearThreshold}")
        add(T.SCORE_REVENUE_DIFFERENCES to (listOf("${r.revenueDifferences}") + listOfNotNull(totals(r.revenueDifferenceTotals).ifEmpty { null })).joinToString(" · "))
        add(T.SCORE_REFUSED to "${r.refusedAttempts}")
        r.checkinsMissed?.let { add(T.SCORE_CHECKINS to T.checkinsValue(r.checkinsMade, it)) }
        add(T.SCORE_PATTERNS to "${r.patternSignals}")
    }

    /** Cash held now: money -> since when. */
    fun cashHeld(r: ScorecardRowDto, zone: ZoneId): List<Pair<String, String>> = r.cashHeld.map { c ->
        money(c.amount, c.currency) to (c.heldSince?.let { T.heldSince(OwnerFormat.date(it, zone), c.heldDays) } ?: "")
    }

    private fun JsonObject.text(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull

    /** The screen a record opens, when the app has one and the role may open it. */
    fun destination(r: ScorecardRecordDto, f: OwnerFeatures): OwnerDestination? {
        val id = r.recordId
        return when (r.recordType) {
            "job_exception" -> id?.takeIf { f.meterEvidence }?.let { OwnerDestination.MeterException(it) }
            "tracking_alert" -> id?.takeIf { f.fleet }?.let { OwnerDestination.Alerts(it) }
            "cash_remittance_overdue" -> id?.takeIf { f.finance && f.cashCustody }?.let { OwnerDestination.RemittanceOverdue(it) }
            "cash_variance" -> id?.takeIf { DecisionKind.WRITE_OFF.visibleTo(f) }?.let { OwnerDestination.Decision(DecisionKinds.WRITE_OFF, it) }
            "revenue_difference" -> id?.takeIf { f.revenueRead }?.let { OwnerDestination.Decision(DecisionKinds.REVENUE_DIFFERENCE, it) }
            "risk_signal" -> r.detail.text("case_id")?.takeIf { f.cases }?.let { OwnerDestination.Case(it) }
            "engine_interval" -> r.machineId?.takeIf { f.fleet }?.let { OwnerDestination.Machine(it) }
            else -> null
        }
    }

    /** Record rows, newest first: label item wording, value money or hours, caption day · machine · job · status · details. */
    fun records(d: ScorecardDetailDto, f: OwnerFeatures, zone: ZoneId): List<OversightRow> = d.records.sortedByDescending { it.at }.mapIndexed { i, r ->
        val value = when {
            r.amount != null -> money(r.amount, r.currency)
            r.hours != null -> "${hours(r.hours)} h"
            else -> null
        }
        val details = when (r.item) {
            "ALERT" -> listOfNotNull(r.detail.text("title"))
            "MISSED_CHECKIN" -> listOfNotNull(r.detail.text("scheduled_at")?.let { OwnerFormat.parseInstant(it) }?.let { T.scheduled(OwnerFormat.time(it, zone)) })
            "REFUSED_ATTEMPT" -> listOfNotNull(r.detail.text("action"), r.detail.text("permission"))
            else -> emptyList()
        }
        val machine = DisplayNames.machine(r.machineCode, r.machineName, null)
        val caption = listOfNotNull(
            r.day?.let(RevenuePresentation::day) ?: OwnerFormat.date(r.at, zone),
            machine, r.jobNumber, r.status?.let(OwnerFormat::humanize), T.SCORE_NEAR_THRESHOLD.takeIf { r.nearThreshold },
        ) + details
        OversightRow("${r.recordType}-${r.recordId ?: i}-$i", T.item(r.item), null, caption.joinToString(" · "), value, destination(r, f))
    }

    // --- unbilled work, idle machines ---------------------------------------------------------------------------

    fun unbilled(list: List<UnbilledJobDto>, f: OwnerFeatures, zone: ZoneId): List<OversightRow> = list.sortedByDescending { it.daysUnbilled }.map { j ->
        val machine = RevenuePresentation.machine(j.machineCode, j.machineName, j.machineId)
        OversightRow(
            j.jobId,
            T.unbilledRow(j.jobNumber ?: "—", DisplayNames.of(j.customerName, j.customerId).orEmpty()),
            listOfNotNull(machine, j.jobSiteName).joinToString(" · "),
            T.unbilledCompleted(OwnerFormat.date(j.completedAt, zone), j.daysUnbilled) + if (j.draftInvoiceId != null) " · " + T.UNBILLED_DRAFT else "",
            j.total?.let { money(it, j.currency) },
            OwnerDestination.Job(j.jobId).takeIf { f.jobs },
        )
    }

    fun idle(list: List<IdleMachineDto>, f: OwnerFeatures, zone: ZoneId): List<OversightRow> = list.sortedByDescending { it.idleDays }.map { m ->
        OversightRow(
            m.machineId,
            RevenuePresentation.machine(m.machineCode, m.machineName, m.machineId),
            T.idleSince(OwnerFormat.date(m.idleSince, zone), m.idleDays),
            listOfNotNull(
                m.lastJobId?.let { T.idleLastJob(m.lastJobNumber ?: "—", OwnerFormat.date(m.lastJobCompletedAt, zone)) },
                m.plannedJobId?.let { T.idlePlanned(m.plannedJobNumber ?: "—") },
            ).joinToString(" · ").ifEmpty { null },
            null,
            OwnerDestination.Machine(m.machineId).takeIf { f.fleet },
        )
    }

    // --- dashboard tiles ------------------------------------------------------------------------------------------

    private fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.intOrNull

    fun unbilledTile(t: JsonObject, f: OwnerFeatures): DashboardTile? {
        if (TenantAccess.UNBILLED_WORK in f.disabled) return null
        val amounts = (t["amounts"] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }.map { money(it.text("amount"), it.text("currency")) }
        return DashboardTile(
            "unbilled_work", T.DASH_UNBILLED,
            listOfNotNull(
                T.DASH_UNBILLED_JOBS to "${t.int("count") ?: 0}",
                T.DASH_UNBILLED_VALUE to (amounts.joinToString(", ").ifEmpty { T.DASH_NONE }),
                t.int("oldest_days")?.let { T.DASH_OLDEST to T.days(it) },
            ),
            OwnerDestination.UnbilledWork.takeIf { f.unbilledWork },
            footer = t.int("after_days")?.let(T::unbilledFooter),
        )
    }

    fun idleTile(t: JsonObject, f: OwnerFeatures): DashboardTile? {
        if (TenantAccess.IDLE_MACHINES in f.disabled) return null
        return DashboardTile(
            "idle_machines", T.DASH_IDLE,
            listOfNotNull(
                T.DASH_IDLE_MACHINES to "${t.int("count") ?: 0}",
                t.int("longest_idle_days")?.let { T.DASH_LONGEST_IDLE to T.days(it) },
            ),
            OwnerDestination.IdleMachines.takeIf { f.idleMachines },
            footer = t.int("after_days")?.let(T::idleFooter),
        )
    }
}

// --- view models -------------------------------------------------------------------------------------------------------

class ScorecardViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<ScorecardPeriod>,
    private val today: () -> LocalDate,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<List<ScorecardRowDto>>({ selected.value.range(today()).let { (f, t) -> data.scorecard(f, t) } }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) :
        this(data, MutableStateFlow(ScorecardPeriod.LAST_30_DAYS), today, refreshOn)

    val period: StateFlow<ScorecardPeriod> get() = selected

    fun range(): Pair<LocalDate, LocalDate> = selected.value.range(today())

    fun select(p: ScorecardPeriod) {
        if (selected.value == p) return
        selected.value = p
        refresh()
    }
}

class ScorecardPersonViewModel(data: OwnerData, staffId: String, from: LocalDate, to: LocalDate, refreshOn: Flow<Unit>) :
    SnapshotViewModel<ScorecardDetailDto>({ data.scorecardPerson(staffId, from, to) }, refreshOn)

class UnbilledWorkViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<List<UnbilledJobDto>>({ data.unbilledWork() }, refreshOn)

class IdleMachinesViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<List<IdleMachineDto>>({ data.idleMachines() }, refreshOn)

// --- screens ---------------------------------------------------------------------------------------------------------

@Composable
private fun RowContent(r: OversightRow) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(r.title, style = AssetaType.headline, modifier = Modifier.weight(1f))
            r.value?.let { Text(it, style = AssetaType.subheadline) }
        }
        r.subtitle?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.subheadline, color = palette.secondaryText) }
        r.caption?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}

private fun items(rows: List<OversightRow>, onOpen: (OwnerDestination) -> Unit): List<GroupedItem> =
    rows.map { r -> GroupedItem(r.key, onClick = r.open?.let { d -> { onOpen(d) } }) { RowContent(r) } }

@Composable
fun ScorecardScreen(vm: ScorecardViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val period by vm.period.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(ScorecardPeriod.entries.map { it to it.label }, period, vm::select)
        SnapshotScaffold(state, vm::refresh) { list ->
            val (from, to) = vm.range()
            val rows = OversightPresentation.rows(list, from, to)
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                if (rows.isEmpty()) {
                    item { EmptyState(OversightTexts.SCORE_EMPTY) }
                    return@LazyColumn
                }
                groupedSection(keyPrefix = "score", header = null, footer = OversightTexts.SCORE_FOOTER, items = items(rows, onOpen))
            }
        }
    }
}

@Composable
fun ScorecardPersonScreen(vm: ScorecardPersonViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val zone = ZoneId.systemDefault()
        val records = OversightPresentation.records(d, features, zone)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(OversightTexts.SCORE_FIGURES) {
                    Text(OversightPresentation.name(d.row), style = AssetaType.headline)
                    OversightPresentation.figureRows(d.row).forEach { (l, v) -> KeyValue(l, v) }
                }
            }
            val held = OversightPresentation.cashHeld(d.row, zone)
            if (held.isNotEmpty()) item { SectionCard(OversightTexts.SCORE_CASH_HELD) { held.forEach { (l, v) -> KeyValue(l, v) } } }
            if (records.isEmpty()) {
                item { SectionCard(OversightTexts.SCORE_RECORDS) { Text(OversightTexts.SCORE_RECORDS_EMPTY, color = palette.secondaryText) } }
            } else {
                groupedSection(keyPrefix = "records", header = OversightTexts.SCORE_RECORDS, items = items(records, onOpen))
            }
        }
    }
}

@Composable
fun UnbilledWorkScreen(vm: UnbilledWorkViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { list ->
        val rows = OversightPresentation.unbilled(list, features, ZoneId.systemDefault())
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (rows.isEmpty()) {
                item { EmptyState(OversightTexts.UNBILLED_EMPTY) }
                return@LazyColumn
            }
            groupedSection(keyPrefix = "unbilled", header = null, footer = OversightTexts.UNBILLED_FOOTER, items = items(rows, onOpen))
        }
    }
}

@Composable
fun IdleMachinesScreen(vm: IdleMachinesViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { list ->
        val rows = OversightPresentation.idle(list, features, ZoneId.systemDefault())
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (rows.isEmpty()) {
                item { EmptyState(OversightTexts.IDLE_EMPTY) }
                return@LazyColumn
            }
            groupedSection(keyPrefix = "idle", header = null, footer = OversightTexts.IDLE_FOOTER, items = items(rows, onOpen))
        }
    }
}
