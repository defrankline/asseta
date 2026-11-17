package com.asseta.owner.ui.approvals

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.CustomerPaymentDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.CreditSale
import com.asseta.owner.data.ExceptionList
import com.asseta.owner.data.HandoverList
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.map
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.accountability.DecisionItem
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionRow
import com.asseta.owner.ui.cash.HandoverRow
import com.asseta.owner.ui.cash.HandoverText
import com.asseta.owner.ui.common.CardButtons
import com.asseta.owner.ui.common.CardDetail
import com.asseta.owner.ui.common.CardGap
import com.asseta.owner.ui.common.CardTitle
import com.asseta.owner.ui.common.ChipRow
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.ItemCard
import com.asseta.owner.ui.common.KindLine
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.exceptions.ExceptionApprovalRow
import com.asseta.owner.ui.exceptions.ExceptionReviewText
import com.asseta.owner.ui.reports.ReportPresentation
import com.asseta.owner.ui.reports.ReportTexts
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import java.time.ZoneId
import java.util.UUID

/** Expense requests waiting with their expenses by id (what was bought, from whom, receipt photos). */
@Serializable
data class ExpenseQueue(val requests: List<ApprovalRequestDto>, val expenses: Map<String, ExpenseDto> = emptyMap()) {
    fun expense(a: ApprovalRequestDto): ExpenseDto? = if (a.subjectType == "EXPENSE") expenses[a.subjectId.toString()] else null
}

/** A credit sale decision in progress or refused ([purchaseId] the order it belongs to). */
data class CreditError(val purchaseId: String, val message: String)

/**
 * Everything waiting for a decision (design OwnerApprovals): machine reports, credit sales and expense requests (the
 * three chips), then every other kind the role may decide under All. Each list loads on its own; [counts] feeds the
 * chips, the side menu badge and the Home tile. The shell and the Approvals screen share one instance per company.
 */
