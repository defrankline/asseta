package com.asseta.supervisor.ui

import androidx.annotation.DrawableRes
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.R
import com.asseta.core.ui.R as CoreR
import com.asseta.core.ui.components.EmptyState as CoreEmptyState
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

/** Amber used for warnings and "not verified" amounts (the iOS `Palette.warning`); adapts to light and dark. */
val WarningColor: Color @Composable @ReadOnlyComposable get() = palette.warning

/**
 * An inset-grouped section (the iOS `Section(header:footer:)` in a `List`/`Form`): uppercase [title] above a rounded
 * group whose children are rows separated by hairlines, [footer] below. Screens pad their content by 16 dp.
 */
@Composable
fun Section(title: String?, footer: String? = null, content: @Composable () -> Unit) {
    GroupedSection(header = title, footer = footer, margin = 0.dp, spacingAfter = 12.dp, content = content)
}

/** A tappable row inside a [Section] (the iOS list `Button`, optionally a `Label` with a symbol). */
@Composable
fun ActionRow(title: String, @DrawableRes icon: Int? = null, enabled: Boolean = true, onClick: () -> Unit) {
    ButtonRow(title, enabled = enabled, icon = icon, onClick = onClick)
}

/** A row that opens another screen, with a trailing chevron (the iOS `NavigationLink` in a list). */
@Composable
fun LinkActionRow(title: String, @DrawableRes icon: Int? = null, onClick: () -> Unit) {
    NavigationRow(title, icon = icon, onClick = onClick)
}

/** Label on the left, value on the right (the iOS `LabeledContent`). */
@Composable
fun LabeledRow(label: String, value: String, valueColor: Color = Color.Unspecified, content: (@Composable () -> Unit)? = null) {
    LabeledValue(label, value, valueColor, trailing = content)
}

/** Unavailable screen content: symbol, title and explanation (the iOS `ContentUnavailableView`). */
@Composable
fun NoticeCard(title: String, body: String, isError: Boolean = false) {
    CoreEmptyState(title, body, icon = if (isError) R.drawable.ic_warning else CoreR.drawable.ic_empty_tray)
}

/** Empty list or record: symbol, title and a short explanation (the iOS `ContentUnavailableView`). */
@Composable
fun EmptyState(title: String, message: String, @DrawableRes icon: Int = CoreR.drawable.ic_empty_tray) {
    CoreEmptyState(title, message, icon = icon)
}

/** What the navigation bar of a form shows on the right: "Save", enabled or not (the iOS sheet's confirmation action). */
class FormSave(val enabled: Boolean, val onSave: () -> Unit)

/** Holder the shell reads to draw a form's "Save" bar button; forms publish into it with [FormSaveAction]. */
@Stable
class FormBarState {
    var save by mutableStateOf<FormSave?>(null)
}

val LocalFormBar = staticCompositionLocalOf<FormBarState?> { null }

/**
 * Puts the form's "Save" in the navigation bar (as the iOS sheets do), or draws a full-width button when the form is
 * shown outside the shell.
 */
@Composable
fun FormSaveAction(enabled: Boolean, saving: Boolean = false, onSave: () -> Unit) {
    val bar = LocalFormBar.current
    val latest by rememberUpdatedState(onSave)
    if (bar == null) {
        Button(onClick = onSave, enabled = enabled && !saving, modifier = Modifier.fillMaxWidth()) { Text(if (saving) "Saving…" else "Save") }
        return
    }
    val enabledNow = enabled && !saving
    SideEffect { if (bar.save?.enabled != enabledNow || bar.save == null) bar.save = FormSave(enabledNow) { latest() } }
    DisposableEffect(bar) { onDispose { bar.save = null } }
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
    private val timeSeconds = DateTimeFormatter.ofLocalizedTime(FormatStyle.MEDIUM).withZone(ZoneId.systemDefault())

    /** Abbreviated date + short time ("Oct 23, 2026, 9:41 AM"). */
    fun format(epochMs: Long): String = dateTime.format(Instant.ofEpochMilli(epochMs))

    /** Abbreviated date + time with seconds (recorded-at lines of operations). */
    fun formatSeconds(epochMs: Long): String = dateTimeSeconds.format(Instant.ofEpochMilli(epochMs))

    fun formatTime(epochMs: Long): String = time.format(Instant.ofEpochMilli(epochMs))

    /** Time of day with seconds ("9:41:07 AM"), like iOS `.standard` time (next automatic retry). */
    fun formatTimeSeconds(epochMs: Long): String = timeSeconds.format(Instant.ofEpochMilli(epochMs))

    /** A server ISO-8601 instant (e.g. planned start), or the raw text when it cannot be parsed. */
    fun formatIso(iso: String): String = runCatching { format(Instant.parse(iso).toEpochMilli()) }.getOrDefault(iso)
}
