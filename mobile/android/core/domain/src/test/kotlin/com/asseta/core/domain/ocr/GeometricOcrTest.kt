package com.asseta.core.domain.ocr

import com.asseta.core.domain.ocr.GeometricOcr.SegmentOpinion
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GeometricOcrTest {
    private fun v(text: String) = text.toList()

    /** A proportional-font row (no segment-decoder opinion: empty mask) of [n] glyphs of the given widths. */
    private fun plainRow(widths: List<Int>, dotAfter: Int? = null, ambiguousDots: Boolean = false, top: Int = 10, h: Int = 50): Pair<GlyphRow, Segmentation> {
        var x = 10
        val glyphs = widths.map { w -> GlyphBox(x, top, x + w - 1, top + h - 1, w * h / 2).also { x += w + 10 } }
        val image = RgbImage(x + 20, top + h + 20, IntArray((x + 20) * (top + h + 20)))
        val row = GlyphRow(glyphs, dotAfter, ambiguousDots)
        return row to Segmentation(image, BooleanArray(image.argb.size), listOf(row))
    }

    private fun lcd(text: String): Pair<GlyphRow, Segmentation> {
        val seg = GlyphSegmenter.segment(SyntheticMeter().apply { drawSegments(text) }.image())
        return seg.rows.first() to seg
    }

    @Test
    fun assignRequiresOneCharacterPerGlyph() {
        assertEquals(v("847710H"), GeometricOcr.assign("8477 1.0h", 7))
        assertNull(GeometricOcr.assign("8477 1.0h", 6))
        assertNull(GeometricOcr.assign("", 3))
    }

    @Test
    fun composePlacesGeometricDotDrumSplitAndUnits() {
        val (row, _) = plainRow(List(7) { 30 }, dotAfter = 4)
        assertEquals("71691.6 H", GeometricOcr.compose(v("716916H"), row))
        val drum = GlyphRow(row.glyphs.take(6), redTenths = 5)
        assertEquals("20264 1", GeometricOcr.compose(v("202641"), drum))
        assertEquals("20264.1", MeterReadingParser.parse("20264 1", 1).value)
        assertNull(GeometricOcr.compose(v("12A345"), drum)) // digit run must be contiguous
        assertNull(GeometricOcr.compose(v("12-345"), drum)) // symbols are rejected
    }

    @Test
    fun unanimousLayoutsWithFullFrameAgreementAreConfident() {
        val (row, seg) = plainRow(listOf(15, 30, 30, 30, 30, 30, 30), dotAfter = 4) // a narrow `1` is plausible
        val read = GeometricOcr.readRow(row, seg, List(3) { v("159504H") }, 1)!!
        assertEquals(SegmentOpinion.ABSENT, read.segments)
        val r = GeometricOcr.combine(listOf(read), "Engine Hours\n15950.4h", 1)!!
        assertEquals("15950.4", r.value)
        assertEquals(GeometricOcr.UNANIMOUS + GeometricOcr.FULL_FRAME_BONUS, r.confidence, 1e-9)
        assertTrue(GeometricOcr.FLAG_FULL_FRAME_AGREES in r.flags)
    }

    @Test
    fun majorityAloneIsNotConfident() {
        val (row, seg) = plainRow(listOf(30, 30, 30, 30, 15, 30), dotAfter = 4)
        val read = GeometricOcr.readRow(row, seg, listOf(v("847710"), v("847710"), v("847716")), 1)!!
        val r = GeometricOcr.combine(listOf(read), "", 1)!!
        assertEquals("84771.0", r.value)
        assertEquals(GeometricOcr.MAJORITY, r.confidence, 1e-9)
        assertFalse(r.isConfident(0.85))
        val split = GeometricOcr.readRow(row, seg, listOf(v("847710"), v("847716"), v("847718")), 1)!!
        assertEquals(GeometricOcr.WEAK, GeometricOcr.combine(listOf(split), "", 1)!!.confidence, 1e-9)
    }

    @Test
    fun parserConfusionsDoNotSplitTheVote() {
        val (row, seg) = plainRow(List(6) { 30 }, dotAfter = 4)
        val read = GeometricOcr.readRow(row, seg, listOf(v("84771O"), v("847710"), v("847710")), 1)!!
        assertEquals(3, read.agreeing)
        assertEquals(v("OIL"), GeometricOcr.canonical(v("OIL"))) // no real digit: left alone
    }

    @Test
    fun segmentDecoderAgreementUpgradesAMajority() {
        val (row, seg) = lcd("50060.6")
        val read = GeometricOcr.readRow(row, seg, listOf(v("S00606"), v("500606"), v("500606")), 1)!!
        assertEquals(SegmentOpinion.AGREE, read.segments)
        assertEquals(3, read.agreeing)
        assertEquals(GeometricOcr.UNANIMOUS, GeometricOcr.combine(listOf(read), "", 1)!!.confidence, 1e-9)
    }

    @Test
    fun wideOneIsResolvedOnlyWithACorroboratingRecogniserRead() {
        val (row, seg) = lcd("71691.6")
        val votes = List(3) { v("116916") }
        assertTrue(GeometricOcr.needsCorroboration(row, seg, votes))

        val alone = GeometricOcr.combine(listOf(GeometricOcr.readRow(row, seg, votes, 1)!!), "", 1)!!
        assertEquals("11691.6", alone.value)
        assertEquals(GeometricOcr.CONFLICT_CAP, alone.confidence, 1e-9)
        assertTrue(GeometricOcr.FLAG_WIDE_ONE in alone.flags)

        val wrongWitness = GeometricOcr.readRow(row, seg, votes, 1, corroboration = listOf(v("716918")))!!
        assertEquals(SegmentOpinion.CONFLICT, wrongWitness.segments)

        val resolved = GeometricOcr.readRow(row, seg, votes, 1, corroboration = listOf(v("9169IL"), v("716916")))!!
        assertEquals(SegmentOpinion.RESOLVED, resolved.segments)
        val r = GeometricOcr.combine(listOf(resolved), "1169 L6\nh", 1)!!
        assertEquals("71691.6", r.value)
        assertEquals(GeometricOcr.UNANIMOUS, r.confidence, 1e-9)
    }

    @Test
    fun decoderDisagreementElsewhereCapsConfidence() {
        val (row, seg) = lcd("71691.6")
        assertFalse(GeometricOcr.needsCorroboration(row, seg, List(3) { v("716918") }))
        val read = GeometricOcr.readRow(row, seg, List(3) { v("716918") }, 1)!!
        assertEquals(SegmentOpinion.CONFLICT, read.segments)
        val r = GeometricOcr.combine(listOf(read), "", 1)!!
        assertEquals(GeometricOcr.CONFLICT_CAP, r.confidence, 1e-9)
        assertFalse(r.isConfident(0.85))
    }

    @Test
    fun plausibilityChecksCapUnanimousReads() {
        val (row, seg) = plainRow(List(6) { 30 }, dotAfter = 4)
        val read = GeometricOcr.readRow(row, seg, List(3) { v("632576") }, 1)!!
        val fullConflict = GeometricOcr.combine(listOf(read), "63251.6", 1)!!
        assertEquals(GeometricOcr.CONFLICT_CAP, fullConflict.confidence, 1e-9)
        assertTrue(GeometricOcr.FLAG_FULL_FRAME_CONFLICT in fullConflict.flags)

        val (other, otherSeg) = plainRow(List(6) { 30 }, dotAfter = 4, top = 100)
        val second = GeometricOcr.readRow(other, otherSeg, List(3) { v("111116") }, 1)!!
        val rows = GeometricOcr.combine(listOf(read, second), "", 1)!!
        assertEquals(GeometricOcr.AMBIGUOUS_CAP, rows.confidence, 1e-9)
        assertTrue(GeometricOcr.FLAG_ROWS_DISAGREE in rows.flags)

        val smallClock = GeometricOcr.readRow(plainRow(List(4) { 10 }, h = 20).first, otherSeg, List(3) { v("1245") }, 1)!!
        assertEquals(GeometricOcr.UNANIMOUS, GeometricOcr.combine(listOf(read, smallClock), "", 1)!!.confidence, 1e-9)

        val (dots, dotsSeg) = plainRow(List(6) { 30 }, ambiguousDots = true)
        val ambiguous = GeometricOcr.combine(listOf(GeometricOcr.readRow(dots, dotsSeg, List(3) { v("632576") }, 1)!!), "", 1)!!
        assertEquals(GeometricOcr.AMBIGUOUS_CAP, ambiguous.confidence, 1e-9)
    }

    @Test
    fun noGeometricValueFallsBackToACappedTextRead() {
        val (row, seg) = plainRow(List(3) { 30 })
        assertNull(GeometricOcr.readRow(row, seg, emptyList(), 1))
        assertNull(GeometricOcr.readRow(row, seg, List(3) { v("HOURS") }, 1)) // S is digit-like: not contiguous
        val noValue = GeometricOcr.readRow(row, seg, List(3) { v("HRS") }, 1)
        assertNotNull(noValue)
        assertNull(GeometricOcr.combine(listOfNotNull(noValue), "", 1))
        val text = OcrReading("4521.7", 0.99, "4521.7", "OK", emptySet())
        val capped = GeometricOcr.unconfirmed(text)
        assertEquals(GeometricOcr.UNCONFIRMED_CAP, capped.confidence, 1e-9)
        assertTrue(GeometricOcr.FLAG_NO_GEOMETRIC_READ in capped.flags)
    }

    @Test
    fun rendererLaysOutEveryGlyphWithDotAndShear() {
        val (row, seg) = lcd("71691.6")
        val upright = GlyphRenderer.render(row, seg, 64.0, 0.3)!!
        assertEquals(6, upright.glyphCount)
        assertTrue(upright.argb.any { it == 0xFF000000.toInt() })
        assertEquals(-1, upright.argb[0]) // white margin
        val italic = GlyphRenderer.render(row, seg, 64.0, 0.3, shear = 0.25)!!
        assertTrue(italic.width > upright.width)
        assertEquals(upright.height, italic.height)
    }
}
