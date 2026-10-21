package com.asseta.core.domain.ocr

import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/**
 * Re-renders a segmented row as clean black glyphs on white with uniform spacing, a clear decimal point where
 * geometry found one, and bottom-aligned baselines (same layout rules as iOS). A text recogniser reads this far more
 * reliably than the raw photo of a segmented or drum display. Output is an opaque ARGB buffer (top row first).
 * [shear] > 0 renders the row italic (top shifted right by `shear` x height): a seven-segment `7` then has a slanted
 * stem, which a Latin text model otherwise reads as `1`.
 */
object GlyphRenderer {
    class Rendered(val width: Int, val height: Int, val argb: IntArray, val glyphCount: Int)

    private const val WHITE = -0x1 // 0xFFFFFFFF
    private const val BLACK = -0x1000000 // 0xFF000000
    private const val MAX_WIDTH = 8000

    fun render(row: GlyphRow, segmentation: Segmentation, scale: Double, gapFactor: Double, shear: Double = 0.0): Rendered? {
        val medianHeight = row.medianHeight.toDouble()
        if (medianHeight <= 0) return null
        val s = scale / medianHeight
        val gap = medianHeight * gapFactor
        val margin = medianHeight * 0.6
        val dotSize = medianHeight * 0.16
        var totalWidth = margin * 2
        row.glyphs.forEachIndexed { i, glyph ->
            totalWidth += glyph.width + gap
            if (row.dotAfter == i) totalWidth += dotSize + gap * 0.5
        }
        val tallest = (row.glyphs.maxOfOrNull { it.height } ?: row.medianHeight).toDouble()
        totalWidth += shear * tallest
        val width = ceil(totalWidth * s).toInt()
        val height = ceil((tallest + margin * 2) * s).toInt()
        if (width <= 0 || height <= 0 || width >= MAX_WIDTH) return null
        val out = IntArray(width * height) { WHITE }
        val baseline = height - margin * s // bottom edge of every glyph
        var x = margin
        row.glyphs.forEachIndexed { i, glyph ->
            for (py in glyph.y0..glyph.y1) {
                var runStart = -1
                for (px in glyph.x0..glyph.x1 + 1) {
                    val ink = px <= glyph.x1 && segmentation.ink(px, py)
                    if (ink && runStart < 0) runStart = px
                    if (!ink && runStart >= 0) {
                        val left = (x + (runStart - glyph.x0) + shear * (glyph.y1 - py)) * s
                        val bottom = baseline - (glyph.y1 - py) * s
                        fill(out, width, height, left, bottom - s - 0.5, (px - runStart) * s + 0.5, s + 0.5)
                        runStart = -1
                    }
                }
            }
            x += glyph.width + gap
            if (row.dotAfter == i) {
                val r = dotSize * s / 2
                disc(out, width, height, (x - gap * 0.5) * s + r, baseline - r, r)
                x += dotSize + gap * 0.5
            }
        }
        return Rendered(width, height, out, row.glyphs.size)
    }

    private fun fill(out: IntArray, w: Int, h: Int, left: Double, top: Double, rw: Double, rh: Double) {
        val x0 = max(0, Math.round(left).toInt())
        val x1 = min(w, Math.round(left + rw).toInt())
        val y0 = max(0, Math.round(top).toInt())
        val y1 = min(h, Math.round(top + rh).toInt())
        for (y in y0 until y1) for (xx in x0 until x1) out[y * w + xx] = BLACK
    }

    private fun disc(out: IntArray, w: Int, h: Int, cx: Double, cy: Double, r: Double) {
        val y0 = max(0, (cy - r).toInt())
        val y1 = min(h - 1, (cy + r).toInt())
        val x0 = max(0, (cx - r).toInt())
        val x1 = min(w - 1, (cx + r).toInt())
        for (y in y0..y1) for (xx in x0..x1) {
            val dx = xx + 0.5 - cx
            val dy = y + 0.5 - cy
            if (dx * dx + dy * dy <= r * r) out[y * w + xx] = BLACK
        }
    }
}
