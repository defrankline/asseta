package com.asseta.core.domain.ocr

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/** ARGB pixels (row-major, top row first) of an image being analysed; backed by a Bitmap copy on device. */
class RgbImage(override val width: Int, override val height: Int, val argb: IntArray) : PixelSource {
    init {
        require(width > 0 && height > 0 && argb.size == width * height) { "pixel buffer does not match size" }
    }

    override fun argb(x: Int, y: Int): Int = argb[y * width + x]

    /**
     * Rotates around the centre by [degrees] (counter-clockwise as seen on screen) with bilinear sampling, filling
     * uncovered corners with the top-left pixel colour so no artificial edges appear. A row tilted down to the right
     * by `skewDegrees` is straightened by `rotated(skewDegrees)`.
     */
    fun rotated(degrees: Double): RgbImage {
        val rad = Math.toRadians(degrees)
        val c = cos(rad)
        val s = sin(rad)
        val cx = (width - 1) / 2.0
        val cy = (height - 1) / 2.0
        val fill = argb[0]
        val out = IntArray(width * height)
        for (y in 0 until height) for (x in 0 until width) {
            val dx = x - cx
            val dy = y - cy
            val sx = dx * c - dy * s + cx
            val sy = dx * s + dy * c + cy
            out[y * width + x] = sample(sx, sy, fill)
        }
        return RgbImage(width, height, out)
    }

    private fun sample(sx: Double, sy: Double, fill: Int): Int {
        if (sx < 0 || sy < 0 || sx > width - 1 || sy > height - 1) return fill
        val x0 = floor(sx).toInt()
        val y0 = floor(sy).toInt()
        val x1 = min(x0 + 1, width - 1)
        val y1 = min(y0 + 1, height - 1)
        val fx = sx - x0
        val fy = sy - y0
        var result = 0xFF shl 24
        for (shift in intArrayOf(16, 8, 0)) {
            fun ch(x: Int, y: Int) = (argb[y * width + x] shr shift) and 0xFF
            val top = ch(x0, y0) * (1 - fx) + ch(x1, y0) * fx
            val bottom = ch(x0, y1) * (1 - fx) + ch(x1, y1) * fx
            result = result or ((top * (1 - fy) + bottom * fy + 0.5).toInt().coerceIn(0, 255) shl shift)
        }
        return result
    }
}

/** Bounding box of a connected component (inclusive pixel coordinates). */
data class GlyphBox(val x0: Int, val y0: Int, val x1: Int, val y1: Int, val area: Int) {
    val width: Int get() = x1 - x0 + 1
    val height: Int get() = y1 - y0 + 1
    val centerX: Double get() = (x0 + x1) / 2.0
    val centerY: Double get() = (y0 + y1) / 2.0

    fun merge(other: GlyphBox) =
        GlyphBox(min(x0, other.x0), min(y0, other.y0), max(x1, other.x1), max(y1, other.y1), area + other.area)
}

/**
 * One candidate text row of glyph-sized components, left to right. [dotAfter]: index of the glyph a geometric decimal
 * point follows (exactly one found); [ambiguousDots]: several dot-like marks; [redTenths]: index of the right-most
 * glyph sitting on a red cell (mechanical drum tenths wheel).
 */
data class GlyphRow(
    val glyphs: List<GlyphBox>,
    val dotAfter: Int? = null,
    val ambiguousDots: Boolean = false,
    val redTenths: Int? = null,
) {
    val medianHeight: Int get() = glyphs.map { it.height }.sorted()[glyphs.size / 2]
    val medianWidth: Int get() = glyphs.map { it.width }.sorted()[glyphs.size / 2]
}

/** [mask] is the foreground (ink) after binarization, same size as [image]; [rows] most prominent first. */
class Segmentation(val image: RgbImage, val mask: BooleanArray, val rows: List<GlyphRow>) {
    fun ink(x: Int, y: Int): Boolean = mask[y * image.width + x]
}

