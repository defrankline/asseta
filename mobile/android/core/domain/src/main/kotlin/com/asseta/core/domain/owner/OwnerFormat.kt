package com.asseta.core.domain.owner

import java.math.BigDecimal
import java.math.RoundingMode
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Currency
import java.util.Locale

/**
 * Display formatting for owner screens. Money stays exact (BigDecimal from the wire string) and is shown with the
 * currency's ISO-4217 minor units (TZS/KES/USD 2, JPY 0, BHD 3) using half-even rounding for display only; storage
 * scale (4 dp) is never shown. Instants are rendered in the tenant's timezone from the overview when known.
 */
object OwnerFormat {
    fun minorUnits(currency: String): Int =
        runCatching { Currency.getInstance(currency).defaultFractionDigits }.getOrNull()?.takeIf { it >= 0 } ?: 2

    fun money(amount: BigDecimal, currency: String, locale: Locale = Locale.US): String {
        val digits = minorUnits(currency)
        val format = DecimalFormat("#,##0" + if (digits > 0) "." + "0".repeat(digits) else "", DecimalFormatSymbols.getInstance(locale))
        return "$currency ${format.format(amount.setScale(digits, RoundingMode.HALF_EVEN))}"
    }

    /** Hours (exact decimal string) trimmed to at most 2 dp: "12.5000" -> "12.5 h". Null -> "—". */
    fun hours(value: BigDecimal?): String {
        if (value == null) return "—"
        val v = value.setScale(2, RoundingMode.HALF_EVEN).stripTrailingZeros()
        return "${if (v.scale() < 0) v.setScale(0).toPlainString() else v.toPlainString()} h"
    }

    private val dateTime = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.US)
    private val time = DateTimeFormatter.ofPattern("HH:mm", Locale.US)

    /** Parses a server instant (ISO-8601 with offset/Z); null when absent or malformed. */
    fun parseInstant(raw: String?): Instant? = raw?.let { runCatching { java.time.OffsetDateTime.parse(it).toInstant() }.getOrNull() }

    fun zone(timezone: String?): ZoneId = timezone?.let { runCatching { ZoneId.of(it) }.getOrNull() } ?: ZoneId.systemDefault()

    fun dateTime(instant: Instant?, zone: ZoneId): String = instant?.let { dateTime.format(it.atZone(zone)) } ?: "—"

    fun dateTime(raw: String?, zone: ZoneId): String = dateTime(parseInstant(raw), zone)

    fun time(instant: Instant, zone: ZoneId): String = time.format(instant.atZone(zone))

    /** "Offline — data from 21 Oct 2026, 14:05 (stale)" style label for cached snapshots. */
    fun staleBanner(fetchedAtMs: Long, zone: ZoneId): String =
        "Offline — data from ${dateTime(Instant.ofEpochMilli(fetchedAtMs), zone)} (stale)"

    /** Server enum values ("TRACKER_OFFLINE") as readable words ("Tracker offline"). */
    fun humanize(raw: String): String = raw.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
}
