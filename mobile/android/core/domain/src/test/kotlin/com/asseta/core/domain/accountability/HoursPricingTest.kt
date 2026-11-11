package com.asseta.core.domain.accountability

import org.junit.Assert.assertEquals
import org.junit.Test
import java.math.BigDecimal

/** The hours sale price rule on the phone (same cases as iOS `HoursPricingTests`). */
class HoursPricingTest {
    private fun d(text: String) = BigDecimal(text)
    private val book = HoursPriceBook(
        prices = mapOf(
            "ex01" to HoursPrice("ex01", d("95000.0000"), d("0"), "TZS"),
            "ug01" to HoursPrice("ug01", d("33333.3333"), d("0"), "UGX"),
            "kw01" to HoursPrice("kw01", d("12.3456"), d("0"), "KWD"),
        ),
        discounts = mapOf("acme" to d("10.00"), "odd" to d("12.5")),
    )

    private fun quote(machine: String, customer: String?, hours: String, walkIn: Boolean = false) =
        (HoursPricing.price(book, machine, customer, walkIn, hours) as HoursSalePrice.Priced).quote

    @Test
    fun `total is hours times the rate rounded to the currency`() {
        val q = quote("ex01", null, "6")
        assertEquals(d("95000.0000"), q.effectiveRate)
        assertEquals(d("570000.00"), q.amount)
        assertEquals("TZS", q.currency)
        assertEquals(d("0"), q.discountPercent)
        // Half-up to the currency's minor units: 2.25 h x 33,333.3333 = 74,999.999925 -> 75,000 (UGX has none).
        assertEquals(d("75000"), quote("ug01", null, "2.25").amount)
        // KWD keeps 3: 1.5 x 12.3456 = 18.5184 -> 18.518.
        assertEquals(d("18.518"), quote("kw01", null, "1.5").amount)
        assertEquals(d("0.005"), HoursPricing.quote(d("0.01"), d("0.5"), d("0"), "KWD").amount)
        assertEquals(d("0.01"), HoursPricing.quote(d("1"), d("0.005"), d("0"), "TZS").amount) // 0.005 -> 0.01, half-up
    }

    @Test
    fun `discount comes off the rate, rounded to four decimals half-even`() {
        val q = quote("ex01", "acme", "6")
        assertEquals(d("85500.0000"), q.effectiveRate)
        assertEquals(d("513000.00"), q.amount)
        assertEquals(d("10.00"), q.discountPercent)
        // 95,000 x 87.5 / 100 = 83,125
        assertEquals(d("83125.0000"), quote("ex01", "odd", "1").effectiveRate)
        // A tie at 4 decimals goes to the even digit (Python's default context): 1.00005 -> 1.0000, 1.00015 -> 1.0002.
        assertEquals(d("1.0000"), HoursPricing.effectiveRate(d("1.00005"), d("0")))
        assertEquals(d("1.0002"), HoursPricing.effectiveRate(d("1.00015"), d("0")))
        // 2.0001 x 50% = 1.00005 -> 1.0000
        assertEquals(d("1.0000"), HoursPricing.effectiveRate(d("2.0001"), d("50")))
        assertEquals(d("0.0000"), HoursPricing.effectiveRate(d("95000"), d("100")))
    }

    @Test
    fun `walk-in and unknown customers pay the full rate`() {
        assertEquals(d("570000.00"), quote("ex01", "acme", "6", walkIn = true).amount)
        assertEquals(d("570000.00"), quote("ex01", "nobody", "6").amount)
        assertEquals(d("570000.00"), quote("ex01", null, "6").amount)
    }

    @Test
    fun `nothing shows without a machine or hours, the office prices a machine without a rate`() {
        assertEquals(HoursSalePrice.Hidden, HoursPricing.price(book, null, "acme", false, "6"))
        assertEquals(HoursSalePrice.Hidden, HoursPricing.price(book, "ex01", "acme", false, ""))
        assertEquals(HoursSalePrice.Hidden, HoursPricing.price(book, "ex01", "acme", false, "0"))
        assertEquals(HoursSalePrice.Hidden, HoursPricing.price(book, "ex01", "acme", false, "1.234"))
        assertEquals(HoursSalePrice.Hidden, HoursPricing.price(book, "ex01", "acme", false, "abc"))
        assertEquals(HoursSalePrice.Unpriced, HoursPricing.price(book, "none", "acme", false, "6"))
        assertEquals(HoursSalePrice.Unpriced, HoursPricing.price(HoursPriceBook(), "ex01", null, true, "6"))
    }

    @Test
    fun `minor units and figures`() {
        assertEquals(2, HoursPricing.minorUnits("TZS"))
        assertEquals(0, HoursPricing.minorUnits("ugx"))
        assertEquals(3, HoursPricing.minorUnits("KWD"))
        assertEquals(2, HoursPricing.minorUnits("XYZ"))
        assertEquals("TZS 570,000", HoursPricing.money(d("570000.00"), "TZS"))
        assertEquals("USD 1,234.50", HoursPricing.money(d("1234.50"), "USD"))
        assertEquals("UGX 75,000", HoursPricing.money(d("75000"), "UGX"))
        assertEquals("KWD 18.518", HoursPricing.money(d("18.518"), "KWD"))
        assertEquals("95,000", HoursPricing.rate(d("95000.0000")))
        assertEquals("33,333.3333", HoursPricing.rate(d("33333.3333")))
        assertEquals("6", HoursPricing.figure(d("6")))
        assertEquals("1,234.5", HoursPricing.figure(d("1234.50")))
        assertEquals("12.5", HoursPricing.figure(d("12.50")))
    }
}
