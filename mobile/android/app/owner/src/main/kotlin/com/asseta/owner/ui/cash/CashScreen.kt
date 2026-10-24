package com.asseta.owner.ui.cash

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.text.input.KeyboardType
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.finance.AmountInput
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.ui.components.ButtonRow
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.HandoverList
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.Section
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId

enum class CashPeriod(val label: String) { TODAY("Today"), WEEK("7 days"), MONTH("This month") }

/** One labelled figure of a supervisor's cash card; [warning] marks amounts still awaiting a decision. */
data class CashLine(val label: String, val amount: BigDecimal, val warning: Boolean = false)

/** Cash with supervisors wording and rules shared with iOS (`CashView`). */
object CashText {
    val PERIODS: List<Pair<CashPeriod, String>> = CashPeriod.entries.map { it to it.label }
    val DEFAULT_PERIOD = CashPeriod.TODAY
    const val HOLDING = "Holding"
    const val EMPTY = "No supervisor cash in this period."
    const val FOOTER = "Holding = opening + floats + collections − approved spending − verified handovers."

    /** Local days [from, to] of a period ending [today]. */
    fun range(period: CashPeriod, today: LocalDate): Pair<LocalDate, LocalDate> = when (period) {
        CashPeriod.TODAY -> today to today
        CashPeriod.WEEK -> today.minusDays(6) to today
        CashPeriod.MONTH -> today.withDayOfMonth(1) to today
    }

    /** Largest holding first. */
    fun sorted(rows: List<CashSupervisorSummaryDto>): List<CashSupervisorSummaryDto> = rows.sortedByDescending { it.closingOutstanding.value }

    /** The movements, then (only when above zero) what still awaits approval or verification. */
    fun lines(r: CashSupervisorSummaryDto): List<CashLine> = listOf(
        CashLine("Opening", r.opening.value),
        CashLine("Floats issued", r.floatsIssued.value),
        CashLine("Collections", r.collections.value),
        CashLine("Approved spending", r.approvedSpending.value),
        CashLine("Handed over (verified)", r.verifiedHandovers.value),
    ) + listOf(
        CashLine("Spending awaiting approval", r.pendingSpending.value, warning = true),
        CashLine("Handovers awaiting verification", r.claimedUnverifiedHandovers.value, warning = true),
        CashLine("Collections awaiting verification", r.unverifiedCollections.value, warning = true),
    ).filter { it.amount.signum() > 0 }
}

/** Issuing a cash float from a supervisor's cash card (wording shared with iOS). */
object FloatText {
    const val ISSUE_FLOAT = "Issue float"
    const val TITLE = "Issue a cash float"
    const val NOTE = "Note (optional)"
    const val ISSUE = "Issue"
    const val CANCEL = "Cancel"
    const val ISSUED = "Float issued."

    fun amountLabel(currency: String): String = "Amount ($currency)"

    /** The typed amount as an exact positive decimal string, or null when not valid. */
    fun amount(text: String): String? =
        (AmountParser.parse(text.trim(), DecimalLimit.MONEY) as? AmountInput.Valid)?.value?.takeIf { it.signum() > 0 }?.toPlainString()
}

class CashViewModel private constructor(
    private val data: OwnerData,
    private val selected: MutableStateFlow<CashPeriod>,
    today: () -> LocalDate,
    refreshOn: Flow<Unit>,
    handovers: Boolean,
) : SnapshotViewModel<List<CashSupervisorSummaryDto>>({
    val (from, to) = CashText.range(selected.value, today())
    data.cash(selected.value.name, from, to)
}, refreshOn) {
    /** [handovers]: also load the claimed cash handovers (`tenant.finance.read`) so each card links to them. */
    constructor(
        data: OwnerData,
        refreshOn: Flow<Unit>,
        handovers: Boolean = false,
        today: () -> LocalDate = { LocalDate.now(ZoneId.systemDefault()) },
    ) : this(data, MutableStateFlow(CashText.DEFAULT_PERIOD), today, refreshOn, handovers)

    val period: StateFlow<CashPeriod> get() = selected

    /** Claimed handovers (null when the role cannot read them), shown on their supervisor's card. */
    val claimedHandovers: Section<HandoverList>? = if (handovers) Section(viewModelScope) { data.handovers(HandoverText.CLAIMED) } else null

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    init {
        claimedHandovers?.refresh()
        viewModelScope.launch { refreshOn.collect { claimedHandovers?.refresh() } }
    }

    fun select(period: CashPeriod) {
        selected.value = period
        refresh()
    }

    fun refreshAll() {
        refresh()
        claimedHandovers?.refresh()
    }

    /** Issue a float of [amountText] in [currency] to [staffMemberId]; the cards reload on success. */
    fun issueFloat(staffMemberId: String, currency: String, amountText: String, note: String) {
        val amount = FloatText.amount(amountText)
        if (_busy.value || amount == null) return
        _busy.value = true
        _error.value = null
        _message.value = null
        viewModelScope.launch {
            when (val r = data.issueFloat(staffMemberId, amount, currency, note)) {
                is ActionResult.Done -> {
                    _message.value = FloatText.ISSUED
                    refresh()
                }
                is ActionResult.Refused -> _error.value = r.error.message
            }
            _busy.value = false
        }
    }
}

