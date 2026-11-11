package com.asseta.core.domain.finance

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import java.math.BigDecimal

/**
 * The part of the tenant `PETTY_CASH` policy snapshot the field app shows or hides UI by (DEC-033; the server applies
 * every rule). Lenient: a missing or unreadable key reads as off / none, so an unknown policy never adds requirements
 * the server does not have and never hides the feature itself (the sync capability does that).
 */
data class PettyCashPolicy(
    val countWitnessRequired: Boolean = false,
    val returnEvidenceRequired: Boolean = false,
    val advancesEnabled: Boolean = false,
    /** An expense above this (in the tenant's base currency) always needs a human approval; null = no maximum. */
    val maxExpenseAmount: BigDecimal? = null,
    /** An advance or expense above what the fund has is still recorded at sync (missing = on, the platform default). */
    val overspendAllowedOffline: Boolean = true,
) {
    companion object {
        const val TYPE = "PETTY_CASH"

        fun fromValues(values: JsonObject?): PettyCashPolicy {
            if (values == null) return PettyCashPolicy()
            fun flag(key: String) = (values[key] as? JsonPrimitive)?.booleanOrNull ?: false
            val max = (values["max_expense_amount"] as? JsonPrimitive)?.contentOrNull?.toBigDecimalOrNull()?.takeIf { it.signum() > 0 }
            val overspend = (values["overspend_allowed_offline"] as? JsonPrimitive)?.booleanOrNull ?: true
            return PettyCashPolicy(flag("count_witness_required"), flag("return_evidence_required"), flag("advances_enabled"), max, overspend)
        }
    }
}

/** Why a human must look at an expense (`control_flags`), in neutral words shared by both apps and iOS. */
object ExpenseFlags {
    const val TITLE = "To check"
    const val OVERSPEND = "OVERSPEND"
    const val SPENT_FROM_COLLECTIONS = "SPENT_FROM_COLLECTIONS"
    const val ABOVE_PETTY_CASH_MAXIMUM = "ABOVE_PETTY_CASH_MAXIMUM"

    fun label(code: String): String = when (code) {
        OVERSPEND -> "Recorded above what the fund had available"
        SPENT_FROM_COLLECTIONS -> "Paid from collected cash"
        ABOVE_PETTY_CASH_MAXIMUM -> "Above the petty cash maximum per expense"
        else -> code.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    fun labels(codes: List<String>): List<String> = codes.filter { it.isNotBlank() }.distinct().map(::label)

    /** `paid_from` PETTY_CASH in lists and details. */
    const val PAID_FROM_PETTY_CASH = "Petty cash"
}

/** Validation wording of the petty cash forms (docs/requirements/accountability-mobile-strings.md, DEC-033). */
object PettyCashMessages {
    const val AMOUNT = "Enter the amount (more than 0)."
    const val COUNTED = "Enter the cash counted (0 or more)."
    const val CHANGE = "Enter the change handed back (0 or more)."
    const val ABOVE_REASON = "Enter the reason for going above the limit (at least 3 characters)."
    const val EVIDENCE = "Photograph the slip or the cash."
    const val REASON = "Enter a reason (at least 3 characters)."
    const val ACK_RECEIVED = "Enter the amount you received (0 or more)."
    const val DISPUTE_REASON = "Say why you dispute it."
    const val FUND_REQUIRED = "Choose the petty cash fund."
    const val ADVANCE_REQUIRED = "Choose the advance this was paid from."

    const val RECIPIENT = "Choose who receives the advance."
    const val PURPOSE = "Enter the purpose (at least 3 characters)."

