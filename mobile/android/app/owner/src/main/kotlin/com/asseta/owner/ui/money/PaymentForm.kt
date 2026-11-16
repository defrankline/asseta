package com.asseta.owner.ui.money

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CreditInvoicePaymentIn
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.ChoiceChip
import com.asseta.core.ui.shell.PrimaryAction
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.Section
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.util.UUID

/** Record payment wording (credit invoices; same as iOS). */
object PaymentTexts {
    const val TITLE = "Record payment"
    const val INVOICE = "INVOICE"
    const val AMOUNT = "Amount"
    const val METHOD = "METHOD"
    const val REFERENCE = "Reference"
    const val REFERENCE_HINT = "Bank or mobile money transaction reference"
    const val RECEIVED = "RECEIVED"
    const val TODAY = "Today"
    const val YESTERDAY = "Yesterday"
    const val NOTE = "Note (optional)"
    const val SAVE = "Record payment"
    const val NO_OPEN = "No open credit invoices."
    const val CHOOSE_INVOICE = "Choose the invoice being paid."
    const val AMOUNT_NEEDED = "Enter the amount received (more than 0)."
    const val REFERENCE_NEEDED = "Enter the transaction reference for a bank or mobile money payment."
    const val CASH_NOTE = "Cash goes into your cash with you until you hand it over."
    const val CLAIMED_NOTE = "Bank and mobile money stay unconfirmed until the office checks them."

    fun overBalance(balance: BigDecimal) = "At most the balance, ${Figures.money(balance, "").trim()}."
    fun left(i: CreditInvoiceDto) = "${Figures.money(Figures.dec(i.balance), i.currency)} left · due ${Figures.day(i.dueDate)}"
    fun done(i: CreditInvoiceDto) = "Payment recorded. ${i.invoiceNumber}: ${Figures.money(Figures.dec(i.balance), i.currency)} left."

    /** Refusals of a credit-invoice payment in plain words. */
    fun refusal(code: String?, fallback: String): String = when (code) {
        "INVOICE_OVERPAYMENT" -> "That is more than the invoice still owes. The invoice has been refreshed."
        "INVOICE_PAID" -> "This invoice is already paid in full."
        "INVOICE_CANCELLED" -> "This invoice was cancelled with its order."
        "INVOICE_NOT_FOUND" -> "This invoice no longer exists."
        "PAYMENT_NOT_PERMITTED" -> "You may not record bank or mobile money payments here. Record cash, or ask the office."
        "STAFF_NOT_LINKED" -> "Your login is not linked to a staff record, so cash can't be put in your custody. Ask the office."
        "NOT_CUSTODIAN" -> "Only office cash staff may record cash for someone else."
        else -> fallback
    }
}

/** A payment method of a credit-invoice payment (no CREDIT: an invoice is paid with money). */
enum class PayMethod(val wire: String, val label: String, val needsReference: Boolean) {
    CASH("CASH", "Cash", false), BANK("BANK", "Bank", true), MOBILE_MONEY("MOBILE_MONEY", "Mobile money", true),
}

/** The form as typed. [key] is the visit's Idempotency-Key and the payment's `client_id`. */
data class PaymentDraft(
    val invoiceId: String? = null,
    val amount: String = "",
    val method: PayMethod = PayMethod.CASH,
    val reference: String = "",
    val yesterday: Boolean = false,
    val note: String = "",
    val key: String = UUID.randomUUID().toString(),
)

/** Pure payment rules (unit-tested; the server re-checks everything). */
object PaymentRules {
    /** Invoices that can still be paid: balance left, not cancelled or paid; overdue first, then by due date. */
    fun open(invoices: List<CreditInvoiceDto>): List<CreditInvoiceDto> =
        invoices.filter { it.status != CreditInvoiceDto.CANCELLED && it.status != CreditInvoiceDto.PAID && Figures.dec(it.balance).signum() > 0 }
            .sortedWith(compareByDescending<CreditInvoiceDto> { it.overdue }.thenBy { it.dueDate })

    /** A positive amount with at most 2 decimals ("170000", "170,000" and "170000.50" read). */
    fun amount(text: String): BigDecimal? =
        text.replace(",", "").trim().toBigDecimalOrNull()?.takeIf { it.signum() > 0 && it.stripTrailingZeros().scale() <= 2 }

    /** The first problem of the draft, or null when it can be sent. */
    fun problem(d: PaymentDraft, invoice: CreditInvoiceDto?): String? {
        if (invoice == null) return PaymentTexts.CHOOSE_INVOICE
        val amount = amount(d.amount) ?: return PaymentTexts.AMOUNT_NEEDED
        val balance = Figures.dec(invoice.balance)
        if (amount > balance) return PaymentTexts.overBalance(balance)
        if (d.method.needsReference && d.reference.isBlank()) return PaymentTexts.REFERENCE_NEEDED
        return null
    }

    /** When the money was received: now today, or noon yesterday (local time). */
    fun receivedAt(yesterday: Boolean, now: Instant, zone: ZoneId): String =
        if (!yesterday) now.toString() else LocalDate.ofInstant(now, zone).minusDays(1).atTime(LocalTime.NOON).atZone(zone).toInstant().toString()

    fun body(d: PaymentDraft, now: Instant, zone: ZoneId): CreditInvoicePaymentIn = CreditInvoicePaymentIn(
        clientId = d.key,
        amount = amount(d.amount)!!.stripTrailingZeros().toPlainString(),
        method = d.method.wire,
        reference = d.reference.trim().takeIf { d.method.needsReference && it.isNotEmpty() },
        receivedAt = receivedAt(d.yesterday, now, zone),
        note = d.note.trim().takeIf { it.isNotEmpty() },
    )
}

