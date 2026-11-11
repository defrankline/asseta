package com.asseta.supervisor.ui.finance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.finance.ApprovalOutlook
import com.asseta.core.domain.finance.ExpenseAssessment
import com.asseta.core.domain.finance.ExpenseCapturePolicy
import com.asseta.core.domain.finance.ExpenseDraft
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.finance.ExpenseRules
import com.asseta.core.domain.finance.ExpenseViolation
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.usecase.ExpenseRequest
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.hasAnyPermission
import com.asseta.supervisor.ui.NoticeCard
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.WarningColor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.util.UUID

data class ExpenseForm(
    val categoryId: String? = null,
    val description: String = "",
    val supplier: String = "",
    val amount: String = "",
    val currency: String = "",
    val paidFrom: PaidFrom? = PaidFrom.CASH_CUSTODY,
    val machineId: String? = null,
    val jobId: String? = null,
    /** Receipt photos in the order taken; at most [ExpenseRules.MAX_RECEIPTS]. */
    val receipts: List<CapturedPhoto> = emptyList(),
    /** DEC-033, paid from PETTY_CASH: the fund and (optionally) the advance given to me. */
    val pettyFundId: String? = null,
    val pettyAdvanceId: String? = null,
)

data class ExpenseSetup(
    val loading: Boolean = true,
    val blocked: String? = null,
    val policy: ExpenseCapturePolicy? = null,
    val policyStamp: String? = null,
    val baseCurrency: String? = null,
)

/** Wording of the expense form shared with iOS (`ExpenseFormModel.rulesSummary`, approval note). */
object ExpenseTexts {
    private fun plain(value: BigDecimal): String = value.stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }.toPlainString()

    /** Plain-language summary of the owner's rules, shown under the first section. */
    fun rulesSummary(policy: ExpenseCapturePolicy, baseCurrency: String?, stamp: String?): String {
        val currency = baseCurrency?.let { " $it" }.orEmpty()
        val receipt = if (policy.receiptRequiredAbove.signum() == 0) "Receipt photo required for every expense."
        else "Receipt photo required above ${plain(policy.receiptRequiredAbove)}$currency."
        val gps = if (policy.gpsRequired) " GPS fix within ±${Math.round(policy.gpsMaxAccuracyM)} m required." else ""
        val approval = if (policy.autoApproveLimit.signum() == 0) " Every expense needs a manager's approval."
        else " Up to ${plain(policy.autoApproveLimit)}$currency is approved automatically."
        return receipt + gps + approval + " (Rules $stamp.)"
    }

    /** Before saving: who approves it (only once the amount is valid). */
    fun approvalNote(outlook: ApprovalOutlook?): String? = when (outlook) {
        is ApprovalOutlook.NeedsApproval -> outlook.reason
        ApprovalOutlook.AutoApproved -> "Within the auto-approval limit: approved automatically once synced."
        null -> null
    }

    /** Issues shown while filling in (the empty-field prompts and the pending GPS attempt are left out, as on iOS). */
    fun visibleIssues(assessment: ExpenseAssessment?, amountText: String): List<String> = assessment?.issues.orEmpty().filter {
        when (it.code) {
            ExpenseViolation.CATEGORY_REQUIRED, ExpenseViolation.DESCRIPTION_REQUIRED, ExpenseViolation.GPS_NOT_ATTEMPTED -> false
            ExpenseViolation.AMOUNT_INVALID -> amountText.isNotBlank()
            else -> true
        }
    }.map { it.message }

    fun paidFrom(value: PaidFrom): String = when (value) {
        PaidFrom.CASH_CUSTODY -> "My cash"
        PaidFrom.COMPANY -> "Company"
        PaidFrom.PETTY_CASH -> com.asseta.core.domain.finance.ExpenseFlags.PAID_FROM_PETTY_CASH
    }

    /** Paid-from choices: "Petty cash" only when the phone has a fund or an advance to pay from (DEC-033). */
    fun paidFromOptions(pettyCash: Boolean): List<PaidFrom> = PaidFrom.entries.filter { it != PaidFrom.PETTY_CASH || pettyCash }
}

/** What the petty cash part of the expense form offers and says (DEC-033), from the synced funds and advances. */
data class PettyExpense(
    val funds: List<com.asseta.core.domain.finance.FundChoice> = emptyList(),
    val advances: List<com.asseta.core.domain.finance.AdvanceChoice> = emptyList(),
    val view: com.asseta.core.sync.data.PettyCashView = com.asseta.core.sync.data.PettyCashView(),
    val policy: com.asseta.core.domain.finance.PettyCashPolicy = com.asseta.core.domain.finance.PettyCashPolicy(),
) {
    fun fund(id: String?) = funds.firstOrNull { it.id == id }
    fun advance(id: String?, fundId: String?) = advances.firstOrNull { it.id == id && it.fundId == fundId }
    fun advancesOf(fundId: String?) = advances.filter { it.fundId == fundId }
}

