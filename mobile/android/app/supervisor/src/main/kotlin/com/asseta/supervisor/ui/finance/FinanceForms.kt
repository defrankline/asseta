package com.asseta.supervisor.ui.finance

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CameraCapture
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.capture.PermissionRationale
import com.asseta.supervisor.capture.hasAllPermissions
import com.asseta.supervisor.ui.NoticeCard
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Save state shared by every finance form. */
data class SaveState(val saving: Boolean = false, val saved: Boolean = false, val messages: List<String> = emptyList())

fun SaveState.after(result: FinanceResult, savedText: String): SaveState = when (result) {
    is FinanceResult.Saved, FinanceResult.AlreadySaved -> SaveState(saved = true, messages = listOf(savedText))
    is FinanceResult.Blocked -> copy(saving = false, messages = listOf(result.message))
    is FinanceResult.Invalid -> copy(saving = false, messages = result.messages)
}

const val NOT_VERIFIED_NOTE = "Saved on this device and queued for sync. It is not verified by the office until it is synced and confirmed."

/** Messages + the save button (or "Done" once saved). */
@Composable
fun SaveSection(state: SaveState, saveLabel: String, onSave: () -> Unit, onDone: () -> Unit, enabled: Boolean = true) {
    if (state.saved) {
        NoticeCard("Saved", state.messages.joinToString("\n"))
        Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Done") }
    } else {
        state.messages.forEach { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = onSave, enabled = enabled && !state.saving, modifier = Modifier.fillMaxWidth()) {
            Text(if (state.saving) "Saving…" else saveLabel)
        }
    }
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
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        options.forEach { option ->
            FilterChip(selected = option == selected, onClick = { onSelect(option) }, enabled = enabled, label = { Text(label(option)) })
        }
    }
}

/** Receipt photo through the in-app camera; the original JPEG goes to the encrypted evidence store on save. */
@Composable
fun ReceiptSection(photo: CapturedPhoto?, required: Boolean, reason: String?, onPhoto: (CapturedPhoto) -> Unit, onError: (String) -> Unit, enabled: Boolean) {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var open by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Receipt" + if (required) " (required)" else " (optional)", style = MaterialTheme.typography.titleSmall)
            reason?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            photo?.let {
                val preview = remember(it) { MeterOcr.decodeForOcr(it.jpeg, it.rotationDegrees)?.asImageBitmap() }
                preview?.let { img -> Image(img, "Receipt photo", Modifier.fillMaxWidth().heightIn(max = 220.dp), contentScale = ContentScale.Fit) }
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
                    buttonLabel = "Take receipt photo",
                    onCaptured = { onPhoto(it); open = false },
                    onError = { onError(it); open = false },
                )
                else -> OutlinedButton(onClick = { open = true }) { Text(if (photo == null) "Photograph receipt" else "Retake receipt") }
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
            _state.update { it.copy(busy = true) }
            val outcome = field.gps.attempt()
            _state.update { it.copy(busy = false, outcome = outcome) }
        }
    }

    suspend fun awaitIdle() { job?.join() }
}

@Composable
fun GpsCard(state: GpsAttempt.State, requirement: String?, onDecision: (Boolean) -> Unit, onRetry: () -> Unit, enabled: Boolean) {
    if (!state.decided) {
        PermissionRationale(
            title = "Location for this expense",
            rationale = "Each expense records a fresh location fix while you use the app (never in the background)." +
                (requirement?.let { " $it" } ?: ""),
            permissions = GpsLocator.PERMISSIONS,
            onResult = onDecision,
            declineLabel = "Continue without location",
        )
        return
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Location", style = MaterialTheme.typography.titleSmall)
            requirement?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            when (val gps = state.outcome) {
                null -> if (state.busy) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CircularProgressIndicator(Modifier.heightIn(max = 20.dp)); Text("Getting a fresh fix (up to 20 s)…")
                }
                is GpsOutcome.Fix -> Text("Location fixed (±${gps.accuracyM?.let { Math.round(it).toString() } ?: "?"} m)")
                else -> Text("No location: ${gps.status.lowercase().replace('_', ' ')}", color = MaterialTheme.colorScheme.error)
            }
            if (enabled && !state.busy && state.outcome != GpsOutcome.PermissionDenied) {
                OutlinedButton(onClick = onRetry) { Text(if (state.outcome == null) "Get location" else "Try location again") }
            }
        }
    }
}
