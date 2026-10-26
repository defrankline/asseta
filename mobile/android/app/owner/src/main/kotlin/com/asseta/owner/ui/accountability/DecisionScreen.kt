package com.asseta.owner.ui.accountability

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
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.approvals.ApprovalText
import com.asseta.owner.ui.approvals.DecisionError
import com.asseta.owner.ui.approvals.SegregationNotice
import com.asseta.owner.ui.common.BlockedNote
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
import com.asseta.core.ui.R as CoreR

private val T = OwnerAccountabilityTexts

/** One accountability request (found among the waiting ones of its kind) with approve / reject. */
/** One accountability request, loaded by id (the exact record: decided ones show their status), with approve / reject. */
class DecisionViewModel(val data: OwnerData, val kind: DecisionKind, val id: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<List<DecisionItem>>({ data.decision(kind, id) }, refreshOn) {
    private val _error = MutableStateFlow<DecisionError?>(null)
    val error: StateFlow<DecisionError?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun item(list: List<DecisionItem>): DecisionItem? = list.firstOrNull { it.id == id }

    fun decide(approve: Boolean, note: String) {
        if (_busy.value || !DecisionMapper.canDecide(kind, approve, note)) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decide(kind, id, approve, note)) {
                is ActionResult.Done -> {
                    val status = if (approve) "APPROVED" else "REJECTED"
                    replaceData { list -> list.map { if (it.id == id) it.copy(status = status, pending = false) else it } }
                    _message.value = if (approve) T.APPROVED else T.REJECTED
                }
                is ActionResult.Refused -> {
                    _error.value = DecisionError(id, r.error, r.code)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun DecisionScreen(vm: DecisionViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var note by rememberSaveable { mutableStateOf("") }
    var confirmReject by rememberSaveable { mutableStateOf(false) }
    SnapshotScaffold(state, vm::refresh) { list ->
        val item = vm.item(list)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            if (item == null) {
                item { EmptyState(T.NOT_FOUND_TITLE, T.NOT_FOUND_MESSAGE, CoreR.drawable.ic_help) }
                return@LazyColumn
            }
            item {
                SectionCard(T.REQUEST) {
                    Text(item.headline, style = AssetaType.headline)
                    item.fields.forEach { KeyValue(it.label, it.value) }
                    // Shown once: kinds whose fields already carry a "Reason" row (revenue) skip the generic line.
                    DecisionMapper.reasonLine(item)?.let { KeyValue(T.F_REASON, it) }
                    item.proposedAt?.let { KeyValue(T.F_PROPOSED, OwnerFormat.dateTime(it, zone)) }
                    LabeledValue(T.F_STATUS) { StatusPill(OwnerFormat.humanize(item.status), ApprovalText.statusColor(item.status)) }
                    item.photoAttachmentId?.let { pid -> EvidencePhoto("meter", online && !state.stale) { vm.data.attachmentUrl(pid) } }
                }
            }
            if (item.pending) item {
                SectionCard(T.DECISION, footer = if (vm.kind == DecisionKind.NON_REVENUE) T.NONREV_FOOTER else T.FOOTER) {
                    val gate = session.can(vm.kind.action, online, state.snapshot?.source)
                    val own = item.isOwn(session.userId)
                    when {
                        gate is MutationCheck.Blocked -> BlockedNote(gate.reason)
                        own -> BlockedNote(T.OWN_REQUEST)
                    }
                    if (gate !is MutationCheck.Blocked) {
                        OutlinedTextField(
                            note, { note = it.take(1000) }, Modifier.fillMaxWidth().testTag("decision-note"),
                            label = { Text(if (vm.kind.meter) T.NOTE_REQUIRED else T.NOTE_OPTIONAL) }, minLines = 2, enabled = !own,
                        )
                        // Same as the expense approvals: a green "Approve" and a bordered red "Reject" on one row; both
                        // disabled on the user's own request (segregation of duties).
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                { vm.decide(true, note) }, enabled = !busy && !own && DecisionMapper.canDecide(vm.kind, true, note),
                                modifier = Modifier.testTag("approve-${item.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(T.APPROVE) }
                            Spacer(Modifier.weight(1f))
                            Button(
                                { confirmReject = true }, enabled = !busy && !own && DecisionMapper.canDecide(vm.kind, false, note),
                                modifier = Modifier.testTag("reject-${item.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(T.REJECT) }
                        }
                        error?.let { SegregationNotice(it) }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    if (confirmReject) {
        AlertDialog(
            onDismissRequest = { confirmReject = false },
            title = { Text(T.CONFIRM_REJECT) },
            confirmButton = { TextButton({ confirmReject = false; vm.decide(false, note) }) { Text(T.REJECT, color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ confirmReject = false }) { Text("Cancel") } },
        )
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}

/** A row of an accountability section under Approvals. */
@Composable
fun DecisionRow(item: DecisionItem, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(item.headline, style = AssetaType.headline)
        item.reason?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.subheadline, color = palette.secondaryText, maxLines = 2) }
        item.proposedAt?.let {
            val time = OwnerFormat.dateTime(it, zone)
            FootNote(item.proposedByName?.let { name -> T.proposedBy(time, name) } ?: T.proposed(time))
        }
    }
}
