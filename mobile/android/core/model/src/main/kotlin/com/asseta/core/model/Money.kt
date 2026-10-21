package com.asseta.core.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Exact decimal amount transported as a JSON string (e.g. "1250.50"), never as a binary float.
 * Rounding is always explicit and chosen by the caller (policies are server configuration, not app constants).
 */
@Serializable(with = DecimalAmountSerializer::class)
class DecimalAmount private constructor(val value: BigDecimal) : Comparable<DecimalAmount> {

    operator fun plus(other: DecimalAmount) = DecimalAmount(value.add(other.value))
    operator fun minus(other: DecimalAmount) = DecimalAmount(value.subtract(other.value))
    operator fun times(multiplier: DecimalAmount) = DecimalAmount(value.multiply(multiplier.value))

    fun rounded(scale: Int, mode: RoundingMode): DecimalAmount = DecimalAmount(value.setScale(scale, mode))

    fun isNegative(): Boolean = value.signum() < 0

    /** Plain string without exponent; the wire format. */
    fun toPlainString(): String = value.toPlainString()

    override fun compareTo(other: DecimalAmount): Int = value.compareTo(other.value)

    /** Numeric equality: "1.0" equals "1.00". */
    override fun equals(other: Any?): Boolean = other is DecimalAmount && value.compareTo(other.value) == 0

    override fun hashCode(): Int = value.stripTrailingZeros().hashCode()

    override fun toString(): String = toPlainString()

    companion object {
        private val PATTERN = Regex("^-?\\d+(\\.\\d+)?$")

        val ZERO = DecimalAmount(BigDecimal.ZERO)

        /** Parses a strict decimal string. Rejects exponents, blanks, NaN/Infinity and grouping separators. */
        fun parse(raw: String): DecimalAmount {
            require(PATTERN.matches(raw)) { "Not a decimal amount: '$raw'" }
            return DecimalAmount(BigDecimal(raw))
        }

        fun of(value: BigDecimal): DecimalAmount = DecimalAmount(value)

        fun of(value: Long): DecimalAmount = DecimalAmount(BigDecimal.valueOf(value))
    }
}

/** A monetary amount with its ISO-4217 currency. Arithmetic across currencies is rejected. */
@Serializable
data class Money(val amount: DecimalAmount, val currency: String) {
    init {
        require(CURRENCY.matches(currency)) { "Currency must be an ISO-4217 code: '$currency'" }
    }

    operator fun plus(other: Money): Money = sameCurrency(other).let { Money(amount + other.amount, currency) }
    operator fun minus(other: Money): Money = sameCurrency(other).let { Money(amount - other.amount, currency) }

    private fun sameCurrency(other: Money) =
        require(currency == other.currency) { "Currency mismatch: $currency vs ${other.currency}" }

}

private val CURRENCY = Regex("^[A-Z]{3}$")

object DecimalAmountSerializer : KSerializer<DecimalAmount> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.asseta.DecimalAmount", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: DecimalAmount) = encoder.encodeString(value.toPlainString())

    override fun deserialize(decoder: Decoder): DecimalAmount {
        val raw = decoder.decodeString()
        return try {
            DecimalAmount.parse(raw)
        } catch (e: IllegalArgumentException) {
            throw SerializationException(e.message)
        }
    }
}
