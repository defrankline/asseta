package com.asseta.owner.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.CompanyClosureRequestDto
import com.asseta.core.model.owner.CompanyClosureStatusDto
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

/** Company closure wording (docs/requirements/accountability-mobile-strings.md "Company closure"; same as iOS). */
object ClosureTexts {
    const val TITLE = "Company closure"
    const val BANNER_ACTION = "View closure request"
    const val STATUS = "Status"
    const val ASKED_BY = "Asked by"
    const val ASKED_ON = "Asked on"
    const val DELETION_DATE = "Deletion date"
    const val REASON = "Reason"
    const val CANCELLED_BY = "Cancelled by"
    const val CANCEL_REASON = "Cancel reason"
    const val UNKNOWN = "Unknown"
    const val NONE = "No closure has been requested for this company."
    const val FOOTER = "Closing a company is started on the web. Until the deletion date, anyone who may close the company can cancel it."
    const val CANCEL_ACTION = "Cancel closure"
    const val CANCEL_TITLE = "Cancel the closure?"
    const val CANCEL_REASON_LABEL = "Reason (required)"
    const val CANCEL_KEEP = "Keep it"
    const val REASON_TOO_SHORT = "Enter a reason (at least 3 characters)."
    const val OFFLINE = "Connect to the internet to cancel the closure."
    const val CANCELLED = "Closure cancelled. The company is back to normal."

    fun status(raw: String): String = when (raw) {
        "REQUESTED" -> "Requested"
        "IN_PROGRESS" -> "Deletion in progress"
        "CANCELLED" -> "Cancelled"
        "COMPLETED" -> "Completed"
        else -> OwnerFormat.humanize(raw)
    }
}

/** Closure rules shared with iOS: only a REQUESTED closure can be cancelled, with a reason of 3+ characters. */
object ClosurePresentation {
    const val MIN_REASON = 3

    fun canCancel(request: CompanyClosureRequestDto?): Boolean = request?.status == "REQUESTED"

    fun reasonValid(reason: String): Boolean = reason.trim().length >= MIN_REASON
}

class CompanyClosureViewModel(private val data: OwnerData) : SnapshotViewModel<CompanyClosureStatusDto>({ data.companyClosure() }) {
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    /** Cancels the closure; [onCancelled] refreshes `/me` so the read-only banner goes away. */
    fun cancel(reason: String, online: Boolean, onCancelled: () -> Unit = {}) {
        if (_busy.value) return
        if (!online) { _error.value = ClosureTexts.OFFLINE; return }
        if (!ClosurePresentation.reasonValid(reason)) { _error.value = ClosureTexts.REASON_TOO_SHORT; return }
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.cancelCompanyClosure(reason)) {
                is ActionResult.Done -> {
                    replaceData { it.copy(request = r.value) }
                    _message.value = ClosureTexts.CANCELLED
                    onCancelled()
                }
                is ActionResult.Refused -> _error.value = r.serverMessage ?: r.error.message
            }
            _busy.value = false
        }
    }
}

@Composable
fun CompanyClosureScreen(vm: CompanyClosureViewModel, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val actions = LocalSessionActions.current
    var asking by rememberSaveable { mutableStateOf(false) }
    var reason by rememberSaveable { mutableStateOf("") }
    val zone = ZoneId.systemDefault()
    SnapshotScaffold(state, vm::refresh) { status ->
        val request = status.request
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(status.companyName, footer = ClosureTexts.FOOTER) {
                    if (request == null) {
                        FootNote(ClosureTexts.NONE)
                    } else {
                        KeyValue(ClosureTexts.STATUS, ClosureTexts.status(request.status))
                        KeyValue(ClosureTexts.ASKED_BY, request.requestedByName ?: ClosureTexts.UNKNOWN)
                        KeyValue(ClosureTexts.ASKED_ON, OwnerFormat.date(request.requestedAt, zone))
                        KeyValue(ClosureTexts.DELETION_DATE, OwnerFormat.date(request.scheduledFor, zone))
                        if (request.reason.isNotBlank()) KeyValue(ClosureTexts.REASON, request.reason)
                        request.cancelledByName?.let { KeyValue(ClosureTexts.CANCELLED_BY, it) }
                        request.cancelReason?.let { KeyValue(ClosureTexts.CANCEL_REASON, it) }
                    }
                    message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText) }
                    if (!asking) error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    if (ClosurePresentation.canCancel(request)) {
                        if (!online) FootNote(ClosureTexts.OFFLINE)
                        ButtonRow(ClosureTexts.CANCEL_ACTION, Modifier.testTag("closure-cancel"), enabled = online && !busy, destructive = true) { asking = true }
                    }
                }
            }
        }
    }
    if (asking) {
        AlertDialog(
            onDismissRequest = { asking = false },
            title = { Text(ClosureTexts.CANCEL_TITLE) },
            text = {
                Column {
                    OutlinedTextField(reason, { reason = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text(ClosureTexts.CANCEL_REASON_LABEL) }, minLines = 2)
                    error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !busy && ClosurePresentation.reasonValid(reason),
                    onClick = { vm.cancel(reason, online) { asking = false; actions.refreshProfile() } },
                ) { Text(ClosureTexts.CANCEL_ACTION, color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton({ asking = false }) { Text(ClosureTexts.CANCEL_KEEP) } },
        )
    }
}
