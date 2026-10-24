package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.LaunchedEffect
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.supervisor.ui.accountability.MoneyAccountability
import com.asseta.supervisor.ui.accountability.cashToAcknowledgeSection
import com.asseta.supervisor.ui.accountability.transfersSection
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.model.sync.CashReconciliationDayDto
import com.asseta.core.sync.data.CashItem
import com.asseta.core.sync.data.CashToday
import com.asseta.core.sync.data.CashView
import com.asseta.core.sync.data.ExpenseItem
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.data.OnlineResult
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.ui.finance.CashFormViewModel
import com.asseta.supervisor.ui.finance.CustodySection
import com.asseta.supervisor.ui.finance.MyCashTexts
import java.time.LocalDate

/**
 * Money tab: my cash custody (synced balance apart from unsynced records), today's reconciliation (from the office when
 * online, else the office's figures saved on this phone or a clearly labelled estimate), then my expenses, cash collections and handovers with the office's
 * decisions. "+" opens the existing expense, collection and handover forms.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoneyScreen(
    field: FieldGraph,
    tenantId: String,
    snapshot: InboxSnapshot,
    syncing: Boolean,
    onRefresh: () -> Unit,
    onRoute: (Route) -> Unit,
    permissions: Set<String> = emptySet(),
    access: FieldAccess? = null,
) {
    val view by remember(tenantId) { field.financeRepository.observeCashView(tenantId) }.collectAsStateWithLifecycle(CashView(emptyList(), emptyList(), null))
    val currencies = view.lines.map { it.currency }
    val today by produceState<OnlineResult<CashToday>?>(null, currencies, syncing) {
        if (value == null) value = field.online.savedCash(tenantId) // until the first fetch finishes
        if (!syncing) value = field.online.todayCash(tenantId, currencies)
    }
    var segment by rememberSaveable { mutableStateOf(MoneySegment.EXPENSES) }
    // Transfers and floats waiting for me, my transfers (online, saved on this phone for offline use).
    val accountability by field.accountability.cache.collectAsStateWithLifecycle()
    val me by produceState<String?>(null, tenantId) { value = field.accountability.myStaffId(tenantId) }
    LaunchedEffect(tenantId, syncing) { if (!syncing) field.accountability.refresh(tenantId, permissions) }
    val cashChain = access?.transferCash == true
    val segments = MoneySegment.entries.filter { it != MoneySegment.TRANSFERS || cashChain }
    val ackRows = if (access?.acknowledgeCash == true) {
        MoneyAccountability.toAcknowledge(accountability, me, MoneyAccountability.answeredIds(snapshot.accountabilityOps))
    } else {
        emptyList()
    }
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (view.lines.isEmpty()) {
                item(key = "no-custody") { EmptyState("No cash balance yet", "Your cash custody appears here after a sync.") }
            }
            view.lines.forEach { line ->
                item(key = "custody-${line.currency}") {
                    Column(Modifier.padding(horizontal = 16.dp)) {
                        CustodySection(line)
                        TodaySection(line, TodayCash.figures(today, line.currency, LocalDate.now()))
                    }
                }
            }
            cashToAcknowledgeSection(ackRows, onRoute)
            item(key = "segments") {
                FilterChipRow(segments.map { it to it.label }, segment, { segment = it }, Modifier.padding(bottom = 8.dp))
            }
            when (segment) {
                MoneySegment.EXPENSES -> {
                    if (snapshot.loaded && snapshot.expenses.isEmpty()) {
                        item(key = "empty-e") { EmptyState("No expenses", "Expenses you record appear here with the office's decision.") }
                    }
                    InboxTexts.moneyGroups(snapshot.expenses) { it.status }.forEach { (title, items) ->
                        groupedSection(
                            keyPrefix = "e-$title", header = title,
                            items = items.map { e -> GroupedItem(e.key, onClick = { onRoute(Route.ExpenseDetail(e.key)) }) { ExpenseRow(e) } },
                        )
                    }
                }
                MoneySegment.COLLECTIONS -> cashList(snapshot.collections, snapshot.loaded, "No cash collections", "Cash you collect from customers appears here with the office's verification.", onRoute)
                MoneySegment.HANDOVERS -> cashList(snapshot.handovers, snapshot.loaded, "No cash handovers", "Cash you hand over to the office appears here with its verification.", onRoute)
                MoneySegment.TRANSFERS -> transfersSection(
                    MoneyAccountability.transfers(accountability, me, snapshot.accountabilityOps, field.inbox::payloadText), snapshot.loaded,
                )
            }
        }
    }
}

private fun androidx.compose.foundation.lazy.LazyListScope.cashList(
    items: List<CashItem>,
    loaded: Boolean,
    emptyTitle: String,
    emptyMessage: String,
    onRoute: (Route) -> Unit,
) {
    if (loaded && items.isEmpty()) item(key = "empty-cash") { EmptyState(emptyTitle, emptyMessage) }
    InboxTexts.moneyGroups(items) { it.status }.forEach { (title, group) ->
        groupedSection(
            keyPrefix = "c-$title", header = title,
            items = group.map { c -> GroupedItem(c.key, onClick = { onRoute(Route.CashDetail(c.key, c.isCollection)) }) { CashRow(c) } },
        )
    }
}

/**
 * Today's figures: the office's reconciliation when online; offline the copy saved on this phone (today's in full with
 * what this phone has not synced yet, an earlier day's outstanding only), else the offline estimate (clearly labelled).
 */
