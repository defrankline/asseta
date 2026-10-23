package com.asseta.core.domain.capture

import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.MeterCapturePolicy
import com.asseta.core.domain.policy.ReadingKind
import java.math.BigDecimal

/** Server job states (strings so an unknown future state never crashes the app; unknown => no field actions). */
object JobStatus {
    const val APPROVED = "APPROVED"
    const val IN_PROGRESS = "IN_PROGRESS"
    const val COMPLETED = "COMPLETED"
    const val CANCELLED = "CANCELLED"
}

/** Job state as the supervisor sees it offline: server state plus their own not-yet-rejected transitions. */
object JobStateRules {
    fun effectiveStatus(serverStatus: String, localStartPending: Boolean, localCompletePending: Boolean): String = when {
        serverStatus == JobStatus.CANCELLED -> serverStatus
        localCompletePending -> JobStatus.COMPLETED
        localStartPending && serverStatus == JobStatus.APPROVED -> JobStatus.IN_PROGRESS
        else -> serverStatus
    }

    /** OPENING only on an APPROVED job, CLOSING only on an IN_PROGRESS job (mirrors server READING_NOT_ALLOWED). */
    fun readingAllowed(kind: ReadingKind, effectiveStatus: String): Boolean = when (kind) {
        ReadingKind.OPENING -> effectiveStatus == JobStatus.APPROVED
        ReadingKind.CLOSING -> effectiveStatus == JobStatus.IN_PROGRESS
    }

    fun canLogWork(effectiveStatus: String): Boolean = effectiveStatus == JobStatus.APPROVED || effectiveStatus == JobStatus.IN_PROGRESS
}

sealed interface ReadingInput {
    data class Valid(val normalized: String) : ReadingInput
    data class Invalid(val error: ReadingError) : ReadingInput
}

enum class ReadingError(val message: String) {
    EMPTY("Enter the meter reading."),
    NOT_A_NUMBER("The reading must be a non-negative number."),
    TOO_MANY_DECIMALS("This meter shows fewer decimal places."),
    TOO_LARGE("The reading is too large."),
}

object ReadingValidator {
    private val PATTERN = Regex("^\\d+(\\.\\d+)?$")
    private const val MAX_DIGITS = 14 // server Reading: max_digits=14

    /** Accepts "," as decimal separator; returns the reading at exactly the meter's decimal places. */
    fun validate(raw: String, decimalPlaces: Int): ReadingInput {
        val text = raw.trim().replace(',', '.')
        if (text.isEmpty()) return ReadingInput.Invalid(ReadingError.EMPTY)
        if (!PATTERN.matches(text)) return ReadingInput.Invalid(ReadingError.NOT_A_NUMBER)
        val value = BigDecimal(text)
        if (value.scale() > decimalPlaces) return ReadingInput.Invalid(ReadingError.TOO_MANY_DECIMALS)
        val scaled = value.setScale(decimalPlaces)
        if (scaled.precision() > MAX_DIGITS) return ReadingInput.Invalid(ReadingError.TOO_LARGE)
        return ReadingInput.Valid(scaled.toPlainString())
    }
}

/** What the automatic (camera + OCR) flow should do after an attempt. */
enum class OcrStep { CONFIRM, RECAPTURE, MANUAL_FALLBACK }

object OcrFlow {
    /**
     * [attemptsMade] counts photos taken so far (>= 1). Low-confidence or unreadable results ask for a recapture until
     * `max_recapture_attempts` recaptures were used, then allow manual entry (photo and OCR output are kept).
     */
    fun next(attemptsMade: Int, reading: OcrReading, policy: MeterCapturePolicy): OcrStep = when {
        reading.isConfident(policy.minOcrConfidence) -> OcrStep.CONFIRM
        attemptsMade <= policy.maxRecaptureAttempts -> OcrStep.RECAPTURE
        else -> OcrStep.MANUAL_FALLBACK
    }
}

/** Everything the supervisor produced for one capture, before it is persisted. */
data class CaptureDraft(
    val kind: ReadingKind,
    val mode: CaptureMode,
    val readingText: String,
    val hasPhoto: Boolean,
    val ocrAttempts: Int,
    val latestOcr: OcrReading?,
    val gpsAttempted: Boolean,
)

enum class CaptureViolation(val message: String) {
    MODE_NOT_ALLOWED("Your company requires a different capture method for this reading."),
    PHOTO_REQUIRED("A photo of the meter is required."),
    OCR_REQUIRED("Take a photo so the reading can be recognized."),
    RECAPTURE_REQUIRED("The photo could not be read reliably. Take another photo."),
    READING_INVALID("The reading must be a non-negative number."),
    GPS_NOT_ATTEMPTED("A location attempt is required for every reading."),
}

object CaptureValidator {
    fun validate(draft: CaptureDraft, policy: MeterCapturePolicy, decimalPlaces: Int): List<CaptureViolation> = buildList {
        if (draft.mode != policy.requiredMode(draft.kind)) add(CaptureViolation.MODE_NOT_ALLOWED)
        when (draft.mode) {
            CaptureMode.AUTOMATIC -> {
                if (!draft.hasPhoto) add(CaptureViolation.PHOTO_REQUIRED)
                val ocr = draft.latestOcr
                if (draft.ocrAttempts < 1 || ocr == null) {
                    add(CaptureViolation.OCR_REQUIRED)
                } else if (OcrFlow.next(draft.ocrAttempts, ocr, policy) == OcrStep.RECAPTURE) {
                    add(CaptureViolation.RECAPTURE_REQUIRED)
                }
            }
            CaptureMode.MANUAL -> if (policy.manualPhotoRequired && !draft.hasPhoto) add(CaptureViolation.PHOTO_REQUIRED)
        }
        if (ReadingValidator.validate(draft.readingText, decimalPlaces) !is ReadingInput.Valid) add(CaptureViolation.READING_INVALID)
        if (!draft.gpsAttempted) add(CaptureViolation.GPS_NOT_ATTEMPTED)
    }
}
