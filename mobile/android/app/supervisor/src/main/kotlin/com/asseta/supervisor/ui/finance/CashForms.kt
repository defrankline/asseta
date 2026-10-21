package com.asseta.supervisor.ui.finance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.CashRules
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.finance.FuelEventType
import com.asseta.core.domain.finance.formatMoney
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.usecase.CashCollectionRequest
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.FuelEventRequest
import com.asseta.supervisor.FieldGraph
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

/** Plain text fields of a cash/fuel form (validated by `CashRules` in the use case). */
data class CashForm(
    val kind: String = "", // COLLECTION | HANDOVER | FUEL
    val customerId: String? = null,
    val jobId: String? = null,
    val machineId: String? = null,
    val fuelType: FuelEventType? = null,
    val amount: String = "",
    val unitPrice: String = "",
    val meter: String = "",
    val currency: String = "",
    val reference: String = "",
    val supplier: String = "",
    val note: String = "",
)

/** Collection, handover and fuel forms share one view model; the client id is generated once per visit. */
class CashFormViewModel(private val field: FieldGraph, private val tenantId: String, kind: String) : ViewModel() {
    private val clientId = UUID.randomUUID().toString()
    val form = MutableStateFlow(CashForm(kind = kind))
    val save = MutableStateFlow(SaveState())
    private val repo = field.financeRepository

    val customers: StateFlow<List<PickerOption>> = repo.observeCustomers(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.name, it.code, it.contactName) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val jobs: StateFlow<List<JobSummary>> = repo.observeJobs(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val machines: StateFlow<List<PickerOption>> = repo.observeMachines(tenantId)
        .map { list -> list.map { PickerOption(it.id, "${it.assetCode} · ${it.name}") } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init {
        viewModelScope.launch { repo.baseCurrency(tenantId)?.let { c -> form.update { it.copy(currency = c) } } }
    }

    fun edit(change: (CashForm) -> CashForm) {
        form.update(change)
        save.update { it.copy(messages = emptyList()) }
    }

    /** A job pre-selects its contract's customer (collection) or its machine (fuel). */
    fun selectJob(jobId: String?) = viewModelScope.launch {
        val job = jobs.value.firstOrNull { it.job.id == jobId }?.job
        val customer = job?.let { repo.customerOfContract(it.contractId) }
        edit { it.copy(jobId = jobId, customerId = customer ?: it.customerId, machineId = job?.machineId ?: it.machineId) }
    }

    fun save() {
        if (save.value.saving || save.value.saved) return
        viewModelScope.launch {
            save.update { it.copy(saving = true, messages = emptyList()) }
            val f = form.value
            val now = field.clock.nowMs()
            val result: FinanceResult = when (f.kind) {
                COLLECTION -> field.finance.cashCollection(
                    CashCollectionRequest(tenantId, clientId, f.customerId, f.jobId, f.amount, f.currency, f.reference, f.note, now),
                )
                HANDOVER -> field.finance.cashHandover(CashHandoverRequest(tenantId, clientId, f.amount, f.currency, f.reference, f.note, now))
                else -> field.finance.fuelEvent(
                    FuelEventRequest(tenantId, clientId, f.fuelType, f.amount, f.unitPrice, f.currency, f.machineId, f.jobId,
                        f.meter, f.supplier, f.note, now),
                )
            }
            save.update { it.after(result, NOT_VERIFIED_NOTE) }
        }
    }

    companion object {
        const val COLLECTION = "COLLECTION"
        const val HANDOVER = "HANDOVER"
        const val FUEL = "FUEL"
    }
}

@Composable
fun CashFormScreen(vm: CashFormViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val customers by vm.customers.collectAsStateWithLifecycle()
    val jobs by vm.jobs.collectAsStateWithLifecycle()
    val machines by vm.machines.collectAsStateWithLifecycle()
    val editable = !save.saved && !save.saving
    val jobOptions = jobs.map { PickerOption(it.job.id, it.job.jobNumber, it.machine?.let { m -> "${m.assetCode} · ${m.name}" }) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when (form.kind) {
            CashFormViewModel.COLLECTION -> {
                Text("Record cash collection", style = MaterialTheme.typography.headlineSmall)
                Text("Cash a customer paid you. It enters your custody and stays unverified until the office confirms it.",
                    style = MaterialTheme.typography.bodySmall)
                SearchablePickerField("Job (optional)", jobOptions, form.jobId, { vm.selectJob(it) }, noneLabel = "No job", enabled = editable)
                SearchablePickerField("Customer", customers, form.customerId, { id -> vm.edit { it.copy(customerId = id) } },
                    emptyText = "No customers synced yet. Customers of your jobs download automatically.", enabled = editable)
                DecimalField("Amount received", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
                TextInput("Reference / receipt number (optional)", form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
                TextInput("Note (optional)", form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
                SaveSection(save, "Save collection", vm::save, onDone)
            }
            CashFormViewModel.HANDOVER -> {
                Text("Hand over cash", style = MaterialTheme.typography.headlineSmall)
                Text("Cash you give to the office. It is a claim until the office verifies it; until then it still counts as yours.",
                    style = MaterialTheme.typography.bodySmall)
                DecimalField("Amount handed over", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
                TextInput("Reference (optional)", form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
                TextInput("Note (e.g. who received it)", form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
                SaveSection(save, "Save handover", vm::save, onDone)
            }
            else -> FuelFields(vm, form, save, jobOptions, machines, editable, onDone)
        }
    }
}

@Composable
private fun FuelFields(
    vm: CashFormViewModel,
    form: CashForm,
    save: SaveState,
    jobOptions: List<PickerOption>,
    machines: List<PickerOption>,
    editable: Boolean,
    onDone: () -> Unit,
) {
    Text("Fuel event", style = MaterialTheme.typography.headlineSmall)
    ChoiceChips(FuelEventType.entries, form.fuelType, { it.label }, { t -> vm.edit { it.copy(fuelType = t) } }, editable)
    SearchablePickerField("Job (optional)", jobOptions, form.jobId, { vm.selectJob(it) }, noneLabel = "No job", enabled = editable)
    SearchablePickerField(
        if (form.fuelType == FuelEventType.PURCHASE) "Machine (optional: none = into stock)" else "Machine",
        machines, form.machineId, { id -> vm.edit { it.copy(machineId = id) } },
        noneLabel = if (form.fuelType == FuelEventType.PURCHASE) "No machine (stock)" else null, enabled = editable,
    )
    DecimalField("Litres", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
    if (form.fuelType != FuelEventType.USAGE) {
        DecimalField("Unit price per litre", form.unitPrice, { v -> vm.edit { it.copy(unitPrice = v) } }, editable)
        TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
        val litres = AmountParser.valueOrNull(form.amount, DecimalLimit.LITRES)
        val price = AmountParser.valueOrNull(form.unitPrice, DecimalLimit.MONEY, allowZero = true)
        if (litres != null && price != null && form.currency.length == 3) {
            Text("Cost: ${formatMoney(CashRules.fuelCost(litres, price), form.currency)}", style = MaterialTheme.typography.bodyMedium)
        }
    }
    DecimalField("Hour-meter reading (optional)", form.meter, { v -> vm.edit { it.copy(meter = v) } }, editable)
    if (form.fuelType == FuelEventType.PURCHASE) {
        TextInput("Supplier (optional)", form.supplier, { v -> vm.edit { it.copy(supplier = v) } }, editable)
    }
    TextInput("Note (optional)", form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
    SaveSection(save, "Save fuel event", vm::save, onDone)
}
