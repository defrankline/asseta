package com.asseta.core.domain.ocr

/** Draws synthetic seven-segment meter rows into an ARGB buffer for the pure-Kotlin OCR geometry tests. */
class SyntheticMeter(val width: Int = 420, val height: Int = 160, background: Int = rgb(170, 185, 150)) {
    val pixels = IntArray(width * height) { background }

    /**
     * Draws [text] (digits and one optional '.') left to right from ([left], [top]) as seven-segment glyphs of
     * [digitWidth] x [digitHeight] with stroke [stroke]; returns the x of every digit cell.
     */
    fun drawSegments(
        text: String,
        left: Int = 30,
        top: Int = 50,
        digitWidth: Int = 30,
        digitHeight: Int = 60,
        stroke: Int = 6,
        gap: Int = 16,
        ink: Int = rgb(25, 30, 25),
        cellColor: (Int) -> Int? = { null },
    ): List<Int> {
        val cells = mutableListOf<Int>()
        var x = left
        val digits = text.count { it.isDigit() }
        for (c in text) {
            if (c == '.') {
                fill(x - gap / 2 - stroke / 2, top + digitHeight - stroke, stroke, stroke, ink)
                continue
            }
            cellColor(cells.size)?.let { fill(x - 14, top - 14, digitWidth + 28, digitHeight + 28, it) }
            cells += x
            for (segment in SEGMENTS.getValue(c)) {
                val (sx, sy, sw, sh) = segmentRect(segment, digitWidth, digitHeight, stroke)
                fill(x + sx, top + sy, sw, sh, ink)
            }
            x += digitWidth + gap
        }
        check(cells.size == digits)
        return cells
    }

    fun fill(x: Int, y: Int, w: Int, h: Int, color: Int) {
        for (yy in y until y + h) for (xx in x until x + w) {
            if (xx in 0 until width && yy in 0 until height) pixels[yy * width + xx] = color
        }
    }

    fun image() = RgbImage(width, height, pixels.copyOf())

    private fun segmentRect(segment: Char, w: Int, h: Int, t: Int): List<Int> = when (segment) {
        'a' -> listOf(0, 0, w, t)
        'b' -> listOf(w - t, 0, t, h / 2)
        'c' -> listOf(w - t, h / 2, t, h - h / 2)
        'd' -> listOf(0, h - t, w, t)
        'e' -> listOf(0, h / 2, t, h - h / 2)
        'f' -> listOf(0, 0, t, h / 2)
        'g' -> listOf(0, h / 2 - t / 2, w, t)
        else -> error("segment $segment")
    }

    companion object {
        val SEGMENTS = mapOf(
            '0' to "abcdef", '1' to "bc", '2' to "abdeg", '3' to "abcdg", '4' to "bcfg", '5' to "acdfg",
            '6' to "acdefg", '7' to "abc", '8' to "abcdefg", '9' to "abcdfg",
        )

        fun rgb(r: Int, g: Int, b: Int) = (0xFF shl 24) or (r shl 16) or (g shl 8) or b
    }
}
