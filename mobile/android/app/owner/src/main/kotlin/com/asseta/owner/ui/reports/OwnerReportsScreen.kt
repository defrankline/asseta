package com.asseta.owner.ui.reports

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportLineDto
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.PeriodTabs
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.Period
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.StaleBanner
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale
import com.asseta.core.ui.R as CoreR

/** Reports wording (design OwnerReports; same as iOS). */
object OwnerReportsTexts {
    const val BY_REASON = "Non-productive hours by reason"
    const val REPORTS = "REPORTS"
    const val CUSTOMERS = "Customers"
    const val HOURS_SOLD = "Hours sold"
    const val HOURS_USED = "Hours used"
    const val NON_PRODUCTIVE = "Non-productive"
    const val NO_HOURS = "No machine hours reported in this period."
    const val COUNTED = "Approved and waiting reports; rejected ones are left out."
    const val ROW_CUSTOMER_HOURS = "Customer hours: bought, used, left"
    const val ROW_BY_MACHINE = "Productive vs non-productive by machine"
    const val ROW_BY_REASON = "Non-productive hours by reason"
    const val ROW_SALES = "Sales and collections by method"
    const val ROW_CREDIT = "Credit invoices and payments"
    const val ROW_CASH = "Cash per supervisor"

    /** "Machine hours, November" / "Machine hours, this week". */
    fun title(period: Period, today: LocalDate): String = when (period) {
        Period.MONTH -> "Machine hours, ${today.month.getDisplayName(TextStyle.FULL, Locale.US)}"
        Period.WEEK -> "Machine hours, this week"
        Period.TODAY -> "Machine hours, today"
    }

    fun stillWithCustomers(hours: BigDecimal) = "${Figures.hours(hours)} still with customers"
}

/** Machine hours of a period: customer work and each non-productive reason (design legend order: customers first). */
data class HoursSplit(val customers: BigDecimal, val reasons: List<Pair<String, BigDecimal>>) {
    val total: BigDecimal get() = reasons.fold(customers) { a, (_, h) -> a + h }
}

/** One REPORTS row and the screen it opens. */
data class ReportLink(val label: String, val open: OwnerDestination)

/** Pure Reports presentation (unit-tested). */
object OwnerReportsPresentation {
    /** Short reason names of the legend ("Breakdown", "Transit", "Idle", "Servicing"); else the tenant's name. */
    fun reasonLabel(l: MachineReportLineDto): String = when (l.reasonCode) {
        "BREAKDOWN" -> "Breakdown"
        "TRANSIT" -> "Transit"
        "IDLE_ON_SITE" -> "Idle"
        "SERVICING" -> "Servicing"
        "WAITING_CUSTOMER" -> "Waiting for customer"
        "WEATHER" -> "Weather"
        else -> l.reasonName ?: l.reasonCode?.lowercase()?.replace('_', ' ')?.replaceFirstChar { it.uppercase() } ?: OwnerReportsTexts.NON_PRODUCTIVE
    }

    /**
     * Customer hours and non-productive hours by reason of the period's reports (rejected ones left out), the
     * biggest reason first. Non-productive hours a list row carries without its lines count as "Non-productive".
     */
    fun split(reports: List<MachineReportDto>): HoursSplit {
        val counted = reports.filter { it.status != MachineReportDto.REJECTED }
        val byReason = linkedMapOf<String, BigDecimal>()
        counted.forEach { r ->
            val lines = r.lines.filter { it.kind == MachineReportLineDto.NON_PRODUCTIVE }
            lines.forEach { l -> byReason.merge(reasonLabel(l), Figures.dec(l.hours), BigDecimal::add) }
            val unlisted = Figures.dec(r.nonProductiveHours) - Figures.sum(lines.map { it.hours })
            if (unlisted.signum() > 0) byReason.merge(OwnerReportsTexts.NON_PRODUCTIVE, unlisted, BigDecimal::add)
        }
        return HoursSplit(
            Figures.sum(counted.map { it.customerHours }),
            byReason.entries.filter { it.value.signum() > 0 }.sortedByDescending { it.value }.map { it.key to it.value },
        )
    }

    /** Hours sold in the period (orders not cancelled) and their amount per currency ("TZS 91.2M"). */
    fun sold(orders: List<OwnerHoursPurchaseDto>): Pair<BigDecimal, String?> {
        val live = orders.filter { it.cancelledAt == null }
        val amounts = live.groupBy { it.currency ?: "" }.toSortedMap().map { (c, l) -> "$c ${Figures.compact(Figures.sum(l.map { it.amount }))}".trim() }
        return Figures.sum(live.map { it.hours }) to amounts.joinToString(", ").ifEmpty { null }
    }

