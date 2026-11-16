package com.asseta.core.domain.finance

import java.math.BigDecimal
import java.math.RoundingMode
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

/**
 * Compact money as the ADR-008 designs write it, shared by the Supervisor and Owner apps (same rule as iOS): from a
 * million "5.2M" / "3.85M" / "2.0M" (at most two decimals, at least one), from a billion "1.2B", below a million the
 * grouped whole amount ("850,000").
 */
object CompactMoney {
    private val SYMBOLS = DecimalFormatSymbols.getInstance(Locale.US)
    private val MILLION = BigDecimal(1_000_000)
    private val BILLION = BigDecimal(1_000_000_000)

    fun format(value: BigDecimal): String {
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
}
