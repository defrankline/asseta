package com.asseta.supervisor.ui.home

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.AccountabilityMessages
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.sync.data.MachineReportView
import com.asseta.core.sync.usecase.InvoicePaymentRequest
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.core.ui.session.PasswordChangeText
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.ChoiceChip
import com.asseta.core.ui.shell.PrimaryAction
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.push.NotificationPermission
import com.asseta.supervisor.push.PhonePushStatus
import com.asseta.supervisor.push.PushTexts
import com.asseta.supervisor.push.SupervisorPush
import com.asseta.supervisor.ui.DateTimeField
import com.asseta.supervisor.ui.accountability.EvidencePhotos
import com.asseta.supervisor.ui.accountability.FieldAccountabilityTexts
import com.asseta.supervisor.ui.finance.DecimalField
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.SearchablePickerField
import com.asseta.supervisor.ui.finance.TextInput
import com.asseta.supervisor.ui.finance.after
import com.asseta.supervisor.ui.rememberOnline
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.util.UUID

data class InvoicePaymentForm(
    val invoiceId: String? = null,
    val amount: String = "",
    val method: PaymentMethod = PaymentMethod.CASH,
    val reference: String = "",
    val atMs: Long = 0,
    val photos: List<CapturedPhoto> = emptyList(),
)

/** A payment on a customer's open credit invoice, queued offline (CREDIT_INVOICE_PAYMENT, client id = operation id). */
class InvoicePaymentViewModel(private val field: FieldGraph, private val tenantId: String, private val permissions: Set<String>, invoiceId: String?) : ViewModel() {
    private val clientId = UUID.randomUUID().toString()
    val form = MutableStateFlow(InvoicePaymentForm(invoiceId = invoiceId, atMs = field.clock.nowMs()))
    private val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()
    private val _access = MutableStateFlow<FieldAccess?>(null)
    val access: StateFlow<FieldAccess?> = _access.asStateFlow()
    val view: StateFlow<MachineReportView> = field.machineReports.observe(tenantId).stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), MachineReportView())

    init {
        viewModelScope.launch { _access.value = field.accountability.access(tenantId, permissions) }
    }

    fun edit(change: (InvoicePaymentForm) -> InvoicePaymentForm) {
        form.update(change)
        _save.update { it.copy(messages = emptyList()) }
    }

    fun onPhotoError(message: String) = _save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    fun balance(f: InvoicePaymentForm = form.value): BigDecimal? = view.value.openInvoices().firstOrNull { it.first.id == f.invoiceId }?.second

    fun save() {
        val s = _save.value
        if (s.saving || s.saved) return
        val f = form.value
        val balance = balance(f) ?: return
        _save.update { it.copy(saving = true, messages = emptyList()) }
        viewModelScope.launch {
            val result = field.reportCapture.recordInvoicePayment(
                InvoicePaymentRequest(
                    tenantId, clientId, f.invoiceId!!, balance, f.amount, f.method, f.reference,
                    f.atMs.coerceAtMost(field.clock.nowMs()), noncashAllowed = _access.value?.noncashPayments == true,
                    evidenceJpegs = f.photos.map { it.jpeg },
                ),
            )
            _save.update { it.after(result) }
        }
    }
}