/**
 * Classic document-analysis pipeline tuned for meter displays (same algorithm as the iOS `GlyphSegmenter`): median
 * filter (salt-and-pepper noise), global Otsu for ink polarity, local-mean adaptive threshold (glare, dim light),
 * connected components, per-column merge (7-segment pieces), row chaining, decimal-dot and red-tenths-cell detection.
 * Pure Kotlin over an ARGB buffer, so it is JVM-tested.
 */
object GlyphSegmenter {
    fun segment(image: RgbImage): Segmentation {
        val w = image.width
        val h = image.height
        val luma = medianFiltered(luminance(image), w, h)
        val mask = adaptiveMask(luma, w, h, foregroundBright = brightIsMinority(luma))
        val components = connectedComponents(mask, w, h)
        val minHeight = max(8, h / 40)
        val glyphLike = components.filter { c ->
            val ratio = c.height.toDouble() / c.width
            c.x0 > 0 && c.y0 > 0 && c.x1 < w - 1 && c.y1 < h - 1 && c.height >= minHeight && c.area >= 12 &&
                c.height <= h * 8 / 10 && ratio >= 0.9 && ratio <= 12
        }
        val rows = chainRows(mergeColumns(glyphLike)).filter { it.glyphs.size >= 3 }.map { row ->
            locateDot(row, components).let { it.copy(redTenths = redTenthsIndex(it, image, mask)) }
        }
        val sorted = rows.sortedWith(compareByDescending<GlyphRow> { it.medianHeight }.thenByDescending { it.glyphs.size })
        return Segmentation(image, mask, sorted)
    }

    /** Segments, and if the most prominent row is tilted more than [maxSkewDegrees], straightens and re-segments. */
    fun segmentDeskewed(image: RgbImage, maxSkewDegrees: Double = 1.5): Segmentation {
        val first = segment(image)
        val best = first.rows.firstOrNull() ?: return first
        val skew = skewDegrees(best)
        return if (abs(skew) > maxSkewDegrees) segment(image.rotated(skew)) else first
    }

    /** Skew of a row in degrees (positive = descending to the right) from a least-squares fit through glyph centres. */
    fun skewDegrees(row: GlyphRow): Double {
        if (row.glyphs.size < 3) return 0.0
        val mx = row.glyphs.sumOf { it.centerX } / row.glyphs.size
        val my = row.glyphs.sumOf { it.centerY } / row.glyphs.size
        var num = 0.0
        var den = 0.0
        for (g in row.glyphs) {
            num += (g.centerX - mx) * (g.centerY - my)
            den += (g.centerX - mx) * (g.centerX - mx)
        }
        return if (den == 0.0) 0.0 else Math.toDegrees(atan2(num, den))
    }

    // Binarization

    fun luminance(image: RgbImage): FloatArray = FloatArray(image.argb.size) { i ->
        val c = image.argb[i]
        0.299f * ((c shr 16) and 0xFF) + 0.587f * ((c shr 8) and 0xFF) + 0.114f * (c and 0xFF)
    }

    fun medianFiltered(values: FloatArray, w: Int, h: Int): FloatArray {
        if (w <= 2 || h <= 2) return values
        val out = values.copyOf()
        val window = FloatArray(9)
        for (r in 1 until h - 1) for (c in 1 until w - 1) {
            var k = 0
            for (dy in -1..1) {
                val base = (r + dy) * w + c
                window[k] = values[base - 1]; window[k + 1] = values[base]; window[k + 2] = values[base + 1]
                k += 3
            }
            for (i in 1 until 9) { // insertion sort of 9 values
                val v = window[i]
                var j = i - 1
                while (j >= 0 && window[j] > v) { window[j + 1] = window[j]; j-- }
                window[j + 1] = v
            }
            out[r * w + c] = window[4]
        }
        return out
    }

