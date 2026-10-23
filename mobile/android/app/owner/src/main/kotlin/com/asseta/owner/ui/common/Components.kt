package com.asseta.owner.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.ui.session.UiError
import com.asseta.owner.data.Snapshot
import java.time.ZoneId

/** Test tag of the stale banner (Compose UI tests). */
const val STALE_BANNER_TAG = "stale_banner"

/** Device connectivity for the open company's screens (provided by the owner shell). */
val LocalOnline = staticCompositionLocalOf { false }

/**
 * Prominent banner for cached data: "Offline — data from <time> (stale)", or "Can't reach Asseta — …" when the device
 * is online but the server is not. Announced by TalkBack.
 */
@Composable
fun StaleBanner(snapshot: Snapshot<*>?, zone: ZoneId = ZoneId.systemDefault(), online: Boolean = LocalOnline.current) {
    if (snapshot == null || !snapshot.stale) return
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        modifier = Modifier.fillMaxWidth().testTag(STALE_BANNER_TAG).semantics { liveRegion = LiveRegionMode.Polite },
    ) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
            Text(OwnerFormat.staleBanner(snapshot.fetchedAtMs, zone, online), style = MaterialTheme.typography.titleSmall)
            Text("Saved on this device. Actions are disabled until you are back online.", style = MaterialTheme.typography.bodySmall)
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
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Can't load this", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
        error?.let { ErrorLine(it) }
        Button(onClick = onRetry) { Text("Try again") }
    }
}

/** Empty list: a title and a short explanation (iOS `ContentUnavailableView` wording). */
@Composable
fun EmptyState(title: String, message: String? = null) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 24.dp).semantics(mergeDescendants = true) {},
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        message?.let {
            Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }
    }
}

/** Grey explanatory text under a section (iOS section footer). */
@Composable
fun FootNote(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
fun ErrorLine(error: UiError) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp).semantics { liveRegion = LiveRegionMode.Polite }) {
        Text(error.message, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Start)
        error.reference?.let { Text("Reference: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    Text(text, style = MaterialTheme.typography.titleMedium, modifier = modifier.semantics { heading() })
}

/** Card with a heading and an optional "Updated …" freshness line for that section. */
@Composable
fun SectionCard(title: String, freshness: String? = null, content: @Composable () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            SectionTitle(title)
            freshness?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            content()
        }
    }
}

@Composable
fun KeyValue(label: String, value: String) {
    Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.End, modifier = Modifier.weight(1f))
    }
}

/** Small status pill with a text label (colour is never the only signal). */
@Composable
fun StatusPill(label: String, color: Color) {
    Surface(color = color.copy(alpha = 0.18f), contentColor = MaterialTheme.colorScheme.onSurface, shape = MaterialTheme.shapes.small) {
        Text(label, style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp))
    }
}

/** Marker / pill colours per connectivity (also used for the map's circle layer). */
object OwnerColors {
    val Live = Color(0xFF2E7D32)
    val Recent = Color(0xFF0277BD)
    val Stale = Color(0xFFF5A300)
    val Offline = Color(0xFFB3261E)
    val Neutral = Color(0xFF6B7780)
    val Critical = Color(0xFFB3261E)
    val Warning = Color(0xFFF5A300)
    val Info = Color(0xFF0277BD)

    fun connectivity(c: Connectivity): Color = when (c) {
        Connectivity.LIVE -> Live
        Connectivity.RECENT -> Recent
        Connectivity.STALE -> Stale
        Connectivity.OFFLINE -> Offline
        else -> Neutral
    }

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
