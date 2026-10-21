package com.asseta.supervisor.ui

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.core.graphics.createBitmap
import java.io.ByteArrayOutputStream

/** Strokes drawn on the pad, in pad pixels; rendered to PNG for upload (purpose SIGNATURE). */
class SignatureState {
    val strokes = mutableStateListOf<List<Offset>>()
    internal val current = mutableStateListOf<Offset>()
    internal var size: IntSize = IntSize.Zero
    val isEmpty: Boolean get() = strokes.isEmpty() && current.isEmpty()

    fun clear() { strokes.clear(); current.clear() }

    /** Black strokes on white, PNG-encoded at the pad's pixel size. */
    fun toPng(): ByteArray? {
        if (isEmpty || size.width <= 0 || size.height <= 0) return null
        val bitmap = createBitmap(size.width, size.height)
        val canvas = Canvas(bitmap).apply { drawColor(android.graphics.Color.WHITE) }
        val paint = Paint().apply {
            color = android.graphics.Color.BLACK; strokeWidth = 6f; style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND; isAntiAlias = true
        }
        (strokes + listOf(current.toList())).forEach { s ->
            s.zipWithNext().forEach { (a, b) -> canvas.drawLine(a.x, a.y, b.x, b.y, paint) }
        }
        return ByteArrayOutputStream().use { out -> bitmap.compress(Bitmap.CompressFormat.PNG, 100, out); out.toByteArray() }
    }
}

@Composable
fun rememberSignatureState() = remember { SignatureState() }

@Composable
fun SignaturePad(state: SignatureState, modifier: Modifier = Modifier) {
    Canvas(
        modifier.fillMaxWidth().height(180.dp).background(Color.White).border(1.dp, Color.Gray)
            .onSizeChanged { state.size = it }
            .pointerInput(state) {
                detectDragGestures(
                    onDragStart = { state.current.clear(); state.current.add(it) },
                    onDrag = { change, _ -> state.current.add(change.position) },
                    onDragEnd = { state.strokes.add(state.current.toList()); state.current.clear() },
                )
            },
    ) {
        (state.strokes + listOf(state.current.toList())).forEach { s ->
            s.zipWithNext().forEach { (a, b) -> drawLine(Color.Black, a, b, strokeWidth = 6f, cap = StrokeCap.Round) }
        }
    }
}
