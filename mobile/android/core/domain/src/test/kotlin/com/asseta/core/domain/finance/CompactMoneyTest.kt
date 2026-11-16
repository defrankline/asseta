package com.asseta.core.domain.finance

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Test

class CompactMoneyTest {
    @Test
    fun `compact money follows the designs`() {
        assertEquals("5.2M", CompactMoney.format(BigDecimal("5200000")))
        assertEquals("3.85M", CompactMoney.format(BigDecimal("3845000")))
        assertEquals("2.0M", CompactMoney.format(BigDecimal("2000000")))
        assertEquals("850,000", CompactMoney.format(BigDecimal("850000")))
        assertEquals("950,000", CompactMoney.format(BigDecimal("950000")))
        assertEquals("1,200", CompactMoney.format(BigDecimal("1200")))
        assertEquals("0", CompactMoney.format(BigDecimal.ZERO))
        assertEquals("1.2B", CompactMoney.format(BigDecimal("1200000000")))
        assertEquals("-3.85M", CompactMoney.format(BigDecimal("-3850000")))
    }
}
