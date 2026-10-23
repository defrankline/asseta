package com.asseta.supervisor.capture

import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

fun Context.hasAllPermissions(permissions: Array<String>): Boolean =
    permissions.all { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }

fun Context.hasAnyPermission(permissions: Array<String>): Boolean =
    permissions.any { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }

/**
 * Just-in-time permission request with a rationale shown first. [onResult] receives whether at least one requested
 * permission was granted (for location, "approximate" still allows an honest, less accurate attempt). A denial is a
 * normal outcome, never a crash.
 */
@Composable
fun PermissionRationale(
    title: String,
    rationale: String,
    permissions: Array<String>,
    onResult: (granted: Boolean) -> Unit,
    modifier: Modifier = Modifier,
    declineLabel: String? = null,
) {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        onResult(result.values.any { it })
    }
    // A grouped-list cell (as the iOS forms), so it sits on the grouped background like the sections around it.
    Box(modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(palette.cell)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = AssetaType.headline)
            Text(rationale, style = MaterialTheme.typography.bodyMedium, color = palette.secondaryText)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { launcher.launch(permissions) }) { Text("Allow") }
                if (declineLabel != null) TextButton(onClick = { onResult(false) }) { Text(declineLabel) }
            }
        }
    }
}