    /** Otsu threshold; ink is the minority class (displays are mostly background). */
    fun brightIsMinority(luma: FloatArray): Boolean {
        val threshold = otsu(luma)
        return luma.count { it.toInt() > threshold } * 2 < luma.size
    }

    fun otsu(values: FloatArray): Int {
        val hist = DoubleArray(256)
        for (v in values) hist[v.toInt().coerceIn(0, 255)] += 1.0
        val total = values.size.toDouble()
        val sumAll = (0 until 256).sumOf { it * hist[it] }
        var weightB = 0.0
        var sumB = 0.0
        var best = -1.0
        var threshold = 127
        for (t in 0 until 256) {
            weightB += hist[t]
            if (weightB <= 0) continue
            val weightF = total - weightB
            if (weightF <= 0) break
            sumB += t * hist[t]
            val diff = sumB / weightB - (sumAll - sumB) / weightF
            val between = weightB * weightF * diff * diff
            if (between > best) { best = between; threshold = t }
        }
        return threshold
    }

    fun adaptiveMask(luma: FloatArray, w: Int, h: Int, foregroundBright: Boolean): BooleanArray {
        val stride = w + 1
        val integral = DoubleArray(stride * (h + 1))
        for (r in 0 until h) {
            var rowSum = 0.0
            for (c in 0 until w) {
                rowSum += luma[r * w + c]
                integral[(r + 1) * stride + c + 1] = integral[r * stride + c + 1] + rowSum
            }
        }
        val sorted = luma.copyOf().also { it.sort() }
        val contrast = max(sorted[sorted.size * 19 / 20] - sorted[sorted.size / 20], 1f)
        val k = 0.18 * contrast
        val radius = max(h / 6, 8)
        val mask = BooleanArray(w * h)
        for (r in 0 until h) {
            val y0 = max(0, r - radius)
            val y1 = min(h - 1, r + radius)
            for (c in 0 until w) {
                val x0 = max(0, c - radius)
                val x1 = min(w - 1, c + radius)
                val n = ((x1 - x0 + 1) * (y1 - y0 + 1)).toDouble()
                val sum = integral[(y1 + 1) * stride + x1 + 1] - integral[y0 * stride + x1 + 1] -
                    integral[(y1 + 1) * stride + x0] + integral[y0 * stride + x0]
                val diff = luma[r * w + c] - sum / n
                mask[r * w + c] = if (foregroundBright) diff > k else diff < -k
            }
        }
        return mask
    }

    // Components and rows

    fun connectedComponents(mask: BooleanArray, w: Int, h: Int): List<GlyphBox> {
        val visited = BooleanArray(w * h)
        val stack = IntArray(w * h) // every pixel is pushed at most once
        val boxes = mutableListOf<GlyphBox>()
        for (start in 0 until w * h) {
            if (!mask[start] || visited[start]) continue
            visited[start] = true
            var top = 0
            stack[top++] = start
            var x0 = start % w; var x1 = x0; var y0 = start / w; var y1 = y0; var area = 0
            while (top > 0) {
                val p = stack[--top]
                area++
                val x = p % w
                val y = p / w
                x0 = min(x0, x); x1 = max(x1, x); y0 = min(y0, y); y1 = max(y1, y)
                if (x > 0 && mask[p - 1] && !visited[p - 1]) { visited[p - 1] = true; stack[top++] = p - 1 }
                if (x < w - 1 && mask[p + 1] && !visited[p + 1]) { visited[p + 1] = true; stack[top++] = p + 1 }
                if (y > 0 && mask[p - w] && !visited[p - w]) { visited[p - w] = true; stack[top++] = p - w }
                if (y < h - 1 && mask[p + w] && !visited[p + w]) { visited[p + w] = true; stack[top++] = p + w }
            }
            boxes += GlyphBox(x0, y0, x1, y1, area)
        }
        return boxes
    }

