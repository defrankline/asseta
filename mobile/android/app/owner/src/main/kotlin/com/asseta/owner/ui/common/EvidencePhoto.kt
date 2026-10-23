package com.asseta.owner.ui.common

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import com.asseta.core.model.owner.PhotoUrlDto
import com.asseta.owner.data.ActionResult
import kotlinx.coroutines.launch

/** "View photo" button: requests a presigned URL only when tapped (online only) and shows the image in memory. */
@Composable
fun EvidencePhoto(label: String, online: Boolean, fetchUrl: suspend () -> ActionResult<PhotoUrlDto>) {
    val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    Column {
        val shown = url
        if (shown != null) {
            RemoteImage(shown, label)
        } else {
            OutlinedButton(
                enabled = online && !busy,
                onClick = {
                    busy = true
                    scope.launch {
                        when (val r = fetchUrl()) {
                            is ActionResult.Done -> url = r.value.url
                            is ActionResult.Refused -> error = r.error.message
                        }
                        busy = false
                    }
                },
            ) { Text(if (online) "View $label" else "${label.replaceFirstChar { it.uppercase() }} (online only)") }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
    }
}
