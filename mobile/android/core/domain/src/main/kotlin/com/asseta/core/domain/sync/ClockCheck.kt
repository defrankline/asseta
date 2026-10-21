package com.asseta.core.domain.sync

import kotlin.math.abs

/** Trusted time reference: the last server time and the monotonic elapsed-since-boot clock at that moment. */
data class ClockAnchor(val serverEpochMs: Long, val elapsedRealtimeMs: Long)

sealed interface ClockStatus {
    /** No anchor yet, or the device rebooted since (monotonic clock reset), so nothing can be concluded. */
    data object Unknown : ClockStatus

    data class Checked(val skewSeconds: Long, val alert: Boolean) : ClockStatus
}

/**
 * Local clock-tamper alert. Expected wall time = anchor server time + monotonic time elapsed since the anchor; a device
 * clock further away than the threshold is flagged in the UI. The device still records and sends its own true clock.
 */
object ClockCheck {
    const val DEFAULT_ALERT_SECONDS = 300L

    fun evaluate(
        anchor: ClockAnchor?,
        wallNowMs: Long,
        elapsedNowMs: Long,
        alertSeconds: Long = DEFAULT_ALERT_SECONDS,
    ): ClockStatus {
        if (anchor == null || elapsedNowMs < anchor.elapsedRealtimeMs) return ClockStatus.Unknown
        val expected = anchor.serverEpochMs + (elapsedNowMs - anchor.elapsedRealtimeMs)
        val skewSeconds = (wallNowMs - expected) / 1000
        return ClockStatus.Checked(skewSeconds, abs(wallNowMs - expected) > alertSeconds * 1000)
    }
}