/** A float being issued from a card: the supervisor and the card's currency. */
private data class FloatTarget(val staffMemberId: String, val staffName: String, val currency: String)

/**
 * One card per supervisor and currency: the cash they hold, how it moved, what still awaits a decision, the claimed
 * handovers (each opening confirm received / dispute) and "Issue float".
 */
@Composable
fun CashScreen(vm: CashViewModel, session: OwnerSession, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val period by vm.period.collectAsStateWithLifecycle()
    val handovers = vm.claimedHandovers?.state?.collectAsStateWithLifecycle()?.value?.data
    val message by vm.message.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var target by remember { mutableStateOf<FloatTarget?>(null) }
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(CashText.PERIODS, period, vm::select)
        SnapshotScaffold(state, vm::refreshAll) { rows ->
            val zone = ZoneId.systemDefault()
            val floats = session.features.issueFloats
            val gate = session.can(OwnerAction.ISSUE_FLOAT, online, state.snapshot?.source)
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
                error?.let {
                    item {
                        GroupedSection {
                            Text(
                                it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("float-error").semantics { liveRegion = LiveRegionMode.Assertive },
                            )
                        }
                    }
                }
                if (floats && gate is MutationCheck.Blocked) item { Column(Modifier.padding(horizontal = 32.dp)) { BlockedNote(gate.reason) } }
                if (rows.isEmpty()) item { EmptyState(CashText.EMPTY, icon = R.drawable.ic_cash) }
                CashText.sorted(rows).forEach { r ->
                    val claimed = handovers?.items.orEmpty().filter { it.staffMemberId == r.staffMemberId && it.currency == r.currency }
                    item(key = "${r.staffMemberId}-${r.currency}") {
                        CashCard(
                            r, claimed, zone,
                            onHandover = { onOpen(OwnerDestination.Handover(it)) },
                            onIssueFloat = if (floats) {
                                { target = FloatTarget(r.staffMemberId.toString(), r.staffName, r.currency) }
                            } else {
                                null
                            },
                            floatEnabled = gate is MutationCheck.Allowed && !busy,
                        )
                    }
                }
                item { Column(Modifier.padding(horizontal = 32.dp)) { FootNote(CashText.FOOTER) } }
            }
        }
    }
    target?.let { t ->
        FloatDialog(t.currency, onDismiss = { target = null }) { amount, note ->
            target = null
            vm.issueFloat(t.staffMemberId, t.currency, amount, note)
        }
    }
}

@Composable
private fun CashCard(
    r: CashSupervisorSummaryDto,
    claimed: List<CashHandoverDto>,
    zone: ZoneId,
    onHandover: (String) -> Unit,
    onIssueFloat: (() -> Unit)?,
    floatEnabled: Boolean,
) {
    GroupedSection(header = r.staffName) {
        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(CashText.HOLDING, style = AssetaType.caption, color = palette.secondaryText)
            Text(OwnerFormat.money(r.closingOutstanding.value, r.currency), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        CashText.lines(r).forEach { l ->
            val value = OwnerFormat.money(l.amount, r.currency)
            if (l.warning) LabeledValue(l.label, value, valueColor = OwnerColors.Warning) else KeyValue(l.label, value)
        }
        claimed.forEach { h ->
            Column(Modifier.fillMaxWidth().clickable(role = Role.Button) { onHandover(h.id.toString()) }.testTag("cash-handover-${h.id}")) {
                HandoverRow(h, r.staffName, zone)
            }
        }
        onIssueFloat?.let { ButtonRow(FloatText.ISSUE_FLOAT, Modifier.testTag("issue-float-${r.staffMemberId}-${r.currency}"), enabled = floatEnabled, onClick = it) }
    }
}

/** "Issue a cash float": the amount in the card's currency and an optional note. */
@Composable
private fun FloatDialog(currency: String, onDismiss: () -> Unit, onIssue: (amount: String, note: String) -> Unit) {
    var amount by rememberSaveable { mutableStateOf("") }
    var note by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(FloatText.TITLE) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    amount, { v -> amount = v.filter { it.isDigit() || it == '.' } }, Modifier.fillMaxWidth().testTag("float-amount"),
                    label = { Text(FloatText.amountLabel(currency)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true,
                )
                OutlinedTextField(
                    note, { note = it.take(1000) }, Modifier.fillMaxWidth().testTag("float-note"),
                    label = { Text(FloatText.NOTE) }, minLines = 2,
                )
            }
        },
        confirmButton = { TextButton({ onIssue(amount, note) }, enabled = FloatText.amount(amount) != null) { Text(FloatText.ISSUE) } },
        dismissButton = { TextButton(onDismiss) { Text(FloatText.CANCEL) } },
    )
}