class ApprovalsViewModel(
    private val data: OwnerData,
    refreshOn: Flow<Unit>,
    meterResets: Boolean = false,
    handovers: Boolean = false,
    payments: Boolean = false,
    exceptions: Boolean = false,
    decisions: List<DecisionKind> = emptyList(),
    /** The role may read expense requests (`tenant.approval.read`); otherwise they are neither asked for nor shown. */
    val expenseRequests: Boolean = true,
    /** Petty cash fundings, top-ups and fund adjustments waiting for approval (read and approve, DEC-033). */
    pettyCash: Boolean = false,
    /** ADR-008: machine reports waiting (tenant.machine_report.read). */
    machineReports: Boolean = false,
    /** ADR-008: credit sales waiting to be made usable (tenant.hours.credit_activate, hours on). */
    creditSales: Boolean = false,
    /** Read the expenses behind the requests (tenant.expense.read) for their description and supplier. */
    expenseDetails: Boolean = false,
) : ViewModel() {
    private val selected = MutableStateFlow(ApprovalFilter.ALL)
    val filter: StateFlow<ApprovalFilter> = selected.asStateFlow()

    val expenses: Section<ExpenseQueue>? = if (expenseRequests) Section(viewModelScope) { data.expenseApprovals(expenseDetails) } else null
    val reports: Section<List<MachineReportDto>>? = if (machineReports) Section(viewModelScope) { data.pendingMachineReports() } else null
    val credit: Section<List<CreditSale>>? = if (creditSales) Section(viewModelScope) { data.creditSalesToApprove() } else null
    val resets: Section<List<MeterResetDto>>? = if (meterResets) Section(viewModelScope) { data.meterResets("PENDING") } else null
    val claimedHandovers: Section<HandoverList>? = if (handovers) Section(viewModelScope) { data.handovers(HandoverText.CLAIMED) } else null
    val claimedPayments: Section<PageDto<CustomerPaymentDto>>? = if (payments) Section(viewModelScope) { data.paymentsToConfirm() } else null
    val pettyCashQueue: Section<PettyCashQueue>? = if (pettyCash) Section(viewModelScope) { data.pettyCashToApprove() } else null
    val openExceptions: Section<ExceptionList>? = if (exceptions) Section(viewModelScope) { data.openExceptions() } else null

    /** Accountability requests waiting for a decision, one independently loaded section per kind the role may see. */
    val decisionSections: List<Pair<DecisionKind, Section<List<DecisionItem>>>> = decisions.map { k ->
        k to Section(viewModelScope) { data.decisions(k) }
    }

    private val sections: List<Section<*>> =
        listOfNotNull(expenses, reports, credit, resets, claimedHandovers, claimedPayments, pettyCashQueue, openExceptions) + decisionSections.map { it.second }

    /** Waiting items per chip (an unloaded list counts 0). */
    val counts: StateFlow<ApprovalCounts> =
        (if (sections.isEmpty()) flowOf(Unit) else combine(sections.map { it.state }) { }).map { currentCounts() }
            .stateIn(viewModelScope, SharingStarted.Eagerly, ApprovalCounts())

    private val _creditBusy = MutableStateFlow<String?>(null)
    val creditBusy: StateFlow<String?> = _creditBusy.asStateFlow()
    private val _creditError = MutableStateFlow<CreditError?>(null)
    val creditError: StateFlow<CreditError?> = _creditError.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        sections.forEach { it.refresh() }
        viewModelScope.launch { refreshOn.collect { refreshAll() } }
    }

    fun select(f: ApprovalFilter) {
        selected.value = f
    }

    fun refreshAll() = sections.forEach { it.refresh() }

    fun currentCounts(): ApprovalCounts {
        val creditDecisions = decisionSections.filter { it.first == DecisionKind.CREDIT }.sumOf { (_, s) -> s.state.value.data.orEmpty().count { it.pending } }
        val otherDecisions = decisionSections.filter { it.first != DecisionKind.CREDIT }.sumOf { (_, s) -> s.state.value.data.orEmpty().count { it.pending } }
        return ApprovalCounts(
            reports = reports?.state?.value?.data?.size ?: 0,
            credit = (credit?.state?.value?.data?.size ?: 0) + creditDecisions,
            expenses = expenses?.state?.value?.data?.requests?.size ?: 0,
            other = otherDecisions +
                (resets?.state?.value?.data?.size ?: 0) +
                (claimedHandovers?.state?.value?.data?.items?.size ?: 0) +
                (claimedPayments?.state?.value?.data?.items?.size ?: 0) +
                (pettyCashQueue?.state?.value?.data?.let { it.movements.size + it.adjustments.size } ?: 0) +
                (openExceptions?.state?.value?.data?.items?.size ?: 0),
        )
    }

    /** Make the order's waiting hours usable at once (as iOS: no reason asked); one Idempotency-Key per attempt. */
    fun approveCredit(sale: CreditSale) {
        val p = sale.purchase
        val hours = CreditSales.awaitingHours(p)
        if (_creditBusy.value != null || hours.signum() <= 0) return
        _creditBusy.value = p.id
        _creditError.value = null
        viewModelScope.launch {
            when (val r = data.approveCredit(p.id, hours.toPlainString(), ApprovalsTexts.CREDIT_APPROVED_REASON, UUID.randomUUID().toString())) {
                is ActionResult.Done -> {
                    _message.value = ApprovalsTexts.CREDIT_APPROVED
                    credit?.refresh()
                }
                is ActionResult.Refused -> {
                    _creditError.value = CreditError(p.id, ApprovalsTexts.creditRefusal(r.code, r.error.message))
                    if (r.reload || r.code == "EXCEEDS_UNACTIVATED_HOURS" || r.code == "PURCHASE_CANCELLED") credit?.refresh()
                }
            }
            _creditBusy.value = null
        }
    }

    /** Reject the credit part of [sale] with [reason] (owner decision); one Idempotency-Key per attempt. */
    fun rejectCredit(sale: CreditSale, reason: String) {
        val p = sale.purchase
        if (_creditBusy.value != null || !ApprovalsTexts.rejectReasonValid(reason)) return
        _creditBusy.value = p.id
        _creditError.value = null
        viewModelScope.launch {
            when (val r = data.rejectCredit(p.id, reason, UUID.randomUUID().toString())) {
                is ActionResult.Done -> {
                    _message.value = ApprovalsTexts.CREDIT_REJECTED
                    credit?.refresh()
                }
                is ActionResult.Refused -> {
                    _creditError.value = CreditError(p.id, ApprovalsTexts.creditRejectRefusal(r.code, r.error.message))
                    if (r.reload || ApprovalsTexts.creditRejectReloads(r.code)) credit?.refresh()
                }
            }
            _creditBusy.value = null
        }
    }
}

/** Chips the role sees: All, and each kind it can have waiting. */
fun approvalChips(vm: ApprovalsViewModel): List<ApprovalFilter> = listOfNotNull(
    ApprovalFilter.ALL,
    ApprovalFilter.MACHINE_REPORTS.takeIf { vm.reports != null },
    ApprovalFilter.CREDIT.takeIf { vm.credit != null || vm.decisionSections.any { it.first == DecisionKind.CREDIT } },
    ApprovalFilter.EXPENSES.takeIf { vm.expenses != null },
)

