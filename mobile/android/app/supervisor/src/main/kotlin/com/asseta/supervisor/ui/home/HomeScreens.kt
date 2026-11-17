package com.asseta.supervisor.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.HoursPurchasePayload
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.sync.data.CashView
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.data.MachineReportView
import com.asseta.core.sync.data.ReportMachine
import com.asseta.core.ui.R as CoreR
import com.asseta.core.ui.shell.ActionTile
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.Greeting
import com.asseta.core.ui.shell.PeriodTabs
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.PrimaryAction
import com.asseta.core.ui.shell.SecondaryAction
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.shell.SummaryFigure
import com.asseta.core.ui.shell.SummaryStrip
import com.asseta.core.ui.shell.TileGrid
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.MapListSwitch
import com.asseta.supervisor.ui.MyMachinesMap
import com.asseta.core.map.FleetMapRules
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.report.ReportTexts
import com.asseta.supervisor.ui.rememberOnline
import kotlinx.serialization.json.Json
import java.math.BigDecimal

private val H = HomeTexts

/** What Home, Money and Dashboard show, from the phone's synced snapshots and its queued operations. */
data class ShellData(
    val sales: List<SaleRecord> = emptyList(),
    val reports: MachineReportView = MachineReportView(),
    val machines: List<ReportMachine> = emptyList(),
    val cash: List<CustodyLine> = emptyList(),
    val handovers: List<Movement> = emptyList(),
    val expenses: List<Movement> = emptyList(),
) {
    val currency: String? get() = cash.firstOrNull()?.currency
    val due: Int get() = machines.count { it.state.needsReport }
    val awaiting: Int get() = machines.count { it.state == ReportState.AWAITING_APPROVAL }

    companion object {
        private val SETTLED = setOf(InboxStatus.VERIFIED, InboxStatus.ACCEPTED, InboxStatus.APPROVED, InboxStatus.RECORDED, InboxStatus.REVIEWED)

        fun of(
            snapshot: InboxSnapshot,
            reports: MachineReportView,
            reminderDays: Int?,
            cash: CashView,
            customerNames: Map<String, String>,
            json: Json,
        ): ShellData = ShellData(
            sales = snapshot.accountabilityOps.filter { it.opType == AccountabilityOps.HOURS_PURCHASE }.mapNotNull { op ->
                runCatching { json.decodeFromString(HoursPurchasePayload.serializer(), op.payloadJson) }.getOrNull()?.let { p ->
                    ShellModel.sale(op.id, op.createdAtDevice, op.status, p) { customerNames[it] }
                }
            },
            reports = reports,
            machines = reports.machines(reminderDays),
            cash = cash.lines,
            handovers = snapshot.handovers.map { Movement(it.atMs, it.amount.toBigDecimalOrNull() ?: BigDecimal.ZERO, it.status !in SETTLED) },
            expenses = snapshot.expenses.map { Movement(it.atMs, it.amount.toBigDecimalOrNull() ?: BigDecimal.ZERO, it.status !in SETTLED) },
        )
    }
}

