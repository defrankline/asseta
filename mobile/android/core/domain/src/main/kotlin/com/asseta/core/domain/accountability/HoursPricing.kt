package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import java.math.BigDecimal
import java.math.RoundingMode
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

/**
 * A machine's current hourly rate as the last pull delivered it (SYNC_HOURS_PRICES). [minorUnits]: the decimal places the
 * server rounds the currency to (`HoursPriceDto.minor_units`; the ISO table when an older server leaves it out).
 */
data class HoursPrice(
    val machineId: String,
    val hourlyRate: BigDecimal,
    val minimumHours: BigDecimal,
    val currency: String,
    val minorUnits: Int = HoursPricing.minorUnits(currency),
)

/** The prices on this phone: machine rates by machine id, approved discounts (percent) by customer id. */
data class HoursPriceBook(val prices: Map<String, HoursPrice> = emptyMap(), val discounts: Map<String, BigDecimal> = emptyMap())

/** What a sale costs: the rate card less the discount, times the hours, rounded to the currency (as the server prices it). */
data class HoursSaleQuote(
    val hours: BigDecimal,
    val hourlyRate: BigDecimal,
    val discountPercent: BigDecimal,
    val effectiveRate: BigDecimal,
    val amount: BigDecimal,
    val currency: String,
    val minorUnits: Int = HoursPricing.minorUnits(currency),
)

/** What the hours sale form shows under Hours. */
sealed interface HoursSalePrice {
    /** No machine yet, or no hours (or not a valid number): nothing is shown. */
    data object Hidden : HoursSalePrice

    /** The machine has no price on this phone: the office prices the sale when it arrives. */
    data object Unpriced : HoursSalePrice

    data class Priced(val quote: HoursSaleQuote) : HoursSalePrice
}

/**
 * The server's price rule for an hours sale, applied on the phone so the total shows offline (same rules as iOS
 * `HoursPricing`): effective rate = hourly rate x (100 - discount) / 100, rounded to 4 decimals (half-even); total =
 * hours x effective rate, rounded half-up to the currency's minor units (the server's, sent with the price). A walk-in
 * has no discount.
 */
object HoursPricing {
    private val HUNDRED = BigDecimal(100)
    private val ZERO_DECIMALS = setOf("BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF")
    private val THREE_DECIMALS = setOf("BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND")

    /** Fallback when the server did not send `minor_units`: ISO 4217 (TZS 2, UGX 0, KWD 3); 2 for a code not listed. */
    fun minorUnits(currency: String): Int = when (currency.trim().uppercase()) {
        in ZERO_DECIMALS -> 0
        in THREE_DECIMALS -> 3
        else -> 2
    }

    fun effectiveRate(hourlyRate: BigDecimal, discountPercent: BigDecimal): BigDecimal =
        (hourlyRate * (HUNDRED - discountPercent)).divide(HUNDRED).setScale(4, RoundingMode.HALF_EVEN)

    fun quote(
        hours: BigDecimal,
        hourlyRate: BigDecimal,
        discountPercent: BigDecimal,
        currency: String,
        minorUnits: Int = minorUnits(currency),
    ): HoursSaleQuote {
        val effective = effectiveRate(hourlyRate, discountPercent)
        val amount = (hours * effective).setScale(minorUnits.coerceIn(0, 6), RoundingMode.HALF_UP)
        return HoursSaleQuote(hours, hourlyRate, discountPercent, effective, amount, currency, minorUnits.coerceIn(0, 6))
    }

    /** The form's price line: hidden until a machine and hours are entered; [walkIn] sales get no discount. */
    fun price(book: HoursPriceBook, machineId: String?, customerId: String?, walkIn: Boolean, hoursText: String): HoursSalePrice {
        if (machineId.isNullOrBlank()) return HoursSalePrice.Hidden
        val hours = AccountabilityRules.saleHours(hoursText)?.takeIf { it.signum() > 0 } ?: return HoursSalePrice.Hidden
        val price = book.prices[machineId] ?: return HoursSalePrice.Unpriced
        val discount = if (walkIn || customerId == null) BigDecimal.ZERO else book.discounts[customerId] ?: BigDecimal.ZERO
        return HoursSalePrice.Priced(quote(hours, price.hourlyRate, discount.max(BigDecimal.ZERO), price.currency, price.minorUnits))
    }