@Composable
fun ApprovalsScreen(vm: ApprovalsViewModel, session: OwnerSession, online: Boolean, nowMs: () -> Long, onOpen: (OwnerDestination) -> Unit) {
    val filter by vm.filter.collectAsStateWithLifecycle()
    val counts by vm.counts.collectAsStateWithLifecycle()
    val reports = vm.reports?.state?.collectAsStateWithLifecycle()?.value
    val credit = vm.credit?.state?.collectAsStateWithLifecycle()?.value
    val expenses = vm.expenses?.state?.collectAsStateWithLifecycle()?.value
    val resets = vm.resets?.state?.collectAsStateWithLifecycle()?.value
    val handovers = vm.claimedHandovers?.state?.collectAsStateWithLifecycle()?.value
    val payments = vm.claimedPayments?.state?.collectAsStateWithLifecycle()?.value
    val exceptions = vm.openExceptions?.state?.collectAsStateWithLifecycle()?.value
    val petty = vm.pettyCashQueue?.state?.collectAsStateWithLifecycle()?.value
    val decisions = vm.decisionSections.map { (kind, section) -> kind to section.state.collectAsStateWithLifecycle().value }
    val busy by vm.creditBusy.collectAsStateWithLifecycle()
    val creditError by vm.creditError.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    var rejecting by remember { mutableStateOf<CreditSale?>(null) }
    val zone = ZoneId.systemDefault()
    val now = nowMs()
    Column(Modifier.fillMaxSize()) {
        ChipRow(approvalChips(vm).map { it to counts.chip(it) }, filter, vm::select)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
            message?.let { m ->
                item(key = "message") {
                    Text(m, color = palette.accent, modifier = Modifier.padding(horizontal = 20.dp, vertical = 6.dp).semantics { liveRegion = LiveRegionMode.Polite })
                }
            }
            if (filter.shows(ApprovalKind.MACHINE_REPORT)) reports?.let { st ->
                cards("reports", st) { list ->
                    list.forEach { r ->
                        item(key = "mr-${r.id}") {
                            ItemCard(onClick = { onOpen(OwnerDestination.MachineReport(r.id)) }) {
                                KindLine(ReportTexts.KIND, Figures.relative(r.submittedAt, now, zone))
                                CardTitle(ReportPresentation.rowTitle(r))
                                CardDetail(ReportPresentation.split(r), accent = true)
                            }
                            CardGap()
                        }
                    }
                }
            }
            if (filter.shows(ApprovalKind.CREDIT)) {
                credit?.let { st ->
                    cards("credit", st) { list ->
                        list.forEach { sale ->
                            item(key = "cs-${sale.purchase.id}") {
                                // Reject asks for the reason (the credit invoice is cancelled); Approve credit makes the waiting
                                // hours usable at once.
                                CreditSaleCard(sale, session, online, st, busy, creditError, now, zone, { vm.approveCredit(sale) }) {
                                    rejecting = sale
                                }
                                CardGap()
                            }
                        }
                    }
                }
                decisions.filter { it.first == DecisionKind.CREDIT }.forEach { (kind, st) -> decisionGroup(kind, st, onOpen) }
            }
            if (filter.shows(ApprovalKind.EXPENSE)) expenses?.let { st ->
                cards("expenses", st) { q ->
                    q.requests.forEach { a ->
                        item(key = "ex-${a.id}") {
                            val e = q.expense(a)
                            ItemCard(onClick = { onOpen(OwnerDestination.Approvals(a.id.toString())) }) {
                                KindLine(ApprovalsTexts.EXPENSE_KIND, Figures.relative(a.requestedAt, now, zone))
                                CardTitle(ExpenseApprovals.title(a, e))
                                ExpenseApprovals.detail(a, e).takeIf { it.isNotBlank() }?.let { CardDetail(it) }
                            }
                            CardGap()
                        }
                    }
                }
            }
            if (filter == ApprovalFilter.ALL) {
                // Every other kind, as before ADR-008, in its own titled group.
                handovers?.let { h ->
                    sectionRows(h) { list ->
                        list.items.map { item -> GroupedItem(item.id.toString(), onClick = { onOpen(OwnerDestination.Handover(item.id.toString())) }) { HandoverRow(item, list.name(item), zone) } }
                    }?.let { groupedSection("handovers", it, header = HandoverText.SECTION) }
                }
                payments?.let { p ->
                    sectionRows(p) { page ->
                        page.items.map { item -> GroupedItem(item.id.toString(), onClick = { onOpen(OwnerDestination.CustomerPayment(item.id.toString())) }) { PaymentRow(item, zone) } }
                    }?.let { groupedSection("payments", it, header = PaymentReviewText.SECTION) }
                }
                petty?.data?.takeIf { it.isNotEmpty() }?.let { q ->
                    groupedSection(
                        "petty-cash",
                        q.movements.map { m -> GroupedItem("pm-${m.id}", onClick = { onOpen(OwnerDestination.PettyCashMovement(m.id.toString())) }) { PettyCashMovementRow(m, zone) } } +
                            q.adjustments.map { a -> GroupedItem("pa-${a.id}", onClick = { onOpen(OwnerDestination.PettyCashAdjustment(a.id.toString())) }) { PettyCashAdjustmentRow(a, zone) } },
                        header = PettyCashReviewText.SECTION,
                    )
                }
                exceptions?.let { x ->
                    sectionRows(x) { list ->
                        list.items.map { e -> GroupedItem(e.id.toString(), onClick = { onOpen(OwnerDestination.MeterException(e.id.toString())) }) { ExceptionApprovalRow(e, zone) } }
                    }?.let { groupedSection("exceptions", it, header = ExceptionReviewText.SECTION) }
                }
                resets?.let { r ->
                    sectionRows(r) { list ->
                        list.map { m -> GroupedItem(m.id.toString(), onClick = { onOpen(OwnerDestination.MeterReset(m.id.toString())) }) { MeterResetRow(m, zone) } }
                    }?.let { groupedSection("resets", it, header = MeterResetText.SECTION) }
                }
                decisions.filter { it.first != DecisionKind.CREDIT }.forEach { (kind, st) -> decisionGroup(kind, st, onOpen) }
            }
            if (counts.of(filter) == 0 && listOfNotNull(reports, credit, expenses, resets, handovers, payments, exceptions, petty).none { it.loading }) {
                item(key = "empty") { EmptyState(ApprovalsTexts.EMPTY_TITLE, ApprovalsTexts.EMPTY_MESSAGE, R.drawable.ic_approval) }
            }
        }
    }
    rejecting?.let { sale -> RejectCreditDialog(sale, onDismiss = { rejecting = null }) { reason -> vm.rejectCredit(sale, reason) } }
}

