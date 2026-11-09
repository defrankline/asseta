package com.asseta.owner.ui.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.CustomerPaymentDto
import com.asseta.core.model.owner.PaymentReview
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.home.KpiTone
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

/** Wording and rules of "Payments to confirm", shared with iOS (strings doc "Go-live fixes — payments to confirm"). */
object PaymentReviewText {
    const val SECTION = "Payments to confirm"
    const val EMPTY = "No customer payments waiting."
    const val SCREEN_TITLE = "Customer payment"
    const val CARD = "Payment"
    const val CUSTOMER_FALLBACK = "A customer"
    const val CLAIMED = "CLAIMED"
    const val VERIFIED = "VERIFIED"
    const val F_CUSTOMER = "Customer"
    const val F_AMOUNT = "Amount"
    const val F_METHOD = "Method"
    const val F_REFERENCE = "Reference"
    const val F_COLLECTION = "Collection number"
    const val F_RECEIVED_AT = "Received"
    const val F_RECEIVED_BY = "Received by"
    const val F_RECORDED_BY = "Recorded by"
    const val F_RECORDED_AT = "Recorded"
    const val F_NOTE = "Note"
    const val F_STATUS = "Status"
    const val F_DECIDED_BY = "Decided by"
    const val F_DECISION_NOTE = "Decision note"
    const val F_REVERSED = "Reversed"
    const val LINKS_PURCHASES = "Hours purchases"
    const val LINKS_INVOICES = "Invoices"
    const val EVIDENCE = "Evidence"
    const val EVIDENCE_NONE = "No evidence photos attached."
    const val EVIDENCE_FAILED = "Evidence photos could not be loaded. Pull to try again."
    const val DECISION = "Decision"
    const val EXPLANATION = "Confirm only when the money has been received (bank statement, mobile money record or cash counted). " +
        "Confirmed money reduces what the customer owes. Rejecting releases what it was linked to."
    const val CONFIRM = "Confirm"
    const val REJECT = "Reject"
    const val CANCEL = "Cancel"
    const val CONFIRM_TITLE = "Confirm this payment?"
    const val REJECT_TITLE = "Reject this payment?"
    const val NOTE_OPTIONAL = "Note (optional)"
    const val REASON_REQUIRED = "Reason (required)"
    const val ERR_REASON_SHORT = "Write at least 3 characters."
    const val CONFIRMED = "Payment confirmed."
    const val REJECTED = "Payment rejected."
    const val OWN = OwnerErrors.PAYMENT_SEGREGATION
    const val NOTE_MIN = 3
    const val NOTE_MAX = 1000

    fun headline(p: CustomerPaymentDto): String =
        "${p.customerName?.trim()?.takeIf { it.isNotEmpty() } ?: CUSTOMER_FALLBACK} paid ${OwnerFormat.money(p.amount.value, p.currency)}"

    fun received(p: CustomerPaymentDto, zone: ZoneId): String = "Received ${OwnerFormat.dateTime(p.receivedAt, zone)}"

    fun recordedBy(p: CustomerPaymentDto): String? = DisplayNames.of(p.recordedByName, p.recordedBy)?.let { "Recorded by $it" }

    fun method(raw: String): String = when (raw) {
        "CASH" -> "Cash"
        "BANK" -> "Bank transfer"
        "MOBILE_MONEY" -> "Mobile money"
        else -> OwnerFormat.humanize(raw)
    }

    fun status(raw: String): String = when (raw) {
        CLAIMED -> "Waiting to be confirmed"
        VERIFIED -> "Confirmed"
        "REJECTED" -> "Rejected"
        else -> OwnerFormat.humanize(raw)
    }

    fun statusTone(status: String): KpiTone = when (status) {
        CLAIMED -> KpiTone.WARNING
        VERIFIED -> KpiTone.GOOD
        "REJECTED" -> KpiTone.CRITICAL
        else -> KpiTone.MUTED
    }

    /** The second line of a row: method and the collection number, else the payer's reference. */
    fun summary(p: CustomerPaymentDto): String = listOfNotNull(method(p.method), number(p)).joinToString(" · ")

    private fun number(p: CustomerPaymentDto): String? = p.collectionNumber?.takeIf { it.isNotBlank() } ?: p.reference?.takeIf { it.isNotBlank() }

