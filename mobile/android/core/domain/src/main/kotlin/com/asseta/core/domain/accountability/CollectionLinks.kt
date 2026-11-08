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
)

/** A purchase recorded on this phone (HOURS_PURCHASE outbox operation, not refused). */
data class UnsyncedPurchase(val clientId: String, val customerId: String?, val hours: String, val operationId: String)

/** A synced open purchase as the picker needs it. */
data class LinkablePurchase(val id: String, val number: String, val customerId: String, val status: String, val remaining: String)

object CollectionLinks {
    const val CANCELLED = "CANCELLED"

    /** Newest synced first as delivered, then this phone's unsynced ones; the customer's only; cancelled ones excluded. */
    fun options(customerId: String?, purchases: List<LinkablePurchase>, unsynced: List<UnsyncedPurchase>): List<CollectionLinkOption> {
        if (customerId.isNullOrBlank()) return emptyList()
        val synced = purchases.filter { it.customerId == customerId && it.status != CANCELLED }.map {
            CollectionLinkOption(it.id, it.number, "${AccountabilityRules.plain(it.remaining.toBigDecimalOrNull() ?: BigDecimal.ZERO)} h left")
        }
        val local = unsynced.filter { it.customerId == customerId }.map {
            CollectionLinkOption(it.clientId, unsyncedTitle(it.hours), null, it.operationId)
        }
        return synced + local
    }

    fun unsyncedTitle(hours: String): String = "Not synced yet · ${AccountabilityRules.plain(hours.toBigDecimalOrNull() ?: BigDecimal.ZERO)} h"
}