@Composable
fun InvoicePaymentScreen(vm: InvoicePaymentViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val view by vm.view.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    LaunchedEffect(save.saved) { if (save.saved) onDone() }
    val editable = !save.saving && !save.saved
    val open = view.openInvoices()
    val methods = listOf(PaymentMethod.CASH) + if (access?.noncashPayments == true) listOf(PaymentMethod.BANK, PaymentMethod.MOBILE_MONEY) else emptyList()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ShellCard {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                SearchablePickerField(
                    HomeTexts.INVOICE,
                    open.map { (inv, bal) -> PickerOption(inv.id, HomeTexts.invoiceOption(inv.invoiceNumber, inv.customerName), HomeTexts.invoiceOwes(ShellModel.grouped(bal), inv.dueDate)) },
                    form.invoiceId, { id -> vm.edit { it.copy(invoiceId = id) } }, emptyText = HomeTexts.NO_INVOICES, enabled = editable,
                )
                if (methods.size > 1) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        methods.forEach { m -> ChoiceChip(FieldAccountabilityTexts.methodChip(m), form.method == m, editable, Modifier.weight(1f)) { vm.edit { it.copy(method = m) } } }
                    }
                }
                DecimalField(HomeTexts.AMOUNT_RECEIVED, form.amount, { v -> vm.edit { it.copy(amount = v) } }, editable)
                if (form.method.needsReference) {
                    TextInput(FieldAccountabilityTexts.REFERENCE, form.reference, { v -> vm.edit { it.copy(reference = v) } }, editable,
                        error = AccountabilityMessages.REFERENCE_LINE.takeIf { form.reference.isBlank() })
                    EvidencePhotos(form.photos, { p -> vm.edit { it.copy(photos = it.photos + p) } }, { i -> vm.edit { it.copy(photos = it.photos.filterIndexed { j, _ -> j != i }) } },
                        vm::onPhotoError, editable, title = FieldAccountabilityTexts.LINE_PHOTO, inline = true)
                }
                DateTimeField(FieldAccountabilityTexts.RECEIVED, form.atMs, { v -> vm.edit { it.copy(atMs = v) } }, editable, notAfter = System.currentTimeMillis())
            }
        }
        Column(Modifier.padding(horizontal = 20.dp)) { save.messages.forEach { Text(it, color = palette.offline) } }
        val amount = form.amount.replace(',', '.').toBigDecimalOrNull()
        val ok = form.invoiceId != null && amount != null && amount.signum() > 0 && (vm.balance(form)?.let { amount <= it } == true) &&
            (!form.method.needsReference || form.reference.isNotBlank())
        PrimaryAction(HomeTexts.SAVE_PAYMENT, enabled = ok && editable, onClick = vm::save)
        Text(HomeTexts.INVOICE_PAYMENT_FOOTER, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText, modifier = Modifier.padding(horizontal = 20.dp))
    }
}

/**
 * Settings (the side menu's footer): notifications on this phone, change password, delete my account (online only) and
 * sign out — what the account menu offered before.
 */
@Composable
fun SupervisorSettingsScreen(push: SupervisorPush, canReadNotifications: Boolean) {
    val actions = LocalSessionActions.current
    val online = rememberOnline()
    val coroutines = rememberCoroutineScope()
    val registered by push.registered.collectAsStateWithLifecycle()
    var checks by remember { mutableIntStateOf(0) }
    val pushStatus = remember(registered, checks) { push.status() }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        push.asked = true
        coroutines.launch { push.register(); checks++ }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (canReadNotifications) {
            ShellCard(padding = false) {
                val canTurnOn = pushStatus == PhonePushStatus.NOT_REGISTERED
                CardRow(PushTexts.ROW, pushStatus.label, last = true, onClick = if (canTurnOn) ({
                    if (Build.VERSION.SDK_INT >= 33 && push.permission() == NotificationPermission.NOT_ASKED) permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    else coroutines.launch { push.register(); checks++ }
                }) else null) { if (canTurnOn) Text(PushTexts.TURN_ON, color = palette.accent) }
            }
        }
        ShellCard(padding = false) {
            CardRow(PasswordChangeText.ACTION, if (online) PasswordChangeText.FOOTER else PasswordChangeText.OFFLINE, last = false,
                onClick = if (online && !actions.changingPassword) actions.changePassword else null)
            CardRow(com.asseta.core.ui.session.AccountDeletionText.ACTION, if (online) null else com.asseta.core.ui.session.AccountDeletionText.OFFLINE, last = false,
                onClick = if (online) actions.deleteAccount else null)
            CardRow(MenuFooter.SIGN_OUT.label, last = true, onClick = actions.signOut)
        }
    }
}
