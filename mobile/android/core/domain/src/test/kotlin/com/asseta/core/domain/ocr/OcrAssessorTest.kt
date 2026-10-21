package com.asseta.core.domain.ocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OcrAssessorTest {
    private fun page(vararg words: OcrWord) = OcrPage(listOf(OcrLine(words.toList())))

    @Test
    fun confidentReadWithExplicitSeparator() {
        val r = OcrAssessor().assess(page(OcrWord("12:45", 0.4f, null), OcrWord("46646.9", 0.97f, null), OcrWord("HRS", 0.9f, null)), 1)
        assertEquals("46646.9", r.value)
        assertEquals(0.97, r.confidence, 1e-6) // clock and unit words do not lower the reading confidence
        assertTrue(r.isConfident(0.85))
    }

    @Test
    fun mergedDrumReadIsNeverConfident() {
        val r = OcrAssessor().assess(page(OcrWord("202641", 0.99f, Box(0, 0, 600, 100))), 1)
        assertEquals("202641.0", r.value)
        assertTrue(OcrReading.FLAG_NO_DECIMAL_SEPARATOR in r.flags)
        assertFalse(r.isConfident(0.85))
        assertEquals(OcrAssessor.MERGED_READ_CONFIDENCE_CAP, r.confidence, 1e-9)
    }

    @Test
    fun redTenthsCellIsSplitOff() {
        // Six equal cells 0..600; only the last (500..600) is red.
        val detector = RedCellDetector { box -> box.left >= 500 }
        val r = OcrAssessor(detector).assess(page(OcrWord("202641", 0.95f, Box(0, 0, 600, 100))), 1)
        assertEquals("20264.1", r.value)
        assertTrue(OcrReading.FLAG_DRUM_TENTHS_SPLIT in r.flags)
        assertTrue(r.isConfident(0.85))
        assertEquals("202641", r.rawText) // raw evidence is unchanged
    }

    @Test
    fun allRedDisplayIsNotTreatedAsDrum() {
        val r = OcrAssessor { true }.assess(page(OcrWord("202641", 0.95f, Box(0, 0, 600, 100))), 1)
        assertEquals("202641.0", r.value)
        assertFalse(r.isConfident(0.85))
    }

    @Test
    fun integerMeterDoesNotNeedSeparatorAndUnreadableHasZeroConfidence() {
        assertTrue(OcrAssessor().assess(page(OcrWord("4521", 0.9f, null)), 0).isConfident(0.85))
        val none = OcrAssessor().assess(page(OcrWord("HOURS", 0.9f, null)), 1)
        assertNull(none.value)
        assertEquals(0.0, none.confidence, 0.0)
        val missing = OcrAssessor().assess(page(OcrWord("4521.7", null, null)), 1)
        assertTrue(OcrReading.FLAG_NO_ENGINE_CONFIDENCE in missing.flags)
        assertFalse(missing.isConfident(0.1))
    }

    @Test
    fun pixelDetectorFindsRedBackground() {
        val w = 200
        val h = 50
        val px = IntArray(w * h) { i -> if (i % w >= 100) 0xFFB01818.toInt() else 0xFF0A0A0A.toInt() }
        val source = object : PixelSource {
            override val width = w
            override val height = h
            override fun argb(x: Int, y: Int) = px[y * w + x]
        }
        val detector = PixelRedCellDetector(source)
        assertTrue(detector.isRedCell(Box(120, 10, 180, 40)))
        assertFalse(detector.isRedCell(Box(20, 10, 80, 40)))
    }

    @Test
    fun drumWheelsSplitIntoGroupsAreReassembledByColour() {
        // ML Kit output "2026 4 1": six cells 0..600 across three words; only the last cell (500..600) is red.
        val words = arrayOf(
            OcrWord("2026", 0.9f, Box(0, 0, 400, 100)), OcrWord("4", 0.9f, Box(400, 0, 500, 100)), OcrWord("1", 0.9f, Box(500, 0, 600, 100)),
        )
        val r = OcrAssessor { box -> box.left >= 500 }.assess(page(*words), 1)
        assertEquals("20264.1", r.value)
        assertTrue(r.isConfident(0.85))
        // Same output without colour evidence: the spec drum rule would pair "2026"+"4"; never confident.
        val blind = OcrAssessor().assess(page(*words), 1)
        assertEquals("2026.4", blind.value)
        assertTrue(OcrReading.FLAG_FRAGMENTED_DIGITS in blind.flags)
        assertFalse(blind.isConfident(0.85))
    }

    @Test
    fun consensusRewardsAgreementAndPenalisesDisagreement() {
        fun r(v: String?, c: Double) = OcrReading(v, c, "", "OK", emptySet())
        val agree = OcrConsensus.combine(listOf(r("3190.6", 0.83), r("3190.60", 0.91)))
        assertEquals(0.91, agree.confidence, 1e-9)
        assertTrue(OcrConsensus.FLAG_VARIANTS_AGREE in agree.flags)
        val disagree = OcrConsensus.combine(listOf(r("3190.6", 0.95), r("3196.0", 0.9)))
        assertEquals("3190.6", disagree.value)
        assertFalse(disagree.isConfident(0.85))
        assertEquals(0.8, OcrConsensus.combine(listOf(r(null, 0.0), r("1.0", 0.8))).confidence, 1e-9)
        assertNull(OcrConsensus.combine(listOf(r(null, 0.0), r(null, 0.0))).value)
    }
}
