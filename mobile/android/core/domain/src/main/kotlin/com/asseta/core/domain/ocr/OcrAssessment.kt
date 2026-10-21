package com.asseta.core.domain.ocr

/** Axis-aligned box in image pixels. */
data class Box(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top
}

/** One recognized word (ML Kit element) with optional per-character boxes (ML Kit symbols). */
data class OcrWord(val text: String, val confidence: Float?, val box: Box?, val symbolBoxes: List<Box> = emptyList())

data class OcrLine(val words: List<OcrWord>)

/** Engine-neutral recognizer output, so the assessment rules are JVM-testable and engine-independent. */
data class OcrPage(val lines: List<OcrLine>) {
    /** The text exactly as recognized (evidence; sent as `ocr_raw_text`). */
    val rawText: String get() = lines.joinToString("\n") { line -> line.words.joinToString(" ") { it.text } }
}

/**
 * Result shown to the supervisor for confirmation. [value] null => manual fallback. [confidence] is what the capture
 * policy's `min_ocr_confidence` is compared against; risky reads are capped below any sane threshold.
 */
data class OcrReading(
    val value: String?,
    val confidence: Double,
    val rawText: String,
    val parseReason: String,
    val flags: Set<String>,
) {
    fun isConfident(minConfidence: Double): Boolean = value != null && confidence >= minConfidence

    companion object {
        const val FLAG_DRUM_TENTHS_SPLIT = "DRUM_TENTHS_SPLIT"
        const val FLAG_NO_DECIMAL_SEPARATOR = "NO_DECIMAL_SEPARATOR"
        const val FLAG_NO_ENGINE_CONFIDENCE = "NO_ENGINE_CONFIDENCE"
        const val FLAG_FRAGMENTED_DIGITS = "FRAGMENTED_DIGITS"
    }
}

/**
 * Turns recognizer output into a reading using the shared parser, plus device-side safeguards for the documented
 * mechanical-drum risk (manifest `known_risks`): text OCR can merge the red tenths wheel into the integer
 * (20264.1 -> "202641") or split the wheels into arbitrary groups ("2026 4 1").
 *
 * 1. Geometry/colour: on a line, the run of all-digit words is treated as one counter; if its last character cell sits
 *    on a red wheel (and the cell before it does not), that character is the tenths drum and is split off before
 *    parsing, so the spec's drum rule yields the right value.
 * 2. Fallbacks (confidence capped at [MERGED_READ_CONFIDENCE_CAP], i.e. never "confident"): a reading for a meter with
 *    decimals that has neither an explicit separator nor a colour-confirmed drum split, and any page where the digits
 *    arrive as several separate groups without colour evidence (the parser would silently pick or pair groups).
 */
class OcrAssessor(private val redCellDetector: RedCellDetector? = null) {

    fun assess(page: OcrPage, decimalPlaces: Int): OcrReading {
        val flags = mutableSetOf<String>()
        val parseText = page.lines.joinToString("\n") { line ->
            val split = if (decimalPlaces >= 1) drumSplit(line) else null
            if (split != null) flags += OcrReading.FLAG_DRUM_TENTHS_SPLIT
            split ?: line.words.joinToString(" ") { it.text }
        }
        val parsed = MeterReadingParser.parse(parseText, decimalPlaces)
        val colourSplit = OcrReading.FLAG_DRUM_TENTHS_SPLIT in flags
        val engineConfidence = numericConfidence(page, weighted = colourSplit)
        if (engineConfidence == null) flags += OcrReading.FLAG_NO_ENGINE_CONFIDENCE
        var confidence = (engineConfidence ?: 0.0).coerceIn(0.0, 1.0)
        if (parsed.value == null) confidence = 0.0
        if (parsed.value != null && decimalPlaces >= 1 && !parsed.explicitSeparator && !colourSplit) {
            flags += OcrReading.FLAG_NO_DECIMAL_SEPARATOR
            confidence = minOf(confidence, MERGED_READ_CONFIDENCE_CAP)
        }
        if (parsed.value != null && !colourSplit && numericWords(page).size > 1) {
            flags += OcrReading.FLAG_FRAGMENTED_DIGITS
            confidence = minOf(confidence, MERGED_READ_CONFIDENCE_CAP)
        }
        return OcrReading(parsed.value, confidence, page.rawText.take(MAX_RAW_TEXT), parsed.reason, flags)
    }

