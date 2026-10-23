package com.asseta.core.domain.finance

import java.math.BigDecimal

/** Precision limits of the server's decimal columns (scale = decimal places, digits = total digits). */
enum class DecimalLimit(val scale: Int, val digits: Int) {
    MONEY(4, 18), // expense/collection/handover amount, fuel unit price
    LITRES(3, 12),
    METER_READING(2, 14),
}

enum class AmountError(val message: String) {
    EMPTY("Enter an amount."),
    NOT_A_NUMBER("Use digits and at most one decimal point (no thousands separators)."),
    NOT_POSITIVE("The amount must be greater than zero."),
    TOO_MANY_DECIMALS("Too many decimal places."),
    TOO_LARGE("The amount is too large."),
}

/** Field-specific wording of an [AmountError] (same sentences as the iOS app), e.g. "Enter the litres." */
fun AmountError.describe(what: String, limit: DecimalLimit): String = when (this) {
    AmountError.EMPTY -> "Enter the ${what.lowercase()}."
    AmountError.NOT_A_NUMBER -> "$what must be a number such as 1250.50."
    AmountError.NOT_POSITIVE -> "$what must be more than zero."
    AmountError.TOO_MANY_DECIMALS -> "$what may have at most ${limit.scale} decimals."
    AmountError.TOO_LARGE -> "$what is too large."
}

sealed interface AmountInput {
    data class Valid(val value: BigDecimal) : AmountInput
    data class Invalid(val error: AmountError) : AmountInput
}

/**
 * Parses user-entered decimals exactly (BigDecimal from the text; never via Float/Double). Accepts "," as the decimal
 * separator; rejects signs, exponents and grouping separators so "1,250.50" can never silently become 1.25.
 */
object AmountParser {
    private val PATTERN = Regex("^\\d+(\\.\\d+)?$")

    fun parse(raw: String, limit: DecimalLimit, allowZero: Boolean = false): AmountInput {
        val text = raw.trim().replace(',', '.')
        if (text.isEmpty()) return AmountInput.Invalid(AmountError.EMPTY)
        if (!PATTERN.matches(text)) return AmountInput.Invalid(AmountError.NOT_A_NUMBER)
        val value = BigDecimal(text)
        if (value.signum() == 0 && !allowZero) return AmountInput.Invalid(AmountError.NOT_POSITIVE)
        val normalized = value.stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }
        if (normalized.scale() > limit.scale) return AmountInput.Invalid(AmountError.TOO_MANY_DECIMALS)
        val integerDigits = normalized.precision() - normalized.scale()
        if (integerDigits > limit.digits - limit.scale) return AmountInput.Invalid(AmountError.TOO_LARGE)
        return AmountInput.Valid(normalized)
    }

    fun valueOrNull(raw: String, limit: DecimalLimit, allowZero: Boolean = false): BigDecimal? =
        (parse(raw, limit, allowZero) as? AmountInput.Valid)?.value
}

object CurrencyCode {
    private val PATTERN = Regex("^[A-Z]{3}$")

    /** Upper-cased ISO-4217 code, or null when not three letters. */
    fun normalize(raw: String): String? = raw.trim().uppercase().takeIf { PATTERN.matches(it) }
}

/** Formats an exact amount for display with its currency (plain digits, no float rounding). */
fun formatMoney(amount: BigDecimal, currency: String): String = "${amount.toPlainString()} $currency"

/** Case- and accent-insensitive multi-word search used by every picker over synced data. */
object SearchMatch {
    private val MARKS = Regex("\\p{Mn}+")

    fun normalize(text: String): String =
        java.text.Normalizer.normalize(text, java.text.Normalizer.Form.NFD).replace(MARKS, "").lowercase().trim()

    /** True when every word of [query] occurs in at least one of [fields]; a blank query matches everything. */
    fun matches(query: String, vararg fields: String?): Boolean {
        val words = normalize(query).split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.isEmpty()) return true
        val haystack = fields.filterNotNull().map(::normalize)
        return words.all { word -> haystack.any { it.contains(word) } }
    }
}
