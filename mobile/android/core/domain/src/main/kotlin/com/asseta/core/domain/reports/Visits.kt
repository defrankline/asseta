package com.asseta.core.domain.reports

import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Where a machine's reading was taken: the phone geocoder's label, the company site, the GPS fix. */
data class VisitPlace(
    val place: String?,
    val site: String?,
    val lat: Double?,
    val lng: Double?,
    val accuracyM: Double?,
)

/*
 * ADR-008: time since the machine's last visit and where the readings were taken. Same wording and format as iOS
 * `Visits` and web `visits.ts` (docs/adr/ADR-008-machine-reports-replace-jobs.md).
 */
object Visits {
    const val FIRST_VISIT = "First visit"
    const val MAX_PLACE = 200

    /**
     * The gap between two visits, whole units truncated from [seconds]: null → "First visit"; under 1 hour "45 min";
     * under 24 hours "5 h 20 min" ("5 h" when the minutes are 0); else "1 day 3 h", "2 days" (minutes dropped).
     */
    fun duration(seconds: Long?): String {
        seconds ?: return FIRST_VISIT
        val s = seconds.coerceAtLeast(0)
        val minutes = s / 60
        val hours = s / 3600
        return when {
            hours < 1 -> "$minutes min"
            hours < 24 -> "$hours h" + (minutes % 60).let { if (it > 0) " $it min" else "" }
            else -> {
                val days = hours / 24
                val h = hours % 24
                "$days ${if (days == 1L) "day" else "days"}" + if (h > 0) " $h h" else ""
            }
        }
    }

    /** Seconds from [fromIso] to [toMs]; null when [fromIso] is null or unreadable. */
    fun secondsBetween(fromIso: String?, toMs: Long): Long? =
        parse(fromIso)?.let { (toMs - it.toEpochMilli()).coerceAtLeast(0) / 1000 }

    /** A visit's date and time: "17 Nov, 15:26" (device local time, 24 h). */
    fun dateTime(iso: String, zone: ZoneId = ZoneId.systemDefault()): String =
        parse(iso)?.atZone(zone)?.format(DateTimeFormatter.ofPattern("d MMM, HH:mm", Locale.ENGLISH)) ?: iso

    /** "Since last visit: 1 day 3 h" (report detail, approvals). */
    fun sinceLastVisit(seconds: Long?): String = "Since last visit: ${duration(seconds)}"

    /** "Time since last visit: 1 day 3 h (last visit 17 Nov, 15:26)" / "Time since last visit: First visit". */
    fun timeSinceLastVisit(lastVisitAt: String?, nowMs: Long, zone: ZoneId = ZoneId.systemDefault()): String {
        val seconds = secondsBetween(lastVisitAt, nowMs)
        return "Time since last visit: ${duration(seconds)}" + if (seconds != null && lastVisitAt != null) " (last visit ${dateTime(lastVisitAt, zone)})" else ""
    }

    /**
     * `Where: {place} (at {site}) · {lat}, {lng} (±{acc} m)`; null parts are left out; null when there are no
     * coordinates (no Where line at all).
     */
    fun where(p: VisitPlace): String? {
        val lat = p.lat ?: return null
        val lng = p.lng ?: return null
        val place = p.place?.trim()?.takeIf { it.isNotEmpty() }
        val site = p.site?.trim()?.takeIf { it.isNotEmpty() }?.let { "at $it" }
        val label = when {
            place != null && site != null -> "$place ($site)"
            else -> place ?: site
        }
        val coords = "${coord(lat)}, ${coord(lng)}" + (p.accuracyM?.let { " (±${Math.round(it)} m)" } ?: "")
        return "Where: " + listOfNotNull(label, coords).joinToString(" · ")
    }

    /** "Last visit: 17 Nov, 15:26 · Where: …" (the previous visit on a report detail); null when there is none. */
    fun lastVisit(at: String?, p: VisitPlace, zone: ZoneId = ZoneId.systemDefault()): String? {
        at ?: return null
        return "Last visit: ${dateTime(at, zone)}" + (where(p)?.let { " · $it" } ?: "")
    }

    /** The maps app at the coordinates (Android geo: intent). */
    fun geoUri(lat: Double, lng: Double): String = "geo:${coord(lat)},${coord(lng)}?q=${coord(lat)},${coord(lng)}"

    /**
     * An area label from a geocoder's parts: neighbourhood / sub-locality, district (sub-admin area), city / locality --
     * missing parts skipped, equal parts once, never a street address; at most 200 characters; null when empty.
     */
    fun placeLabel(subLocality: String?, district: String?, locality: String?): String? {
        val parts = mutableListOf<String>()
        listOf(subLocality, district, locality).forEach { raw ->
            val p = raw?.trim().orEmpty()
            if (p.isNotEmpty() && parts.none { it.equals(p, ignoreCase = true) }) parts += p
        }
        return parts.joinToString(", ").take(MAX_PLACE).trim().ifEmpty { null }
    }

    /** True when the visit took longer than the company's warning hours (null = never flagged). */
    fun gapFlagged(seconds: Long?, warningHours: Int?): Boolean =
        seconds != null && warningHours != null && seconds > warningHours.toLong() * 3600

    private fun coord(v: Double): String = String.format(Locale.US, "%.4f", v)

    private fun parse(iso: String?): Instant? = iso?.let {
        runCatching { OffsetDateTime.parse(it).toInstant() }.getOrNull() ?: runCatching { Instant.parse(it) }.getOrNull()
    }
}
