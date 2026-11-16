package com.asseta.owner.ui.common

import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.domain.reports.MachineReportRules
import java.math.BigDecimal
import java.math.RoundingMode
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.time.temporal.TemporalAdjusters
import java.util.Locale

/** A period of local days (both ends included). */
data class DayRange(val from: LocalDate, val to: LocalDate)

/** The Today / Week / Month choice of Money and Reports. */
enum class Period(val label: String) {
    TODAY("Today"), WEEK("Week"), MONTH("Month");

    /** The local days of this period up to [today]: the week starts on Monday, the month on the 1st. */
    fun range(today: LocalDate): DayRange = when (this) {
        TODAY -> DayRange(today, today)
        WEEK -> DayRange(today.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)), today)
        MONTH -> DayRange(today.withDayOfMonth(1), today)
    }
}

/**
 * ADR-008 figures as the designs write them: compact money ("5.2M", "3.85M", "2.0M owed"), whole money
 * ("TZS 3,800,000"), hours ("300 h", "12.5 h"), percentages and "today 07:40" style times. Same rules as iOS.
 */
object Figures {
    private val SYMBOLS = DecimalFormatSymbols.getInstance(Locale.US)
    private val TIME = DateTimeFormatter.ofPattern("HH:mm", Locale.US)
    private val DAY = DateTimeFormatter.ofPattern("d MMM", Locale.US)

    /** A decimal string from the wire; blank or malformed counts as 0. */
    fun dec(raw: String?): BigDecimal = raw?.trim()?.toBigDecimalOrNull() ?: BigDecimal.ZERO

    /** Sum of decimal strings. */
    fun sum(values: Iterable<String?>): BigDecimal = values.fold(BigDecimal.ZERO) { a, v -> a + dec(v) }

    /**
     * Compact money: from a million "5.2M" / "3.85M" / "2.0M" (at most two decimals, at least one), from a billion
     * "1.2B", below a million the grouped whole amount ("850,000").
     */
    fun compact(value: BigDecimal): String {
        val abs = value.abs()
        val sign = if (value.signum() < 0) "-" else ""
        fun scaled(divisor: BigDecimal, suffix: String): String {
            val v = abs.divide(divisor, 2, RoundingMode.HALF_UP)
            return sign + DecimalFormat("#,##0.0#", SYMBOLS).format(v) + suffix
        }
        return when {
            abs >= BILLION -> scaled(BILLION, "B")
            abs >= MILLION -> scaled(MILLION, "M")
            else -> sign + DecimalFormat("#,##0", SYMBOLS).format(abs.setScale(0, RoundingMode.HALF_UP))
        }
    }

    /** "TZS 3,800,000" (whole amounts) or "TZS 3,800,000.50" (cents only when there are some). */
    fun money(value: BigDecimal, currency: String): String {
        val whole = value.stripTrailingZeros().scale() <= 0
        return if (whole) "$currency ${DecimalFormat("#,##0", SYMBOLS).format(value.setScale(0, RoundingMode.HALF_UP))}" else OwnerFormat.money(value, currency)
    }

    /** "300 h", "12.5 h", "1,240 h". */
    fun hours(value: BigDecimal): String = "${MachineReportRules.formatHours(value)} h"

    /** Whole percent of [part] in [whole] ("73%"); null when [whole] is 0. */
    fun percent(part: BigDecimal, whole: BigDecimal): String? =
        if (whole.signum() <= 0) null else "${part.multiply(HUNDRED).divide(whole, 0, RoundingMode.HALF_UP).toPlainString()}%"

    /** "today 07:40", "yesterday 18:10", "2 days ago" (up to 6 days), then "12 Nov". */
    fun relative(raw: String?, nowMs: Long, zone: ZoneId): String {
        val at = OwnerFormat.parseInstant(raw) ?: return "—"
        val day = at.atZone(zone).toLocalDate()
        val today = Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate()
        return when (val days = ChronoUnit.DAYS.between(day, today)) {
            0L -> "today ${TIME.format(at.atZone(zone))}"
            1L -> "yesterday ${TIME.format(at.atZone(zone))}"
            in 2L..6L -> "$days days ago"
            else -> DAY.format(at.atZone(zone))
        }
    }

    /** "30 Nov" from a local date (`yyyy-MM-dd`); the raw text when malformed. */
    fun day(raw: String?): String = raw?.let { runCatching { DAY.format(LocalDate.parse(it)) }.getOrDefault(it) } ?: "—"

    /** "3 days" / "1 day". */
    fun days(n: Int): String = if (n == 1) "1 day" else "$n days"

    private val HUNDRED = BigDecimal(100)
    private val MILLION = BigDecimal(1_000_000)
    private val BILLION = BigDecimal(1_000_000_000)
}
