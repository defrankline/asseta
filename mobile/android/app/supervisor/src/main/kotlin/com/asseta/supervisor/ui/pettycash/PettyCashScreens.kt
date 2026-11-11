package com.asseta.supervisor.ui.pettycash

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.DepositAccountOption
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.finance.PettyCashPolicy
import com.asseta.core.domain.finance.PettyCashRules
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.PersonDto
import com.asseta.core.model.sync.PettyCashOps
import com.asseta.core.sync.data.PettyCashRepository
import com.asseta.core.sync.data.PettyCashView
import com.asseta.core.sync.usecase.PettyCashCountRequest
import com.asseta.core.sync.usecase.PettyCashEntities
import com.asseta.core.sync.usecase.PettyCashReturnRequest
import com.asseta.core.sync.usecase.PettyCashTopUpRequest
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.ui.ActionRow
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LinkActionRow
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.NoticeCard
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.SyncStateLabel
import com.asseta.supervisor.ui.WarningColor
import com.asseta.supervisor.ui.accountability.EvidencePhotos
import com.asseta.supervisor.ui.accountability.FormColumn
import com.asseta.supervisor.ui.finance.DecimalField
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SaveSection
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.SearchablePickerField
import com.asseta.supervisor.ui.finance.SegmentedChoice
import com.asseta.supervisor.ui.finance.TextInput
import com.asseta.supervisor.ui.finance.after
import com.asseta.core.sync.usecase.FinanceResult
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

private val T = PettyCashTexts

/** The Money tab's "Petty cash" section: one row to My petty cash, with how many items wait for me. */
fun LazyListScope.pettyCashSection(waiting: Int, onRoute: (Route) -> Unit) {
    item(key = "petty-cash") {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Section(T.SECTION, footer = if (waiting > 0) T.rowWaiting(waiting) else null) {
                LinkActionRow(T.ROW, R.drawable.ic_wallet) { onRoute(Route.PettyCash) }
            }
        }
    }
}

/**
 * Base of the petty cash screens: the snapshot on this phone (funds, waiting items, advances, this phone's records),
 * my staff id and the synced `PETTY_CASH` policy. Works offline; [clientId] is generated once per visit.
 */
open class PettyCashViewModel(protected val field: FieldGraph, protected val tenantId: String) : ViewModel() {
    protected val clientId: String = UUID.randomUUID().toString()
    private val _me = MutableStateFlow<String?>(null)
    val me: StateFlow<String?> = _me.asStateFlow()
    private val _policy = MutableStateFlow(PettyCashPolicy())
    val policy: StateFlow<PettyCashPolicy> = _policy.asStateFlow()
    protected val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    val view: StateFlow<PettyCashView> = _me.flatMapLatest { me -> field.pettyCash.observe(tenantId, me) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), PettyCashView())

    init {
        viewModelScope.launch {
            _me.value = field.accountability.myStaffId(tenantId)
            _policy.value = field.pettyCash.policy(tenantId)
        }
    }

    protected fun saving(): Boolean {
        if (_save.value.saving || _save.value.saved) return true
        _save.update { it.copy(saving = true, messages = emptyList()) }
        return false
    }

    protected fun finish(result: FinanceResult) = _save.update { it.after(result) }

    fun clearMessages() = _save.update { it.copy(messages = emptyList()) }
}

