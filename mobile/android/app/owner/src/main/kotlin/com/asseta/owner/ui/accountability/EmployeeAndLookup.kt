package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.EmployeeAccountabilityDto
import com.asseta.core.model.owner.EmployeeCashHeldDto
import com.asseta.core.model.owner.EmployeeRecordDto
import com.asseta.core.model.owner.LookupMatchDto
import com.asseta.core.model.owner.LookupResultDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.session.UiError
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.ErrorLine
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId

private val T = ManagementTexts

// --- shared row ----------------------------------------------------------------------------------------------------

@Composable
private fun ManagementRowContent(r: ManagementRow) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(r.label, style = if (r.heading) AssetaType.headline else AssetaType.subheadline, fontWeight = if (r.heading) FontWeight.SemiBold else null, modifier = Modifier.weight(1f))
            r.value?.let { Text(it, style = AssetaType.subheadline, color = palette.secondaryText) }
        }
        r.caption?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
        if (r.target is FigureTarget.Web) Text(T.OPEN_WEB, style = AssetaType.caption, color = palette.accent)
    }
}

/** Opens a figure's target: pushes the app screen, or the web console in the browser. */
@Composable
fun rememberFigureOpener(onOpen: (OwnerDestination) -> Unit): (FigureTarget) -> Unit {
    val uri = LocalUriHandler.current
    return { t ->
        when (t) {
            is FigureTarget.App -> onOpen(t.destination)
            is FigureTarget.Web -> runCatching { uri.openUri(t.url) }
        }
    }
}

internal fun managementItems(rows: List<ManagementRow>, go: (FigureTarget) -> Unit): List<GroupedItem> =
    rows.map { r -> GroupedItem(r.key, onClick = r.target?.let { t -> { go(t) } }) { ManagementRowContent(r) } }

fun LazyListScope.managementGroup(group: ManagementGroup, go: (FigureTarget) -> Unit) {
    groupedSection(keyPrefix = group.key, header = group.title, footer = group.footer, items = managementItems(group.rows, go))
}

// --- employee accountability ---------------------------------------------------------------------------------------

/** One titled list of an employee's records (empty lists are left out). */
data class EmployeeList(val key: String, val title: String, val rows: List<ManagementRow>)

/** Pure presentation of the employee screen (unit-tested; same rules as iOS). */
class EmployeePresentation(private val f: OwnerFeatures, private val webBase: String, private val zone: ZoneId = ZoneId.systemDefault()) {
    private fun titled(d: EmployeeAccountabilityDto): List<Pair<String, List<EmployeeRecordDto>>> = listOf(
        T.LIST_COLLECTIONS to d.collections, T.LIST_FLOATS to d.floats, T.LIST_TRANSFERS_IN to d.transfersIn, T.LIST_TRANSFERS_OUT to d.transfersOut,
        T.LIST_REMITTANCES to d.remittances, T.LIST_SPENDING to d.spending, T.LIST_RETENTIONS to d.retentions, T.LIST_DIFFERENCES to d.differences,
        T.LIST_CUSTODY_ADJUSTMENTS to d.custodyAdjustments, T.LIST_REPORTS to d.reportsSubmitted, T.LIST_APPROVALS to d.approvalsMade,
        T.LIST_ADJUSTMENTS_REQUESTED to d.adjustmentsRequested, T.LIST_ADJUSTMENTS_DECIDED to d.adjustmentsDecided,
    ) + if (d.scorecardVisible) listOf(T.LIST_SCORECARD to d.scorecardItems) else emptyList()

    fun money(amount: String?, currency: String?, unit: String? = null): String? {
        val raw = amount ?: return null
        val value = raw.toBigDecimalOrNull() ?: return raw
        return if (unit == "HOURS" || currency == null) "${OwnerFormat.hoursNumber(raw)} h" else OwnerFormat.money(value, currency)
    }

    /** Per list: count, and money totals per currency for money rows. */
    fun figures(d: EmployeeAccountabilityDto): List<Pair<String, String>> = titled(d).map { (title, rows) ->
        val totals = rows.filter { it.unit != "HOURS" && it.currency != null && it.amount?.toBigDecimalOrNull() != null }
            .groupBy { it.currency!! }
            .map { (c, list) -> OwnerFormat.money(list.fold(BigDecimal.ZERO) { sum, r -> sum + r.amount!!.toBigDecimal() }, c) }
        title to T.empCount(rows.size, totals.joinToString(", ").takeIf { it.isNotEmpty() })
    }

