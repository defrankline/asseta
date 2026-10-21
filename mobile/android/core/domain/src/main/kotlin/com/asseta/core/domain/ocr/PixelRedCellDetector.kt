package com.asseta.core.domain.ocr

/** Read-only ARGB pixel access (backed by an Android Bitmap on device, an IntArray in tests). */
interface PixelSource {
    val width: Int
    val height: Int
    fun argb(x: Int, y: Int): Int
}

/**
 * Samples a grid over the character box expanded to its wheel cell and reports "red" when enough samples are strongly
 * red (R dominant over G and B). The glyph itself is white/black, so only the wheel background votes red.
 */
class PixelRedCellDetector(
    private val pixels: PixelSource,
    private val minRedFraction: Double = 0.30,
) : RedCellDetector {

    override fun isRedCell(charBox: Box): Boolean = redFraction(charBox) >= minRedFraction

    fun redFraction(charBox: Box): Double {
        val padX = charBox.width / 4
        val padY = charBox.height / 6
        val left = (charBox.left - padX).coerceIn(0, pixels.width - 1)
        val right = (charBox.right + padX).coerceIn(0, pixels.width - 1)
        val top = (charBox.top - padY).coerceIn(0, pixels.height - 1)
        val bottom = (charBox.bottom + padY).coerceIn(0, pixels.height - 1)
        if (right <= left || bottom <= top) return 0.0
        var red = 0
        var total = 0
        for (gy in 0 until GRID) {
            val y = top + (bottom - top) * gy / (GRID - 1)
            for (gx in 0 until GRID) {
                val x = left + (right - left) * gx / (GRID - 1)
                total++
                if (isRed(pixels.argb(x, y))) red++
            }
        }
        return red.toDouble() / total
    }

    private fun isRed(argb: Int): Boolean {
        val r = (argb shr 16) and 0xFF
        val g = (argb shr 8) and 0xFF
        val b = argb and 0xFF
        return r >= 50 && r >= g * 1.8 && r >= b * 1.8 // saturation test; low floor keeps dim red wheels
    }

    private companion object {
        const val GRID = 12
    }
}
