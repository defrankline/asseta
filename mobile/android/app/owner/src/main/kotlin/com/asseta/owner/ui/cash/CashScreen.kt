package com.asseta.owner.ui.cash

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId

enum class CashPeriod(val label: String) { TODAY("Today"), WEEK("7 days"), MONTH("This month") }

/** One labelled figure of a supervisor's cash card; [warning] marks amounts still awaiting a decision. */
data class CashLine(val label: String, val amount: BigDecimal, val warning: Boolean = false)

/** Cash with supervisors wording and rules shared with iOS (`CashView`). Read-only. */
object CashText {
    val PERIODS: List<Pair<CashPeriod, String>> = CashPeriod.entries.map { it to it.label }
    val DEFAULT_PERIOD = CashPeriod.TODAY
    const val HOLDING = "Holding"
    const val EMPTY = "No supervisor cash in this period."
    const val FOOTER = "Holding = opening + floats + collections − approved spending − verified handovers."

    /** Local days [from, to] of a period ending [today]. */
    fun range(period: CashPeriod, today: LocalDate): Pair<LocalDate, LocalDate> = when (period) {
        CashPeriod.TODAY -> today to today
        CashPeriod.WEEK -> today.minusDays(6) to today
        CashPeriod.MONTH -> today.withDayOfMonth(1) to today
    }

    /** Largest holding first. */
    fun sorted(rows: List<CashSupervisorSummaryDto>): List<CashSupervisorSummaryDto> = rows.sortedByDescending { it.closingOutstanding.value }

    /** The movements, then (only when above zero) what still awaits approval or verification. */
    fun lines(r: CashSupervisorSummaryDto): List<CashLine> = listOf(
        CashLine("Opening", r.opening.value),
        CashLine("Floats issued", r.floatsIssued.value),
        CashLine("Collections", r.collections.value),
        CashLine("Approved spending", r.approvedSpending.value),
        CashLine("Handed over (verified)", r.verifiedHandovers.value),
    ) + listOf(
        CashLine("Spending awaiting approval", r.pendingSpending.value, warning = true),
        CashLine("Handovers awaiting verification", r.claimedUnverifiedHandovers.value, warning = true),
        CashLine("Collections awaiting verification", r.unverifiedCollections.value, warning = true),
    ).filter { it.amount.signum() > 0 }
}

class CashViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<CashPeriod>,
    today: () -> LocalDate,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<List<CashSupervisorSummaryDto>>({
    val (from, to) = CashText.range(selected.value, today())
    data.cash(selected.value.name, from, to)
}, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now(ZoneId.systemDefault()) }) :
        this(data, MutableStateFlow(CashText.DEFAULT_PERIOD), today, refreshOn)

    val period: StateFlow<CashPeriod> get() = selected

    fun select(period: CashPeriod) {
        selected.value = period
        refresh()
    }
}

/** One card per supervisor and currency: the cash they hold, how it moved, and what still awaits a decision. */
@Composable
fun CashScreen(vm: CashViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val period by vm.period.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(CashText.PERIODS, period, vm::select)
        SnapshotScaffold(state, vm::refresh) { rows ->
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                if (rows.isEmpty()) item { EmptyState(CashText.EMPTY, icon = R.drawable.ic_cash) }
                CashText.sorted(rows).forEach { r ->
                    item(key = "${r.staffMemberId}-${r.currency}") { CashCard(r) }
                }
                item { Column(Modifier.padding(horizontal = 32.dp)) { FootNote(CashText.FOOTER) } }
            }
        }
    }
}

@Composable
private fun CashCard(r: CashSupervisorSummaryDto) {
    GroupedSection(header = r.staffName) {
        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(CashText.HOLDING, style = AssetaType.caption, color = palette.secondaryText)
            Text(OwnerFormat.money(r.closingOutstanding.value, r.currency), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        CashText.lines(r).forEach { l ->
            val value = OwnerFormat.money(l.amount, r.currency)
            if (l.warning) LabeledValue(l.label, value, valueColor = OwnerColors.Warning) else KeyValue(l.label, value)
        }
    }
}
