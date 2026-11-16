package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.OcrStep
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.ReadingKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset

class FieldRulesTest {
    @Test
    fun captureIssuesUseTheIosWording() {
        val manual = CaptureUi(ReadingKind.DAILY, loading = false, decimals = 1, mode = CaptureMode.MANUAL)
        assertEquals(listOf("Enter the meter reading.", "A location attempt is required for every reading."), manual.issues)
        assertEquals(
            listOf("This meter shows at most 1 decimal place."),
            manual.copy(readingText = "12.34", gps = GpsOutcome.Timeout).issues,
        )
        assertEquals(listOf("This meter shows whole hours only."), manual.copy(decimals = 0, readingText = "1.5", gps = GpsOutcome.NoFix).issues)
        assertEquals(emptyList<String>(), manual.copy(readingText = "12.3", gps = GpsOutcome.PermissionDenied).issues)

        val automatic = CaptureUi(ReadingKind.DAILY, loading = false, decimals = 0, mode = CaptureMode.AUTOMATIC, gps = GpsOutcome.NoFix)
        assertTrue("A photo of the meter is required." in automatic.issues)
        val recapture = automatic.copy(readingText = "", ocrStep = OcrStep.RECAPTURE)
        assertTrue("The photo could not be read reliably. Take another photo." in recapture.issues)
    }

    @Test
    fun correctionIsComparedOnTheNormalizedReading() {
        val ui = CaptureUi(ReadingKind.DAILY, decimals = 1, mode = CaptureMode.AUTOMATIC,
            ocr = OcrReading("1234.5", 0.95, "1234.5", "OK", emptySet()), ocrStep = OcrStep.CONFIRM)
        assertFalse(ui.copy(readingText = "1234,5").isManualCorrection)
        assertTrue(ui.copy(readingText = "1243.5").isManualCorrection)
    }

    @Test
    fun dateTimeIsCombinedInTheDeviceZoneAndClamped() {
        val zone = ZoneId.of("Africa/Lusaka") // UTC+2
        val day = Instant.parse("2026-10-23T00:00:00Z").toEpochMilli()
        val combined = DateTimeRules.combine(day, 9, 30, zone)
        assertEquals(Instant.parse("2026-10-23T07:30:00Z").toEpochMilli(), combined)
        assertEquals(day, DateTimeRules.clamp(combined, null, day))
        assertEquals(combined, DateTimeRules.clamp(combined, day, null))
        assertEquals(2026, Instant.ofEpochMilli(combined).atZone(ZoneOffset.UTC).year)
    }
}
