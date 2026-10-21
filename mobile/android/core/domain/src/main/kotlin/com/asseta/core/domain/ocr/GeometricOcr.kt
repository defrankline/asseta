package com.asseta.core.domain.ocr

import kotlin.math.min

/**
 * Engine-independent scoring of the geometric OCR pipeline (port of the iOS `MeterOCR` rules). The text recogniser
 * (ML Kit on Android) reads each row re-rendered by [GlyphRenderer] in the [LAYOUTS]; this object maps its text back to
 * glyphs, votes, consults [SevenSegmentDecoder], composes parser input and scores agreement.
 *
 * The recogniser's own confidence is not used: it is high even for wrong reads of segmented displays. Confidence is
 * earned by independent agreement only, plus plausibility checks:
 * - the decimal point comes from geometry (LCD dot) or a red tenths wheel (mechanical drum);
 * - every glyph must map to exactly one character, and the digit run must be contiguous;
 * - a `1` as wide as the other digits is suspicious (blurred 7-segment `7`);
 * - a full-frame read with the same digit count but different digits caps confidence;
 * - on 7-segment displays the deterministic segment decoder is a second opinion: agreement with a layout majority
 *   counts as unanimous, and it resolves a too-wide `1` only when at least one recogniser read (an upright layout or
 *   an italic corroboration render, see [needsCorroboration]) gave exactly the decoder's digits.
 *
 * Votes are compared after mapping the parser's letter/digit confusions (`O`->`0`, ...) when a vote contains a real
 * digit: the shared parser maps them inside numeric tokens anyway, so `84771.O` and `84771.0` are the same reading.
 *
 * Scores: unanimous [UNANIMOUS] (+[FULL_FRAME_BONUS] when the full-frame read agrees), 2 of 3 layouts [MAJORITY],
 * else [WEAK]; capped at [CONFLICT_CAP] for a suspicious `1`, a segment-decoder conflict or a full-frame conflict, and
 * at [AMBIGUOUS_CAP] for an ambiguous decimal point or another same-size row with a different number. A recogniser read
 * without geometric confirmation never exceeds [UNCONFIRMED_CAP]. Heuristic agreement scores, not calibrated
 * probabilities; any disagreement keeps a read below the usual 0.85 threshold so the app asks for a recapture.
 */
object GeometricOcr {
    data class Layout(val scale: Double, val gapFactor: Double)

    val LAYOUTS = listOf(Layout(64.0, 0.3), Layout(100.0, 0.5), Layout(80.0, 0.4))

    /** Italic re-renders (each of [LAYOUTS] per shear) read only to corroborate the decoder on a too-wide `1`. */
    val CORROBORATION_SHEARS = listOf(0.15, 0.25)
    const val MAX_ROWS = 3
    const val UNANIMOUS = 0.92
    const val MAJORITY = 0.70
    const val WEAK = 0.50
    const val FULL_FRAME_BONUS = 0.05
    const val MAX_CONFIDENCE = 0.98
    const val CONFLICT_CAP = 0.60
    const val AMBIGUOUS_CAP = 0.50
    const val UNCONFIRMED_CAP = 0.40

    enum class SegmentOpinion { ABSENT, AGREE, RESOLVED, CONFLICT }

    data class RowReading(
        val value: String?,
        val text: String,
        val agreeing: Int,
        val suspiciousOne: Boolean,
        val ambiguousDots: Boolean,
        val segments: SegmentOpinion,
        val medianHeight: Int,
        val parseReason: String,
    ) {
        val agreement: Double get() = agreeing.toDouble() / LAYOUTS.size
    }

    private const val DIGIT_LIKE = "0123456789OQDILSBZG|"
    private const val ONES = "1IL|"
    private const val IGNORED = ".,·:'`"

    /**
     * Maps recognised text to glyph slots by order: after dropping whitespace and punctuation (the decimal point comes
     * from geometry) there must be exactly one character per rendered glyph, else the layout is discarded (null).
     */
    fun assign(text: String, glyphCount: Int): List<Char>? {
        val chars = text.filter { !it.isWhitespace() && it !in IGNORED }
        if (chars.length != glyphCount) return null
        return chars.uppercase().toList().takeIf { it.size == glyphCount }
    }

