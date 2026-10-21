package com.asseta.supervisor.capture

import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner

/** A photo exactly as the camera encoded it (original JPEG bytes) plus the rotation needed to view it upright. */
class CapturedPhoto(val jpeg: ByteArray, val rotationDegrees: Int, val takenAtMs: Long)

/**
 * In-app CameraX capture into memory: the JPEG never touches unencrypted storage; the caller encrypts it as is.
 */
@Composable
fun CameraCapture(buttonLabel: String, onCaptured: (CapturedPhoto) -> Unit, onError: (String) -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var busy by remember { mutableStateOf(false) }
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    .setResolutionStrategy(ResolutionStrategy(Size(1920, 1440), ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER))
                    .build(),
            )
            .setJpegQuality(92)
            .build()
    }
    val previewView = remember { PreviewView(context) }
    DisposableEffect(lifecycleOwner) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            runCatching {
                val provider = future.get()
                val preview = Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture)
            }.onFailure { onError("Camera unavailable: ${it.message}") }
        }, ContextCompat.getMainExecutor(context))
        onDispose { runCatching { future.get().unbindAll() } }
    }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.fillMaxWidth().aspectRatio(4f / 3f)) { AndroidView({ previewView }, Modifier.fillMaxWidth().aspectRatio(4f / 3f)) }
        Button(
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                busy = true
                imageCapture.takePicture(
                    ContextCompat.getMainExecutor(context),
                    object : ImageCapture.OnImageCapturedCallback() {
                        override fun onCaptureSuccess(image: ImageProxy) {
                            val photo = image.use {
                                val buffer = it.planes[0].buffer
                                val bytes = ByteArray(buffer.remaining()).also(buffer::get)
                                CapturedPhoto(bytes, it.imageInfo.rotationDegrees, System.currentTimeMillis())
                            }
                            busy = false
                            onCaptured(photo)
                        }

                        override fun onError(exception: ImageCaptureException) {
                            busy = false
                            onError("Photo failed: ${exception.message}")
                        }
                    },
                )
            },
        ) {
            if (busy) CircularProgressIndicator(Modifier.aspectRatio(1f)) else Text(buttonLabel)
        }
    }
}
