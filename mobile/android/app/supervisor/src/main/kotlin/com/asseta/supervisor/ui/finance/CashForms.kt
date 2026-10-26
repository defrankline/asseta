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
import com.asseta.core.domain.accountability.DepositAccountOption
import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.accountability.RemittanceRequirements
import com.asseta.core.domain.accountability.RemittanceRules
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.CashRules
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.finance.FuelEventType
import com.asseta.core.domain.finance.formatMoney
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.usecase.CashCollectionRequest
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.FuelEventRequest
import com.asseta.core.sync.usecase.RemittanceDetails
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.ui.accountability.EvidencePhotos
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.DateTimeField
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.WarningColor
import com.asseta.supervisor.ui.accountability.FieldAccountabilityTexts
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.util.UUID

private val T = FieldAccountabilityTexts

/** Plain text fields of a cash/fuel form (validated by `CashRules` in the use case). */
data class CashForm(
    val kind: String = "", // COLLECTION | HANDOVER | FUEL
    val customerId: String? = null,
    val jobId: String? = null,
    val machineId: String? = null,
    val fuelType: FuelEventType? = FuelEventType.ISSUE,
    val amount: String = "",
    val unitPrice: String = "",
    val meter: String = "",
    val currency: String = "",
    val reference: String = "",
    val supplier: String = "",
    val note: String = "",
    /** When the cash was received / handed over or the fuel event happened (device time, not in the future). */
    val atMs: Long = 0,
    /** Another cash holder (recorders may record for others per tenant policy); null = me. */
    val holderId: String? = null,
    /** Remittance details (REMITTANCE_DETAILS_V1): how and where the money went, with deposit slip photos. */
    val method: RemittanceMethod = RemittanceMethod.CASH_TO_OFFICE,
    val depositAccountId: String? = null,
    val photos: List<CapturedPhoto> = emptyList(),
)

/** What the handover form shows for the remittance details (pure, unit-tested; same rules on iOS). */
object RemittanceForm {
    /** Picker rows: active accounts in the form's currency matching the method. */
    fun accountOptions(accounts: List<DepositAccountOption>, method: RemittanceMethod, currency: String): List<PickerOption> =
        RemittanceRules.accountsFor(accounts, method, currency).map { PickerOption(it.id, it.name, it.subtitle.takeIf { s -> s.isNotEmpty() }) }

    /** Choosing an account sets the method from its type; clearing it keeps the method. */
    fun selectAccount(form: CashForm, accountId: String?, accounts: List<DepositAccountOption>): CashForm {
        val account = accounts.firstOrNull { it.id == accountId }
        return form.copy(depositAccountId = accountId, method = RemittanceMethod.ofAccountType(account?.accountType) ?: form.method)
    }

    /** A new method drops an account of another type. */
    fun selectMethod(form: CashForm, method: RemittanceMethod, accounts: List<DepositAccountOption>): CashForm {
        val account = accounts.firstOrNull { it.id == form.depositAccountId }
        return form.copy(method = method, depositAccountId = form.depositAccountId.takeIf { account == null || account.accountType == method.accountType })
    }

    fun issues(form: CashForm, req: RemittanceRequirements, accounts: List<DepositAccountOption>): List<String> =
        RemittanceRules.check(req, form.method, form.depositAccountId, accounts.firstOrNull { it.id == form.depositAccountId }, form.currency,
            form.reference, form.photos.size)

    fun accountLabel(req: RemittanceRequirements): String = if (req.accountRequired) T.REMIT_ACCOUNT else T.REMIT_ACCOUNT_OPTIONAL

    fun referenceLabel(req: RemittanceRequirements, method: RemittanceMethod): String =
        if (RemittanceRules.referenceRequired(req, method)) T.REMIT_REFERENCE else T.REMIT_REFERENCE_OPTIONAL

