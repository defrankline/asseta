package com.asseta.core.model

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.RoundingMode

class MoneyTest {
    private val json = Json

    @Test
    fun `parses and serializes as string without float conversion`() {
        val money = json.decodeFromString(Money.serializer(), """{"amount":"0.10","currency":"ZMW"}""")
        val sum = money + money + money
        assertEquals("0.30", sum.amount.toPlainString())
        assertEquals("""{"amount":"0.30","currency":"ZMW"}""", json.encodeToString(Money.serializer(), sum))
    }

    @Test
    fun `rejects json numbers so floats never enter money`() {
        assertThrows(SerializationException::class.java) {
            json.decodeFromString(Money.serializer(), """{"amount":0.1,"currency":"ZMW"}""")
        }
    }

    @Test
    fun `rejects exponent and garbage`() {
        listOf("1e3", "", "NaN", "1,000.00", " 1", "Infinity").forEach { raw ->
            assertThrows(IllegalArgumentException::class.java) { DecimalAmount.parse(raw) }
        }
    }

    @Test
    fun `large values keep exact precision`() {
        val a = DecimalAmount.parse("9999999999999999.99")
        assertEquals("10000000000000000.00", (a + DecimalAmount.parse("0.01")).toPlainString())
    }

    @Test
    fun `numeric equality ignores scale`() {
        assertEquals(DecimalAmount.parse("1.0"), DecimalAmount.parse("1.00"))
        assertEquals(DecimalAmount.parse("1.0").hashCode(), DecimalAmount.parse("1.00").hashCode())
    }

    @Test
    fun `rounding is explicit`() {
        val v = DecimalAmount.parse("2.345")
        assertEquals("2.35", v.rounded(2, RoundingMode.HALF_UP).toPlainString())
        assertEquals("2.34", v.rounded(2, RoundingMode.HALF_EVEN).toPlainString())
    }

    @Test
    fun `currency mismatch and invalid code rejected`() {
        val zmw = Money(DecimalAmount.of(1), "ZMW")
        assertThrows(IllegalArgumentException::class.java) { zmw + Money(DecimalAmount.of(1), "USD") }
        assertThrows(IllegalArgumentException::class.java) { Money(DecimalAmount.of(1), "usd") }
    }

    @Test
    fun `negative detection`() {
        assertTrue(DecimalAmount.parse("-0.01").isNegative())
    }
}
