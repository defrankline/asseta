package com.asseta.core.domain.ocr

import com.asseta.core.domain.ocr.SyntheticMeter.Companion.rgb
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class GlyphSegmenterTest {
    @Test
    fun lcdRowIsSegmentedWithGeometricDecimalPoint() {
        val meter = SyntheticMeter().apply { drawSegments("71691.6") }
        val seg = GlyphSegmenter.segment(meter.image())
        val row = seg.rows.first()
        assertEquals(6, row.glyphs.size)
        assertEquals(4, row.dotAfter)
        assertFalse(row.ambiguousDots)
        assertNull(row.redTenths)
        assertEquals("716916".toList(), SevenSegmentDecoder.decode(row, seg))
    }

    @Test
    fun brightSegmentsOnDarkBackgroundAreInk() {
        val meter = SyntheticMeter(background = rgb(20, 18, 10)).apply { drawSegments("2834.5", ink = rgb(255, 176, 40)) }
        val seg = GlyphSegmenter.segment(meter.image())
        assertEquals("28345".toList(), SevenSegmentDecoder.decode(seg.rows.first(), seg))
        assertEquals(3, seg.rows.first().dotAfter)
    }

    @Test
    fun twoDotsMakeTheDecimalPositionAmbiguous() {
        val meter = SyntheticMeter().apply { drawSegments("12.34.5") }
        val row = GlyphSegmenter.segment(meter.image()).rows.first()
        assertTrue(row.ambiguousDots)
        assertNull(row.dotAfter)
    }

    @Test
    fun redTenthsWheelIsDetectedOnlyAtTheRightEnd() {
        val meter = SyntheticMeter(width = 480, background = rgb(18, 18, 18))
        meter.drawSegments("202641", gap = 34, ink = rgb(200, 200, 200), cellColor = { i -> if (i == 5) rgb(110, 12, 12) else null })
        val row = GlyphSegmenter.segment(meter.image()).rows.first()
        assertEquals(6, row.glyphs.size)
        assertEquals(5, row.redTenths)

        val allRed = SyntheticMeter(width = 480, background = rgb(110, 12, 12))
        allRed.drawSegments("202641", gap = 34, ink = rgb(230, 230, 230))
        assertNull(GlyphSegmenter.segment(allRed.image()).rows.first().redTenths)
    }

    @Test
    fun noiseSpecksAreNotGlyphs() {
        val meter = SyntheticMeter().apply { drawSegments("5309.2") }
        val random = java.util.Random(7)
        repeat(400) { meter.pixels[random.nextInt(meter.pixels.size)] = rgb(0, 0, 0) }
        val seg = GlyphSegmenter.segment(meter.image())
        assertEquals("53092".toList(), SevenSegmentDecoder.decode(seg.rows.first(), seg))
    }

    @Test
    fun tiltedRowIsMeasuredAndStraightened() {
        val meter = SyntheticMeter(height = 200).apply { drawSegments("63257.6", top = 70) }
        val tilted = meter.image().rotated(-6.0) // counter-clockwise by -6 deg: descends to the right
        val skew = GlyphSegmenter.skewDegrees(GlyphSegmenter.segment(tilted).rows.first())
        assertTrue("skew $skew", abs(skew - 6.0) < 1.5)
        val straightened = GlyphSegmenter.segmentDeskewed(tilted)
        val row = straightened.rows.first()
        assertTrue(abs(GlyphSegmenter.skewDegrees(row)) < 1.5)
        assertEquals(6, row.glyphs.size)
        assertEquals(4, row.dotAfter)
    }

    @Test
    fun rotationKeepsSizeAndFillsCornersWithBackground() {
        val image = SyntheticMeter().image()
        val rotated = image.rotated(10.0)
        assertEquals(image.width, rotated.width)
        assertEquals(image.argb[0], rotated.argb[0])
    }

    @Test
    fun proportionalFontGivesNoSegmentOpinion() {
        // Diagonal strokes leave the segment probes half-covered: uncertain -> no opinion rather than a guess.
        val meter = SyntheticMeter()
        for (d in 0 until 4) for (y in 0 until 60) meter.fill(40 + d * 50 + y / 3, 50 + y, 9, 1, rgb(0, 0, 0))
        val seg = GlyphSegmenter.segment(meter.image())
        val row = seg.rows.firstOrNull()
        assertNotNull(row)
        assertNull(SevenSegmentDecoder.decode(row!!, seg))
    }
}