    /** Returns the line rewritten as "<integer wheels> <tenths wheel>" when the last digit cell is a red wheel. */
    private fun drumSplit(line: OcrLine): String? {
        val detector = redCellDetector ?: return null
        val runs = mutableListOf<IntRange>()
        var start = -1
        line.words.forEachIndexed { i, w ->
            val digits = w.text.isNotEmpty() && w.text.all { it.isDigit() }
            if (digits && start < 0) start = i
            if (!digits && start >= 0) { runs += start until i; start = -1 }
        }
        if (start >= 0) runs += start until line.words.size
        val run = runs.filter { r -> r.sumOf { line.words[it].text.length } >= 4 }.maxByOrNull { r -> r.sumOf { line.words[it].text.length } }
            ?: return null
        val boxes = run.flatMap { i -> charBoxes(line.words[i]) ?: return null }
        if (boxes.size < 2 || !detector.isRedCell(boxes.last()) || detector.isRedCell(boxes[boxes.size - 2])) return null
        val digits = run.joinToString("") { line.words[it].text }
        val before = line.words.subList(0, run.first).map { it.text }
        val after = line.words.subList(run.last + 1, line.words.size).map { it.text }
        return (before + "${digits.dropLast(1)} ${digits.last()}" + after).joinToString(" ")
    }

    private fun charBoxes(word: OcrWord): List<Box>? =
        word.symbolBoxes.takeIf { it.size == word.text.length } ?: word.box?.let { evenSplit(it, word.text.length) }

    private fun numericWords(page: OcrPage): List<OcrWord> =
        page.lines.flatMap { it.words }.filter { w -> w.text.any { it.isDigit() } && !CLOCK.matches(w.text) }

    /**
     * Engine confidence over words that carry digits (clock times excluded): the lowest word confidence, which is
     * conservative by design; for a colour-confirmed drum, whose wheels are recognised as separate cells, the
     * character-weighted mean of the wheel words.
     */
    private fun numericConfidence(page: OcrPage, weighted: Boolean): Double? {
        val numeric = numericWords(page)
        if (numeric.isEmpty() || numeric.any { it.confidence == null }) return null
        if (!weighted) return numeric.minOf { it.confidence!!.toDouble() }
        return numeric.sumOf { it.confidence!!.toDouble() * it.text.length } / numeric.sumOf { it.text.length }
    }

    private fun evenSplit(box: Box, count: Int): List<Box> = (0 until count).map { i ->
        Box(box.left + box.width * i / count, box.top, box.left + box.width * (i + 1) / count, box.bottom)
    }

    companion object {
        const val MERGED_READ_CONFIDENCE_CAP = 0.5
        const val MAX_RAW_TEXT = 500
        private val CLOCK = Regex("^\\d{1,2}:\\d{2}(:\\d{2})?$")
    }
}

/**
 * Combines readings of the same photo from several image variants (original + enhanced). Agreement on the value is
 * extra evidence (highest confidence kept); disagreement is ambiguity (capped, never confident); a variant that found
 * nothing does not change the other's result.
 */
object OcrConsensus {
    const val FLAG_VARIANTS_AGREE = "VARIANTS_AGREE"
    const val FLAG_VARIANTS_DISAGREE = "VARIANTS_DISAGREE"

    fun combine(readings: List<OcrReading>): OcrReading {
        require(readings.isNotEmpty())
        val withValue = readings.filter { it.value != null }
        if (withValue.isEmpty()) return readings.first()
        val best = withValue.maxBy { it.confidence }
        val values = withValue.map { java.math.BigDecimal(it.value) }.distinctBy { it.stripTrailingZeros() }
        return when {
            withValue.size == 1 -> best
            values.size == 1 -> best.copy(flags = withValue.flatMap { it.flags }.toSet() + FLAG_VARIANTS_AGREE)
            else -> best.copy(
                confidence = minOf(best.confidence, OcrAssessor.MERGED_READ_CONFIDENCE_CAP),
                flags = best.flags + FLAG_VARIANTS_DISAGREE,
            )
        }
    }
}

/** Decides whether the background around a character box is a red counter wheel (mechanical tenths drum). */
fun interface RedCellDetector {
    fun isRedCell(charBox: Box): Boolean
}
