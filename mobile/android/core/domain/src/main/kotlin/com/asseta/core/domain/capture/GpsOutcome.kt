package com.asseta.core.domain.capture

import java.time.Instant

/**
 * The real result of the mandatory fresh GPS attempt for one capture. Coordinates exist only for [Fix]; failures carry
 * none and are never replaced by an older or invented location.
 */
sealed interface GpsOutcome {
    val status: String

    data class Fix(
        val latitude: Double,
        val longitude: Double,
        val accuracyM: Double?,
        val capturedAt: Instant,
        val provider: String?,
    ) : GpsOutcome {
        init {
            require(latitude in -90.0..90.0 && longitude in -180.0..180.0) { "Invalid coordinates" }
        }
        override val status: String get() = "FIX"
    }

    data object NoFix : GpsOutcome { override val status = "NO_FIX" }
    data object Timeout : GpsOutcome { override val status = "TIMEOUT" }
    data object PermissionDenied : GpsOutcome { override val status = "PERMISSION_DENIED" }
    data object Disabled : GpsOutcome { override val status = "DISABLED" }

    companion object {
        /** A provider may hand back a cached location; only a fix taken after the attempt started counts. */
        fun acceptFix(fixTime: Instant, attemptStartedAt: Instant, toleranceMs: Long = 2_000): Boolean =
            !fixTime.isBefore(attemptStartedAt.minusMillis(toleranceMs))

        fun describe(outcome: GpsOutcome): String = when (outcome) {
            is Fix -> "Location fixed (±${outcome.accuracyM?.let { Math.round(it).toString() } ?: "?"} m)"
            NoFix -> "No location fix: the reading will be recorded without location and reviewed."
            Timeout -> "Location timed out: the reading will be recorded without location and reviewed."
            PermissionDenied -> "Location permission denied: the reading will be recorded without location and reviewed."
            Disabled -> "Location is turned off: the reading will be recorded without location and reviewed."
        }
    }
}