/** My petty cash: funds with the server's figures and actions, what waits for me, advances and this phone's records. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyPettyCashScreen(vm: PettyCashViewModel, access: FieldAccess?, syncing: Boolean, onRefresh: () -> Unit, onRoute: (Route) -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val policy by vm.policy.collectAsStateWithLifecycle()
    val me by vm.me.collectAsStateWithLifecycle()
    if (access?.pettyCash != true) {
        FormColumn { NoticeCard(T.TITLE, T.UNAVAILABLE, isError = true) }
        return
    }
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (view.loaded && view.funds.isEmpty() && view.waitingCount == 0 && view.advances.isEmpty()) {
                item(key = "empty") { EmptyState(T.EMPTY_TITLE, T.EMPTY_MESSAGE) }
            }
            if (view.waitingCount > 0) {
                groupedSection(
                    keyPrefix = "waiting", header = T.WAITING,
                    items = view.awaiting.map { m -> GroupedItem("m-${m.id}", onClick = { onRoute(Route.PettyCashAck(m.id)) }) { Text(T.waitingMovement(m)) } } +
                        view.holderChanges.map { c -> GroupedItem("h-${c.id}", onClick = { onRoute(Route.PettyCashHolderChange(c.id)) }) { Text(T.waitingHolderChange(c)) } },
                )
            }
            view.funds.forEach { f ->
                item(key = "fund-${f.id}") {
                    Column(Modifier.padding(horizontal = 16.dp)) {
                        val b = f.balance
                        Section(T.fundHeader(f), footer = b?.let { T.asOf(LocalTime.formatIso(it.asOf)) }) {
                            if (b != null) {
                                LabeledRow(T.BALANCE, T.money(b.balance, f.currency))
                                LabeledRow(T.AVAILABLE, T.money(b.availableToSpend, f.currency))
                                if (T.nonZero(b.pendingSpending)) LabeledRow(T.PENDING_SPENDING, T.money(b.pendingSpending, f.currency))
                                if (T.nonZero(b.awaitingAcknowledgement)) LabeledRow(T.AWAITING_ACK, T.money(b.awaitingAcknowledgement, f.currency))
                                if (T.nonZero(b.returnsClaimed)) LabeledRow(T.RETURNS_CLAIMED, T.money(b.returnsClaimed, f.currency))
                                if (b.belowLowBalance) Text(T.LOW, color = WarningColor)
                                LabeledRow(T.LAST_COUNT, b.lastCountAt?.let(LocalTime::formatIso) ?: T.NOT_COUNTED)
                                b.nextCountDueAt?.let { LabeledRow(T.NEXT_COUNT, LocalTime.formatIso(it)) }
                            }
                            LabeledRow(T.LIMIT, T.money(f.approvedLimit, f.currency))
                            ActionRow(T.ACTION_TOP_UP) { onRoute(Route.PettyCashTopUp(f.id)) }
                            ActionRow(T.ACTION_RETURN) { onRoute(Route.PettyCashReturn(f.id)) }
                            if (access.pettyCashCount) ActionRow(T.ACTION_COUNT) { onRoute(Route.PettyCashCount(f.id)) }
                        }
                    }
                }
            }
            if (policy.advancesEnabled && view.advances.isNotEmpty()) {
                val clearable = PettyCashRepository.clearable(view, me).map { it.id }.toSet()
                groupedSection(
                    keyPrefix = "advances", header = T.ADVANCES,
                    items = view.advances.map { a ->
                        GroupedItem("a-${a.id}", onClick = if (a.id in clearable) ({ onRoute(Route.PettyCashAdvance(a.id)) }) else null) {
                            Column {
                                Text(T.advanceRow(a))
                                Text(T.advanceWho(a, me), color = palette.secondaryText)
                                Text(T.advanceDetail(a, LocalTime.formatIso(a.dueAt)), color = palette.secondaryText)
                                if (a.overdue) Text(T.ADVANCE_OVERDUE, color = WarningColor)
                            }
                        }
                    },
                )
            }
            if (view.records.isNotEmpty()) {
                groupedSection(
                    keyPrefix = "records", header = T.ON_PHONE,
                    items = view.records.map { r ->
                        GroupedItem("r-${r.operationId}") {
                            Column {
                                Text(T.recordTitle(r, view.fund(r.fundId)?.currency))
                                Text(LocalTime.format(r.createdAtMs), color = palette.secondaryText)
                                SyncStateLabel(r.status)
                                if (r.isRefused) Text(T.conflict(r.errorCode) ?: r.lastError.orEmpty(), color = palette.offline)
                            }
                        }
                    },
                )
            }
        }
    }
}

// --- Acknowledge a funding or top-up -------------------------------------------------------------------------------

class PettyCashAckViewModel(field: FieldGraph, tenantId: String, val movementId: String) : PettyCashViewModel(field, tenantId) {
    val received = MutableStateFlow<String?>(null)
    val note = MutableStateFlow("")
    private val _waiting = MutableStateFlow(false)
    val waiting: StateFlow<Boolean> = _waiting.asStateFlow()

    init {
        viewModelScope.launch { _waiting.value = field.pettyCashCapture.answered(tenantId, PettyCashEntities.ACK, movementId) }
    }

    fun answer(acknowledge: Boolean, declared: String) {
        if (saving()) return
        viewModelScope.launch { finish(field.pettyCashCapture.acknowledge(tenantId, movementId, acknowledge, received.value ?: declared, note.value)) }
    }
}

@Composable
fun PettyCashAckScreen(vm: PettyCashAckViewModel, access: FieldAccess?, onDone: () -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val waiting by vm.waiting.collectAsStateWithLifecycle()
    val received by vm.received.collectAsStateWithLifecycle()
    val note by vm.note.collectAsStateWithLifecycle()
    val m = view.awaiting.firstOrNull { it.id == vm.movementId }
    val editable = !save.saving && !save.saved && !waiting
    FormColumn {
        if (access?.pettyCash != true) return@FormColumn NoticeCard(T.TITLE_ACK, T.UNAVAILABLE, isError = true)
        if (waiting) return@FormColumn Section(null) { Text(T.ACK_WAITING, color = WarningColor) }
        if (m == null) {
            if (view.loaded && !save.saved) EmptyState(T.TITLE_ACK, T.NOT_FOUND)
            SaveSection(save, {}, onDone, enabled = false, label = T.ACKNOWLEDGE)
            return@FormColumn
        }
        Section(null) {
            Text(if (m.kind == PettyCashOps.FUNDING) T.ACK_FUNDING else T.ACK_TOP_UP)
            LabeledRow(T.FUND, m.fundName ?: view.fund(m.fundId)?.name.orEmpty())
            LabeledRow(T.ACK_NUMBER, m.number)
            LabeledRow(T.ACK_ISSUED, T.money(m.amount, m.currency))
            m.issuedAt?.let { LabeledRow(T.ACK_ISSUED_AT, LocalTime.formatIso(it)) }
            m.issuedByName?.takeIf { it.isNotBlank() }?.let { LabeledRow(T.ACK_ISSUED_BY, it) }
            m.reference?.takeIf { it.isNotBlank() }?.let { LabeledRow(T.ACK_REFERENCE, it) }
            m.note?.takeIf { it.isNotBlank() }?.let { Text(it, color = palette.secondaryText) }
        }
        Section(null, footer = T.ACK_FOOTER) {
            DecimalField(T.ACK_AMOUNT, received ?: m.amount, { v -> vm.received.value = v; vm.clearMessages() }, editable)
            TextInput(T.NOTE, note, { v -> vm.note.value = v }, editable, singleLine = false)
        }
        SaveSection(save, { vm.answer(true, m.amount) }, onDone, enabled = editable, label = T.ACKNOWLEDGE)
        OutlinedButton(onClick = { vm.answer(false, m.amount) }, enabled = editable && note.isNotBlank()) { Text(T.DISPUTE, color = palette.offline) }
        if (note.isBlank()) Text(T.DISPUTE_REASON, color = palette.secondaryText)
    }
}

// --- Request a top-up ----------------------------------------------------------------------------------------------

data class TopUpForm(val amount: String = "", val note: String = "", val aboveReason: String = "")

class PettyCashTopUpViewModel(field: FieldGraph, tenantId: String, val fundId: String) : PettyCashViewModel(field, tenantId) {
    val form = MutableStateFlow(TopUpForm())

    fun edit(change: (TopUpForm) -> TopUpForm) { form.update(change); clearMessages() }

    fun save() {
        val fund = view.value.fund(fundId) ?: return
        val headroom = PettyCashRules.headroom(fund.approvedLimit, fund.balance?.balance)
        if (saving()) return
        val f = form.value
        viewModelScope.launch { finish(field.pettyCashCapture.topUp(PettyCashTopUpRequest(tenantId, clientId, fundId, f.amount, f.note, f.aboveReason, headroom))) }
    }
}

@Composable
fun PettyCashTopUpScreen(vm: PettyCashTopUpViewModel, access: FieldAccess?, onDone: () -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val form by vm.form.collectAsStateWithLifecycle()
    val fund = view.fund(vm.fundId)
    val editable = !save.saving && !save.saved
    FormColumn {
        if (access?.pettyCash != true) return@FormColumn NoticeCard(T.TITLE_TOP_UP, T.UNAVAILABLE, isError = true)
        if (fund == null) {
            if (view.loaded && !save.saved) EmptyState(T.TITLE_TOP_UP, T.NOT_FOUND)
            SaveSection(save, {}, onDone, enabled = false, label = T.TOP_UP_SEND)
            return@FormColumn
        }
        val headroom = PettyCashRules.headroom(fund.approvedLimit, fund.balance?.balance)
        FundSummary(fund)
        Section(null, footer = T.TOP_UP_AMOUNT_FOOTER) {
            DecimalField(T.TOP_UP_AMOUNT, form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
        }
        if (PettyCashRules.aboveCap(form.amount, headroom)) {
            Section(null, footer = T.topUpAboveFooter(T.money(headroom?.toPlainString(), fund.currency))) {
                TextInput(T.TOP_UP_ABOVE_REASON, form.aboveReason, { v -> vm.edit { it.copy(aboveReason = v) } }, editable, singleLine = false)
            }
        }
        Section(null, footer = T.TOP_UP_FOOTER) {
            TextInput(T.NOTE, form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
        }
        val check = PettyCashRules.topUp(form.amount, form.note, form.aboveReason, headroom)
        SaveSection(save, vm::save, onDone, enabled = check is FormCheck.Valid, label = T.TOP_UP_SEND)
    }
}

@Composable
private fun FundSummary(fund: com.asseta.core.model.sync.PettyCashFundDto) {
    Section(T.fundHeader(fund)) {
        fund.balance?.let {
            LabeledRow(T.BALANCE, T.money(it.balance, fund.currency))
            LabeledRow(T.AVAILABLE, T.money(it.availableToSpend, fund.currency))
        }
        LabeledRow(T.LIMIT, T.money(fund.approvedLimit, fund.currency))
    }
}

// --- Return money to the office ------------------------------------------------------------------------------------

data class ReturnForm(
    val amount: String? = null,
    val method: RemittanceMethod = RemittanceMethod.CASH_TO_OFFICE,
    val accountId: String? = null,
    val reference: String = "",
    val note: String = "",
    val photos: List<CapturedPhoto> = emptyList(),
)

class PettyCashReturnViewModel(field: FieldGraph, tenantId: String, val fundId: String, private val accountsOn: Boolean) : PettyCashViewModel(field, tenantId) {
    val form = MutableStateFlow(ReturnForm())
    val accounts: StateFlow<List<DepositAccountOption>> = field.financeRepository.observeDepositAccounts(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun edit(change: (ReturnForm) -> ReturnForm) { form.update(change); clearMessages() }

    fun onPhotoError(message: String) = _save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    /** The amount shown: what was typed, else available to spend when above 0. */
    fun amountText(available: String?): String = form.value.amount ?: available?.toBigDecimalOrNull()?.takeIf { it.signum() > 0 }?.stripTrailingZeros()?.toPlainString().orEmpty()

    fun save() {
        val fund = view.value.fund(fundId) ?: return
        if (saving()) return
        val f = form.value
        viewModelScope.launch {
            finish(
                field.pettyCashCapture.returnFund(
                    PettyCashReturnRequest(
                        tenantId, clientId, fundId, amountText(fund.balance?.availableToSpend), f.method, f.accountId?.takeIf { accountsOn }, f.reference, f.note,
                        f.photos.map { it.jpeg }, policy.value.returnEvidenceRequired, field.clock.nowMs(),
                    ),
                ),
            )
        }
    }
}

