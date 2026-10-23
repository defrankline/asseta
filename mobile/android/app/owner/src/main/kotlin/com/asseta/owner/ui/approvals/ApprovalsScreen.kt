package com.asseta.owner.ui.approvals

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.session.UiError
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

/** A refused decision, kept next to the request it belongs to ([code] e.g. SEGREGATION_OF_DUTIES). */
data class DecisionError(val approvalId: String, val error: UiError, val code: String?) {
    val segregationOfDuties: Boolean get() = code == "SEGREGATION_OF_DUTIES"
}

/** Approval wording and rules shared with iOS (`ApprovalsView` / `ApprovalDetailView`). */
object ApprovalText {
    val FILTERS: List<Pair<String, String>> = listOf("PENDING" to "Pending", "APPROVED" to "Approved", "REJECTED" to "Rejected")
    const val DEFAULT_FILTER = "PENDING"
    const val EMPTY_TITLE = "Nothing here"
    const val EMPTY_MESSAGE = "No requests with this status."
    const val NOT_FOUND_TITLE = "Request not found"
    const val NOT_FOUND_MESSAGE = "It may be older than the latest 200 requests."
    const val NOTE_LABEL = "Note (optional to approve, required to reject)"
    const val SOD_FOOTER = "The person who submitted a request can't decide it (segregation of duties)."
    const val SOD_TITLE = "Not allowed: segregation of duties"
    const val CONFIRM_REJECT = "Reject this request?"

    /** A rejection must say why; an approval note is optional. */
    fun canDecide(approve: Boolean, note: String): Boolean = approve || note.isNotBlank()

    fun statusColor(status: String) = when (status) {
        "APPROVED" -> OwnerColors.Live
        "REJECTED" -> OwnerColors.Critical
        else -> OwnerColors.Warning
    }

    fun summary(a: ApprovalRequestDto): String = "${OwnerFormat.humanize(a.subjectType)} · ${a.reason}"
}

class ApprovalsViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<ApprovalRequestDto>>({ data.approvals(selected.value) }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>) : this(data, MutableStateFlow(ApprovalText.DEFAULT_FILTER), refreshOn)

    val status: StateFlow<String?> get() = selected

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }
}

