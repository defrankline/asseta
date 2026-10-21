package com.asseta.supervisor.capture

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Rect
import androidx.core.graphics.createBitmap
import androidx.core.graphics.scale
import com.asseta.core.domain.ocr.Box
import com.asseta.core.domain.ocr.GeometricOcr
import com.asseta.core.domain.ocr.GlyphRenderer
import com.asseta.core.domain.ocr.GlyphSegmenter
import com.asseta.core.domain.ocr.OcrAssessor
import com.asseta.core.domain.ocr.OcrConsensus
import com.asseta.core.domain.ocr.OcrLine
import com.asseta.core.domain.ocr.OcrPage
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.ocr.OcrWord
import com.asseta.core.domain.ocr.PixelRedCellDetector
import com.asseta.core.domain.ocr.PixelSource
import com.asseta.core.domain.ocr.RgbImage
import com.google.mlkit.common.MlKit
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

/**
 * On-device hour-meter OCR with the bundled ML Kit Latin model (works offline; no remote OCR). OCR output is evidence
 * for confirmation by the supervisor, never proof.
 *
 * ML Kit's own confidence is high even for wrong reads of segmented displays, so it is not the score. The photo is
 * segmented into glyphs ([GlyphSegmenter], deskewed), the most prominent rows are re-rendered as clean black-on-white
 * glyphs in several layouts ([GlyphRenderer]), each layout is read by ML Kit and must give one character per glyph,
 * and [GeometricOcr] scores the agreement between layouts, the seven-segment decoder and the full-frame read. ML Kit
 * reads an upright seven-segment `7` as `1`; when only that separates it from the decoder, italic renders of the row
 * are read as well, and the decoder's digits are taken only if one of those ML Kit reads matches them exactly. Without a
 * geometric read, the previous text-only assessment (drum colour split, enhanced variant) is used, capped below any
 * sane acceptance threshold.
 */
class MeterOcr(context: Context) {
    private val recognizer = run {
        // Normally done by ML Kit's init provider; explicit (idempotent) so instrumentation and early callers work too.
        runCatching { MlKit.initialize(context.applicationContext) }
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }

    suspend fun read(bitmap: Bitmap, decimalPlaces: Int, minConfidence: Double): OcrReading {
        val fullFrame = recognize(bitmap)
        val segmentation = GlyphSegmenter.segmentDeskewed(toRgbImage(bitmap))
        val rows = segmentation.rows.take(GeometricOcr.MAX_ROWS).mapNotNull { row ->
            suspend fun reads(shear: Double) = GeometricOcr.LAYOUTS.mapNotNull { layout ->
                GlyphRenderer.render(row, segmentation, layout.scale, layout.gapFactor, shear)
                    ?.let { GeometricOcr.assign(layoutText(recognize(it.toBitmap())), it.glyphCount) }
            }
            val votes = reads(shear = 0.0)
            val corroboration = if (GeometricOcr.needsCorroboration(row, segmentation, votes)) {
                GeometricOcr.CORROBORATION_SHEARS.flatMap { reads(it) }
            } else {
                emptyList()
            }
            GeometricOcr.readRow(row, segmentation, votes, decimalPlaces, corroboration)
        }
        val fullPage = toPage(fullFrame)
        return GeometricOcr.combine(rows, fullPage.rawText, decimalPlaces)
            ?: GeometricOcr.unconfirmed(textOnly(bitmap, fullPage, decimalPlaces, minConfidence))
    }

    private suspend fun recognize(bitmap: Bitmap): Text = recognizer.process(InputImage.fromBitmap(bitmap, 0)).awaitResult()

    /**
     * Text-only assessment: the original; if not confident, also a contrast-enhanced variant, combined (disagreement is
     * never confident). The red-wheel check samples the original colours (the variant has the same geometry).
     */
    private suspend fun textOnly(bitmap: Bitmap, page: OcrPage, decimalPlaces: Int, minConfidence: Double): OcrReading {
        val assessor = OcrAssessor(PixelRedCellDetector(BitmapPixels(bitmap)))
        val original = assessor.assess(page, decimalPlaces)
        if (original.isConfident(minConfidence)) return original
        val enhanced = assessor.assess(toPage(recognize(ImageEnhancer.enhance(bitmap))), decimalPlaces)
        return OcrConsensus.combine(listOf(original, enhanced)).copy(rawText = original.rawText)
    }

    companion object {
        private const val MAX_OCR_DIMENSION = 2048

        /** Long-side limit for glyph segmentation (CPU work grows with the pixel count). */
        private const val MAX_SEGMENTATION_DIMENSION = 1280

        private fun GlyphRenderer.Rendered.toBitmap(): Bitmap =
            createBitmap(width, height).apply { setPixels(argb, 0, width, 0, 0, width, height) }

        /** Text of a rendered row, blocks left to right (one character per glyph is checked by the caller). */
        fun layoutText(text: Text): String =
            text.textBlocks.sortedBy { it.boundingBox?.left ?: 0 }.joinToString(" ") { block ->
                block.lines.sortedBy { it.boundingBox?.left ?: 0 }.joinToString(" ") { it.text }
            }

        /** ARGB snapshot for the pure-Kotlin segmenter, downscaled so the long side is at most 1280 px. */
        fun toRgbImage(bitmap: Bitmap): RgbImage {
            val longSide = maxOf(bitmap.width, bitmap.height)
            val source = if (longSide <= MAX_SEGMENTATION_DIMENSION) {
                bitmap
            } else {
                val f = MAX_SEGMENTATION_DIMENSION.toDouble() / longSide
                bitmap.scale((bitmap.width * f).toInt().coerceAtLeast(1), (bitmap.height * f).toInt().coerceAtLeast(1))
            }
            val w = source.width
            val h = source.height
            return RgbImage(w, h, IntArray(w * h).also { source.getPixels(it, 0, w, 0, 0, w, h) })
        }

        /** Decodes a downsampled, upright copy for OCR only; the stored evidence stays the original JPEG bytes. */
        fun decodeForOcr(jpeg: ByteArray, rotationDegrees: Int): Bitmap? {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size, bounds)
            var sample = 1
            while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_OCR_DIMENSION) sample *= 2
            val decoded = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size, BitmapFactory.Options().apply { inSampleSize = sample })
                ?: return null
            if (rotationDegrees % 360 == 0) return decoded
            val matrix = Matrix().apply { postRotate(rotationDegrees.toFloat()) }
            return Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, true)
        }

        fun toPage(text: Text): OcrPage = OcrPage(
            text.textBlocks.flatMap { block ->
                block.lines.map { line ->
                    OcrLine(
                        line.elements.map { e ->
                            OcrWord(e.text, e.confidence, e.boundingBox?.toBox(), e.symbols.mapNotNull { it.boundingBox?.toBox() })
                        },
                    )
                }
            },
        )

        private fun Rect.toBox() = Box(left, top, right, bottom)
    }
}

/** Pixel snapshot of a bitmap for the red-wheel detector (one bulk copy instead of per-pixel JNI calls). */
class BitmapPixels(bitmap: Bitmap) : PixelSource {
    override val width: Int = bitmap.width
    override val height: Int = bitmap.height
    private val pixels = IntArray(width * height).also { bitmap.getPixels(it, 0, width, 0, 0, width, height) }
    override fun argb(x: Int, y: Int): Int = pixels[y * width + x]
}
