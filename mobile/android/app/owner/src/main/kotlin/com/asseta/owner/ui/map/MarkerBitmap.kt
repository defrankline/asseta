package com.asseta.owner.ui.map

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.ui.graphics.toArgb
import androidx.core.content.ContextCompat
import com.asseta.owner.R

/**
 * Draws a machine marker as one bitmap, matching the iOS Owner app: a coloured circle with a white truck, a dashed ring
 * when the position is not live (colour is not the only cue), a red open-alert badge and the asset code underneath.
 * Drawn locally so the map needs no glyph/font server for labels.
 */
internal object MarkerBitmap {
    private const val CIRCLE_DP = 36f
    private const val BADGE_DP = 18f
    private const val LABEL_SP = 12f

    /** Distance (dp) from the bitmap's top edge to the circle centre: the map anchors the marker there. */
    const val CENTER_FROM_TOP_DP = BADGE_DP / 2 + CIRCLE_DP / 2

    fun imageId(m: MapMarker): String = "marker:${m.color.toArgb()}:${m.live}:${m.alerts}:${m.code}"

    fun draw(context: Context, m: MapMarker): Bitmap {
        val d = context.resources.displayMetrics.density
        val label = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = LABEL_SP * context.resources.displayMetrics.scaledDensity
            typeface = Typeface.DEFAULT_BOLD
            textAlign = Paint.Align.CENTER
        }
        val radius = CIRCLE_DP / 2 * d
        val badge = BADGE_DP / 2 * d
        val top = badge // room for the badge above the circle
        val width = maxOf(2 * radius + 2 * badge, label.measureText(m.code) + 8 * d)
        val height = top + 2 * radius + 4 * d + label.textSize + 4 * d
        val bitmap = Bitmap.createBitmap(width.toInt() + 1, height.toInt() + 1, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val cx = width / 2
        val cy = top + radius

        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = m.color.toArgb() }
        canvas.drawCircle(cx, cy, radius, fill)
        val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = 2 * d; color = android.graphics.Color.WHITE }
        canvas.drawCircle(cx, cy, radius - d, ring)
        if (!m.live) {
            ring.color = 0x990F2A3D.toInt()
            ring.pathEffect = DashPathEffect(floatArrayOf(3 * d, 3 * d), 0f)
            canvas.drawCircle(cx, cy, radius - d, ring)
        }
        ContextCompat.getDrawable(context, R.drawable.ic_marker_truck)?.let { truck ->
            val half = (radius * 0.55f).toInt()
            truck.setBounds((cx - half).toInt(), (cy - half).toInt(), (cx + half).toInt(), (cy + half).toInt())
            truck.draw(canvas)
        }
        if (m.alerts > 0) {
            val bx = cx + radius * 0.75f
            val by = cy - radius * 0.75f
            canvas.drawCircle(bx, by, badge, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFD32F2F.toInt() })
            val count = Paint(label).apply { color = android.graphics.Color.WHITE; textSize = badge * 1.1f }
            canvas.drawText(if (m.alerts > 99) "99+" else m.alerts.toString(), bx, by - (count.ascent() + count.descent()) / 2, count)
        }
        val baseline = cy + radius + 4 * d - label.ascent()
        val halo = Paint(label).apply { style = Paint.Style.STROKE; strokeWidth = 3 * d; color = android.graphics.Color.WHITE }
        canvas.drawText(m.code, cx, baseline, halo)
        canvas.drawText(m.code, cx, baseline, label.apply { color = 0xFF0F2A3D.toInt() })
        return bitmap
    }
}