    /** The REPORTS rows the role can open (no files: each opens the matching screen). */
    fun links(f: OwnerFeatures): List<ReportLink> = listOfNotNull(
        ReportLink(OwnerReportsTexts.ROW_CUSTOMER_HOURS, OwnerDestination.Customers).takeIf { f.customers },
        ReportLink(OwnerReportsTexts.ROW_BY_MACHINE, OwnerDestination.Machines).takeIf { f.machineReports },
        ReportLink(OwnerReportsTexts.ROW_BY_REASON, OwnerDestination.HoursByReason).takeIf { f.machineReports },
        ReportLink(OwnerReportsTexts.ROW_SALES, OwnerDestination.Money).takeIf { f.customerHours },
        ReportLink(OwnerReportsTexts.ROW_CREDIT, OwnerDestination.Money).takeIf { f.customerHours },
        ReportLink(OwnerReportsTexts.ROW_CASH, OwnerDestination.Cash).takeIf { f.finance },
    )

    /** Bar colours: amber for customers, then one colour per reason (repeating). */
    val REASON_COLORS = listOf(Color(0xFFE5675C), Color(0xFF4FA3E0), Color(0xFF9B7BE0), Color(0xFF5CC8A8), Color(0xFFB7C4D1), Color(0xFF7BA05C))
}

/** Reports and the reason breakdown share one instance per company (the chosen period carries over). */
class OwnerReportsViewModel(private val data: OwnerData, features: OwnerFeatures, refreshOn: Flow<Unit>, private val today: () -> LocalDate = { LocalDate.now() }) : ViewModel() {
    private val selected = MutableStateFlow(Period.MONTH)
    val period: StateFlow<Period> = selected.asStateFlow()
    private fun range() = selected.value.range(today())

    val reports: Section<List<MachineReportDto>>? = if (features.machineReports) Section(viewModelScope) { range().let { data.machineReportsBetween(it.from, it.to) } } else null
    val orders: Section<List<OwnerHoursPurchaseDto>>? = if (features.customerHours) Section(viewModelScope) { range().let { data.ordersBetween(it.from, it.to) } } else null
    private val all = listOfNotNull(reports, orders)

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { refresh() } }
    }

    fun refresh() = all.forEach { it.refresh() }

    fun select(p: Period) {
        if (selected.value == p) return
        selected.value = p
        refresh()
    }

    fun currentDay(): LocalDate = today.invoke()
}

@Composable
fun OwnerReportsScreen(vm: OwnerReportsViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val period by vm.period.collectAsStateWithLifecycle()
    val reports = vm.reports?.state?.collectAsStateWithLifecycle()?.value
    val orders = vm.orders?.state?.collectAsStateWithLifecycle()?.value
    val split = reports?.data?.let(OwnerReportsPresentation::split)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
        item { PeriodTabs(listOf(Period.WEEK to Period.WEEK.label, Period.MONTH to Period.MONTH.label), period, vm::select) }
        reports?.let { st ->
            item {
                ShellCard(Modifier.padding(top = 16.dp)) {
                    StaleBanner(st.snapshot)
                    Text(OwnerReportsTexts.title(period, vm.currentDay()), fontSize = 14.sp, color = palette.secondaryText)
                    when {
                        split == null && st.loading -> Unit
                        split == null -> FootNote(st.error?.message.orEmpty())
                        split.total.signum() == 0 -> FootNote(OwnerReportsTexts.NO_HOURS)
                        else -> {
                            Text(Figures.hours(split.total), fontSize = 28.sp, fontWeight = FontWeight.Bold)
                            HoursBar(split)
                            Legend(split)
                        }
                    }
                }
            }
        }
        if (orders != null || split != null) {
            item {
                Row(Modifier.padding(start = 20.dp, end = 20.dp, top = 12.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    val (soldHours, soldAmount) = orders?.data?.let(OwnerReportsPresentation::sold) ?: (null to null)
                    if (orders != null) Tile(OwnerReportsTexts.HOURS_SOLD, soldHours?.let(Figures::hours) ?: "—", soldAmount, Modifier.weight(1f))
                    if (split != null || reports != null) {
                        val used = split?.customers
                        val left = if (soldHours != null && used != null) (soldHours - used).max(BigDecimal.ZERO) else null
                        Tile(OwnerReportsTexts.HOURS_USED, used?.let(Figures::hours) ?: "—", left?.let(OwnerReportsTexts::stillWithCustomers), Modifier.weight(1f))
                    }
                }
            }
        }
        val links = OwnerReportsPresentation.links(features)
        if (links.isNotEmpty()) {
            item { SectionLabel(OwnerReportsTexts.REPORTS) }
            item {
                ShellCard(padding = false) {
                    links.forEachIndexed { i, l ->
                        CardRow(l.label, last = i == links.lastIndex, onClick = { onOpen(l.open) }, trailing = { Chevron() })
                    }
                }
            }
        }
    }
}

