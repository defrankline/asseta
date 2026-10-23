package com.asseta.core.domain.finance

import java.math.BigDecimal
import java.time.Instant

enum class FuelEventType(val label: String) {
    PURCHASE("Purchase (bought from a supplier)"),
    ISSUE("Issue (from stock into a machine)"),
    USAGE("Usage (consumption log, no cost)"),
}

/** Validation outcome of a cash/fuel form: the exact values to send, or the messages to show. */
sealed interface FormCheck<out T> {
    data class Valid<T>(val value: T) : FormCheck<T>
    data class Invalid(val messages: List<String>) : FormCheck<Nothing>
}

data class CashCollectionValues(val amount: BigDecimal, val currency: String, val reference: String?, val note: String?)

data class CashHandoverValues(val amount: BigDecimal, val currency: String, val reference: String?, val note: String?)

data class FuelValues(
    val litres: BigDecimal,
    val unitPrice: BigDecimal?,
    val currency: String?,
    val meterReading: BigDecimal?,
    val supplier: String?,
    val note: String?,
)

/** Offline rules for cash collections, handovers and fuel events (mirrors the server DTO validation). */
object CashRules {
    const val MAX_REFERENCE = 120
    const val MAX_NOTE = 1000

    fun collection(customerId: String?, amountText: String, currency: String, reference: String, note: String): FormCheck<CashCollectionValues> {
        val messages = mutableListOf<String>()
        if (customerId.isNullOrBlank()) messages += "Choose the customer who paid."
        val amount = money(amountText, messages)
        val code = currency(currency, messages)
        val ref = optionalText(reference, MAX_REFERENCE, "reference", messages)
        val text = optionalText(note, MAX_NOTE, "note", messages)
        return if (messages.isEmpty()) FormCheck.Valid(CashCollectionValues(amount!!, code!!, ref, text)) else FormCheck.Invalid(messages)
    }

    fun handover(amountText: String, currency: String, reference: String, note: String): FormCheck<CashHandoverValues> {
        val messages = mutableListOf<String>()
        val amount = money(amountText, messages)
        val code = currency(currency, messages)
        val ref = optionalText(reference, MAX_REFERENCE, "reference", messages)
        val text = optionalText(note, MAX_NOTE, "note", messages)
        return if (messages.isEmpty()) FormCheck.Valid(CashHandoverValues(amount!!, code!!, ref, text)) else FormCheck.Invalid(messages)
    }

    /**
     * ISSUE and USAGE need a machine (PURCHASE without one goes into stock); PURCHASE and ISSUE need a unit price;
     * USAGE carries no price. Litres > 0 with at most 3 decimals; meter reading at most 2 decimals.
     */
    fun fuel(
        type: FuelEventType?,
        litresText: String,
        unitPriceText: String,
        currency: String,
        machineId: String?,
        meterText: String,
        supplier: String,
        note: String,
    ): FormCheck<FuelValues> {
        val messages = mutableListOf<String>()
        if (type == null) messages += "Choose the kind of fuel event."
        val litres = when (val parsed = AmountParser.parse(litresText, DecimalLimit.LITRES)) {
            is AmountInput.Valid -> parsed.value
            is AmountInput.Invalid -> null.also { messages += parsed.error.describe("Litres", DecimalLimit.LITRES) }
        }
        if (type != null && type != FuelEventType.PURCHASE && machineId.isNullOrBlank()) messages += "Choose the machine or job the fuel went to."
        val priced = type == FuelEventType.PURCHASE || type == FuelEventType.ISSUE
        val unitPrice = if (priced) {
            when (val parsed = AmountParser.parse(unitPriceText, DecimalLimit.MONEY, allowZero = true)) {
                is AmountInput.Valid -> parsed.value
                is AmountInput.Invalid -> null.also { messages += parsed.error.describe("Unit price", DecimalLimit.MONEY) }
            }
        } else null
        val code = if (priced) currency(currency, messages) else null
        val meter = meterText.takeIf { it.isNotBlank() }?.let {
            when (val parsed = AmountParser.parse(it, DecimalLimit.METER_READING, allowZero = true)) {
                is AmountInput.Valid -> parsed.value
                is AmountInput.Invalid -> null.also { messages += parsed.error.describe("Meter reading", DecimalLimit.METER_READING) }
            }
        }
        val supplierText = optionalText(supplier, 200, "supplier", messages)
        val noteText = optionalText(note, MAX_NOTE, "note", messages)
        return if (messages.isEmpty()) {
            FormCheck.Valid(FuelValues(litres!!, unitPrice, code, meter, supplierText, noteText))
        } else {
            FormCheck.Invalid(messages)
        }
    }

