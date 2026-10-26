package com.asseta.core.domain.accountability

/**
 * DEC-031 D2: how a remittance reached the company and the tenant's requirements on it (CASH_CUSTODY policy keys
 * `remittance_account_required`, `remittance_reference_required`, `remittance_evidence_required`; all off by default).
 * The form enforces them so the supervisor fixes the handover before it is saved; the server applies them again.
 */
data class RemittanceRequirements(
    val accountRequired: Boolean = false,
    /** Only for bank deposits and mobile money; cash to the office never needs a reference. */
    val referenceRequired: Boolean = false,
    val evidenceRequired: Boolean = false,
)

enum class RemittanceMethod(val wire: String, val accountType: String) {
    CASH_TO_OFFICE("CASH_TO_OFFICE", "CASH_OFFICE"),
    BANK_DEPOSIT("BANK_DEPOSIT", "BANK"),
    MOBILE_MONEY("MOBILE_MONEY", "MOBILE_MONEY"),
    ;

    val nonCash: Boolean get() = this != CASH_TO_OFFICE

    companion object {
        fun ofWire(wire: String?): RemittanceMethod? = entries.firstOrNull { it.wire == wire }
        fun ofAccountType(type: String?): RemittanceMethod? = entries.firstOrNull { it.accountType == type }
    }
}

/** A company deposit account as the picker shows it. */
data class DepositAccountOption(
    val id: String,
    val name: String,
    val accountType: String,
    val institution: String?,
    val accountNumberMasked: String?,
    val currency: String,
    val isActive: Boolean,
) {
    /** "{institution} · {masked}" with missing parts left out. */
    val subtitle: String get() = listOfNotNull(institution?.takeIf { it.isNotBlank() }, accountNumberMasked?.takeIf { it.isNotBlank() }).joinToString(" · ")
}

object RemittanceRules {
    const val ERR_ACCOUNT = "Choose the company account the money was paid into."
    const val ERR_REFERENCE = "Enter the transaction reference of the bank deposit or mobile-money payment."
    const val ERR_EVIDENCE = "Photograph the deposit slip or payment confirmation."
    const val ERR_ACCOUNT_MISMATCH = "The account you chose does not match how the money was handed over."
    const val ERR_ACCOUNT_CURRENCY = "The account you chose holds a different currency."
    const val ERR_ACCOUNT_GONE = "The account you chose is no longer in use. Choose another one."
    const val MAX_EVIDENCE = 10

    /** Active accounts in [currency] (case-insensitive) that match [method], by name. */
    fun accountsFor(accounts: List<DepositAccountOption>, method: RemittanceMethod, currency: String): List<DepositAccountOption> =
        accounts.filter { it.isActive && it.accountType == method.accountType && it.currency.equals(currency.trim(), ignoreCase = true) }
            .sortedBy { it.name.lowercase() }

    fun referenceRequired(req: RemittanceRequirements, method: RemittanceMethod): Boolean = req.referenceRequired && method.nonCash

    /**
     * Why the remittance cannot be saved yet (empty = fine). [account] is the chosen account (null = none);
     * [accountId] non-null with [account] null means it is no longer on the phone (deactivated).
     */
    fun check(
        req: RemittanceRequirements,
        method: RemittanceMethod,
        accountId: String?,
        account: DepositAccountOption?,
        currency: String,
        reference: String,
        photoCount: Int,
    ): List<String> {
        val messages = mutableListOf<String>()
        when {
            accountId != null && (account == null || !account.isActive) -> messages += ERR_ACCOUNT_GONE
            account != null && account.accountType != method.accountType -> messages += ERR_ACCOUNT_MISMATCH
            account != null && !account.currency.equals(currency.trim(), ignoreCase = true) -> messages += ERR_ACCOUNT_CURRENCY
            accountId == null && req.accountRequired -> messages += ERR_ACCOUNT
        }
        if (referenceRequired(req, method) && reference.isBlank()) messages += ERR_REFERENCE
        if (req.evidenceRequired && photoCount == 0) messages += ERR_EVIDENCE
        if (photoCount > MAX_EVIDENCE) messages += "At most $MAX_EVIDENCE photos per handover."
        return messages
    }
}
