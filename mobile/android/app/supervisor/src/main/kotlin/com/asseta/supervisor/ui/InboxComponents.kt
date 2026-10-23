package com.asseta.supervisor.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.domain.inbox.Tone
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

/** Colour of a status tone (same mapping as iOS `InboxStatus.color`). */
@Composable
fun toneColor(tone: Tone): Color {
    val p = palette
    return when (tone) {
        Tone.NEUTRAL -> p.neutral
        Tone.GOOD -> p.live
        Tone.WARNING -> p.warning
        Tone.BAD -> p.offline
        Tone.INFO -> p.recent
    }
}

/** The one combined status pill of a record. */
@Composable
fun StatusPill(status: InboxStatus) = Pill(status.label, toneColor(status.tone))

/** A list row: title and status pill on the first line, grey detail lines below (iOS `InboxRow`). */
@Composable
fun InboxRow(title: String, status: InboxStatus?, vararg lines: String?) {
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = AssetaType.headline, modifier = Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
            status?.let { StatusPill(it) }
        }
        lines.filterNotNull().filter { it.isNotBlank() }.forEach {
            Text(it, style = AssetaType.subheadline, color = palette.secondaryText, maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** Evidence photo: the local encrypted copy when this phone has it, else the server copy when online and allowed. */
@Composable
fun EvidenceImage(description: String, local: (suspend () -> ByteArray?)?, remoteUrl: (suspend () -> String?)?) {
    val state by produceState<Pair<Boolean, Bitmap?>>(false to null, description) {
        val bytes = local?.invoke()
        val bitmap = bytes?.let { decode(it) } ?: remoteUrl?.invoke()?.let { url -> download(url)?.let { decode(it) } }
        value = true to bitmap
    }
    val (done, bitmap) = state
    when {
        !done -> CircularProgressIndicator(Modifier.padding(8.dp))
        bitmap != null -> Image(bitmap.asImageBitmap(), description, Modifier.fillMaxWidth().heightIn(max = 320.dp), contentScale = ContentScale.Fit)
        else -> Text("The photo is not on this phone. Connect to view it.", style = AssetaType.footnote, color = palette.secondaryText)
    }
}

private const val MAX_BYTES = 15L * 1024 * 1024
private val imageClient by lazy { OkHttpClient() }

/** Downloads a short-lived presigned URL into memory only (never written to disk). */
private suspend fun download(url: String): ByteArray? = withContext(Dispatchers.IO) {
    runCatching {
        imageClient.newCall(Request.Builder().url(url).build()).execute().use { r ->
            if (!r.isSuccessful || r.body.contentLength() > MAX_BYTES) null else r.body.bytes()
        }
    }.getOrNull()
}

private suspend fun decode(bytes: ByteArray): Bitmap? = withContext(Dispatchers.Default) {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    var sample = 1
    while (bounds.outWidth / sample > 2048 || bounds.outHeight / sample > 2048) sample *= 2
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
}
