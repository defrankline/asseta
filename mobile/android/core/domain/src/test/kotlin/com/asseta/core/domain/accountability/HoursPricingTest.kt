package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.FormCheck
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
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
    fun `the server's minor units win over the ISO table`() {
        // A tenant whose TZS has no cents: 2.5 h x 33,333.3333 = 83,333.33325 -> 83,333.
        val noCents = HoursPriceBook(prices = mapOf("m" to HoursPrice("m", d("33333.3333"), d("0"), "TZS", minorUnits = 0)))
        val q = (HoursPricing.price(noCents, "m", null, false, "2.5") as HoursSalePrice.Priced).quote
        assertEquals(d("83333"), q.amount)
        assertEquals(0, q.minorUnits)
        // Without the field (an older server) the ISO table applies: 83,333.33.
        val iso = HoursPriceBook(prices = mapOf("m" to HoursPrice("m", d("33333.3333"), d("0"), "TZS")))
        assertEquals(d("83333.33"), (HoursPricing.price(iso, "m", null, false, "2.5") as HoursSalePrice.Priced).quote.amount)
        assertEquals("TZS 1,234.567", HoursPricing.money(d("1234.567"), "TZS", 3))
    }

    @Test
    fun `payment lines against the total`() {
        val price = HoursPricing.price(book, "ex01", null, false, "6") // 570,000
        fun s(vararg amounts: String) = HoursPayments.summary(amounts.map { PaymentLine(PaymentMethod.CASH, it, "") }, price)
        assertEquals(PaymentStatus.NotPaid, s().status)
        assertEquals(d("570000.00"), s().balance)
        assertEquals(PaymentStatus.FullyPaid, s("300000", "270000").status)
        assertEquals(PaymentStatus.PartPaid(d("270000.00")), s("300000").status)
        assertEquals(PaymentStatus.OverTotal, s("300000", "270000.01").status)
        assertEquals(d("0"), s("600000").balance!!.stripTrailingZeros())
        assertEquals(d("300000"), s("300000", "abc", "").paid) // a line without a valid amount counts as nothing yet
        assertEquals(PaymentStatus.NoTotal, HoursPayments.summary(listOf(PaymentLine(amountText = "5")), HoursSalePrice.Unpriced).status)
        // A new line takes what is still owed, once; without a total it starts empty.
        assertEquals(PaymentLine(PaymentMethod.CASH, "570000", ""), HoursPayments.newLine(emptyList(), price))
        assertEquals("270000", HoursPayments.newLine(listOf(PaymentLine(amountText = "300000")), price).amountText)
        assertEquals("", HoursPayments.newLine(listOf(PaymentLine(amountText = "570000")), price).amountText)
        assertEquals("", HoursPayments.newLine(emptyList(), HoursSalePrice.Unpriced).amountText)
    }

    @Test
    fun `the opening cash line follows the total until typed into`() {
        val opening = HoursPayments.opening()
        assertEquals(listOf(PaymentLine(PaymentMethod.CASH, "", "", followsTotal = true)), opening)
        // Total unknown: stays empty (and still needs an amount to save).
        assertEquals("", HoursPayments.follow(opening, HoursSalePrice.Hidden).single().amountText)
        assertEquals("", HoursPayments.follow(opening, HoursSalePrice.Unpriced).single().amountText)
        val six = HoursPayments.follow(opening, HoursPricing.price(book, "ex01", null, false, "6"))
        assertEquals("570000", six.single().amountText)
        assertEquals(PaymentStatus.FullyPaid, HoursPayments.summary(six, HoursPricing.price(book, "ex01", null, false, "6")).status)
        // Hours, customer (discount) and machine change the total: the line follows.
        val four = HoursPayments.follow(six, HoursPricing.price(book, "ex01", null, false, "4"))
        assertEquals("380000", four.single().amountText)
        assertEquals("342000", HoursPayments.follow(four, HoursPricing.price(book, "ex01", "acme", false, "4")).single().amountText)
        assertEquals("", HoursPayments.follow(four, HoursPricing.price(book, "zz", null, false, "4")).single().amountText)
        // Typed: never changed again.
        val typed = listOf(four.single().typed("100000"))
        assertEquals(PaymentLine(PaymentMethod.CASH, "100000", ""), typed.single())
        assertEquals(typed, HoursPayments.follow(typed, HoursPricing.price(book, "ex01", null, false, "6")))
        // Method changes keep it following; a later line is filled once and never follows.
        val bank = HoursPayments.follow(listOf(six.single().copy(method = PaymentMethod.BANK)), HoursPricing.price(book, "ex01", null, false, "4"))
        assertEquals(PaymentLine(PaymentMethod.BANK, "380000", "", followsTotal = true), bank.single())
        val added = HoursPayments.newLine(listOf(PaymentLine(amountText = "300000")), HoursPricing.price(book, "ex01", null, false, "6"))
        assertEquals(false, added.followsTotal)
        // Removed: no lines, not paid yet.
        assertEquals(PaymentStatus.NotPaid, HoursPayments.summary(emptyList(), HoursPricing.price(book, "ex01", null, false, "6")).status)
    }

    @Test
    fun `split rules`() {
        val price = HoursPricing.price(book, "ex01", null, false, "6")
        fun draft(vararg lines: PaymentLine) = HoursSaleDraft(false, "acme", "", "", "ex01", "6", lines.toList(), "")
        val cash = PaymentLine(PaymentMethod.CASH, "300000", "")
        val bank = PaymentLine(PaymentMethod.BANK, "270000", "")
        assertEquals(listOf(AccountabilityMessages.REFERENCE), (AccountabilityRules.hoursSale(draft(cash, bank), false, true, price) as FormCheck.Invalid).messages)
        assertEquals(
            listOf(AccountabilityMessages.NONCASH_OFF, AccountabilityMessages.REFERENCE),
            (AccountabilityRules.hoursSale(draft(cash, bank), false, false, price) as FormCheck.Invalid).messages,
        )
        val ok = AccountabilityRules.hoursSale(draft(cash, bank.copy(reference = "CRDB")), false, true, price) as FormCheck.Valid
        assertEquals(listOf(PaymentMethod.CASH, PaymentMethod.BANK), ok.value.payments.map { it.method })
        assertEquals(
            listOf(AccountabilityMessages.paymentsExceed("TZS 570,000")),
            (AccountabilityRules.hoursSale(draft(cash, cash), false, true, price) as FormCheck.Invalid).messages,
        )
        // Without a known total the server checks it.
        assertTrue(AccountabilityRules.hoursSale(draft(cash, cash), false, true, HoursSalePrice.Unpriced) is FormCheck.Valid)
        val eleven = draft(*Array(11) { PaymentLine(PaymentMethod.CASH, "1", "") })
        assertEquals(listOf(AccountabilityMessages.TOO_MANY_PAYMENTS), (AccountabilityRules.hoursSale(eleven, false) as FormCheck.Invalid).messages)
        assertTrue(AccountabilityRules.hoursSale(draft(cash), false) is FormCheck.Valid)
    }

    @Test
    fun `save blockers say why save is off`() {
        val price = HoursPricing.price(book, "ex01", null, false, "6")
        fun draft(vararg lines: PaymentLine, machine: String? = "ex01", hours: String = "6", customer: String? = "acme") =
            HoursSaleDraft(false, customer, "", "", machine, hours, lines.toList(), "")
        fun blockers(d: HoursSaleDraft, noncash: Boolean = true, p: HoursSalePrice = price) = AccountabilityRules.hoursSaleBlockers(d, false, noncash, p)
        val cash = PaymentLine(PaymentMethod.CASH, "300000", "")
        val bank = PaymentLine(PaymentMethod.BANK, "100000", "")
        val mobile = PaymentLine(PaymentMethod.MOBILE_MONEY, "170000", "")
        // Fully paid but the references are missing: Save is off and the line says why.
        assertEquals("To save: enter the reference for payments 2 and 3.", blockers(draft(cash, bank, mobile)))
        assertTrue(AccountabilityRules.referenceMissing(bank))
        assertEquals(false, AccountabilityRules.referenceMissing(cash))
        assertEquals(false, AccountabilityRules.referenceMissing(bank.copy(reference = "CRDB")))
        assertEquals("Enter the reference for this payment", AccountabilityMessages.REFERENCE_LINE)
        assertEquals(null, blockers(draft(cash, bank.copy(reference = "R1"), mobile.copy(reference = "R2"))))
        assertEquals("To save: enter the amount for payment 1.", blockers(draft(PaymentLine(PaymentMethod.CASH, "", ""))))
        assertEquals("To save: enter the amount for payments 1 and 2.", blockers(draft(PaymentLine(amountText = "abc"), PaymentLine(amountText = "0"))))
        assertEquals("To save: lower the payments to the total of TZS 570,000.", blockers(draft(cash, cash)))
        assertEquals(
            "To save: choose the machine and enter the hours (more than 0).",
            blockers(draft(PaymentLine(amountText = "5"), machine = null, hours = ""), p = HoursSalePrice.Hidden),
        )
        assertEquals("To save: choose the customer.", blockers(draft(customer = null)))
        assertEquals("To save: change payment 2 to cash and enter the reference for payment 2.", blockers(draft(cash, bank), noncash = false))
        assertEquals(null, blockers(draft())) // not paid yet
        assertEquals("To save: choose a registered customer.", AccountabilityRules.hoursSaleBlockers(
            HoursSaleDraft(true, null, "Juma", "", "ex01", "6", emptyList(), ""), walkInAllowed = false))
        assertEquals("payments 1, 2 and 3", AccountabilityMessages.payments(listOf(1, 2, 3)))
    }

    @Test
    fun `methods follow the tenant policy`() {
        val values = { noncash: String -> kotlinx.serialization.json.Json.parseToJsonElement(
            """{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false$noncash}""",
        ).jsonObject }
        val access = { policy: CustomerHoursPolicy? -> FieldAccess(setOf(com.asseta.core.model.sync.SyncCapabilities.OP_HOURS_PURCHASE), setOf("tenant.hours.purchase"), hours = policy) }
        val off = CustomerHoursPolicy.fromValues(values(""))
        val on = CustomerHoursPolicy.fromValues(values(""","field_noncash_payments":true"""))
        assertEquals(listOf(PaymentMethod.CASH), access(off).saleMethods)
        assertEquals(PaymentMethod.entries, access(on).saleMethods)
        assertEquals(listOf(PaymentMethod.CASH), access(CustomerHoursPolicy.fromValues(values(""","field_noncash_payments":false"""))).saleMethods)
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