    /** "TZS 570,000"; "USD 12.50" when there are cents ([minorUnits] decimals). */
    fun money(amount: BigDecimal, currency: String, minorUnits: Int = minorUnits(currency)): String {
        val digits = if (amount.stripTrailingZeros().scale() <= 0) 0 else minorUnits
        return "$currency ${number(amount.setScale(digits, RoundingMode.HALF_UP), digits, digits)}"
    }

    /** An hourly rate or an amount without its currency: grouping, up to 4 decimals ("95,000", "85,500.5"). */
    fun rate(value: BigDecimal): String = number(value, 0, 4)

    /** Hours or a percent: grouping, up to 2 decimals ("6", "12.5"). */
    fun figure(value: BigDecimal): String = number(value, 0, 2)

    private fun number(value: BigDecimal, min: Int, max: Int): String {
        val format = DecimalFormat("#,##0", DecimalFormatSymbols.getInstance(Locale.US)).apply {
            minimumFractionDigits = min
            maximumFractionDigits = max
            roundingMode = RoundingMode.HALF_EVEN
            isParseBigDecimal = true
        }
        return format.format(value)
    }
}

/** Where the payment lines of a sale stand against its offline total. */
sealed interface PaymentStatus {
    data object NotPaid : PaymentStatus
    data object FullyPaid : PaymentStatus
    data class PartPaid(val balance: BigDecimal) : PaymentStatus
    /** The parts add up to more than the total: saving is blocked. */
    data object OverTotal : PaymentStatus
    /** Paid something, but the total is not known on this phone (the office prices the sale). */
    data object NoTotal : PaymentStatus
}

/** What is paid so far, the total when known, and the status. */
data class PaymentSummary(val paid: BigDecimal, val quote: HoursSaleQuote?, val status: PaymentStatus) {
    val balance: BigDecimal? get() = quote?.let { (it.amount - paid).max(BigDecimal.ZERO) }
}

/** Payment lines of an hours sale (same rules as iOS `HoursPayments`). */
object HoursPayments {
    /** `HoursPurchaseIn.payments` takes at most 10 parts. */
    const val MAX = 10

    /** The lines' valid amounts added up (a line without a valid amount counts as nothing yet). */
    fun paid(lines: List<PaymentLine>): BigDecimal =
        lines.fold(BigDecimal.ZERO) { sum, line -> sum + (AmountParser.valueOrNull(line.amountText, DecimalLimit.MONEY) ?: BigDecimal.ZERO) }

    fun summary(lines: List<PaymentLine>, price: HoursSalePrice): PaymentSummary {
        val paid = paid(lines)
        val quote = (price as? HoursSalePrice.Priced)?.quote
        val status = when {
            paid.signum() == 0 -> PaymentStatus.NotPaid
            quote == null -> PaymentStatus.NoTotal
            paid > quote.amount -> PaymentStatus.OverTotal
            paid.compareTo(quote.amount) == 0 -> PaymentStatus.FullyPaid
            else -> PaymentStatus.PartPaid(quote.amount - paid)
        }
        return PaymentSummary(paid, quote, status)
    }

    /**
     * A new line: [method], with its amount set to what is still owed when the total is known (empty otherwise). The
     * amount is filled once, when the line is added; typed values are never changed afterwards.
     */
    fun newLine(lines: List<PaymentLine>, price: HoursSalePrice, method: PaymentMethod = PaymentMethod.CASH): PaymentLine {
        val balance = summary(lines, price).balance?.takeIf { it.signum() > 0 }
        return PaymentLine(method, balance?.let(AccountabilityRules::plain).orEmpty(), "")
    }
}