/** Non-productive hours by reason for the period chosen on Reports (with each reason's share). */
@Composable
fun HoursByReasonScreen(vm: OwnerReportsViewModel) {
    val period by vm.period.collectAsStateWithLifecycle()
    val st = vm.reports?.state?.collectAsStateWithLifecycle()?.value ?: return
    val split = st.data?.let(OwnerReportsPresentation::split)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
        item { PeriodTabs(listOf(Period.WEEK to Period.WEEK.label, Period.MONTH to Period.MONTH.label), period, vm::select) }
        item { Column(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) { StaleBanner(st.snapshot) } }
        when {
            split == null && st.loading -> Unit
            split == null -> item { Column(Modifier.padding(horizontal = 20.dp)) { FootNote(st.error?.message.orEmpty()) } }
            split.reasons.isEmpty() -> item { Column(Modifier.padding(horizontal = 20.dp)) { FootNote(OwnerReportsTexts.NO_HOURS) } }
            else -> {
                val np = split.reasons.fold(BigDecimal.ZERO) { a, (_, h) -> a + h }
                item { SectionLabel("${OwnerReportsTexts.NON_PRODUCTIVE} · ${Figures.hours(np)}") }
                item {
                    ShellCard(padding = false) {
                        split.reasons.forEachIndexed { i, (reason, hours) ->
                            CardRow(
                                reason, Figures.percent(hours, split.total)?.let { "$it of machine hours" }, last = i == split.reasons.lastIndex,
                                trailing = { Text(Figures.hours(hours), fontWeight = FontWeight.Bold) },
                            )
                        }
                    }
                }
                item { Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) { FootNote(OwnerReportsTexts.COUNTED) } }
            }
        }
    }
}

@Composable
private fun HoursBar(split: HoursSplit) {
    val total = split.total.toFloat().takeIf { it > 0f } ?: return
    val parts = listOf(palette.accent to split.customers) +
        split.reasons.mapIndexed { i, (_, h) -> OwnerReportsPresentation.REASON_COLORS[i % OwnerReportsPresentation.REASON_COLORS.size] to h }
    Row(
        Modifier.padding(vertical = 12.dp).fillMaxWidth().height(14.dp).clip(RoundedCornerShape(999.dp)).background(palette.raised)
            .semantics { contentDescription = "Machine hours by customers and reasons" },
    ) {
        parts.filter { it.second.signum() > 0 }.forEach { (color, h) ->
            Box(Modifier.weight(h.toFloat() / total).fillMaxHeight().background(color))
        }
    }
}

@Composable
private fun Legend(split: HoursSplit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        LegendRow(palette.accent, "${OwnerReportsTexts.CUSTOMERS} ${Figures.hours(split.customers)}")
        split.reasons.forEachIndexed { i, (reason, h) ->
            LegendRow(OwnerReportsPresentation.REASON_COLORS[i % OwnerReportsPresentation.REASON_COLORS.size], "$reason ${Figures.hours(h)}")
        }
    }
}

@Composable
private fun LegendRow(color: Color, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.size(10.dp).clip(RoundedCornerShape(3.dp)).background(color))
        Text(text, fontSize = 14.sp)
    }
}

@Composable
private fun Tile(label: String, value: String, detail: String?, modifier: Modifier) {
    Column(modifier.clip(RoundedCornerShape(18.dp)).background(palette.cell).padding(16.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, fontSize = 13.sp, color = palette.secondaryText)
        Text(value, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        detail?.let { Text(it, fontSize = 13.sp, color = palette.secondaryText) }
    }
}

@Composable
private fun Chevron() = Icon(painterResource(CoreR.drawable.ic_shell_chevron), null, tint = palette.secondaryText, modifier = Modifier.size(18.dp))
