package com.asseta.owner.ui.common

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

/**
 * Evidence photo from a short-lived presigned URL, loaded on demand into memory only (never written to disk or the
 * offline cache). The URL already authorizes the download, so no Asseta headers are sent with it.
 */
object EvidenceImages {
    private val client by lazy { OkHttpClient() }
    private const val MAX_BYTES = 15L * 1024 * 1024

    suspend fun load(url: String): Bitmap? = withContext(Dispatchers.IO) {
        runCatching {
            client.newCall(Request.Builder().url(url).build()).execute().use { response ->
                val body = response.body
                if (!response.isSuccessful || body.contentLength() > MAX_BYTES) return@use null
                val bytes = body.bytes()
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                var sample = 1
                while (bounds.outWidth / sample > 2048 || bounds.outHeight / sample > 2048) sample *= 2
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
            }
        }.getOrNull()
    }
}

@Composable
fun RemoteImage(url: String, description: String) {
    val bitmap by produceState<Result<Bitmap?>?>(null, url) { value = runCatching { EvidenceImages.load(url) } }
    when (val b = bitmap) {
        null -> CircularProgressIndicator()
        else -> b.getOrNull()?.let {
            Image(it.asImageBitmap(), description, Modifier.fillMaxWidth().heightIn(max = 360.dp), contentScale = ContentScale.Fit)
        } ?: Text("The photo could not be loaded.", color = MaterialTheme.colorScheme.error)
    }
}