/** One expense entry; the client id is generated once per visit (idempotency). Rules live in `ExpenseRules`. */
class ExpenseViewModel(private val field: FieldGraph, private val tenantId: String, private val pettyCash: Boolean = false) : ViewModel() {
    private val clientId = UUID.randomUUID().toString()
    val gps = GpsAttempt(field, viewModelScope)
    val form = MutableStateFlow(ExpenseForm())
    val setup = MutableStateFlow(ExpenseSetup())
    val save = MutableStateFlow(SaveState())

    val categories: StateFlow<List<PickerOption>> = field.financeRepository.observeCategories(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.name, it.code) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val jobs: StateFlow<List<JobSummary>> = field.financeRepository.observeJobs(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val machines: StateFlow<List<PickerOption>> = field.financeRepository.observeMachines(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.assetCode, it.name) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val me = MutableStateFlow<String?>(null)
    private val pettyPolicy = MutableStateFlow(com.asseta.core.domain.finance.PettyCashPolicy())

    /** Funds and advances I can pay from (empty while petty cash is not available to me). */
    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    val petty: StateFlow<PettyExpense> = if (!pettyCash) MutableStateFlow(PettyExpense()) else
        combine(me.flatMapLatest { field.pettyCash.observe(tenantId, it) }, me, pettyPolicy) { view, me, policy ->
            val usable = if (policy.advancesEnabled) view else view.copy(advances = emptyList())
            val advances = com.asseta.core.sync.data.PettyCashRepository.advanceChoicesOf(usable, me)
            val funds = com.asseta.core.sync.data.PettyCashRepository.fundChoices(usable, me)
            PettyExpense(funds, advances, view, policy)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), PettyExpense())

