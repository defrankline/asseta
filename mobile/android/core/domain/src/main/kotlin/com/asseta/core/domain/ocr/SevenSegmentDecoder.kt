package com.asseta.core.domain.ocr

/**
 * Deterministic 7-segment decoder used as an independent second opinion for LCD/LED meters (same rules as iOS).
 *
 * Each glyph is sampled at the seven segment positions inside a cell spanning the row's common top/bottom and the
 * row's median digit width (right-aligned, because a `1` lights only the right segments). A segment is on
 * (ink >= 45%), off (<= 15%) or uncertain; any uncertain segment or an unknown pattern fails the whole row, so
 * proportional fonts simply produce no opinion (null).
 */
object SevenSegmentDecoder {
    private val PATTERNS = mapOf(
        "abcdef" to '0', "bc" to '1', "abdeg" to '2', "abcdg" to '3', "bcfg" to '4', "acdfg" to '5',
        "acdefg" to '6', "cdefg" to '6', "abc" to '7', "abcf" to '7', "abcdefg" to '8', "abcdfg" to '9', "abcfg" to '9',
    )

    /** (segment, u-range, v-range) in cell-relative coordinates, v measured from the top. */
    private class Region(val segment: Char, val u0: Double, val u1: Double, val v0: Double, val v1: Double)

    private val REGIONS = listOf(
        Region('a', 0.3, 0.7, 0.0, 0.12), Region('b', 0.8, 1.0, 0.2, 0.4), Region('c', 0.8, 1.0, 0.6, 0.8),
        Region('d', 0.3, 0.7, 0.88, 1.0), Region('e', 0.0, 0.2, 0.6, 0.8), Region('f', 0.0, 0.2, 0.2, 0.4),
        Region('g', 0.3, 0.7, 0.44, 0.56),
    )

    fun decode(row: GlyphRow, segmentation: Segmentation): List<Char>? {
        val top = row.glyphs.map { it.y0 }.sorted()[row.glyphs.size / 2]
        val bottom = row.glyphs.map { it.y1 }.sorted()[row.glyphs.size / 2]
        val cellHeight = bottom - top + 1
        val cellWidth = row.medianWidth
        if (cellHeight < 12 || cellWidth < 4) return null
        return row.glyphs.map { glyph ->
            if (glyph.width * 100 < cellWidth * 40) {
                // A narrow full-height stroke is a `1`.
                if (glyph.height * 100 < cellHeight * 80) return null
                return@map '1'
            }
            val lit = StringBuilder()
            for (region in REGIONS) {
                val ratio = inkRatio(segmentation, glyph.x1, cellWidth, top, cellHeight, region) ?: return null
                if (ratio >= 0.45) lit.append(region.segment) else if (ratio > 0.15) return null
            }
            PATTERNS[lit.toString()] ?: return null
        }
    }

    private fun inkRatio(s: Segmentation, x1: Int, width: Int, top: Int, height: Int, region: Region): Double? {
        val x0 = x1 - width + 1
        val left = x0 + (region.u0 * width).toInt()
        val right = x0 + (region.u1 * width).toInt() - 1
        val upper = top + (region.v0 * height).toInt()
        val lower = top + (region.v1 * height).toInt() - 1
        if (left < 0 || upper < 0 || right >= s.image.width || lower >= s.image.height || right < left || lower < upper) {
            return null
        }
        var ink = 0
        var total = 0
        for (y in upper..lower) for (x in left..right) {
            total++
            if (s.ink(x, y)) ink++
        }
        return if (total == 0) null else ink.toDouble() / total
    }
}