    fun cash(line: EmployeeCashHeldDto): ManagementRow {
        fun nz(raw: String) = raw.toBigDecimalOrNull()?.takeIf { it.signum() != 0 }?.let { OwnerFormat.money(it, line.currency) }
        return ManagementRow(
            "cash-${line.currency}", line.currency, money(line.outstanding, line.currency),
            caption = T.heldCaption(nz(line.inTransitOut), nz(line.claimedUnverifiedHandovers), nz(line.pendingFloats), nz(line.approvedRetention)),
        )
    }

    fun lists(d: EmployeeAccountabilityDto): List<EmployeeList> = titled(d).filter { (_, rows) -> rows.isNotEmpty() }.mapIndexed { i, (title, rows) ->
        EmployeeList("list-$i", title, rows.mapIndexed { j, r -> record("r-$i-$j", r) })
    }

    private fun record(key: String, r: EmployeeRecordDto) = ManagementRow(
        key, listOfNotNull(r.reference, r.label).firstOrNull() ?: T.recordType(r.recordType), money(r.amount, r.currency, r.unit),
        caption = listOfNotNull(T.recordRow(OwnerFormat.date(r.occurredAt, zone), r.status), DisplayNames.of(r.counterpartyStaffName, r.counterpartyStaffId)).joinToString(" · "),
        target = ManagementLinks.target(r.route, f, webBase),
    )
}

class EmployeeAccountabilityViewModel private constructor(
    data: OwnerData,
    staffId: String,
    private val selected: MutableStateFlow<ScorecardPeriod?>,
    private val custom: Pair<LocalDate, LocalDate>?,
    private val today: () -> LocalDate,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<EmployeeAccountabilityDto>({
    val (from, to) = selected.value?.range(today()) ?: custom ?: ScorecardPeriod.LAST_30_DAYS.range(today())
    data.employeeAccountability(staffId, from, to)
}, refreshOn) {
    constructor(data: OwnerData, staffId: String, dayFrom: String?, dayTo: String?, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) : this(
        data, staffId,
        MutableStateFlow(period(dayFrom, dayTo, today).let { it.first }),
        period(dayFrom, dayTo, today).second,
        today, refreshOn,
    )

    /** Null: the custom period handed over by the scorecard. */
    val period: StateFlow<ScorecardPeriod?> get() = selected

    fun select(p: ScorecardPeriod) {
        if (selected.value == p) return
        selected.value = p
        refresh()
    }

    private companion object {
        /** Matches the chip for a period handed over by the scorecard; a period no chip covers stays custom. */
        fun period(dayFrom: String?, dayTo: String?, today: () -> LocalDate): Pair<ScorecardPeriod?, Pair<LocalDate, LocalDate>?> {
            val from = dayFrom?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
            val to = dayTo?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
            if (from == null || to == null) return ScorecardPeriod.LAST_30_DAYS to null
            val chip = ScorecardPeriod.entries.firstOrNull { it.range(today()) == (from to to) }
            return chip to (from to to)
        }
    }
}

@Composable
fun EmployeeAccountabilityScreen(vm: EmployeeAccountabilityViewModel, features: OwnerFeatures, webBase: String, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val period by vm.period.collectAsStateWithLifecycle()
    val go = rememberFigureOpener(onOpen)
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(ScorecardPeriod.entries.map<ScorecardPeriod, Pair<ScorecardPeriod?, String>> { it to it.label }, period, { p -> p?.let(vm::select) })
        SnapshotScaffold(state, vm::refresh) { d ->
            val p = EmployeePresentation(features, webBase)
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                item(key = "identity") {
                    SectionCard(null) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(d.identity.fullName, style = AssetaType.headline, modifier = Modifier.weight(1f))
                            if (!d.identity.isActive) StatusPill(T.EMP_INACTIVE, OwnerColors.Warning)
                        }
                        d.identity.employeeCode?.let { KeyValue(T.EMP_CODE, it) }
                        if (d.identity.roles.isNotEmpty()) KeyValue(T.EMP_ROLES, d.identity.roles.joinToString(", "))
                        d.identity.phone?.let { KeyValue(T.EMP_PHONE, it) }
                    }
                }
                item(key = "figures") { SectionCard(T.EMP_FIGURES) { p.figures(d).forEach { (l, v) -> KeyValue(l, v) } } }
                if (d.cashHeld.isNotEmpty()) groupedSection(keyPrefix = "cash", header = T.EMP_CASH_HELD, items = managementItems(d.cashHeld.map(p::cash), go))
                p.lists(d).forEach { l -> groupedSection(keyPrefix = l.key, header = l.title, items = managementItems(l.rows, go)) }
                if (d.truncated.isNotEmpty()) item(key = "truncated") { SectionCard(null) { FootNote(T.EMP_TRUNCATED) } }
            }
        }
    }
}

// --- find a reference --------------------------------------------------------------------------------------------

