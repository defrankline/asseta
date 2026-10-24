package com.asseta.core.ui.image

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import java.io.ByteArrayInputStream

/** How to turn a photo upright for an EXIF orientation (1–8): rotate clockwise, then mirror horizontally if [mirror]. */
data class ExifTransform(val rotationDegrees: Int, val mirror: Boolean) {
    companion object {
        fun of(orientation: Int): ExifTransform = when (orientation) {
            2 -> ExifTransform(0, true)
            3 -> ExifTransform(180, false)
            4 -> ExifTransform(180, true)
            5 -> ExifTransform(90, true)
            6 -> ExifTransform(90, false)
            7 -> ExifTransform(270, true)
            8 -> ExifTransform(270, false)
            else -> ExifTransform(0, false)
        }
    }
}

/**
 * Decodes a photo downscaled to at most [maxSide] px and turned upright by its EXIF orientation. BitmapFactory ignores
 * EXIF, so camera photos (which keep the sensor's pixels and only tag the orientation) otherwise show sideways.
 */
fun decodeUpright(bytes: ByteArray, maxSide: Int = 2048): Bitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    var sample = 1
    while (bounds.outWidth / sample > maxSide || bounds.outHeight / sample > maxSide) sample *= 2
    val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return null
    val orientation = runCatching {
        ExifInterface(ByteArrayInputStream(bytes)).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
    }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)
    val t = ExifTransform.of(orientation)
    if (t.rotationDegrees == 0 && !t.mirror) return decoded
    val matrix = Matrix().apply {
        postRotate(t.rotationDegrees.toFloat())
        if (t.mirror) postScale(-1f, 1f)
    }
    return Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, true).also { if (it !== decoded) decoded.recycle() }
}
