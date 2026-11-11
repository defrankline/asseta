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
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.PettyCashAdjustmentReviewDto
import com.asseta.core.model.owner.PettyCashMovementReview
import com.asseta.core.model.owner.PettyCashMovementReviewDto
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.map
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
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
import kotlinx.serialization.Serializable
import java.math.BigDecimal
import java.time.ZoneId

/** Petty cash requests waiting for approval (DEC-033): fundings / top-ups and fund adjustments. */
@Serializable
data class PettyCashQueue(
    val movements: List<PettyCashMovementReviewDto> = emptyList(),
    val adjustments: List<PettyCashAdjustmentReviewDto> = emptyList(),
) {
    fun isEmpty() = movements.isEmpty() && adjustments.isEmpty()
    fun isNotEmpty() = !isEmpty()
}

/** No queue loaded, or nothing in it. */
fun PettyCashQueue?.isNullOrEmptyQueue(): Boolean = this == null || isEmpty()

/** One petty cash request under review: a funding / top-up or a fund adjustment, in one shape for the screen. */
@Serializable
data class PettyCashRequest(
    val id: String,
    val isAdjustment: Boolean,
    val kind: String,
    val number: String,
    val fund: String?,
    val holder: String?,
    val amount: String,
    val currency: String,
    val status: String,
    val suggested: String? = null,
    val cap: String? = null,
    val aboveCapReason: String? = null,
    val reason: String? = null,
    val note: String? = null,
    val createdBy: String?,
    val createdByName: String?,
    val createdAt: String,
    val decidedBy: String?,
    val decidedByName: String?,
    val decisionNote: String?,
    val expenses: List<String> = emptyList(),
    val expensesFailed: Boolean = false,
) {
    companion object {
        fun of(r: PettyCashMovementReview): PettyCashRequest = with(r.movement) {
            PettyCashRequest(
                id.toString(), false, kind, number, fundName, DisplayNames.of(holderStaffName, holderStaffId.toString()), amount.value.toPlainString(), currency, status,
                suggestedAmount?.value?.toPlainString(), capAmount?.value?.toPlainString(), aboveCapReason, null, note, createdBy, createdByName, createdAt,
                decidedBy, decidedByName, decisionNote,
                r.expenses.map { PettyCashReviewText.expenseLine(it.description, OwnerFormat.money(it.amount.value, currency)) }, r.expensesFailed,
            )
        }

        fun of(a: PettyCashAdjustmentReviewDto): PettyCashRequest = PettyCashRequest(
            a.id.toString(), true, PettyCashReviewText.ADJUSTMENT, a.number, a.fundName, null, a.amount.value.toPlainString(), a.currency, a.status,
            reason = a.reason, createdBy = a.createdBy, createdByName = a.createdByName, createdAt = a.createdAt,
            decidedBy = a.decidedBy, decidedByName = a.decidedByName, decisionNote = a.decisionNote,
        )
    }
}

