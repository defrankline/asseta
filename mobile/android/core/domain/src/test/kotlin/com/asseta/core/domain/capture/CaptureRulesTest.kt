package com.asseta.core.domain.capture

import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.MeterCapturePolicy
import com.asseta.core.domain.policy.ReadingKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class CaptureRulesTest {
    private fun policy(opening: CaptureMode = CaptureMode.AUTOMATIC, closing: CaptureMode = CaptureMode.MANUAL, photo: Boolean = true) =
        MeterCapturePolicy(opening, closing, photo, 0.85, 2, true, "SOFT")

    private fun ocr(value: String?, confidence: Double) = OcrReading(value, confidence, value ?: "", "OK", emptySet())

    private fun draft(
        mode: CaptureMode = CaptureMode.AUTOMATIC, kind: ReadingKind = ReadingKind.OPENING, reading: String = "1234.5",
        photo: Boolean = true, attempts: Int = 1, latest: OcrReading? = ocr("1234.5", 0.95), gps: Boolean = true,
    ) = CaptureDraft(kind, mode, reading, photo, attempts, latest, gps)

    @Test
    fun readingValidationUsesMeterDecimalPlaces() {
        assertEquals(ReadingInput.Valid("1234.5"), ReadingValidator.validate("1234.5", 1))
        assertEquals(ReadingInput.Valid("1234.0"), ReadingValidator.validate(" 1234 ", 1))
        assertEquals(ReadingInput.Valid("1234.50"), ReadingValidator.validate("1234,5", 2))
        assertEquals(ReadingInput.Invalid(ReadingError.TOO_MANY_DECIMALS), ReadingValidator.validate("1234.56", 1))
        assertEquals(ReadingInput.Invalid(ReadingError.NOT_A_NUMBER), ReadingValidator.validate("-5", 1))
        assertEquals(ReadingInput.Invalid(ReadingError.NOT_A_NUMBER), ReadingValidator.validate("1e5", 1))
        assertEquals(ReadingInput.Invalid(ReadingError.EMPTY), ReadingValidator.validate("", 1))
        assertEquals(ReadingInput.Invalid(ReadingError.TOO_LARGE), ReadingValidator.validate("1234567890123456", 0))
    }

    @Test
    fun automaticModeRequiresPhotoAndOcr() {
        assertEquals(emptyList<CaptureViolation>(), CaptureValidator.validate(draft(), policy(), 1))
        assertEquals(listOf(CaptureViolation.PHOTO_REQUIRED, CaptureViolation.OCR_REQUIRED),
            CaptureValidator.validate(draft(photo = false, attempts = 0, latest = null), policy(), 1))
    }

    @Test
    fun lowConfidenceForcesRecaptureUntilAttemptsExhausted() {
        val p = policy() // max_recapture_attempts = 2 -> up to 3 photos
        val low = ocr("1234.5", 0.4)
        assertEquals(OcrStep.RECAPTURE, OcrFlow.next(1, low, p))
        assertEquals(OcrStep.RECAPTURE, OcrFlow.next(2, low, p))
        assertEquals(OcrStep.MANUAL_FALLBACK, OcrFlow.next(3, low, p))
        assertEquals(OcrStep.CONFIRM, OcrFlow.next(1, ocr("1.0", 0.85), p))
        assertEquals(OcrStep.RECAPTURE, OcrFlow.next(1, ocr(null, 0.99), p))
        assertEquals(listOf(CaptureViolation.RECAPTURE_REQUIRED), CaptureValidator.validate(draft(attempts = 2, latest = low), p, 1))
        // After exhausting recaptures, manual entry is allowed while photo + OCR evidence are kept.
        assertEquals(emptyList<CaptureViolation>(), CaptureValidator.validate(draft(attempts = 3, latest = low, reading = "1299.0"), p, 1))
    }

    @Test
    fun manualModeRespectsPhotoPolicyAndRequiredMode() {
        assertEquals(emptyList<CaptureViolation>(),
            CaptureValidator.validate(draft(CaptureMode.MANUAL, ReadingKind.CLOSING, photo = false, attempts = 0, latest = null), policy(photo = false), 1))
        assertEquals(listOf(CaptureViolation.PHOTO_REQUIRED),
            CaptureValidator.validate(draft(CaptureMode.MANUAL, ReadingKind.CLOSING, photo = false, attempts = 0, latest = null), policy(photo = true), 1))
        assertTrue(CaptureViolation.MODE_NOT_ALLOWED in
            CaptureValidator.validate(draft(CaptureMode.MANUAL, ReadingKind.OPENING), policy(), 1))
        assertTrue(CaptureViolation.READING_INVALID in CaptureValidator.validate(draft(reading = "12.34"), policy(), 1))
        assertTrue(CaptureViolation.GPS_NOT_ATTEMPTED in CaptureValidator.validate(draft(gps = false), policy(), 1))
    }

    @Test
    fun readingKindFollowsEffectiveJobState() {
        assertTrue(JobStateRules.readingAllowed(ReadingKind.OPENING, JobStatus.APPROVED))
        assertFalse(JobStateRules.readingAllowed(ReadingKind.CLOSING, JobStatus.APPROVED))
        val afterLocalStart = JobStateRules.effectiveStatus(JobStatus.APPROVED, localStartPending = true, localCompletePending = false)
        assertEquals(JobStatus.IN_PROGRESS, afterLocalStart)
        assertTrue(JobStateRules.readingAllowed(ReadingKind.CLOSING, afterLocalStart))
        assertEquals(JobStatus.CANCELLED, JobStateRules.effectiveStatus(JobStatus.CANCELLED, true, true))
        assertFalse(JobStateRules.canLogWork("SOMETHING_NEW"))
    }

    @Test
    fun gpsOutcomesNeverCarryInventedCoordinates() {
        val start = Instant.parse("2026-10-21T10:00:00Z")
        assertTrue(GpsOutcome.acceptFix(start.plusSeconds(3), start))
        assertFalse(GpsOutcome.acceptFix(start.minusSeconds(60), start)) // cached/old location is not a fresh fix
        assertEquals("PERMISSION_DENIED", GpsOutcome.PermissionDenied.status)
        assertEquals("FIX", GpsOutcome.Fix(1.0, 2.0, 5.0, start, "fused").status)
    }
}
