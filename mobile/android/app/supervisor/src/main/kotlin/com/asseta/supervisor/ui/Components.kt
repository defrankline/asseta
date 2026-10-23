package com.asseta.supervisor.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

/** Orange used for warnings and "not verified" amounts (the iOS `.orange`). */
val WarningColor = Color(0xFFB25E00)

/** A titled card with an optional footer (the iOS grouped `Section(header:footer:)`). */
@Composable
fun Section(title: String?, footer: String? = null, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (title != null) {
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    HorizontalDivider()
                }
                content()
            }
        }
        footer?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp))
        }
    }
}

/** A tappable row inside a [Section] (the iOS list `Button`). */
@Composable
fun ActionRow(title: String, enabled: Boolean = true, onClick: () -> Unit) {
    Text(
        title,
        style = MaterialTheme.typography.bodyLarge,
        color = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f),
        modifier = Modifier.fillMaxWidth().clickable(enabled = enabled, onClick = onClick).padding(vertical = 8.dp),
    )
}

/** Label on the left, value on the right (the iOS `LabeledContent`). */
@Composable
fun LabeledRow(label: String, value: String, valueColor: Color = Color.Unspecified, content: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        if (content != null) content() else {
            Text(value, style = MaterialTheme.typography.bodyLarge, color = if (valueColor == Color.Unspecified) MaterialTheme.colorScheme.onSurfaceVariant else valueColor,
                textAlign = TextAlign.End)
        }
    }
}

@Composable
fun NoticeCard(title: String, body: String, isError: Boolean = false) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            Text(body, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** "Not saved" alert with the refusal message (the iOS `.alert("Not saved")`). */
@Composable
fun NotSavedAlert(message: String?, onDismiss: () -> Unit) {
    if (message == null) return
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Not saved") },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = onDismiss) { Text("OK") } },
    )
}

/** Device-local display of device timestamps (stored and sent as UTC ISO-8601), localized like the iOS formatters. */
object LocalTime {
    private val dateTime = DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT).withZone(ZoneId.systemDefault())
    private val dateTimeSeconds = DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.MEDIUM).withZone(ZoneId.systemDefault())
    private val time = DateTimeFormatter.ofPattern("HH:mm").withZone(ZoneId.systemDefault())

    /** Abbreviated date + short time ("Oct 23, 2026, 9:41 AM"). */
    fun format(epochMs: Long): String = dateTime.format(Instant.ofEpochMilli(epochMs))

    /** Abbreviated date + time with seconds (recorded-at lines of operations). */
    fun formatSeconds(epochMs: Long): String = dateTimeSeconds.format(Instant.ofEpochMilli(epochMs))

    fun formatTime(epochMs: Long): String = time.format(Instant.ofEpochMilli(epochMs))

    /** A server ISO-8601 instant (e.g. planned start), or the raw text when it cannot be parsed. */
    fun formatIso(iso: String): String = runCatching { format(Instant.parse(iso).toEpochMilli()) }.getOrDefault(iso)
}