    fun currency(currency: String) = "The fund holds $currency."
    fun giveOverspend(available: String) = "Above what the fund has available ($available): it is recorded when the phone syncs and marked for the office to check."
    fun giveOverspendBlocked(available: String) = "Above what the fund has available ($available). Your company does not allow this offline."
    fun overspend(available: String) = "Above what the fund has available ($available): it is kept for approval and marked for the approver to check."
    fun aboveMaximum(maximum: String) = "Above the petty cash maximum per expense ($maximum): a manager must approve it."
}

data class AdvanceValues(val recipientId: String, val amount: BigDecimal, val purpose: String)

data class TopUpValues(val amount: BigDecimal?, val note: String?, val aboveCapReason: String?)
data class ReturnValues(val amount: BigDecimal, val reference: String?, val note: String?)
data class AckAnswer(val amountReceived: BigDecimal?, val note: String?)

/** A fund the phone can pay an expense from: one I hold, or the fund of an advance given to me. */
data class FundChoice(val id: String, val currency: String, val available: BigDecimal?, val held: Boolean)

/** An advance given to me, spendable from its fund. */
data class AdvanceChoice(val id: String, val fundId: String, val remaining: BigDecimal)

/** Offline checks of the petty cash forms and of an expense paid from a fund (the server re-validates everything). */
object PettyCashRules {
    const val MIN_REASON = 3
    const val MAX_NOTE = 1000
    const val MAX_REFERENCE = 120
    const val MAX_PHOTOS = 10
    const val MIN_WITNESS_SEARCH = 2

    fun note(text: String): String? = text.trim().take(MAX_NOTE).ifEmpty { null }

    /** "500.00" + TZS -> "500 TZS" (the field app's money style). */
    fun money(value: BigDecimal, currency: String): String =
        value.stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }.toPlainString() + " " + currency

    /** What brings the fund to its limit (limit - balance, never below 0); null when unknown. */
    fun headroom(limit: String?, balance: String?): BigDecimal? {
        val l = limit?.toBigDecimalOrNull() ?: return null
        val b = balance?.toBigDecimalOrNull() ?: return null
        return (l - b).max(BigDecimal.ZERO)
    }

    /** The amount asks for more than [headroom]: the reason for going above becomes required. */
    fun aboveCap(amountText: String, headroom: BigDecimal?): Boolean {
        val amount = AmountParser.valueOrNull(amountText, DecimalLimit.MONEY) ?: return false
        return headroom != null && amount > headroom
    }

    /** Acknowledge: the amount received (0 or more). Dispute: a reason is required and no amount is sent. */
    fun acknowledgement(acknowledge: Boolean, receivedText: String, note: String): FormCheck<AckAnswer> {
        val text = note(note)
        if (!acknowledge) return if (text == null) FormCheck.Invalid(listOf(PettyCashMessages.DISPUTE_REASON)) else FormCheck.Valid(AckAnswer(null, text))
        val received = AmountParser.valueOrNull(receivedText, DecimalLimit.MONEY, allowZero = true)
            ?: return FormCheck.Invalid(listOf(PettyCashMessages.ACK_RECEIVED))
        return FormCheck.Valid(AckAnswer(received, text))
    }

    /** Top-up request: amount optional (empty = the server's suggestion); above [headroom] needs the reason. */
    fun topUp(amountText: String, note: String, aboveReason: String, headroom: BigDecimal?): FormCheck<TopUpValues> {
        val m = mutableListOf<String>()
        val amount = if (amountText.isBlank()) null else AmountParser.valueOrNull(amountText, DecimalLimit.MONEY).also { if (it == null) m += PettyCashMessages.AMOUNT }
        val above = amount != null && headroom != null && amount > headroom
        val reason = aboveReason.trim().take(MAX_NOTE)
        if (above && reason.length < MIN_REASON) m += PettyCashMessages.ABOVE_REASON
        return if (m.isEmpty()) FormCheck.Valid(TopUpValues(amount, note(note), reason.takeIf { above && it.isNotEmpty() })) else FormCheck.Invalid(m)
    }

    fun returnFund(amountText: String, reference: String, note: String, photos: Int, evidenceRequired: Boolean): FormCheck<ReturnValues> {
        val m = mutableListOf<String>()
        val amount = AmountParser.valueOrNull(amountText, DecimalLimit.MONEY)
        if (amount == null) m += PettyCashMessages.AMOUNT
        if (evidenceRequired && photos == 0) m += PettyCashMessages.EVIDENCE
        val ref = reference.trim().take(MAX_REFERENCE).ifEmpty { null }
        return if (m.isEmpty()) FormCheck.Valid(ReturnValues(amount!!, ref, note(note))) else FormCheck.Invalid(m)
    }