data class LookupState(val query: String = "", val busy: Boolean = false, val result: LookupResultDto? = null, val error: UiError? = null, val offline: Boolean = false)

/** Pure presentation of a lookup match (unit-tested; same rules as iOS). */
class LookupPresentation(private val f: OwnerFeatures, private val webBase: String, private val zone: ZoneId = ZoneId.systemDefault()) {
    fun title(m: LookupMatchDto): String = T.recordType(m.recordType)

    fun subtitle(m: LookupMatchDto): String = listOfNotNull(m.reference, m.status?.let(OwnerFormat::humanize)).joinToString(" · ")

    /** What, when, who, balance: rows left empty are hidden. */
    fun rows(m: LookupMatchDto): List<Pair<String, String>> = listOfNotNull(
        DisplayNames.of(m.recordedByName, m.recordedBy)?.let { T.LOOKUP_RECORDED_BY to who(it, m.recordedAt) },
        DisplayNames.of(m.decidedByName, m.decidedBy)?.let { T.LOOKUP_DECIDED_BY to who(it, m.decidedAt) },
        DisplayNames.of(m.customerName, m.customerId)?.let { T.LOOKUP_CUSTOMER to it },
        DisplayNames.of(m.machineCode ?: m.machineName, m.machineId)?.let { T.LOOKUP_MACHINE to it },
        DisplayNames.of(m.staffMemberName, m.staffMemberId)?.let { T.LOOKUP_STAFF to it },
        m.amount?.let { a -> T.LOOKUP_AMOUNT to money(a, m.currency) },
        m.balanceOutstanding?.let { b -> T.LOOKUP_BALANCE to (if (m.balanceUnit == "HOURS") "${OwnerFormat.hoursNumber(b)} h" else money(b, m.currency)) },
        m.hoursRemaining?.let { h -> T.LOOKUP_HOURS_REMAINING to "${OwnerFormat.hoursNumber(h)} h" },
    )

    private fun who(name: String, at: String?) = at?.let { "$name · ${OwnerFormat.dateTime(it, zone)}" } ?: name

    private fun money(raw: String, currency: String?): String =
        raw.toBigDecimalOrNull()?.let { v -> currency?.let { OwnerFormat.money(v, it) } ?: OwnerFormat.hoursNumber(raw) } ?: raw

    fun target(m: LookupMatchDto): FigureTarget? = ManagementLinks.target(m.route, f, webBase)
}

class LookupViewModel(private val data: OwnerData) : ViewModel() {
    private val _state = MutableStateFlow(LookupState())
    val state: StateFlow<LookupState> = _state

    fun edit(q: String) = _state.update { it.copy(query = q.take(100)) }

    fun search() {
        val q = _state.value.query.trim()
        if (q.isEmpty() || _state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, result = null, error = null, offline = false) }
            when (val r = data.lookup(q)) {
                is ActionResult.Done -> _state.update { it.copy(busy = false, result = r.value) }
                // A refusal has a server code; none means the request did not reach the server.
                is ActionResult.Refused -> _state.update { it.copy(busy = false, error = r.error.takeIf { _ -> r.code != null }, offline = r.code == null) }
            }
        }
    }
}

@Composable
fun LookupScreen(vm: LookupViewModel, features: OwnerFeatures, webBase: String, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val go = rememberFigureOpener(onOpen)
    val p = LookupPresentation(features, webBase)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
        item(key = "search") {
            Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    state.query, vm::edit, Modifier.fillMaxWidth().testTag("lookup-field"), label = { Text(T.LOOKUP_HINT) }, singleLine = true,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters, autoCorrectEnabled = false, imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { vm.search() }),
                )
                Button(vm::search, Modifier.fillMaxWidth().testTag("lookup-search"), enabled = state.query.isNotBlank() && !state.busy) { Text(T.LOOKUP_SEARCH) }
                state.error?.let { ErrorLine(it) }
                if (state.offline) Text(T.LOOKUP_OFFLINE, color = palette.secondaryText)
                if (state.busy) CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
            }
        }
        state.result?.let { r ->
            if (r.matches.isEmpty()) item(key = "empty") { EmptyState(T.LOOKUP_EMPTY) }
            r.matches.forEachIndexed { i, m ->
                val target = p.target(m)
                groupedSection(
                    keyPrefix = "match-$i", header = p.title(m), footer = null,
                    items = listOf(
                        GroupedItem("head-$i", onClick = target?.let { t -> { go(t) } }) {
                            ManagementRowContent(ManagementRow("h", p.subtitle(m), target = target))
                        },
                    ) + p.rows(m).mapIndexed { j, (l, v) -> GroupedItem("row-$i-$j") { KeyValue(l, v) } },
                )
            }
        }
    }
}
