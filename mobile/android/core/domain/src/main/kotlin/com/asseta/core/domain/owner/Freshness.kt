package com.asseta.core.domain.owner

/** Where a screen's data came from: a live server response or the encrypted offline snapshot. */
enum class DataSource { LIVE, CACHE }

/** Server connectivity dimension of a machine (`Connectivity` in the contract); unknown values fail safe. */
enum class Connectivity(val wire: String, val label: String) {
    LIVE("LIVE", "Live"),
    RECENT("RECENT", "Recent"),
    STALE("STALE", "Stale"),
    OFFLINE("OFFLINE", "Offline"),
    NEVER_REPORTED("NEVER_REPORTED", "Never reported"),
    NO_TRACKER("NO_TRACKER", "No tracker"),
    UNKNOWN("UNKNOWN", "Unknown"),
    ;

    companion object {
        fun from(raw: String?): Connectivity = entries.firstOrNull { it.wire == raw && it != UNKNOWN } ?: UNKNOWN
    }
}

/**
 * Freshness rules for owner screens. The server decides connectivity; the app only ever *downgrades* it: a machine
 * is shown as live only when the server says so in a response that is itself fresh (not from the offline cache and
 * not older than [LIVE_RESPONSE_MAX_AGE_MS]).
 */
object Freshness {
    const val LIVE_RESPONSE_MAX_AGE_MS = 2 * 60_000L

    fun displayConnectivity(serverValue: String?, serverIsLive: Boolean, source: DataSource, fetchedAtMs: Long, nowMs: Long): Connectivity {
        val c = Connectivity.from(serverValue)
        val responseFresh = source == DataSource.LIVE && nowMs - fetchedAtMs in 0..LIVE_RESPONSE_MAX_AGE_MS
        return if (c == Connectivity.LIVE && !(serverIsLive && responseFresh)) Connectivity.RECENT else c
    }

    /** "just now", "5 min ago", "3 h ago", "2 d ago" from an age in seconds (null = never). */
    fun ageLabel(ageSeconds: Long?): String = when {
        ageSeconds == null -> "never"
        ageSeconds < 60 -> "just now"
        ageSeconds < 3_600 -> "${ageSeconds / 60} min ago"
        ageSeconds < 86_400 -> "${ageSeconds / 3_600} h ago"
        else -> "${ageSeconds / 86_400} d ago"
    }

    fun ageSeconds(thenMs: Long?, nowMs: Long): Long? = thenMs?.let { ((nowMs - it) / 1000).coerceAtLeast(0) }
}
