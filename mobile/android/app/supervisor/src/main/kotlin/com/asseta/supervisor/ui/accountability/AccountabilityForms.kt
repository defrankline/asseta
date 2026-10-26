package com.asseta.supervisor.ui.accountability

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.accountability.HoursSaleDraft
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.sync.CustodianDto
import com.asseta.core.model.sync.FieldHoursPurchaseDto
import com.asseta.core.sync.data.FieldAccountabilityCache
import com.asseta.core.sync.data.RetentionResult
import com.asseta.core.sync.usecase.CashAckRequest
import com.asseta.core.sync.usecase.CashTransferRequest
import com.asseta.core.sync.usecase.HoursSaleRequest
import com.asseta.core.sync.usecase.HoursTransferRequest
import com.asseta.core.sync.usecase.RetentionRequest
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CameraCapture
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.capture.PermissionRationale
import com.asseta.supervisor.capture.hasAllPermissions
import com.asseta.supervisor.ui.DateTimeField
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.FormSaveAction
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.NoticeCard
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.WarningColor
import com.asseta.supervisor.ui.finance.DecimalField
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SaveSection
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.SearchablePickerField
import com.asseta.supervisor.ui.finance.SegmentedChoice
import com.asseta.supervisor.ui.finance.TextInput
import com.asseta.supervisor.ui.finance.after
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

private val T = FieldAccountabilityTexts

/** Cash holders as picker options; [me] is listed first as "Me". */
fun custodianOptions(custodians: List<CustodianDto>, me: String?): List<PickerOption> {
    val mine = listOfNotNull(me?.let { PickerOption(it, T.ME, custodians.firstOrNull { c -> c.staffMemberId == it }?.fullName) })
    return mine + custodians.filter { it.staffMemberId != me }.sortedBy { it.fullName.lowercase() }
        .map { PickerOption(it.staffMemberId, it.fullName, it.employeeCode) }
}

/** Purchases with hours left, as picker options ("HP-2026-00012 · 12.5 h left", customer below). */
fun purchaseOptions(purchases: List<FieldHoursPurchaseDto>): List<PickerOption> = purchases.map {
    PickerOption(it.id, T.purchaseOption(it.purchaseNumber, it.totals.remaining), it.customerName, it.purchaseNumber)
}

/** Base for the accountability forms: the user's access (capabilities + permissions + saved policies) and saved data. */
abstract class AccountabilityFormViewModel(protected val field: FieldGraph, protected val tenantId: String, private val permissions: Set<String>) : ViewModel() {
    protected val clientId: String = UUID.randomUUID().toString()
    private val _access = MutableStateFlow<FieldAccess?>(null)
    val access: StateFlow<FieldAccess?> = _access.asStateFlow()
    val cache: StateFlow<FieldAccountabilityCache> = field.accountability.cache
    protected val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()
    private val _me = MutableStateFlow<String?>(null)
    val me: StateFlow<String?> = _me.asStateFlow()

    init {
        viewModelScope.launch {
            _me.value = field.accountability.myStaffId(tenantId)
            _access.value = field.accountability.access(tenantId, permissions)
            // Fresh lists when online; the saved copy keeps the form usable offline.
            if (field.accountability.refresh(tenantId, permissions)) _access.value = field.accountability.access(tenantId, permissions)
        }
    }

    protected fun saving(): Boolean {
        if (_save.value.saving || _save.value.saved) return true
        _save.update { it.copy(saving = true, messages = emptyList()) }
        return false
    }
}

// --- Sell customer hours -----------------------------------------------------------------------------------------

data class HoursSaleForm(
    val walkIn: Boolean = false,
    val customerId: String? = null,
    val walkInName: String = "",
    val walkInPhone: String = "",
    val machineId: String? = null,
    val hours: String = "",
    val paidNow: Boolean = true,
    val method: PaymentMethod = PaymentMethod.CASH,
    val amount: String = "",
    val reference: String = "",
    val note: String = "",
    val holderId: String? = null,
    val atMs: Long = 0,
    val photos: List<CapturedPhoto> = emptyList(),
) {
    fun draft() = HoursSaleDraft(walkIn, customerId, walkInName, walkInPhone, machineId, hours, paidNow, method, amount, reference, note)
}