/** Home (approved design Main): greeting, summary strip, the four tiles and the recent list. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    displayName: String?,
    company: String,
    access: FieldAccess?,
    data: ShellData,
    syncing: Boolean,
    onRefresh: () -> Unit,
    notice: String?,
    onRoute: (Route) -> Unit,
    top: @Composable () -> Unit,
) {
    val now = System.currentTimeMillis()
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
            top()
            Greeting(com.asseta.core.ui.shell.ShellText.greeting(displayName), company)
            notice?.let { Box(Modifier.padding(start = 20.dp, end = 20.dp, bottom = 12.dp)) { com.asseta.supervisor.ui.NoticeCard(company, it) } }
            val cash = data.cash.firstOrNull()
            SummaryStrip(
                listOfNotNull(
                    SummaryFigure(H.CASH_IN_HAND, cash?.let { ShellModel.compact(it.estimatedInHand) } ?: "—"),
                    SummaryFigure(H.HOURS_TO_REPORT, ReportTexts.machines(data.due), accent = data.due > 0).takeIf { access?.machineReport == true },
                    SummaryFigure(H.AWAITING_APPROVAL, data.awaiting.toString()).takeIf { access?.machineReport == true },
                ),
            )
            SectionLabel(H.WHAT_TO_DO)
            TileGrid(
                ShellModel.tiles(access).map { item ->
                    @Composable { m: Modifier ->
                        when (item) {
                            MenuItem.SELL_HOURS -> ActionTile(item.label, H.SELL_HOURS_SUB, CoreR.drawable.ic_shell_sell_hours, m, primary = true) { onRoute(Route.HoursSale) }
                            MenuItem.MACHINE_REPORT -> ActionTile(item.label, H.MACHINE_REPORT_SUB, CoreR.drawable.ic_shell_machine_report, m, badge = ReportTexts.dueBadge(data.due)) { onRoute(Route.MachineReport()) }
                            MenuItem.MONEY -> ActionTile(item.label, H.MONEY_SUB, CoreR.drawable.ic_shell_money, m) { onRoute(Route.Money) }
                            else -> ActionTile(item.label, H.DASHBOARD_SUB, CoreR.drawable.ic_shell_dashboard, m) { onRoute(Route.Dashboard) }
                        }
                    }
                },
            )
            SectionLabel(H.RECENT)
            val rows = recent(data, now)
            ShellCard(padding = false) {
                if (rows.isEmpty()) Text(H.NO_RECENT, color = palette.secondaryText, modifier = Modifier.padding(16.dp))
                rows.forEachIndexed { i, r ->
                    CardRow(r.title, r.subtitle, last = i == rows.lastIndex, onClick = {
                        if (r.key.startsWith("report-")) onRoute(Route.MyReports) else onRoute(Route.MySales)
                    }) { StatusPill(r.pill, tone(r.tone)) }
                }
            }
        }
    }
}

fun tone(t: RecentTone) = when (t) {
    RecentTone.WAITING -> PillTone.WAITING
    RecentTone.GOOD -> PillTone.GOOD
    RecentTone.BAD -> PillTone.BAD
    RecentTone.NEUTRAL -> PillTone.NEUTRAL
}

/** Newest first: my reports (the server's and those still on this phone) and my sales; at most four. */
fun recent(data: ShellData, now: Long, limit: Int = 4): List<RecentRow> = (reportRows(data, now) + data.sales.map { ShellModel.recentSale(it, data.currency, now) })
    .sortedByDescending { it.atMs }.take(limit)

fun reportRows(data: ShellData, now: Long): List<RecentRow> {
    val server = data.reports.myReports.map { r ->
        val at = runCatching { IsoTime.parse(r.submittedAt).toEpochMilli() }.getOrDefault(0L)
        val tone = when (r.status) {
            MachineReportDto.APPROVED -> RecentTone.GOOD
            MachineReportDto.REJECTED -> RecentTone.BAD
            else -> RecentTone.WAITING
        }
        RecentRow("report-${r.id}", at, ReportTexts.recentReport(r.machineCode ?: r.machineName ?: "Machine", r.hours.toBigDecimalOrNull()?.takeUnless { r.isOpening }),
            ShellModel.when_(at, now), H.reportStatus(r.status), tone)
    }
    val local = data.reports.local.filter { l -> data.reports.myReports.none { it.id == l.operationId } }.map { l ->
        val code = data.machines.firstOrNull { it.id == l.machineId }?.code ?: "Machine"
        val refused = l.refused
        RecentRow("report-${l.operationId}", l.createdAtMs, ReportTexts.recentReport(code, l.hours.takeIf { it.signum() > 0 }),
            ShellModel.when_(l.createdAtMs, now), if (refused) H.NOT_SYNCED else if (l.waiting) H.WAITING_TO_SYNC else H.AWAITING_APPROVAL,
            if (refused) RecentTone.BAD else RecentTone.WAITING)
    }
    return server + local
}

