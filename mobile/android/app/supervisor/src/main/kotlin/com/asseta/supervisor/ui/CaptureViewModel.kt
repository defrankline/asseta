package com.asseta.supervisor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.OcrFlow
import com.asseta.core.domain.capture.OcrStep
import com.asseta.core.domain.capture.ReadingError
import com.asseta.core.domain.capture.ReadingInput
import com.asseta.core.domain.capture.ReadingValidator
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.MeterCapturePolicy
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.accountability.AccountabilityMessages
import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.CaptureRequest
import com.asseta.core.sync.usecase.CaptureTarget
import com.asseta.core.sync.usecase.CaptureTargetRef
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
    val saving: Boolean = false,
    /** A refusal or failure to show in the "Not saved" alert. */
    val error: String? = null,
    val saved: Boolean = false,
    /** What the reading is for (job reading, daily reading, baseline or correction). */
    val target: CaptureTarget = CaptureTarget.Job,
    /** Baseline note / correction reason. */
    val extraText: String = "",
    /** The reading being corrected (correction only). */
    val correctionOf: String? = null,
) {
    /** The reading field is shown for MANUAL, after a confident OCR read (correction) or after recaptures ran out. */
    val readingEditable: Boolean
        get() = mode == CaptureMode.MANUAL || ocrStep == OcrStep.CONFIRM || ocrStep == OcrStep.MANUAL_FALLBACK

    /** The supervisor changed the recognized value (sent as a manual correction; OCR value and raw text are kept). */
    val isManualCorrection: Boolean
        get() {
            val value = ocr?.value ?: return false
            val reading = ReadingValidator.validate(readingText, decimals) as? ReadingInput.Valid ?: return false
            return reading.normalized != value
        }

    val photoRequired: Boolean get() = mode == CaptureMode.AUTOMATIC || policy?.manualPhotoRequired == true

    /** Recaptures left after the current one (shown with the recapture request). */
    val recapturesLeft: Int get() = ((policy?.maxRecaptureAttempts ?: 0) - attempts).coerceAtLeast(0)

    /** Everything that still blocks saving, worded like the iOS app (shown once a photo or reading exists). */
    val issues: List<String>
        get() = CaptureIssues.of(this)
}

object CaptureIssues {
    fun of(ui: CaptureUi): List<String> = buildList {
        when (val r = ReadingValidator.validate(ui.readingText, ui.decimals)) {
            is ReadingInput.Valid -> Unit
            is ReadingInput.Invalid -> add(reading(r.error, ui.decimals))
        }
        if (ui.photoRequired && ui.photo == null) add("A photo of the meter is required.")
        if (ui.mode == CaptureMode.AUTOMATIC) {
            when {
                ui.ocrStep == OcrStep.RECAPTURE -> add("The photo could not be read reliably. Take another photo.")
                ui.photo != null && ui.ocr == null && !ui.ocrBusy -> add("Take a photo so the reading can be recognized.")
            }
        }
        if (ui.gps == null) add("A location attempt is required for every reading.")
        if (ui.target is CaptureTarget.Correction && !AccountabilityRules.correctionReasonValid(ui.extraText)) {
            add(AccountabilityMessages.CORRECTION_REASON)
        }
    }

    fun reading(error: ReadingError, decimals: Int): String = when (error) {
        ReadingError.EMPTY -> "Enter the meter reading."
        ReadingError.NOT_A_NUMBER, ReadingError.TOO_LARGE -> "The reading must be a non-negative number."
        ReadingError.TOO_MANY_DECIMALS ->
            if (decimals == 0) "This meter shows whole hours only." else "This meter shows at most $decimals decimal place${if (decimals == 1) "" else "s"}."
    }
}

/**
 * One capture session. The capture id is generated once here (idempotency key); every rule decision is delegated to
 * the domain (OcrFlow, CaptureValidator via the use case) so the screen never re-implements business rules.
 */