/** One request (found in the latest 200; there is no single-request endpoint) with approve / reject. */
class ApprovalDetailViewModel(val data: OwnerData, val approvalId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PageDto<ApprovalRequestDto>>({ data.recentApprovals() }, refreshOn) {
    private val _error = MutableStateFlow<DecisionError?>(null)
    val error: StateFlow<DecisionError?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun request(page: PageDto<ApprovalRequestDto>): ApprovalRequestDto? = page.items.firstOrNull { it.id.toString() == approvalId }

    fun decide(approve: Boolean, note: String?) {
        if (_busy.value || !ApprovalText.canDecide(approve, note.orEmpty())) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decideApproval(approvalId, approve, note)) {
                is ActionResult.Done -> {
                    replaceData { page -> page.copy(items = page.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = if (approve) "Approved." else "Rejected."
                }
                is ActionResult.Refused -> {
                    _error.value = DecisionError(approvalId, r.error, r.code)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun ApprovalsScreen(vm: ApprovalsViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            ApprovalText.FILTERS.forEach { (s, label) -> FilterChip(status == s, { vm.filter(s) }, label = { Text(label) }) }
        }
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (page.items.isEmpty()) item { EmptyState(ApprovalText.EMPTY_TITLE, ApprovalText.EMPTY_MESSAGE) }
                items(page.items, key = { it.id.toString() }) { a ->
                    Card(Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(OwnerDestination.Approvals(a.id.toString())) }) {
                        Column(Modifier.padding(12.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(OwnerFormat.money(a.amount.value, a.currency), style = MaterialTheme.typography.titleMedium)
                                StatusPill(OwnerFormat.humanize(a.status), ApprovalText.statusColor(a.status))
                            }
                            Text(ApprovalText.summary(a), style = MaterialTheme.typography.bodyMedium)
                            Text("Requested ${OwnerFormat.dateTime(a.requestedAt, zone)}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ApprovalDetailScreen(vm: ApprovalDetailViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var note by rememberSaveable { mutableStateOf("") }
    var confirmReject by rememberSaveable { mutableStateOf(false) }
    SnapshotScaffold(state, vm::refresh) { page ->
        val a = vm.request(page)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (a == null) {
                item { EmptyState(ApprovalText.NOT_FOUND_TITLE, ApprovalText.NOT_FOUND_MESSAGE) }
                return@LazyColumn
            }
            item {
                SectionCard("Request") {
                    KeyValue("Amount", OwnerFormat.money(a.amount.value, a.currency))
                    KeyValue("Type", OwnerFormat.humanize(a.subjectType))
                    KeyValue("Reason", a.reason)
                    KeyValue("Requested", OwnerFormat.dateTime(a.requestedAt, zone))
                    KeyValue("Status", OwnerFormat.humanize(a.status))
                    a.decidedAt?.let { KeyValue("Decided", OwnerFormat.dateTime(it, zone)) }
                    a.decisionNote?.let { KeyValue("Decision note", it) }
                    KeyValue("Policy", a.policyVersion)
                }
            }
            if (a.subjectType == "EXPENSE") item { ExpenseCard(vm.data, a.subjectId.toString(), online && !state.stale, zone) }
            if (a.status == "PENDING") item {
                SectionCard("Decision") {
                    val gate = session.can(OwnerAction.DECIDE_APPROVAL, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        FootNote(gate.reason)
                    } else {
                        OutlinedTextField(note, { note = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text(ApprovalText.NOTE_LABEL) }, minLines = 2)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                { vm.decide(true, note) }, enabled = !busy, modifier = Modifier.testTag("approve-${a.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live),
                            ) { Text("Approve") }
                            OutlinedButton(
                                { confirmReject = true }, enabled = !busy && ApprovalText.canDecide(false, note), modifier = Modifier.testTag("reject-${a.id}"),
                            ) { Text("Reject", color = MaterialTheme.colorScheme.error) }
                        }
                        error?.let { SegregationNotice(it) }
                    }
                    FootNote(ApprovalText.SOD_FOOTER)
                }
            }
            message?.let { item { Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } }
        }
    }
    if (confirmReject) {
        AlertDialog(
            onDismissRequest = { confirmReject = false },
            title = { Text(ApprovalText.CONFIRM_REJECT) },
            confirmButton = { TextButton({ confirmReject = false; vm.decide(false, note) }) { Text("Reject", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ confirmReject = false }) { Text("Cancel") } },
        )
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}

/** Expense behind an approval: fetched on demand (online only, never cached), with receipt photos. */
@Composable
private fun ExpenseCard(data: OwnerData, expenseId: String, online: Boolean, zone: ZoneId) {
    val scope = rememberCoroutineScope()
    var expense by remember { mutableStateOf<ExpenseDto?>(null) }
    var detailError by remember { mutableStateOf<String?>(null) }
    SectionCard("Expense") {
        val e = expense
        if (e == null) {
            TextButton(enabled = online, onClick = {
                scope.launch {
                    when (val r = data.expense(expenseId)) {
                        is ActionResult.Done -> expense = r.value
                        is ActionResult.Refused -> detailError = r.error.message
                    }
                }
            }) { Text(if (online) "Expense details" else "Expense details (online only)") }
        } else {
            KeyValue("Description", e.description)
            e.supplier?.let { KeyValue("Supplier", it) }
            KeyValue("Paid from", OwnerFormat.humanize(e.paidFrom))
            KeyValue("Incurred", OwnerFormat.dateTime(e.incurredAt, zone))
            e.receiptAttachmentIds.forEach { rid -> EvidencePhoto("receipt", online) { data.receiptUrl(e.id.toString(), rid.toString()) } }
        }
        detailError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
    }
}

/** Segregation-of-duties and other refusals, shown on the request itself (not as a transient toast). */
@Composable
fun SegregationNotice(error: DecisionError) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        modifier = Modifier.fillMaxWidth().testTag("decision-error").semantics { liveRegion = LiveRegionMode.Assertive },
    ) {
        Column(Modifier.padding(8.dp)) {
            if (error.segregationOfDuties) Text(ApprovalText.SOD_TITLE, style = MaterialTheme.typography.titleSmall)
            Text(error.error.message, style = MaterialTheme.typography.bodySmall)
            error.error.reference?.let { Text("Reference: $it", style = MaterialTheme.typography.bodySmall) }
        }
    }
}