@Composable
fun PettyCashReturnScreen(vm: PettyCashReturnViewModel, access: FieldAccess?, onDone: () -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val form by vm.form.collectAsStateWithLifecycle()
    val policy by vm.policy.collectAsStateWithLifecycle()
    val accounts by vm.accounts.collectAsStateWithLifecycle()
    val fund = view.fund(vm.fundId)
    val editable = !save.saving && !save.saved
    FormColumn {
        if (access?.pettyCash != true) return@FormColumn NoticeCard(T.TITLE_RETURN, T.UNAVAILABLE, isError = true)
        if (fund == null) {
            if (view.loaded && !save.saved) EmptyState(T.TITLE_RETURN, T.NOT_FOUND)
            SaveSection(save, {}, onDone, enabled = false)
            return@FormColumn
        }
        val amount = vm.amountText(fund.balance?.availableToSpend)
        FundSummary(fund)
        Section(null, footer = T.RETURN_FOOTER) {
            DecimalField(T.RETURN_AMOUNT, amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
            Text(T.RETURN_METHOD, color = palette.secondaryText)
            SegmentedChoice(RemittanceMethod.entries, form.method, T::method, { m -> vm.edit { it.copy(method = m) } }, editable)
            val options = field(accounts, fund.currency, access)
            if (options.isNotEmpty()) {
                SearchablePickerField(T.RETURN_ACCOUNT, options, form.accountId, { id -> vm.edit { it.copy(accountId = id) } }, noneLabel = T.RETURN_NO_ACCOUNT, enabled = editable)
            }
            TextInput(T.RETURN_REFERENCE, form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
            TextInput(T.NOTE, form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
        }
        EvidencePhotos(
            form.photos, { p -> vm.edit { it.copy(photos = it.photos + p) } }, { i -> vm.edit { it.copy(photos = it.photos.filterIndexed { j, _ -> j != i }) } },
            vm::onPhotoError, editable,
            footer = if (policy.returnEvidenceRequired) T.RETURN_EVIDENCE_REQUIRED else com.asseta.supervisor.ui.accountability.FieldAccountabilityTexts.EVIDENCE_FOOTER,
        )
        val check = PettyCashRules.returnFund(amount, form.reference, form.note, form.photos.size, policy.returnEvidenceRequired)
        SaveSection(save, vm::save, onDone, enabled = check is FormCheck.Valid)
    }
}

/** Active deposit accounts in the fund's currency; none while the company does not use deposit accounts. */
private fun field(accounts: List<DepositAccountOption>, currency: String, access: FieldAccess): List<PickerOption> =
    if (!access.depositAccounts) emptyList()
    else accounts.filter { it.isActive && it.currency == currency }.map { PickerOption(it.id, it.name, it.subtitle.ifEmpty { null }) }

// --- Record a count ------------------------------------------------------------------------------------------------

data class CountForm(
    val counted: String = "",
    val note: String = "",
    val photos: List<CapturedPhoto> = emptyList(),
    val witness: PersonDto? = null,
    val query: String = "",
)

class PettyCashCountViewModel(field: FieldGraph, tenantId: String, val fundId: String) : PettyCashViewModel(field, tenantId) {
    val form = MutableStateFlow(CountForm())

    /** Witness search results; null = offline or not searched. */
    private val _people = MutableStateFlow<List<PersonDto>?>(null)
    val people: StateFlow<List<PersonDto>?> = _people.asStateFlow()

    fun edit(change: (CountForm) -> CountForm) { form.update(change); clearMessages() }

    fun onPhotoError(message: String) = _save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    /** Name search over colleagues (online; at least two characters). */
    suspend fun search(query: String) {
        _people.value = if (query.trim().length < PettyCashRules.MIN_WITNESS_SEARCH) null else field.online.searchPeople(query)
    }

    fun save() {
        if (saving()) return
        val f = form.value
        viewModelScope.launch {
            finish(field.pettyCashCapture.count(PettyCashCountRequest(tenantId, clientId, fundId, f.counted, f.witness?.userId, f.note, f.photos.map { it.jpeg }, field.clock.nowMs())))
        }
    }
}

@Composable
fun PettyCashCountScreen(vm: PettyCashCountViewModel, access: FieldAccess?, online: Boolean, onDone: () -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val form by vm.form.collectAsStateWithLifecycle()
    val policy by vm.policy.collectAsStateWithLifecycle()
    val people by vm.people.collectAsStateWithLifecycle()
    val fund = view.fund(vm.fundId)
    val editable = !save.saving && !save.saved
    LaunchedEffect(form.query, online) {
        delay(350)
        if (online) vm.search(form.query)
    }
    FormColumn {
        if (access?.pettyCashCount != true) return@FormColumn NoticeCard(T.TITLE_COUNT, T.UNAVAILABLE, isError = true)
        if (fund == null) {
            if (view.loaded && !save.saved) EmptyState(T.TITLE_COUNT, T.NOT_FOUND)
            SaveSection(save, {}, onDone, enabled = false)
            return@FormColumn
        }
        Section(T.fundHeader(fund), footer = T.COUNT_FOOTER) {
            DecimalField(T.COUNT_AMOUNT, form.counted, { v -> vm.edit { it.copy(counted = v) } }, editable)
            TextInput(T.NOTE, form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
        }
        if (policy.countWitnessRequired) {
            Section(T.WITNESS, footer = if (form.witness == null) T.WITNESS_FOOTER + " " + T.NO_WITNESS else T.WITNESS_FOOTER) {
                val w = form.witness
                if (w != null) {
                    LabeledRow(T.WITNESS, w.displayName)
                    if (editable) ActionRow(T.WITNESS_NONE) { vm.edit { it.copy(witness = null) } }
                } else if (!online) {
                    Text(T.WITNESS_OFFLINE, color = palette.secondaryText)
                } else {
                    TextInput(T.WITNESS_SEARCH, form.query, { v -> vm.edit { it.copy(query = v) } }, editable)
                    val results = people
                    if (results != null && results.isEmpty()) Text(T.WITNESS_NO_RESULTS, color = palette.secondaryText)
                    results.orEmpty().forEach { p -> ActionRow(p.displayName, enabled = editable) { vm.edit { it.copy(witness = p, query = "") } } }
                }
            }
        }
        EvidencePhotos(form.photos, { p -> vm.edit { it.copy(photos = it.photos + p) } }, { i -> vm.edit { it.copy(photos = it.photos.filterIndexed { j, _ -> j != i }) } },
            vm::onPhotoError, editable)
        SaveSection(save, vm::save, onDone, enabled = PettyCashRules.count(form.counted) is FormCheck.Valid)
    }
}

// --- Take over a fund ----------------------------------------------------------------------------------------------

class PettyCashHolderChangeViewModel(field: FieldGraph, tenantId: String, val changeId: String) : PettyCashViewModel(field, tenantId) {
    val note = MutableStateFlow("")
    private val _waiting = MutableStateFlow(false)
    val waiting: StateFlow<Boolean> = _waiting.asStateFlow()

    init {
        viewModelScope.launch { _waiting.value = field.pettyCashCapture.answered(tenantId, PettyCashEntities.HOLDER_CHANGE, changeId) }
    }

    fun answer(accept: Boolean) {
        if (saving()) return
        viewModelScope.launch { finish(field.pettyCashCapture.holderChange(tenantId, changeId, accept, note.value)) }
    }
}

@Composable
fun PettyCashHolderChangeScreen(vm: PettyCashHolderChangeViewModel, access: FieldAccess?, onDone: () -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val waiting by vm.waiting.collectAsStateWithLifecycle()
    val note by vm.note.collectAsStateWithLifecycle()
    val c = view.holderChanges.firstOrNull { it.id == vm.changeId }
    val editable = !save.saving && !save.saved && !waiting
    FormColumn {
        if (access?.pettyCash != true) return@FormColumn NoticeCard(T.TITLE_HOLDER_CHANGE, T.UNAVAILABLE, isError = true)
        if (waiting) return@FormColumn Section(null) { Text(T.ACK_WAITING, color = WarningColor) }
        if (c == null) {
            if (view.loaded && !save.saved) EmptyState(T.TITLE_HOLDER_CHANGE, T.NOT_FOUND)
            SaveSection(save, {}, onDone, enabled = false)
            return@FormColumn
        }
        val from = c.fromStaffName?.takeIf { it.isNotBlank() } ?: T.SOMEONE
        Section(null, footer = T.holderFooter(from)) {
            LabeledRow(T.FUND, c.fundName.orEmpty())
            LabeledRow(T.HOLDER_FROM, from)
            c.requestedByName?.takeIf { it.isNotBlank() }?.let { LabeledRow(T.HOLDER_REQUESTED_BY, it) }
            LabeledRow(T.HOLDER_REQUESTED_AT, LocalTime.formatIso(c.requestedAt))
            c.note?.takeIf { it.isNotBlank() }?.let { Text(it, color = palette.secondaryText) }
        }
        Section(null) { TextInput(T.NOTE, note, { v -> vm.note.value = v; vm.clearMessages() }, editable, singleLine = false) }
        SaveSection(save, { vm.answer(true) }, onDone, enabled = editable, label = T.HOLDER_ACCEPT)
        val canDecline = PettyCashRules.holderDecision(false, note) is FormCheck.Valid
        OutlinedButton(onClick = { vm.answer(false) }, enabled = editable && canDecline) { Text(T.HOLDER_DECLINE, color = palette.offline) }
        if (!canDecline) Text(T.HOLDER_DECLINE_REASON, color = palette.secondaryText)
    }
}

// --- Clear an advance ----------------------------------------------------------------------------------------------

class PettyCashAdvanceViewModel(field: FieldGraph, tenantId: String, val advanceId: String) : PettyCashViewModel(field, tenantId) {
    val change = MutableStateFlow<String?>(null)
    val note = MutableStateFlow("")

    fun save(remaining: String) {
        if (saving()) return
        viewModelScope.launch { finish(field.pettyCashCapture.clearAdvance(tenantId, advanceId, change.value ?: remaining, note.value)) }
    }
}

@Composable
fun PettyCashAdvanceScreen(vm: PettyCashAdvanceViewModel, access: FieldAccess?, onDone: () -> Unit) {
    val view by vm.view.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val change by vm.change.collectAsStateWithLifecycle()
    val note by vm.note.collectAsStateWithLifecycle()
    val me by vm.me.collectAsStateWithLifecycle()
    val a = PettyCashRepository.clearable(view, me).firstOrNull { it.id == vm.advanceId }
    val editable = !save.saving && !save.saved
    FormColumn {
        if (access?.pettyCash != true) return@FormColumn NoticeCard(T.TITLE_ADVANCE, T.UNAVAILABLE, isError = true)
        if (a == null) {
            if (view.loaded && !save.saved) EmptyState(T.TITLE_ADVANCE, T.NOT_FOUND)
            SaveSection(save, {}, onDone, enabled = false)
            return@FormColumn
        }
        val remaining = a.remaining.toBigDecimalOrNull()?.max(java.math.BigDecimal.ZERO)?.stripTrailingZeros()?.toPlainString() ?: "0"
        Section(a.number) {
            LabeledRow(T.FUND, a.fundName ?: view.fund(a.fundId)?.name.orEmpty())
            LabeledRow(T.ADVANCE_RECIPIENT, a.recipientStaffName?.takeIf { it.isNotBlank() } ?: T.SOMEONE)
            LabeledRow(T.ADVANCE_AMOUNT, T.money(a.amount, a.currency))
            LabeledRow(T.ADVANCE_PURPOSE, a.purpose)
            LabeledRow(T.ADVANCE_APPROVED, T.money(a.approvedSpending, a.currency))
            if (T.nonZero(a.pendingSpending)) LabeledRow(T.ADVANCE_PENDING, T.money(a.pendingSpending, a.currency))
            LabeledRow(T.ADVANCE_REMAINING, T.money(a.remaining, a.currency))
            LabeledRow(T.ADVANCE_DUE, LocalTime.formatIso(a.dueAt))
        }
        if (T.nonZero(a.pendingSpending)) Section(null) { Text(T.ADVANCE_PENDING_WARNING, color = WarningColor) }
        Section(null, footer = T.ADVANCE_FOOTER) {
            DecimalField(T.ADVANCE_CHANGE, change ?: remaining, { v -> vm.change.value = v; vm.clearMessages() }, editable)
            TextInput(T.NOTE, note, { v -> vm.note.value = v }, editable, singleLine = false)
        }
        SaveSection(save, { vm.save(remaining) }, onDone, enabled = PettyCashRules.advanceClear(change ?: remaining) is FormCheck.Valid, label = T.ADVANCE_CLEAR)
    }
}

/** What a petty cash notification opens on the phone (DEC-033): the waiting record when it still waits, else the list. */
object PettyCashLinks {
    fun route(entity: String?, id: String?, view: PettyCashView): Route? = when {
        entity == null || !entity.startsWith("petty_cash") -> null
        entity == "petty_cash_movement" && view.awaiting.any { it.id == id } -> Route.PettyCashAck(id!!)
        entity == "petty_cash_holder_change" && view.holderChanges.any { it.id == id } -> Route.PettyCashHolderChange(id!!)
        else -> Route.PettyCash
    }

    /** The feature is on for this user (also off when the tenant switched PETTY_CASH off). */
    fun on(access: FieldAccess?, tenant: TenantAccess): Boolean = access?.pettyCash == true && TenantAccess.PETTY_CASH !in tenant.disabledCapabilities
}
