package com.asseta.supervisor.capture

import android.graphics.Bitmap
import androidx.core.graphics.createBitmap

/**
 * Second OCR variant for low-contrast displays (LCD, dim/backlit): luminance, percentile contrast stretch, polarity
 * normalised to dark text on a light background, and a 3x3 minimum filter that closes the small gaps between
 * seven-segment strokes. Same size as the input, so recognizer boxes stay comparable. OCR input only; evidence is
 * always the original JPEG.
 */
object ImageEnhancer {
    fun enhance(source: Bitmap): Bitmap {
        val w = source.width
        val h = source.height
        val px = IntArray(w * h).also { source.getPixels(it, 0, w, 0, 0, w, h) }
        val lum = IntArray(px.size) { i ->
            val c = px[i]
            ((c shr 16 and 0xFF) * 299 + (c shr 8 and 0xFF) * 587 + (c and 0xFF) * 114) / 1000
        }
        val histogram = IntArray(256).also { hist -> lum.forEach { hist[it]++ } }
        val lo = percentile(histogram, px.size, 0.02)
        val hi = percentile(histogram, px.size, 0.98).coerceAtLeast(lo + 1)
        val stretched = IntArray(px.size) { i -> ((lum[i] - lo) * 255 / (hi - lo)).coerceIn(0, 255) }
        // Background is the majority: if most pixels are dark, the display shows light text -> invert.
        if (stretched.count { it < 128 } > stretched.size / 2) for (i in stretched.indices) stretched[i] = 255 - stretched[i]
        val closed = IntArray(px.size)
        for (y in 0 until h) for (x in 0 until w) {
            var m = 255
            for (dy in -1..1) for (dx in -1..1) {
                val yy = (y + dy).coerceIn(0, h - 1)
                val xx = (x + dx).coerceIn(0, w - 1)
                m = minOf(m, stretched[yy * w + xx])
            }
            closed[y * w + x] = (0xFF shl 24) or (m shl 16) or (m shl 8) or m
        }
        return createBitmap(w, h).apply { setPixels(closed, 0, w, 0, 0, w, h) }
    }

    private fun percentile(histogram: IntArray, total: Int, fraction: Double): Int {
        val target = (total * fraction).toLong()
        var seen = 0L
        histogram.forEachIndexed { value, count ->
            seen += count
            if (seen > target) return value
        }
        return 255
    }
}