    /** Petty cash checks that block saving. */
    val pettyIssues: StateFlow<List<String>> = combine(form, petty) { f, p ->
        if (f.paidFrom != PaidFrom.PETTY_CASH) emptyList()
        else com.asseta.core.domain.finance.PettyCashRules.expenseIssues(
            p.fund(f.pettyFundId), p.advance(f.pettyAdvanceId, f.pettyFundId), com.asseta.core.domain.finance.CurrencyCode.normalize(f.currency),
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** Live offline assessment: receipt requirement, GPS rules and the approval outlook, shown before saving. */
    val assessment: StateFlow<ExpenseAssessment?> = combine(form, setup, gps.state, jobs) { f, s, g, j ->
        val policy = s.policy ?: return@combine null
        ExpenseRules.assess(draft(f, g.outcome, j), policy, s.baseCurrency)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    init {
        viewModelScope.launch {
            if (pettyCash) {
                me.value = field.accountability.myStaffId(tenantId)
                pettyPolicy.value = field.pettyCash.policy(tenantId)
            }
        }
        viewModelScope.launch {
            val base = field.financeRepository.baseCurrency(tenantId)
            form.update { it.copy(currency = base.orEmpty()) }
            setup.value = when (val d = field.financeRepository.expensePolicy(tenantId)) {
                is ExpensePolicyDecision.Blocked -> ExpenseSetup(loading = false, blocked = d.message)
                is ExpensePolicyDecision.Allowed -> ExpenseSetup(false, null, d.policy, d.snapshot.versionStamp, base)
            }
        }
    }

    private fun draft(f: ExpenseForm, outcome: GpsOutcome?, jobs: List<JobSummary>) = ExpenseDraft(
        f.categoryId, f.description, f.supplier, f.amount, f.currency, f.paidFrom, f.machineId ?: jobMachine(f.jobId, jobs),
        f.jobId, jobMachine(f.jobId, jobs), f.receipts.isNotEmpty(), outcome,
    )

    private fun jobMachine(jobId: String?, jobs: List<JobSummary>) = jobs.firstOrNull { it.job.id == jobId }?.job?.machineId

    fun edit(change: (ExpenseForm) -> ExpenseForm) {
        form.update(change)
        save.update { it.copy(messages = emptyList()) }
    }

    /** Choosing a fund sets the expense's currency to the fund's; an advance of another fund is dropped. */
    fun selectFund(fundId: String?) = edit { f ->
        val fund = petty.value.fund(fundId)
        f.copy(
            pettyFundId = fundId, pettyAdvanceId = f.pettyAdvanceId.takeIf { petty.value.advance(it, fundId) != null },
            currency = fund?.currency ?: f.currency,
        )
    }

    fun selectPaidFrom(p: PaidFrom) {
        edit { it.copy(paidFrom = p) }
        // A single fund is chosen for the user.
        if (p == PaidFrom.PETTY_CASH && form.value.pettyFundId == null) petty.value.funds.singleOrNull()?.let { selectFund(it.id) }
    }

    /** Choosing a job charges the expense to that job's machine. */
    fun selectJob(jobId: String?) = edit { it.copy(jobId = jobId, machineId = jobMachine(jobId, jobs.value) ?: it.machineId) }

    fun onPhotoError(message: String) = save.update { it.copy(messages = listOf("The receipt photo could not be saved: $message")) }

    fun addReceipt(photo: CapturedPhoto) {
        if (form.value.receipts.size >= ExpenseRules.MAX_RECEIPTS) {
            save.update { it.copy(messages = listOf("At most ${ExpenseRules.MAX_RECEIPTS} receipt photos per expense.")) }
            return
        }
        edit { it.copy(receipts = it.receipts + photo) }
    }

    fun removeReceipt(index: Int) = edit { f -> f.copy(receipts = f.receipts.filterIndexed { i, _ -> i != index }) }

    fun save() {
        if (save.value.saving || save.value.saved) return
        viewModelScope.launch {
            save.update { it.copy(saving = true, messages = emptyList()) }
            gps.awaitIdle()
            val f = form.value
            val result = field.finance.expense(
                ExpenseRequest(
                    tenantId, clientId, f.categoryId, f.description, f.supplier, f.amount, f.currency, f.paidFrom, f.machineId,
                    f.jobId, f.receipts.map { it.jpeg }, gps.state.value.outcome, f.receipts.firstOrNull()?.takenAtMs ?: field.clock.nowMs(),
                    pettyFund = petty.value.fund(f.pettyFundId).takeIf { f.paidFrom == PaidFrom.PETTY_CASH },
                    pettyAdvance = petty.value.advance(f.pettyAdvanceId, f.pettyFundId).takeIf { f.paidFrom == PaidFrom.PETTY_CASH },
                ),
            )
            save.update { it.after(result) }
        }
    }
}

/**
 * Record expense (`EXPENSE`). The owner's `EXPENSE_CAPTURE` snapshot is enforced offline: receipt photo above the
 * threshold, GPS fix and accuracy when required, and a clear note when the amount needs a manager's approval.
 */
@Composable
fun ExpenseScreen(vm: ExpenseViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val setup by vm.setup.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val gps by vm.gps.state.collectAsStateWithLifecycle()
    val assessment by vm.assessment.collectAsStateWithLifecycle()
    val categories by vm.categories.collectAsStateWithLifecycle()
    val machines by vm.machines.collectAsStateWithLifecycle()
    val jobs by vm.jobs.collectAsStateWithLifecycle()
    val petty by vm.petty.collectAsStateWithLifecycle()
    val pettyIssues by vm.pettyIssues.collectAsStateWithLifecycle()
    val pettyChosen = form.paidFrom == PaidFrom.PETTY_CASH
    val context = LocalContext.current
    LaunchedEffect(Unit) { if (context.hasAnyPermission(GpsLocator.PERMISSIONS)) vm.gps.onDecision(true) }
    val editable = !save.saved && !save.saving
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when {
            setup.loading -> CircularProgressIndicator()
            setup.blocked != null -> NoticeCard("Can't record an expense now", setup.blocked!!, isError = true)
            else -> {
                val policy = setup.policy!!
                Section(null, footer = ExpenseTexts.rulesSummary(policy, setup.baseCurrency, setup.policyStamp)) {
                    SearchablePickerField("Category", categories, form.categoryId, { id -> vm.edit { it.copy(categoryId = id) } },
                        emptyText = "No expense categories have been synced yet. Connect and sync.", enabled = editable)
                    DecimalField("Amount", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                    TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable && !pettyChosen)
                    TextInput("What was it for?", form.description, { v -> vm.edit { it.copy(description = v) } }, editable, singleLine = false)
                    TextInput("Supplier (optional)", form.supplier, { v -> vm.edit { it.copy(supplier = v) } }, editable)
                }
                Section("Paid from") {
                    SegmentedChoice(ExpenseTexts.paidFromOptions(petty.funds.isNotEmpty()), form.paidFrom, ExpenseTexts::paidFrom, vm::selectPaidFrom, editable)
                }
                if (pettyChosen) PettyFundSection(petty, form, vm, editable)
                Section("Charge to", footer = if (form.jobId != null) "The cost is charged to the job's machine." else "Optional.") {
                    SearchablePickerField("Job", jobOptions(jobs), form.jobId, vm::selectJob, noneLabel = "No job", enabled = editable)
                    SearchablePickerField("Machine", machines, form.machineId, { id -> vm.edit { it.copy(machineId = id) } },
                        noneLabel = "No machine", enabled = editable && form.jobId == null)
                }
                ReceiptSection(form.receipts, assessment?.receiptRequired == true, vm::addReceipt, vm::removeReceipt, vm::onPhotoError, editable)
                GpsSection(gps, policy.gpsRequired, vm.gps::onDecision, vm.gps::attempt, editable)
                val issues = ExpenseTexts.visibleIssues(assessment, form.amount)
                if (issues.isNotEmpty()) Section(null) { issues.forEach { Text(it, color = WarningColor) } }
                if (pettyChosen && pettyIssues.isNotEmpty() && form.pettyFundId != null) Section(null) { pettyIssues.forEach { Text(it, color = WarningColor) } }
                if (assessment?.amount != null) {
                    val pettyNotes = if (pettyChosen) com.asseta.core.domain.finance.PettyCashRules.expenseNotes(
                        petty.fund(form.pettyFundId), petty.advance(form.pettyAdvanceId, form.pettyFundId), assessment?.amount, setup.baseCurrency, petty.policy,
                    ) else emptyList()
                    // An overspend or an amount above the maximum always waits for a person, whatever the auto-approval limit.
                    if (pettyNotes.isNotEmpty()) Section(null) { pettyNotes.forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = WarningColor) } }
                    else ExpenseTexts.approvalNote(assessment?.approval)?.let { Section(null) { Text(it, style = MaterialTheme.typography.bodySmall) } }
                }
                SaveSection(save, vm::save, onDone, enabled = assessment?.isValid == true && pettyIssues.isEmpty() && gps.decided && !gps.busy)
            }
        }
    }
}

