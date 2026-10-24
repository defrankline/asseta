package com.asseta.owner.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.session.UiError
import com.asseta.core.ui.theme.AssetaColors
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.Snapshot
import com.asseta.owner.ui.home.KpiTone
import java.time.ZoneId
import com.asseta.core.ui.R as CoreR
import com.asseta.core.ui.components.EmptyState as CoreEmptyState

/** Test tag of the stale banner (Compose UI tests). */
const val STALE_BANNER_TAG = "stale_banner"

/** Device connectivity for the open company's screens (provided by the owner shell). */
val LocalOnline = staticCompositionLocalOf { false }

/**
 * Prominent amber banner for cached data (same as iOS `StaleBanner`): "Offline — data from <time> (stale)", or
 * "Can't reach Asseta — …" when the device is online but the server is not. Announced by TalkBack.
 */
@Composable
fun StaleBanner(snapshot: Snapshot<*>?, zone: ZoneId = ZoneId.systemDefault(), online: Boolean = LocalOnline.current) {
    if (snapshot == null || !snapshot.stale) return
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)
            .background(AssetaColors.Amber, RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .testTag(STALE_BANNER_TAG).semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite },
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(painterResource(CoreR.drawable.ic_cloud_off), contentDescription = null, tint = AssetaColors.Slate, modifier = Modifier.size(20.dp))
        Column {
            Text(OwnerFormat.staleBanner(snapshot.fetchedAtMs, zone, online), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold, color = AssetaColors.Slate)
            Text("Saved on this device. Actions are disabled until you are back online.", style = AssetaType.caption, color = AssetaColors.Slate)
        }
    }
}

/** Standard body: progress, error with retry, or [content] (with the stale banner and any refresh error on top). */
@Composable
fun <T> SnapshotScaffold(state: ScreenState<T>, onRetry: () -> Unit, modifier: Modifier = Modifier, content: @Composable (T) -> Unit) {
    Column(modifier.fillMaxSize()) {
        StaleBanner(state.snapshot)
        if (state.loading && state.snapshot != null) LinearProgressIndicator(Modifier.fillMaxWidth())
        val data = state.data
        when {
            data != null -> {
                state.error?.let { ErrorLine(it) }
                content(data)
            }
            state.loading -> Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator(Modifier.semantics { contentDescription = "Loading" })
            }
            else -> LoadFailure(state.error, onRetry)
        }
    }
}

/** Nothing (not even cache) can be shown: "Can't load this", the reason and "Try again" (same as iOS). */
@Composable
fun LoadFailure(error: UiError?, onRetry: () -> Unit) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center) {
        CoreEmptyState(
            "Can't load this",
            listOfNotNull(error?.message, error?.reference?.let { "Reference: $it" }).joinToString("\n").ifEmpty { null },
            icon = CoreR.drawable.ic_cloud_off,
        ) { Button(onClick = onRetry) { Text("Try again") } }
    }
}

/** Empty list or record: symbol, title and a short explanation (iOS `ContentUnavailableView`, same wording). */
@Composable
fun EmptyState(title: String, message: String? = null, icon: Int = CoreR.drawable.ic_empty_tray) = CoreEmptyState(title, message, icon)

/** Grey explanatory text (iOS footnote). */
@Composable
fun FootNote(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
}

/** Why an action is disabled, with a lock (iOS `BlockedNote`). */
@Composable
fun BlockedNote(reason: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(painterResource(R.drawable.ic_lock), contentDescription = null, tint = palette.secondaryText, modifier = Modifier.size(16.dp))
        FootNote(reason)
    }
}

@Composable
fun ErrorLine(error: UiError) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp).semantics { liveRegion = LiveRegionMode.Polite }) {
        Text(error.message, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Start)
        error.reference?.let { Text("Reference: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
    }
}

/**
 * An inset-grouped section (iOS `Section(header:footer:)` in a `List`/`Form`): uppercase [title] above the group,
 * each child a row with separators, [footer] below. [freshness] is shown as the first, grey row.
 */
@Composable
fun SectionCard(title: String?, freshness: String? = null, footer: String? = null, content: @Composable () -> Unit) {
    GroupedSection(header = title, footer = footer) {
        freshness?.let { FootNote(it) }
        content()
    }
}

/** Label with its grey value (iOS `LabeledContent`). */
@Composable
fun KeyValue(label: String, value: String) = LabeledValue(label, value)

/** Small status pill with a text label (colour is never the only signal). */
@Composable
fun StatusPill(label: String, color: Color) = Pill(label, color)

/** Marker / pill / figure colours, the same values as iOS (`Palette` in AssetaAppShell); adapt to light and dark. */
object OwnerColors {
    val Live: Color @Composable @ReadOnlyComposable get() = palette.live
    val Recent: Color @Composable @ReadOnlyComposable get() = palette.recent
    val Stale: Color @Composable @ReadOnlyComposable get() = palette.stale
    val Offline: Color @Composable @ReadOnlyComposable get() = palette.offline
    val Neutral: Color @Composable @ReadOnlyComposable get() = palette.neutral
    val Critical: Color @Composable @ReadOnlyComposable get() = palette.critical
    val Warning: Color @Composable @ReadOnlyComposable get() = palette.warning
    val Info: Color @Composable @ReadOnlyComposable get() = palette.info

    @Composable @ReadOnlyComposable
    fun connectivity(c: Connectivity): Color = when (c) {
        Connectivity.LIVE -> Live
        Connectivity.RECENT -> Recent
        Connectivity.STALE -> Stale
        Connectivity.OFFLINE -> Offline
        else -> Neutral
    }

    /** Pill colour of a presentation tone (NORMAL and MUTED are grey). */
    @Composable @ReadOnlyComposable
    fun tone(t: KpiTone): Color = when (t) {
        KpiTone.GOOD -> Live
        KpiTone.WARNING -> Warning
        KpiTone.CRITICAL -> Critical
        KpiTone.NORMAL, KpiTone.MUTED -> Neutral
    }

    @Composable @ReadOnlyComposable
    fun severity(raw: String): Color = when (raw) {
        "CRITICAL" -> Critical
        "WARNING" -> Warning
        else -> Info
    }
}

/** "Updated 5 min ago" for a section's newest source record. */
fun freshnessLine(latestSourceAt: String?, nowMs: Long): String {
    val at = OwnerFormat.parseInstant(latestSourceAt) ?: return "No source data yet"
    return "Source data updated ${com.asseta.core.domain.owner.Freshness.ageLabel(com.asseta.core.domain.owner.Freshness.ageSeconds(at.toEpochMilli(), nowMs))}"
}
