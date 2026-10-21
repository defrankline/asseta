package com.asseta.core.domain.ocr

import java.math.BigDecimal
import java.util.regex.Pattern

/**
 * Hour-meter OCR text -> reading, spec v1. Native port of `backend/.../meter/ocr_parse.py`; it must produce exactly the
 * results in `contracts/fixtures/ocr/parse_cases.json` (shared with iOS and the server) so rules never drift.
 *
 * Rules: ignore clock times and unit words; map common letter/digit confusions inside numeric tokens; a token with an
 * explicit '.'/',' separator is decimal; a long integer token immediately followed by a single digit token is a tenths
 * drum (mechanical counters); exactly one candidate must remain, else ambiguous. No value => manual fallback.
 */
object MeterReadingParser {
    const val SPEC_VERSION = "1"

    // Python's Unicode-aware \b and \d spelled out explicitly (word char = letter, number or '_'), because Android's
    // ICU regex does not support UNICODE_CHARACTER_CLASS and the JVM's default \b/\d differ; same result on both.
    private const val NOT_AFTER_WORD = "(?<![\\p{L}\\p{N}_])"
    private const val NOT_BEFORE_WORD = "(?![\\p{L}\\p{N}_])"
    private val UNITS = Pattern.compile("$NOT_AFTER_WORD(HRS?|HOURS?|H)$NOT_BEFORE_WORD")
    private val CLOCK = Pattern.compile("$NOT_AFTER_WORD\\p{Nd}{1,2}:\\p{Nd}{2}(:\\p{Nd}{2})?$NOT_BEFORE_WORD")
    private val TOKEN = Pattern.compile("[0-9OQDILSBZG|]+(?:[.,][0-9OQDILSBZG|]+)?")
    private val CONFUSABLE = mapOf(
        'O' to '0', 'D' to '0', 'Q' to '0', 'I' to '1', 'L' to '1', '|' to '1',
        'S' to '5', 'B' to '8', 'Z' to '2', 'G' to '6',
    )

    fun parse(text: String, decimalPlaces: Int): ParseResult {
        require(decimalPlaces >= 0) { "decimalPlaces must be >= 0" }
        var upper = CLOCK.matcher(text.uppercase()).replaceAll(" ")
        upper = UNITS.matcher(upper).replaceAll(" ")
        val tokens = buildList {
            val m = TOKEN.matcher(upper)
            while (m.find()) {
                val raw = m.group()
                if (raw.any { Character.isDigit(it) }) add(raw.map { CONFUSABLE[it] ?: it }.joinToString("").replace(',', '.'))
            }
        }
        val candidates = mutableListOf<Candidate>()
        var i = 0
        while (i < tokens.size) {
            val tok = tokens[i]
            val next = tokens.getOrNull(i + 1)
            if ('.' !in tok && next != null && next.length == 1 && tok.length >= 3 && decimalPlaces >= 1) {
                candidates += Candidate("$tok.$next", explicitSeparator = false, drumSplit = true)
                i += 2
                continue
            }
            if (tok.replace(".", "").length >= 3) candidates += Candidate(tok, explicitSeparator = '.' in tok, drumSplit = false)
            i += 1
        }
        if (candidates.isEmpty()) return ParseResult(null, Reason.NO_NUMBER)
        val texts = candidates.map { it.text }
        if (candidates.size > 1) return ParseResult(null, Reason.AMBIGUOUS, candidates = texts)
        val chosen = candidates.single()
        val value = BigDecimal(chosen.text)
        if (value.scale() > decimalPlaces) return ParseResult(null, Reason.PRECISION_EXCEEDS_METER, candidates = texts)
        return ParseResult(
            value = value.setScale(decimalPlaces).toPlainString(),
            reason = Reason.OK,
            explicitSeparator = chosen.explicitSeparator,
            drumSplit = chosen.drumSplit,
            candidates = texts,
        )
    }

    private data class Candidate(val text: String, val explicitSeparator: Boolean, val drumSplit: Boolean)

    object Reason {
        const val OK = "OK"
        const val NO_NUMBER = "NO_NUMBER"
        const val AMBIGUOUS = "AMBIGUOUS"
        const val PRECISION_EXCEEDS_METER = "PRECISION_EXCEEDS_METER"
    }
}

/**
 * [value] is a decimal string at the meter's precision, or null (manual fallback). [explicitSeparator]/[drumSplit]
 * say how the fractional part was established; app-level confidence uses them (not part of the shared spec output).
 * [candidates] are the normalized candidate tokens the decision was based on (diagnostics / OCR consistency checks).
 */
data class ParseResult(
    val value: String?,
    val reason: String,
    val explicitSeparator: Boolean = false,
    val drumSplit: Boolean = false,
    val candidates: List<String> = emptyList(),
)
