package com.asseta.core.domain.accountability

import com.asseta.core.model.owner.MySiteCheckinsDto
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** A slot's state on the phone: the server's, or [SAVED] when a check-in saved on this phone (not synced) covers it. */
enum class SlotState { MADE, SAVED, MISSED, DUE, UPCOMING }

/** One scheduled check-in as the phone shows it ([from]..[to] is the window around [at]). */
data class SlotView(val at: Instant, val from: Instant, val to: Instant, val state: SlotState)

/** What the Jobs tab says about today's check-ins. */
sealed interface CheckinSummary {
    data class Due(val until: Instant) : CheckinSummary
    data class Next(val at: Instant) : CheckinSummary
    data object NoneLeft : CheckinSummary
}

/**
 * Site check-ins on the phone (DEC-031 M3; same rules as iOS). The schedule comes from the last online read
 * (`GET /site-checkins/mine`, saved for offline use); each slot's state is recomputed from the clock and the
 * check-ins known so the screen stays right offline: a check-in inside the window (scheduled ± window) makes the slot
 * MADE (confirmed by the server) or SAVED (only on this phone); otherwise MISSED once the window has ended, DUE
 * while it is open, UPCOMING before. Pure, unit-tested.
 */
object SiteCheckinRules {
    fun instant(raw: String?): Instant? = raw?.let { runCatching { OffsetDateTime.parse(it).toInstant() }.getOrNull() }

    fun zone(saved: MySiteCheckinsDto?): ZoneId =
        saved?.timezone?.let { runCatching { ZoneId.of(it) }.getOrNull() } ?: ZoneId.systemDefault()

    /**
     * Today's slots (in the tenant's timezone) in time order. [confirmed]: check-in times the server has (its list and
     * this phone's acked check-ins); [pending]: this phone's check-ins not synced yet.
     */
    fun today(saved: MySiteCheckinsDto?, confirmed: List<Instant>, pending: List<Instant>, now: Instant): List<SlotView> {
        saved ?: return emptyList()
        val zone = zone(saved)
        val day = now.atZone(zone).toLocalDate()
        return saved.slots.mapNotNull { slot ->
            val at = instant(slot.scheduledAt) ?: return@mapNotNull null
            if (at.atZone(zone).toLocalDate() != day) return@mapNotNull null
            val window = java.time.Duration.ofMinutes(slot.windowMinutes.toLong().coerceAtLeast(0))
            val from = at.minus(window)
            val to = at.plus(window)
            fun inside(t: Instant) = !t.isBefore(from) && !t.isAfter(to)
            val state = when {
                slot.status == "MADE" || confirmed.any(::inside) -> SlotState.MADE
                pending.any(::inside) -> SlotState.SAVED
                !now.isBefore(to) -> SlotState.MISSED
                !now.isBefore(from) -> SlotState.DUE
                else -> SlotState.UPCOMING
            }
            SlotView(at, from, to, state)
        }.sortedBy { it.at }
    }

    /** The Jobs tab line: a slot due now (until its window ends), else the next upcoming one, else none left. */
    fun summary(slots: List<SlotView>): CheckinSummary =
        slots.firstOrNull { it.state == SlotState.DUE }?.let { CheckinSummary.Due(it.to) }
            ?: slots.firstOrNull { it.state == SlotState.UPCOMING }?.let { CheckinSummary.Next(it.at) }
            ?: CheckinSummary.NoneLeft

    private val TIME = DateTimeFormatter.ofPattern("HH:mm", Locale.US)
    private val DATE_TIME = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.US)

    fun time(at: Instant, zone: ZoneId): String = TIME.format(at.atZone(zone))

    fun dateTime(at: Instant, zone: ZoneId): String = DATE_TIME.format(at.atZone(zone))

    /** Distance in whole metres ("42"). */
    fun metres(distance: Double): String = Math.round(distance).toString()
}
