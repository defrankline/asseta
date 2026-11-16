package com.asseta.owner.ui.accountability

import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.OwnerFormat
import java.math.BigDecimal
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Pure formatting shared by the accountability screens: days, money, hours and machine names (unit-tested). */
object RecordFormat {
    private val DAY = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.US)

    /** "2026-10-26" -> "26 Oct 2026" (unparseable input as is). */
    fun day(raw: String): String = runCatching { DAY.format(LocalDate.parse(raw.take(10))) }.getOrDefault(raw)

    fun money(amount: String?, currency: String): String =
        amount?.toBigDecimalOrNull()?.let { OwnerFormat.money(it, currency) } ?: "${amount.orEmpty()} $currency"

    /** "2.5" (no unit; the texts add " h"). */
    fun num(raw: String?): String = raw?.toBigDecimalOrNull()?.let { OwnerFormat.decimal(it.setScale(2, java.math.RoundingMode.HALF_EVEN)) } ?: (raw ?: "0")

    fun hours(raw: String?): String = "${num(raw)} h"

    fun nonZero(raw: String?): Boolean = (raw?.toBigDecimalOrNull() ?: BigDecimal.ZERO).signum() != 0

    fun machine(code: String?, name: String?, id: String): String = DisplayNames.machine(code, name, id).orEmpty()

    /** A note of at least 5 characters (server `Note`) for every decision. */
    fun noteValid(note: String): Boolean = note.trim().length >= DecisionMapper.METER_NOTE_MIN

    /** Days of a machine's day list: the last [days] local days up to [today] (today included). */
    fun window(today: LocalDate, days: Long = MACHINE_DAYS): Pair<LocalDate, LocalDate> = today.minusDays(days - 1) to today

    const val MACHINE_DAYS = 14L
}