@Composable
private fun CreditSaleCard(
    sale: CreditSale,
    session: OwnerSession,
    online: Boolean,
    state: ScreenState<List<CreditSale>>,
    busy: String?,
    error: CreditError?,
    nowMs: Long,
    zone: ZoneId,
    onApprove: () -> Unit,
    onReject: () -> Unit,
) {
    val p = sale.purchase
    ItemCard {
        KindLine(ApprovalsTexts.CREDIT_KIND, Figures.relative(p.createdAt, nowMs, zone))
        CardTitle(CreditSales.title(p))
        CardDetail(CreditSales.detail(sale))
        val approve = session.can(OwnerAction.ACTIVATE_CREDIT, online, state.snapshot?.source)
        when {
            CreditSales.recordedBy(p, session.userId) -> FootNote(ApprovalsTexts.OWN_SALE)
            approve is MutationCheck.Blocked -> FootNote(approve.reason)
            else -> CardButtons(
                left = ApprovalsTexts.REJECT,
                right = ApprovalsTexts.APPROVE_CREDIT,
                enabled = busy == null,
                onLeft = onReject, onRight = onApprove,
            )
        }
        error?.takeIf { it.purchaseId == p.id }?.let {
            Text(it.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Assertive })
        }
    }
}

/** Cards of one independently loaded list: nothing while first loading, its error, or the items. */
private fun <T> LazyListScope.cards(key: String, state: ScreenState<T>, items: LazyListScope.(T) -> Unit) {
    val data = state.data
    when {
        data == null && state.loading -> Unit
        data == null -> item(key = "$key-error") { FootNote(state.error?.message.orEmpty()) }
        else -> items(data)
    }
}

/** Rows of an independently loaded group: none while loading or when empty (the group is then hidden), else the error or items. */
private fun <T> sectionRows(state: ScreenState<T>, items: (T) -> List<GroupedItem>): List<GroupedItem>? {
    val data = state.data
    return when {
        data == null && state.loading -> null
        data == null -> listOf(GroupedItem("error") { FootNote(state.error?.message.orEmpty()) })
        else -> items(data).ifEmpty { null }
    }
}

private fun LazyListScope.decisionGroup(kind: DecisionKind, st: ScreenState<List<DecisionItem>>, onOpen: (OwnerDestination) -> Unit) {
    val items = st.data.orEmpty().filter { it.pending }
    if (items.isNotEmpty()) {
        val zone = ZoneId.systemDefault()
        groupedSection(
            "decision-${kind.code}",
            items.map { d -> GroupedItem(d.id, onClick = { onOpen(OwnerDestination.Decision(kind.code, d.id)) }) { DecisionRow(d, zone) } },
            header = kind.header,
        )
    }
}
