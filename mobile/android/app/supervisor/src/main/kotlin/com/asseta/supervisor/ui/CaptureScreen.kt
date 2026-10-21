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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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

/** Hour-meter capture: required mode from the policy snapshot, camera + on-device OCR or manual entry, fresh GPS. */
@Composable
fun CaptureScreen(vm: CaptureViewModel, onDone: () -> Unit, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var cameraGranted by remember { mutableStateOf(context.hasAllPermissions(arrayOf(Manifest.permission.CAMERA))) }
    var cameraOpen by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        if (context.hasAnyPermission(GpsLocator.PERMISSIONS)) vm.onLocationDecision(true)
    }
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("${ui.kind.name.lowercase().replaceFirstChar { it.uppercase() }} reading", style = MaterialTheme.typography.headlineSmall)
        when {
            ui.loading -> CircularProgressIndicator()
            ui.blocked != null -> NoticeCard("Capture blocked", ui.blocked!!, isError = true)
            else -> {
                Text(ui.machineLabel, style = MaterialTheme.typography.titleMedium)
                Text(modeLine(ui), style = MaterialTheme.typography.bodyMedium)

                GpsSection(ui, onDecision = vm::onLocationDecision, onRetry = vm::attemptGps)

                if (!ui.photoRequired && ui.photo == null && !cameraOpen && !ui.saved) {
                    OutlinedButton(onClick = { cameraOpen = true }) { Text("Add a photo (optional)") }
                }
                if (ui.photoRequired || cameraOpen || ui.photo != null) {
                    if (!cameraGranted) {
                        PermissionRationale(
                            title = "Camera",
                            rationale = "A photo of the hour meter is kept as evidence" +
                                (if (ui.mode == CaptureMode.AUTOMATIC) " and the reading is recognised on this device." else ".") +
                                " Photos stay encrypted on this phone until uploaded.",
                            permissions = arrayOf(Manifest.permission.CAMERA),
                            onResult = { cameraGranted = it },
                        )
                    } else if (cameraOpen || (ui.photo == null && ui.photoRequired)) {
                        CameraCapture(
                            buttonLabel = if (ui.attempts == 0) "Take photo" else "Retake photo",
                            onCaptured = { vm.onPhoto(it); cameraOpen = false },
                            onError = vm::onPhotoError,
                        )
                    }
                    ui.photo?.let { photo ->
                        val preview = remember(photo) { MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)?.asImageBitmap() }
                        preview?.let { Image(it, "Meter photo", Modifier.fillMaxWidth().heightIn(max = 220.dp), contentScale = ContentScale.Fit) }
                        if (!cameraOpen && !ui.saved) OutlinedButton(onClick = { cameraOpen = true }) { Text("Retake photo") }
                    }
                }
                OcrSection(ui)
                if (ui.readingEditable) {
                    OutlinedTextField(
                        value = ui.readingText,
                        onValueChange = vm::onReadingChanged,
                        label = { Text("Reading (${ui.decimals} decimal place${if (ui.decimals == 1) "" else "s"})") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        singleLine = true,
                        enabled = !ui.saved,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (ui.isManualCorrection) {
                        Text("You changed the recognised value. The photo and recognised text are kept and the change is flagged for review.",
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
                ui.violations.forEach { Text(it.message, color = MaterialTheme.colorScheme.error) }
                ui.message?.let { NoticeCard(if (ui.saved) "Saved" else "Note", it, isError = !ui.saved) }
                if (ui.saved) {
                    Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Back to job") }
                } else {
                    Button(onClick = vm::save, enabled = !ui.saving && !ui.ocrBusy && ui.readingEditable && ui.locationDecided,
                        modifier = Modifier.fillMaxWidth()) {
                        Text(if (ui.saving) "Saving…" else "Save reading")
                    }
                }
            }
        }
    }
}

private fun modeLine(ui: CaptureUi): String = when (ui.mode) {
    CaptureMode.AUTOMATIC -> "Required by your company: photo + automatic recognition (rules ${ui.policyStamp})."
    CaptureMode.MANUAL -> "Required by your company: manual entry" +
        (if (ui.policy?.manualPhotoRequired == true) " with a photo" else "") + " (rules ${ui.policyStamp})."
    null -> ""
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
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Location", style = MaterialTheme.typography.titleSmall)
            when {
                ui.gpsBusy -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CircularProgressIndicator(Modifier.heightIn(max = 20.dp)); Text("Getting a fresh fix (up to 20 s)…")
                }
                ui.gps is GpsOutcome.Fix -> {
                    val fix = ui.gps
                    Text(GpsOutcome.describe(fix))
                    Text("%.5f, %.5f · %s".format(java.util.Locale.ROOT, fix.latitude, fix.longitude, fix.provider ?: "fused"),
                        style = MaterialTheme.typography.bodySmall)
                }
                ui.gps != null -> Text(GpsOutcome.describe(ui.gps), color = MaterialTheme.colorScheme.error)
            }
            if (!ui.gpsBusy && ui.gps !is GpsOutcome.Fix && ui.gps != GpsOutcome.PermissionDenied && !ui.saved) {
                OutlinedButton(onClick = onRetry) { Text("Try location again") }
            }
        }
    }
}

@Composable
private fun OcrSection(ui: CaptureUi) {
    if (ui.mode != CaptureMode.AUTOMATIC) return
    if (ui.ocrBusy) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { CircularProgressIndicator(); Text("Recognising the reading…") }
        return
    }
    val ocr = ui.ocr ?: return
    val confidence = "${Math.round(ocr.confidence * 100)}%"
    val policy = ui.policy ?: return
    when (ui.ocrStep) {
        OcrStep.CONFIRM -> NoticeCard("Recognised ${ocr.value}", "Confidence $confidence. Check it against the meter and confirm, or correct it.")
        OcrStep.RECAPTURE -> NoticeCard(
            "Could not read the meter confidently",
            "Result: ${ocr.value ?: "none"} (confidence $confidence). Retake the photo: fill the frame with the meter and avoid glare. " +
                "Attempt ${ui.attempts} of ${policy.maxRecaptureAttempts + 1}.",
            isError = true,
        )
        OcrStep.MANUAL_FALLBACK -> NoticeCard(
            "Enter the reading manually",
            "Recognition stayed below the required confidence after ${ui.attempts} photos. The last photo and recognised text are kept as evidence.",
        )
        null -> Unit
    }
}

@Composable
fun NoticeCard(title: String, body: String, isError: Boolean = false) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            Text(body, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