    fun photosLabel(req: RemittanceRequirements): String = if (req.evidenceRequired) T.REMIT_PHOTOS else T.REMIT_PHOTOS_OPTIONAL
}

/** Wording of the cash and fuel forms shared with iOS. */
object CashTexts {
    fun fuelType(type: FuelEventType): String = when (type) {
        FuelEventType.PURCHASE -> "Purchase"
        FuelEventType.ISSUE -> "Issue"
        FuelEventType.USAGE -> "Usage"
    }

    fun fuelExplanation(type: FuelEventType?): String = when (type) {
        FuelEventType.PURCHASE -> "Fuel bought into stock. Record the money spent as an expense too."
        FuelEventType.ISSUE -> "Fuel given to a machine from stock."
        FuelEventType.USAGE, null -> "Fuel a machine consumed (no price)."
    }

    /** "Cost: X CUR" for priced fuel events when litres, price and currency are all valid; else null. */
    fun fuelCost(type: FuelEventType?, litres: String, unitPrice: String, currency: String): String? {
        if (type == FuelEventType.USAGE || type == null || currency.length != 3) return null
        val l = AmountParser.valueOrNull(litres, DecimalLimit.LITRES) ?: return null
        val p = AmountParser.valueOrNull(unitPrice, DecimalLimit.MONEY, allowZero = true) ?: return null
        return "Cost: ${formatMoney(CashRules.fuelCost(l, p).stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }, currency)}"
    }
}

/** [enabled]: the server announced REMITTANCE_DETAILS_V1; [requirements]: the tenant's CASH_CUSTODY requirements. */
data class RemittanceAccess(val enabled: Boolean, val requirements: RemittanceRequirements)