class HoursSaleViewModel(field: FieldGraph, tenantId: String, permissions: Set<String>) : AccountabilityFormViewModel(field, tenantId, permissions) {
    val form = MutableStateFlow(HoursSaleForm(atMs = field.clock.nowMs()))
    val customers: StateFlow<List<PickerOption>> = field.financeRepository.observeCustomers(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.name, it.code, it.contactName) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val machines: StateFlow<List<PickerOption>> = field.financeRepository.observeMachines(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.assetCode, it.name) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun edit(change: (HoursSaleForm) -> HoursSaleForm) {
        form.update(change)
        _save.update { it.copy(messages = emptyList()) }
    }

    fun onPhotoError(message: String) = _save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    fun save() {
        if (saving()) return
        val f = form.value
        val a = access.value
        viewModelScope.launch {
            val result = field.accountabilityCapture.hoursSale(
                HoursSaleRequest(
                    tenantId, clientId, f.draft(), walkInAllowed = a?.walkIn == true,
                    cashHolderId = f.holderId?.takeIf { a?.recordForOthers == true && it != me.value },
                    receivedAtMs = f.atMs.coerceAtMost(field.clock.nowMs()), evidenceJpegs = f.photos.map { it.jpeg },
                ),
            )
            _save.update { it.after(result) }
        }
    }
}