/** Wording and rules of "Petty cash to approve", shared with iOS (strings doc "DEC-033 — petty cash funds"). */
object PettyCashReviewText {
    const val SECTION = "Petty cash to approve"
    const val EMPTY = "No petty cash requests waiting."
    const val ADJUSTMENT = "ADJUSTMENT"
    const val TITLE_MOVEMENT = "Petty cash request"
    const val TITLE_ADJUSTMENT = "Fund adjustment"
    const val FUND_FALLBACK = "A fund"
    const val CARD = "Request"
    const val F_FUND = "Fund"
    const val F_HOLDER = "Holder"
    const val F_KIND = "Kind"
    const val F_NUMBER = "Number"
    const val F_AMOUNT = "Amount"
    const val F_SUGGESTED = "Suggested"
    const val F_CAP = "Brings the fund to its limit"
    const val F_ABOVE_CAP_REASON = "Reason for going above the limit"
    const val F_REASON = "Reason"
    const val F_NOTE = "Note"
    const val F_PROPOSED_BY = "Proposed by"
    const val F_PROPOSED_AT = "Proposed"
    const val F_STATUS = "Status"
    const val F_DECIDED_BY = "Decided by"
    const val F_DECISION_NOTE = "Decision note"
    const val EXPENSES = "Spending behind this top-up"
    const val EXPENSES_NONE = "No expenses listed."
    const val EXPENSES_FAILED = "The expenses could not be loaded. Pull to try again."
    const val DECISION = "Decision"
    const val EXPLANATION_MOVEMENT = "Approving lets the office hand the money over. It counts in the fund only after the holder acknowledges it."
    const val EXPLANATION_ADJUSTMENT = "Approving changes the fund balance by this amount."
    const val APPROVE = "Approve"
    const val REJECT = "Reject"
    const val CANCEL = "Cancel"
    const val APPROVE_TITLE = "Approve this request?"
    const val REJECT_TITLE = "Reject this request?"
    const val NOTE_OPTIONAL = "Note (optional)"
    const val REASON_REQUIRED = "Reason (required)"
    const val ERR_REASON_SHORT = "Write at least 3 characters."
    const val APPROVED = "Request approved."
    const val REJECTED = "Request rejected."
    const val OWN = "You proposed this, so someone else must approve or reject it."
    const val ALREADY_DECIDED = "Someone already decided this. Reload to see it."
    const val NOTE_MIN = 3
    const val NOTE_MAX = 1000

    fun kind(raw: String): String = when (raw) {
        "FUNDING" -> "Funding"
        "TOP_UP" -> "Top-up"
        ADJUSTMENT -> "Fund adjustment"
        else -> OwnerFormat.humanize(raw)
    }

    fun status(raw: String): String = when (raw) {
        "PROPOSED", "PENDING" -> "Waiting for approval"
        "APPROVED" -> "Approved"
        "REJECTED" -> "Rejected"
        else -> OwnerFormat.humanize(raw)
    }

    fun statusTone(raw: String): KpiTone = when (raw) {
        "PROPOSED", "PENDING" -> KpiTone.WARNING
        "APPROVED" -> KpiTone.GOOD
        "REJECTED" -> KpiTone.CRITICAL
        else -> KpiTone.MUTED
    }

    /** An adjustment is signed: "+TZS 5,000.00" raises the fund, "-TZS 5,000.00" lowers it. */
    fun amount(r: PettyCashRequest): String {
        val v = r.amount.toBigDecimalOrNull() ?: BigDecimal.ZERO
        val text = OwnerFormat.money(v.abs(), r.currency)
        return if (r.isAdjustment) (if (v.signum() < 0) "-" else "+") + text else text
    }

    /** "Top-up TZS 50,000.00 · Site A box". */
    fun headline(r: PettyCashRequest): String = "${kind(r.kind)} ${amount(r)} · ${r.fund?.trim()?.takeIf { it.isNotEmpty() } ?: FUND_FALLBACK}"

    fun proposedBy(r: PettyCashRequest): String? = DisplayNames.of(r.createdByName, r.createdBy)?.let { "Proposed by $it" }

    fun expenseLine(description: String, amount: String) = "$description · $amount"

    /** The request's facts in screen order; empty values left out. */
    fun fields(r: PettyCashRequest, zone: ZoneId): List<Pair<String, String>> = listOfNotNull(
        F_FUND to (r.fund?.takeIf { it.isNotBlank() } ?: FUND_FALLBACK),
        r.holder?.let { F_HOLDER to it },
        F_KIND to kind(r.kind),
        F_NUMBER to r.number,
        F_AMOUNT to amount(r),
        r.suggested?.toBigDecimalOrNull()?.let { F_SUGGESTED to OwnerFormat.money(it, r.currency) },
        r.cap?.toBigDecimalOrNull()?.let { F_CAP to OwnerFormat.money(it, r.currency) },
        r.aboveCapReason?.takeIf { it.isNotBlank() }?.let { F_ABOVE_CAP_REASON to it },
        r.reason?.takeIf { it.isNotBlank() }?.let { F_REASON to it },
        r.note?.takeIf { it.isNotBlank() }?.let { F_NOTE to it },
        DisplayNames.of(r.createdByName, r.createdBy)?.let { F_PROPOSED_BY to it },
        F_PROPOSED_AT to OwnerFormat.dateTime(r.createdAt, zone),
    )

