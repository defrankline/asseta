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
    }
}

/** One expense entry; the client id is generated once per visit (idempotency). Rules live in `ExpenseRules`. */
class ExpenseViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
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

    /** Live offline assessment: receipt requirement, GPS rules and the approval outlook, shown before saving. */
    val assessment: StateFlow<ExpenseAssessment?> = combine(form, setup, gps.state, jobs) { f, s, g, j ->
        val policy = s.policy ?: return@combine null
        ExpenseRules.assess(draft(f, g.outcome, j), policy, s.baseCurrency)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    init {
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
                    TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
                    TextInput("What was it for?", form.description, { v -> vm.edit { it.copy(description = v) } }, editable, singleLine = false)
                    TextInput("Supplier (optional)", form.supplier, { v -> vm.edit { it.copy(supplier = v) } }, editable)
                }
                Section("Paid from") {
                    SegmentedChoice(PaidFrom.entries, form.paidFrom, ExpenseTexts::paidFrom, { p -> vm.edit { it.copy(paidFrom = p) } }, editable)
                }
                Section("Charge to", footer = if (form.jobId != null) "The cost is charged to the job's machine." else "Optional.") {
                    SearchablePickerField("Job", jobOptions(jobs), form.jobId, vm::selectJob, noneLabel = "No job", enabled = editable)
                    SearchablePickerField("Machine", machines, form.machineId, { id -> vm.edit { it.copy(machineId = id) } },
                        noneLabel = "No machine", enabled = editable && form.jobId == null)
                }
                ReceiptSection(form.receipts, assessment?.receiptRequired == true, vm::addReceipt, vm::removeReceipt, vm::onPhotoError, editable)
                GpsSection(gps, policy.gpsRequired, vm.gps::onDecision, vm.gps::attempt, editable)
                val issues = ExpenseTexts.visibleIssues(assessment, form.amount)
                if (issues.isNotEmpty()) Section(null) { issues.forEach { Text(it, color = WarningColor) } }
                if (assessment?.amount != null) {
                    ExpenseTexts.approvalNote(assessment?.approval)?.let { Section(null) { Text(it, style = MaterialTheme.typography.bodySmall) } }
                }
                SaveSection(save, vm::save, onDone, enabled = assessment?.isValid == true && gps.decided && !gps.busy)
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