@Composable
private fun TodaySection(line: CustodyLine, figures: TodayFigures) {
    val c = line.currency
    val header = TodayCash.header(figures)
    when (figures) {
        TodayFigures.Estimate -> Section(header, footer = InboxTexts.ESTIMATE_FOOTER) {
            LabeledRow("Estimated cash in hand", MyCashTexts.money(line.estimatedInHand, c), WarningColor)
        }
        is TodayFigures.Live -> Section(header, footer = InboxTexts.RECONCILIATION_FOOTER) { OfficeRows(figures.day, c) }
        is TodayFigures.SavedToday -> {
            Section(header, footer = TodayCash.SAVED_FOOTER) { OfficeRows(figures.day, c) }
            val notSynced = TodayCash.notSynced(line)
            if (notSynced.isNotEmpty()) {
                Section(TodayCash.NOT_SYNCED) {
                    notSynced.forEach { (label, amount) -> LabeledRow(label, amount) }
                    LabeledRow("Estimated cash in hand", MyCashTexts.money(line.estimatedInHand, c), WarningColor)
                }
            }
        }
        is TodayFigures.SavedEarlier -> Section(header, footer = InboxTexts.ESTIMATE_FOOTER) {
            LabeledRow("Outstanding", "") {
                Text(InboxTexts.money(figures.day.outstanding, c), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
            LabeledRow("Estimated cash in hand", MyCashTexts.money(line.estimatedInHand, c), WarningColor)
        }
    }
}

/** The office's reconciliation of one day (online, or as saved on this phone today). */
@Composable
private fun OfficeRows(day: CashReconciliationDayDto, c: String) {
    LabeledRow("Opening balance", InboxTexts.money(day.opening, c))
    LabeledRow("Floats issued", InboxTexts.money(day.floatsIssued, c))
    LabeledRow("Collections", InboxTexts.money(day.collections, c))
    LabeledRow("Approved spending", InboxTexts.money(day.approvedSpending, c))
    LabeledRow("Verified handovers", InboxTexts.money(day.verifiedHandovers, c))
    LabeledRow("Outstanding", "") {
        Text(InboxTexts.money(day.outstanding, c), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
    }
    if (day.claimedUnverifiedHandovers.toBigDecimalOrNull()?.signum() != 0) {
        LabeledRow("Handed over, awaiting verification", InboxTexts.money(day.claimedUnverifiedHandovers, c))
    }
    if (day.unverifiedCollections.toBigDecimalOrNull()?.signum() != 0) {
        LabeledRow("Collections awaiting verification", InboxTexts.money(day.unverifiedCollections, c))
    }
    if (day.pendingSpending.toBigDecimalOrNull()?.signum() != 0) {
        LabeledRow("Expenses awaiting approval", InboxTexts.money(day.pendingSpending, c))
    }
}

@Composable
private fun ExpenseRow(e: ExpenseItem) {
    InboxRow(
        e.description.ifBlank { "Expense" }, e.status,
        InboxTexts.money(e.amount, e.currency) + " · " + InboxTexts.paidFrom(e.paidFrom),
        LocalTime.format(e.atMs),
        e.decisionNote?.let { "Office note: $it" },
    )
}

@Composable
private fun CashRow(c: CashItem) {
    InboxRow(
        InboxTexts.money(c.amount, c.currency), c.status,
        listOfNotNull(c.reference, c.note).joinToString(" · ").ifEmpty { null },
        LocalTime.format(c.atMs),
        c.decisionNote?.let { "Office note: $it" },
    )
}

/** One expense: amount, paid from, category, job/machine, receipts, the office's decision and sync state. */
@Composable
fun ExpenseDetailScreen(
    field: FieldGraph,
    snapshot: InboxSnapshot,
    key: String,
    permissions: Set<String>,
    onRecordExpense: () -> Unit,
    onRoute: (Route) -> Unit,
) {
    val e = snapshot.expenses.firstOrNull { it.key == key || it.serverId == key }
    if (e == null) {
        if (snapshot.loaded) EmptyState("Expense not available", "It is no longer on this phone.")
        return
    }
    val category by produceState<String?>(null, e.categoryId) { value = e.categoryId?.let { field.financeRepository.category(it)?.name } }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            LabeledRow("Status", "") { StatusPill(e.status) }
            LabeledRow("Amount", InboxTexts.money(e.amount, e.currency))
            LabeledRow("Paid from", InboxTexts.paidFrom(e.paidFrom))
            category?.let { LabeledRow("Category", it) }
            LabeledRow("Description", e.description)
            e.supplier?.let { LabeledRow("Supplier", it) }
            LabeledRow("When", LocalTime.format(e.atMs))
            e.jobId?.let(snapshot.jobs::get)?.let { LabeledRow("Job", it.jobNumber) }
            e.machineId?.let(snapshot.machines::get)?.let { LabeledRow("Machine", InboxTexts.machine(it.assetCode, it.name)) }
        }
        if (e.status == InboxStatus.APPROVED || e.status == InboxStatus.REJECTED) {
            Section("Office decision") {
                LabeledRow("Decision", e.status.label, toneColor(e.status.tone))
                e.decidedAtMs?.let { LabeledRow("Decided", LocalTime.format(it)) }
                Text(e.decisionNote ?: "No note.", style = AssetaType.subheadline)
            }
        }
        val serverId = e.serverId
        val op = e.op
        if (e.receiptAttachmentIds.isNotEmpty() || op != null) {
            Section("Receipts") {
                if (serverId != null && e.receiptAttachmentIds.isNotEmpty()) {
                    e.receiptAttachmentIds.forEachIndexed { i, id ->
                        EvidenceImage("Receipt ${i + 1}", local = null, remoteUrl = { field.online.receiptUrl(serverId, id) })
                    }
                } else if (op != null) {
                    val local by produceState<List<String>>(emptyList(), op.id) { value = field.inbox.attachmentsOf(op.id) }
                    if (local.isEmpty()) Text("No receipt photo.", style = AssetaType.footnote, color = palette.secondaryText)
                    local.forEachIndexed { i, lid -> EvidenceImage("Receipt ${i + 1}", local = { field.inbox.localEvidence(lid) }, remoteUrl = null) }
                }
            }
        }
        op?.let {
            Section("Sync") {
                LabeledRow("On this phone", "") { SyncStateLabel(it.status) }
                it.errorCode?.let { code -> Text("$code: ${it.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline) }
            }
        }
        if (e.status == InboxStatus.REJECTED && "tenant.expense.write" in permissions) {
            Section(null, footer = "A rejected expense stays rejected. Record a new one if the office asked you to correct it.") {
                ActionRow("Record a new expense", R.drawable.ic_receipt, onClick = onRecordExpense)
            }
        }
        val fuel = serverId?.let { id -> snapshot.fuel.filter { it.expenseId == id } }.orEmpty()
        if (fuel.isNotEmpty()) {
            Section("Fuel") {
                fuel.forEach { f -> LinkActionRow("Fuel ${InboxTexts.fuelType(f.eventType).lowercase()} · ${InboxTexts.litres(f.litres)}") { onRoute(Route.FuelDetail(f.key)) } }
            }
        }
    }
}

/** One cash collection or handover: amount, reference, the office's verification and sync state. */
@Composable
fun CashDetailScreen(
    field: FieldGraph,
    tenantId: String,
    snapshot: InboxSnapshot,
    key: String,
    collection: Boolean,
    permissions: Set<String>,
    onRoute: (Route) -> Unit,
) {
    val items = if (collection) snapshot.collections else snapshot.handovers
    val c = items.firstOrNull { it.key == key }
    if (c == null) {
        if (snapshot.loaded) EmptyState(if (collection) "Collection not available" else "Handover not available", "It is no longer on this phone.")
        return
    }
    val customers by remember(tenantId) { field.financeRepository.observeCustomers(tenantId) }.collectAsStateWithLifecycle(emptyList())
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            LabeledRow("Status", "") { StatusPill(c.status) }
            LabeledRow("Amount", InboxTexts.money(c.amount, c.currency))
            if (collection) LabeledRow("Customer", customers.firstOrNull { it.id == c.customerId }?.name ?: "Customer")
            c.reference?.let { LabeledRow("Reference", it) }
            LabeledRow(if (collection) "Received" else "Handed over", LocalTime.format(c.atMs))
            if (c.allocations > 0) LabeledRow("Allocated to invoices", "${c.allocations}")
        }
        c.note?.let { Section("Note") { Text(it, style = AssetaType.subheadline) } }
        if (c.status == InboxStatus.VERIFIED || c.status == InboxStatus.REJECTED) {
            Section("Office decision") {
                LabeledRow("Decision", c.status.label, toneColor(c.status.tone))
                c.verifiedAtMs?.let { LabeledRow("Decided", LocalTime.format(it)) }
                Text(c.decisionNote ?: "No note.", style = AssetaType.subheadline)
            }
        }
        c.op?.let {
            Section("Sync") {
                LabeledRow("On this phone", "") { SyncStateLabel(it.status) }
                it.errorCode?.let { code -> Text("$code: ${it.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline) }
            }
        }
        if (c.status == InboxStatus.REJECTED && "tenant.collection.record" in permissions) {
            Section(null) {
                if (collection) {
                    ActionRow("Record cash collection", R.drawable.ic_banknote) { onRoute(Route.CashForm(CashFormViewModel.COLLECTION)) }
                } else {
                    ActionRow("Hand over cash again", R.drawable.ic_hand_over) { onRoute(Route.CashForm(CashFormViewModel.HANDOVER)) }
                }
            }
        }
    }
}