    /**
     * True when only italic corroboration renders could resolve the row: the decoder has an opinion that differs from
     * the layout majority only at too-wide `1` glyphs, and no upright layout read the decoder's digits.
     */
    fun needsCorroboration(row: GlyphRow, segmentation: Segmentation, votes: List<List<Char>>): Boolean {
        val canonical = votes.map(::canonical)
        val winner = majority(canonical) ?: return false
        val decoded = SevenSegmentDecoder.decode(row, segmentation) ?: return false
        return decoded != winner && decoded !in canonical && hasWideOne(winner, row) &&
            differsOnlyAtWideOnes(winner, decoded, row)
    }

    /**
     * Votes over the per-layout reads ([votes], from [assign]) of one row and consults the segment decoder.
     * [corroboration] are reads of italic renders (see [needsCorroboration]); they never vote, they only count as "a
     * recogniser read the decoder's digits" when resolving a too-wide `1`.
     */
    fun readRow(
        row: GlyphRow,
        segmentation: Segmentation,
        votes: List<List<Char>>,
        decimalPlaces: Int,
        corroboration: List<List<Char>> = emptyList(),
    ): RowReading? {
        val canonicalVotes = votes.map(::canonical)
        val winner = majority(canonicalVotes) ?: return null
        var chars = winner
        var agreeing = canonicalVotes.count { it == winner }
        var wideOne = hasWideOne(chars, row)
        var segments = SegmentOpinion.ABSENT
        val decoded = SevenSegmentDecoder.decode(row, segmentation)
        if (decoded != null) {
            if (decoded == chars) {
                segments = SegmentOpinion.AGREE
                // Two independent recognisers (a layout majority and the deterministic decoder) agree on every glyph.
                if (agreeing * 3 >= LAYOUTS.size * 2) agreeing = LAYOUTS.size
            } else if (wideOne && (decoded in canonicalVotes || decoded in corroboration.map(::canonical)) &&
                differsOnlyAtWideOnes(chars, decoded, row)
            ) {
                // A full-width glyph was read as `1`; the decoder, confirmed by at least one recogniser read, shows
                // the digit (typically a 7-segment `7`).
                chars = decoded
                agreeing = LAYOUTS.size
                wideOne = false
                segments = SegmentOpinion.RESOLVED
            } else {
                segments = SegmentOpinion.CONFLICT
            }
        }
        val text = compose(chars, row) ?: return null
        val parse = MeterReadingParser.parse(text, decimalPlaces)
        return RowReading(parse.value, text, agreeing, wideOne, row.ambiguousDots, segments, row.medianHeight, parse.reason)
    }

    /**
     * Combines the readings of the most prominent rows with the full-frame recogniser text. Null when no row produced
     * a value (the caller then falls back to an unconfirmed read capped at [UNCONFIRMED_CAP]).
     */
    fun combine(rows: List<RowReading>, fullFrameText: String, decimalPlaces: Int): OcrReading? {
        val parsed = rows.filter { it.value != null }
        val primary = parsed.firstOrNull() ?: return null
        var confidence = when {
            primary.agreement >= 1 -> UNANIMOUS
            primary.agreement >= 0.6 -> MAJORITY
            else -> WEAK
        }
        val flags = mutableSetOf("LAYOUTS_${primary.agreeing}_OF_${LAYOUTS.size}")
        if (primary.suspiciousOne) { confidence = min(confidence, CONFLICT_CAP); flags += FLAG_WIDE_ONE }
        if (primary.ambiguousDots) { confidence = min(confidence, AMBIGUOUS_CAP); flags += FLAG_AMBIGUOUS_DOT }
        if (primary.segments != SegmentOpinion.ABSENT) flags += "SEGMENTS_${primary.segments}"
        if (primary.segments == SegmentOpinion.CONFLICT) confidence = min(confidence, CONFLICT_CAP)
        // Another row of similar-size text with a different number makes the reading ambiguous; smaller rows
        // (clock, odometer, labels) are ordinary distractors.
        val peers = parsed.filter { it.medianHeight * 4 >= primary.medianHeight * 3 }
        if (peers.mapNotNull { it.value }.toSet().size > 1) { confidence = min(confidence, AMBIGUOUS_CAP); flags += FLAG_ROWS_DISAGREE }
        val ours = digits(primary.value!!)
        val full = MeterReadingParser.parse(fullFrameText, decimalPlaces)
        val other = full.candidates.firstOrNull()?.takeIf { full.reason == MeterReadingParser.Reason.OK }?.let(::digits)
        if (other != null) {
            if (other == ours) {
                confidence = min(confidence + FULL_FRAME_BONUS, MAX_CONFIDENCE); flags += FLAG_FULL_FRAME_AGREES
            } else if (other.length == ours.length) {
                confidence = min(confidence, CONFLICT_CAP); flags += FLAG_FULL_FRAME_CONFLICT
            }
        }
        val raw = (listOf(primary.text) + fullFrameText.lines().filter { it.isNotBlank() }).joinToString(" | ")
        return OcrReading(primary.value, confidence, raw.take(OcrAssessor.MAX_RAW_TEXT), primary.parseReason, flags)
    }

