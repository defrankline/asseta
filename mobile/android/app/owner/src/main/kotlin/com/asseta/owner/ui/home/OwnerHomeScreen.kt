package com.asseta.owner.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.ui.shell.ActionTile
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.CountBadge
import com.asseta.core.ui.shell.Greeting
import com.asseta.core.ui.shell.HomeTopRow
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.ShellText
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.shell.SummaryFigure
import com.asseta.core.ui.shell.SummaryStrip
import com.asseta.core.ui.shell.TileGrid
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.approvals.ApprovalCounts
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.Period
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.reports.ReportPresentation
import com.asseta.owner.ui.reports.ReportTexts
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId
import com.asseta.core.ui.R as CoreR

/** Home wording (design OwnerHome; same as iOS). */
object HomeTexts {
    const val CASH = "Cash with supervisors"
    const val SOLD = "Hours sold this week"
    const val PRODUCTIVE = "Productive"
    const val YOUR_BUSINESS = "YOUR BUSINESS"
    const val ATTENTION = "NEEDS YOUR ATTENTION"
    const val APPROVALS = "Approvals"
    const val APPROVALS_SUB = "Reports, credit, expenses"
    const val CUSTOMERS = "Customers"
    const val CUSTOMERS_SUB = "Hours bought, used, left"
    const val MACHINES = "Machines"
    const val MACHINES_SUB = "Map, readings, hours"
    const val MONEY = "Money"
    const val MONEY_SUB = "Collections, cash, expenses"
    const val NOTHING = "Nothing needs your attention right now."
    const val NONE = "—"
    const val NOTIFICATIONS = "Notifications"
}

/** One "Needs your attention" row. */
data class AttentionItem(val key: String, val title: String, val detail: String, val pill: String, val tone: PillTone, val open: OwnerDestination)

/** Pure Home figures (unit-tested). */
object HomePresentation {
    /** Cash with supervisors of the overview's first currency, compact ("5.2M"); "—" without it. */
    fun cash(o: TenantOverviewDto?): String =
        o?.money?.currencies?.firstOrNull()?.let { Figures.compact(it.cashWithSupervisors.value) } ?: HomeTexts.NONE

    /** Hours of the orders recorded this week (cancelled ones left out): "92 h". */
    fun hoursSold(orders: List<OwnerHoursPurchaseDto>?): String =
        orders?.let { list -> Figures.hours(list.filter { it.cancelledAt == null }.fold(BigDecimal.ZERO) { a, p -> a + Figures.dec(p.hours) }) } ?: HomeTexts.NONE

    /** Customer hours over all hours of the period's reports (rejected ones left out): "73%". */
    fun productive(reports: List<MachineReportDto>?): String {
        val counted = reports?.filter { it.status != MachineReportDto.REJECTED } ?: return HomeTexts.NONE
        val total = Figures.sum(counted.map { it.hours })
        return Figures.percent(Figures.sum(counted.map { it.customerHours }), total) ?: HomeTexts.NONE
    }

    fun figures(o: TenantOverviewDto?, orders: List<OwnerHoursPurchaseDto>?, reports: List<MachineReportDto>?, f: OwnerFeatures): List<SummaryFigure> = listOfNotNull(
        SummaryFigure(HomeTexts.CASH, cash(o)).takeIf { f.finance },
        SummaryFigure(HomeTexts.SOLD, hoursSold(orders)).takeIf { f.customerHours },
        SummaryFigure(HomeTexts.PRODUCTIVE, productive(reports), accent = true).takeIf { f.machineReports },
    )

    /** Reports waiting (with their non-productive hours) → Review; machines with no report for days → Overdue. */
    fun attention(pending: List<MachineReportDto>?, statuses: List<MachineReportStatusDto>?, nowMs: Long, zone: ZoneId): List<AttentionItem> =
        pending.orEmpty().map { r ->
            AttentionItem("mr-${r.id}", ReportPresentation.attentionTitle(r), ReportPresentation.attentionDetail(r, nowMs, zone), ReportTexts.REVIEW, PillTone.WAITING, OwnerDestination.MachineReport(r.id))
        } + ReportPresentation.overdue(statuses.orEmpty()).map { s ->
            AttentionItem("od-${s.machineId}", ReportPresentation.overdueTitle(s), ReportPresentation.overdueDetail(s), ReportTexts.OVERDUE, PillTone.BAD, OwnerDestination.Machine(s.machineId))
        }
}

