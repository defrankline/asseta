package com.asseta.core.sync

import com.asseta.core.domain.accountability.HoursPricing
import com.asseta.core.domain.accountability.HoursSalePrice
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.engine.SyncReport
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.math.BigDecimal

/** SYNC_HOURS_PRICES on the phone: machine rates and customer discounts stored, replaced on every pull, cleared without it. */
@RunWith(RobolectricTestRunner::class)
class HoursPricesSyncTest : SyncTestBase() {
    private val ex01 = "d0000000-0000-4000-8000-000000000001"
    private val ex02 = "d0000000-0000-4000-8000-000000000002"
    private val acme = "c0000000-0000-4000-8000-000000000001"
    private val other = "c0000000-0000-4000-8000-000000000002"
    private val on = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.SYNC_HOURS_PRICES)

    private fun price(machine: String, rate: String, currency: String = "TZS", minorUnits: Int? = 2) = buildJsonObject {
        put("machine_id", machine); put("rate_card_id", "e0000000-0000-4000-8000-000000000001"); put("hourly_rate", rate)
        put("minimum_hours", "0.0000"); put("currency", currency); minorUnits?.let { put("minor_units", it) }
        put("effective_from", "2026-01-01T00:00:00Z")
    }

    @Test
    fun theServersMinorUnitsAreKeptAndAnOlderServerFallsBackToIso() {
        fake.capabilities = on
        fake.inbox = mapOf("hours_prices" to listOf(price(ex01, "33333.3333", minorUnits = 0), price(ex02, "33333.3333", "UGX", minorUnits = null)))
        synced()
        val book = book()
        assertEquals(0, book.prices.getValue(ex01).minorUnits)
        assertEquals(0, book.prices.getValue(ex02).minorUnits) // UGX from the ISO table
        val q = (HoursPricing.price(book, ex01, null, walkIn = false, hoursText = "2.5") as HoursSalePrice.Priced).quote
        assertEquals(BigDecimal("83333"), q.amount)
    }

    private fun discount(customer: String, percent: String) = buildJsonObject { put("customer_id", customer); put("percent", percent) }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun book() = runBlocking { financeRepository.observeHoursPrices(tenant).first() }

    @Test
    fun pricesAreStoredReplacedAndClearedWithoutTheCapability() {
        fake.capabilities = on
        fake.inbox = mapOf(
            "hours_prices" to listOf(price(ex01, "95000.0000"), price(ex02, "120000.0000")),
            "customer_discounts" to listOf(discount(acme, "10.00"), discount(other, "5.00")),
        )
        synced()
        var book = book()
        assertEquals(setOf(ex01, ex02), book.prices.keys)
        assertEquals(BigDecimal("95000.0000"), book.prices.getValue(ex01).hourlyRate)
        assertEquals(BigDecimal("10.00"), book.discounts.getValue(acme))
        val total = HoursPricing.price(book, ex01, acme, walkIn = false, hoursText = "6") as HoursSalePrice.Priced
        assertEquals(BigDecimal("513000.00"), total.quote.amount)

        // The next pull replaces both sets: a rate changes, a machine and a discount leave.
        fake.inbox = mapOf("hours_prices" to listOf(price(ex01, "100000.0000")), "customer_discounts" to listOf(discount(other, "7.50")))
        synced()
        book = book()
        assertEquals(setOf(ex01), book.prices.keys)
        assertEquals(BigDecimal("100000.0000"), book.prices.getValue(ex01).hourlyRate)
        assertEquals(mapOf(other to BigDecimal("7.50")), book.discounts)
        assertEquals(HoursSalePrice.Unpriced, HoursPricing.price(book, ex02, acme, walkIn = false, hoursText = "6"))

        // An empty snapshot leaves nothing.
        fake.inbox = emptyMap()
        synced()
        assertTrue(book().prices.isEmpty() && book().discounts.isEmpty())

        // Without the capability (switched off, or an older server) nothing is kept.
        fake.inbox = mapOf("hours_prices" to listOf(price(ex01, "95000")), "customer_discounts" to listOf(discount(acme, "10")))
        synced()
        assertEquals(1, book().prices.size)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(book().prices.isEmpty() && book().discounts.isEmpty())
    }
}
