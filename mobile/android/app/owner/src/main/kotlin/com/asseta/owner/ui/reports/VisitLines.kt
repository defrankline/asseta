package com.asseta.owner.ui.reports

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.asseta.core.domain.reports.VisitPlace
import com.asseta.core.domain.reports.Visits
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.ui.theme.palette

/** Opens the maps app at the coordinates (geo: intent); nothing happens when no app can show a map. */
private fun openMap(context: Context, lat: Double, lng: Double) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Visits.geoUri(lat, lng))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
        // No maps app on this phone.
    }
}

/**
 * The report's visit lines: "Since last visit: 1 day 3 h" (warning colour over the company's hours), "Where: …" of
 * this report's reading and "Last visit: 17 Nov, 15:26 · Where: …"; tapping a Where line opens the maps app.
 */
@Composable
fun VisitLines(r: MachineReportDto, flagged: Boolean) {
    Column(Modifier.padding(top = 8.dp)) {
        Text(ReportPresentation.sinceLastVisit(r), fontSize = 14.sp, color = if (flagged) palette.warning else palette.secondaryText)
        WhereText(ReportPresentation.visit(r), ReportPresentation.where(r))
        WhereText(ReportPresentation.previousVisit(r), ReportPresentation.lastVisit(r))
    }
}

@Composable
private fun WhereText(place: VisitPlace, text: String?) {
    text ?: return
    val lat = place.lat
    val lng = place.lng
    val context = LocalContext.current
    val tappable = lat != null && lng != null
    Text(
        text, fontSize = 13.sp, color = if (tappable) palette.accent else palette.secondaryText,
        modifier = Modifier.padding(top = 2.dp).let { m -> if (tappable) m.clickable { openMap(context, lat, lng) } else m },
    )
}