    fun decisionFields(r: PettyCashRequest): List<Pair<String, String>> = listOfNotNull(
        DisplayNames.of(r.decidedByName, r.decidedBy)?.let { F_DECIDED_BY to it },
        r.decisionNote?.takeIf { it.isNotBlank() }?.let { F_DECISION_NOTE to it },
    )

    /** A rejection must say why; approving takes an optional note. */
    fun canDecide(approve: Boolean, note: String): Boolean {
        val length = note.trim().length
        return length <= NOTE_MAX && (approve || length >= NOTE_MIN)
    }

    /** The proposer never decides their own request (the server refuses it too, and also refuses the fund's holder). */
    fun isOwn(r: PettyCashRequest, userId: String?): Boolean = userId != null && r.createdBy.equals(userId, ignoreCase = true)

    fun decidable(r: PettyCashRequest): Boolean = r.status == "PROPOSED" || r.status == "PENDING"

    /** Every refusal in the server's own words, except "already decided" (then the record reloads). */
    fun refusal(code: String?, serverMessage: String): String = if (code == "PETTY_CASH_ALREADY_DECIDED") ALREADY_DECIDED else serverMessage

    fun done(approve: Boolean): String = if (approve) APPROVED else REJECTED
}

@Composable
fun PettyCashMovementRow(m: PettyCashMovementReviewDto, zone: ZoneId) = PettyCashRequestRow(PettyCashRequest.of(PettyCashMovementReview(m)), zone)

@Composable
fun PettyCashAdjustmentRow(a: PettyCashAdjustmentReviewDto, zone: ZoneId) = PettyCashRequestRow(PettyCashRequest.of(a), zone)

@Composable
private fun PettyCashRequestRow(r: PettyCashRequest, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(PettyCashReviewText.headline(r), style = AssetaType.headline)
        Text(listOfNotNull(r.number, PettyCashReviewText.proposedBy(r)).joinToString(" · "), style = AssetaType.subheadline, color = palette.secondaryText)
        (r.reason ?: r.aboveCapReason ?: r.note)?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText, maxLines = 2) }
        Text(OwnerFormat.dateTime(r.createdAt, zone), style = AssetaType.caption, color = palette.secondaryText)
    }
}

