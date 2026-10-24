package com.asseta.owner.ui.exceptions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
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
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.alerts.AlertText
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EmptyState
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

/**
 * Exception review wording and rules, mirroring the web `ReviewExceptionDialog` (and shared with iOS): the reviewer
 * records an outcome -- EXPLAINED or CONFIRMED -- with a mandatory note of 5..2000 characters (audited).
 */
object ExceptionReviewText {
    const val SECTION = "Exceptions"
    const val EMPTY = "No open exceptions."
    const val REVIEW = "Review"
    const val RECORD_REVIEW = "Record review"
    const val CANCEL = "Cancel"
    const val EXPLANATION =
        "Record what the review found. The note is kept in the audit trail together with the original evidence, which is never changed."
    const val OUTCOME = "Outcome"
    const val NOTE = "Review note"
    const val CHOOSE_OUTCOME = "Choose an outcome"
    const val NOTE_REQUIRED = "A review note is required"
    const val NOTE_TOO_SHORT = "At least 5 characters"
    const val NOTE_TOO_LONG = "At most 2000 characters"
    const val REVIEWED = "Exception reviewed."
    const val NOT_FOUND = "Exception not found"
    const val BLOCKS_BILLING = "Blocks billing until reviewed"
    const val OPEN_JOB = "Open job"
    const val NOTE_MIN = 5
    const val NOTE_MAX = 2000

    /** Outcome value to the web's label, in the web's order. */
    val OUTCOMES: List<Pair<String, String>> = listOf(
        "EXPLAINED" to "Explained — a legitimate reason was found",
        "CONFIRMED" to "Discrepancy confirmed — evidence stands as recorded",
    )

    /** "Review · Meter decrease" (the review dialog title). */
    fun dialogTitle(e: ExceptionDto): String = "Review · ${ExceptionText.title(e)}"

    /** "Meter decrease on J-1001" (or just the type when the job number is unknown). */
    fun headline(e: ExceptionDto, jobNumber: String?): String =
        jobNumber?.takeIf { it.isNotBlank() }?.let { "${ExceptionText.title(e)} on $it" } ?: ExceptionText.title(e)

    /** The note's validation message, as on the web; null when valid. */
    fun noteError(note: String): String? {
        val n = note.trim()
        return when {
            n.isEmpty() -> NOTE_REQUIRED
            n.length < NOTE_MIN -> NOTE_TOO_SHORT
            n.length > NOTE_MAX -> NOTE_TOO_LONG
            else -> null
        }
    }

    fun canReview(outcome: String?, note: String): Boolean = outcome in OUTCOMES.map { it.first } && noteError(note) == null
}

/** A row of the Approvals "Exceptions" section: "<type> on <job number>" and when it was recorded. */
@Composable
fun ExceptionApprovalRow(e: ExceptionDto, jobNumber: String?, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(ExceptionReviewText.headline(e, jobNumber), style = AssetaType.headline, modifier = Modifier.weight(1f))
            if (e.blocking) StatusPill(ExceptionText.BLOCKING, OwnerColors.Critical)
        }
        Text(ExceptionText.detail(e, zone), style = AssetaType.subheadline, color = palette.secondaryText)
    }
}

