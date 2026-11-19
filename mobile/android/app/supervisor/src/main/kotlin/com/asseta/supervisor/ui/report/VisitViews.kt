package com.asseta.supervisor.ui.report

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.asseta.core.domain.reports.VisitPlace
import com.asseta.core.domain.reports.Visits
import com.asseta.core.ui.theme.palette

/** Opens the maps app at the coordinates (geo: intent); nothing happens when no app can show a map. */
fun openMap(context: Context, lat: Double, lng: Double) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Visits.geoUri(lat, lng))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
        // No maps app on this phone.
    }
}

/** A "Where: …" line (or "Last visit: … · Where: …" with [text]); tapping it opens the maps app. Nothing without coordinates. */
@Composable
fun WhereLine(place: VisitPlace, modifier: Modifier = Modifier, text: String? = Visits.where(place)) {
    text ?: return
    val lat = place.lat
    val lng = place.lng
    val context = LocalContext.current
    Text(
        text, style = MaterialTheme.typography.bodySmall, color = if (lat != null && lng != null) palette.accent else palette.secondaryText,
        modifier = if (lat != null && lng != null) modifier.clickable { openMap(context, lat, lng) } else modifier,
    )
}