    /** A recogniser-only read (no geometric confirmation) is never confident enough to skip a recapture. */
    fun unconfirmed(reading: OcrReading): OcrReading = reading.copy(
        confidence = min(reading.confidence, UNCONFIRMED_CAP),
        flags = reading.flags + FLAG_NO_GEOMETRIC_READ,
    )

    /** Most frequent vote; ties go to the earliest layout. */
    private fun majority(votes: List<List<Char>>): List<Char>? =
        votes.groupBy { it }.entries.maxByOrNull { it.value.size }?.key

    /** Maps the parser's letter/digit confusions to digits when the vote contains at least one real digit. */
    fun canonical(chars: List<Char>): List<Char> =
        if (chars.none { it in '0'..'9' }) chars else chars.map { CONFUSABLE[it] ?: it }

    private val CONFUSABLE = mapOf(
        'O' to '0', 'D' to '0', 'Q' to '0', 'I' to '1', 'L' to '1', '|' to '1',
        'S' to '5', 'B' to '8', 'Z' to '2', 'G' to '6',
    )

    /** Parser input from per-glyph characters: geometric decimal point, drum tenths split, unit letters separated. */
    fun compose(chars: List<Char>, row: GlyphRow): String? {
        val isDigit = chars.map { c ->
            when {
                c in DIGIT_LIKE -> true
                c.isLetter() -> false
                else -> return null
            }
        }
        val first = isDigit.indexOf(true)
        val last = isDigit.lastIndexOf(true)
        if (first < 0 || !isDigit.subList(first, last + 1).all { it }) return null
        val text = StringBuilder()
        chars.forEachIndexed { i, c ->
            if (i == last + 1 || (i == first && i > 0)) text.append(' ')
            if (row.redTenths != null && row.dotAfter == null && i == row.redTenths && i == last) text.append(' ')
            text.append(c)
            if (row.dotAfter == i && i < last) text.append('.')
        }
        return text.toString()
    }

    /** True when [a] and [b] differ only at glyphs [a] reads as a too-wide `1`. */
    fun differsOnlyAtWideOnes(a: List<Char>, b: List<Char>, row: GlyphRow): Boolean {
        if (a.size != b.size || a.size != row.glyphs.size) return false
        val median = row.glyphs.map { it.width }.sorted()[row.glyphs.size / 2].toDouble()
        return a.indices.all { i -> a[i] == b[i] || (a[i] in ONES && row.glyphs[i].width > 0.7 * median) }
    }

    /** A recognised `1` whose glyph is nearly as wide as the other digits. */
    fun hasWideOne(chars: List<Char>, row: GlyphRow): Boolean {
        val pairs = chars.zip(row.glyphs)
        val others = pairs.filter { (c, _) -> c !in ONES && c.isDigit() }.map { it.second.width }.sorted()
        if (others.isEmpty()) return false
        val median = others[others.size / 2].toDouble()
        return pairs.any { (c, g) -> c in ONES && g.width > 0.7 * median }
    }

    /** Digits without leading zeros (so `03190.6` and `3190.6` compare equal). */
    fun digits(text: String): String = text.filter { it in '0'..'9' }.trimStart('0')

    const val FLAG_WIDE_ONE = "WIDE_ONE"
    const val FLAG_AMBIGUOUS_DOT = "AMBIGUOUS_DOT"
    const val FLAG_ROWS_DISAGREE = "ROWS_DISAGREE"
    const val FLAG_FULL_FRAME_AGREES = "FULL_FRAME_AGREES"
    const val FLAG_FULL_FRAME_CONFLICT = "FULL_FRAME_CONFLICT"
    const val FLAG_NO_GEOMETRIC_READ = "NO_GEOMETRIC_READ"
}
