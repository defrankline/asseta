package com.asseta.core.domain.accountability

import java.math.BigDecimal

/** What "Pays for" on the collection form can name (same rules as iOS). */
data class CollectionLinkOption(
    /** The purchase id, or the client id of a purchase saved on this phone and not synced yet. */
    val id: String,
    val title: String,
    val subtitle: String?,
    /** The outbox operation of a purchase not synced yet; the collection waits for it. */
    val operationId: String? = null,
    /** An open invoice: what it still owes (the collection pays it up to this). Null for a purchase. */
    val invoiceBalance: BigDecimal? = null,
) {
    val isInvoice: Boolean get() = invoiceBalance != null
}

/** An open invoice delivered by sync, as the picker needs it. */
data class LinkableInvoice(val id: String, val number: String, val customerId: String, val currency: String, val balance: String)

/** A purchase recorded on this phone and not acknowledged yet (HOURS_PURCHASE outbox operation pending, sent or held). */
data class UnsyncedPurchase(val clientId: String, val customerId: String?, val hours: String, val operationId: String)

/** A synced open purchase as the picker needs it. */
data class LinkablePurchase(val id: String, val number: String, val customerId: String, val status: String, val remaining: String, val clientId: String? = null)

object CollectionLinks {
    const val CANCELLED = "CANCELLED"

    /** Newest synced first as delivered, then this phone's unsynced ones (one row per client id, none once it is synced); the customer's only; cancelled ones excluded. */
    fun options(
        customerId: String?,
        purchases: List<LinkablePurchase>,
        unsynced: List<UnsyncedPurchase>,
        invoices: List<LinkableInvoice> = emptyList(),
        currency: String = "",
    ): List<CollectionLinkOption> {
        if (customerId.isNullOrBlank()) return emptyList()
        val synced = purchases.filter { it.customerId == customerId && it.status != CANCELLED }.map {
            CollectionLinkOption(it.id, it.number, "${AccountabilityRules.plain(it.remaining.toBigDecimalOrNull() ?: BigDecimal.ZERO)} h left")
        }
        val known = purchases.flatMap { listOfNotNull(it.id, it.clientId) }.toSet()
        val local = unsynced.filter { it.customerId == customerId && it.clientId !in known }.distinctBy { it.clientId }.map {
            CollectionLinkOption(it.clientId, unsyncedTitle(it.hours), null, it.operationId)
        }
        return synced + local + invoiceOptions(customerId, invoices, currency)
    }

    /** The customer's open invoices in the collection's [currency] (the server refuses another currency), by invoice order as delivered. */
    private fun invoiceOptions(customerId: String, invoices: List<LinkableInvoice>, currency: String): List<CollectionLinkOption> =
        invoices.filter { it.customerId == customerId && it.currency.equals(currency, ignoreCase = true) }.mapNotNull { inv ->
            val balance = inv.balance.toBigDecimalOrNull()?.takeIf { it.signum() > 0 } ?: return@mapNotNull null
            CollectionLinkOption(inv.id, inv.number, invoiceSubtitle(balance, inv.currency), invoiceBalance = balance)
        }

    /** What a collection allocates to an invoice: at most what it owes, at most the cash received. */
    fun allocationAmount(amount: BigDecimal, balance: BigDecimal): BigDecimal = amount.min(balance)

    fun invoiceSubtitle(balance: BigDecimal, currency: String): String = "Invoice · ${AccountabilityRules.plain(balance)} $currency due"

    fun unsyncedTitle(hours: String): String = "Not synced yet · ${AccountabilityRules.plain(hours.toBigDecimalOrNull() ?: BigDecimal.ZERO)} h"
}
