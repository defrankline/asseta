package com.asseta.owner.ui.approvals

import androidx.compose.foundation.BorderStroke
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
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
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
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.session.UiError
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
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

class ApprovalsViewModel private constructor(
    val data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    val highlight: String?,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<ApprovalRequestDto>>({ data.approvals(selected.value) }, refreshOn) {
    constructor(data: OwnerData, highlight: String?, refreshOn: Flow<Unit>) : this(data, MutableStateFlow("PENDING"), highlight, refreshOn)

    val status: StateFlow<String?> get() = selected
    private val _error = MutableStateFlow<DecisionError?>(null)
    val error: StateFlow<DecisionError?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }

    fun decide(id: String, approve: Boolean, note: String?) {
        if (_busy.value) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decideApproval(id, approve, note)) {
                is ActionResult.Done -> {
                    replaceData { page -> page.copy(items = page.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = if (approve) "Approved." else "Rejected."
                }
                is ActionResult.Refused -> {
                    _error.value = DecisionError(id, r.error, r.code)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }

    companion object {
        val FILTERS = listOf("PENDING", "APPROVED", "REJECTED")
    }
}

@Composable
fun ApprovalsScreen(vm: ApprovalsViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var deciding by remember { mutableStateOf<Pair<ApprovalRequestDto, Boolean>?>(null) }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            ApprovalsViewModel.FILTERS.forEach { s -> FilterChip(status == s, { vm.filter(s) }, label = { Text(OwnerFormat.humanize(s)) }) }
        }
        message?.let { Text(it, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.primary) }
        SnapshotScaffold(state, vm::refresh) { page ->
            val gate = session.can(OwnerAction.DECIDE_APPROVAL, online, state.snapshot?.source)
            val zone = ZoneId.systemDefault()
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (page.items.isEmpty()) item { Text("Nothing here.") }
                if (gate is MutationCheck.Blocked && page.items.any { it.status == "PENDING" }) item { Text(gate.reason, style = MaterialTheme.typography.bodySmall) }
                items(page.items, key = { it.id.toString() }) { a ->
                    ApprovalCard(
                        vm, a, a.id.toString() == vm.highlight, zone, online && !state.stale,
                        enabled = gate is MutationCheck.Allowed && !busy,
                        error = error?.takeIf { it.approvalId == a.id.toString() },
                        onDecide = { approve -> deciding = a to approve },
                    )
                }
            }
        }
    }
    deciding?.let { (a, approve) ->
        DecisionDialog(a, approve, onDismiss = { deciding = null }) { note -> vm.decide(a.id.toString(), approve, note); deciding = null }
    }
}

@Composable
private fun ApprovalCard(
    vm: ApprovalsViewModel, a: ApprovalRequestDto, highlighted: Boolean, zone: ZoneId, online: Boolean, enabled: Boolean,
    error: DecisionError?, onDecide: (Boolean) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var expense by remember { mutableStateOf<ExpenseDto?>(null) }
    var detailError by remember { mutableStateOf<String?>(null) }
    Card(Modifier.fillMaxWidth(), border = if (highlighted) BorderStroke(2.dp, MaterialTheme.colorScheme.secondary) else null) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(OwnerFormat.money(a.amount.value, a.currency), style = MaterialTheme.typography.titleMedium)
            Text("${OwnerFormat.humanize(a.subjectType)} · ${OwnerFormat.humanize(a.status)}", style = MaterialTheme.typography.bodySmall)
            Text(a.reason, style = MaterialTheme.typography.bodyMedium)
            Text("Requested ${OwnerFormat.dateTime(a.requestedAt, zone)}", style = MaterialTheme.typography.bodySmall)
            a.decisionNote?.let { Text("Decision note: $it", style = MaterialTheme.typography.bodySmall) }
            expense?.let { e ->
                KeyValue("Description", e.description)
                e.supplier?.let { KeyValue("Supplier", it) }
                KeyValue("Paid from", OwnerFormat.humanize(e.paidFrom))
                KeyValue("Incurred", OwnerFormat.dateTime(e.incurredAt, zone))
                e.receiptAttachmentIds.forEach { rid -> EvidencePhoto("receipt", online) { vm.data.receiptUrl(e.id.toString(), rid.toString()) } }
            }
            detailError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            if (error != null) SegregationNotice(error)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (a.subjectType == "EXPENSE" && expense == null) {
                    TextButton(enabled = online, onClick = {
                        scope.launch {
                            when (val r = vm.data.expense(a.subjectId.toString())) {
                                is ActionResult.Done -> expense = r.value
                                is ActionResult.Refused -> detailError = r.error.message
                            }
                        }
                    }) { Text("Expense details") }
                }
                if (a.status == "PENDING") {
                    OutlinedButton({ onDecide(false) }, enabled = enabled, modifier = Modifier.testTag("reject-${a.id}")) { Text("Reject") }
                    Button({ onDecide(true) }, enabled = enabled, modifier = Modifier.testTag("approve-${a.id}")) { Text("Approve") }
                }
            }
        }
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
            if (error.segregationOfDuties) Text("Not allowed: segregation of duties", style = MaterialTheme.typography.titleSmall)
            Text(error.error.message, style = MaterialTheme.typography.bodySmall)
            error.error.reference?.let { Text("Reference: $it", style = MaterialTheme.typography.bodySmall) }
        }
    }
}

@Composable
private fun DecisionDialog(a: ApprovalRequestDto, approve: Boolean, onDismiss: () -> Unit, onConfirm: (String?) -> Unit) {
    var note by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (approve) "Approve request" else "Reject request") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("${OwnerFormat.money(a.amount.value, a.currency)} — ${a.reason}")
                OutlinedTextField(note, { note = it.take(1000) }, label = { Text(if (approve) "Note (optional)" else "Reason for rejection") }, minLines = 2)
            }
        },
        confirmButton = { Button({ onConfirm(note) }, enabled = approve || note.isNotBlank()) { Text(if (approve) "Approve" else "Reject") } },
        dismissButton = { TextButton(onDismiss) { Text("Cancel") } },
    )
}
