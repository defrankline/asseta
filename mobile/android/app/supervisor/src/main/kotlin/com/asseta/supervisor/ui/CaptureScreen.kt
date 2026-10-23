package com.asseta.supervisor.ui

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.OcrStep
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.supervisor.capture.CameraCapture
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.capture.PermissionRationale
import com.asseta.supervisor.capture.hasAllPermissions
import com.asseta.supervisor.capture.hasAnyPermission
import java.util.Locale

/**
 * Meter reading capture. The mode (AUTOMATIC camera + on-device OCR, or MANUAL entry) is set by the policy snapshot and
 * cannot be changed here; a fresh GPS attempt is made for every capture.
 */
@Composable
fun CaptureScreen(vm: CaptureViewModel, onDone: () -> Unit, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var cameraGranted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var cameraOpen by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        if (context.hasAnyPermission(GpsLocator.PERMISSIONS)) vm.onLocationDecision(true)
    }
    LaunchedEffect(ui.saved) { if (ui.saved) onDone() }
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        when {
            ui.loading -> CircularProgressIndicator()
            ui.blocked != null -> NoticeCard("Not available", ui.blocked!!, isError = true)
            else -> {
                Section(null, footer = "Set by your company's capture rules (${ui.policyStamp}).") {
                    LabeledRow("Machine", ui.machineLabel)
                    LabeledRow("Method", if (ui.mode == CaptureMode.AUTOMATIC) "Camera + automatic reading" else "Manual entry")
                }
                val openCamera = { cameraOpen = true }
                if (ui.photoRequired || ui.mode == CaptureMode.MANUAL) {
                    Section(if (ui.photoRequired) "Meter photo (required)" else "Meter photo (optional)") {
                        ui.photo?.let { photo ->
                            val preview = remember(photo) { MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)?.asImageBitmap() }
                            preview?.let { Image(it, "Meter photo", Modifier.fillMaxWidth().heightIn(max = 220.dp), contentScale = ContentScale.Fit) }
                        }
                        val final = ui.mode == CaptureMode.AUTOMATIC && (ui.ocrStep == OcrStep.CONFIRM || ui.ocrStep == OcrStep.MANUAL_FALLBACK)
                        when {
                            ui.ocrBusy -> Busy("Reading the meter on this phone…")
                            cameraOpen && !cameraGranted -> PermissionRationale(
                                title = "Camera",
                                rationale = "A photo of the hour meter is kept as evidence" +
                                    (if (ui.mode == CaptureMode.AUTOMATIC) " and the reading is recognized on this phone." else ".") +
                                    " Photos stay encrypted on this phone until uploaded.",
                                permissions = arrayOf(Manifest.permission.CAMERA),
                                onResult = { cameraGranted = it; if (!it) cameraOpen = false },
                            )
                            cameraOpen -> CameraCapture(
                                buttonLabel = if (ui.photo == null) "Take photo" else "Retake photo",
                                onCaptured = { vm.onPhoto(it); cameraOpen = false },
                                onError = { vm.onPhotoError(it); cameraOpen = false },
                            )
                            !final -> OutlinedButton(onClick = openCamera) { Text(if (ui.photo == null) "Take photo" else "Retake photo") }
                        }
                        if (ui.ocrStep == OcrStep.RECAPTURE && !ui.ocrBusy) {
                            Text("The reading could not be recognized reliably. Retake the photo (${ui.recapturesLeft} more after this).",
                                color = WarningColor)
                        }
                    }
                }
                if (ui.readingEditable) ReadingSection(ui, vm, onRetake = openCamera, cameraOpen = cameraOpen)
                GpsSection(ui, onDecision = vm::onLocationDecision, onRetry = vm::attemptGps)
                val issues = ui.issues
                if (issues.isNotEmpty() && (ui.photo != null || ui.readingText.isNotEmpty())) {
                    Section(null) { issues.forEach { Text(it, color = WarningColor) } }
                }
                Button(onClick = vm::save, enabled = !ui.saving && !ui.ocrBusy && issues.isEmpty(), modifier = Modifier.fillMaxWidth()) {
                    Text(if (ui.saving) "Saving…" else "Save")
                }
            }
        }
    }
    NotSavedAlert(ui.error, vm::clearError)
}

@Composable
private fun ReadingSection(ui: CaptureUi, vm: CaptureViewModel, onRetake: () -> Unit, cameraOpen: Boolean) {
    Section("Reading (hours)") {
        val ocr = ui.ocr
        if (ui.ocrStep == OcrStep.CONFIRM && ocr?.value != null) {
            LabeledRow("Recognized", ocr.value!!)
            LabeledRow("Confidence", "${Math.round(ocr.confidence * 100)}%")
            Text("Check the value against the meter. Correct it if it is wrong.", style = MaterialTheme.typography.bodySmall)
        }
        if (ui.ocrStep == OcrStep.MANUAL_FALLBACK) {
            Text("Automatic reading was not reliable after several photos. Type the reading; the photo is kept as evidence.",
                style = MaterialTheme.typography.bodySmall, color = WarningColor)
        }
        OutlinedTextField(
            value = ui.readingText,
            onValueChange = vm::onReadingChanged,
            placeholder = { Text(if (ui.decimals == 0) "e.g. 4521" else "e.g. 4521." + "0".repeat(ui.decimals)) },
            keyboardOptions = KeyboardOptions(keyboardType = if (ui.decimals == 0) KeyboardType.Number else KeyboardType.Decimal),
            textStyle = MaterialTheme.typography.titleLarge,
            singleLine = true,
            enabled = !ui.saving,
            modifier = Modifier.fillMaxWidth(),
        )
        if (ui.isManualCorrection) {
            Text("You changed the recognized value. It will be sent as a manual correction.", style = MaterialTheme.typography.bodySmall)
        }
        if (ui.mode == CaptureMode.AUTOMATIC && ui.ocrStep == OcrStep.CONFIRM && !cameraOpen) {
            OutlinedButton(onClick = onRetake) { Text("Retake photo") }
        }
    }
}

@Composable
private fun GpsSection(ui: CaptureUi, onDecision: (Boolean) -> Unit, onRetry: () -> Unit) {
    if (!ui.locationDecided) {
        PermissionRationale(
            title = "Location for this reading",
            rationale = "Each reading records a fresh location fix while you use the app (never in the background). " +
                "If you decline, the reading is saved without location and flagged for review.",
            permissions = GpsLocator.PERMISSIONS,
            onResult = onDecision,
            declineLabel = "Continue without location",
        )
        return
    }
    Section("GPS") {
        GpsResult(ui.gps, ui.gpsBusy, savableNote = true)
        if (!ui.gpsBusy && !ui.saving) OutlinedButton(onClick = onRetry) { Text("Try location again") }
    }
}

/** Fresh-fix progress, the fix (coordinates + accuracy) or the honest failure (shared with the expense form). */
@Composable
fun GpsResult(gps: GpsOutcome?, busy: Boolean, savableNote: Boolean) {
    when {
        busy || gps == null -> Busy("Getting a fresh location fix…")
        gps is GpsOutcome.Fix -> {
            LabeledRow("Location", String.format(Locale.ROOT, "%.5f, %.5f", gps.latitude, gps.longitude))
            LabeledRow("Accuracy", String.format(Locale.ROOT, "± %.0f m", gps.accuracyM ?: 0.0))
        }
        else -> {
            Text(FieldTexts.gpsFailure(gps), color = WarningColor)
            if (savableNote) {
                Text("The reading can still be saved; it is recorded with this location result for review.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun Busy(text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
        Text(text)
    }
}
