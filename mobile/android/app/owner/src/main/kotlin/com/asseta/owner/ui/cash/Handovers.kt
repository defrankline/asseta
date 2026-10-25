package com.asseta.owner.ui.cash

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
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.HandoverList
import com.asseta.owner.data.Load
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EmptyState
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
import com.asseta.core.ui.R as CoreR

/**
 * Cash handover wording and rules shared with iOS: a supervisor's CLAIMED handover is confirmed as received
 * (verified = true, optional note) or disputed (verified = false, reason required). The recorder cannot decide it.
 */
object HandoverText {
    const val SECTION = "Cash handovers"
    const val CLAIMED = "CLAIMED"
    const val EMPTY = "No cash handovers waiting."
    const val SUPERVISOR_FALLBACK = "A supervisor"
    const val CONFIRM = "Confirm received"
    const val DISPUTE = "Dispute"
    const val CANCEL = "Cancel"
    const val CONFIRM_TITLE = "Confirm this handover?"
    const val DISPUTE_TITLE = "Dispute this handover?"
    const val NOTE = "Note"
    const val REASON = "Reason"
    const val CONFIRMED = "Handover confirmed."
    const val DISPUTED = "Handover disputed."
    const val CARD = "Handover"
    const val DECISION = "Decision"
    const val NOT_FOUND = "Handover not found"

    /** "Juma Katavi handed over TZS 50,000.00". */
    fun headline(h: CashHandoverDto, name: String?): String =
        "${name?.takeIf { it.isNotBlank() } ?: SUPERVISOR_FALLBACK} handed over ${OwnerFormat.money(h.amount.value, h.currency)}"

    /** "Claimed 24 Oct 2026, 08:00" (when the cash was handed over). */
    fun claimed(h: CashHandoverDto, zone: ZoneId): String = "Claimed ${OwnerFormat.dateTime(h.handedAt, zone)}"

    /** A dispute must say why; confirming takes an optional note and the amount actually received (0 or more). */
    fun canDecide(confirm: Boolean, note: String, amountReceived: String? = null): Boolean =
        if (confirm) amountReceived == null || receivedAmount(amountReceived) != null else note.isNotBlank()

    /** The counted amount as an exact decimal string (",", spaces tolerated), or null when it is not a number >= 0. */
    fun receivedAmount(text: String): String? {
        val t = text.trim().replace(',', '.')
        if (!Regex("^\\d+(\\.\\d+)?$").matches(t)) return null
        return java.math.BigDecimal(t).toPlainString()
    }

    fun done(confirm: Boolean): String = if (confirm) CONFIRMED else DISPUTED

    fun statusTone(status: String): KpiTone = when (status) {
        "CLAIMED" -> KpiTone.WARNING
        "VERIFIED" -> KpiTone.GOOD
        "REJECTED" -> KpiTone.CRITICAL
        else -> KpiTone.MUTED
    }
}

/** A handover row (Approvals "Cash handovers" section and the Cash screen cards). */
@Composable
fun HandoverRow(h: CashHandoverDto, name: String?, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(HandoverText.headline(h, name), style = AssetaType.headline)
        Text(HandoverText.claimed(h, zone), style = AssetaType.subheadline, color = palette.secondaryText)
        h.note?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}

/**
 * One handover (there is no single-handover endpoint): found among the claimed ones (shared snapshot with the
 * Approvals section) or, once decided, in the full list; confirm received / dispute.
 */
