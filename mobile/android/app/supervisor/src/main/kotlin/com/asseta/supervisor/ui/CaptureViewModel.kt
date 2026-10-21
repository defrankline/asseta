package com.asseta.supervisor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.capture.CaptureViolation
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.JobStateRules
import com.asseta.core.domain.capture.OcrFlow
import com.asseta.core.domain.capture.OcrStep
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.MeterCapturePolicy
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.sync.usecase.CaptureRequest
import com.asseta.core.sync.usecase.CaptureResult
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.MeterOcr
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.UUID

data class CaptureUi(
    val kind: ReadingKind,
    val loading: Boolean = true,
    val blocked: String? = null,
    val machineLabel: String = "",
    val decimals: Int = 0,
    val mode: CaptureMode? = null,
    val policy: MeterCapturePolicy? = null,
    val policyStamp: String? = null,
    val photo: CapturedPhoto? = null,
    val attempts: Int = 0,
    val ocrBusy: Boolean = false,
    val ocr: OcrReading? = null,
    val ocrStep: OcrStep? = null,
    val readingText: String = "",
    val gps: GpsOutcome? = null,
    val gpsBusy: Boolean = false,
    val gpsAttemptAtMs: Long? = null,
    val locationDecided: Boolean = false,
    val violations: List<CaptureViolation> = emptyList(),
    val saving: Boolean = false,
    val message: String? = null,
    val saved: Boolean = false,
) {
    /** The reading field is editable for MANUAL, after a confident OCR read (correction) or after recaptures ran out. */
    val readingEditable: Boolean
        get() = mode == CaptureMode.MANUAL || ocrStep == OcrStep.CONFIRM || ocrStep == OcrStep.MANUAL_FALLBACK

    val isManualCorrection: Boolean get() = ocr?.value != null && readingText.isNotBlank() && readingText != ocr.value

    val photoRequired: Boolean get() = mode == CaptureMode.AUTOMATIC || policy?.manualPhotoRequired == true
}

/**
 * One capture session. The capture id is generated once here (idempotency key); every rule decision is delegated to
 * the domain (OcrFlow, CaptureValidator via the use case) so the screen never re-implements business rules.
 */