/** Home's own figures: this week's sales and reports, the overview's cash, where each machine stands. */
class OwnerHomeViewModel(data: OwnerData, features: OwnerFeatures, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) : ViewModel() {
    private val week = Period.WEEK.range(today())
    val overview: Section<TenantOverviewDto>? = if (features.finance) Section(viewModelScope) { data.overview() } else null
    val orders: Section<List<OwnerHoursPurchaseDto>>? = if (features.customerHours) Section(viewModelScope) { data.ordersBetween(week.from, week.to) } else null
    val reports: Section<List<MachineReportDto>>? = if (features.machineReports) Section(viewModelScope) { data.machineReportsBetween(week.from, week.to) } else null
    val statuses: Section<List<MachineReportStatusDto>>? = if (features.machineReports) Section(viewModelScope) { data.machineReportStatus() } else null
    private val all = listOfNotNull(overview, orders, reports, statuses)

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { refresh() } }
    }

    fun refresh() = all.forEach { it.refresh() }
}

@Composable
fun OwnerHomeScreen(
    vm: OwnerHomeViewModel,
    features: OwnerFeatures,
    displayName: String?,
    company: String,
    approvals: ApprovalCounts?,
    pendingReports: List<MachineReportDto>?,
    unread: Int?,
    nowMs: () -> Long,
    onMenu: () -> Unit,
    onOpen: (OwnerDestination) -> Unit,
    /** The company notice and go-live banner, above the figures. */
    header: (@Composable () -> Unit)? = null,
) {
    val overview = vm.overview?.state?.collectAsStateWithLifecycle()?.value?.data
    val orders = vm.orders?.state?.collectAsStateWithLifecycle()?.value?.data
    val reports = vm.reports?.state?.collectAsStateWithLifecycle()?.value?.data
    val statuses = vm.statuses?.state?.collectAsStateWithLifecycle()?.value
    val figures = HomePresentation.figures(overview, orders, reports, features)
    val attention = HomePresentation.attention(pendingReports, statuses?.data, nowMs(), ZoneId.systemDefault())
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item(key = "top") {
            HomeTopRow(onMenu) {
                if (features.notifications) Bell(ShellText.badge(unread)) { onOpen(OwnerDestination.Notifications()) }
            }
        }
        item(key = "greeting") { Greeting(ShellText.greeting(displayName), company) }
        header?.let { h -> item(key = "header") { Column(Modifier.padding(start = 20.dp, end = 20.dp, bottom = 16.dp)) { h() } } }
        if (figures.isNotEmpty()) item(key = "figures") { SummaryStrip(figures) }
        val tiles = buildList<@Composable (Modifier) -> Unit> {
            if (features.approvalsScreen) add { m -> ActionTile(HomeTexts.APPROVALS, HomeTexts.APPROVALS_SUB, CoreR.drawable.ic_shell_approvals, m, primary = true, badge = approvals?.waiting) { onOpen(OwnerDestination.Approvals()) } }
            if (features.customers) add { m -> ActionTile(HomeTexts.CUSTOMERS, HomeTexts.CUSTOMERS_SUB, CoreR.drawable.ic_shell_customers, m) { onOpen(OwnerDestination.Customers) } }
            if (features.machines) add { m -> ActionTile(HomeTexts.MACHINES, HomeTexts.MACHINES_SUB, CoreR.drawable.ic_shell_machines, m) { onOpen(OwnerDestination.Machines) } }
            if (features.money) add { m -> ActionTile(HomeTexts.MONEY, HomeTexts.MONEY_SUB, CoreR.drawable.ic_shell_money, m) { onOpen(OwnerDestination.Money) } }
        }
        if (tiles.isNotEmpty()) {
            item(key = "business-label") { SectionLabel(HomeTexts.YOUR_BUSINESS) }
            item(key = "tiles") { TileGrid(tiles) }
        }
        if (features.machineReports) {
            item(key = "attention-label") { SectionLabel(HomeTexts.ATTENTION) }
            item(key = "attention") {
                if (attention.isEmpty()) {
                    Column(Modifier.padding(horizontal = 20.dp)) { FootNote(HomeTexts.NOTHING) }
                } else {
                    ShellCard(padding = false) {
                        attention.forEachIndexed { i, a ->
                            CardRow(a.title, a.detail, last = i == attention.lastIndex, onClick = { onOpen(a.open) }, trailing = { StatusPill(a.pill, a.tone) })
                        }
                    }
                }
            }
        }
    }
}

/** The bell with the unread badge (red). */
@Composable
private fun Bell(badge: String?, onClick: () -> Unit) {
    Box {
        Box(
            Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(palette.cell)
                .clickable(role = Role.Button, onClick = onClick)
                .semantics { contentDescription = HomeTexts.NOTIFICATIONS + (badge?.let { ", $it unread" } ?: "") },
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(CoreR.drawable.ic_shell_bell), null, modifier = Modifier.size(22.dp))
        }
        badge?.let { Box(Modifier.align(Alignment.TopEnd).padding(start = 30.dp)) { CountBadge(it, alert = true) } }
    }
}
