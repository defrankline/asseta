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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
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
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.EvidencePhoto
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

/** Meter reset wording and rules shared with iOS (Approvals "Meter resets" section and `MeterResetView`). */
object MeterResetText {
    const val SECTION = "Meter resets"
    const val ROW_TITLE = "Meter reset"
    const val EMPTY = "No meter resets waiting."
    const val NOTE_LABEL = "Note (required)"
    const val APPROVE = "Approve reset"
    const val REJECT = "Reject reset"
    const val NOT_FOUND = "Meter reset not found"

    /** A reading without trailing zeros: "1250.5", "0". */
    fun reading(value: java.math.BigDecimal): String = OwnerFormat.decimal(value)

    /** "1250.5 → 0 · effective 22 Oct 2026, 08:00". */
    fun detail(r: MeterResetDto, zone: ZoneId): String =
        "${reading(r.oldReading.value)} → ${reading(r.newReading.value)} · effective ${OwnerFormat.dateTime(r.effectiveAt, zone)}"

    fun statusTone(status: String): KpiTone = when (status) {
        "PENDING" -> KpiTone.WARNING
        "APPROVED" -> KpiTone.GOOD
        "REJECTED" -> KpiTone.CRITICAL
        else -> KpiTone.MUTED
    }

    /** Both outcomes need a note of at least 5 characters. */
    fun canDecide(note: String): Boolean = MutationGate.resetNoteValid(note)

    fun done(approve: Boolean): String = if (approve) "Reset approved." else "Reset rejected."
}

/**
 * One reset request, found in the pending list (shared snapshot with the Approvals section) or, once decided, in the
 * full list; approve / reject with a required note.
 */
class MeterResetViewModel(val data: OwnerData, val resetId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<List<MeterResetDto>>({
        val pending = data.meterResets("PENDING")
        if (pending is Load.Ok && pending.snapshot.data.any { it.id.toString() == resetId }) {
            pending
        } else {
            data.meterResets(null).let { all -> if (all is Load.Ok) all else pending }
        }
    }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun reset(list: List<MeterResetDto>): MeterResetDto? = list.firstOrNull { it.id.toString() == resetId }

    fun decide(approve: Boolean, note: String) {
        if (_busy.value || !MeterResetText.canDecide(note)) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decideMeterReset(resetId, approve, note)) {
                is ActionResult.Done -> {
                    replaceData { list -> list.map { if (it.id == r.value.id) r.value else it } }
                    _message.value = MeterResetText.done(approve)
                    // Reload: the decided reset now comes from the full list.
                    refresh()
                }
                is ActionResult.Refused -> {
                    _error.value = OwnerErrors.meterResetMessage(r.code, r.error.message)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

/** A row of the Approvals "Meter resets" section. */
@Composable
fun MeterResetRow(r: MeterResetDto, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(MeterResetText.ROW_TITLE, style = AssetaType.headline)
        Text(MeterResetText.detail(r, zone), style = AssetaType.subheadline, color = palette.secondaryText)
        Text(r.reason, style = AssetaType.caption, color = palette.secondaryText)
    }
}

@Composable
fun MeterResetScreen(vm: MeterResetViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var note by rememberSaveable { mutableStateOf("") }
    SnapshotScaffold(state, vm::refresh) { list ->
        val r = vm.reset(list)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            if (r == null) {
                item { EmptyState(MeterResetText.NOT_FOUND, icon = CoreR.drawable.ic_help) }
                return@LazyColumn
            }
            item {
                SectionCard(MeterResetText.ROW_TITLE) {
                    KeyValue("Old reading", MeterResetText.reading(r.oldReading.value))
                    KeyValue("New reading", MeterResetText.reading(r.newReading.value))
                    KeyValue("Effective at", OwnerFormat.dateTime(r.effectiveAt, zone))
                    KeyValue("Reason", r.reason)
                    LabeledValue("Status") { StatusPill(OwnerFormat.humanize(r.status), OwnerColors.tone(MeterResetText.statusTone(r.status))) }
                    r.decidedAt?.let { KeyValue("Decided", OwnerFormat.dateTime(it, zone)) }
                    r.evidenceAttachmentId?.let { id -> EvidencePhoto("evidence photo", online && !state.stale) { vm.data.attachmentUrl(id.toString()) } }
                }
            }
            if (r.status == "PENDING" && session.features.meterApprove) item {
                SectionCard("Decision") {
                    val gate = session.can(OwnerAction.DECIDE_METER_RESET, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        BlockedNote(gate.reason)
                    } else {
                        OutlinedTextField(note, { note = it.take(2000) }, Modifier.fillMaxWidth(), label = { Text(MeterResetText.NOTE_LABEL) }, minLines = 2)
                        val ready = !busy && MeterResetText.canDecide(note)
                        // Same layout as the expense decision: green "Approve reset" and a bordered red "Reject reset".
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                { vm.decide(true, note) }, enabled = ready, modifier = Modifier.testTag("approve-reset-${r.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(MeterResetText.APPROVE) }
                            Spacer(Modifier.weight(1f))
                            Button(
                                { vm.decide(false, note) }, enabled = ready, modifier = Modifier.testTag("reject-reset-${r.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text(MeterResetText.REJECT) }
                        }
                        error?.let {
                            Text(
                                it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("reset-error").semantics { liveRegion = LiveRegionMode.Assertive },
                            )
                        }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}
