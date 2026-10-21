package com.asseta.core.domain.finance

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal

class CashRulesTest {

    @Test
    fun amountsAreParsedExactlyAsBigDecimalNeverFloat() {
        // 0.1 + 0.2 is exactly 0.3 in decimal arithmetic (it is not with binary floats).
        val a = AmountParser.valueOrNull("0.1", DecimalLimit.MONEY)!!
        val b = AmountParser.valueOrNull("0,2", DecimalLimit.MONEY)!!
        assertEquals(0, (a + b).compareTo(BigDecimal("0.3")))
        assertEquals(BigDecimal("12345678901234.5678"), AmountParser.valueOrNull("12345678901234.5678", DecimalLimit.MONEY))
        assertEquals(BigDecimal("1250.5"), AmountParser.valueOrNull(" 1250.50 ", DecimalLimit.MONEY))
    }

    @Test
    fun malformedOrOutOfRangeAmountsAreRejected() {
        fun err(raw: String, limit: DecimalLimit = DecimalLimit.MONEY) = (AmountParser.parse(raw, limit) as AmountInput.Invalid).error
        assertEquals(AmountError.EMPTY, err(""))
        assertEquals(AmountError.NOT_A_NUMBER, err("1,250.50")) // grouping separator never silently accepted
        assertEquals(AmountError.NOT_A_NUMBER, err("1e3"))
        assertEquals(AmountError.NOT_A_NUMBER, err("-5"))
        assertEquals(AmountError.NOT_A_NUMBER, err("NaN"))
        assertEquals(AmountError.NOT_POSITIVE, err("0.00"))
        assertEquals(AmountError.TOO_MANY_DECIMALS, err("1.23456"))
        assertEquals(AmountError.TOO_MANY_DECIMALS, err("1.2345", DecimalLimit.LITRES))
        assertEquals(AmountError.TOO_LARGE, err("123456789012345"))
        assertTrue(AmountParser.parse("0", DecimalLimit.MONEY, allowZero = true) is AmountInput.Valid)
        assertEquals("TZS", CurrencyCode.normalize(" tzs "))
        assertNull(CurrencyCode.normalize("TZ"))
    }

    @Test
    fun collectionAndHandoverValidation() {
        val ok = CashRules.collection("cust", "250000", "tzs", " R-77 ", "") as FormCheck.Valid
        assertEquals(CashCollectionValues(BigDecimal("250000"), "TZS", "R-77", null), ok.value)
        val bad = CashRules.collection(null, "abc", "T", "x".repeat(121), "") as FormCheck.Invalid
        assertEquals(4, bad.messages.size)
        val handover = CashRules.handover("1000.5", "TZS", "", "To office") as FormCheck.Valid
        assertEquals(BigDecimal("1000.5"), handover.value.amount)
        assertTrue(CashRules.handover("0", "TZS", "", "") is FormCheck.Invalid)
    }

    @Test
    fun fuelRulesFollowEventType() {
        val purchase = CashRules.fuel(FuelEventType.PURCHASE, "40.5", "3000", "TZS", null, "", "Puma", "") as FormCheck.Valid
        assertEquals(BigDecimal("3000"), purchase.value.unitPrice)
        assertEquals(0, CashRules.fuelCost(purchase.value.litres, purchase.value.unitPrice!!).compareTo(BigDecimal("121500")))
        val issueWithoutMachine = CashRules.fuel(FuelEventType.ISSUE, "10", "2900", "TZS", null, "", "", "") as FormCheck.Invalid
        assertEquals(listOf("Choose the machine."), issueWithoutMachine.messages)
        val usage = CashRules.fuel(FuelEventType.USAGE, "12.125", "", "", "m1", "1234.25", "", "") as FormCheck.Valid
        assertNull(usage.value.unitPrice)
        assertNull(usage.value.currency)
        assertEquals(BigDecimal("1234.25"), usage.value.meterReading)
        val badMeter = CashRules.fuel(FuelEventType.USAGE, "1", "", "", "m1", "1.234", "", "") as FormCheck.Invalid
        assertTrue(badMeter.messages.single().startsWith("Meter reading"))
        assertTrue(CashRules.fuel(null, "", "", "", null, "", "", "") is FormCheck.Invalid)
    }

    @Test
    fun custodySummarySeparatesVerifiedFromUnsyncedRecords() {
        val synced = CustodyBalance("TZS", BigDecimal("500000"), BigDecimal("100000"), BigDecimal("20000"), null)
        val pending = listOf(
            PendingCashItem(PendingCashKind.COLLECTION, BigDecimal("250000.50"), "TZS"),
            PendingCashItem(PendingCashKind.HANDOVER, BigDecimal("50000"), "TZS"),
            PendingCashItem(PendingCashKind.CASH_EXPENSE, BigDecimal("12000.25"), "TZS"),
            PendingCashItem(PendingCashKind.COLLECTION, BigDecimal("10"), "USD"),
        )
        val lines = CustodySummary.lines(listOf(synced), pending)
        assertEquals(listOf("TZS", "USD"), lines.map { it.currency })
        val tzs = lines[0]
        assertEquals(BigDecimal("250000.50"), tzs.pendingCollections)
        // 500000 - 100000 - 20000 + 250000.50 - 50000 - 12000.25
        assertEquals(0, tzs.estimatedInHand.compareTo(BigDecimal("568000.25")))
        assertTrue(tzs.hasPending)
        assertNull(lines[1].synced)
        assertFalse(CustodySummary.lines(listOf(synced), emptyList()).single().hasPending)
    }

    @Test
    fun baseCurrencyHintAndSearch() {
        assertEquals("TZS", CustodySummary.baseCurrencyHint(listOf("TZS"), listOf("USD")))
        assertEquals("USD", CustodySummary.baseCurrencyHint(emptyList(), listOf("USD", "USD")))
        assertNull(CustodySummary.baseCurrencyHint(listOf("TZS", "USD"), emptyList()))
        assertTrue(SearchMatch.matches("road bui", "Road Builders Ltd", "C-01"))
        assertTrue(SearchMatch.matches("cafe", "Café Supplies"))
        assertTrue(SearchMatch.matches("  ", "anything"))
        assertFalse(SearchMatch.matches("road x", "Road Builders Ltd"))
        assertTrue(SearchMatch.matches("ex-01 excav", "EX-01", "Excavator 01"))
    }
}
