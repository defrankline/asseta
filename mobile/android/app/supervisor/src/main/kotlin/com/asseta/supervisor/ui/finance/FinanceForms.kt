package com.asseta.supervisor.ui.finance

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.finance.ExpenseRules
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CameraCapture
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.capture.PermissionRationale
import com.asseta.supervisor.capture.hasAllPermissions
import com.asseta.supervisor.ui.FormSaveAction
import com.asseta.supervisor.ui.GpsResult
import com.asseta.supervisor.ui.Section
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Save state shared by every finance form. */
data class SaveState(val saving: Boolean = false, val saved: Boolean = false, val messages: List<String> = emptyList())

fun SaveState.after(result: FinanceResult): SaveState = when (result) {
    is FinanceResult.Saved, FinanceResult.AlreadySaved -> SaveState(saved = true)
    is FinanceResult.Blocked -> copy(saving = false, messages = listOf(result.message))
    is FinanceResult.Invalid -> copy(saving = false, messages = result.messages)
}

/** Refusal messages + the Save button; a saved form closes (like the iOS sheets). */
@Composable
fun SaveSection(state: SaveState, onSave: () -> Unit, onDone: () -> Unit, enabled: Boolean = true) {
    LaunchedEffect(state.saved) { if (state.saved) onDone() }
    state.messages.forEach { Text(it, color = palette.offline) }
    FormSaveAction(enabled = enabled, saving = state.saving || state.saved, onSave = onSave)
}

@Composable
fun DecimalField(label: String, value: String, onChange: (String) -> Unit, enabled: Boolean, modifier: Modifier = Modifier) {
    OutlinedTextField(
        value = value,
        onValueChange = { text -> onChange(text.filter { it.isDigit() || it == '.' || it == ',' }) },
        label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        singleLine = true,
        enabled = enabled,
        modifier = modifier.fillMaxWidth(),
    )
}

@Composable
fun TextInput(label: String, value: String, onChange: (String) -> Unit, enabled: Boolean, singleLine: Boolean = true) {
    OutlinedTextField(value, onChange, label = { Text(label) }, singleLine = singleLine, enabled = enabled, modifier = Modifier.fillMaxWidth())
}

/** Exclusive choice among a few fixed (non-backend) values. */
@Composable
fun <T> ChoiceChips(options: List<T>, selected: T?, label: (T) -> String, onSelect: (T) -> Unit, enabled: Boolean) {
    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { option ->
            FilterChip(selected = option == selected, onClick = { onSelect(option) }, enabled = enabled, label = { Text(label(option)) })
        }
    }
}

/** Two or three fixed values side by side (the iOS segmented picker). */
@Composable
fun <T> SegmentedChoice(options: List<T>, selected: T?, label: (T) -> String, onSelect: (T) -> Unit, enabled: Boolean) {
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        options.forEachIndexed { index, option ->
            SegmentedButton(
                selected = option == selected, onClick = { onSelect(option) }, enabled = enabled,
                shape = SegmentedButtonDefaults.itemShape(index, options.size),
            ) { Text(label(option)) }
        }
    }
}

/** Receipt photo through the in-app camera; the original JPEG goes to the encrypted evidence store on save. */
@Composable
fun ReceiptSection(
    photos: List<CapturedPhoto>,
    required: Boolean,
    onAdd: (CapturedPhoto) -> Unit,
    onRemove: (Int) -> Unit,
    onError: (String) -> Unit,
    enabled: Boolean,
) {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var open by remember { mutableStateOf(false) }
    Section(
        if (required) "Receipt (required)" else "Receipt (optional)",
        footer = "Stored encrypted on this phone and uploaded before the expense is sent.",
    ) {
        photos.forEachIndexed { index, photo ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                val preview = remember(photo) { MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)?.asImageBitmap() }
                preview?.let { img ->
                    Image(img, "Receipt photo ${index + 1}", Modifier.weight(1f).heightIn(max = 120.dp), contentScale = ContentScale.Fit,
                        alignment = Alignment.CenterStart)
                }
                if (enabled) TextButton(onClick = { onRemove(index) }) { Text("Remove", color = palette.offline) }
            }
        }
        when {
            !enabled -> Unit
            open && !granted -> PermissionRationale(
                title = "Camera",
                rationale = "A photo of the receipt is kept as evidence for the office. It stays encrypted on this phone until uploaded.",
                permissions = arrayOf(Manifest.permission.CAMERA),
                onResult = { granted = it; if (!it) open = false },
            )
            open -> CameraCapture(
                buttonLabel = "Photograph receipt",
                onCaptured = { onAdd(it); open = false },
                onError = { onError(it); open = false },
            )
            // Up to ten receipt photos per expense (as on iOS); the button is hidden at the limit.
            photos.size < ExpenseRules.MAX_RECEIPTS -> OutlinedButton(onClick = { open = true }) {
                Text(if (photos.isEmpty()) "Photograph receipt" else "Add another receipt photo")
            }
        }
    }
}

/** A fresh, foreground GPS attempt for one record (same honesty rules as meter captures; never a cached location). */
class GpsAttempt(private val field: FieldGraph, private val scope: CoroutineScope) {
    data class State(val decided: Boolean = false, val busy: Boolean = false, val outcome: GpsOutcome? = null)

    private val _state = MutableStateFlow(State())
    val state: StateFlow<State> = _state.asStateFlow()
    private var job: Job? = null

    fun onDecision(granted: Boolean) {
        _state.update { it.copy(decided = true) }
        if (granted) attempt() else _state.update { it.copy(outcome = GpsOutcome.PermissionDenied) }
    }

    fun attempt() {
        if (job?.isActive == true) return
        job = scope.launch {
            _state.update { it.copy(busy = true, outcome = null) }
            val outcome = field.gps.attempt()
            _state.update { it.copy(busy = false, outcome = outcome) }
        }
    }

    suspend fun awaitIdle() { job?.join() }
}

@Composable
fun GpsSection(state: GpsAttempt.State, required: Boolean, onDecision: (Boolean) -> Unit, onRetry: () -> Unit, enabled: Boolean) {
    if (!state.decided) {
        PermissionRationale(
            title = "Location for this expense",
            rationale = "Each expense records a fresh location fix while you use the app (never in the background)." +
                if (required) " Your company requires a GPS fix for expenses." else "",
            permissions = GpsLocator.PERMISSIONS,
            onResult = onDecision,
            declineLabel = "Continue without location",
        )
        return
    }
    Section(if (required) "GPS (required)" else "GPS") {
        GpsResult(state.outcome, state.busy, savableNote = false)
        if (enabled && !state.busy) OutlinedButton(onClick = onRetry) { Text("Try location again") }
    }
}