/** Collection, handover and fuel forms share one view model; the client id is generated once per visit. */
class CashFormViewModel(
    private val field: FieldGraph,
    private val tenantId: String,
    kind: String,
    private val permissions: Set<String> = emptySet(),
) : ViewModel() {
    private val clientId = UUID.randomUUID().toString()
    val form = MutableStateFlow(CashForm(kind = kind, atMs = field.clock.nowMs()))
    val save = MutableStateFlow(SaveState())
    private val repo = field.financeRepository

    val customers: StateFlow<List<PickerOption>> = repo.observeCustomers(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.name, it.code, it.contactName) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val jobs: StateFlow<List<JobSummary>> = repo.observeJobs(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val machines: StateFlow<List<PickerOption>> = repo.observeMachines(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.assetCode, it.name) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** "Your cash" on the handover form: the estimated cash in hand per currency. */
    val custody: StateFlow<List<CustodyLine>> = repo.observeCashView(tenantId).map { it.lines }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** Company deposit accounts saved from sync (picker filters active ones of the form's currency and method). */
    val depositAccounts: StateFlow<List<DepositAccountOption>> = repo.observeDepositAccounts(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** Whether the server takes remittance details, and the tenant's requirements on them. */
    val remittance = MutableStateFlow(RemittanceAccess(false, RemittanceRequirements()))

    /** The cash holders a recorder may record for (empty unless the tenant policy allows it). */
    val holders = MutableStateFlow<List<PickerOption>>(emptyList())
    val me = MutableStateFlow<String?>(null)

    init {
        viewModelScope.launch { repo.baseCurrency(tenantId)?.let { c -> form.update { it.copy(currency = c) } } }
        viewModelScope.launch {
            me.value = field.accountability.myStaffId(tenantId)
            val access = field.accountability.access(tenantId, permissions)
            remittance.value = RemittanceAccess(access.remittanceDetails, access.remittanceRequirements)
            if (access.recordForOthers) {
                holders.value = com.asseta.supervisor.ui.accountability.custodianOptions(field.accountability.cache.value.custodians, me.value)
            }
        }
    }

    private fun holder(): String? = form.value.holderId?.takeIf { holders.value.isNotEmpty() && it != me.value }

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
            val at = f.atMs.coerceAtMost(field.clock.nowMs())
            val result: FinanceResult = when (f.kind) {
                COLLECTION -> field.finance.cashCollection(
                    CashCollectionRequest(tenantId, clientId, f.customerId, f.jobId, f.amount, f.currency, f.reference, f.note, at, holder()),
                )
                HANDOVER -> {
                    val r = remittance.value
                    val details = if (r.enabled) RemittanceDetails(f.method, f.depositAccountId, f.photos.map { it.jpeg }, r.requirements) else null
                    field.finance.cashHandover(CashHandoverRequest(tenantId, clientId, f.amount, f.currency, f.reference, f.note, at, holder(), details))
                }
                else -> field.finance.fuelEvent(
                    FuelEventRequest(tenantId, clientId, f.fuelType, f.amount, f.unitPrice, f.currency, f.machineId, f.jobId,
                        f.meter, if (f.fuelType == FuelEventType.PURCHASE) f.supplier else "", f.note, at),
                )
            }
            save.update { it.after(result) }
        }
    }

    fun onPhotoError(message: String) = save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

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
    val custody by vm.custody.collectAsStateWithLifecycle()
    val holders by vm.holders.collectAsStateWithLifecycle()
    val me by vm.me.collectAsStateWithLifecycle()
    val accounts by vm.depositAccounts.collectAsStateWithLifecycle()
    val remittance by vm.remittance.collectAsStateWithLifecycle()
    val editable = !save.saved && !save.saving
    // Recorders may record for another cash holder when the company allows it (operators hold cash without a login).
    val holderPicker: @Composable () -> Unit = {
        if (holders.isNotEmpty()) {
            SearchablePickerField(FieldAccountabilityTexts.CASH_HOLDER, holders, form.holderId ?: me, { id -> vm.edit { it.copy(holderId = id) } },
                emptyText = FieldAccountabilityTexts.CUSTODIANS_EMPTY, enabled = editable)
        }
    }
    val now = System.currentTimeMillis()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when (form.kind) {
            CashFormViewModel.COLLECTION -> {
                Section(null) {
                    SearchablePickerField("Job (optional)", jobOptions(jobs), form.jobId, { vm.selectJob(it) }, noneLabel = "No job", enabled = editable)
                    SearchablePickerField("Customer", customers, form.customerId, { id -> vm.edit { it.copy(customerId = id) } },
                        emptyText = "Customers of your jobs appear here after a sync.", enabled = editable)
                    holderPicker()
                }
                Section(null, footer = "The cash is added to your custody once the server accepts it. The office verifies it later.") {
                    DecimalField("Amount", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                    TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
                    TextInput("Receipt / reference number (optional)", form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
                    DateTimeField("Received", form.atMs, { v -> vm.edit { it.copy(atMs = v) } }, editable, notAfter = now)
                    TextInput("Note (optional)", form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
                }
                SaveSection(save, vm::save, onDone, enabled = form.customerId != null && form.amount.isNotEmpty())
            }
            CashFormViewModel.HANDOVER -> {
                if (custody.isNotEmpty()) {
                    Section("Your cash") {
                        custody.forEach { LabeledRow(it.currency, it.estimatedInHand.plainText()) }
                    }
                }
                val details = remittance.enabled
                val req = remittance.requirements
                Section(null, footer = "Your custody goes down only when finance verifies the handover.") {
                    holderPicker()
                    DecimalField("Amount handed over", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                    TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
                    if (!details) TextInput("Reference (deposit slip, receipt no.)", form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
                    DateTimeField("Handed over", form.atMs, { v -> vm.edit { it.copy(atMs = v) } }, editable, notAfter = now)
                    TextInput("Note (who received it…)", form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
                }
                var issues = emptyList<String>()
                if (details) {
                    Section(T.REMIT_METHOD) {
                        SegmentedChoice(RemittanceMethod.entries, form.method, T::remitMethod,
                            { m -> vm.edit { RemittanceForm.selectMethod(it, m, accounts) } }, editable)
                        SearchablePickerField(RemittanceForm.accountLabel(req), RemittanceForm.accountOptions(accounts, form.method, form.currency),
                            form.depositAccountId, { id -> vm.edit { RemittanceForm.selectAccount(it, id, accounts) } },
                            noneLabel = T.REMIT_ACCOUNT_NONE, emptyText = T.REMIT_ACCOUNTS_EMPTY, enabled = editable)
                        TextInput(RemittanceForm.referenceLabel(req, form.method), form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
                    }
                    EvidencePhotos(form.photos, { p -> vm.edit { it.copy(photos = it.photos + p) } },
                        { i -> vm.edit { it.copy(photos = it.photos.filterIndexed { j, _ -> j != i }) } }, vm::onPhotoError, editable,
                        title = RemittanceForm.photosLabel(req), footer = T.REMIT_PHOTOS_FOOTER, photograph = T.REMIT_PHOTOGRAPH,
                        addPhoto = T.REMIT_ADD_PHOTO, remove = T.REMIT_REMOVE_PHOTO)
                    issues = RemittanceForm.issues(form, req, accounts)
                    if (issues.isNotEmpty() && save.messages.isEmpty() && form.amount.isNotEmpty()) Section(null) { issues.forEach { Text(it, color = WarningColor) } }
                }
                SaveSection(save, vm::save, onDone, enabled = form.amount.isNotEmpty() && issues.isEmpty())
            }
            else -> FuelFields(vm, form, save, jobOptions(jobs), machines, editable, now, onDone)
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
    now: Long,
    onDone: () -> Unit,
) {
    SegmentedChoice(FuelEventType.entries, form.fuelType, CashTexts::fuelType, { t -> vm.edit { it.copy(fuelType = t) } }, editable)
    Section(null, footer = CashTexts.fuelExplanation(form.fuelType)) {
        DecimalField("Litres", form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
        if (form.fuelType != FuelEventType.USAGE) {
            DecimalField("Price per litre", form.unitPrice, { v -> vm.edit { it.copy(unitPrice = v) } }, editable)
            TextInput("Currency", form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
            CashTexts.fuelCost(form.fuelType, form.amount, form.unitPrice, form.currency)?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium)
            }
        }
        if (form.fuelType == FuelEventType.PURCHASE) {
            TextInput("Supplier (optional)", form.supplier, { v -> vm.edit { it.copy(supplier = v) } }, editable)
        }
        DateTimeField("When", form.atMs, { v -> vm.edit { it.copy(atMs = v) } }, editable, notAfter = now)
    }
    Section("Machine") {
        SearchablePickerField("Job", jobOptions, form.jobId, { vm.selectJob(it) }, noneLabel = "No job", enabled = editable)
        SearchablePickerField(
            "Machine", machines, form.machineId, { id -> vm.edit { it.copy(machineId = id) } },
            noneLabel = if (form.fuelType == FuelEventType.PURCHASE) "No machine (stock)" else null, enabled = editable && form.jobId == null,
        )
        DecimalField("Meter reading (optional)", form.meter, { v -> vm.edit { it.copy(meter = v) } }, editable)
    }
    Section(null) { TextInput("Note (optional)", form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false) }
    val issues = CashRules.fuel(form.fuelType, form.amount, form.unitPrice, form.currency, form.machineId, form.meter, form.supplier, form.note)
    val visible = (issues as? FormCheck.Invalid)?.messages.orEmpty().filterNot { it.startsWith("Enter the") }
    if (visible.isNotEmpty() && save.messages.isEmpty()) Section(null) { visible.forEach { Text(it, color = WarningColor) } }
    SaveSection(save, vm::save, onDone, enabled = issues is FormCheck.Valid)
}

/** Plain digits for amounts (never localized grouping, which could be misread). */
fun BigDecimal.plainText(): String = stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }.toPlainString()
