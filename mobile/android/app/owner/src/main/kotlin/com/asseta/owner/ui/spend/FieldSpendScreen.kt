package com.asseta.owner.ui.spend

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
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.map
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.home.KpiTone
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.math.BigDecimal
import java.time.ZoneId

enum class SpendSegment { EXPENSES, FUEL }

/** Field spend and job spend wording shared with iOS (`FieldSpendView` / job detail). */
object SpendText {
    val SEGMENTS: List<Pair<SpendSegment, String>> = listOf(SpendSegment.EXPENSES to "Expenses", SpendSegment.FUEL to "Fuel")

    /** The server's waiting-for-decision expense status (`ExpenseStatus.PENDING_APPROVAL`). */
    const val PENDING = "PENDING_APPROVAL"

    /** Expense filter chips; null = all (the default). */
    val EXPENSE_FILTERS: List<Pair<String?, String>> = listOf(PENDING to "Pending", null to "All")
    val DEFAULT_EXPENSE_FILTER: String? = null

    const val NO_EXPENSES = "No expenses yet."
    const val NO_FUEL = "No fuel recorded yet."
    const val NO_JOB_EXPENSES = "No expenses on this job."
    const val NO_JOB_FUEL = "No fuel recorded on this job."

    fun expenseTone(status: String): KpiTone = when (status) {
        "PENDING", "PENDING_APPROVAL", "SUBMITTED" -> KpiTone.WARNING
        "APPROVED" -> KpiTone.GOOD
        "REJECTED" -> KpiTone.CRITICAL
        else -> KpiTone.MUTED
    }

    /** "<supplier · >22 Oct 2026". */
    fun expenseDetail(e: ExpenseDto, zone: ZoneId): String =
        listOfNotNull(e.supplier?.takeIf { it.isNotBlank() }, OwnerFormat.date(e.incurredAt, zone)).joinToString(" · ")

    /** "Total approved: TZS 150,000.00", one line per currency (sorted); empty when nothing is approved. */
    fun totalApproved(items: List<ExpenseDto>, money: (BigDecimal, String) -> String = { v, c -> OwnerFormat.money(v, c) }): List<String> =
        items.filter { it.status == "APPROVED" }.groupBy { it.currency }.toSortedMap()
            .map { (c, list) -> "Total approved: ${money(list.fold(BigDecimal.ZERO) { sum, e -> sum + e.amount.value }, c)}" }

    /** "Purchase · 40 L". */
    fun fuelTitle(f: FuelEventDto): String = "${OwnerFormat.humanize(f.eventType)} · ${OwnerFormat.decimal(f.litres.value)} L"

    /** "<supplier · >22 Oct 2026". */
    fun fuelDetail(f: FuelEventDto, zone: ZoneId): String =
        listOfNotNull(f.supplier?.takeIf { it.isNotBlank() }, OwnerFormat.date(f.occurredAt, zone)).joinToString(" · ")
}

/** What the Field spend screen shows for the selected segment. */
data class SpendList(val segment: SpendSegment, val expenses: List<ExpenseDto> = emptyList(), val fuel: List<FuelEventDto> = emptyList())

class FieldSpendViewModel private constructor(
    data: OwnerData,
    private val selectedSegment: MutableStateFlow<SpendSegment>,
    private val selectedStatus: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<SpendList>({
    when (val segment = selectedSegment.value) {
        SpendSegment.EXPENSES -> data.expenses(selectedStatus.value).map { SpendList(segment, expenses = it.items) }
        SpendSegment.FUEL -> data.fuel().map { SpendList(segment, fuel = it.items) }
    }
}, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>) :
        this(data, MutableStateFlow(SpendSegment.EXPENSES), MutableStateFlow(SpendText.DEFAULT_EXPENSE_FILTER), refreshOn)

    val segment: StateFlow<SpendSegment> get() = selectedSegment
    val status: StateFlow<String?> get() = selectedStatus

    fun select(segment: SpendSegment) {
        selectedSegment.value = segment
        refresh()
    }

    fun filter(status: String?) {
        selectedStatus.value = status
        refresh()
    }
}

/** Read-only expenses and fuel recorded in the field; a row linked to a job opens it. */
@Composable
fun FieldSpendScreen(vm: FieldSpendViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val segment by vm.segment.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(SpendText.SEGMENTS, segment, vm::select)
        if (segment == SpendSegment.EXPENSES) FilterChipRow(SpendText.EXPENSE_FILTERS, status, vm::filter)
        SnapshotScaffold(state, vm::refresh) { list ->
            val zone = ZoneId.systemDefault()
            val openJob = { jobId: Any? -> jobId?.takeIf { features.jobs }?.let { id -> { onOpen(OwnerDestination.Job(id.toString())) } } }
            val rows = buildList {
                when (list.segment) {
                    SpendSegment.EXPENSES -> {
                        if (list.expenses.isEmpty()) add(GroupedItem("empty") { EmptyState(SpendText.NO_EXPENSES, icon = R.drawable.ic_receipt) })
                        list.expenses.forEach { e -> add(GroupedItem(e.id.toString(), onClick = openJob(e.jobId)) { ExpenseRow(e, zone) }) }
                    }
                    SpendSegment.FUEL -> {
                        if (list.fuel.isEmpty()) add(GroupedItem("empty") { EmptyState(SpendText.NO_FUEL, icon = R.drawable.ic_receipt) })
                        list.fuel.forEach { f -> add(GroupedItem(f.id.toString(), onClick = openJob(f.jobId)) { FuelRow(f, zone) }) }
                    }
                }
            }
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) { groupedSection("spend-${list.segment}", rows) }
        }
    }
}

/** Description with amount, "<supplier · >date" with the status pill, and the decision note (also on job detail). */
@Composable
fun ExpenseRow(e: ExpenseDto, zone: ZoneId) {
    Column(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(e.description, style = AssetaType.headline, modifier = Modifier.weight(1f))
            Text(OwnerFormat.money(e.amount.value, e.currency), style = AssetaType.headline)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(SpendText.expenseDetail(e, zone), style = AssetaType.subheadline, color = palette.secondaryText, modifier = Modifier.weight(1f))
            StatusPill(OwnerFormat.humanize(e.status), OwnerColors.tone(SpendText.expenseTone(e.status)))
        }
        e.decisionNote?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}

/** "<type> · <litres> L" with the attributed cost, then "<supplier · >date" (also on job detail). */
@Composable
fun FuelRow(f: FuelEventDto, zone: ZoneId) {
    Column(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(SpendText.fuelTitle(f), style = AssetaType.headline, modifier = Modifier.weight(1f))
            Text(OwnerFormat.money(f.attributedCost.value, f.currency), style = AssetaType.headline)
        }
        Text(SpendText.fuelDetail(f, zone), style = AssetaType.subheadline, color = palette.secondaryText)
    }
}