class CaptureViewModel(
    private val field: FieldGraph,
    private val tenantId: String,
    private val jobId: String,
    kind: ReadingKind,
) : ViewModel() {
    private val captureId = UUID.randomUUID().toString()
    private val _ui = MutableStateFlow(CaptureUi(kind))
    val ui: StateFlow<CaptureUi> = _ui.asStateFlow()
    private var gpsJob: Job? = null

    init {
        viewModelScope.launch { load() }
    }

    private suspend fun load() {
        val job = field.repository.job(jobId) ?: return _ui.update { it.copy(loading = false, blocked = "Job not found.") }
        val machine = field.repository.machine(job.machineId)
            ?: return _ui.update { it.copy(loading = false, blocked = "Machine details missing. Connect to refresh rules.") }
        val state = field.repository.fieldState(tenantId, job)
        if (!JobStateRules.readingAllowed(_ui.value.kind, state.effectiveStatus)) {
            return _ui.update { it.copy(loading = false, blocked = "This reading is not allowed while the job is ${state.effectiveStatus}.") }
        }
        when (val decision = field.repository.capturePolicy(tenantId, machine.id)) {
            is CapturePolicyDecision.Blocked -> _ui.update { it.copy(loading = false, blocked = decision.message) }
            is CapturePolicyDecision.Allowed -> _ui.update {
                it.copy(
                    loading = false,
                    machineLabel = "${machine.assetCode} · ${machine.name}",
                    decimals = machine.meterDecimalPlaces,
                    mode = decision.policy.requiredMode(it.kind),
                    policy = decision.policy,
                    policyStamp = decision.snapshot.versionStamp,
                )
            }
        }
    }

    /** Location permission answered (or declined): attempt a fresh fix, or record PERMISSION_DENIED honestly. */
    fun onLocationDecision(granted: Boolean) {
        _ui.update { it.copy(locationDecided = true) }
        if (granted) attemptGps() else _ui.update { it.copy(gps = GpsOutcome.PermissionDenied, gpsAttemptAtMs = field.clock.nowMs()) }
    }

    fun attemptGps() {
        if (gpsJob?.isActive == true) return
        gpsJob = viewModelScope.launch {
            _ui.update { it.copy(gpsBusy = true) }
            val startedAt = field.clock.nowMs()
            val outcome = field.gps.attempt()
            _ui.update { it.copy(gpsBusy = false, gps = outcome, gpsAttemptAtMs = startedAt) }
        }
    }

    fun onPhoto(photo: CapturedPhoto) {
        val current = _ui.value
        val attempts = current.attempts + 1
        _ui.update { it.copy(photo = photo, attempts = attempts, message = null, violations = emptyList()) }
        refreshGpsIfStale(photo.takenAtMs)
        if (current.mode != CaptureMode.AUTOMATIC) return
        val policy = current.policy ?: return
        viewModelScope.launch {
            _ui.update { it.copy(ocrBusy = true) }
            val reading = withContext(Dispatchers.Default) {
                val bitmap = MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)
                if (bitmap == null) null else runCatching { field.ocr.read(bitmap, current.decimals, policy.minOcrConfidence) }.getOrNull()
            } ?: OcrReading(null, 0.0, "", "OCR_FAILED", emptySet())
            val step = OcrFlow.next(attempts, reading, policy)
            _ui.update {
                it.copy(
                    ocrBusy = false, ocr = reading, ocrStep = step,
                    readingText = if (step == OcrStep.RECAPTURE) "" else reading.value.orEmpty(),
                )
            }
        }
    }

    fun onPhotoError(message: String) = _ui.update { it.copy(message = message) }

    fun onReadingChanged(text: String) = _ui.update { it.copy(readingText = text.filter { c -> c.isDigit() || c == '.' || c == ',' }, violations = emptyList()) }

    fun save() {
        val state = _ui.value
        if (state.saving || state.saved || state.mode == null) return
        viewModelScope.launch {
            _ui.update { it.copy(saving = true, message = null) }
            val capturedAt = state.photo?.takenAtMs ?: field.clock.nowMs()
            refreshGpsIfStale(capturedAt)
            gpsJob?.join()
            val latest = _ui.value
            val result = field.captureReading(
                CaptureRequest(
                    tenantId = tenantId, jobId = jobId, captureId = captureId, kind = latest.kind,
                    mode = latest.mode!!, readingText = latest.readingText, photoJpeg = latest.photo?.jpeg,
                    ocrAttempts = latest.attempts.takeIf { latest.mode == CaptureMode.AUTOMATIC } ?: 0,
                    latestOcr = latest.ocr, gps = latest.gps, capturedAtMs = capturedAt,
                ),
            )
            _ui.update {
                when (result) {
                    is CaptureResult.Saved, CaptureResult.AlreadySaved -> it.copy(saving = false, saved = true,
                        message = "Reading saved on this device. It will be sent when you are online.")
                    is CaptureResult.Blocked -> it.copy(saving = false, message = result.message)
                    is CaptureResult.Invalid -> it.copy(saving = false, violations = result.violations)
                }
            }
        }
    }

    /** Every capture needs its own fresh attempt; re-attempt if the last one is older than [MAX_GPS_AGE_MS]. */
    private fun refreshGpsIfStale(captureAtMs: Long) {
        val s = _ui.value
        if (!s.locationDecided || s.gps == GpsOutcome.PermissionDenied && !field.gps.hasPermission()) return
        val last = s.gpsAttemptAtMs
        if (s.gps == null || last == null || captureAtMs - last > MAX_GPS_AGE_MS) attemptGps()
    }

    private companion object {
        const val MAX_GPS_AGE_MS = 90_000L
    }
}