    /** The payment's facts in screen order; empty values left out. */
    fun fields(p: CustomerPaymentDto, zone: ZoneId): List<Pair<String, String>> = listOfNotNull(
        DisplayNames.of(p.customerName, p.customerId.toString())?.let { F_CUSTOMER to it },
        F_AMOUNT to OwnerFormat.money(p.amount.value, p.currency),
        F_METHOD to method(p.method),
        p.reference?.takeIf { it.isNotBlank() }?.let { F_REFERENCE to it },
        p.collectionNumber?.takeIf { it.isNotBlank() }?.let { F_COLLECTION to it },
        F_RECEIVED_AT to OwnerFormat.dateTime(p.receivedAt, zone),
        DisplayNames.of(p.receivedByStaffName, p.receivedByStaffId)?.let { F_RECEIVED_BY to it },
        DisplayNames.of(p.recordedByName, p.recordedBy)?.let { F_RECORDED_BY to it },
        F_RECORDED_AT to OwnerFormat.dateTime(p.recordedAt, zone),
        p.note?.takeIf { it.isNotBlank() }?.let { F_NOTE to it },
    )

    /** Who decided it and why, once decided. */
    fun decisionFields(p: CustomerPaymentDto, zone: ZoneId): List<Pair<String, String>> = listOfNotNull(
        DisplayNames.of(p.verifiedByName, p.verifiedBy)?.let { F_DECIDED_BY to it },
        p.decisionNote?.takeIf { it.isNotBlank() }?.let { F_DECISION_NOTE to it },
        p.reversedAt?.let { F_REVERSED to OwnerFormat.dateTime(it, zone) },
    )

    /** "PUR-12 · TZS 50,000.00". */
    fun link(number: String, money: String): String = "$number · $money"

    /** "Number · amount" of each invoice the payment is set against (the short id until a number is known); released ones left out. */
    fun invoices(r: PaymentReview): List<String> = r.payment.allocations.filter { it.releasedAt == null }.map { a ->
        val id = a.invoiceId.toString()
        link(r.invoiceNumbers[id] ?: DisplayNames.shortId(id).orEmpty(), OwnerFormat.money(a.amount.value, r.payment.currency))
    }

    fun photo(n: Int): String = "photo $n"

    /** A rejection must say why; confirming takes an optional note. */
    fun canDecide(confirm: Boolean, note: String): Boolean {
        val length = note.trim().length
        return length <= NOTE_MAX && (confirm || length >= NOTE_MIN)
    }

    /** The recorder can never decide their own payment (segregation of duties; the server refuses it too). */
    fun isOwn(p: CustomerPaymentDto, userId: String?): Boolean = userId != null && p.recordedBy.equals(userId, ignoreCase = true)

    /** The decision section is offered only while the payment waits and was not reversed. */
    fun decidable(p: CustomerPaymentDto): Boolean = p.status == CLAIMED && p.reversedAt == null

    fun canOpenPurchase(features: OwnerFeatures): Boolean = features.customerHours

    fun done(confirm: Boolean): String = if (confirm) CONFIRMED else REJECTED
}

/** A row of the Approvals "Payments to confirm" section. */
@Composable
fun PaymentRow(p: CustomerPaymentDto, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(PaymentReviewText.headline(p), style = AssetaType.headline)
        Text(PaymentReviewText.summary(p), style = AssetaType.subheadline, color = palette.secondaryText)
        Text(PaymentReviewText.received(p, zone), style = AssetaType.caption, color = palette.secondaryText)
        PaymentReviewText.recordedBy(p)?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}