    fun count(countedText: String): FormCheck<BigDecimal> =
        AmountParser.valueOrNull(countedText, DecimalLimit.MONEY, allowZero = true)?.let { FormCheck.Valid(it) }
            ?: FormCheck.Invalid(listOf(PettyCashMessages.COUNTED))

    fun advanceClear(changeText: String): FormCheck<BigDecimal> =
        AmountParser.valueOrNull(changeText, DecimalLimit.MONEY, allowZero = true)?.let { FormCheck.Valid(it) }
            ?: FormCheck.Invalid(listOf(PettyCashMessages.CHANGE))

    /**
     * Giving an advance: a recipient other than the holder, an amount, a purpose (3+ characters). Above [available] it is
     * refused when the tenant does not allow overspending offline ([currency] names the fund's money in the message).
     */
    fun giveAdvance(
        recipientId: String?, holderId: String, amountText: String, purpose: String, available: BigDecimal?, currency: String,
        policy: PettyCashPolicy,
    ): FormCheck<AdvanceValues> {
        val m = mutableListOf<String>()
        if (recipientId.isNullOrBlank() || recipientId == holderId) m += PettyCashMessages.RECIPIENT
        val amount = AmountParser.valueOrNull(amountText, DecimalLimit.MONEY)
        if (amount == null) m += PettyCashMessages.AMOUNT
        val text = purpose.trim().take(MAX_NOTE)
        if (text.length < MIN_REASON) m += PettyCashMessages.PURPOSE
        giveNote(amount, available, currency, policy)?.takeIf { !policy.overspendAllowedOffline }?.let { m += it }
        return if (m.isEmpty()) FormCheck.Valid(AdvanceValues(recipientId!!, amount!!, text)) else FormCheck.Invalid(m)
    }

    /** The note when the advance is above what the fund has available (allowed offline, or the reason it is blocked). */
    fun giveNote(amount: BigDecimal?, available: BigDecimal?, currency: String, policy: PettyCashPolicy): String? {
        if (amount == null || available == null || amount <= available) return null
        val text = money(available.max(BigDecimal.ZERO), currency)
        return if (policy.overspendAllowedOffline) PettyCashMessages.giveOverspend(text) else PettyCashMessages.giveOverspendBlocked(text)
    }

    /** Taking over a fund: accept (note optional) or decline with a reason. */
    fun holderDecision(accept: Boolean, note: String): FormCheck<String?> {
        val text = note(note)
        if (!accept && (text == null || text.length < MIN_REASON)) return FormCheck.Invalid(listOf(PettyCashMessages.REASON))
        return FormCheck.Valid(text)
    }

    /** Blocking issues of an expense paid from a fund: the fund (and, for a fund I do not hold, the advance) and its currency. */
    fun expenseIssues(fund: FundChoice?, advance: AdvanceChoice?, currency: String?): List<String> = buildList {
        if (fund == null) {
            add(PettyCashMessages.FUND_REQUIRED)
            return@buildList
        }
        if (!fund.held && advance == null) add(PettyCashMessages.ADVANCE_REQUIRED)
        if (currency != null && currency != fund.currency) add(PettyCashMessages.currency(fund.currency))
    }

    /**
     * Notes shown before saving (never blocking: an offline overspend is kept for approval and flagged by the server):
     * above what the fund (or the advance) has available, and above the per-expense maximum (base currency only).
     */
    fun expenseNotes(fund: FundChoice?, advance: AdvanceChoice?, amount: BigDecimal?, baseCurrency: String?, policy: PettyCashPolicy): List<String> {
        if (fund == null || amount == null) return emptyList()
        return buildList {
            val available = advance?.remaining ?: fund.available
            if (available != null && amount > available) add(PettyCashMessages.overspend(money(available.max(BigDecimal.ZERO), fund.currency)))
            val max = policy.maxExpenseAmount
            if (max != null && baseCurrency != null && fund.currency == baseCurrency && amount > max) add(PettyCashMessages.aboveMaximum(money(max, fund.currency)))
        }
    }
}