/** One petty cash movement or adjustment, read by id: approve or reject while it waits. */
class PettyCashReviewViewModel private constructor(
    private val load: suspend () -> Load<PettyCashRequest>,
    private val decideCall: suspend (Boolean, String) -> ActionResult<PettyCashRequest>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PettyCashRequest>({ load() }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun decide(approve: Boolean, note: String) {
        if (_busy.value || !PettyCashReviewText.canDecide(approve, note)) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = decideCall(approve, note)) {
                is ActionResult.Done -> {
                    val decided = r.value
                    replaceData { it.copy(status = decided.status, decidedBy = decided.decidedBy, decidedByName = decided.decidedByName, decisionNote = decided.decisionNote) }
                    _message.value = PettyCashReviewText.done(approve)
                }
                is ActionResult.Refused -> {
                    _error.value = PettyCashReviewText.refusal(r.code, r.serverMessage ?: r.error.message)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }

    companion object {
        fun movement(data: OwnerData, id: String, refreshOn: Flow<Unit>) = PettyCashReviewViewModel(
            { data.pettyCashMovementReview(id).map(PettyCashRequest::of) },
            { approve, note -> data.decidePettyCashMovement(id, approve, note).map { PettyCashRequest.of(PettyCashMovementReview(it)) } },
            refreshOn,
        )

        fun adjustment(data: OwnerData, id: String, refreshOn: Flow<Unit>) = PettyCashReviewViewModel(
            { data.pettyCashAdjustmentReview(id).map(PettyCashRequest::of) },
            { approve, note -> data.decidePettyCashAdjustment(id, approve, note).map(PettyCashRequest::of) },
            refreshOn,
        )
    }
}

private fun <T, R> ActionResult<T>.map(f: (T) -> R): ActionResult<R> = when (this) {
    is ActionResult.Done -> ActionResult.Done(f(value))
    is ActionResult.Refused -> this
}

@Composable
fun PettyCashReviewScreen(vm: PettyCashReviewViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var approving by rememberSaveable { mutableStateOf(false) }
    var rejecting by rememberSaveable { mutableStateOf(false) }
    var note by rememberSaveable { mutableStateOf("") }
    val zone = ZoneId.systemDefault()
    SnapshotScaffold(state, vm::refresh) { r ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(PettyCashReviewText.CARD) {
                    Text(PettyCashReviewText.headline(r), style = AssetaType.headline)
                    PettyCashReviewText.fields(r, zone).forEach { (label, value) -> KeyValue(label, value) }
                    LabeledValue(PettyCashReviewText.F_STATUS) { StatusPill(PettyCashReviewText.status(r.status), OwnerColors.tone(PettyCashReviewText.statusTone(r.status))) }
                    PettyCashReviewText.decisionFields(r).forEach { (label, value) -> KeyValue(label, value) }
                }
            }
            if (!r.isAdjustment && r.kind == "TOP_UP") item {
                SectionCard(PettyCashReviewText.EXPENSES) {
                    when {
                        r.expensesFailed -> FootNote(PettyCashReviewText.EXPENSES_FAILED)
                        r.expenses.isEmpty() -> FootNote(PettyCashReviewText.EXPENSES_NONE)
                        else -> r.expenses.forEach { Text(it, style = MaterialTheme.typography.bodyLarge) }
                    }
                }
            }
            if (PettyCashReviewText.decidable(r)) item {
                SectionCard(PettyCashReviewText.DECISION, footer = if (r.isAdjustment) PettyCashReviewText.EXPLANATION_ADJUSTMENT else PettyCashReviewText.EXPLANATION_MOVEMENT) {
                    val gate = session.can(OwnerAction.DECIDE_PETTY_CASH, online, state.snapshot?.source)
                    when {
                        gate is MutationCheck.Blocked -> BlockedNote(gate.reason)
                        PettyCashReviewText.isOwn(r, session.userId) -> BlockedNote(PettyCashReviewText.OWN)
                        else -> Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                { note = ""; approving = true }, enabled = !busy, modifier = Modifier.testTag("approve-petty-${r.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(PettyCashReviewText.APPROVE) }
                            Spacer(Modifier.weight(1f))
                            Button(
                                { note = ""; rejecting = true }, enabled = !busy, modifier = Modifier.testTag("reject-petty-${r.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(PettyCashReviewText.REJECT) }
                        }
                    }
                }
            }
            error?.let {
                item {
                    GroupedSection {
                        Text(
                            it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.testTag("petty-error").semantics { liveRegion = LiveRegionMode.Assertive },
                        )
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    if (approving || rejecting) {
        val approve = approving
        val close = { approving = false; rejecting = false }
        val tooShort = !approve && note.isNotEmpty() && !PettyCashReviewText.canDecide(false, note)
        AlertDialog(
            onDismissRequest = close,
            title = { Text(if (approve) PettyCashReviewText.APPROVE_TITLE else PettyCashReviewText.REJECT_TITLE) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.data?.let { Text(PettyCashReviewText.headline(it), style = AssetaType.subheadline) }
                    OutlinedTextField(
                        note, { note = it.take(PettyCashReviewText.NOTE_MAX) }, Modifier.fillMaxWidth().testTag("petty-note"),
                        label = { Text(if (approve) PettyCashReviewText.NOTE_OPTIONAL else PettyCashReviewText.REASON_REQUIRED) }, minLines = 2, isError = tooShort,
                        supportingText = if (tooShort) ({ Text(PettyCashReviewText.ERR_REASON_SHORT) }) else null,
                    )
                }
            },
            confirmButton = {
                TextButton({ close(); vm.decide(approve, note) }, enabled = PettyCashReviewText.canDecide(approve, note)) {
                    if (approve) Text(PettyCashReviewText.APPROVE) else Text(PettyCashReviewText.REJECT, color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(close) { Text(PettyCashReviewText.CANCEL) } },
        )
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}