/** One exception, found among the open ones or, once reviewed, in the full list; review with outcome and note. */
class ExceptionDetailViewModel(val data: OwnerData, val exceptionId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PageDto<ExceptionDto>>({
        val open = data.exceptions("OPEN", null)
        if (open is Load.Ok && open.snapshot.data.items.any { it.id.toString() == exceptionId }) {
            open
        } else {
            data.exceptions(null, null).let { all -> if (all is Load.Ok) all else open }
        }
    }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun exception(page: PageDto<ExceptionDto>): ExceptionDto? = page.items.firstOrNull { it.id.toString() == exceptionId }

    fun review(outcome: String?, note: String) {
        if (_busy.value || outcome == null || !ExceptionReviewText.canReview(outcome, note)) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.reviewException(exceptionId, outcome, note)) {
                is ActionResult.Done -> {
                    replaceData { page -> page.copy(items = page.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = ExceptionReviewText.REVIEWED
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
fun ExceptionDetailScreen(vm: ExceptionDetailViewModel, session: OwnerSession, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var reviewing by rememberSaveable { mutableStateOf(false) }
    var outcome by rememberSaveable { mutableStateOf<String?>(null) }
    var note by rememberSaveable { mutableStateOf("") }
    SnapshotScaffold(state, vm::refresh) { page ->
        val e = vm.exception(page)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            if (e == null) {
                item { EmptyState(ExceptionReviewText.NOT_FOUND, icon = CoreR.drawable.ic_help) }
                return@LazyColumn
            }
            item {
                SectionCard(ExceptionText.title(e)) {
                    LabeledValue("Status") {
                        StatusPill(OwnerFormat.humanize(e.status), ExceptionText.statusTone(e.status)?.let { OwnerColors.tone(it) } ?: OwnerColors.Warning)
                    }
                    KeyValue("Severity", OwnerFormat.humanize(e.severity))
                    if (e.blocking) KeyValue(ExceptionText.BLOCKING, ExceptionReviewText.BLOCKS_BILLING)
                    KeyValue("Recorded", OwnerFormat.dateTime(e.createdAt, zone))
                    e.reviewedAt?.let { KeyValue("Reviewed", OwnerFormat.dateTime(it, zone)) }
                    e.reviewNote?.takeIf { it.isNotBlank() }?.let { KeyValue(ExceptionReviewText.NOTE, it) }
                    e.jobId?.takeIf { session.features.jobs }?.let { id ->
                        ButtonRow(ExceptionReviewText.OPEN_JOB) { onOpen(OwnerDestination.Job(id.toString())) }
                    }
                }
            }
            if (e.evidence.isNotEmpty()) item {
                SectionCard("Evidence") { e.evidence.toSortedMap().forEach { (k, v) -> KeyValue(OwnerFormat.humanize(k), AlertText.evidence(v)) } }
            }
            if (e.status == "OPEN") item {
                SectionCard("Decision") {
                    val gate = session.can(OwnerAction.REVIEW_EXCEPTION, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        BlockedNote(gate.reason)
                    } else {
                        Button(
                            { outcome = null; note = ""; reviewing = true },
                            enabled = !busy, modifier = Modifier.testTag("review-exception-${e.id}"), shape = RoundedCornerShape(8.dp),
                        ) { Text(ExceptionReviewText.REVIEW) }
                        error?.let {
                            Text(
                                it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("exception-error").semantics { liveRegion = LiveRegionMode.Assertive },
                            )
                        }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
        val target = vm.exception(page)
        if (reviewing && target != null) {
            ReviewDialog(
                target, outcome, note,
                onOutcome = { outcome = it }, onNote = { note = it.take(ExceptionReviewText.NOTE_MAX) },
                onDismiss = { reviewing = false },
                onSubmit = { reviewing = false; vm.review(outcome, note) },
            )
        }
    }
}

/** The web's review dialog: outcome (two options), the required review note, "Record review". */
@Composable
private fun ReviewDialog(
    e: ExceptionDto,
    outcome: String?,
    note: String,
    onOutcome: (String) -> Unit,
    onNote: (String) -> Unit,
    onDismiss: () -> Unit,
    onSubmit: () -> Unit,
) {
    var touched by rememberSaveable { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(ExceptionReviewText.dialogTitle(e)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(ExceptionReviewText.EXPLANATION, style = AssetaType.subheadline, color = palette.secondaryText)
                Text(ExceptionReviewText.OUTCOME, style = MaterialTheme.typography.labelLarge)
                Column(Modifier.selectableGroup()) {
                    ExceptionReviewText.OUTCOMES.forEach { (value, label) ->
                        Row(
                            Modifier.fillMaxWidth().selectable(selected = outcome == value, role = Role.RadioButton) { onOutcome(value) }
                                .testTag("outcome-$value"),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(selected = outcome == value, onClick = null)
                            Text(label, style = AssetaType.subheadline, modifier = Modifier.weight(1f))
                        }
                    }
                }
                if (touched && outcome == null) {
                    Text(ExceptionReviewText.CHOOSE_OUTCOME, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }
                val noteError = ExceptionReviewText.noteError(note).takeIf { touched || note.isNotEmpty() }
                OutlinedTextField(
                    note, { touched = true; onNote(it) }, Modifier.fillMaxWidth().testTag("review-note"),
                    label = { Text(ExceptionReviewText.NOTE) }, minLines = 3, isError = noteError != null,
                    supportingText = noteError?.let { msg -> { Text(msg) } },
                )
            }
        },
        confirmButton = {
            TextButton({ if (ExceptionReviewText.canReview(outcome, note)) onSubmit() else touched = true }) {
                Text(ExceptionReviewText.RECORD_REVIEW)
            }
        },
        dismissButton = { TextButton(onDismiss) { Text(ExceptionReviewText.CANCEL) } },
    )
}