/** Money (approved design Money): cash in hand, collections by method, handed over, expenses and the actions. */
@Composable
fun MoneyHomeScreen(data: ShellData, access: FieldAccess?, permissions: Set<String>, onRoute: (Route) -> Unit, onExpense: () -> Unit) {
    var period by rememberSaveable { mutableStateOf(Period.TODAY) }
    val now = System.currentTimeMillis()
    val f = ShellModel.money(period.range(now), data.sales, data.reports.invoicePayments, data.handovers, data.expenses)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        PeriodTabs(Period.entries.map { it to it.label }, period, { period = it })
        ShellCard {
            Text(H.CASH_IN_HAND_CAPS.uppercase(), fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = palette.secondaryText)
            val line = data.cash.firstOrNull()
            Text(line?.let { ShellModel.money(it.estimatedInHand, it.currency) } ?: H.NO_CASH, fontSize = 28.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
            Text(H.cashFormula(ShellModel.grouped(f.collected), ShellModel.grouped(f.handedOver), ShellModel.grouped(f.expenses)),
                style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(top = 4.dp))
        }
        SectionLabel(H.COLLECTIONS_BY_METHOD)
        ShellCard(padding = false) {
            val rows = listOf(PaymentMethod.CASH to H.CASH, PaymentMethod.BANK to H.BANK, PaymentMethod.MOBILE_MONEY to H.MOBILE_MONEY, PaymentMethod.CREDIT to H.CREDIT)
            rows.forEach { (m, label) ->
                CardRow(label + (if (m == PaymentMethod.CREDIT) H.CREDIT_AWAITING else ""), last = false) { Text(ShellModel.grouped(f.byMethod.getValue(m)), fontWeight = FontWeight.SemiBold) }
            }
            CardRow(H.TOTAL_SOLD, last = true) { Text(ShellModel.grouped(f.totalSold), fontWeight = FontWeight.Bold) }
        }
        ShellCard(padding = false) {
            CardRow(H.HANDED_OVER, H.AWAITING_CHECK.takeIf { f.handedOverAwaiting > 0 }, last = false) { Text(ShellModel.grouped(f.handedOver), fontWeight = FontWeight.SemiBold) }
            CardRow(H.EXPENSES, H.receipts(f.expenseCount, f.expensePending), last = true) { Text(ShellModel.grouped(f.expenses), fontWeight = FontWeight.SemiBold) }
        }
        Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if ("tenant.collection.record" in permissions) {
                Box(Modifier.weight(1f).height(52.dp).clip(RoundedCornerShape(16.dp)).background(palette.accent)) {
                    androidx.compose.material3.TextButton(onClick = { onRoute(Route.CashForm(com.asseta.supervisor.ui.finance.CashFormViewModel.HANDOVER)) }, modifier = Modifier.fillMaxSize()) {
                        Text(H.HAND_OVER, color = com.asseta.core.ui.theme.AssetaColors.OnAmber, fontWeight = FontWeight.Bold)
                    }
                }
            }
            if (ShellModel.EXPENSE_WRITE in permissions) SecondaryAction(H.EXPENSE, modifier = Modifier.weight(1f), onClick = onExpense)
            if (access?.pettyCash == true) SecondaryAction(H.PETTY_CASH, modifier = Modifier.weight(1f)) { onRoute(Route.PettyCash) }
        }
        if (access?.creditInvoicePayment == true) PrimaryAction(H.RECORD_INVOICE_PAYMENT) { onRoute(Route.InvoicePayment()) }
        ShellCard(padding = false) { CardRow(H.MONEY_RECORDS, last = true, onClick = { onRoute(Route.MoneyRecords) }) }
        Text(H.MONEY_FOOTER, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(horizontal = 20.dp))
    }
}