@Composable
fun HoursSaleScreen(vm: HoursSaleViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    val cache by vm.cache.collectAsStateWithLifecycle()
    val me by vm.me.collectAsStateWithLifecycle()
    val customers by vm.customers.collectAsStateWithLifecycle()
    val machines by vm.machines.collectAsStateWithLifecycle()
    val a = access ?: return
    val editable = !save.saving && !save.saved
    val now = System.currentTimeMillis()
    FormColumn {
        if (!a.sellHours) {
            NoticeCard(T.TITLE_HOURS_SALE, if (a.hours == null) T.NEEDS_RULES else T.HOURS_OFF, isError = true)
            return@FormColumn
        }
        Section(T.SECTION_CUSTOMER, footer = if (form.walkIn) T.WALK_IN_FOOTER else null) {
            if (a.walkIn) SegmentedChoice(listOf(false, true), form.walkIn, { if (it) T.WALK_IN else T.REGISTERED }, { w -> vm.edit { it.copy(walkIn = w) } }, editable)
            if (form.walkIn) {
                TextInput(T.WALK_IN_NAME, form.walkInName, { v -> vm.edit { it.copy(walkInName = v) } }, editable)
                TextInput(T.WALK_IN_PHONE, form.walkInPhone, { v -> vm.edit { it.copy(walkInPhone = v) } }, editable)
            } else {
                SearchablePickerField(T.CUSTOMER, customers, form.customerId, { id -> vm.edit { it.copy(customerId = id) } }, emptyText = T.CUSTOMER_EMPTY, enabled = editable)
            }
        }
        Section(T.SECTION_HOURS, footer = T.HOURS_FOOTER) {
            SearchablePickerField(T.MACHINE, machines, form.machineId, { id -> vm.edit { it.copy(machineId = id) } }, enabled = editable)
            DecimalField(T.HOURS, form.hours, { v -> vm.edit { it.copy(hours = v) } }, editable)
            TextInput(T.NOTE_OPTIONAL, form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
        }
        Section(T.SECTION_PAYMENT, footer = if (form.paidNow) T.PAYMENT_FOOTER else T.NOT_PAID_FOOTER) {
            SegmentedChoice(listOf(true, false), form.paidNow, { if (it) T.PAID_NOW else T.NOT_PAID }, { p -> vm.edit { it.copy(paidNow = p) } }, editable)
            if (form.paidNow) {
                SegmentedChoice(PaymentMethod.entries, form.method, T::method, { m -> vm.edit { it.copy(method = m) } }, editable)
                DecimalField(T.AMOUNT_RECEIVED, form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                if (form.method != PaymentMethod.CASH) TextInput(T.REFERENCE, form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable)
                DateTimeField(T.RECEIVED, form.atMs, { v -> vm.edit { it.copy(atMs = v) } }, editable, notAfter = now)
                if (form.method == PaymentMethod.CASH && a.recordForOthers) {
                    SearchablePickerField(T.CASH_HOLDER, custodianOptions(cache.custodians, me), form.holderId ?: me, { id -> vm.edit { it.copy(holderId = id) } },
                        emptyText = T.CUSTODIANS_EMPTY, enabled = editable)
                }
            }
        }
        if (form.paidNow) {
            EvidencePhotos(form.photos, { p -> vm.edit { it.copy(photos = it.photos + p) } }, { i -> vm.edit { it.copy(photos = it.photos.filterIndexed { j, _ -> j != i }) } },
                vm::onPhotoError, editable)
        }
        val check = AccountabilityRules.hoursSale(form.draft(), a.walkIn)
        SaveSection(save, vm::save, onDone, enabled = check is FormCheck.Valid)
    }
}

/** Payment evidence photos through the in-app camera (originals stored encrypted on save; at most ten). */
@Composable
fun EvidencePhotos(
    photos: List<CapturedPhoto>,
    onAdd: (CapturedPhoto) -> Unit,
    onRemove: (Int) -> Unit,
    onError: (String) -> Unit,
    enabled: Boolean,
    title: String = T.EVIDENCE,
    footer: String = T.EVIDENCE_FOOTER,
    photograph: String = T.PHOTOGRAPH,
    addPhoto: String = T.ADD_PHOTO,
    remove: String = "Remove",
) {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var open by remember { mutableStateOf(false) }
    Section(title, footer = footer) {
        photos.forEachIndexed { index, photo ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                val preview = remember(photo) { MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)?.asImageBitmap() }
                preview?.let { Image(it, "$title ${index + 1}", Modifier.weight(1f).heightIn(max = 120.dp), contentScale = ContentScale.Fit, alignment = Alignment.CenterStart) }
                if (enabled) TextButton(onClick = { onRemove(index) }) { Text(remove, color = palette.offline) }
            }
        }
        when {
            !enabled -> Unit
            open && !granted -> PermissionRationale(
                title = "Camera",
                rationale = footer,
                permissions = arrayOf(Manifest.permission.CAMERA),
                onResult = { granted = it; if (!it) open = false },
            )
            open -> CameraCapture(buttonLabel = photograph, onCaptured = { onAdd(it); open = false }, onError = { onError(it); open = false })
            photos.size < MAX_PHOTOS -> OutlinedButton(onClick = { open = true }) { Text(if (photos.isEmpty()) photograph else addPhoto) }
        }
    }
}

private const val MAX_PHOTOS = 10

@Composable
fun FormColumn(content: @Composable () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) { content() }
}

// --- Request hours transfer --------------------------------------------------------------------------------------

data class HoursTransferForm(
    val purchaseId: String? = null,
    val fromMachineId: String? = null,
    val toMachineId: String? = null,
    val hours: String = "",
    val reasonCodeId: String? = null,
    val reason: String = "",
)