    /** Merges components stacked in the same column (7-segment pieces, broken strokes). */
    fun mergeColumns(boxes: List<GlyphBox>): List<GlyphBox> {
        val merged = mutableListOf<GlyphBox>()
        for (box in boxes.sortedBy { it.x0 }) {
            val i = merged.indexOfLast { m ->
                val overlap = min(m.x1, box.x1) - max(m.x0, box.x0)
                overlap > min(m.width, box.width) / 2 && abs(m.centerY - box.centerY) < max(m.height, box.height)
            }
            if (i >= 0) merged[i] = merged[i].merge(box) else merged += box
        }
        return merged
    }

    /** Greedy left-to-right chaining of similar-height glyphs with small gaps (tolerates skew). */
    fun chainRows(glyphs: List<GlyphBox>): List<GlyphRow> {
        val used = BooleanArray(glyphs.size)
        val order = glyphs.indices.sortedBy { glyphs[it].x0 }
        val rows = mutableListOf<GlyphRow>()
        for (start in order) {
            if (used[start]) continue
            used[start] = true
            val chain = mutableListOf(glyphs[start])
            var current = glyphs[start]
            for (next in order) {
                if (used[next] || glyphs[next].x0 <= current.x0) continue
                val candidate = glyphs[next]
                val ratio = candidate.height.toDouble() / current.height
                val gap = candidate.x0 - current.x1
                if (ratio > 0.62 && ratio < 1.6 && abs(candidate.centerY - current.centerY) < current.height / 2.0 &&
                    gap < current.height && gap > -current.width / 2
                ) {
                    used[next] = true
                    chain += candidate
                    current = candidate
                }
            }
            rows += GlyphRow(chain)
        }
        return rows
    }

    /** A small solid mark on the baseline between two glyphs is the decimal point; several marks are ambiguous. */
    fun locateDot(row: GlyphRow, components: List<GlyphBox>): GlyphRow {
        val mh = row.medianHeight
        val found = mutableSetOf<Int>()
        for (d in components) {
            if (d.height < max(3, mh / 14) || d.height * 100 > mh * 35 || d.width * 100 > mh * 35 ||
                d.area < 0.45 * d.width * d.height
            ) continue
            val left = row.glyphs.indexOfLast { it.x1 <= d.x0 + 1 }
            if (left < 0 || left + 1 >= row.glyphs.size || row.glyphs[left + 1].x0 < d.x1 - 1) continue
            val baseline = (row.glyphs[left].y1 + row.glyphs[left + 1].y1) / 2.0
            if (d.y1 >= baseline - mh / 5.0 && d.y1 <= baseline + mh / 8.0) found += left
        }
        return row.copy(dotAfter = found.singleOrNull(), ambiguousDots = found.size > 1)
    }

    /** The right-most glyph whose surrounding background is saturated red (drum tenths wheel), its neighbour not. */
    fun redTenthsIndex(row: GlyphRow, image: RgbImage, mask: BooleanArray): Int? {
        val last = row.glyphs.lastIndex
        if (last < 1) return null
        fun isRed(g: GlyphBox): Boolean {
            var r = 0.0; var gr = 0.0; var b = 0.0; var n = 0
            val ex = g.width / 3
            val ey = g.height / 5
            for (y in max(0, g.y0 - ey)..min(image.height - 1, g.y1 + ey)) {
                for (x in max(0, g.x0 - ex)..min(image.width - 1, g.x1 + ex)) {
                    if (mask[y * image.width + x]) continue
                    val c = image.argb[y * image.width + x]
                    r += (c shr 16) and 0xFF; gr += (c shr 8) and 0xFF; b += c and 0xFF; n++
                }
            }
            if (n == 0) return false
            r /= n; gr /= n; b /= n
            return r > 1.8 * max(gr, b) && r - max(gr, b) > 25
        }
        return if (isRed(row.glyphs[last]) && !isRed(row.glyphs[last - 1])) last else null
    }
}