class CaptureViewModel(
    private val field: FieldGraph,
    private val tenantId: String,
    private val jobId: String?,
    kind: ReadingKind,
    private val target: CaptureTarget = CaptureTarget.Job,
) : ViewModel() {
    private val captureId = UUID.randomUUID().toString()
    private val _ui = MutableStateFlow(CaptureUi(kind, target = target))
    val ui: StateFlow<CaptureUi> = _ui.asStateFlow()
    private var gpsJob: Job? = null

    init {
        viewModelScope.launch { load() }
    }

    private suspend fun load() {
        val (subject, refusal) = field.captureReading.subject(tenantId, CaptureTargetRef(jobId, _ui.value.kind, target))
        if (subject == null) {
            val which = if (_ui.value.kind == ReadingKind.OPENING) "Opening" else "Closing"
            val message = when {
                target != CaptureTarget.Job -> refusal
                refusal == CaptureMeterReading.JOB_GONE -> "It is no longer assigned to you on this device."
                refusal == CaptureMeterReading.MACHINE_DETAILS_MISSING -> "Machine details missing. Connect to refresh rules."
                else -> "$which reading is not allowed now."
            } ?: "Not available."
            return _ui.update { it.copy(loading = false, blocked = message) }
        }
        val machine = subject.machine
        val correctionOf = (target as? CaptureTarget.Correction)?.let { t -> field.inbox.readingValue(tenantId, t.readingId) }
        when (val decision = field.repository.capturePolicy(tenantId, machine.id)) {
            is CapturePolicyDecision.Blocked -> _ui.update { it.copy(loading = false, blocked = decision.message) }
            is CapturePolicyDecision.Allowed -> _ui.update {
                it.copy(
                    loading = false,
                    kind = subject.kind,
                    machineLabel = "${machine.assetCode} · ${machine.name}",
                    decimals = machine.meterDecimalPlaces,
                    mode = decision.policy.requiredMode(subject.kind),
                    policy = decision.policy,
                    policyStamp = decision.snapshot.versionStamp,
                    correctionOf = correctionOf,
                )
            }
        }
    }

    fun onExtraText(text: String) = _ui.update { it.copy(extraText = text.take(2000)) }

    /** Location permission answered (or declined): attempt a fresh fix, or record PERMISSION_DENIED honestly. */
    fun onLocationDecision(granted: Boolean) {
        _ui.update { it.copy(locationDecided = true) }
        if (granted) attemptGps() else _ui.update { it.copy(gps = GpsOutcome.PermissionDenied, gpsAttemptAtMs = field.clock.nowMs()) }
    }

    fun attemptGps() {
        if (gpsJob?.isActive == true) return
        gpsJob = viewModelScope.launch {
            _ui.update { it.copy(gpsBusy = true, gps = null) }
            val startedAt = field.clock.nowMs()
            val outcome = field.gps.attempt()
            _ui.update { it.copy(gpsBusy = false, gps = outcome, gpsAttemptAtMs = startedAt) }
        }
    }

    fun onPhoto(photo: CapturedPhoto) {
        val current = _ui.value
        val attempts = current.attempts + 1
        _ui.update { it.copy(photo = photo, attempts = attempts, error = null, ocr = null, ocrStep = null) }
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

    fun onPhotoError(message: String) = _ui.update { it.copy(error = "The photo could not be saved: $message") }

    fun clearError() = _ui.update { it.copy(error = null) }

    fun onReadingChanged(text: String) = _ui.update { it.copy(readingText = text.filter { c -> c.isDigit() || c == '.' || c == ',' }) }

    fun save() {
        val state = _ui.value
        if (state.saving || state.saved || state.mode == null || state.issues.isNotEmpty()) return
        viewModelScope.launch {
            _ui.update { it.copy(saving = true, error = null) }
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
                    target = when (val t = target) {
                        is CaptureTarget.Baseline -> t.copy(note = latest.extraText)
                        is CaptureTarget.Correction -> t.copy(reason = latest.extraText)
                        else -> t
                    },
                ),
            )
            _ui.update {
                when (result) {
                    is CaptureResult.Saved, CaptureResult.AlreadySaved -> it.copy(saving = false, saved = true)
                    is CaptureResult.Blocked -> it.copy(saving = false, error = result.message)
                    is CaptureResult.Invalid -> it.copy(saving = false, error = result.violations.joinToString("\n") { v -> v.message })
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