class PaymentViewModel(
    private val data: OwnerData,
    preselected: String?,
    private val clock: () -> Instant = { Instant.now() },
    private val zone: ZoneId = ZoneId.systemDefault(),
) : ViewModel() {
    val invoices = Section(viewModelScope) { data.creditInvoices() }
    private val _draft = MutableStateFlow(PaymentDraft(invoiceId = preselected))
    val draft: StateFlow<PaymentDraft> = _draft.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _done = MutableStateFlow<String?>(null)
    val done: StateFlow<String?> = _done.asStateFlow()

    init {
        invoices.refresh()
    }

    fun edit(change: (PaymentDraft) -> PaymentDraft) {
        _draft.update(change)
        _error.value = null
    }

    fun invoice(): CreditInvoiceDto? = invoices.state.value.data?.firstOrNull { it.id == _draft.value.invoiceId }

    /** Sends the payment once (the same key on a retry after a network failure). */
    fun submit() {
        val d = _draft.value
        if (_busy.value || PaymentRules.problem(d, invoice()) != null) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.recordInvoicePayment(d.invoiceId!!, PaymentRules.body(d, clock(), zone), d.key)) {
                is ActionResult.Done -> {
                    _done.value = PaymentTexts.done(r.value)
                    // A new form visit: a second payment gets its own key.
                    _draft.value = PaymentDraft(invoiceId = r.value.id.takeIf { Figures.dec(r.value.balance).signum() > 0 })
                    invoices.refresh()
                }
                is ActionResult.Refused -> {
                    _error.value = PaymentTexts.refusal(r.code, r.error.message)
                    if (r.code?.startsWith("INVOICE_") == true) invoices.refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun PaymentScreen(vm: PaymentViewModel, session: OwnerSession, online: Boolean) {
    val st by vm.invoices.state.collectAsStateWithLifecycle()
    val d by vm.draft.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val done by vm.done.collectAsStateWithLifecycle()
    val open = PaymentRules.open(st.data.orEmpty())
    val invoice = open.firstOrNull { it.id == d.invoiceId }
    val gate = session.can(OwnerAction.RECORD_INVOICE_PAYMENT, online, st.snapshot?.source)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
        done?.let { m -> item { Text(m, color = palette.accent, modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp).semantics { liveRegion = LiveRegionMode.Polite }) } }
        if (gate is MutationCheck.Blocked) item { Column(Modifier.padding(horizontal = 20.dp)) { BlockedNote(gate.reason) } }
        item { SectionLabel(PaymentTexts.INVOICE) }
        item {
            when {
                st.data == null && st.loading -> Unit
                st.data == null -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(st.error?.message.orEmpty()) }
                open.isEmpty() -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(PaymentTexts.NO_OPEN) }
                else -> ShellCard(padding = false) {
                    open.forEachIndexed { i, inv ->
                        CardRow(
                            MoneyPresentation.invoiceTitle(inv), PaymentTexts.left(inv), last = i == open.lastIndex,
                            onClick = { vm.edit { it.copy(invoiceId = inv.id) } },
                            trailing = { if (inv.id == d.invoiceId) StatusPill("✓", com.asseta.core.ui.shell.PillTone.ACCENT) else MoneyPresentation.pill(inv).let { (l, t) -> StatusPill(l, t) } },
                        )
                    }
                }
            }
        }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    d.amount, { v -> vm.edit { it.copy(amount = v.take(20)) } }, Modifier.fillMaxWidth().testTag("payment-amount"),
                    label = { Text(PaymentTexts.AMOUNT + (invoice?.currency?.let { " ($it)" } ?: "")) }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                )
            }
        }
        item { SectionLabel(PaymentTexts.METHOD) }
        item {
            Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PayMethod.entries.forEach { m -> ChoiceChip(m.label, d.method == m, modifier = Modifier.weight(1f)) { vm.edit { it.copy(method = m) } } }
            }
        }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (d.method.needsReference) {
                    OutlinedTextField(
                        d.reference, { v -> vm.edit { it.copy(reference = v.take(120)) } }, Modifier.fillMaxWidth().testTag("payment-reference"),
                        label = { Text(PaymentTexts.REFERENCE) }, placeholder = { Text(PaymentTexts.REFERENCE_HINT) }, singleLine = true,
                    )
                }
                FootNote(if (d.method.needsReference) PaymentTexts.CLAIMED_NOTE else PaymentTexts.CASH_NOTE)
            }
        }
        item { SectionLabel(PaymentTexts.RECEIVED) }
        item {
            Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ChoiceChip(PaymentTexts.TODAY, !d.yesterday, modifier = Modifier.weight(1f)) { vm.edit { it.copy(yesterday = false) } }
                ChoiceChip(PaymentTexts.YESTERDAY, d.yesterday, modifier = Modifier.weight(1f)) { vm.edit { it.copy(yesterday = true) } }
            }
        }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) {
                OutlinedTextField(d.note, { v -> vm.edit { it.copy(note = v.take(1000)) } }, Modifier.fillMaxWidth(), label = { Text(PaymentTexts.NOTE) }, minLines = 2)
            }
        }
        item {
            val problem = PaymentRules.problem(d, invoice)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                (error ?: problem.takeIf { d.amount.isNotBlank() || d.reference.isNotBlank() })?.let {
                    Text(
                        it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(horizontal = 20.dp).semantics { liveRegion = LiveRegionMode.Assertive },
                    )
                }
                PrimaryAction(PaymentTexts.SAVE, enabled = !busy && problem == null && gate is MutationCheck.Allowed, modifier = Modifier.testTag("payment-save")) { vm.submit() }
            }
        }
    }
}