class HoursTransferViewModel(field: FieldGraph, tenantId: String, permissions: Set<String>) : AccountabilityFormViewModel(field, tenantId, permissions) {
    val form = MutableStateFlow(HoursTransferForm())
    val machines: StateFlow<List<PickerOption>> = field.financeRepository.observeMachines(tenantId)
        .map { list -> list.map { PickerOption(it.id, it.assetCode, it.name) } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun edit(change: (HoursTransferForm) -> HoursTransferForm) {
        form.update(change)
        _save.update { it.copy(messages = emptyList()) }
    }

    /** A purchase pre-selects the machine its hours are on. */
    fun selectPurchase(id: String?) = edit { f ->
        val p = cache.value.purchases.firstOrNull { it.id == id }
        f.copy(purchaseId = id, fromMachineId = p?.let(::defaultFrom))
    }

    fun purchase(): FieldHoursPurchaseDto? = cache.value.purchases.firstOrNull { it.id == form.value.purchaseId }

    fun remaining() = purchase()?.let { p -> AccountabilityRules.remainingOn(form.value.fromMachineId, p.machines.associate { it.machineId to it.remaining }, p.totals.remaining) }

    fun save() {
        if (saving()) return
        val f = form.value
        viewModelScope.launch {
            val result = field.accountabilityCapture.hoursTransfer(
                HoursTransferRequest(tenantId, clientId, f.purchaseId, f.fromMachineId, f.toMachineId, f.hours, remaining(), f.reason,
                    f.reasonCodeId, access.value?.hours?.reasonCodeRequired == true),
            )
            _save.update { it.after(result) }
        }
    }

    companion object {
        /** The purchase's own machine when hours are left on it, else the first machine holding hours. */
        fun defaultFrom(p: FieldHoursPurchaseDto): String {
            val withHours = p.machines.filter { (it.remaining.toBigDecimalOrNull()?.signum() ?: 0) > 0 }.map { it.machineId }
            return if (withHours.isEmpty() || p.machineId in withHours) p.machineId else withHours.first()
        }
    }
}

@Composable
fun HoursTransferScreen(vm: HoursTransferViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    val cache by vm.cache.collectAsStateWithLifecycle()
    val machines by vm.machines.collectAsStateWithLifecycle()
    val a = access ?: return
    val editable = !save.saving && !save.saved
    FormColumn {
        if (!a.requestHoursTransfer) {
            NoticeCard(T.TITLE_HOURS_TRANSFER, if (a.hours == null) T.NEEDS_RULES else T.HOURS_OFF, isError = true)
            return@FormColumn
        }
        val purchases = cache.purchasesWithHours()
        val p = purchases.firstOrNull { it.id == form.purchaseId }
        val requiresApproval = a.hours?.transferRequiresApproval != false
        Section(null, footer = if (requiresApproval) T.TRANSFER_FOOTER_APPROVAL else T.TRANSFER_FOOTER_DIRECT) {
            if (purchases.isEmpty()) Text(T.PURCHASES_EMPTY, color = palette.secondaryText)
            SearchablePickerField(T.PURCHASE, purchaseOptions(purchases), form.purchaseId, vm::selectPurchase, emptyText = T.PURCHASES_EMPTY, enabled = editable)
            if (p != null) {
                val holding = p.machines.filter { (it.remaining.toBigDecimalOrNull()?.signum() ?: 0) > 0 }.map { it.machineId }.ifEmpty { listOf(p.machineId) }
                val fromOptions = machines.filter { it.id in holding }.ifEmpty { holding.map { PickerOption(it, it.take(8)) } }
                SearchablePickerField(T.FROM_MACHINE, fromOptions, form.fromMachineId, { id -> vm.edit { it.copy(fromMachineId = id) } }, enabled = editable && holding.size > 1)
            }
            SearchablePickerField(T.TO_MACHINE, machines.filter { it.id != form.fromMachineId }, form.toMachineId, { id -> vm.edit { it.copy(toMachineId = id) } }, enabled = editable)
            DecimalField(T.HOURS_TO_MOVE, form.hours, { v -> vm.edit { it.copy(hours = v) } }, editable)
        }
        Section(T.REASON) {
            val reasons = cache.transferReasons.map { PickerOption(it.id, it.label, it.code) }
            if (reasons.isNotEmpty() || a.hours?.reasonCodeRequired == true) {
                val required = a.hours?.reasonCodeRequired == true
                SearchablePickerField(if (required) T.REASON_CATEGORY else T.REASON_CATEGORY_OPTIONAL, reasons, form.reasonCodeId,
                    { id -> vm.edit { it.copy(reasonCodeId = id) } }, noneLabel = if (required) null else T.NO_CATEGORY, enabled = editable)
            }
            TextInput(T.REASON, form.reason, { v -> vm.edit { it.copy(reason = v) } }, editable, singleLine = false)
        }
        val check = AccountabilityRules.hoursTransfer(form.purchaseId, form.fromMachineId, form.toMachineId, form.hours, vm.remaining(), form.reason,
            form.reasonCodeId, a.hours?.reasonCodeRequired == true)
        (check as? FormCheck.Invalid)?.messages?.filter { it.startsWith("Only") || it.startsWith("Choose a different") }?.takeIf { it.isNotEmpty() && save.messages.isEmpty() }
            ?.let { msgs -> Section(null) { msgs.forEach { Text(it, color = WarningColor) } } }
        SaveSection(save, vm::save, onDone, enabled = check is FormCheck.Valid)
    }
}

// --- Transfer cash -----------------------------------------------------------------------------------------------

data class CashTransferForm(
    val fromId: String? = null,
    val toId: String? = null,
    val amount: String = "",
    val currency: String = "",
    val received: String = "",
    val note: String = "",
    val atMs: Long = 0,
)

class CashTransferViewModel(field: FieldGraph, tenantId: String, permissions: Set<String>) : AccountabilityFormViewModel(field, tenantId, permissions) {
    val form = MutableStateFlow(CashTransferForm(atMs = field.clock.nowMs()))

