package com.asseta.supervisor.ui.accountability

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.model.owner.NonRevenueActivityDto
import com.asseta.core.model.owner.RevenueReasonDto
import com.asseta.core.sync.data.NonRevenueResult
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.FieldTexts
import com.asseta.supervisor.ui.FormSaveAction
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.NoticeCard
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SearchablePickerField
import com.asseta.supervisor.ui.finance.TextInput
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.math.RoundingMode
import java.time.OffsetDateTime

/** Tone of a non-revenue status line. */
enum class NonRevenueTone { WARNING, ACCENT, LIVE }

/**
 * Wording and rules of non-revenue time on the job's work log (DEC-031 R1; keys `field.nonrev.*`, same on iOS).
 * Pure, unit-tested.
 */
object NonRevenueText {
    const val EXPLAIN = "Explain"
    const val TITLE = "Explain non-revenue time"
    const val ENTRY = "Work log entry"
    const val REASON = "Reason"
    const val CHOOSE_REASON = "Choose a reason"
    const val REASONS_EMPTY = "Your company has no revenue reasons yet. Ask the office."
    const val NOTE = "Note (at least 5 characters)"
    const val SEND = "Send"
    const val FOOTER = "This time counts as revenue until someone else approves it. Needs a connection."
    const val SENT = "Sent. Someone else will approve it."
    const val OFFLINE = "Explaining needs a connection."
    const val NOTE_MIN = 5

    fun status(wire: String): String = when (wire) {
        "NONE" -> "Counted as revenue until explained"
        "PROPOSED" -> "Explained · waiting for approval"
        "APPROVED" -> "Approved as non-revenue time"
        "REJECTED" -> "Not approved · counted as revenue"
        else -> wire.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    fun tone(wire: String): NonRevenueTone = when (wire) {
        "PROPOSED" -> NonRevenueTone.ACCENT
        "APPROVED" -> NonRevenueTone.LIVE
        else -> NonRevenueTone.WARNING
    }

    /** "Explain" is offered for time nobody explained yet, or whose explanation was not approved. */
    fun canExplain(wire: String): Boolean = wire == "NONE" || wire == "REJECTED"

    /** The refusal in plain words ([fallback]: the server message). */
    fun error(code: String?, fallback: String): String = when (code) {
        "NON_REVENUE_PENDING" -> "This time is already waiting for approval."
        "NON_REVENUE_APPROVAL_NOT_REQUIRED" -> "Your company does not need approval for this time."
        "REVENUE_RECONCILIATION_DISABLED" -> "Your company has switched off revenue checks."
        "REASON_INACTIVE" -> "This reason is no longer in use. Choose another."
        else -> fallback
    }

    fun hours(raw: String): String = raw.toBigDecimalOrNull()?.setScale(2, RoundingMode.HALF_EVEN)?.stripTrailingZeros()
        ?.let { if (it.scale() < 0) it.setScale(0) else it }?.toPlainString() ?: raw

    /** "{type} · {start} → {end} ({hours} h)". */
    fun entryLine(type: String, start: String, end: String, hours: String) = "$type · $start → $end (${hours(hours)} h)"

    fun noteValid(note: String): Boolean = note.trim().length >= NOTE_MIN

    /** The server's activities of a job keyed by activity id (the work log matches its server entries by id). */
    fun byActivity(list: List<NonRevenueActivityDto>?): Map<String, NonRevenueActivityDto> = list.orEmpty().associateBy { it.activityId }
}

/** The explain form of one non-revenue entry (online only). */
class ExplainNonRevenueViewModel(private val field: FieldGraph, val activity: NonRevenueActivityDto) : ViewModel() {
    private val _reasons = MutableStateFlow<List<RevenueReasonDto>?>(null)
    val reasons: StateFlow<List<RevenueReasonDto>?> = _reasons.asStateFlow()
    val reasonId = MutableStateFlow<String?>(null)
    val note = MutableStateFlow("")
    private val _sending = MutableStateFlow(false)
    val sending: StateFlow<Boolean> = _sending.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _sent = MutableStateFlow(false)
    val sent: StateFlow<Boolean> = _sent.asStateFlow()

    fun loadReasons() {
        if (_reasons.value != null) return
        viewModelScope.launch { _reasons.value = field.accountability.revenueReasons() }
    }

    fun send() {
        val reason = reasonId.value ?: return
        if (_sending.value || !NonRevenueText.noteValid(note.value)) return
        _sending.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = field.accountability.explainNonRevenue(activity.activityId, reason, note.value)) {
                is NonRevenueResult.Sent -> _sent.value = true
                is NonRevenueResult.Refused -> _error.value = NonRevenueText.error(r.code, r.message)
            }
            _sending.value = false
        }
    }
}

private fun localTime(raw: String): String =
    runCatching { LocalTime.formatTime(OffsetDateTime.parse(raw).toInstant().toEpochMilli()) }.getOrDefault(raw)

@Composable
fun ExplainNonRevenueScreen(vm: ExplainNonRevenueViewModel, online: Boolean, onDone: () -> Unit) {
    val reasons by vm.reasons.collectAsStateWithLifecycle()
    val reasonId by vm.reasonId.collectAsStateWithLifecycle()
    val note by vm.note.collectAsStateWithLifecycle()
    val sending by vm.sending.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val sent by vm.sent.collectAsStateWithLifecycle()
    LaunchedEffect(online) { if (online) vm.loadReasons() }
    LaunchedEffect(sent) { if (sent) onDone() }
    val a = vm.activity
    FormColumn {
        Section(NonRevenueText.ENTRY) {
            Text(NonRevenueText.entryLine(FieldTexts.activityType(a.activityType), localTime(a.startedAt), localTime(a.endedAt), a.hours))
            a.note?.takeIf { it.isNotBlank() }?.let { Text(it, color = palette.secondaryText) }
        }
        if (!online) {
            NoticeCard(NonRevenueText.TITLE, NonRevenueText.OFFLINE, isError = true)
            return@FormColumn
        }
        Section(NonRevenueText.REASON, footer = NonRevenueText.FOOTER) {
            val list = reasons
            if (list != null && list.isEmpty()) Text(NonRevenueText.REASONS_EMPTY, color = palette.secondaryText)
            SearchablePickerField(
                NonRevenueText.CHOOSE_REASON, list.orEmpty().map { PickerOption(it.id, it.name, it.description) }, reasonId,
                { vm.reasonId.value = it }, emptyText = NonRevenueText.REASONS_EMPTY, enabled = !sending,
            )
            TextInput(NonRevenueText.NOTE, note, { vm.note.value = it.take(2000) }, !sending, singleLine = false)
        }
        error?.let { Text(it, color = palette.offline) }
        FormSaveAction(
            enabled = reasonId != null && NonRevenueText.noteValid(note) && !sending,
            saving = sending, label = NonRevenueText.SEND, onSave = vm::send,
        )
    }
}

/** Colour of a status line. */
@Composable
fun nonRevenueColor(tone: NonRevenueTone): Color = when (tone) {
    NonRevenueTone.WARNING -> palette.warning
    NonRevenueTone.ACCENT -> palette.accent
    NonRevenueTone.LIVE -> palette.live
}