class HandoverViewModel(val data: OwnerData, val handoverId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<HandoverList>({
        val claimed = data.handovers(HandoverText.CLAIMED)
        fun Load<HandoverList>.has() = this is Load.Ok && snapshot.data.items.any { it.id.toString() == handoverId }
        if (claimed.has()) {
            claimed
        } else {
            val all = data.handovers(null)
            // A notification may name a remittance in neither list (older, or another status): read it by id.
            if (all.has()) all else data.handover(handoverId).let { one -> if (one is Load.Ok) one else if (all is Load.Ok) all else claimed }
        }
    }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun handover(list: HandoverList): CashHandoverDto? = list.items.firstOrNull { it.id.toString() == handoverId }

    fun decide(confirm: Boolean, note: String, amountReceived: String? = null) {
        if (_busy.value || !HandoverText.canDecide(confirm, note, amountReceived)) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decideHandover(handoverId, confirm, note, amountReceived?.let(HandoverText::receivedAmount))) {
                is ActionResult.Done -> {
                    replaceData { list -> list.copy(items = list.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = HandoverText.done(confirm)
                }
                is ActionResult.Refused -> {
                    _error.value = r.error.message
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun HandoverScreen(vm: HandoverViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var confirming by rememberSaveable { mutableStateOf(false) }
    var disputing by rememberSaveable { mutableStateOf(false) }
    var note by rememberSaveable { mutableStateOf("") }
    var received by rememberSaveable { mutableStateOf("") }
    SnapshotScaffold(state, vm::refresh) { list ->
        val h = vm.handover(list)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            if (h == null) {
                item { EmptyState(HandoverText.NOT_FOUND, icon = CoreR.drawable.ic_help) }
                return@LazyColumn
            }
            item {
                SectionCard(HandoverText.CARD) {
                    Text(HandoverText.headline(h, list.name(h)), style = AssetaType.headline)
                    Text(HandoverText.claimed(h, zone), style = AssetaType.subheadline, color = palette.secondaryText)
                    h.reference?.let { KeyValue("Reference", it) }
                    h.note?.takeIf { it.isNotBlank() }?.let { KeyValue(HandoverText.NOTE, it) }
                    LabeledValue("Status") { StatusPill(OwnerFormat.humanize(h.status), OwnerColors.tone(HandoverText.statusTone(h.status))) }
                    h.expectedBalance?.let { KeyValue(OwnerAccountabilityTexts.REMIT_EXPECTED, OwnerFormat.money(it.value, h.currency)) }
                    h.partialShortfall?.let { KeyValue(OwnerAccountabilityTexts.REMIT_SHORTFALL, OwnerFormat.money(it.value, h.currency)) }
                    h.amountReceived?.let { KeyValue(OwnerAccountabilityTexts.REMIT_RECEIVED, OwnerFormat.money(it.value, h.currency)) }
                    h.decisionNote?.let { KeyValue("Decision note", it) }
                }
            }
            if (h.status == HandoverText.CLAIMED) item {
                SectionCard(HandoverText.DECISION) {
                    val gate = session.can(OwnerAction.DECIDE_HANDOVER, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        BlockedNote(gate.reason)
                    } else {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                { note = ""; received = OwnerFormat.decimal(h.amount.value); confirming = true }, enabled = !busy,
                                modifier = Modifier.testTag("confirm-handover-${h.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(HandoverText.CONFIRM) }
                            Spacer(Modifier.weight(1f))
                            Button(
                                { note = ""; disputing = true }, enabled = !busy, modifier = Modifier.testTag("dispute-handover-${h.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(HandoverText.DISPUTE) }
                        }
                        error?.let {
                            Text(
                                it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("handover-error").semantics { liveRegion = LiveRegionMode.Assertive },
                            )
                        }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    if (confirming || disputing) {
        val confirm = confirming
        val close = { confirming = false; disputing = false }
        AlertDialog(
            onDismissRequest = close,
            title = { Text(if (confirm) HandoverText.CONFIRM_TITLE else HandoverText.DISPUTE_TITLE) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (confirm) {
                        // The office records what it actually counted; a different amount opens a cash difference.
                        OutlinedTextField(
                            received, { v -> received = v.filter { it.isDigit() || it == '.' || it == ',' }.take(24) },
                            Modifier.fillMaxWidth().testTag("handover-received"), singleLine = true,
                            label = { Text(OwnerAccountabilityTexts.REMIT_AMOUNT_RECEIVED) },
                            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Decimal),
                            isError = HandoverText.receivedAmount(received) == null,
                            supportingText = {
                                Text(if (HandoverText.receivedAmount(received) == null) OwnerAccountabilityTexts.REMIT_ERR_AMOUNT else OwnerAccountabilityTexts.REMIT_AMOUNT_FOOTER)
                            },
                        )
                    }
                    OutlinedTextField(
                        note, { note = it.take(1000) }, Modifier.fillMaxWidth().testTag("handover-note"),
                        label = { Text(if (confirm) HandoverText.NOTE else HandoverText.REASON) }, minLines = 2,
                    )
                }
            },
            confirmButton = {
                val amount = received.takeIf { confirm }
                TextButton({ close(); vm.decide(confirm, note, amount) }, enabled = HandoverText.canDecide(confirm, note, amount)) {
                    if (confirm) Text(HandoverText.CONFIRM) else Text(HandoverText.DISPUTE, color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(close) { Text(HandoverText.CANCEL) } },
        )
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}
