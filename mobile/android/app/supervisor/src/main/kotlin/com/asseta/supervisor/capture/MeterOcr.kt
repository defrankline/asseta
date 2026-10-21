package com.asseta.supervisor.capture

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Rect
import com.asseta.core.domain.ocr.Box
import com.asseta.core.domain.ocr.OcrAssessor
import com.asseta.core.domain.ocr.OcrConsensus
import com.asseta.core.domain.ocr.OcrLine
import com.asseta.core.domain.ocr.OcrPage
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.ocr.OcrWord
import com.asseta.core.domain.ocr.PixelRedCellDetector
import com.asseta.core.domain.ocr.PixelSource
import com.google.mlkit.common.MlKit
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

/**
 * On-device hour-meter OCR with the bundled ML Kit Latin model (works offline; no remote OCR). Recognized text is
 * parsed with the shared spec parser; the drum tenths wheel is detected by colour/geometry (see OcrAssessor).
 * OCR output is evidence for confirmation by the supervisor, never proof.
 */
class MeterOcr(context: Context) {
    private val recognizer = run {
        // Normally done by ML Kit's init provider; explicit (idempotent) so instrumentation and early callers work too.
        runCatching { MlKit.initialize(context.applicationContext) }
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }

    /**
     * Recognizes the original; if that is not confident at [minConfidence], also a contrast-enhanced variant, and
     * combines them (agreement = evidence, disagreement = never confident). The red-wheel check samples the original
     * colours (the variant has the same geometry).
     */
    suspend fun read(bitmap: Bitmap, decimalPlaces: Int, minConfidence: Double): OcrReading {
        val assessor = OcrAssessor(PixelRedCellDetector(BitmapPixels(bitmap)))
        suspend fun assess(variant: Bitmap) =
            assessor.assess(toPage(recognizer.process(InputImage.fromBitmap(variant, 0)).awaitResult()), decimalPlaces)
        val original = assess(bitmap)
        if (original.isConfident(minConfidence)) return original
        val enhanced = assess(ImageEnhancer.enhance(bitmap))
        return OcrConsensus.combine(listOf(original, enhanced)).copy(rawText = original.rawText)
    }

    companion object {
        private const val MAX_OCR_DIMENSION = 2048

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