    init {
        viewModelScope.launch { field.financeRepository.baseCurrency(tenantId)?.let { c -> form.update { it.copy(currency = c) } } }
    }

    fun edit(change: (CashTransferForm) -> CashTransferForm) {
        form.update(change)
        _save.update { it.copy(messages = emptyList()) }
    }

    fun selfAck(): Boolean = access.value?.cash?.recorderReceiverCountsAsAck == true

    fun save() {
        if (saving()) return
        val f = form.value
        viewModelScope.launch {
            val result = field.accountabilityCapture.cashTransfer(
                CashTransferRequest(tenantId, clientId, f.fromId, f.toId, me.value, f.amount, f.currency, selfAck(), f.received, f.note,
                    f.atMs.coerceAtMost(field.clock.nowMs())),
            )
            _save.update { it.after(result) }
        }
    }
}

@Composable
fun CashTransferScreen(vm: CashTransferViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    val cache by vm.cache.collectAsStateWithLifecycle()
    val me by vm.me.collectAsStateWithLifecycle()
    val a = access ?: return
    val editable = !save.saving && !save.saved
    val now = System.currentTimeMillis()
    val from = form.fromId ?: me
    val receiverIsMe = form.toId != null && form.toId == me
    val selfAck = receiverIsMe && vm.selfAck()
    FormColumn {
        if (!a.transferCash) {
            NoticeCard(T.TITLE_CASH_TRANSFER, unavailableMessage(a), isError = true)
            return@FormColumn
        }
        val footer = when {
            selfAck -> T.CASH_FOOTER_SELF
            a.cash?.transferAckRequired == false -> T.CASH_FOOTER_NO_ACK
            else -> T.CASH_FOOTER_ACK
        }
        val options = custodianOptions(cache.custodians, me)
        Section(null, footer = footer) {
            SearchablePickerField(T.FROM, options, from, { id -> vm.edit { it.copy(fromId = id) } }, emptyText = T.CUSTODIANS_EMPTY,
                enabled = editable && a.recordForOthers)
            SearchablePickerField(T.TO, options.filter { it.id != from }, form.toId, { id -> vm.edit { it.copy(toId = id) } },
                emptyText = T.CUSTODIANS_EMPTY, enabled = editable)
            DecimalField(T.AMOUNT_HANDED, form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
            TextInput(T.CURRENCY, form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
            if (selfAck) DecimalField(T.AMOUNT_YOU_RECEIVED, form.received, { v -> vm.edit { it.copy(received = v) } }, editable)
            DateTimeField(T.TRANSFERRED, form.atMs, { v -> vm.edit { it.copy(atMs = v) } }, editable, notAfter = now)
            TextInput(T.NOTE_OPTIONAL, form.note, { v -> vm.edit { it.copy(note = v) } }, editable, singleLine = false)
        }
        val check = AccountabilityRules.cashTransfer(from, form.toId, form.amount, form.currency, receiverIsMe, vm.selfAck(), form.received, form.note)
        SaveSection(save, vm::save, onDone, enabled = check is FormCheck.Valid)
    }
}

private fun unavailableMessage(a: FieldAccess): String = if (a.capabilities == null) T.NEEDS_RULES else com.asseta.core.sync.usecase.CaptureMeterReading.SERVER_TOO_OLD

// --- Acknowledge a transfer or a float ---------------------------------------------------------------------------

class CashAckViewModel(field: FieldGraph, tenantId: String, permissions: Set<String>, val targetId: String, val isFloat: Boolean) :
    AccountabilityFormViewModel(field, tenantId, permissions) {
    val received = MutableStateFlow<String?>(null)
    val note = MutableStateFlow("")
    private val _waiting = MutableStateFlow(false)

    /** This phone already answered (waiting to sync). */
    val waiting: StateFlow<Boolean> = _waiting.asStateFlow()

    init {
        viewModelScope.launch { _waiting.value = field.accountabilityCapture.answered(tenantId, targetId, isFloat) }
    }

    fun answer(acknowledge: Boolean, declared: String) {
        if (saving()) return
        viewModelScope.launch {
            val result = field.accountabilityCapture.acknowledge(
                CashAckRequest(tenantId, targetId, isFloat, acknowledge, received.value ?: declared, note.value),
            )
            _save.update { it.after(result) }
        }
    }
}

@Composable
fun CashAckScreen(vm: CashAckViewModel, onDone: () -> Unit) {
    val save by vm.save.collectAsStateWithLifecycle()
    val cache by vm.cache.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    val waiting by vm.waiting.collectAsStateWithLifecycle()
    val receivedText by vm.received.collectAsStateWithLifecycle()
    val note by vm.note.collectAsStateWithLifecycle()
    val a = access ?: return
    val transfer = if (vm.isFloat) null else cache.transfers.firstOrNull { it.id == vm.targetId }
    val float = if (vm.isFloat) cache.floats.firstOrNull { it.id == vm.targetId } else null
    val declared = transfer?.amountDeclared ?: float?.amount
    val currency = transfer?.currency ?: float?.currency.orEmpty()
    val editable = !save.saving && !save.saved && !waiting
    FormColumn {
        if (declared == null) {
            EmptyState(if (vm.isFloat) T.TITLE_ACK_FLOAT else T.TITLE_ACK_TRANSFER, T.ACK_NOT_FOUND)
            return@FormColumn
        }
        if (!a.acknowledgeCash) {
            NoticeCard(if (vm.isFloat) T.TITLE_ACK_FLOAT else T.TITLE_ACK_TRANSFER, unavailableMessage(a), isError = true)
            return@FormColumn
        }
        Section(null) {
            Text(if (float != null) T.FLOAT_FROM_OFFICE else T.transferFrom(T.colleague(transfer?.fromStaffName, cache.custodianName(transfer?.fromStaffId), transfer?.fromStaffId)))
            LabeledRow(T.DECLARED, "$declared $currency")
            LabeledRow(if (float != null) T.ISSUED else T.SENT, LocalTime.formatIso(transfer?.transferredAt ?: float!!.occurredAt))
            (transfer?.note ?: float?.note)?.takeIf { it.isNotBlank() }?.let { Text(it, color = palette.secondaryText) }
        }
        if (waiting) {
            Section(null) { Text(T.ACK_WAITING, color = WarningColor) }
            return@FormColumn
        }
        Section(null, footer = T.ACK_FOOTER) {
            DecimalField(T.ACK_AMOUNT, receivedText ?: declared, { v -> vm.received.value = v }, editable)
            TextInput(T.NOTE_OPTIONAL, note, { v -> vm.note.value = v }, editable, singleLine = false)
        }
        SaveSection(save, { vm.answer(true, declared) }, onDone, enabled = editable, label = T.ACKNOWLEDGE)
        OutlinedButton(onClick = { vm.answer(false, declared) }, enabled = editable && note.isNotBlank()) { Text(T.DISPUTE, color = palette.offline) }
        if (note.isBlank()) Text(T.DISPUTE_REASON, color = palette.secondaryText)
    }
}

// --- Ask to keep cash (online) ------------------------------------------------------------------------------------

data class RetentionForm(
    val holderId: String? = null,
    val amount: String = "",
    val currency: String = "",
    val reasonId: String? = null,
    val reason: String = "",
)

class RetentionViewModel(field: FieldGraph, tenantId: String, permissions: Set<String>) : AccountabilityFormViewModel(field, tenantId, permissions) {
    val form = MutableStateFlow(RetentionForm())
    private val _sent = MutableStateFlow<String?>(null)
    val sent: StateFlow<String?> = _sent.asStateFlow()

    init {
        viewModelScope.launch { field.financeRepository.baseCurrency(tenantId)?.let { c -> form.update { it.copy(currency = c) } } }
    }

    fun edit(change: (RetentionForm) -> RetentionForm) {
        form.update(change)
        _save.update { it.copy(messages = emptyList()) }
    }

    fun send() {
        val f = form.value
        val values = when (val check = AccountabilityRules.retention(f.amount, f.currency, f.reason)) {
            is FormCheck.Invalid -> return _save.update { it.copy(messages = check.messages) }
            is FormCheck.Valid -> check.value
        }
        if (saving()) return
        viewModelScope.launch {
            val holder = f.holderId?.takeIf { access.value?.recordForOthers == true && it != me.value }
            if (access.value?.retentionOffline == true) {
                // Offline-capable: queued in the outbox (CASH_RETENTION_REQUEST, idempotent by this visit's client id).
                val result = field.accountabilityCapture.retention(
                    RetentionRequest(tenantId, clientId, f.amount, f.currency, f.reason, f.reasonId, holder),
                )
                _save.update { it.after(result) }
                if (_save.value.saved) _sent.value = T.RETENTION_SAVED
                return@launch
            }
            when (val r = field.accountability.requestRetention(values.amount, values.currency, values.reason, f.reasonId, holder, clientId)) {
                is RetentionResult.Sent -> {
                    _sent.value = T.RETENTION_SENT
                    _save.value = SaveState()
                }
                is RetentionResult.Refused -> _save.value = SaveState(messages = listOf(r.message))
            }
        }
    }

    /** The key the status screen opens: this visit's client id (queued) or the server id (sent online). */
    val statusKey: String get() = clientId
}

@Composable
fun RetentionScreen(vm: RetentionViewModel, onDone: () -> Unit, onStatus: (String) -> Unit = {}) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    val cache by vm.cache.collectAsStateWithLifecycle()
    val me by vm.me.collectAsStateWithLifecycle()
    val a = access ?: return
    val editable = !save.saving && !save.saved
    FormColumn {
        if (!a.askToKeepCash) {
            NoticeCard(T.TITLE_RETENTION, if (a.cash == null) T.NEEDS_RULES else T.RETENTION_OFF, isError = true)
            return@FormColumn
        }
        Section(null, footer = T.RETENTION_FOOTER) {
            if (a.recordForOthers) {
                SearchablePickerField(T.CASH_HOLDER, custodianOptions(cache.custodians, me), form.holderId ?: me, { id -> vm.edit { it.copy(holderId = id) } },
                    emptyText = T.CUSTODIANS_EMPTY, enabled = editable)
            }
            DecimalField(T.RETENTION_AMOUNT, form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
            TextInput(T.CURRENCY, form.currency, { v -> vm.edit { it.copy(currency = v.uppercase().take(3)) } }, editable)
        }
        Section(T.REASON) {
            val reasons = cache.retentionReasons.map { PickerOption(it.id, it.label, it.description) }
            if (reasons.isNotEmpty()) {
                SearchablePickerField(T.REASON_CATEGORY_OPTIONAL, reasons, form.reasonId, { id -> vm.edit { it.copy(reasonId = id) } },
                    noneLabel = T.NO_CATEGORY, enabled = editable)
            }
            TextInput(T.REASON, form.reason, { v -> vm.edit { it.copy(reason = v) } }, editable, singleLine = false)
        }
        val sent by vm.sent.collectAsStateWithLifecycle()
        if (sent != null) {
            Section(null) { Text(sent!!, color = palette.accent) }
            if (a.retentionOffline) TextButton(onClick = { onStatus(vm.statusKey) }) { Text(T.RETENTION_VIEW_STATUS) }
            return@FormColumn
        }
        if (!a.retentionOffline) Text(T.ONLINE_ONLY, color = palette.secondaryText)
        save.messages.forEach { Text(it, color = palette.offline) }
        FormSaveAction(
            enabled = AccountabilityRules.retention(form.amount, form.currency, form.reason) is FormCheck.Valid && editable,
            saving = save.saving, label = T.SEND, onSave = vm::send,
        )
    }
}

// --- Status of a request to keep cash ----------------------------------------------------------------------------

/** [key]: this phone's form id (outbox entity) or the server's request id (notification). Read online when possible. */
class RetentionStatusViewModel(private val field: FieldGraph, private val tenantId: String, private val key: String) : ViewModel() {
    private val _status = MutableStateFlow<com.asseta.core.sync.data.RetentionStatus?>(null)
    val status: StateFlow<com.asseta.core.sync.data.RetentionStatus?> = _status.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch { _status.value = field.accountability.retentionStatus(tenantId, key) }
    }
}

/** Pure wording of the retention status screen (unit-tested; same lines on iOS). */
object RetentionStatusText {
    /** The status line: the server's decision, else why it is not known yet. */
    fun line(s: com.asseta.core.sync.data.RetentionStatus): String {
        val server = s.server
        val op = s.operation
        return when {
            server != null -> T.retentionStatus(server.status)
            op != null && s.retentionId == null -> T.conflict(op.errorCode) ?: T.RETENTION_NOT_SYNCED
            s.offline -> T.RETENTION_OFFLINE
            else -> T.RETENTION_NOT_FOUND
        }
    }
}

@Composable
fun RetentionStatusScreen(vm: RetentionStatusViewModel) {
    val status by vm.status.collectAsStateWithLifecycle()
    val s = status ?: return
    val server = s.server
    val payload = s.operation?.payloadJson?.let { raw ->
        runCatching { kotlinx.serialization.json.Json.parseToJsonElement(raw) as kotlinx.serialization.json.JsonObject }.getOrNull()
    }
    fun text(key: String) = (payload?.get(key) as? kotlinx.serialization.json.JsonPrimitive)?.content
    FormColumn {
        if (server == null && s.operation == null && !s.offline) {
            EmptyState(T.TITLE_RETENTION_STATUS, T.RETENTION_NOT_FOUND)
            return@FormColumn
        }
        Section(null) {
            val amount = server?.amount ?: text("amount")
            val currency = server?.currency ?: text("currency")
            if (amount != null) LabeledRow(T.AMOUNT, "$amount ${currency.orEmpty()}".trim())
            (server?.reason ?: text("reason"))?.let { LabeledRow(T.REASON, it) }
            server?.createdAt?.let { LabeledRow(T.RETENTION_REQUESTED, LocalTime.formatIso(it)) }
                ?: s.operation?.let { LabeledRow(T.RETENTION_REQUESTED, LocalTime.format(it.createdAtDevice)) }
            LabeledRow(T.RETENTION_STATUS, RetentionStatusText.line(s))
            server?.let { r ->
                com.asseta.core.domain.accountability.DisplayNames.of(r.decidedByName, r.decidedBy)?.let { LabeledRow(T.RETENTION_DECIDED_BY, it) }
                r.decisionNote?.takeIf { it.isNotBlank() }?.let { LabeledRow(T.RETENTION_DECISION_NOTE, it) }
            }
        }
        if (server == null && s.retentionId != null) OutlinedButton(onClick = vm::refresh) { Text("Retry") }
    }
}