    /** Litres x unit price, exact (shown before saving; the server computes the attributed cost itself). */
    fun fuelCost(litres: BigDecimal, unitPrice: BigDecimal): BigDecimal = litres.multiply(unitPrice)

    private fun money(text: String, messages: MutableList<String>): BigDecimal? =
        when (val parsed = AmountParser.parse(text, DecimalLimit.MONEY)) {
            is AmountInput.Valid -> parsed.value
            is AmountInput.Invalid -> null.also { messages += parsed.error.describe("Amount", DecimalLimit.MONEY) }
        }

    private fun currency(text: String, messages: MutableList<String>): String? =
        CurrencyCode.normalize(text).also { if (it == null) messages += "Enter a 3-letter currency code." }

    private fun optionalText(text: String, max: Int, what: String, messages: MutableList<String>): String? {
        val trimmed = text.trim()
        if (trimmed.length > max) messages += "The $what is too long (max $max characters)."
        return trimmed.takeIf { it.isNotEmpty() }
    }
}

/** Server-owned custody balance for one currency, as last synced. */
data class CustodyBalance(
    val currency: String,
    val outstanding: BigDecimal,
    val claimedUnverifiedHandovers: BigDecimal,
    val pendingSpending: BigDecimal,
    val asOf: Instant?,
)

enum class PendingCashKind { COLLECTION, HANDOVER, CASH_EXPENSE }

/** A cash movement recorded on this device that the server has not acknowledged yet. */
data class PendingCashItem(val kind: PendingCashKind, val amount: BigDecimal, val currency: String)

/**
 * One currency of the "My cash" view. [synced] is the server's verified view; the pending sums are unsynced device
 * records (not verified by anyone yet). [estimatedInHand] is an estimate of the cash physically held: the synced
 * outstanding minus claimed handovers and expenses awaiting approval (already out of the supervisor's hands), adjusted
 * by the unsynced records. It is never presented as a verified figure.
 */
data class CustodyLine(
    val currency: String,
    val synced: CustodyBalance?,
    val pendingCollections: BigDecimal,
    val pendingHandovers: BigDecimal,
    val pendingCashExpenses: BigDecimal,
) {
    val hasPending: Boolean get() = listOf(pendingCollections, pendingHandovers, pendingCashExpenses).any { it.signum() != 0 }

    val estimatedInHand: BigDecimal
        get() = (synced?.let { it.outstanding - it.claimedUnverifiedHandovers - it.pendingSpending } ?: BigDecimal.ZERO) +
            pendingCollections - pendingHandovers - pendingCashExpenses
}

object CustodySummary {
    fun lines(balances: List<CustodyBalance>, pending: List<PendingCashItem>): List<CustodyLine> {
        val currencies = (balances.map { it.currency } + pending.map { it.currency }).distinct().sorted()
        return currencies.map { currency ->
            fun sum(kind: PendingCashKind) = pending.filter { it.currency == currency && it.kind == kind }
                .fold(BigDecimal.ZERO) { acc, item -> acc + item.amount }
            CustodyLine(
                currency = currency,
                synced = balances.firstOrNull { it.currency == currency },
                pendingCollections = sum(PendingCashKind.COLLECTION),
                pendingHandovers = sum(PendingCashKind.HANDOVER),
                pendingCashExpenses = sum(PendingCashKind.CASH_EXPENSE),
            )
        }
    }

    /**
     * The device's best knowledge of the tenant currency: the single custody currency (the server reports the tenant
     * currency when the supervisor has no movements), else the single currency of the assigned jobs; otherwise unknown.
     */
    fun baseCurrencyHint(custodyCurrencies: Collection<String>, jobCurrencies: Collection<String>): String? =
        custodyCurrencies.distinct().singleOrNull() ?: jobCurrencies.distinct().singleOrNull()
}
