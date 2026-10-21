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
import com.asseta.core.domain.finance.ApprovalOutlook
import com.asseta.core.domain.finance.ExpenseAssessment
import com.asseta.core.domain.finance.ExpenseCapturePolicy
import com.asseta.core.domain.finance.ExpenseDraft
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.finance.ExpenseRules
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.usecase.ExpenseRequest
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.hasAnyPermission
import com.asseta.supervisor.ui.NoticeCard
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
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
    val receipt: CapturedPhoto? = null,
)

data class ExpenseSetup(
    val loading: Boolean = true,
    val blocked: String? = null,
    val policy: ExpenseCapturePolicy? = null,
    val policyStamp: String? = null,
    val baseCurrency: String? = null,
)

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
        .map { list -> list.map { PickerOption(it.id, "${it.assetCode} · ${it.name}") } }
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

    private fun draft(f: ExpenseForm, outcome: com.asseta.core.domain.capture.GpsOutcome?, jobs: List<JobSummary>) = ExpenseDraft(
        f.categoryId, f.description, f.supplier, f.amount, f.currency, f.paidFrom, f.machineId ?: jobMachine(f.jobId, jobs),
        f.jobId, jobMachine(f.jobId, jobs), f.receipt != null, outcome,
    )

    private fun jobMachine(jobId: String?, jobs: List<JobSummary>) = jobs.firstOrNull { it.job.id == jobId }?.job?.machineId

    fun edit(change: (ExpenseForm) -> ExpenseForm) {
        form.update(change)
        save.update { it.copy(messages = emptyList()) }
    }

    /** Choosing a job attributes the expense to that job's machine. */
    fun selectJob(jobId: String?) = edit { it.copy(jobId = jobId, machineId = jobMachine(jobId, jobs.value) ?: it.machineId) }

    fun onPhotoError(message: String) = save.update { it.copy(messages = listOf(message)) }

    fun save() {
        if (save.value.saving || save.value.saved) return
        viewModelScope.launch {
            save.update { it.copy(saving = true, messages = emptyList()) }
            gps.awaitIdle()
            val f = form.value
            val result = field.finance.expense(
                ExpenseRequest(
                    tenantId, clientId, f.categoryId, f.description, f.supplier, f.amount, f.currency, f.paidFrom, f.machineId,
                    f.jobId, f.receipt?.jpeg, gps.state.value.outcome, f.receipt?.takenAtMs ?: field.clock.nowMs(),
                ),
            )
            val approval = (assessment.value?.approval as? ApprovalOutlook.NeedsApproval)?.let { " ${it.reason}" }.orEmpty()
            save.update { it.after(result, NOT_VERIFIED_NOTE + approval) }
        }
    }
}

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
        Text("Record expense", style = MaterialTheme.typography.headlineSmall)
        when {
            setup.loading -> CircularProgressIndicator()
            setup.blocked != null -> NoticeCard("Expenses blocked", setup.blocked!!, isError = true)
            else -> {
                val policy = setup.policy!!
                Text("Your company's expense rules (${setup.policyStamp}) are applied on this device.", style = MaterialTheme.typography.bodySmall)
                SearchablePickerField("Category", categories, form.categoryId, { id -> vm.edit { it.copy(categoryId = id) } }, enabled = editable)
                TextInput("What was paid for", form.description, { v -> vm.edit { it.copy(description = v) } }, editable, singleLine = false)
                TextInput("Supplier (optional)", form.supplier, { v -> vm.edit { it.copy(supplier = v) } }, editable)
                DecimalField("Amount", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                TextInput("Currency" + (setup.baseCurrency?.let { " (company: $it)" } ?: ""), form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
                Text("Paid from", style = MaterialTheme.typography.titleSmall)
                ChoiceChips(PaidFrom.entries, form.paidFrom, { it.label }, { p -> vm.edit { it.copy(paidFrom = p) } }, editable)
                SearchablePickerField(
                    "Job (optional)",
                    jobs.map { PickerOption(it.job.id, it.job.jobNumber, it.machine?.let { m -> "${m.assetCode} · ${m.name}" }) },
                    form.jobId, vm::selectJob, noneLabel = "No job", enabled = editable,
                )
                SearchablePickerField("Machine (optional)", machines, form.machineId, { id -> vm.edit { it.copy(machineId = id) } },
                    noneLabel = "No machine", emptyText = "No assigned machines on this device yet.", enabled = editable)
                ReceiptSection(form.receipt, assessment?.receiptRequired == true, assessment?.receiptReason,
                    { p -> vm.edit { it.copy(receipt = p) } }, vm::onPhotoError, editable)
                val requirement = if (policy.gpsRequired) "Required: a fix within ${Math.round(policy.gpsMaxAccuracyM)} m." else null
                GpsCard(gps, requirement, vm.gps::onDecision, vm.gps::attempt, editable)
                when (val outlook = assessment?.approval) {
                    is ApprovalOutlook.NeedsApproval -> NoticeCard("Will need approval", outlook.reason)
                    ApprovalOutlook.AutoApproved -> Text("Within the auto-approval limit: approved automatically once synced.", style = MaterialTheme.typography.bodySmall)
                    null -> Unit
                }
                val pending = assessment?.issues.orEmpty().map { it.message }
                if (!save.saved && pending.isNotEmpty() && save.messages.isEmpty()) {
                    Text("Still needed: " + pending.joinToString(" "), style = MaterialTheme.typography.bodySmall)
                }
                SaveSection(save, "Save expense", vm::save, onDone, enabled = gps.decided && !gps.busy)
            }
        }
    }
}