/** Open (not completed or cancelled) jobs for the pickers: job number with machine, customer and site. */
fun jobOptions(jobs: List<JobSummary>): List<PickerOption> = jobs
    .filter { it.job.status != "COMPLETED" && it.job.status != "CANCELLED" }
    .map { s ->
        PickerOption(s.job.id, s.job.jobNumber, listOfNotNull(s.machine?.assetCode, s.customerName, s.siteName).joinToString(" · ").ifEmpty { null })
    }

/** Fund and advance pickers of an expense paid from petty cash (DEC-033). */
@Composable
private fun PettyFundSection(petty: PettyExpense, form: ExpenseForm, vm: ExpenseViewModel, editable: Boolean) {
    val t = com.asseta.supervisor.ui.pettycash.PettyCashTexts
    val fund = petty.fund(form.pettyFundId)
    val footer = fund?.available?.let { t.expenseFooter(com.asseta.core.domain.finance.PettyCashRules.money(it, fund.currency)) }
    Section(t.EXPENSE_SECTION, footer = footer) {
        val options = petty.funds.map { f ->
            val dto = petty.view.fund(f.id)
            val name = dto?.let { t.fundHeader(it) } ?: petty.view.advances.firstOrNull { it.fundId == f.id }?.fundName ?: f.id.take(8)
            PickerOption(f.id, name, f.available?.let { t.expenseFundOption(com.asseta.core.domain.finance.PettyCashRules.money(it, f.currency)) })
        }
        SearchablePickerField(t.EXPENSE_FUND, options, form.pettyFundId, vm::selectFund, emptyText = t.EXPENSE_FUND_EMPTY, enabled = editable)
        val advances = petty.advancesOf(form.pettyFundId)
        if (fund != null && advances.isNotEmpty()) {
            val advanceOptions = advances.map { a ->
                val dto = petty.view.advances.firstOrNull { it.id == a.id }
                PickerOption(a.id, dto?.number ?: a.id.take(8), t.expenseAdvanceOption(com.asseta.core.domain.finance.PettyCashRules.money(a.remaining, fund.currency)))
            }
            SearchablePickerField(
                if (fund.held) t.EXPENSE_ADVANCE else t.EXPENSE_ADVANCE_REQUIRED_LABEL, advanceOptions, form.pettyAdvanceId,
                { id -> vm.edit { it.copy(pettyAdvanceId = id) } }, noneLabel = if (fund.held) t.EXPENSE_NO_ADVANCE else null, enabled = editable,
            )
        }
    }
}