/** Dashboard (approved design Dashboard): hours sold / used, productive vs non-productive, my machines (list / map), reports. */
@Composable
fun DashboardScreen(field: FieldGraph, tenantId: String, data: ShellData, permissions: Set<String>, onRoute: (Route) -> Unit) {
    var period by rememberSaveable { mutableStateOf(Period.WEEK) }
    var showMap by rememberSaveable { mutableStateOf(false) }
    val now = System.currentTimeMillis()
    val d = ShellModel.dashboard(period.range(now), data.sales, data.reports.myReports, data.reports.local) { runCatching { IsoTime.parse(it).toEpochMilli() }.getOrNull() }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        PeriodTabs(Period.entries.map { it to it.label }, period, { period = it })
        Row(Modifier.padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Figure(H.HOURS_SOLD, "${MachineReportRules.formatHours(d.hoursSold)} h", listOfNotNull(data.currency, ShellModel.compact(d.soldAmount)).joinToString(" "), Modifier.weight(1f))
            Figure(H.HOURS_USED, "${MachineReportRules.formatHours(d.hoursUsed)} h", H.FROM_BOUGHT, Modifier.weight(1f))
        }
        ShellCard {
            Text(H.machineHours(period), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
            Text("${MachineReportRules.formatHours(d.machineHours)} h", fontSize = 26.sp, fontWeight = FontWeight.Bold)
            val share = if (d.machineHours.signum() > 0) d.productive.toFloat() / d.machineHours.toFloat() else 0f
            Row(Modifier.padding(top = 10.dp).fillMaxWidth().height(12.dp).clip(RoundedCornerShape(999.dp)).background(palette.raised)) {
                if (share > 0f) Box(Modifier.weight(share.coerceAtLeast(0.001f)).fillMaxSize().background(palette.accent))
                if (share < 1f) Box(Modifier.weight((1f - share).coerceAtLeast(0.001f)).fillMaxSize())
            }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Legend(palette.accent, H.productive(MachineReportRules.formatHours(d.productive), d.productivePercent))
                Legend(palette.secondaryText, H.nonProductive(MachineReportRules.formatHours(d.nonProductive)))
            }
        }
        SectionLabel(H.MY_MACHINES)
        // The Map / List switch only with the machine map permission (strings doc "Supervisor — map of my machines").
        val canMap = FleetMapRules.canShowMap(permissions)
        if (canMap) Box(Modifier.padding(horizontal = 20.dp)) { MapListSwitch(showMap, { showMap = it }) }
        if (showMap && canMap) {
            MyMachinesMap(field, tenantId, rememberOnline(), 0, Modifier.padding(horizontal = 20.dp).fillMaxWidth().height(320.dp).clip(RoundedCornerShape(18.dp)))
        } else {
            ShellCard(padding = false) {
                if (data.machines.isEmpty()) Text(ReportTexts.NO_MACHINES, color = palette.secondaryText, modifier = Modifier.padding(16.dp))
                data.machines.forEachIndexed { i, m ->
                    val at = (m.status.lastReportAt ?: m.status.previousAt)?.let { runCatching { IsoTime.parse(it).toEpochMilli() }.getOrNull() }
                    CardRow(m.label, H.lastReading(m.previous?.let { MachineReportRules.formatHours(it) }, ShellModel.ago(at, now)), last = i == data.machines.lastIndex,
                        onClick = { onRoute(Route.MachineReport(m.id)) }) { StatusPill(ReportTexts.state(m.state), stateTone(m.state)) }
                }
            }
        }
        SectionLabel(H.REPORTS)
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SecondaryAction(H.CUSTOMER_BALANCES, modifier = Modifier.weight(1f)) { onRoute(Route.CustomerBalances) }
                SecondaryAction(H.MY_REPORTS, modifier = Modifier.weight(1f)) { onRoute(Route.MyReports) }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SecondaryAction(H.MY_SALES, modifier = Modifier.weight(1f)) { onRoute(Route.MySales) }
                SecondaryAction(H.MY_CASH, modifier = Modifier.weight(1f)) { onRoute(Route.MoneyRecords) }
            }
        }
    }
}