/** One customer payment, read by id: confirm or reject while it waits. */
class PaymentReviewViewModel(val data: OwnerData, val paymentId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PaymentReview>({ data.paymentReview(paymentId) }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun decide(confirm: Boolean, note: String) {
        if (_busy.value || !PaymentReviewText.canDecide(confirm, note)) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decidePayment(paymentId, confirm, note)) {
                is ActionResult.Done -> {
                    replaceData { it.copy(payment = r.value) }
                    _message.value = PaymentReviewText.done(confirm)
                }
                is ActionResult.Refused -> {
                    _error.value = OwnerErrors.paymentMessage(r.code, r.error.message)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun PaymentReviewScreen(vm: PaymentReviewViewModel, session: OwnerSession, online: Boolean, onOpen: (OwnerDestination) -> Unit = {}) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var confirming by rememberSaveable { mutableStateOf(false) }
    var rejecting by rememberSaveable { mutableStateOf(false) }
    var note by rememberSaveable { mutableStateOf("") }
    val zone = ZoneId.systemDefault()
    SnapshotScaffold(state, vm::refresh) { review ->
        val p = review.payment
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(PaymentReviewText.CARD) {
                    Text(PaymentReviewText.headline(p), style = AssetaType.headline)
                    PaymentReviewText.fields(p, zone).forEach { (label, value) -> KeyValue(label, value) }
                    LabeledValue(PaymentReviewText.F_STATUS) { StatusPill(PaymentReviewText.status(p.status), OwnerColors.tone(PaymentReviewText.statusTone(p.status))) }
                    PaymentReviewText.decisionFields(p, zone).forEach { (label, value) -> KeyValue(label, value) }
                }
            }
            p.purchaseLinks?.takeIf { it.isNotEmpty() }?.let { links ->
                item {
                    SectionCard(PaymentReviewText.LINKS_PURCHASES) {
                        links.forEach { l ->
                            val text = PaymentReviewText.link(l.purchaseNumber, OwnerFormat.money(l.amount.value, p.currency))
                            if (PaymentReviewText.canOpenPurchase(session.features)) {
                                NavigationRow(text) { onOpen(OwnerDestination.HoursPurchase(l.purchaseId.toString())) }
                            } else {
                                Text(text, style = MaterialTheme.typography.bodyLarge)
                            }
                        }
                    }
                }
            }
            PaymentReviewText.invoices(review).takeIf { it.isNotEmpty() }?.let { invoices ->
                item {
                    SectionCard(PaymentReviewText.LINKS_INVOICES) {
                        invoices.forEach { Text(it, style = MaterialTheme.typography.bodyLarge) }
                    }
                }
            }
            item {
                SectionCard(PaymentReviewText.EVIDENCE) {
                    when {
                        review.evidenceFailed -> FootNote(PaymentReviewText.EVIDENCE_FAILED)
                        review.evidenceIds.isEmpty() -> FootNote(PaymentReviewText.EVIDENCE_NONE)
                        else -> review.evidenceIds.forEachIndexed { i, attachmentId ->
                            EvidencePhoto(PaymentReviewText.photo(i + 1), online) { vm.data.paymentEvidenceUrl(p.id.toString(), attachmentId) }
                        }
                    }
                }
            }
            if (PaymentReviewText.decidable(p)) item {
                SectionCard(PaymentReviewText.DECISION, footer = PaymentReviewText.EXPLANATION) {
                    val gate = session.can(OwnerAction.DECIDE_PAYMENT, online, state.snapshot?.source)
                    when {
                        gate is MutationCheck.Blocked -> BlockedNote(gate.reason)
                        PaymentReviewText.isOwn(p, session.userId) -> BlockedNote(PaymentReviewText.OWN)
                        else -> Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                { note = ""; confirming = true }, enabled = !busy, modifier = Modifier.testTag("confirm-payment-${p.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(PaymentReviewText.CONFIRM) }
                            Spacer(Modifier.weight(1f))
                            Button(
                                { note = ""; rejecting = true }, enabled = !busy, modifier = Modifier.testTag("reject-payment-${p.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(PaymentReviewText.REJECT) }
                        }
                    }
                }
            }
            // Outside the decision card: after "someone already decided" the reloaded payment no longer shows that card.
            error?.let {
                item {
                    GroupedSection {
                        Text(
                            it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.testTag("payment-error").semantics { liveRegion = LiveRegionMode.Assertive },
                        )
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    if (confirming || rejecting) {
        val confirm = confirming
        val close = { confirming = false; rejecting = false }
        val tooShort = !confirm && note.isNotEmpty() && !PaymentReviewText.canDecide(false, note)
        AlertDialog(
            onDismissRequest = close,
            title = { Text(if (confirm) PaymentReviewText.CONFIRM_TITLE else PaymentReviewText.REJECT_TITLE) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.data?.let { Text(PaymentReviewText.headline(it.payment), style = AssetaType.subheadline) }
                    OutlinedTextField(
                        note, { note = it.take(PaymentReviewText.NOTE_MAX) }, Modifier.fillMaxWidth().testTag("payment-note"),
                        label = { Text(if (confirm) PaymentReviewText.NOTE_OPTIONAL else PaymentReviewText.REASON_REQUIRED) }, minLines = 2, isError = tooShort,
                        supportingText = if (tooShort) ({ Text(PaymentReviewText.ERR_REASON_SHORT) }) else null,
                    )
                }
            },
            confirmButton = {
                TextButton({ close(); vm.decide(confirm, note) }, enabled = PaymentReviewText.canDecide(confirm, note)) {
                    if (confirm) Text(PaymentReviewText.CONFIRM) else Text(PaymentReviewText.REJECT, color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(close) { Text(PaymentReviewText.CANCEL) } },
        )
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}