fun stateTone(s: ReportState) = when (s) {
    ReportState.AWAITING_APPROVAL -> PillTone.WAITING
    ReportState.DUE, ReportState.OPENING -> PillTone.ACCENT
    ReportState.REJECTED -> PillTone.BAD
    ReportState.UP_TO_DATE -> PillTone.GOOD
}

@Composable
private fun Figure(label: String, value: String, detail: String, modifier: Modifier) {
    Column(modifier.clip(RoundedCornerShape(18.dp)).background(palette.cell).padding(16.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
        Text(value, fontSize = 22.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
        Text(detail, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
    }
}

@Composable
private fun Legend(color: androidx.compose.ui.graphics.Color, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(10.dp).clip(RoundedCornerShape(3.dp)).background(color))
        Text(text, style = MaterialTheme.typography.bodySmall)
    }
}

/** My machine reports (the server's of the last 30 days and those still on this phone). */
@Composable
fun MyReportsScreen(data: ShellData, onRoute: (Route) -> Unit) {
    val now = System.currentTimeMillis()
    val rows = reportRows(data, now).sortedByDescending { it.atMs }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp)) {
        ShellCard(padding = false) {
            if (rows.isEmpty()) Text(H.NO_REPORTS, color = palette.secondaryText, modifier = Modifier.padding(16.dp))
            rows.forEachIndexed { i, r ->
                val id = r.key.removePrefix("report-")
                val report = data.reports.myReports.firstOrNull { it.id == id }
                val detail = report?.let { rep ->
                    listOfNotNull(
                        ReportTexts.readings(rep.startReading, rep.endReading, rep.isOpening),
                        rep.decisionNote?.takeIf { rep.status == MachineReportDto.REJECTED },
                    ).joinToString(" · ")
                } ?: data.reports.local.firstOrNull { it.operationId == id }?.let { ReportTexts.conflict(it.errorCode) ?: it.error }
                CardRow(r.title, r.subtitle, last = i == rows.lastIndex, detail = detail, onClick = {
                    (report?.machineId ?: data.reports.local.firstOrNull { it.operationId == id }?.machineId)?.let { onRoute(Route.MachineReport(it)) }
                }) { StatusPill(r.pill, tone(r.tone)) }
            }
        }
    }
}

/** My hours sales recorded on this phone. */
@Composable
fun MySalesScreen(data: ShellData) {
    val now = System.currentTimeMillis()
    val rows = data.sales.sortedByDescending { it.atMs }.map { ShellModel.recentSale(it, data.currency, now) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp)) {
        ShellCard(padding = false) {
            if (rows.isEmpty()) Text(H.NO_SALES, color = palette.secondaryText, modifier = Modifier.padding(16.dp))
            rows.forEachIndexed { i, r -> CardRow(r.title, r.subtitle, last = i == rows.lastIndex) { StatusPill(r.pill, tone(r.tone)) } }
        }
    }
}

/** Customers with usable hours (the machine report snapshot), offline. */
@Composable
fun CustomerBalancesScreen(data: ShellData) {
    val rows = data.reports.hours.groupBy { it.customerId }.map { (id, list) ->
        Triple(id, list.firstNotNullOfOrNull { it.customerName } ?: id.take(8), list.fold(BigDecimal.ZERO) { s, r -> s + (r.available.toBigDecimalOrNull() ?: BigDecimal.ZERO) })
    }.sortedBy { it.second.lowercase() }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ShellCard(padding = false) {
            if (rows.isEmpty()) Text(H.NO_BALANCES, color = palette.secondaryText, modifier = Modifier.padding(16.dp))
            rows.forEachIndexed { i, (_, name, h) -> CardRow(name, last = i == rows.lastIndex) { Text(H.hoursLeft(MachineReportRules.formatHours(h)), fontWeight = FontWeight.SemiBold) } }
        }
        Text(H.BALANCES_FOOTER, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(horizontal = 20.dp))
    }
}

